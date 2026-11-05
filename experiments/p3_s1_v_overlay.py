#!/usr/bin/env python3
"""Burn captions derived from an actual P3 trace onto its MuJoCo video."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _last_status(trace: list[dict], index: int, key: str) -> str:
    for row in reversed(trace[: index + 1]):
        value = row.get(key)
        if value:
            return f"{value} @ {row.get('time_s', 0.0):.1f}s"
    return "pending"


def _unwrapped_yaw(trace: list[dict]) -> list[float | None]:
    values: list[float | None] = []
    previous: float | None = None
    total = 0.0
    for row in trace:
        yaw = row.get("yaw_rad")
        if yaw is None:
            values.append(None)
            continue
        yaw = float(yaw)
        if previous is not None:
            total += (yaw - previous + 3.141592653589793) % (2.0 * 3.141592653589793) - 3.141592653589793
        values.append(total)
        previous = yaw
    return values


def overlay(result_path: Path, source: Path, output: Path, *, zoom_crop: bool = False) -> int:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    trace = result["trace"]
    yaw_sweep = _unwrapped_yaw(trace)
    width = int(result.get("video_width", 640))
    height = int(result.get("video_height", 480))
    fps = int(result.get("video_fps", 25))
    frame_bytes = width * height * 3
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font_size = max(17, round(height * 0.028))
    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(source), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        stdout=subprocess.PIPE,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(output)],
        stdin=subprocess.PIPE,
    )
    assert decoder.stdout is not None and encoder.stdin is not None
    frames = 0
    try:
        while True:
            raw = decoder.stdout.read(frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                raise RuntimeError(f"truncated RGB frame at index {frames}: {len(raw)} bytes")
            trace_index = min(frames * 2, len(trace) - 1)
            row = trace[trace_index]
            snr = result.get("ebn0_db")
            snr_text = "ideal" if result.get("phase") == "r0s" else (
                "no noise" if snr is None else f"{float(snr):g} dB"
            )
            lines = [
                f"Current Goal: {result.get('target_color', 'red')}",
                f"Robot State: {row.get('controller_state', row.get('state', 'unknown'))}",
                f"Heading: {math_degrees(row.get('yaw_rad'))} deg   Search sweep: {math_degrees(yaw_sweep[trace_index])} deg",
                f"Eb/N0: {snr_text}",
                f"OBS: {_last_status(trace, trace_index, 'obs_frame_status')}   "
                f"CMD: {_last_status(trace, trace_index, 'cmd_frame_status')}",
            ]
            image = Image.frombytes("RGB", (width, height), raw)
            if zoom_crop:
                image = image.crop((round(width * 0.125), round(height * 0.21),
                                    round(width * 0.875), round(height * 0.96))).resize(
                    (width, height), Image.Resampling.LANCZOS
                )
            draw = ImageDraw.Draw(image)
            header_h = max(108, round(height * 0.20))
            draw.rectangle((0, 0, width, header_h), fill=(12, 16, 22))
            line_gap = round(font_size * 1.35)
            for line_no, text in enumerate(lines):
                draw.text((18, 10 + line_no * line_gap), text, font=font, fill=(245, 247, 250))
            encoder.stdin.write(image.tobytes())
            frames += 1
    finally:
        decoder.stdout.close()
        decoder_code = decoder.wait()
        encoder.stdin.close()
        encoder_code = encoder.wait()
    if decoder_code or encoder_code:
        raise RuntimeError(f"ffmpeg failed: decode={decoder_code}, encode={encoder_code}")
    expected = result.get("video_frame_count")
    if expected is not None and frames != expected:
        raise RuntimeError(f"video/trace frame mismatch: rendered={frames}, expected={expected}")
    return frames


def math_degrees(value: float | None) -> str:
    return "unknown" if value is None else f"{float(value) * 180.0 / 3.141592653589793:.1f}"


def split_view(wide: Path, first_person: Path, output: Path, result_path: Path, *, expected_frames: int) -> int:
    """Synchronously place the full third-person view beside the robot camera."""
    import numpy as np

    result = json.loads(result_path.read_text(encoding="utf-8"))
    trace = result["trace"]
    wide_size = (int(result.get("video_width", 640)), int(result.get("video_height", 480)))
    # Keep the sensor image's 4:3 aspect ratio within a vertically centered panel.
    fp_size = (round(wide_size[1] * 2 / 3), round(wide_size[1] / 2))
    panel_width = fp_size[0] + 24
    canvas_size = (wide_size[0] + panel_width, wide_size[1])
    camera_data = np.load(first_person)
    camera_frames, camera_times = camera_data["rgb"], camera_data["time_s"]
    camera_rows = [row for row in trace if row.get("camera_sample")]
    if len(camera_frames) != len(camera_times) or len(camera_rows) != len(camera_frames):
        raise RuntimeError("first-person camera frames do not match trace camera samples")
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(wide), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        stdout=subprocess.PIPE,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{canvas_size[0]}x{canvas_size[1]}", "-r", str(result.get("video_fps", 25)), "-i", "pipe:0", "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(output)],
        stdin=subprocess.PIPE,
    )
    frame_bytes = wide_size[0] * wide_size[1] * 3
    assert decoder.stdout is not None and encoder.stdin is not None
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font_size = max(16, round(wide_size[1] * 0.028))
    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
    count = 0
    try:
        while True:
            raw = decoder.stdout.read(frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                raise RuntimeError(f"truncated wide frame at index {count}")
            if count >= expected_frames:
                raise RuntimeError("wide-view video has more frames than its trace")
            trace_index = min(count * 2, len(trace) - 1)
            capture_time = float(trace[trace_index]["time_s"]) - 0.02
            camera_index = int(np.argmin(np.abs(camera_times - capture_time)))
            fp_rgb = Image.fromarray(camera_frames[camera_index]).resize(
                fp_size, Image.Resampling.BILINEAR
            )
            canvas = Image.new("RGB", canvas_size, (12, 16, 22))
            canvas.paste(Image.frombytes("RGB", wide_size, raw), (0, 0))
            panel_x = wide_size[0] + 12
            panel_y = (wide_size[1] - fp_size[1]) // 2
            canvas.paste(fp_rgb, (panel_x, panel_y))
            draw = ImageDraw.Draw(canvas)
            draw.text((panel_x, max(8, panel_y - font_size - 8)), "Robot camera | synchronized",
                      font=font, fill=(245, 247, 250))
            encoder.stdin.write(canvas.tobytes())
            count += 1
    finally:
        decoder.stdout.close()
        decoder.wait()
        encoder.stdin.close()
        code = encoder.wait()
    if code:
        raise RuntimeError(f"split-view ffmpeg encoder failed ({code})")
    if count != expected_frames:
        raise RuntimeError(f"split-view frame count {count} != expected {expected_frames}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--zoom-crop", action="store_true")
    parser.add_argument("--first-person-frames", type=Path)
    parser.add_argument("--split-output", type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    frames = overlay(args.result, args.input, args.output, zoom_crop=args.zoom_crop)
    payload = {"output": str(args.output), "frames": frames, "zoom_crop": args.zoom_crop}
    if args.first_person_frames or args.split_output:
        if not args.first_person_frames or not args.split_output:
            parser.error("--first-person-frames and --split-output must be used together")
        split_frames = split_view(args.output, args.first_person_frames, args.split_output,
                                  args.result, expected_frames=int(result["video_frame_count"]))
        payload.update({"split_output": str(args.split_output), "split_frames": split_frames})
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

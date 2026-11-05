#!/usr/bin/env python3
"""Prepare trace-linked P3 videos, static screenshots, figures and website JSON."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"
VIDEO_DIR = WEBSITE / "assets/video"
IMAGE_DIR = WEBSITE / "assets/img"
DATA_DIR = WEBSITE / "assets/data"
RUN_ROOT = Path("artifacts/p3_s1_v2_industrial/randomized_seed_20261105")

RUNS = {
    "ideal": {
        "stage": "s1-1", "video": "s1-1_B_-30deg_seed0_captioned.mp4",
        "split": None, "label": "ideal-message", "ebn0_db": None,
    },
    "noiseless": {
        "stage": "s1-2", "video": "s1-2_B_-30deg_seed0_captioned.mp4",
        "split": None, "label": "qpsk-noiseless", "ebn0_db": None,
    },
    "awgn-8db": {
        "stage": "s1-3", "video": "s1-3_B_-30deg_seed0_captioned.mp4",
        "split": "s1-3_B_-30deg_seed0_split_view.mp4", "label": "qpsk-awgn",
        "ebn0_db": 8.0,
    },
}

IMAGE_SOURCES = {
    "industrial-overview.png": RUN_ROOT / "s1-0/scene_overview.png",
    "industrial-front.png": RUN_ROOT / "s1-0/view_front_three_quarter.png",
    "industrial-aerial.png": RUN_ROOT / "s1-0/view_raised_overview.png",
    "qpsk-ber.png": Path("artifacts/p1_phy/ber_theory_vs_simulation.png"),
    "rrc-psd.png": Path("artifacts/p1_phy/rrc_rolloff_psd.png"),
    "qpsk-waveform-constellation.png": Path("artifacts/p1_phy/passband_waveform_constellation.png"),
    "semantic-frame-metrics.png": Path("artifacts/p2_semantic/p2_end_to_end_metrics.png"),
}

OBSERVATION_FIELDS = (
    "target_id", "color", "valid", "range_m", "bearing_rad", "timestamp_s",
    "confidence", "depth_valid_ratio", "failure_reason",
)

SUMMARY_FIELDS = (
    "success", "termination_reason", "failure_class", "sim_time_s", "steps",
    "policy_hz", "communication_hz", "path_length_m", "final_range_m",
    "final_bearing_rad", "final_target", "fall", "nonfinite", "terminated",
    "stop_hold_steps", "phy_bit_count", "phy_bit_errors", "phy_ber",
    "phy_theory_ber", "phy_frame_attempts", "phy_frame_errors", "frame_error_rate",
    "frame_acceptance_rate", "accepted_correct", "accepted_wrong", "reject_counts",
    "frame_counts", "hold_policy_ticks", "timeout_zero_events", "startup_zero_ticks",
    "obs_timeout_ticks", "obstacle_contact_event_count", "target_contact_event_count",
    "minimum_sampled_obstacle_distance_m", "distance_sampling_hz", "trace_summary",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def ffprobe(path: Path) -> dict[str, Any]:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])
    info = json.loads(raw)
    video = next(stream for stream in info["streams"] if stream.get("codec_type") == "video")
    fps_num, fps_den = map(int, video["r_frame_rate"].split("/"))
    return {
        "codec": video.get("codec_name"), "width": int(video["width"]),
        "height": int(video["height"]), "fps": fps_num / fps_den,
        "frame_count": int(video.get("nb_frames", 0)),
        "duration_s": float(info["format"]["duration"]),
        "audio_streams": sum(stream.get("codec_type") == "audio" for stream in info["streams"]),
    }


def probe_image(path: Path) -> dict[str, Any]:
    from PIL import Image
    with Image.open(path) as im:
        return {"format": im.format, "width": im.width, "height": im.height, "mode": im.mode}


def export_video(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "23", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
        "-movflags", "+faststart", str(destination),
    ], check=True)
    source_info, export_info = ffprobe(source), ffprobe(destination)
    if (source_info["width"], source_info["height"], source_info["fps"], source_info["frame_count"]) != (
        export_info["width"], export_info["height"], export_info["fps"], export_info["frame_count"]
    ):
        raise RuntimeError(f"video timing/resolution changed: {source} -> {destination}")
    if abs(source_info["duration_s"] - export_info["duration_s"]) > 0.001:
        raise RuntimeError(f"video duration changed: {source} -> {destination}")
    return {"source_media": source_info, "export_media": export_info}


def selected_tick(row: dict[str, Any]) -> dict[str, Any]:
    """Keep requested time-series values without duplicating diagnostics/arrays."""
    result = {
        field: row[field] for field in (
            "step", "time_s", "controller_state", "camera_sample", "obs_fresh",
            "controller_output", "transmitted_cmd", "received_cmd", "applied_cmd",
            "command_age_ms", "command_hold", "command_expired", "obs_frame_status",
            "cmd_frame_status", "new_obs_received", "new_cmd_received", "base_height",
            "base_position_w", "yaw_rad", "fall",
        ) if field in row
    }
    for source_key, output_key in (("raw_observation", "raw_observation"),
                                   ("controller_input", "controller_input")):
        observation = row.get(source_key)
        if isinstance(observation, dict):
            result[output_key] = {
                key: observation[key] for key in OBSERVATION_FIELDS if key in observation
            }
        elif observation is not None:
            result[output_key] = observation
    return result


def export_run(run_id: str, run_spec: dict[str, Any], video_dest: Path,
               manifest_files: list[dict[str, Any]]) -> None:
    stage_dir = ROOT / RUN_ROOT / run_spec["stage"]
    trace_path = stage_dir / "result_wideview.json"
    video_source = stage_dir / run_spec["video"]
    if not trace_path.is_file() or not video_source.is_file():
        raise FileNotFoundError(f"formal run evidence missing for {run_id}")
    trace_result = json.loads(trace_path.read_text(encoding="utf-8"))
    video_meta = export_video(video_source, video_dest)
    trace = trace_result["trace"]
    frame_count = video_meta["export_media"]["frame_count"]
    fps = video_meta["export_media"]["fps"]
    policy_dt = float(trace_result["timing_contract"]["policy_tick_s"])
    if frame_count != trace_result["video_frame_count"]:
        raise RuntimeError(f"video frame count differs from source trace: {run_id}")
    if frame_count > (len(trace) + 1) // 2:
        raise RuntimeError(f"no trace row for a video frame: {run_id}")

    frame_map = []
    for frame_index in range(frame_count):
        trace_index = frame_index * 2
        row = trace[trace_index]
        frame_map.append({
            "frame_index": frame_index,
            "video_time_s": round(frame_index / fps, 6),
            "trace_index": trace_index,
            "trace_step": row["step"],
            "sim_time_s": round(float(row["time_s"]) - policy_dt, 6),
        })

    link_events = []
    for event in trace_result["link_events"]:
        # Preserve each source event (including every reject) and its exact bit strings.
        link_events.append({key: event[key] for key in (
            "direction", "message_type", "tx_time_s", "rx_time_s", "capture_time_s",
            "tx_bits", "rx_bits", "bit_errors", "status", "accepted_message",
            "delivered_at_episode_end",
        ) if key in event})

    ticks = []
    for index, row in enumerate(trace):
        tick = selected_tick(row)
        tick["trace_index"] = index
        tick["video_frame_index"] = index // 2 if index % 2 == 0 and index // 2 < frame_count else None
        if tick["video_frame_index"] is not None:
            tick["video_time_s"] = round(tick["time_s"] - policy_dt, 6)
        ticks.append(tick)

    data_path = DATA_DIR / f"{run_id}.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "run_id": run_id,
        "condition": {
            "label": run_spec["label"], "ebn0_db": run_spec["ebn0_db"],
            "scenario_id": trace_result["scenario_id"], "seed": trace_result["seed"],
            "target_color": trace_result["target_color"],
            "layout_randomization": trace_result.get("layout_randomization"),
        },
        "provenance": {
            "trace_source": rel(trace_path), "trace_sha256": sha256(trace_path),
            "video_source": rel(video_source), "video_source_sha256": sha256(video_source),
            "video_export": rel(video_dest), "video_export_sha256": sha256(video_dest),
        },
        "video_clock": {
            **video_meta["export_media"], "source_caption_burned_in": True,
            "sync_rule": "video frame i maps to trace[i*2]; sim_time_s = trace.time_s - policy_tick_s",
            "policy_tick_s": policy_dt, "frame_map": frame_map,
        },
        "summary": {key: trace_result[key] for key in SUMMARY_FIELDS if key in trace_result},
        "events": link_events,
        "ticks": ticks,
    }
    data_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_files.append({
        "role": "run_data", "run_id": run_id, "source": rel(trace_path),
        "source_sha256": sha256(trace_path), "source_bytes": trace_path.stat().st_size,
        "export": rel(data_path),
        "export_sha256": sha256(data_path), "export_bytes": data_path.stat().st_size,
        "event_count": len(link_events),
        "reject_count": sum(event["status"] != "accepted" for event in link_events),
        "rejects_by_status": trace_result["reject_counts"],
        "video_export": rel(video_dest), "video_export_sha256": sha256(video_dest),
        **video_meta,
    })
    manifest_files.append({
        "role": "video", "run_id": run_id, "source": rel(video_source),
        "source_sha256": sha256(video_source), "source_bytes": video_source.stat().st_size,
        "export": rel(video_dest), "export_sha256": sha256(video_dest),
        "export_bytes": video_dest.stat().st_size, **video_meta,
        "compression": {"codec": "libx264", "preset": "medium", "crf": 23,
                       "pixel_format": "yuv420p", "audio": "removed; source has no audio"},
        "overlay": "burned from the same run trace",
    })


def main() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_files: list[dict[str, Any]] = []

    run_video_exports: dict[str, Path] = {}
    for run_id, spec in RUNS.items():
        stage_dir = ROOT / RUN_ROOT / spec["stage"]
        source = stage_dir / spec["video"]
        destination = VIDEO_DIR / f"industrial-{run_id}.mp4"
        run_video_exports[run_id] = destination
        export_run(run_id, spec, destination, manifest_files)

    split_spec = RUNS["awgn-8db"]
    split_source = ROOT / RUN_ROOT / split_spec["stage"] / split_spec["split"]
    split_dest = VIDEO_DIR / "industrial-awgn-8db-split.mp4"
    split_meta = export_video(split_source, split_dest)
    manifest_files.append({
        "role": "video", "run_id": "awgn-8db", "source": rel(split_source),
        "source_sha256": sha256(split_source), "source_bytes": split_source.stat().st_size,
        "export": rel(split_dest), "export_sha256": sha256(split_dest),
        "export_bytes": split_dest.stat().st_size, **split_meta,
        "compression": {"codec": "libx264", "preset": "medium", "crf": 23,
                       "pixel_format": "yuv420p", "audio": "removed; source has no audio"},
        "overlay": "burned from the same 8 dB run trace; synchronized first-person inset",
    })

    for name, relative_source in IMAGE_SOURCES.items():
        source = ROOT / relative_source
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = IMAGE_DIR / name
        shutil.copyfile(source, destination)
        manifest_files.append({
            "role": "image", "source": rel(source), "source_sha256": sha256(source),
            "source_bytes": source.stat().st_size, "export": rel(destination),
            "export_sha256": sha256(destination), "export_bytes": destination.stat().st_size,
            "processing": "byte-identical PNG copy; no pixel or curve changes",
            "media": probe_image(destination),
        })

    cover_source = ROOT / RUN_ROOT / "s1-3/s1-3_B_-30deg_seed0_captioned.mp4"
    cover_dest = IMAGE_DIR / "industrial-awgn-8db-cover.png"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "21.0",
        "-i", str(cover_source), "-frames:v", "1", "-update", "1", str(cover_dest),
    ], check=True)
    manifest_files.append({
        "role": "video_cover", "run_id": "awgn-8db", "source": rel(cover_source),
        "source_sha256": sha256(cover_source), "source_bytes": cover_source.stat().st_size,
        "source_time_s": 21.0,
        "export": rel(cover_dest), "export_sha256": sha256(cover_dest),
        "export_bytes": cover_dest.stat().st_size,
        "processing": "single PNG frame extracted without crop or overlay changes",
        "media": probe_image(cover_dest),
    })

    manifest = {
        "manifest_version": 1,
        "purpose": "Local P4-A website media preparation; not staged or published by this script.",
        "formal_run_root": RUN_ROOT.as_posix(),
        "runs": {run_id: {"stage": spec["stage"], "video_export": rel(run_video_exports[run_id]),
                           "data_export": f"website/assets/data/{run_id}.json"}
                 for run_id, spec in RUNS.items()},
        "files": manifest_files,
    }
    manifest_path = ROOT / "WEBSITE_MEDIA_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest": rel(manifest_path), "file_count": len(manifest_files),
        "video_count": sum(item["role"] == "video" for item in manifest_files),
        "image_count": sum(item["role"] in ("image", "video_cover") for item in manifest_files),
        "data_count": sum(item["role"] == "run_data" for item in manifest_files),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

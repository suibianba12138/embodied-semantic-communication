"""Reproducible Wire v1 / QPSK end-to-end and quantization experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from esc import frame, phy  # noqa: E402


def binomial_stats(events: int, trials: int) -> dict[str, float | int]:
    if not 0 <= events <= trials or trials <= 0:
        raise ValueError("invalid binomial counts")
    alpha = 0.05
    lo = 0.0 if events == 0 else float(beta.ppf(alpha / 2, events, trials - events + 1))
    hi = 1.0 if events == trials else float(beta.ppf(1 - alpha / 2, events + 1, trials - events))
    upper = 1.0 if events == trials else float(beta.ppf(1 - alpha, events + 1, trials - events))
    return {"events": events, "trials": trials, "rate": events / trials,
            "ci95_low": lo, "ci95_high": hi, "upper_95_one_sided": upper}


def _message(kind: str, rng: np.random.Generator, capture_time_s: float):
    if kind == "OBS":
        color = "red" if rng.integers(0, 2) == 0 else "blue"
        valid = bool(rng.integers(0, 4) != 0)
        if valid:
            return frame.ObsMessage(color, True, float(rng.uniform(0.05, 20.0)),
                                    float(rng.uniform(-math.pi, math.pi)), capture_time_s)
        return frame.ObsMessage(color, False, None, None, capture_time_s)
    if rng.integers(0, 8) == 0:
        return frame.CmdMessage(0.0, 0.0, 0.0, ttl_ms=200, mode="ZERO")
    return frame.CmdMessage(float(rng.uniform(-1.5, 1.5)), float(rng.uniform(-1.5, 1.5)),
                            float(rng.uniform(-1.5, 1.5)), ttl_ms=200)


def run_link(config: dict) -> list[dict]:
    taps = phy.rrc_filter(alpha=config["rrc_alpha"], span=config["rrc_span_symbols"],
                          sps=config["samples_per_symbol"])
    sps = config["samples_per_symbol"]
    receive_time = config["simulated_receive_time_s"]
    all_results: list[dict] = []
    for ebn0_db in config["ebn0_db"]:
        for kind_id, kind in enumerate(("OBS", "CMD")):
            rng = np.random.default_rng(np.random.SeedSequence(
                [config["master_seed"], kind_id, int(ebn0_db + 20)]))
            nframes = int(config["frames_per_type_per_ebn0"])
            bit_errors = frame_errors = accepted = crc_rejects = semantic_correct = accepted_wrong = 0
            statuses: dict[str, int] = {}
            for index in range(nframes):
                message = _message(kind, rng, 0.0)
                tx_bits = (frame.encode_obs(message, seq=index % 256) if kind == "OBS"
                           else frame.encode_cmd(message, seq=index % 256))
                tx_symbols = phy.qpsk_modulate(tx_bits)
                tx_samples = phy.rrc_transmit(tx_symbols, taps, sps=sps)
                noisy = phy.add_awgn_baseband(tx_samples, float(ebn0_db), rng)
                filtered = phy.matched_filter(noisy, taps)
                rx_symbols = phy.sample_symbols(filtered, symbol_count=48, sps=sps,
                                                delay_samples=2 * (len(taps) - 1) // 2)
                rx_bits = phy.qpsk_demodulate(rx_symbols)
                bit_errors += int(np.count_nonzero(tx_bits != rx_bits))
                frame_errors += int(np.any(tx_bits != rx_bits))
                context = frame.ReceiverContext(f"{kind}-{index}", session_start_s=0.0)
                result = frame.receive_frame(rx_bits, context, now_s=receive_time)
                statuses[result.status] = statuses.get(result.status, 0) + 1
                if result.status == "accepted":
                    accepted += 1
                    expected = frame.decode_message(message)
                    if result.message == expected:
                        semantic_correct += 1
                    else:
                        accepted_wrong += 1
            total_bits = nframes * 96
            crc_rejects = statuses.get("crc_reject", 0)
            all_results.append({
                "ebn0_db": float(ebn0_db), "message_type": kind,
                "frames": nframes, "bits": total_bits, "bit_errors": bit_errors,
                "ber": bit_errors / total_bits,
                "theory_ber": float(phy.qpsk_theoretical_ber(float(ebn0_db))),
                "ber_upper_95_one_sided": binomial_stats(bit_errors, total_bits)["upper_95_one_sided"],
                "frame_errors": frame_errors,
                "frame_error_rate": frame_errors / nframes,
                "frame_error_rate_stats": binomial_stats(frame_errors, nframes),
                "accepted": accepted, "frame_acceptance_rate": accepted / nframes,
                "acceptance_stats": binomial_stats(accepted, nframes),
                "crc_rejects": crc_rejects,
                "crc_reject_rate": crc_rejects / nframes,
                "crc_reject_rate_stats": binomial_stats(crc_rejects, nframes),
                "semantic_correct": semantic_correct,
                "semantic_recovery_rate": semantic_correct / nframes,
                "semantic_recovery_stats": binomial_stats(semantic_correct, nframes),
                "accepted_but_wrong_payload": accepted_wrong,
                "accepted_but_wrong_rate_per_attempt": accepted_wrong / nframes,
                "accepted_but_wrong_rate_given_accepted": accepted_wrong / accepted if accepted else None,
                "reject_counts": {k: statuses.get(k, 0) for k in (
                    "length_reject", "preamble_reject", "crc_reject", "header_reject",
                    "schema_reject", "sequence_reject", "ttl_reject", "accepted")},
                "sequence_context": "one fresh bounded context per isolated frame trial",
            })
    return all_results


def run_v11_quantization(path: str | None) -> dict:
    if path is None:
        return {"status": "NOT_RUN", "reason": "no V1.1 trace path configured"}
    trace_path = Path(path)
    with trace_path.open("r", encoding="utf-8") as f:
        episode = json.load(f)
    camera_rows = [row for row in episode["trace"] if row.get("camera_sample")]
    valid_rows = [row for row in camera_rows if row.get("target_valid") and
                  row.get("target", {}).get("range_m") is not None and
                  row.get("target", {}).get("bearing_rad") is not None]
    range_errors: list[float] = []
    bearing_errors: list[float] = []
    range_flips = bearing_flips = combined_flips = 0
    range_boundary_distances: list[float] = []
    bearing_boundary_distances: list[float] = []
    valid_color_rows = 0
    for row in camera_rows:
        target = row.get("target") or {}
        color = target.get("color", episode.get("target_color"))
        if color not in ("red", "blue"):
            continue
        is_valid = bool(row.get("target_valid") and target.get("range_m") is not None and
                        target.get("bearing_rad") is not None)
        capture = float(row.get("time_s", target.get("timestamp_s", 0.0)))
        msg = frame.ObsMessage(color, is_valid,
                               float(target["range_m"]) if is_valid else None,
                               float(target["bearing_rad"]) if is_valid else None, capture)
        decoded = frame.parse_frame(frame.encode_obs(msg, seq=0)).message
        if is_valid:
            valid_color_rows += 1
            raw_range = float(target["range_m"])
            raw_bearing = float(target["bearing_rad"])
            range_errors.append(abs(decoded.range_m - raw_range))
            bearing_delta = (decoded.bearing_rad - raw_bearing + math.pi) % (2 * math.pi) - math.pi
            bearing_errors.append(abs(bearing_delta))
            range_boundary_distances.append(abs(raw_range - 0.6))
            bearing_boundary_distances.append(abs(abs(raw_bearing) - math.radians(10)))
            r_flip = (raw_range <= 0.6) != (decoded.range_m <= 0.6)
            b_flip = (abs(raw_bearing) <= math.radians(10)) != (abs(decoded.bearing_rad) <= math.radians(10))
            range_flips += int(r_flip)
            bearing_flips += int(b_flip)
            combined_flips += int(r_flip or b_flip)
    def stats(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "max": None, "mean": None, "min": None}
        return {"count": len(values), "max": max(values), "mean": float(np.mean(values)), "min": min(values)}
    # Deliberate synthetic boundary probes show that the quantizer can change a discrete gate.
    probe_range = 0.6001
    probe_angle = math.radians(10.01)
    probe = frame.ObsMessage("red", True, probe_range, probe_angle, 1.0)
    probe_decoded = frame.parse_frame(frame.encode_obs(probe, seq=0)).message
    return {
        "status": "OFFLINE_VALIDATED",
        "source_path": str(trace_path), "scenario_id": episode.get("scenario_id"),
        "episode_success_recorded": bool(episode.get("success")),
        "camera_samples": len(camera_rows), "valid_camera_samples": len(valid_rows),
        "valid_color_samples_quantized": valid_color_rows,
        "range_abs_error_m": stats(range_errors),
        "bearing_circular_abs_error_rad": stats(bearing_errors),
        "range_stop_gate_flips_le_0_6m": range_flips,
        "bearing_align_gate_flips_abs_le_10deg": bearing_flips,
        "combined_gate_flips": combined_flips,
        "closest_valid_sample_to_range_boundary_m": min(range_boundary_distances) if range_boundary_distances else None,
        "closest_valid_sample_to_bearing_boundary_deg": math.degrees(min(bearing_boundary_distances)) if bearing_boundary_distances else None,
        "synthetic_boundary_probe": {
            "range_input_m": probe_range, "range_decoded_m": probe_decoded.range_m,
            "range_stop_gate_flipped": (probe_range <= 0.6) != (probe_decoded.range_m <= 0.6),
            "bearing_input_deg": math.degrees(probe_angle),
            "bearing_decoded_deg": math.degrees(probe_decoded.bearing_rad),
            "bearing_align_gate_flipped": (abs(probe_angle) <= math.radians(10)) !=
                                         (abs(probe_decoded.bearing_rad) <= math.radians(10)),
        },
    }


def plot_results(results: list[dict], output: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    for kind, marker in (("OBS", "o"), ("CMD", "s")):
        rows = [r for r in results if r["message_type"] == kind]
        x = [r["ebn0_db"] for r in rows]
        axes[0].semilogy(x, [max(r["ber"], 0.5 / r["bits"]) for r in rows], marker + "-", label=kind)
        axes[1].plot(x, [r["frame_acceptance_rate"] for r in rows], marker + "-", label=kind)
        axes[2].plot(x, [r["semantic_recovery_rate"] for r in rows], marker + "-", label=kind)
    axes[0].plot([r["ebn0_db"] for r in results if r["message_type"] == "OBS"],
                 [phy.qpsk_theoretical_ber(r["ebn0_db"]) for r in results if r["message_type"] == "OBS"],
                 "k--", label="QPSK theory")
    axes[0].set(title="Raw bit BER", xlabel="$E_b/N_0$ (dB)", ylabel="BER")
    axes[1].set(title="Frame acceptance", xlabel="$E_b/N_0$ (dB)", ylabel="Rate", ylim=(-0.03, 1.03))
    axes[2].set(title="Exact semantic recovery", xlabel="$E_b/N_0$ (dB)", ylabel="Rate", ylim=(-0.03, 1.03))
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "experiments/p2_semantic_config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p2_semantic")
    parser.add_argument("--v11-trace", type=Path, default=None)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    trace_path = args.v11_trace or config.get("v11_trace")
    args.output.mkdir(parents=True, exist_ok=True)
    link = run_link(config)
    quantization = run_v11_quantization(str(trace_path) if trace_path else None)
    w, h = config["camera_width"], config["camera_height"]
    rgbd_bits = w * h * (3 * 8 + 32)
    summary = {
        "config": {**config, "v11_trace": str(trace_path) if trace_path else None},
        "seed_derivation": "numpy.random.SeedSequence([master_seed, message_type_id, EbN0_dB + 20]); OBS=0, CMD=1",
        "wire_v1": {"bits": 96, "payload_bits": 52, "overhead_bits": 44,
                    "obs_nonreserved_field_bits": 38, "cmd_nonreserved_field_bits": 48,
                    "qpsk_symbols": 48, "obs_bits": 96, "cmd_bits": 96},
        "data_volume_comparison": {
            "obs_payload_area_bits": 52, "obs_nonreserved_field_bits": 38,
            "cmd_payload_area_bits": 52, "cmd_nonreserved_field_bits": 48,
            "obs_or_cmd_full_wire_frame_bits": 96,
            "uncompressed_rgb_only_bits_per_frame": w * h * 24,
            "uncompressed_rgbd_bits_per_frame_assuming_float32_depth": rgbd_bits,
            "rgbd_to_semantic_wire_ratio": rgbd_bits / 96,
            "assumption": "64x48 RGB uint8 plus one float32 depth value per pixel; no framing/compression metadata",
            "fidelity_note": "structured task fields are not equivalent-information or lossless substitutes for RGB-D pixels",
        },
        "link_results": link,
        "v11_quantization": quantization,
        "confidence_method": "two-sided exact 95% Clopper-Pearson; one-sided exact 95% upper for rare/zero counts",
    }
    (args.output / "p2_semantic_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with (args.output / "p2_semantic_results.csv").open("w", encoding="utf-8") as f:
        columns = ["ebn0_db", "message_type", "frames", "bits", "bit_errors", "ber", "theory_ber", "ber_upper_95_one_sided",
                   "frame_errors", "frame_error_rate", "accepted", "frame_acceptance_rate", "crc_rejects",
                   "crc_reject_rate", "semantic_correct", "semantic_recovery_rate", "accepted_but_wrong_payload"]
        f.write(",".join(columns) + "\n")
        for row in link:
            f.write(",".join(str(row[c]) for c in columns) + "\n")
    plot_results(link, args.output / "p2_end_to_end_metrics.png")
    print(json.dumps({"results": len(link), "frames_per_result": config["frames_per_type_per_ebn0"],
                      "output": str(args.output), "v11_status": quantization["status"]}, indent=2))


if __name__ == "__main__":
    main()

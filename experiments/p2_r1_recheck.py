"""Independent multi-seed 8 dB P2 recheck with bit-position diagnostics."""

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
from scipy.stats import (beta, binomtest, chi2, chi2_contingency, fisher_exact,
                         f_oneway, t, ttest_1samp, ttest_ind, ttest_rel)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from esc import frame, phy  # noqa: E402

SEGMENTS = {"preamble": (0, 16), "header": (16, 28), "payload": (28, 80), "crc": (80, 96)}


def exact_rate(errors: int, trials: int, confidence: float = 0.95) -> dict:
    alpha = 1.0 - confidence
    low = 0.0 if errors == 0 else float(beta.ppf(alpha / 2, errors, trials - errors + 1))
    high = 1.0 if errors == trials else float(beta.ppf(1 - alpha / 2, errors + 1, trials - errors))
    return {"events": int(errors), "trials": int(trials), "rate": errors / trials,
            "confidence": confidence, "ci_low": low, "ci_high": high}


def frame_cluster_ber(frame_error_counts: list[int] | np.ndarray, confidence: float = 0.95) -> dict:
    """Student-t interval for BER using independent frames as sampling clusters."""
    counts = np.asarray(frame_error_counts, dtype=np.float64)
    if counts.ndim != 1 or counts.size < 2 or np.any(counts < 0) or np.any(counts > 96):
        raise ValueError("frame_error_counts must contain at least two valid per-frame counts")
    ber = float(counts.mean() / 96.0)
    if counts.sum() == 0:
        upper = -math.log((1.0 - confidence) / 2.0) / (counts.size * 96.0)
        return {"frames": int(counts.size), "ber": 0.0, "standard_error": None,
                "confidence": confidence, "ci_low": 0.0, "ci_high": upper,
                "method": "zero-event Poisson upper limit at frame-cluster exposure"}
    se = float(counts.std(ddof=1) / math.sqrt(counts.size) / 96.0)
    critical = float(t.ppf((1.0 + confidence) / 2.0, counts.size - 1))
    return {"frames": int(counts.size), "ber": ber, "standard_error": se,
            "confidence": confidence, "ci_low": max(0.0, ber - critical * se),
            "ci_high": min(1.0, ber + critical * se)}


def frame_seed_heterogeneity_p(seed_frame_errors: list[np.ndarray]) -> float:
    if all(np.var(values) == 0.0 for values in seed_frame_errors):
        return 1.0 if len({float(np.mean(values)) for values in seed_frame_errors}) == 1 else 0.0
    return float(f_oneway(*seed_frame_errors).pvalue)


def _cluster_region_wald_p(region_counts_per_frame: np.ndarray, widths: np.ndarray) -> float:
    """Cluster-robust Wald test of equal per-bit error rates across four regions."""
    rates = np.asarray(region_counts_per_frame, dtype=np.float64) / np.asarray(widths, dtype=np.float64)
    contrasts = rates[:, :3] - rates[:, [3]]
    mean_diff = contrasts.mean(axis=0)
    cov_mean = np.cov(contrasts, rowvar=False, ddof=1) / contrasts.shape[0]
    rank = int(np.linalg.matrix_rank(cov_mean))
    if rank == 0:
        return 1.0 if np.all(mean_diff == 0) else 0.0
    statistic = float(mean_diff @ np.linalg.pinv(cov_mean) @ mean_diff)
    return float(chi2.sf(statistic, df=rank))


def _paired_t_p(left: np.ndarray, right: np.ndarray) -> float:
    differences = np.asarray(left) - np.asarray(right)
    if np.all(differences == differences[0]):
        return 1.0 if differences[0] == 0 else 0.0
    return float(ttest_rel(left, right).pvalue)


def _welch_t_p(left: np.ndarray, right: np.ndarray) -> float:
    if np.all(left == left[0]) and np.all(right == right[0]):
        return 1.0 if left[0] == right[0] else 0.0
    return float(ttest_ind(left, right, equal_var=False).pvalue)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm adjusted p-values, returned in original order."""
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.ones(n, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (n - rank) * p_values[int(idx)]))
        adjusted[int(idx)] = running
    return [float(x) for x in adjusted]


def _message(kind: str, rng: np.random.Generator):
    if kind == "OBS":
        color = "red" if rng.integers(0, 2) == 0 else "blue"
        valid = bool(rng.integers(0, 4) != 0)
        if not valid:
            return frame.ObsMessage(color, False, None, None, 0.0)
        return frame.ObsMessage(color, True, float(rng.uniform(0.05, 20.0)),
                                float(rng.uniform(-math.pi, math.pi)), 0.0)
    if rng.integers(0, 8) == 0:
        return frame.CmdMessage(0.0, 0.0, 0.0, ttl_ms=200, mode="ZERO")
    return frame.CmdMessage(float(rng.uniform(-1.5, 1.5)), float(rng.uniform(-1.5, 1.5)),
                            float(rng.uniform(-1.5, 1.5)), ttl_ms=200)


def simulate_batch(*, kind: str, seed: int, frames: int, ebn0_db: float = 8.0,
                   alpha: float = 0.35, span: int = 10, sps: int = 16,
                   receive_time_s: float = 0.05) -> dict:
    type_id = 0 if kind == "OBS" else 1
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), type_id]))
    taps = phy.rrc_filter(alpha=alpha, span=span, sps=sps)
    errors_by_bit = np.zeros(96, dtype=np.int64)
    errors_by_symbol = np.zeros(48, dtype=np.int64)
    bit_errors_per_frame = np.zeros(frames, dtype=np.int16)
    errors_by_region_per_frame = np.zeros((frames, 4), dtype=np.int16)
    first_5_per_frame = np.zeros(frames, dtype=np.int16)
    middle_38_per_frame = np.zeros(frames, dtype=np.int16)
    last_5_per_frame = np.zeros(frames, dtype=np.int16)
    frame_errors = accepted = crc_rejects = semantic_correct = accepted_wrong = 0
    status_counts: dict[str, int] = {}

    for index in range(frames):
        message = _message(kind, rng)
        tx_bits = frame.encode_obs(message, seq=index % 256) if kind == "OBS" else frame.encode_cmd(message, seq=index % 256)
        tx = phy.rrc_transmit(phy.qpsk_modulate(tx_bits), taps, sps=sps)
        noisy = phy.add_awgn_baseband(tx, ebn0_db, rng)
        matched = phy.matched_filter(noisy, taps)
        rx_symbols = phy.sample_symbols(matched, symbol_count=48, sps=sps,
                                        delay_samples=2 * (len(taps) - 1) // 2)
        rx_bits = phy.qpsk_demodulate(rx_symbols)
        bit_errors = (tx_bits != rx_bits)
        errors_by_bit += bit_errors
        errors_by_symbol += bit_errors.reshape(48, 2).sum(axis=1)
        bit_errors_per_frame[index] = int(bit_errors.sum())
        for region_idx, (region_lo, region_hi) in enumerate(SEGMENTS.values()):
            errors_by_region_per_frame[index, region_idx] = int(bit_errors[region_lo:region_hi].sum())
        first_5_per_frame[index] = int(bit_errors[:10].sum())
        middle_38_per_frame[index] = int(bit_errors[10:86].sum())
        last_5_per_frame[index] = int(bit_errors[86:].sum())
        frame_errors += int(np.any(bit_errors))
        ctx = frame.ReceiverContext(f"{kind}-{seed}-{index}", session_start_s=0.0)
        result = frame.receive_frame(rx_bits, ctx, now_s=receive_time_s)
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
        if result.status == "crc_reject":
            crc_rejects += 1
        elif result.status == "accepted":
            accepted += 1
            if result.message == frame.decode_message(message):
                semantic_correct += 1
            else:
                accepted_wrong += 1

    nbits = frames * 96
    nerrors = int(errors_by_bit.sum())
    region_counts = {}
    for name, (lo, hi) in SEGMENTS.items():
        count = int(errors_by_bit[lo:hi].sum())
        region_counts[name] = {"errors": count, "bits": frames * (hi - lo),
                               "ber": count / (frames * (hi - lo))}
    edge_positions = np.r_[0:10, 86:96]
    edge_errors = int(errors_by_bit[edge_positions].sum())
    edge_bits = frames * len(edge_positions)
    middle_errors = nerrors - edge_errors
    middle_bits = nbits - edge_bits
    return {
        "message_type": kind, "seed": int(seed), "frames": int(frames),
        "bits": int(nbits), "bit_errors": nerrors, "ber": nerrors / nbits,
        "ber_ci95": exact_rate(nerrors, nbits),
        "ber_frame_cluster_ci95": frame_cluster_ber(bit_errors_per_frame, 0.95),
        "ber_frame_cluster_ci97_5": frame_cluster_ber(bit_errors_per_frame, 0.975),
        "theory_ber": float(phy.qpsk_theoretical_ber(ebn0_db)),
        "theory_binomial_p_two_sided": float(binomtest(nerrors, nbits,
                                                        float(phy.qpsk_theoretical_ber(ebn0_db))).pvalue),
        "theory_frame_cluster_t_p_two_sided": float(ttest_1samp(
            bit_errors_per_frame.astype(np.float64), 96.0 * float(phy.qpsk_theoretical_ber(ebn0_db))).pvalue),
        "frame_errors": frame_errors, "fer": frame_errors / frames,
        "frame_acceptance": accepted / frames, "accepted_frames": accepted,
        "crc_rejects": crc_rejects, "semantic_correct_frames": semantic_correct,
        "semantic_recovery_rate": semantic_correct / frames,
        "accepted_but_wrong_payload": accepted_wrong,
        "reject_counts": {k: status_counts.get(k, 0) for k in (
            "length_reject", "preamble_reject", "crc_reject", "header_reject",
            "schema_reject", "sequence_reject", "ttl_reject", "accepted")},
        "errors_by_wire_region": region_counts,
        "first_5_symbols": {"errors": int(errors_by_bit[:10].sum()), "bits": frames * 10},
        "middle_38_symbols": {"errors": int(errors_by_bit[10:86].sum()), "bits": frames * 76},
        "last_5_symbols": {"errors": int(errors_by_bit[86:].sum()), "bits": frames * 10},
        "edge_10_symbols": {"errors": edge_errors, "bits": edge_bits,
                            "ber": edge_errors / edge_bits, "ci95": exact_rate(edge_errors, edge_bits)},
        "interior_38_symbols": {"errors": middle_errors, "bits": middle_bits,
                                "ber": middle_errors / middle_bits, "ci95": exact_rate(middle_errors, middle_bits)},
        "errors_by_bit_position": errors_by_bit.tolist(),
        "errors_by_symbol_position": errors_by_symbol.tolist(),
        "bit_errors_per_frame": bit_errors_per_frame.tolist(),
        "errors_by_region_per_frame": errors_by_region_per_frame.tolist(),
        "first_5_errors_per_frame": first_5_per_frame.tolist(),
        "middle_38_errors_per_frame": middle_38_per_frame.tolist(),
        "last_5_errors_per_frame": last_5_per_frame.tolist(),
    }


def _heterogeneity_p(counts: list[int], trials: list[int]) -> float:
    if sum(counts) == 0 or sum(counts) == sum(trials):
        return 1.0
    table = np.array([[e, n - e] for e, n in zip(counts, trials)], dtype=np.int64)
    return float(chi2_contingency(table, correction=False).pvalue)


def analyze(batches: list[dict], *, ebn0_db: float = 8.0) -> dict:
    alpha = 0.05
    theory = float(phy.qpsk_theoretical_ber(ebn0_db))
    per_type = {}
    type_pvals = []
    seed_heterogeneity = {}
    location_tests = []

    for kind in ("OBS", "CMD"):
        rows = [r for r in batches if r["message_type"] == kind]
        errors = sum(r["bit_errors"] for r in rows)
        bits = sum(r["bits"] for r in rows)
        frame_error_counts = np.concatenate([np.asarray(r["bit_errors_per_frame"], dtype=np.int16) for r in rows])
        frames = sum(r["frames"] for r in rows)
        accepted = sum(r["accepted_frames"] for r in rows)
        sem = sum(r["semantic_correct_frames"] for r in rows)
        crc = sum(r["crc_rejects"] for r in rows)
        per_type[kind] = {
            "frames": frames, "bits": bits, "bit_errors": errors, "ber": errors / bits,
            "ber_ci95": exact_rate(errors, bits),
            "ber_ci97_5_bonferroni_for_two_types": exact_rate(errors, bits, confidence=0.975),
            "ber_frame_cluster_ci95": frame_cluster_ber(frame_error_counts, 0.95),
            "ber_frame_cluster_ci97_5": frame_cluster_ber(frame_error_counts, 0.975),
            "theory_ber": theory,
            "theory_binomial_p_two_sided": float(binomtest(errors, bits, theory).pvalue),
            "theory_frame_cluster_t_p_two_sided": float(ttest_1samp(frame_error_counts, 96.0 * theory).pvalue),
            "frame_errors": sum(r["frame_errors"] for r in rows),
            "fer": sum(r["frame_errors"] for r in rows) / frames,
            "accepted_frames": accepted, "frame_acceptance_rate": accepted / frames,
            "crc_rejects": crc, "crc_reject_rate": crc / frames,
            "semantic_correct_frames": sem, "semantic_recovery_rate": sem / frames,
            "accepted_but_wrong_payload": sum(r["accepted_but_wrong_payload"] for r in rows),
            "reject_counts": {name: sum(r["reject_counts"][name] for r in rows) for name in (
                "length_reject", "preamble_reject", "crc_reject", "header_reject",
                "schema_reject", "sequence_reject", "ttl_reject", "accepted")},
        }
        type_pvals.append(per_type[kind]["theory_frame_cluster_t_p_two_sided"])

        seed_cluster_counts = [np.asarray(r["bit_errors_per_frame"], dtype=np.float64) for r in rows]
        seed_heterogeneity[kind] = frame_seed_heterogeneity_p(seed_cluster_counts)

        region_names = list(SEGMENTS)
        region_errors = [sum(r["errors_by_wire_region"][name]["errors"] for r in rows) for name in region_names]
        region_bits = [sum(r["errors_by_wire_region"][name]["bits"] for r in rows) for name in region_names]
        region_by_frame = np.concatenate([np.asarray(r["errors_by_region_per_frame"], dtype=np.float64)
                                          for r in rows], axis=0)
        region_widths = np.array([SEGMENTS[name][1] - SEGMENTS[name][0] for name in region_names], dtype=float)
        field_cluster_p = _cluster_region_wald_p(region_by_frame, region_widths)
        field_bitwise_p = _heterogeneity_p(region_errors, region_bits)
        edge_errors = sum(r["edge_10_symbols"]["errors"] for r in rows)
        edge_bits = sum(r["edge_10_symbols"]["bits"] for r in rows)
        inner_errors = sum(r["interior_38_symbols"]["errors"] for r in rows)
        inner_bits = sum(r["interior_38_symbols"]["bits"] for r in rows)
        edge_by_frame = np.concatenate([np.asarray(r["first_5_errors_per_frame"], dtype=float) +
                                        np.asarray(r["last_5_errors_per_frame"], dtype=float)
                                        for r in rows])
        inner_by_frame = np.concatenate([np.asarray(r["middle_38_errors_per_frame"], dtype=float)
                                         for r in rows])
        edge_p = _paired_t_p(edge_by_frame / 20.0, inner_by_frame / 76.0)
        edge_bitwise_p = float(fisher_exact([[edge_errors, edge_bits - edge_errors],
                                             [inner_errors, inner_bits - inner_errors]],
                                            alternative="two-sided").pvalue)
        location_tests.extend([(kind, "wire_region_frame_cluster_wald", field_cluster_p),
                               (kind, "first_last_5_symbols_vs_interior_frame_cluster", edge_p)])
        per_type[kind]["region_error_counts"] = {
            name: {"errors": error, "bits": bits, "ber": error / bits}
            for name, error, bits in zip(region_names, region_errors, region_bits)}
        per_type[kind]["edge_vs_interior_frame_cluster_test_p"] = edge_p
        per_type[kind]["edge_vs_interior_bitwise_fisher_p_supplemental"] = edge_bitwise_p
        per_type[kind]["wire_region_frame_cluster_wald_p"] = field_cluster_p
        per_type[kind]["wire_region_bitwise_heterogeneity_p_supplemental"] = field_bitwise_p
        per_type[kind]["edge_symbols"] = {"errors": edge_errors, "bits": edge_bits,
                                           "ber": edge_errors / edge_bits,
                                           "ci95": exact_rate(edge_errors, edge_bits)}
        per_type[kind]["interior_symbols"] = {"errors": inner_errors, "bits": inner_bits,
                                               "ber": inner_errors / inner_bits,
                                               "ci95": exact_rate(inner_errors, inner_bits)}

    # Pre-specified family-wise corrections: 2 overall BER tests, 4 location tests,
    # 2 seed-heterogeneity tests, and the 10 descriptive seed BER tests.
    type_adjusted = holm_adjust(type_pvals)
    for kind, adjusted in zip(("OBS", "CMD"), type_adjusted):
        per_type[kind]["theory_p_holm_two_types"] = adjusted
    location_adjusted = holm_adjust([x[2] for x in location_tests])
    location_tests = [(*test, adjusted) for test, adjusted in zip(location_tests, location_adjusted)]
    seed_heterogeneity_adjusted = holm_adjust([seed_heterogeneity[k] for k in ("OBS", "CMD")])
    seed_heterogeneity = {k: {"p_unadjusted": seed_heterogeneity[k],
                              "p_holm_two_types": p}
                          for k, p in zip(("OBS", "CMD"), seed_heterogeneity_adjusted)}
    all_seed_p = [r["theory_frame_cluster_t_p_two_sided"] for r in batches]
    seed_p_adj = holm_adjust(all_seed_p)
    batch_results = []
    for row, adjusted in zip(batches, seed_p_adj):
        batch_results.append({k: v for k, v in row.items() if k not in (
            "errors_by_bit_position", "errors_by_symbol_position", "bit_errors_per_frame",
            "errors_by_region_per_frame", "first_5_errors_per_frame",
            "middle_38_errors_per_frame", "last_5_errors_per_frame") } | {
            "theory_frame_cluster_t_p_holm_ten_seed_comparisons": adjusted,
            "ber_ci99_5_bonferroni_ten_seed_comparisons": exact_rate(
                row["bit_errors"], row["bits"], confidence=0.995),
            "ber_frame_cluster_ci99_5_bonferroni_ten_seed_comparisons": frame_cluster_ber(
                row["bit_errors_per_frame"], confidence=0.995)})

    by_type = {kind: np.sum([r["errors_by_symbol_position"] for r in batches
                             if r["message_type"] == kind], axis=0).astype(int).tolist()
               for kind in ("OBS", "CMD")}
    obs_frame_errors = np.concatenate([np.asarray(r["bit_errors_per_frame"], dtype=float)
                                       for r in batches if r["message_type"] == "OBS"])
    cmd_frame_errors = np.concatenate([np.asarray(r["bit_errors_per_frame"], dtype=float)
                                       for r in batches if r["message_type"] == "CMD"])
    return {
        "ebn0_db": ebn0_db, "theory_ber": theory,
        "per_type_aggregate": per_type,
        "per_seed_batches": batch_results,
        "seed_heterogeneity": seed_heterogeneity,
        "wire_region_and_edge_tests": [
            {"message_type": kind, "test": name, "p_unadjusted": p, "p_holm_four_location_tests": adj}
            for (kind, name, p, adj) in location_tests],
        "obs_cmd_error_rate_frame_cluster_welch_p": _welch_t_p(obs_frame_errors, cmd_frame_errors),
        "obs_cmd_error_rate_bitwise_fisher_p_supplemental": float(fisher_exact([
            [per_type["OBS"]["bit_errors"], per_type["OBS"]["bits"] - per_type["OBS"]["bit_errors"]],
            [per_type["CMD"]["bit_errors"], per_type["CMD"]["bits"] - per_type["CMD"]["bit_errors"]],
        ], alternative="two-sided").pvalue),
        "errors_by_symbol_position": by_type,
        "multiple_comparison_policy": {
            "aggregate_obs_cmd_theory_tests": "Frame-cluster t-tests with Holm correction across 2 pre-specified tests; bit-level exact binomial tests are supplemental",
            "seed_theory_tests": "Frame-cluster t-tests with Holm correction across 10 batch tests; batch intervals also use Bonferroni 99.5% coverage",
            "seed_heterogeneity": "Holm correction across 2 message types",
            "position_diagnostics": "Holm correction across 4 pre-specified region/edge tests; symbol-position counts are descriptive, not 48 separate significance claims",
        },
    }


def _plot_position(summary: dict, output: Path) -> None:
    pos = summary["errors_by_symbol_position"]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = np.arange(48)
    for kind, marker in (("OBS", "o"), ("CMD", "s")):
        ax.plot(x, pos[kind], marker + "-", ms=4, label=f"{kind}, total errors by symbol")
    for boundary in (8, 14, 40):
        ax.axvline(boundary - 0.5, color="gray", lw=0.8, ls="--")
    ax.set(xlabel="QPSK symbol index in 48-symbol frame", ylabel="Bit errors in symbol (all seed batches)",
           title="8 dB error positions; dashed lines mark wire-field boundaries")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "experiments/p2_r1_config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p2_r1")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    batches = [simulate_batch(kind=kind, seed=seed, frames=config["frames_per_seed_per_type"],
                              ebn0_db=config["ebn0_db"], alpha=config["rrc_alpha"],
                              span=config["rrc_span_symbols"], sps=config["samples_per_symbol"],
                              receive_time_s=config["simulated_receive_time_s"])
               for kind in ("OBS", "CMD") for seed in config["seeds"]]
    summary = {
        "config": config,
        "frozen_parameters": {"QPSK": "P0-C Gray map, Es=1", "RRC": "alpha=0.35, span=10, sps=16, unit-energy taps",
                              "AWGN": "P0-C discrete Eb/N0 convention", "wire": "P0-C Wire v1, 96 bits"},
        "seed_derivation": "numpy.random.SeedSequence([seed, type_id]); type_id OBS=0, CMD=1",
        "frames_per_type": len(config["seeds"]) * config["frames_per_seed_per_type"],
        "total_bits_per_type": len(config["seeds"]) * config["frames_per_seed_per_type"] * 96,
        "analysis": analyze(batches, ebn0_db=config["ebn0_db"]),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "p2_r1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fields = ("message_type", "seed", "frames", "bits", "bit_errors", "ber", "theory_ber",
              "frame_errors", "fer", "accepted_frames", "frame_acceptance", "crc_rejects",
              "semantic_correct_frames", "semantic_recovery_rate", "accepted_but_wrong_payload")
    with (args.output / "p2_r1_seed_batches.csv").open("w", encoding="utf-8") as f:
        f.write(",".join(fields) + "\n")
        for row in summary["analysis"]["per_seed_batches"]:
            f.write(",".join(str(row[k]) for k in fields) + "\n")
    _plot_position(summary["analysis"], args.output / "p2_r1_error_positions.png")
    print(json.dumps({"output": str(args.output), "batches": len(batches),
                      "frames_per_type": summary["frames_per_type"],
                      "ber": {k: v["ber"] for k, v in summary["analysis"]["per_type_aggregate"].items()}}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproducible P1 QPSK/RRC/AWGN experiments and plots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from esc.phy import (  # noqa: E402
    add_awgn_baseband,
    add_awgn_passband,
    matched_filter,
    passband_coherent_demodulate,
    passband_modulate,
    qpsk_demodulate,
    qpsk_modulate,
    qpsk_theoretical_ber,
    raised_cosine_symbol_response,
    rrc_filter,
    rrc_transmit,
    sample_symbols,
    simulate_ber,
    welch_psd,
)


def _seed(master: int, label: str) -> int:
    # Stable across Python processes; do not use Python's randomized hash().
    value = master & 0xFFFFFFFF
    for byte in label.encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def _ber_dict(result, seed: int):
    return {
        "mode": result.mode,
        "ebn0_db": result.ebn0_db,
        "bits_compared": result.bits,
        "bit_errors": result.errors,
        "ber": result.ber,
        "theory_ber": result.theory_ber,
        "upper_95_one_sided": result.upper_95,
        "seed": seed,
    }


def run(config_path: Path, output_dir: Path) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "p1_phy_config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    rs = int(config["symbol_rate_hz"])
    sps = int(config["samples_per_symbol"])
    fs = rs * sps
    fc = int(config["carrier_hz"])
    span = int(config["rrc_span_symbols"])
    alpha = 0.35
    chunk_symbols = int(config["chunk_symbols"])
    master_seed = int(config["master_seed"])

    ber_results = []
    print("Running complex-baseband BER sweep", flush=True)
    for db in config["ebn0_db"]:
        seed = _seed(master_seed, f"baseband:{db}")
        result = simulate_ber(
            ebn0_db=float(db),
            bit_budget=int(config["baseband_bit_budget_per_point"]),
            seed=seed,
            mode="ber_baseband",
            alpha=alpha,
            span=span,
            sps=sps,
            fc_hz=fc,
            rs_hz=rs,
            chunk_symbols=chunk_symbols,
        )
        ber_results.append(_ber_dict(result, seed))
        print(f"  baseband Eb/N0={db:>2} dB: {result.errors}/{result.bits} errors, BER={result.ber:.7g}", flush=True)

    passband_results = []
    print("Running real-passband BER comparison", flush=True)
    for db in config["passband_compare_ebn0_db"]:
        seed = _seed(master_seed, f"passband:{db}")
        result = simulate_ber(
            ebn0_db=float(db),
            bit_budget=int(config["passband_bit_budget_per_point"]),
            seed=seed,
            mode="waveform_passband",
            alpha=alpha,
            span=span,
            sps=sps,
            fc_hz=fc,
            rs_hz=rs,
            chunk_symbols=chunk_symbols,
        )
        passband_results.append(_ber_dict(result, seed))
        print(f"  passband Eb/N0={db:>2} dB: {result.errors}/{result.bits} errors, BER={result.ber:.7g}", flush=True)

    # Fixed-filter numerical diagnostics.
    taps = rrc_filter(alpha=alpha, span=span, sps=sps)
    rc = raised_cosine_symbol_response(taps, sps=sps, symbol_offsets=span)
    center = len(rc) // 2
    isi = rc.copy()
    isi[center] = 0.0
    filter_metrics = {
        "tap_count": int(taps.size),
        "tap_energy": float(np.dot(taps, taps)),
        "tap_symmetry_max_abs": float(np.max(np.abs(taps - taps[::-1]))),
        "tx_group_delay_ms": 1000.0 * (len(taps) - 1) / 2 / fs,
        "tx_rx_group_delay_ms": 1000.0 * (len(taps) - 1) / fs,
        "cascade_main_sample": float(rc[center]),
        "cascade_max_sampled_residual_isi": float(np.max(np.abs(isi))),
        "tx_full_samples_for_96_bit_frame": int(48 * sps + len(taps) - 1),
        "tx_full_window_ms_for_96_bit_frame": 1000.0 * (48 * sps + len(taps) - 1) / fs,
        "nominal_bandwidth_hz": float((1 + alpha) * rs),
        "carrier_upper_edge_hz": float(fc + (1 + alpha) * rs / 2),
        "nyquist_hz": float(fs / 2),
    }

    # Rolloff PSD comparison uses real passband RRC waveforms and fixed seeds.
    fig, ax = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    for index, rolloff in enumerate(config["alpha_sweep"]):
        rng = np.random.default_rng(_seed(master_seed, f"psd:{rolloff}"))
        symbols = qpsk_modulate(rng.integers(0, 2, size=2 * 4096, dtype=np.uint8))
        h = rrc_filter(alpha=float(rolloff), span=span, sps=sps)
        tx_bb = rrc_transmit(symbols, h, sps=sps)
        tx_pb = passband_modulate(tx_bb, fc_hz=fc, fs_hz=fs)
        frequencies, density = welch_psd(tx_pb, fs_hz=fs, nperseg=8192)
        keep = (frequencies >= fc - 12_000) & (frequencies <= fc + 12_000)
        ax.plot(frequencies[keep] / 1000.0, 10 * np.log10(np.maximum(density[keep], 1e-15)),
                label=fr"$\alpha={rolloff}$")
    ax.set(title="Real passband QPSK/RRC power spectral density", xlabel="Frequency (kHz)",
           ylabel="PSD (dB/Hz)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.savefig(output_dir / "rrc_rolloff_psd.png", dpi=170)
    plt.close(fig)

    # Short real-passband waveform and constellation at 4 dB.
    visual_bits = np.random.default_rng(_seed(master_seed, "visual_bits")).integers(
        0, 2, size=2 * 128, dtype=np.uint8
    )
    visual_symbols = qpsk_modulate(visual_bits)
    visual_tx_bb = rrc_transmit(visual_symbols, taps, sps=sps)
    visual_tx_pb = passband_modulate(visual_tx_bb, fc_hz=fc, fs_hz=fs)
    visual_rx_pb = add_awgn_passband(visual_tx_pb, 4.0,
                                     np.random.default_rng(_seed(master_seed, "visual_awgn")))
    visual_rx_symbols = passband_coherent_demodulate(
        visual_rx_pb, taps, fc_hz=fc, fs_hz=fs, symbol_count=visual_symbols.size, sps=sps
    )
    # Mark only the interior symbols to avoid finite-burst edge transients.
    interior = slice(span, -span)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)
    sample_count = min(12 * sps, visual_tx_pb.size)
    time_ms = np.arange(sample_count) / fs * 1000.0
    axes[0].plot(time_ms, visual_tx_pb[:sample_count], label="Tx passband", linewidth=1.0)
    axes[0].plot(time_ms, visual_rx_pb[:sample_count], label="Rx passband with AWGN", alpha=0.7, linewidth=0.8)
    axes[0].set(title="20 kHz real passband waveform (4 dB Eb/N0)", xlabel="Time (ms)", ylabel="Amplitude")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[1].scatter(visual_rx_symbols[interior].real, visual_rx_symbols[interior].imag,
                    s=14, alpha=0.55, label="Matched-filter samples")
    axes[1].scatter(visual_symbols[interior].real, visual_symbols[interior].imag,
                    s=34, marker="x", label="Transmitted symbols")
    axes[1].set(title="Passband coherent receive constellation", xlabel="I", ylabel="Q",
                xlim=(-1.5, 1.5), ylim=(-1.5, 1.5), aspect="equal")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    fig.savefig(output_dir / "passband_waveform_constellation.png", dpi=170)
    plt.close(fig)

    # BER comparison plot; zero empirical errors remain plotted at a floor and labeled by counts in JSON.
    fig, ax = plt.subplots(figsize=(8, 5.2), constrained_layout=True)
    dbs = np.asarray(config["ebn0_db"], dtype=float)
    theory = np.asarray(qpsk_theoretical_ber(dbs))
    bb = np.asarray([row["ber"] for row in ber_results])
    bb_plot = np.where(bb > 0, bb, 0.5 / np.asarray([r["bits_compared"] for r in ber_results]))
    ax.semilogy(dbs, theory, "k-", label="QPSK theory")
    ax.semilogy(dbs, bb_plot, "o-", label="Complex baseband RRC/AWGN")
    pb_dbs = np.asarray([row["ebn0_db"] for row in passband_results], dtype=float)
    pb_ber = np.asarray([row["ber"] for row in passband_results])
    pb_n = np.asarray([row["bits_compared"] for row in passband_results])
    ax.semilogy(pb_dbs, np.where(pb_ber > 0, pb_ber, 0.5 / pb_n), "s", label="Real passband RRC/AWGN")
    ax.set(title="Gray QPSK BER: theory and measured errors", xlabel="$E_b/N_0$ (dB)", ylabel="BER")
    ax.set_xticks(dbs)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.savefig(output_dir / "ber_theory_vs_simulation.png", dpi=170)
    plt.close(fig)

    summary = {
        "status": "executed",
        "frozen_spec": config["frozen_spec"],
        "experiment_config": config,
        "sampling": {"rs_hz": rs, "sps": sps, "fs_hz": fs, "fc_hz": fc},
        "filter_metrics": filter_metrics,
        "baseband_ber": ber_results,
        "passband_ber": passband_results,
        "figures": [
            "ber_theory_vs_simulation.png",
            "rrc_rolloff_psd.png",
            "passband_waveform_constellation.png",
        ],
        "interpretation": {
            "zero_errors": "Never interpreted as BER=0; the exact one-sided 95% upper bound is reported.",
            "ber_bits": "Counts exclude span symbols at both boundaries of every independent waveform chunk.",
            "passband": "Uses real carrier-modulated samples, real AWGN, coherent mixing, RRC matched filtering and timed decisions.",
        },
    }
    summary_path = output_dir / "p1_phy_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "experiments/p1_phy_config.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "artifacts/p1_phy")
    args = parser.parse_args()
    summary = run(args.config, args.output)
    print(f"Wrote {args.output / 'p1_phy_summary.json'}")
    for result in summary["baseband_ber"]:
        print(f"{result['ebn0_db']:>2.0f} dB BB: {result['bit_errors']}/{result['bits_compared']} BER={result['ber']:.7g} upper95={result['upper_95_one_sided']:.7g}")
    for result in summary["passband_ber"]:
        print(f"{result['ebn0_db']:>2.0f} dB PB: {result['bit_errors']}/{result['bits_compared']} BER={result['ber']:.7g} upper95={result['upper_95_one_sided']:.7g}")


if __name__ == "__main__":
    main()

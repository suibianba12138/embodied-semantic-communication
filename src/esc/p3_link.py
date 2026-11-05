"""Small helpers for the P0-C P3 robot-link simulation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from esc import frame


def cycle_event_times(cycle_start_s: float) -> dict[str, float]:
    """P0-C 100 ms cycle event times (seconds on MuJoCo's simulation clock)."""
    start = float(cycle_start_s)
    if not np.isfinite(start) or start < 0.0:
        raise ValueError("cycle_start_s must be finite and non-negative")
    return {
        "obs_capture_s": start,
        "obs_decode_s": start + 0.015,
        "controller_tick_s": start + 0.020,
        "cmd_decode_s": start + 0.035,
        "policy_apply_s": start + 0.040,
        "next_cycle_s": start + 0.100,
    }


def frame_qpsk_roundtrip(
    bits: NDArray[np.generic], *, ebn0_db: float | None, seed: int
) -> NDArray[np.uint8]:
    """Transmit one full 96-bit Wire v1 frame through full RRC/QPSK filtering.

    ``None`` means no AWGN. The complete 48-symbol frame is retained; no chunk
    edge symbols are dropped. AWGN uses the frozen P0-C discrete baseband
    convention and a caller-controlled per-frame seed.
    """
    tx_bits = np.asarray(bits)
    if tx_bits.ndim != 1 or tx_bits.size != frame.FRAME_BITS:
        raise ValueError("P3 transport requires exactly one 96-bit frame")
    if not np.all((tx_bits == 0) | (tx_bits == 1)):
        raise ValueError("frame bits must be binary")
    tx_bits = tx_bits.astype(np.uint8, copy=False)
    from esc import phy

    taps = phy.rrc_filter(alpha=0.35, span=10, sps=16)
    symbols = phy.qpsk_modulate(tx_bits)
    tx_samples = phy.rrc_transmit(symbols, taps, sps=16)
    if ebn0_db is None:
        rx_samples = tx_samples
    else:
        rng = np.random.default_rng(seed)
        rx_samples = phy.add_awgn_baseband(tx_samples, ebn0_db, rng)
    filtered = phy.matched_filter(rx_samples, taps)
    rx_symbols = phy.sample_symbols(
        filtered, symbol_count=48, sps=16, delay_samples=160
    )
    return phy.qpsk_demodulate(rx_symbols)

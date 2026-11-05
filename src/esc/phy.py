"""Gray-QPSK, unit-energy RRC, and discrete AWGN physical-layer primitives.

All noise functions use the frozen P0-C discrete energy convention:
``Eb=0.5``, ``N0=Eb/(Eb/N0)``, complex-baseband sample variance ``N0``,
and real-passband sample variance ``N0/2``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erfc, pi, sqrt
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.signal import upfirdn, welch

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
BitArray = NDArray[np.uint8]


@dataclass(frozen=True)
class BERResult:
    mode: str
    ebn0_db: float
    bits: int
    errors: int
    ber: float
    theory_ber: float
    upper_95: float


def _as_bits(bits: NDArray[np.generic]) -> BitArray:
    values = np.asarray(bits)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("bits must be a non-empty one-dimensional array")
    if not np.all((values == 0) | (values == 1)):
        raise ValueError("bits must contain only 0 and 1")
    if values.size % 2:
        raise ValueError("QPSK requires an even number of bits")
    return values.astype(np.uint8, copy=False)


def qpsk_modulate(bits: NDArray[np.generic]) -> ComplexArray:
    """Map MSB-first pairs with P0-C Gray mapping and average Es=1."""
    values = _as_bits(bits).reshape(-1, 2)
    i_sign = 1.0 - 2.0 * values[:, 0]
    q_sign = 1.0 - 2.0 * values[:, 1]
    return ((i_sign + 1j * q_sign) / sqrt(2.0)).astype(np.complex128)


def qpsk_demodulate(symbols: NDArray[np.generic]) -> BitArray:
    """Hard decide I/Q at zero; exact zero is assigned to the positive side."""
    values = np.asarray(symbols, dtype=np.complex128)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("symbols must be a non-empty finite one-dimensional array")
    bits = np.empty((values.size, 2), dtype=np.uint8)
    bits[:, 0] = values.real < 0.0
    bits[:, 1] = values.imag < 0.0
    return bits.reshape(-1)


def rrc_filter(alpha: float = 0.35, span: int = 10, sps: int = 16) -> FloatArray:
    """Design the P0-C symmetric RRC taps and normalize sum(h**2) to one."""
    if not (0.0 < alpha <= 1.0):
        raise ValueError("alpha must be in (0, 1]")
    if isinstance(span, bool) or int(span) != span or span <= 0:
        raise ValueError("span must be a positive integer")
    if isinstance(sps, bool) or int(sps) != sps or sps <= 0:
        raise ValueError("sps must be a positive integer")
    count = int(span) * int(sps) + 1
    t = (np.arange(count, dtype=np.float64) - (count - 1) / 2.0) / float(sps)
    taps = np.empty_like(t)
    at_zero = np.isclose(t, 0.0, atol=1e-14, rtol=0.0)
    at_singularity = np.isclose(np.abs(t), 1.0 / (4.0 * alpha), atol=1e-12, rtol=0.0)
    regular = ~(at_zero | at_singularity)
    taps[regular] = (
        np.sin(pi * t[regular] * (1.0 - alpha))
        + 4.0 * alpha * t[regular] * np.cos(pi * t[regular] * (1.0 + alpha))
    ) / (pi * t[regular] * (1.0 - (4.0 * alpha * t[regular]) ** 2))
    taps[at_zero] = 1.0 + alpha * (4.0 / pi - 1.0)
    taps[at_singularity] = (alpha / sqrt(2.0)) * (
        (1.0 + 2.0 / pi) * np.sin(pi / (4.0 * alpha))
        + (1.0 - 2.0 / pi) * np.cos(pi / (4.0 * alpha))
    )
    taps = (taps + taps[::-1]) / 2.0
    taps /= np.sqrt(np.dot(taps, taps))
    return taps


def rrc_transmit(symbols: NDArray[np.generic], taps: NDArray[np.generic], sps: int = 16) -> ComplexArray:
    """Zero-insert by sps and full-convolve with the real transmit RRC."""
    values = np.asarray(symbols, dtype=np.complex128)
    coeffs = np.asarray(taps, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("symbols must be a non-empty finite one-dimensional array")
    if coeffs.ndim != 1 or coeffs.size == 0 or not np.isfinite(coeffs).all():
        raise ValueError("taps must be a non-empty finite one-dimensional array")
    if isinstance(sps, bool) or int(sps) != sps or sps <= 0:
        raise ValueError("sps must be a positive integer")
    upsampled = np.zeros(values.size * int(sps), dtype=np.complex128)
    upsampled[:: int(sps)] = values
    return upfirdn(coeffs, upsampled).astype(np.complex128, copy=False)


def matched_filter(samples: NDArray[np.generic], taps: NDArray[np.generic]) -> ComplexArray:
    """Full-convolve samples with the same symmetric unit-energy RRC taps."""
    values = np.asarray(samples, dtype=np.complex128)
    coeffs = np.asarray(taps, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("samples must be a non-empty finite one-dimensional array")
    if coeffs.ndim != 1 or coeffs.size == 0 or not np.isfinite(coeffs).all():
        raise ValueError("taps must be a non-empty finite one-dimensional array")
    return upfirdn(coeffs, values).astype(np.complex128, copy=False)


def sample_symbols(
    samples: NDArray[np.generic], *, symbol_count: int, sps: int = 16, delay_samples: int = 160
) -> ComplexArray:
    """Sample a full-convolution receive buffer after the specified delay."""
    values = np.asarray(samples, dtype=np.complex128)
    if symbol_count <= 0 or sps <= 0 or delay_samples < 0:
        raise ValueError("symbol_count/sps must be positive and delay_samples non-negative")
    indices = delay_samples + np.arange(symbol_count, dtype=np.int64) * int(sps)
    if values.ndim != 1 or indices[-1] >= values.size:
        raise ValueError("receive buffer is too short for requested symbols and delay")
    return values[indices]


def raised_cosine_symbol_response(
    taps: NDArray[np.generic], *, sps: int = 16, symbol_offsets: int = 10
) -> FloatArray:
    """Return centered TX/RX cascade samples at integer-symbol offsets."""
    coeffs = np.asarray(taps, dtype=np.float64)
    if coeffs.ndim != 1 or coeffs.size == 0 or coeffs.size % 2 != 1:
        raise ValueError("taps must be a non-empty odd-length vector")
    response = np.convolve(coeffs, coeffs)
    center = response.size // 2
    offsets = np.arange(-symbol_offsets, symbol_offsets + 1) * int(sps)
    indices = center + offsets
    if indices[0] < 0 or indices[-1] >= response.size:
        raise ValueError("requested offsets exceed cascade response")
    return response[indices]


def n0_from_ebn0(ebn0_db: float) -> float:
    """P0-C discrete convention: Eb=Es/2=0.5 and N0=Eb/gamma_b."""
    if not np.isfinite(ebn0_db):
        raise ValueError("Eb/N0 must be finite")
    gamma_b = 10.0 ** (float(ebn0_db) / 10.0)
    return 0.5 / gamma_b


def add_awgn_baseband(
    samples: NDArray[np.generic], ebn0_db: float, rng: np.random.Generator
) -> ComplexArray:
    """Add complex sampled noise with E|w|^2=N0 (I/Q variance N0/2)."""
    values = np.asarray(samples, dtype=np.complex128)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("samples must be a finite one-dimensional array")
    sigma = sqrt(n0_from_ebn0(ebn0_db) / 2.0)
    noise = sigma * (rng.standard_normal(values.size) + 1j * rng.standard_normal(values.size))
    return values + noise


def add_awgn_passband(
    samples: NDArray[np.generic], ebn0_db: float, rng: np.random.Generator
) -> FloatArray:
    """Add real sampled noise with variance N0/2 per the frozen P0-C convention."""
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("samples must be a finite one-dimensional array")
    return values + sqrt(n0_from_ebn0(ebn0_db) / 2.0) * rng.standard_normal(values.size)


def passband_modulate(baseband: NDArray[np.generic], *, fc_hz: float, fs_hz: float) -> FloatArray:
    """Apply the frozen real passband scale sqrt(2) Re{x[n] exp(j 2πfcn/fs)}."""
    values = np.asarray(baseband, dtype=np.complex128)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("baseband must be a non-empty finite one-dimensional array")
    if not np.isfinite(fc_hz) or not np.isfinite(fs_hz) or fs_hz <= 0.0 or not (0.0 < fc_hz < fs_hz / 2.0):
        raise ValueError("carrier must satisfy 0 < fc < fs/2")
    n = np.arange(values.size, dtype=np.float64)
    carrier = np.exp(2j * pi * fc_hz * n / fs_hz)
    return (sqrt(2.0) * np.real(values * carrier)).astype(np.float64)


def passband_coherent_demodulate(
    passband: NDArray[np.generic],
    taps: NDArray[np.generic],
    *,
    fc_hz: float,
    fs_hz: float,
    symbol_count: int,
    sps: int = 16,
) -> ComplexArray:
    """Ideal coherent downconversion, RRC matched filtering, and timed sampling."""
    values = np.asarray(passband, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("passband must be a non-empty finite one-dimensional array")
    if not np.isfinite(fc_hz) or not np.isfinite(fs_hz) or fs_hz <= 0.0 or not (0.0 < fc_hz < fs_hz / 2.0):
        raise ValueError("carrier must satisfy 0 < fc < fs/2")
    n = np.arange(values.size, dtype=np.float64)
    mixer = sqrt(2.0) * values * np.exp(-2j * pi * fc_hz * n / fs_hz)
    filtered = matched_filter(mixer, taps)
    total_delay = 2 * (len(taps) - 1) // 2
    return sample_symbols(filtered, symbol_count=symbol_count, sps=sps, delay_samples=total_delay)


def qpsk_theoretical_ber(ebn0_db: NDArray[np.generic] | float) -> FloatArray | float:
    """Uncoded coherent Gray-QPSK/AWGN BER: 0.5 erfc(sqrt(Eb/N0))."""
    values = np.asarray(ebn0_db, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Eb/N0 values must be finite")
    gamma = np.power(10.0, values / 10.0)
    output = np.vectorize(lambda x: 0.5 * erfc(sqrt(float(x))), otypes=[np.float64])(gamma)
    return float(output) if output.ndim == 0 else output


def ber_count(tx_bits: NDArray[np.generic], rx_bits: NDArray[np.generic]) -> tuple[int, int, float]:
    """Return compared bit count, error count, and BER."""
    tx = np.asarray(tx_bits)
    rx = np.asarray(rx_bits)
    if tx.ndim != 1 or rx.ndim != 1 or tx.size == 0 or tx.size != rx.size:
        raise ValueError("tx_bits and rx_bits must be non-empty equal-length vectors")
    if not np.all((tx == 0) | (tx == 1)) or not np.all((rx == 0) | (rx == 1)):
        raise ValueError("bit arrays must contain only 0 and 1")
    errors = int(np.count_nonzero(tx != rx))
    return int(tx.size), errors, errors / int(tx.size)


def upper_ber_bound_95(errors: int, bits: int) -> float:
    """One-sided exact 95% Clopper-Pearson upper confidence bound."""
    if bits <= 0 or errors < 0 or errors > bits:
        raise ValueError("require 0 <= errors <= bits and bits > 0")
    if errors == bits:
        return 1.0
    from scipy.stats import beta

    return float(beta.ppf(0.95, errors + 1, bits - errors))


def welch_psd(
    samples: NDArray[np.generic], *, fs_hz: float, nperseg: int = 4096
) -> tuple[FloatArray, FloatArray]:
    """Return fftshifted two-sided Welch PSD and frequency grid."""
    values = np.asarray(samples)
    if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
        raise ValueError("samples must be a finite one-dimensional vector")
    if not np.isfinite(fs_hz) or fs_hz <= 0.0:
        raise ValueError("fs_hz must be finite and positive")
    freqs, density = welch(values, fs=fs_hz, nperseg=min(int(nperseg), values.size),
                           return_onesided=False, scaling="density")
    order = np.fft.fftshift(np.arange(freqs.size))
    return np.fft.fftshift(freqs).astype(np.float64), np.fft.fftshift(density).astype(np.float64)


def simulate_ber(
    *,
    ebn0_db: float,
    bit_budget: int,
    seed: int,
    mode: Literal["ber_baseband", "waveform_passband"],
    alpha: float = 0.35,
    span: int = 10,
    sps: int = 16,
    fc_hz: float = 20_000.0,
    rs_hz: float = 4_800.0,
    chunk_symbols: int = 8192,
) -> BERResult:
    """Stream a full RRC TX/AWGN/RRC RX BER experiment in bounded memory.

    Ten symbols at each chunk edge are omitted from statistics because a
    standalone chunk lacks neighboring symbols within the finite TX/RX pulse
    support. With span=10 this removes only a small, reported number of bits.
    """
    if bit_budget < 2 or bit_budget % 2:
        raise ValueError("bit_budget must be a positive even number")
    if chunk_symbols <= 20:
        raise ValueError("chunk_symbols must exceed the 20-symbol filter transient")
    mode_value = str(mode)
    if mode_value not in ("ber_baseband", "waveform_passband"):
        raise ValueError("unsupported BER mode")
    fs_hz = rs_hz * sps
    if mode_value == "waveform_passband" and fc_hz + (1.0 + alpha) * rs_hz / 2.0 >= fs_hz / 2.0:
        raise ValueError("passband spectrum would exceed Nyquist")
    rng = np.random.default_rng(seed)
    taps = rrc_filter(alpha=alpha, span=span, sps=sps)
    total_bits = bit_errors = 0
    total_symbols = bit_budget // 2
    symbols_done = 0
    transient = span
    while symbols_done < total_symbols:
        count = min(chunk_symbols, total_symbols - symbols_done)
        bits = rng.integers(0, 2, size=2 * count, dtype=np.uint8)
        symbols = qpsk_modulate(bits)
        tx_bb = rrc_transmit(symbols, taps, sps=sps)
        if mode_value == "ber_baseband":
            rx_input = add_awgn_baseband(tx_bb, ebn0_db, rng)
            rx_bb = matched_filter(rx_input, taps)
            rx_symbols = sample_symbols(rx_bb, symbol_count=count, sps=sps, delay_samples=2 * (len(taps) - 1) // 2)
        else:
            tx_pb = passband_modulate(tx_bb, fc_hz=fc_hz, fs_hz=fs_hz)
            rx_pb = add_awgn_passband(tx_pb, ebn0_db, rng)
            rx_symbols = passband_coherent_demodulate(
                rx_pb, taps, fc_hz=fc_hz, fs_hz=fs_hz, symbol_count=count, sps=sps
            )
        rx_bits = qpsk_demodulate(rx_symbols)
        valid_start = transient
        valid_end = count - transient
        if valid_end > valid_start:
            start_bit = 2 * valid_start
            stop_bit = 2 * valid_end
            errors = int(np.count_nonzero(bits[start_bit:stop_bit] != rx_bits[start_bit:stop_bit]))
            compared = stop_bit - start_bit
            bit_errors += errors
            total_bits += compared
        symbols_done += count
    ber = bit_errors / total_bits
    theory = float(qpsk_theoretical_ber(ebn0_db))
    return BERResult(mode_value, float(ebn0_db), total_bits, bit_errors, ber, theory,
                     upper_ber_bound_95(bit_errors, total_bits))

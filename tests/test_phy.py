import numpy as np
import pytest

from esc import phy


def test_gray_qpsk_mapping_and_all_pairs_roundtrip():
    bits = np.array([0, 0, 0, 1, 1, 1, 1, 0], dtype=np.uint8)
    symbols = phy.qpsk_modulate(bits)
    expected = np.array([1 + 1j, 1 - 1j, -1 - 1j, -1 + 1j]) / np.sqrt(2)
    np.testing.assert_allclose(symbols, expected, atol=0.0, rtol=0.0)
    np.testing.assert_array_equal(phy.qpsk_demodulate(symbols), bits)


@pytest.mark.parametrize("bits", [[], [0], [0, 2], [0, 1, 0]])
def test_modulator_rejects_invalid_bit_sequences(bits):
    with pytest.raises(ValueError):
        phy.qpsk_modulate(np.asarray(bits))


def test_rrc_is_frozen_length_symmetric_and_unit_energy():
    taps = phy.rrc_filter(alpha=0.35, span=10, sps=16)
    assert taps.shape == (161,)
    np.testing.assert_allclose(taps, taps[::-1], atol=1e-14, rtol=0.0)
    assert abs(float(np.dot(taps, taps)) - 1.0) < 1e-12


@pytest.mark.parametrize("alpha", [0.2, 0.35, 0.5])
def test_rrc_rolloff_sweep_taps_remain_finite_and_unit_energy(alpha):
    taps = phy.rrc_filter(alpha=alpha, span=10, sps=16)
    assert taps.shape == (161,)
    assert np.isfinite(taps).all()
    assert abs(float(np.dot(taps, taps)) - 1.0) < 1e-12


def test_tx_rx_full_lengths_group_delay_and_low_residual_isi():
    symbols = phy.qpsk_modulate(np.tile([0, 0, 0, 1, 1, 1, 1, 0], 32))
    taps = phy.rrc_filter(alpha=0.35, span=10, sps=16)
    tx = phy.rrc_transmit(symbols, taps, sps=16)
    rx = phy.matched_filter(tx, taps)
    assert len(tx) == len(symbols) * 16 + 160
    assert len(rx) == len(symbols) * 16 + 320
    recovered = phy.sample_symbols(rx, symbol_count=len(symbols), sps=16, delay_samples=160)
    np.testing.assert_allclose(recovered, symbols, atol=0.012, rtol=0.0)
    response = phy.raised_cosine_symbol_response(taps, sps=16, symbol_offsets=10)
    assert abs(response[len(response) // 2] - 1.0) < 1e-12
    neighbors = np.delete(response, len(response) // 2)
    assert np.max(np.abs(neighbors)) < 0.01


def test_p0c_awgn_variances_and_seed_reproducibility():
    ebn0_db = 4.0
    n0 = 0.5 / (10.0 ** (ebn0_db / 10.0))
    zeros = np.zeros(1_000_000, dtype=np.complex128)
    bb1 = phy.add_awgn_baseband(zeros, ebn0_db, np.random.default_rng(17))
    bb2 = phy.add_awgn_baseband(zeros, ebn0_db, np.random.default_rng(17))
    np.testing.assert_array_equal(bb1, bb2)
    assert abs(np.mean(np.abs(bb1) ** 2) / n0 - 1.0) < 0.01
    assert abs(np.var(bb1.real) / (n0 / 2.0) - 1.0) < 0.01

    pb = phy.add_awgn_passband(np.zeros(1_000_000), ebn0_db, np.random.default_rng(18))
    assert abs(np.var(pb) / (n0 / 2.0) - 1.0) < 0.01


def test_theoretical_qpsk_ber_matches_closed_form():
    expected = np.array([0.5 * __import__("math").erfc(np.sqrt(10.0 ** (db / 10.0))) for db in (0, 4, 8)])
    np.testing.assert_allclose(phy.qpsk_theoretical_ber(np.array([0.0, 4.0, 8.0])), expected)


def test_passband_mod_demod_noiseless_roundtrip():
    bits = np.random.default_rng(123).integers(0, 2, size=4096, dtype=np.uint8)
    symbols = phy.qpsk_modulate(bits)
    taps = phy.rrc_filter(alpha=0.35, span=10, sps=16)
    bb = phy.rrc_transmit(symbols, taps, sps=16)
    pb = phy.passband_modulate(bb, fc_hz=20_000.0, fs_hz=76_800.0)
    recovered_bb = phy.passband_coherent_demodulate(pb, taps, fc_hz=20_000.0, fs_hz=76_800.0,
                                                     symbol_count=len(symbols), sps=16)
    np.testing.assert_array_equal(phy.qpsk_demodulate(recovered_bb), bits)


@pytest.mark.parametrize("mode", ["ber_baseband", "waveform_passband"])
def test_streaming_ber_estimate_is_seeded_and_statistically_plausible(mode):
    result = phy.simulate_ber(
        ebn0_db=0.0,
        bit_budget=40_000,
        seed=20261104,
        mode=mode,
        chunk_symbols=8192,
    )
    repeated = phy.simulate_ber(
        ebn0_db=0.0,
        bit_budget=40_000,
        seed=20261104,
        mode=mode,
        chunk_symbols=8192,
    )
    assert result.bits == repeated.bits
    assert result.errors == repeated.errors
    theory = result.theory_ber
    standard_error = np.sqrt(theory * (1.0 - theory) / result.bits)
    assert abs(result.ber - theory) < 5.0 * standard_error
    assert result.upper_95 >= result.ber


def test_invalid_phy_parameters_fail_closed():
    with pytest.raises(ValueError):
        phy.rrc_filter(alpha=0.0, span=10, sps=16)
    with pytest.raises(ValueError):
        phy.passband_modulate(np.ones(4, dtype=complex), fc_hz=40_000, fs_hz=76_800)

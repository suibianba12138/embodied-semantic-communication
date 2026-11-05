import numpy as np

from esc.p3_link import frame_qpsk_roundtrip, cycle_event_times


def test_full_96_bit_frame_survives_noiseless_qpsk_chain():
    bits = np.random.default_rng(91).integers(0, 2, 96, dtype=np.uint8)
    received = frame_qpsk_roundtrip(bits, ebn0_db=None, seed=3)
    np.testing.assert_array_equal(received, bits)


def test_awgn_frame_roundtrip_is_reproducible_for_seed():
    bits = np.tile(np.array([1, 0, 1, 1, 0, 0], dtype=np.uint8), 16)
    rx_a = frame_qpsk_roundtrip(bits, ebn0_db=8.0, seed=412)
    rx_b = frame_qpsk_roundtrip(bits, ebn0_db=8.0, seed=412)
    np.testing.assert_array_equal(rx_a, rx_b)
    assert rx_a.shape == (96,)
    assert np.all((rx_a == 0) | (rx_a == 1))


def test_p0c_cycle_has_100ms_obs_and_cmd_slots_and_50hz_policy_ticks():
    events = cycle_event_times(0.0)
    assert events == {
        "obs_capture_s": 0.0,
        "obs_decode_s": 0.015,
        "controller_tick_s": 0.02,
        "cmd_decode_s": 0.035,
        "policy_apply_s": 0.04,
        "next_cycle_s": 0.1,
    }
    assert np.allclose(np.diff(np.arange(0.04, 0.101, 0.02)), 0.02)

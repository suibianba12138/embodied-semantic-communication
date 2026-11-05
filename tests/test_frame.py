import numpy as np
import pytest

from esc import frame
from esc import phy


def test_crc16_ccitt_false_standard_vector():
    assert frame.crc16_ccitt_false(b"123456789") == 0x29B1


def test_wire_v1_is_exactly_96_bits_msb_first_and_roundtrips_obs():
    message = frame.ObsMessage(color_id="red", valid=True, range_m=0.6,
                               bearing_rad=np.deg2rad(10.0), capture_time_s=12.34)
    bits = frame.encode_obs(message, seq=0xA5)
    assert bits.shape == (96,)
    assert bits.dtype == np.uint8
    assert frame.bits_to_int(bits[:16]) == 0xD391
    parsed = frame.parse_frame(bits)
    assert parsed.status == "accepted"
    assert parsed.seq == 0xA5
    assert parsed.message.color_id == "red"
    assert parsed.message.valid
    assert parsed.message.range_m == pytest.approx(0.60)
    assert parsed.message.bearing_rad == pytest.approx(np.deg2rad(10), abs=np.pi / 1024)


@pytest.mark.parametrize("color", ["red", "blue"])
def test_obs_invalid_is_legal_and_has_zero_measurements(color):
    msg = frame.ObsMessage(color_id=color, valid=False, range_m=None,
                           bearing_rad=None, capture_time_s=40.96)
    bits = frame.encode_obs(msg, seq=7)
    decoded = frame.parse_frame(bits).message
    assert decoded == frame.ObsMessage(color_id=color, valid=False, range_m=None,
                                       bearing_rad=None, capture_time_s=0.0)


def test_obs_quantization_wrap_and_rejects_invalid_values():
    msg = frame.ObsMessage("blue", True, 0.605, np.pi, 409.59)
    decoded = frame.parse_frame(frame.encode_obs(msg, seq=1)).message
    assert decoded.range_m == pytest.approx(0.61)
    assert decoded.bearing_rad == pytest.approx(-np.pi)
    assert decoded.capture_time_s == pytest.approx(40.95, abs=0.005)
    with pytest.raises(ValueError):
        frame.encode_obs(frame.ObsMessage("green", True, 1.0, 0.0, 0.0), seq=0)
    with pytest.raises(ValueError):
        frame.encode_obs(frame.ObsMessage("red", True, 40.96, 0.0, 0.0), seq=0)
    with pytest.raises(ValueError):
        frame.encode_obs(frame.ObsMessage("red", True, float("nan"), 0.0, 0.0), seq=0)
    bad_reserved = frame.rebuild_frame(type_id=0, seq=2, payload=1)
    assert frame.parse_frame(bad_reserved).status == "schema_reject"


def test_cmd_signed_12bit_quantization_modes_and_validation():
    msg = frame.CmdMessage(0.125, -0.237, 0.031, ttl_ms=200, mode="NORMAL")
    parsed = frame.parse_frame(frame.encode_cmd(msg, seq=255))
    assert parsed.status == "accepted"
    assert parsed.message.vx == pytest.approx(0.125)
    assert parsed.message.vy == pytest.approx(-0.237)
    assert parsed.message.wz == pytest.approx(0.031)
    assert parsed.message.ttl_ms == 200
    assert frame.parse_frame(frame.encode_cmd(frame.CmdMessage(0, 0, 0, 200, "ZERO"), seq=0)).message.mode == "ZERO"
    with pytest.raises(ValueError):
        frame.encode_cmd(frame.CmdMessage(2.048, 0, 0), seq=0)
    with pytest.raises(ValueError):
        frame.encode_cmd(frame.CmdMessage(float("inf"), 0, 0), seq=0)
    with pytest.raises(ValueError):
        frame.encode_cmd(frame.CmdMessage(0.1, 0, 0, mode="ZERO"), seq=0)


def test_parser_rejects_length_preamble_crc_header_and_schema_in_order():
    valid = frame.encode_obs(frame.ObsMessage("red", True, 1.0, 0.0, 1.0), seq=3)
    assert frame.parse_frame(valid[:-1]).status == "length_reject"
    bad_pre = valid.copy(); bad_pre[0] ^= 1
    assert frame.parse_frame(bad_pre).status == "preamble_reject"
    bad_crc = valid.copy(); bad_crc[-1] ^= 1
    assert frame.parse_frame(bad_crc).status == "crc_reject"
    bad_header = frame.rebuild_frame(type_id=3, seq=3, payload=frame.extract_payload(valid))
    assert frame.parse_frame(bad_header).status == "header_reject"
    bad_schema = frame.rebuild_frame(type_id=0, seq=3, payload=(3 << 49))
    assert frame.parse_frame(bad_schema).status == "schema_reject"


def test_sequence_wrap_and_duplicate_rejection_are_contextual():
    ctx = frame.ReceiverContext(session_id="s1", session_start_s=0.0)
    msg = frame.ObsMessage("red", False, None, None, 0.0)
    assert frame.receive_frame(frame.encode_obs(msg, seq=255), ctx, now_s=0.05).status == "accepted"
    assert frame.receive_frame(frame.encode_obs(msg, seq=0), ctx, now_s=0.06).status == "accepted"
    assert frame.receive_frame(frame.encode_obs(msg, seq=0), ctx, now_s=0.07).status == "sequence_reject"
    assert frame.receive_frame(frame.encode_obs(msg, seq=255), ctx, now_s=0.08).status == "sequence_reject"


def test_obs_age_tick_wrap_and_cmd_ttl_receive_context():
    ctx = frame.ReceiverContext(session_id="s", session_start_s=40.9)
    obs = frame.ObsMessage("blue", False, None, None, 40.95)
    assert frame.receive_frame(frame.encode_obs(obs, seq=1), ctx, now_s=41.00).status == "accepted"
    stale = frame.ObsMessage("blue", False, None, None, 40.70)
    assert frame.receive_frame(frame.encode_obs(stale, seq=2), ctx, now_s=41.10).status == "ttl_reject"
    cmd = frame.CmdMessage(0.1, 0, 0, ttl_ms=200)
    assert frame.receive_frame(frame.encode_cmd(cmd, seq=1), ctx, now_s=41.1).status == "accepted"
    assert ctx.command_expired(now_s=41.299) is False
    assert ctx.command_expired(now_s=41.3) is True
    assert ctx.command_status(now_s=41.299) == "accepted"
    assert ctx.command_status(now_s=41.3) == "ttl_reject"


def test_session_context_is_bounded_and_sequence_is_per_type():
    ctx = frame.ReceiverContext(session_id="short", session_start_s=0.0, max_session_duration_s=20.0)
    obs = frame.ObsMessage("red", False, None, None, 0.0)
    cmd = frame.CmdMessage(0, 0, 0, mode="ZERO")
    assert frame.receive_frame(frame.encode_obs(obs, seq=9), ctx, now_s=0.01).status == "accepted"
    assert frame.receive_frame(frame.encode_cmd(cmd, seq=9), ctx, now_s=0.01).status == "accepted"
    assert frame.receive_frame(frame.encode_obs(obs, seq=10), ctx, now_s=20.01).status == "sequence_reject"


def test_full_96_bit_qpsk_rrc_noiseless_roundtrip_keeps_every_bit():
    msg = frame.ObsMessage("red", True, 0.6, np.deg2rad(10.0), 1.23)
    bits = frame.encode_obs(msg, seq=17)
    symbols = phy.qpsk_modulate(bits)
    taps = phy.rrc_filter()
    tx = phy.rrc_transmit(symbols, taps, sps=16)
    rx = phy.matched_filter(tx, taps)
    samples = phy.sample_symbols(rx, symbol_count=48, sps=16, delay_samples=160)
    recovered = phy.qpsk_demodulate(samples)
    np.testing.assert_array_equal(recovered, bits)
    assert frame.parse_frame(recovered).status == "accepted"


def test_awgn_end_to_end_semantic_recovery_and_seed_reproducibility():
    msg = frame.CmdMessage(-0.25, 0.1, -0.01, ttl_ms=200)
    bits = frame.encode_cmd(msg, seq=8)

    def transmit(seed):
        rng = np.random.default_rng(seed)
        taps = phy.rrc_filter()
        tx = phy.rrc_transmit(phy.qpsk_modulate(bits), taps, sps=16)
        noisy = phy.add_awgn_baseband(tx, 18.0, rng)
        matched = phy.matched_filter(noisy, taps)
        symbols = phy.sample_symbols(matched, symbol_count=48, sps=16, delay_samples=160)
        return phy.qpsk_demodulate(symbols)

    rx1 = transmit(20261104)
    rx2 = transmit(20261104)
    np.testing.assert_array_equal(rx1, rx2)
    np.testing.assert_array_equal(rx1, bits)
    assert frame.parse_frame(rx1).message == frame.decode_message(msg)

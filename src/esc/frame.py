"""Wire v1 semantic frame codec and bounded receive context (P0-C §3)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

import numpy as np
from numpy.typing import NDArray

BitArray = NDArray[np.uint8]
PREAMBLE = 0xD391
FRAME_BITS = 96
OBS = 0
CMD = 1
OBS_MAX_AGE_TICKS = 20
TICK_MODULUS = 4096


@dataclass(frozen=True)
class ObsMessage:
    color_id: Literal["red", "blue"]
    valid: bool
    range_m: float | None
    bearing_rad: float | None
    capture_time_s: float


@dataclass(frozen=True)
class CmdMessage:
    vx: float
    vy: float
    wz: float
    ttl_ms: int = 200
    mode: Literal["NORMAL", "ZERO"] = "NORMAL"


@dataclass(frozen=True)
class FrameResult:
    status: str
    message_type: str | None = None
    seq: int | None = None
    message: ObsMessage | CmdMessage | None = None
    payload: int | None = None
    detail: str | None = None


def _integer(value: int, *, maximum: int, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if not 0 <= value <= maximum:
        raise ValueError(f"{name} must be in [0, {maximum}]")
    return value


def _finite(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _half_away(value: float) -> int:
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def bits_to_int(bits: NDArray[np.generic]) -> int:
    values = np.asarray(bits)
    if values.ndim != 1 or not np.all((values == 0) | (values == 1)):
        raise ValueError("bits must be a one-dimensional binary vector")
    result = 0
    for bit in values:
        result = (result << 1) | int(bit)
    return result


def int_to_bits(value: int, width: int) -> BitArray:
    if isinstance(width, bool) or int(width) != width or width < 0:
        raise ValueError("width must be a non-negative integer")
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0 or value >= (1 << width):
        raise ValueError("value does not fit the requested width")
    return np.fromiter(((int(value) >> shift) & 1 for shift in range(width - 1, -1, -1)),
                       dtype=np.uint8, count=width)


def bits_to_bytes(bits: NDArray[np.generic]) -> bytes:
    values = np.asarray(bits)
    if values.ndim != 1 or values.size % 8 or not np.all((values == 0) | (values == 1)):
        raise ValueError("bits must be a byte-aligned one-dimensional binary vector")
    return bytes(bits_to_int(values[i:i + 8]) for i in range(0, values.size, 8))


def crc16_ccitt_false(data: bytes | bytearray | memoryview) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xffff, no reflection/xorout."""
    crc = 0xFFFF
    for byte in bytes(data):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _encode_header(type_id: int, seq: int) -> int:
    if isinstance(type_id, bool) or not isinstance(type_id, (int, np.integer)) or not 0 <= type_id <= 3:
        raise ValueError("type_id must fit the two-bit header field")
    return (1 << 10) | (type_id << 8) | _integer(seq, maximum=255, name="seq")


def rebuild_frame(*, type_id: int, seq: int, payload: int) -> BitArray:
    """Pack a raw 52-bit payload; primarily useful for exact parser fixtures."""
    payload = _integer(payload, maximum=(1 << 52) - 1, name="payload")
    header = _encode_header(type_id, seq)
    covered = int_to_bits((header << 52) | payload, 64)
    crc = crc16_ccitt_false(bits_to_bytes(covered))
    return np.concatenate((int_to_bits(PREAMBLE, 16), covered, int_to_bits(crc, 16)))


def _obs_payload(msg: ObsMessage) -> int:
    if msg.color_id not in ("red", "blue"):
        raise ValueError("color_id must be red or blue")
    color = 1 if msg.color_id == "red" else 2
    if not isinstance(msg.valid, (bool, np.bool_)):
        raise ValueError("valid must be boolean")
    tick_time = _finite(msg.capture_time_s, "capture_time_s")
    if tick_time < 0:
        raise ValueError("capture_time_s must be non-negative")
    tick = _half_up(tick_time / 0.01) % TICK_MODULUS
    if msg.valid:
        if msg.range_m is None or msg.bearing_rad is None:
            raise ValueError("valid OBS requires finite range_m and bearing_rad")
        range_m = _finite(msg.range_m, "range_m")
        bearing = _finite(msg.bearing_rad, "bearing_rad")
        if range_m < 0:
            raise ValueError("range_m must be non-negative")
        range_cm = _half_up(range_m * 100.0)
        if range_cm > 4095:
            raise ValueError("range_m exceeds 4095 cm wire range")
        wrapped = (bearing + math.pi) % (2.0 * math.pi) - math.pi
        bearing_q = _half_up(((wrapped + math.pi) / (2.0 * math.pi)) * 1024) % 1024
    else:
        if msg.range_m is not None or msg.bearing_rad is not None:
            raise ValueError("invalid OBS must use None for range_m and bearing_rad")
        range_cm = bearing_q = 0
    payload = (((((color << 1) | int(msg.valid)) << 12 | range_cm) << 10 | bearing_q)
               << 12) | tick
    return payload << 14


def _signed12(value: float, name: str) -> int:
    value = _finite(value, name)
    q = _half_away(value / 0.001)
    if not -2048 <= q <= 2047:
        raise ValueError(f"{name} exceeds signed 12-bit quantized range")
    return q & 0xFFF


def _cmd_payload(msg: CmdMessage) -> int:
    if msg.mode not in ("NORMAL", "ZERO"):
        raise ValueError("mode must be NORMAL or ZERO")
    ttl = _integer(msg.ttl_ms, maximum=2550, name="ttl_ms")
    if ttl == 0 or ttl % 10:
        raise ValueError("ttl_ms must be a positive multiple of 10 ms")
    ttl_q = ttl // 10
    vx, vy, wz = (_signed12(msg.vx, "vx"), _signed12(msg.vy, "vy"), _signed12(msg.wz, "wz"))
    if msg.mode == "ZERO" and (vx != 0 or vy != 0 or wz != 0):
        raise ValueError("ZERO mode requires all quantized velocities to be zero")
    mode = 0 if msg.mode == "NORMAL" else 1
    return ((((((vx << 12) | vy) << 12 | wz) << 8 | ttl_q) << 4 | mode) << 4)


def encode_obs(message: ObsMessage, *, seq: int) -> BitArray:
    return rebuild_frame(type_id=OBS, seq=seq, payload=_obs_payload(message))


def encode_cmd(message: CmdMessage, *, seq: int) -> BitArray:
    return rebuild_frame(type_id=CMD, seq=seq, payload=_cmd_payload(message))


def extract_payload(bits: NDArray[np.generic]) -> int:
    values = np.asarray(bits)
    if values.shape != (FRAME_BITS,) or not np.all((values == 0) | (values == 1)):
        raise ValueError("expected exactly 96 binary bits")
    return bits_to_int(values[28:80])


def _decode_obs(payload: int) -> tuple[ObsMessage | None, str | None]:
    reserved = payload & 0x3FFF
    tick = (payload >> 14) & 0xFFF
    bearing_q = (payload >> 26) & 0x3FF
    range_cm = (payload >> 36) & 0xFFF
    valid = (payload >> 48) & 1
    color = (payload >> 49) & 0x7
    if reserved != 0 or color not in (1, 2):
        return None, "nonzero reserved bits or unsupported color_id"
    if not valid and (range_cm != 0 or bearing_q != 0):
        return None, "invalid OBS must zero range and bearing"
    msg = ObsMessage("red" if color == 1 else "blue", bool(valid),
                     range_cm / 100.0 if valid else None,
                     -math.pi + (2.0 * math.pi * bearing_q / 1024) if valid else None,
                     tick * 0.01)
    return msg, None


def _from_signed12(bits: int) -> int:
    return bits - 4096 if bits & 0x800 else bits


def _decode_cmd(payload: int) -> tuple[CmdMessage | None, str | None]:
    reserved = payload & 0xF
    mode = (payload >> 4) & 0xF
    ttl_q = (payload >> 8) & 0xFF
    wz = _from_signed12((payload >> 16) & 0xFFF)
    vy = _from_signed12((payload >> 28) & 0xFFF)
    vx = _from_signed12((payload >> 40) & 0xFFF)
    if reserved or mode not in (0, 1) or ttl_q == 0:
        return None, "reserved/mode/TTL fields invalid"
    if mode == 1 and (vx != 0 or vy != 0 or wz != 0):
        return None, "ZERO mode requires zero velocities"
    return CmdMessage(vx * 0.001, vy * 0.001, wz * 0.001, ttl_q * 10,
                      "NORMAL" if mode == 0 else "ZERO"), None


def parse_frame(bits: NDArray[np.generic]) -> FrameResult:
    values = np.asarray(bits)
    if values.ndim != 1 or values.size != FRAME_BITS:
        return FrameResult("length_reject")
    if not np.all((values == 0) | (values == 1)):
        return FrameResult("length_reject", detail="non-binary input")
    values = values.astype(np.uint8, copy=False)
    if bits_to_int(values[:16]) != PREAMBLE:
        return FrameResult("preamble_reject")
    covered = values[16:80]
    received_crc = bits_to_int(values[80:96])
    if crc16_ccitt_false(bits_to_bytes(covered)) != received_crc:
        return FrameResult("crc_reject")
    header = bits_to_int(values[16:28])
    version, type_id, seq = header >> 10, (header >> 8) & 0x3, header & 0xFF
    if version != 1 or type_id not in (OBS, CMD):
        return FrameResult("header_reject", seq=seq)
    payload = bits_to_int(values[28:80])
    if type_id == OBS:
        message, error = _decode_obs(payload)
        name = "OBS"
    else:
        message, error = _decode_cmd(payload)
        name = "CMD"
    if error:
        return FrameResult("schema_reject", name, seq, payload=payload, detail=error)
    return FrameResult("accepted", name, seq, message, payload)


def decode_message(message: ObsMessage | CmdMessage) -> ObsMessage | CmdMessage:
    """Return the exact semantic value represented after wire quantization."""
    bits = encode_obs(message, seq=0) if isinstance(message, ObsMessage) else encode_cmd(message, seq=0)
    return parse_frame(bits).message  # type: ignore[return-value]


@dataclass
class ReceiverContext:
    session_id: str
    session_start_s: float
    max_session_duration_s: float = 20.0
    last_seq: dict[str, int] | None = None
    command_received_s: float | None = None
    active_command: CmdMessage | None = None

    def __post_init__(self) -> None:
        self.session_start_s = _finite(self.session_start_s, "session_start_s")
        self.max_session_duration_s = _finite(self.max_session_duration_s, "max_session_duration_s")
        if not self.session_id or self.max_session_duration_s <= 0 or self.max_session_duration_s >= 20.48:
            raise ValueError("context requires an id and a positive session duration below 20.48 s")
        self.last_seq = {} if self.last_seq is None else dict(self.last_seq)

    def command_expired(self, *, now_s: float) -> bool:
        now_s = _finite(now_s, "now_s")
        if self.active_command is None or self.command_received_s is None:
            return True
        deadline = self.command_received_s + self.active_command.ttl_ms / 1000.0
        return now_s >= deadline - 1e-12

    def command_status(self, *, now_s: float) -> str:
        """Admission state for a held command; expiry is reported as ttl_reject."""
        return "ttl_reject" if self.command_expired(now_s=now_s) else "accepted"


def receive_frame(bits: NDArray[np.generic], context: ReceiverContext, *, now_s: float) -> FrameResult:
    now_s = _finite(now_s, "now_s")
    result = parse_frame(bits)
    if result.status != "accepted":
        return result
    elapsed = now_s - context.session_start_s
    if elapsed < 0 or elapsed > context.max_session_duration_s:
        return FrameResult("sequence_reject", result.message_type, result.seq, detail="receiver session expired")
    assert result.message_type is not None and result.seq is not None
    prev = context.last_seq.get(result.message_type) if context.last_seq is not None else None
    if prev is not None:
        delta = (result.seq - prev) & 0xFF
        if not 1 <= delta <= 127:
            return FrameResult("sequence_reject", result.message_type, result.seq, detail="duplicate or old sequence")
    if isinstance(result.message, ObsMessage):
        now_tick = _half_up(max(now_s, 0.0) / 0.01) % TICK_MODULUS
        sent_tick = _half_up(result.message.capture_time_s / 0.01) % TICK_MODULUS
        age_ticks = (now_tick - sent_tick) % TICK_MODULUS
        if age_ticks >= TICK_MODULUS // 2 or age_ticks > OBS_MAX_AGE_TICKS:
            return FrameResult("ttl_reject", result.message_type, result.seq, result.message,
                               result.payload, "OBS age is ambiguous or exceeds 200 ms")
    # Sequence advances only after all admission checks pass.
    context.last_seq[result.message_type] = result.seq
    if isinstance(result.message, CmdMessage):
        context.active_command = result.message
        context.command_received_s = now_s
    return result

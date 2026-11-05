import math

from experiments.p2_semantic import run_link
from esc.frame import ObsMessage, encode_obs, parse_frame


def test_link_experiment_is_reproducible_from_fixed_seed():
    config = {
        "master_seed": 82,
        "ebn0_db": [8],
        "frames_per_type_per_ebn0": 4,
        "simulated_receive_time_s": 0.05,
        "rrc_alpha": 0.35,
        "rrc_span_symbols": 10,
        "samples_per_symbol": 16,
    }
    assert run_link(config) == run_link(config)


def test_boundary_probe_demonstrates_possible_quantization_gate_change():
    raw = ObsMessage("red", True, 0.6001, math.radians(10.01), 1.0)
    decoded = parse_frame(encode_obs(raw, seq=1)).message
    assert (raw.range_m <= 0.6) != (decoded.range_m <= 0.6)
    assert (abs(raw.bearing_rad) <= math.radians(10)) != (abs(decoded.bearing_rad) <= math.radians(10))

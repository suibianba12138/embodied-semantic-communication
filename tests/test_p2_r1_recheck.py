from experiments.p2_r1_recheck import exact_rate, frame_cluster_ber, simulate_batch


def test_r1_batch_is_reproducible_and_tracks_all_wire_positions():
    first = simulate_batch(kind="OBS", seed=53, frames=12)
    second = simulate_batch(kind="OBS", seed=53, frames=12)
    assert first == second
    assert len(first["errors_by_bit_position"]) == 96
    assert len(first["errors_by_symbol_position"]) == 48
    assert first["bits"] == 12 * 96


def test_exact_rate_reports_nonzero_uncertainty_for_no_observed_events():
    estimate = exact_rate(0, 1000)
    assert estimate["rate"] == 0.0
    assert estimate["ci_high"] > 0.0
    cluster = frame_cluster_ber([0] * 100)
    assert cluster["ci_high"] > 0.0

from esc.p3_s1_scene import OBSTACLES, validate_layout


def test_showcase_obstacles_use_multiple_shapes_and_keep_clear_route():
    assert len(OBSTACLES) >= 4
    assert {obstacle.shape for obstacle in OBSTACLES} >= {"box", "cylinder"}
    validate_layout(OBSTACLES)


def test_layout_rejects_obstacle_in_robot_initial_footprint():
    from dataclasses import replace

    obstacle = replace(OBSTACLES[0], x=0.0, y=0.0)
    try:
        validate_layout((obstacle, *OBSTACLES[1:]))
    except ValueError as exc:
        assert "initial footprint" in str(exc)
    else:
        raise AssertionError("an obstacle overlapping the initial footprint was accepted")


def test_p3_s1_v_obstacles_clear_the_original_b_minus_30_trace():
    import json
    from pathlib import Path
    from esc.p3_s1_scene import Obstacle

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "experiments/p3_s1_v_config_v3.json").read_text())
    obstacles = tuple(Obstacle(
        row["name"], row["shape"], *map(float, row["position_xyz"]),
        tuple(map(float, row["size"])),
    ) for row in config["obstacles"])
    route = tuple(tuple(map(float, point)) for point in config["reference_path_xy"])
    validate_layout(obstacles, reference_path_xy=route)
    assert config["scenario_id"] == "B_-30deg_seed0"
    assert len(obstacles) == 6


def test_industrial_assemblies_have_six_distinct_roles_and_keep_reference_route_clear():
    import json
    from pathlib import Path
    from esc.p3_s1_scene import flatten_scene_objects, set_scene_randomization, validate_scene_geoms

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "experiments/p3_s1_v2_industrial_config.json").read_text())
    reference_config = json.loads((root / config["reference_path_config"]).read_text())
    set_scene_randomization(config["layout_randomization"])
    geoms = flatten_scene_objects(config["objects"])
    assert geoms == flatten_scene_objects(config["objects"])
    route = tuple(tuple(map(float, point)) for point in reference_config["reference_path_xy"])
    validate_scene_geoms(geoms, reference_path_xy=route)

    prop_objects = [item for item in config["objects"]
                    if item["name"] != "background_lab_wall"]
    assert len(prop_objects) == 6
    assert len({item["label"] for item in prop_objects}) == 6
    assert sum(geom.collidable for geom in geoms) == 22
    assert sum(not geom.collidable for geom in geoms) == 20
    assert config["render"]["width"] == 1280
    assert config["render"]["height"] == 720


def test_industrial_red_palette_does_not_add_false_red_target_objects():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "experiments/p3_s1_v2_industrial_config.json").read_text())
    for material in config["materials"].values():
        r, g, b, _ = material["rgba"]
        assert not (r > 0.65 and r > g * 1.8 and r > b * 1.8)
    for obj in config["objects"]:
        for part in obj["parts"]:
            r, g, b, _ = part["rgba"]
            assert not (r > 0.65 and r > g * 1.8 and r > b * 1.8)

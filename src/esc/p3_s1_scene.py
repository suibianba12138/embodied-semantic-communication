"""Static collision-scene definition for the P3-S1 showcase."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import cos, hypot, pi, sin, sqrt
from pathlib import Path
import random


@dataclass(frozen=True)
class Obstacle:
    name: str
    shape: str
    x: float
    y: float
    z: float
    size: tuple[float, float, float]


@dataclass(frozen=True)
class SceneGeom:
    """One native MuJoCo primitive in a composed showcase object."""

    name: str
    object_name: str
    shape: str
    x: float
    y: float
    z: float
    size: tuple[float, float, float]
    rgba: tuple[float, float, float, float]
    collidable: bool
    material: str | None = None
    yaw_rad: float = 0.0


def flatten_scene_objects(objects: list[dict]) -> tuple[SceneGeom, ...]:
    """Resolve object-local primitive positions and colors from scene JSON."""
    geoms: list[SceneGeom] = []
    randomization = _SCENE_RANDOMIZATION
    rng = random.Random(int(randomization.get("seed", 0)))
    for obj in objects:
        ox, oy, oz = map(float, obj["origin_xyz"])
        jitter = float(randomization.get("translation_xy_m", 0.0)) if obj.get("randomize_layout", False) else 0.0
        ox += rng.uniform(-jitter, jitter)
        oy += rng.uniform(-jitter, jitter)
        yaw_deg = float(obj.get("yaw_deg", 0.0))
        yaw_jitter = float(randomization.get("yaw_deg", 0.0)) if obj.get("randomize_layout", False) else 0.0
        yaw_rad = (yaw_deg + rng.uniform(-yaw_jitter, yaw_jitter)) * pi / 180.0
        cz, sz = cos(yaw_rad), sin(yaw_rad)
        for part in obj["parts"]:
            offset = tuple(map(float, part.get("offset_xyz", (0.0, 0.0, 0.0))))
            rgba = tuple(map(float, part["rgba"]))
            if len(rgba) != 4:
                raise ValueError(f"RGBA must have four values: {obj['name']}/{part['name']}")
            shape = str(part["shape"])
            if shape not in ("box", "cylinder", "sphere"):
                raise ValueError(f"unsupported primitive shape: {shape}")
            size = tuple(map(float, part["size"]))
            if len(size) != 3 or any(value <= 0.0 for value in size[:2]):
                raise ValueError(f"invalid primitive size: {obj['name']}/{part['name']}")
            geoms.append(SceneGeom(
                name=f"{obj['name']}__{part['name']}", object_name=str(obj["name"]),
                shape=shape, x=ox + offset[0] * cz - offset[1] * sz,
                y=oy + offset[0] * sz + offset[1] * cz,
                z=oz + offset[2], size=size, rgba=rgba,
                collidable=bool(part.get("collidable", False)),
                material=part.get("material", obj.get("material")),
                yaw_rad=yaw_rad + float(part.get("yaw_deg", 0.0)) * pi / 180.0,
            ))
    names = [geom.name for geom in geoms]
    if len(names) != len(set(names)):
        raise ValueError("scene geom names must be unique")
    return tuple(geoms)


_SCENE_RANDOMIZATION: dict[str, float | int] = {"seed": 0, "translation_xy_m": 0.0, "yaw_deg": 0.0}


def set_scene_randomization(config: dict[str, float | int] | None) -> None:
    global _SCENE_RANDOMIZATION
    _SCENE_RANDOMIZATION = dict(config or {"seed": 0, "translation_xy_m": 0.0, "yaw_deg": 0.0})


def validate_scene_geoms(
    geoms: tuple[SceneGeom, ...], *, reference_path_xy: tuple[tuple[float, float], ...],
    robot_radius_m: float = 0.35, route_margin_m: float = 0.15,
    initial_clearance_m: float = 0.35,
) -> None:
    """Check each collidable primitive against the initial footprint and reference path."""
    colliders = [geom for geom in geoms if geom.collidable]
    if not colliders:
        raise ValueError("industrial scene has no collision geometry")
    if len(reference_path_xy) < 2:
        raise ValueError("reference path must contain at least two points")
    for geom in colliders:
        radius = (sqrt(geom.size[0] ** 2 + geom.size[1] ** 2)
                  if geom.shape == "box" else geom.size[0])
        if hypot(geom.x, geom.y) - radius < initial_clearance_m:
            raise ValueError(f"collider overlaps initial footprint: {geom.name}")
        distance = min(
            _point_segment_distance(geom.x, geom.y, a, b)
            for a, b in zip(reference_path_xy, reference_path_xy[1:])
        )
        clearance = distance - radius - robot_radius_m
        if clearance < route_margin_m:
            raise ValueError(
                f"collider encroaches on reference path: {geom.name} "
                f"(estimated clearance {clearance:.3f} m)"
            )


CONFIG_PATH = Path(__file__).resolve().parents[2] / "experiments/p3_s1_multi_obstacle_config.json"
_CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
OBSTACLES: tuple[Obstacle, ...] = tuple(
    Obstacle(
        row["name"], row["shape"], *map(float, row["position_xyz"]),
        tuple(map(float, row["size"])),
    )
    for row in _CONFIG["obstacles"]
)
INITIAL_ROBOT_CLEARANCE_M = float(_CONFIG["reserved_route"]["initial_robot_clearance_m"])
ROUTE_HALF_WIDTH_M = float(_CONFIG["reserved_route"]["half_width_m"])


def _point_segment_distance(px: float, py: float, a: tuple[float, float],
                            b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0.0 and dy == 0.0:
        return hypot(px - a[0], py - a[1])
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy)))
    return hypot(px - (a[0] + t * dx), py - (a[1] + t * dy))


def validate_layout(
    obstacles: tuple[Obstacle, ...], *, reference_path_xy: tuple[tuple[float, float], ...] | None = None,
    robot_radius_m: float = 0.35, route_margin_m: float = 0.15,
    check_reserved_route: bool = True,
) -> None:
    if len(obstacles) < 4:
        raise ValueError("at least four obstacles are required")
    if len({item.name for item in obstacles}) != len(obstacles):
        raise ValueError("obstacle names must be unique")
    if not {item.shape for item in obstacles} >= {"box", "cylinder"}:
        raise ValueError("layout must include boxes and cylinders")
    for obstacle in obstacles:
        if obstacle.shape not in ("box", "cylinder"):
            raise ValueError(f"unsupported obstacle shape: {obstacle.shape}")
        if not all(value > 0.0 for value in obstacle.size[:2]) or obstacle.z <= 0.0:
            raise ValueError(f"invalid obstacle dimensions or height: {obstacle.name}")
        radius = (sqrt(obstacle.size[0] ** 2 + obstacle.size[1] ** 2)
                  if obstacle.shape == "box" else obstacle.size[0])
        if hypot(obstacle.x, obstacle.y) - radius < INITIAL_ROBOT_CLEARANCE_M:
            raise ValueError(f"obstacle overlaps initial footprint: {obstacle.name}")
        if reference_path_xy is None and check_reserved_route:
            lateral_extent = obstacle.size[1] if obstacle.shape == "box" else obstacle.size[0]
            if abs(obstacle.y) - lateral_extent < ROUTE_HALF_WIDTH_M:
                raise ValueError(f"obstacle encroaches on reserved route: {obstacle.name}")
        elif reference_path_xy is not None:
            if len(reference_path_xy) < 2:
                raise ValueError("reference path must contain at least two points")
            path_distance = min(
                _point_segment_distance(obstacle.x, obstacle.y, a, b)
                for a, b in zip(reference_path_xy, reference_path_xy[1:])
            )
            clearance = path_distance - radius - robot_radius_m
            if clearance < route_margin_m:
                raise ValueError(
                    f"obstacle encroaches on reference path: {obstacle.name} "
                    f"(estimated clearance {clearance:.3f} m)"
                )


def add_obstacles_to_mjspec(spec: object, obstacles: tuple[Obstacle, ...] | None = None) -> None:
    """Add static, visibly neutral, collidable geometry to a copied MjSpec."""
    import mujoco

    obstacles = OBSTACLES if obstacles is None else obstacles
    validate_layout(obstacles, check_reserved_route=False)
    for obstacle in obstacles:
        if obstacle.shape == "box":
            geom_type = mujoco.mjtGeom.mjGEOM_BOX
            size = obstacle.size
        else:
            geom_type = mujoco.mjtGeom.mjGEOM_CYLINDER
            size = obstacle.size
        spec.worldbody.add_geom(
            name=obstacle.name,
            pos=(obstacle.x, obstacle.y, obstacle.z),
            type=geom_type,
            size=size,
            rgba=(0.32, 0.36, 0.40, 1.0),
            contype=1,
            conaffinity=1,
            group=0,
        )


def add_industrial_scene_to_mjspec(
    spec: object, geoms: tuple[SceneGeom, ...], materials: dict[str, dict] | None = None,
) -> None:
    """Install composed native geometry and palette materials in a copied MjSpec."""
    import mujoco

    for name, values in (materials or {}).items():
        spec.add_material(
            name=name, rgba=tuple(values["rgba"]), metallic=float(values.get("metallic", 0.0)),
            roughness=float(values.get("roughness", 0.8)),
            reflectance=float(values.get("reflectance", 0.0)),
            specular=float(values.get("specular", 0.2)),
            emission=float(values.get("emission", 0.0)),
        )
    for geom in geoms:
        geom_type = {
            "box": mujoco.mjtGeom.mjGEOM_BOX,
            "cylinder": mujoco.mjtGeom.mjGEOM_CYLINDER,
            "sphere": mujoco.mjtGeom.mjGEOM_SPHERE,
        }[geom.shape]
        spec.worldbody.add_geom(
            name=geom.name, pos=(geom.x, geom.y, geom.z), type=geom_type,
            euler=(0.0, 0.0, geom.yaw_rad), size=geom.size, rgba=geom.rgba, material=geom.material,
            contype=1 if geom.collidable else 0,
            conaffinity=1 if geom.collidable else 0,
            group=0,
        )


def style_industrial_floor(spec: object, palette: dict[str, object]) -> None:
    """Recolor the existing floor material/texture without touching robot or sensor."""
    try:
        floor_material = spec.material("floor_mat")
    except (KeyError, ValueError):
        floor_material = None
    if floor_material is not None:
        floor_material.rgba = tuple(palette["floor_rgba"])
        floor_material.roughness = float(palette.get("floor_roughness", 0.95))
        floor_material.reflectance = 0.0
        floor_material.specular = 0.12
    for texture in spec.textures:
        if texture.name in ("floor", "groundplane", "texplane"):
            concrete = tuple(palette["floor_texture_rgb"])
            texture.rgb1 = concrete
            texture.rgb2 = tuple(palette.get(
                "floor_texture_rgb2", tuple(max(0.0, min(1.0, x * 0.96)) for x in concrete)
            ))
            texture.markrgb = tuple(palette.get("floor_mark_rgb", concrete))

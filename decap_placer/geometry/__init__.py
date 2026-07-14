# decap_placer/geometry/__init__.py
"""
Геометрические утилиты для работы с зоной, keepout, релаксацией и тепловыми via.
Экспортирует основные функции для внешних модулей.
"""

from .boundary import (
    polyline_points,
    ray_boundary_distance,
    polygon_signed_area,
    closest_point_on_polygon,
)
from .keepout import (
    Rect,
    build_keepout,
    find_free_point,
    point_is_clear,
)
from .placement import compute_position
from .relax import relax_1d, relax_positions, get_tangential_axis
from .thermal_grid import get_pad_size, compute_thermal_via_grid

__all__ = [
    # boundary
    "polyline_points",
    "ray_boundary_distance",
    "polygon_signed_area",
    "closest_point_on_polygon",
    # keepout
    "Rect",
    "build_keepout",
    "find_free_point",
    "point_is_clear",
    # placement
    "compute_position",
    # relax
    "relax_1d",
    "relax_positions",
    "get_tangential_axis",
    # thermal_grid
    "get_pad_size",
    "compute_thermal_via_grid",
]
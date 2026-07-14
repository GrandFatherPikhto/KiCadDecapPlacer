# decap_placer/placement/services/position_calculator.py

import math
import logging
from typing import List, Tuple, Dict, Any
from kipy.board_types import Pad, FootprintInstance
from kipy.geometry import Vector2

from ...config import Config, Rule, Spoke, SpokeComponent
from ...geometry.placement import compute_position
from ...geometry.boundary import polyline_points
from ...kicad.adapter import KiCadBoardAdapter
from ...utils.units import MM
from ...exceptions import GeometryError

logger = logging.getLogger(__name__)


class PositionCalculator:
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config

    def compute_raw_positions(
        self,
        target_fp: FootprintInstance,
        boundary_polygon: List[Vector2],
        rules: List[Rule],
        side: str
    ) -> List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]]:
        center = target_fp.position
        raw = []

        for rule in rules:
            for spoke in rule.spokes:
                pad = self.adapter.get_pad_by_number(target_fp, spoke.pad)
                if pad is None:
                    logger.warning(
                        f"У {self.cfg.target_ref} нет площадки {spoke.pad}, "
                        f"пропуск всей спицы ({len(spoke.components)} компонент.)"
                    )
                    continue

                for component in spoke.components:
                    try:
                        dest, direction = compute_position(
                            center=center,
                            pad_pos=pad.position,
                            boundary_polygon=boundary_polygon,
                            placement=component.placement,
                            offset_mm=component.offset_mm
                        )
                    except Exception as e:
                        raise GeometryError(f"Ошибка для {component.ref} (спица {spoke.pad}): {e}")

                    # Применяем сдвиг вдоль границы
                    if spoke.shift_along_boundary_mm != 0.0:
                        nx, ny = direction
                        tx, ty = -ny, nx
                        shift_nm = spoke.shift_along_boundary_mm * MM
                        dest = Vector2.from_xy(
                            int(dest.x + tx * shift_nm),
                            int(dest.y + ty * shift_nm)
                        )
                        logger.debug(
                            f"  {component.ref}: применён сдвиг вдоль границы {spoke.shift_along_boundary_mm:.3f} мм -> "
                            f"({dest.x/MM:.3f}, {dest.y/MM:.3f}) мм"
                        )

                    # Угол – по направлению нормали (без зеркалирования)
                    phi_deg = math.degrees(math.atan2(direction[1], direction[0]))
                    raw.append((component, dest, direction, phi_deg))
                    logger.debug(
                        f"  {component.ref} (спица {spoke.pad}, сырая позиция) -> "
                        f"({dest.x/MM:.3f}, {dest.y/MM:.3f}) мм, угол={phi_deg:.1f}°"
                    )

        return raw
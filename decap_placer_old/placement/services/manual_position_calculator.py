# decap_placer/placement/services/manual_position_calculator.py

import logging
from typing import List, Tuple
from kipy.board_types import FootprintInstance
from kipy.geometry import Vector2

from ...config import Config, Rule, SpokeComponent
from ...kicad.adapter import KiCadBoardAdapter
from ...utils.units import MM

logger = logging.getLogger(__name__)


class ManualPositionCalculator:
    """
    Ручное позиционирование компонентов.
    Все координаты задаются явно в конфиге.
    """

    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config

    def compute_raw_positions(
        self,
        target_fp: FootprintInstance,
        boundary_polygon: List[Vector2],  # не используется
        rules: List[Rule],
        side: str
    ) -> List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]]:
        raw = []
        for rule in rules:
            for spoke in rule.spokes:
                pad = self.adapter.get_pad_by_number(target_fp, spoke.pad)
                if pad is None:
                    logger.warning(f"У {self.cfg.target_ref} нет площадки {spoke.pad}, пропускаем спицу")
                    continue

                pad_pos = pad.position
                anchor_dx, anchor_dy = spoke.manual_anchor_offset_mm
                anchor_pos = Vector2.from_xy(
                    int(pad_pos.x + anchor_dx * MM),
                    int(pad_pos.y + anchor_dy * MM)
                )

                for component in spoke.components:
                    comp_dx, comp_dy = component.manual_offset_mm
                    dest = Vector2.from_xy(
                        int(anchor_pos.x + comp_dx * MM),
                        int(anchor_pos.y + comp_dy * MM)
                    )
                    angle = component.manual_angle_deg
                    raw.append((component, dest, (1.0, 0.0), angle))
                    logger.debug(
                        f"  {component.ref}: ручная позиция ({dest.x/MM:.3f}, {dest.y/MM:.3f}) мм, угол {angle:.1f}°"
                    )
        return raw
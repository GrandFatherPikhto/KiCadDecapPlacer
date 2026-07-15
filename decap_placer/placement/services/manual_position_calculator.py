# decap_placer/placement/services/manual_position_calculator.py

import logging
from typing import List
from kipy.board_types import FootprintInstance

from ...config import Config, Rule
from ...kicad.adapter import KiCadBoardAdapter
from ...geometry.spoke_layout import apply_spoke_geometry
from ..commands import PlacedComponentInfo

logger = logging.getLogger(__name__)


class ManualPositionCalculator:
    """
    Ручное позиционирование компонентов по шаблонам спиц (см.
    geometry/spoke_layout.py). Геометрия зоны (boundary_polygon) больше не
    нужна вообще — позиция полностью определяется pad + spoke.shift/
    rotation + содержимое шаблона.
    """

    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config

    def compute_raw_positions(
        self,
        target_fp: FootprintInstance,
        rules: List[Rule],
        side: str
    ) -> List[PlacedComponentInfo]:
        result = []
        for rule in rules:
            for spoke in rule.spokes:
                if not spoke.enabled:
                    continue
                template = self.cfg.templates.get(spoke.template)
                if template is None:
                    logger.warning(f"Спица на паде {spoke.pad}: шаблон {spoke.template!r} "
                                   f"не найден в templates, спица пропущена")
                    continue

                pad = self.adapter.get_pad_by_number(target_fp, spoke.pad)
                if pad is None:
                    logger.warning(f"У {self.cfg.target_ref} нет площадки {spoke.pad}, "
                                   f"спица пропущена")
                    continue

                layout = apply_spoke_geometry(pad.position, spoke, template, rule.net)

                for comp_layout in (layout.component1, layout.component2):
                    if comp_layout is None:
                        continue
                    result.append(PlacedComponentInfo(
                        ref=comp_layout.ref,
                        dest=comp_layout.position,
                        angle_deg=comp_layout.angle_deg,
                        rotation_deg=spoke.rotation_deg,
                        gnd_via_offset_along_mm=comp_layout.gnd_via_offset_along_mm,
                        gnd_via_offset_across_mm=comp_layout.gnd_via_offset_across_mm,
                        gnd_via_net=comp_layout.gnd_via_net,
                        gnd_via_drill_mm=comp_layout.gnd_via_drill_mm,
                        gnd_via_diameter_mm=comp_layout.gnd_via_diameter_mm,
                    ))
                    logger.debug(
                        f"  {comp_layout.ref}: позиция ({comp_layout.position.x/1e6:.3f}, "
                        f"{comp_layout.position.y/1e6:.3f}) мм, угол {comp_layout.angle_deg:.1f}°"
                    )
        return result

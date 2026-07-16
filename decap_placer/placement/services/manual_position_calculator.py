# decap_placer/placement/services/manual_position_calculator.py

import logging
from typing import List
from kipy.board_types import FootprintInstance

from ...config import Config, Rule
from ...kicad.adapter import KiCadBoardAdapter
from ...geometry.spoke_layout import apply_spoke_geometry
from ..commands import PlacedComponentInfo
from .component_pool import ComponentPool

logger = logging.getLogger(__name__)


class ManualPositionCalculator:
    """
    Ручное позиционирование компонентов по шаблонам спиц (см.
    geometry/spoke_layout.py). Геометрия зоны (boundary_polygon) больше не
    нужна вообще — позиция полностью определяется pad + spoke.shift/
    rotation + содержимое шаблона.

    Конкретные ref компонентов НЕ читаются из конфига — подбираются из
    ComponentPool (по реальной цепи правила + пользовательскому полю
    Role), один пул на правило, разбираемый по очереди при обработке его
    спиц в порядке следования в YAML.
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
            # Собираем ВСЕ роли, нужные хоть одной спице этого правила --
            # пул строится один раз на всё правило, не на каждую спицу.
            roles_needed = set()
            for spoke in rule.spokes:
                if not spoke.enabled:
                    continue
                template = self.cfg.templates.get(spoke.template)
                if template is None:
                    continue
                roles_needed.update(slot.role for slot in template.components)

            pool = ComponentPool(self.adapter, rule.net, roles=sorted(roles_needed))

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

                # Разбираем пул по ролям, нужным ИМЕННО этому шаблону --
                # ValidationError из pool.pop() фатально всплывёт наружу,
                # если на какую-то роль не хватило компонентов.
                role_to_ref = {slot.role: pool.pop(slot.role, spoke.pad) for slot in template.components}

                layout = apply_spoke_geometry(pad.position, spoke, template, rule.net, role_to_ref)

                for comp_layout in layout.components:
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
                        f"  {comp_layout.ref} (роль {comp_layout.role}, пад {spoke.pad}): "
                        f"позиция ({comp_layout.position.x/1e6:.3f}, {comp_layout.position.y/1e6:.3f}) мм, "
                        f"угол {comp_layout.angle_deg:.1f}°"
                    )
        return result

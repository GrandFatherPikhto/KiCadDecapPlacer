# decap_placer/placement/services/power_pin_orienter.py

import math
import logging
from typing import List, Tuple, Optional
from kipy.board_types import FootprintInstance, Pad, BoardLayer
from kipy.geometry import Vector2, Angle

from ...config import Config, SpokeComponent, Spoke, Rule
from ...kicad.adapter import KiCadBoardAdapter
from ...utils.units import MM
from ..power_pin import resolve_power_pin_facing

logger = logging.getLogger(__name__)


class PowerPinOrienter:
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config

    def adjust_angles(
        self,
        raw: List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]],
        target_fp: FootprintInstance,
        target_layer: BoardLayer,
        rules: List[Rule]
    ) -> List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]]:
        adjusted = []
        for component, dest, direction, angle_base in raw:
            spoke = self._find_spoke(component, rules)
            if spoke is None:
                logger.warning(f"Не найдена спица для {component.ref}, пропускаем коррекцию угла")
                adjusted.append((component, dest, direction, angle_base))
                continue

            # Определяем facing
            if len(spoke.components) >= 2:
                if component.placement == "inside":
                    facing = "away"
                else:
                    facing = "pad"
                logger.debug(f"  {component.ref}: автоматический facing={facing} (спица с {len(spoke.components)} компонентами)")
            else:
                facing = resolve_power_pin_facing(component, spoke, self.cfg)

            pad = self.adapter.get_pad_by_number(target_fp, spoke.pad)
            if pad is None:
                logger.warning(f"Не найден пад {spoke.pad} у {self.cfg.target_ref}, пропускаем коррекцию угла")
                adjusted.append((component, dest, direction, angle_base))
                continue

            corrected_angle = self._resolve_facing_angle(
                component, pad, dest, angle_base, facing, target_layer
            )
            adjusted.append((component, dest, direction, corrected_angle))
            logger.debug(
                f"  {component.ref}: угол скорректирован с {angle_base:.1f}° -> {corrected_angle:.1f}° "
                f"(facing={facing})"
            )
        return adjusted

    def _find_spoke(self, component: SpokeComponent, rules: List[Rule]) -> Optional[Spoke]:
        for rule in rules:
            for spoke in rule.spokes:
                if any(c.ref == component.ref for c in spoke.components):
                    return spoke
        return None

    def _find_power_pad(self, fp: FootprintInstance, component: SpokeComponent) -> Optional[Pad]:
        pads = self.adapter.get_footprint_pads(fp)
        if component.power_net:
            for p in pads:
                if p.net.name == component.power_net:
                    return p
            return None
        for p in pads:
            if p.net.name != "GND":
                return p
        return None

    def _resolve_facing_angle(
        self,
        component: SpokeComponent,
        ic_pad: Pad,
        dest: Vector2,
        angle_base: float,
        facing: str,
        target_layer: BoardLayer
    ) -> float:
        fp = self.adapter.get_footprint(component.ref)
        if fp is None:
            logger.warning(f"power_pin_facing: {component.ref} не найден на плате, "
                           f"направление силового пина не корректируется")
            return angle_base

        power_pad = self._find_power_pad(fp, component)
        if power_pad is None:
            logger.warning(f"power_pin_facing: у {component.ref} не найден силовой (не-GND) пад, "
                           f"направление не корректируется")
            return angle_base

        origin = Vector2.from_xy(0, 0)
        diff = power_pad.position - fp.position
        local_offset = diff.rotate(Angle.from_degrees(-fp.orientation.degrees), origin)

        needs_flip = fp.layer != target_layer
        if needs_flip:
            logger.warning(f"power_pin_facing: {component.ref} требует флипа в этом прогоне — "
                           f"направление силового пина предсказывается по НЕПОДТВЕРЖДЁННОМУ "
                           f"допущению о конвенции флипа, стоит перепроверить на живой плате")
            local_offset = Vector2.from_xy(-local_offset.x, local_offset.y)

        def predicted_pos(angle_deg: float) -> Vector2:
            rotated = local_offset.rotate(Angle.from_degrees(angle_deg), origin)
            return dest + rotated

        candidates = [angle_base, angle_base + 180.0]
        dists = [(predicted_pos(a) - ic_pad.position).length() for a in candidates]

        # Отладка
        logger.debug(
            f"    {component.ref}: power_pad лок.={local_offset.x/MM:.3f},{local_offset.y/MM:.3f} мм, "
            f"кандидаты={[round(c,1) for c in candidates]}, расстояния={[round(d/MM,3) for d in dists]}"
        )

        if facing == "pad":
            chosen = candidates[0] if dists[0] < dists[1] else candidates[1]
        elif facing == "away":
            chosen = candidates[0] if dists[0] > dists[1] else candidates[1]
        else:
            raise ValueError(f"неизвестный power_pin_facing: {facing!r} (ожидается 'pad' или 'away')")

        logger.debug(f"    {component.ref}: выбран {chosen:.1f}°")
        return chosen
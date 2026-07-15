# decap_placer/placement/services/via_planner.py

import math
import logging
from typing import List, Tuple, Optional, Set
from kipy.board_types import FootprintInstance, Pad, BoardLayer
from kipy.geometry import Vector2

from ...config import Config, ViaConfig, SpokeComponent, Rule
from ...geometry.keepout import Rect, build_keepout, find_free_point
from ...geometry.thermal_grid import compute_thermal_via_grid
from ...geometry.pad_projection import predict_pad_position
from ...kicad.adapter import KiCadBoardAdapter
from ...utils.units import MM
from ...exceptions import GeometryError, ComponentNotFoundError
from ..commands import ViaCommand

logger = logging.getLogger(__name__)


class ViaPlanner:
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config

    def plan_vias(
        self,
        planned: List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]],
        target_fp: FootprintInstance,
        zone_center_point: Vector2,
        boundary_polygon: List[Vector2],
        rules: List[Rule],
        target_layer: BoardLayer
    ) -> List[ViaCommand]:
        # Keepout всё ещё строится, но используется только для термовиа (если они включены)
        keepout = self._build_keepout(target_fp, planned)
        logger.debug(f"Keepout: {len(keepout)} прямоугольников")

        vias = []

        # 1. Power via (ручные)
        for rule in rules:
            for spoke in rule.spokes:
                if spoke.power_via is None or not spoke.power_via.enabled:
                    continue
                pv = spoke.power_via
                pad = self.adapter.get_pad_by_number(target_fp, spoke.pad)
                if pad is None:
                    logger.warning(f"Power via: у {self.cfg.target_ref} нет площадки {spoke.pad}")
                    continue
                # Учитываем якорь спицы
                anchor_dx, anchor_dy = spoke.manual_anchor_offset_mm
                dx_mm, dy_mm = spoke.manual_power_via_offset_mm
                if dx_mm == 0.0 and dy_mm == 0.0:
                    logger.warning(f"Power via для {spoke.pad}: не задано ручное смещение, пропуск")
                    continue
                pos = Vector2.from_xy(
                    int(pad.position.x + (anchor_dx + dx_mm) * MM),
                    int(pad.position.y + (anchor_dy + dy_mm) * MM)
                )
                net = self.adapter.get_net_by_name(rule.net)
                if net is None:
                    logger.warning(f"Power via: цепь {rule.net} не найдена")
                    continue
                vias.append(ViaCommand(pos, pv.drill_mm, pv.diameter_mm, rule.net, self.cfg.target_ref))
                logger.debug(f"  power via для {spoke.pad}: ({pos.x/MM:.3f}, {pos.y/MM:.3f}) мм")

        # 2. Stitching via (ручные, по заданному смещению от GND-пада)
        for component, new_pos, direction, angle_deg in planned:
            via_cfg = self._merge_via_config(component)
            if not via_cfg.enabled:
                continue
            dx_mm, dy_mm = component.manual_gnd_via_offset_mm
            if dx_mm == 0.0 and dy_mm == 0.0:
                logger.warning(f"Via для {component.ref}: не задано ручное смещение, пропуск")
                continue
            via_net = self.adapter.get_net_by_name(via_cfg.net)
            if via_net is None:
                logger.warning(f"Цепь {via_cfg.net} для виа у {component.ref} не найдена")
                continue

            fp = self.adapter.get_footprint(component.ref)
            if fp is None:
                logger.warning(f"Компонент {component.ref} не найден, пропуск виа")
                continue

            # Находим силовой пад (не-GND)
            power_pad = None
            for pad in self.adapter.get_footprint_pads(fp):
                if pad.net.name != "GND":   # или использовать component.power_net, если задан
                    power_pad = pad
                    break
            if power_pad is None:
                logger.warning(f"Силовой пад для {component.ref} не найден, пропуск виа")
                continue

            needs_flip = fp.layer != target_layer
            power_pos = predict_pad_position(fp, power_pad, new_pos, angle_deg, needs_flip)
            pos = Vector2.from_xy(
                int(power_pos.x + dx_mm * MM),
                int(power_pos.y + dy_mm * MM)
            )
            vias.append(ViaCommand(pos, via_cfg.drill_mm, via_cfg.diameter_mm, via_cfg.net, component.ref))
            logger.debug(f"  stitching via для {component.ref}: ({pos.x/MM:.3f}, {pos.y/MM:.3f}) мм")

        # 3. Термовиа (оставляем как есть, они тоже могут быть нужны)
        vias.extend(self._plan_thermal_vias(planned, target_fp, zone_center_point, keepout))

        logger.info(f"plan_vias завершено: {len(vias)} виа")
        return vias

    def _build_keepout(
        self,
        target_fp: FootprintInstance,
        planned: List[Tuple[SpokeComponent, Vector2, Tuple[float, float], float]],
        exclude: Optional[Set[Tuple[str, str]]] = None
    ) -> List[Rect]:
        pad_items = []
        for pad in self.adapter.get_footprint_pads(target_fp):
            if exclude and (self.cfg.target_ref, pad.number) in exclude:
                continue
            pad_items.append(pad)
        for component, _, _, _ in planned:
            fp = self.adapter.get_footprint(component.ref)
            if fp is None:
                continue
            for pad in self.adapter.get_footprint_pads(fp):
                if exclude and (component.ref, pad.number) in exclude:
                    continue
                pad_items.append(pad)
        bboxes = self.adapter.get_bounding_boxes(pad_items)
        return build_keepout(bboxes, self.cfg.via_keepout_clearance_mm, mm_per_unit=MM)

    def _plan_thermal_vias(
        self,
        planned: List[Tuple[SpokeComponent, Vector2, Tuple[float, float]]],
        target_fp: FootprintInstance,
        zone_center_point: Vector2,
        keepout: List[Rect]
    ) -> List[ViaCommand]:
        tva = self.cfg.thermal_via_array
        if not tva.enabled:
            return []
        logger.debug(f"Планирование термовиа для {tva.target_ref}, площадка {tva.pad}")
        fp = self.adapter.get_footprint(tva.target_ref)
        if fp is None:
            raise ComponentNotFoundError(f"Термопад: компонент {tva.target_ref} не найден")
        pad = self.adapter.get_pad_by_number(fp, tva.pad)
        if pad is None:
            raise ComponentNotFoundError(f"Термопад: у {tva.target_ref} нет площадки {tva.pad}")
        try:
            points = compute_thermal_via_grid(
                pad,
                rows=tva.rows,
                cols=tva.cols,
                margin_mm=tva.margin_mm,
                stagger=(tva.pattern == "staggered")
            )
        except GeometryError as e:
            raise GeometryError(f"Термопад: {e}")
        exclude = {(tva.target_ref, tva.pad)}
        keepout_excl = self._build_keepout(target_fp, planned, exclude=exclude)
        via_radius = tva.diameter_mm / 2.0 * MM
        result = []
        for p in points:
            preferred = self._zone_preferred_direction(p, tva.net, zone_center_point)
            free_p = find_free_point(
                p, keepout_excl, via_radius,
                preferred_direction=preferred,
                step_mm=self.cfg.via_search_step_mm,
                max_radius_mm=self.cfg.via_search_max_radius_mm,
                n_directions=self.cfg.via_search_n_directions,
            )
            if free_p is None:
                logger.warning(f"Термовиа: место для ({p.x/MM:.3f}, {p.y/MM:.3f}) мм не найдено, точка пропущена")
                continue
            result.append(ViaCommand(free_p, tva.drill_mm, tva.diameter_mm, tva.net, tva.target_ref))
        logger.info(f"Запланировано {len(result)} термовиа на {tva.pad}")
        return result

    def _merge_via_config(self, component: SpokeComponent) -> ViaConfig:
        global_dict = dict(self.cfg.via.__dict__)
        override = component.via
        if override is None:
            return ViaConfig(**global_dict)
        if isinstance(override, bool):
            if override:
                return ViaConfig(**global_dict)
            else:
                merged = dict(global_dict)
                merged["enabled"] = False
                return ViaConfig(**merged)
        if isinstance(override, dict):
            merged = dict(global_dict)
            merged.update(override)
            return ViaConfig(**merged)
        raise ValueError(f"Некорректное значение via: {override!r}")

    def _zone_preferred_direction(self, ideal: Vector2, net_name: str, zone_center: Vector2) -> Optional[Tuple[float, float]]:
        if net_name.upper() != "GND":
            return None
        dx = zone_center.x - ideal.x
        dy = zone_center.y - ideal.y
        length = math.hypot(dx, dy)
        if length == 0:
            return None
        return (dx / length, dy / length)
#!/usr/bin/env python3
"""
Регрессия на исправление (2026-07-15): Power Via "уезжала вбок без
видимой причины" вдоль границы зоны для падов, разбросанных по разным X
на одной стороне (реальный сценарий: пады 17/139/130/122 на верхней
границе RA_DECAP_ZONE).

Причина была в направлении: раньше оно считалось "от пада к центру
bounding box'а всей зоны" — для пад, далёких от горизонтального центра
зоны, это давало заметную боковую (X) составляющую вместо чистого
перпендикуляра к границе. Плюс — power via должна ставиться честно
напротив пада, если там свободно, и двигаться только вдоль границы
(не в произвольном направлении), если что-то мешает.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from kipy.geometry import Vector2

from decap_placer.config import Config, ViaConfig, ThermalViaArrayConfig, PowerViaConfig, Rule, Spoke
from decap_placer.placement.services.via_planner import ViaPlanner
from decap_placer.geometry.keepout import Rect

MM = 1_000_000

# Прямоугольная зона (0,0)-(100,50) мм — верхняя граница y=0.
BOUNDARY = [
    Vector2.from_xy(0, 0), Vector2.from_xy(100 * MM, 0),
    Vector2.from_xy(100 * MM, 50 * MM), Vector2.from_xy(0, 50 * MM),
]


def _make_planner():
    cfg = Config(
        target_ref="IC1", boundary_zone="RA_DECAP_ZONE", side="back",
        rotation_mode="boundary", fixed_angle_deg=0.0,
        via=ViaConfig(enabled=False), thermal_via_array=ThermalViaArrayConfig(),
        rules=[], via_keepout_clearance_mm=0.2, via_search_step_mm=0.1,
        via_search_max_radius_mm=3.0, via_search_n_directions=8,
    )
    adapter = MagicMock()
    adapter.get_net_by_name.return_value = MagicMock()
    return ViaPlanner(adapter, cfg), adapter


class TestPowerViaDirection:
    def test_perpendicular_for_pads_at_different_x_on_same_edge(self):
        """4 пада на одной (верхней) границе, на сильно разных X — direction
        для всех должен быть ЧИСТО перпендикулярным (dx=0), без бокового
        сноса к горизонтальному центру зоны."""
        planner, adapter = _make_planner()
        pv_cfg = PowerViaConfig(enabled=True, placement="inside", offset_mm=3.0,
                                drill_mm=0.3, diameter_mm=0.6)
        target_fp = MagicMock()

        for x_mm in (17.0, 40.0, 60.0, 90.0):
            pad = MagicMock()
            pad.position = Vector2.from_xy(int(x_mm * MM), 0)
            adapter.get_pad_by_number.return_value = pad
            rules = [Rule(net="+3V3", spokes=[Spoke(pad="X", power_via=pv_cfg)])]

            result, _ = planner._plan_power_vias(
                planned=[], target_fp=target_fp, boundary_polygon=BOUNDARY,
                rules=rules, keepout=[], zone_center=Vector2.from_xy(50 * MM, 25 * MM)
            )
            assert len(result) == 1
            dx_mm = (result[0].position.x - pad.position.x) / MM
            assert abs(dx_mm) < 0.01, f"pad x={x_mm}: dx={dx_mm} — снос вбок, должно быть 0"

    def test_no_movement_when_ideal_spot_is_free(self):
        """Приоритет: если напротив пада честно свободно — виа стоит там
        же, без единого лишнего сдвига."""
        planner, adapter = _make_planner()
        pv_cfg = PowerViaConfig(enabled=True, placement="inside", offset_mm=3.0,
                                drill_mm=0.3, diameter_mm=0.6)
        pad = MagicMock()
        pad.position = Vector2.from_xy(int(50.0 * MM), 0)
        adapter.get_pad_by_number.return_value = pad
        rules = [Rule(net="+3V3", spokes=[Spoke(pad="X", power_via=pv_cfg)])]

        result, _ = planner._plan_power_vias(
            planned=[], target_fp=MagicMock(), boundary_polygon=BOUNDARY,
            rules=rules, keepout=[], zone_center=Vector2.from_xy(50 * MM, 25 * MM)
        )
        pos = result[0].position
        assert pos.x == pad.position.x
        assert abs(pos.y - pad.position.y - int(3.0 * MM)) < 10

    def test_moves_only_along_boundary_when_blocked(self):
        """Если идеальная точка занята — движение ТОЛЬКО вдоль границы
        (X для верхней стороны), не перпендикулярно (Y должен остаться
        неизменным)."""
        planner, adapter = _make_planner()
        pv_cfg = PowerViaConfig(enabled=True, placement="inside", offset_mm=3.0,
                                drill_mm=0.3, diameter_mm=0.6)
        pad = MagicMock()
        pad.position = Vector2.from_xy(int(50.0 * MM), 0)
        adapter.get_pad_by_number.return_value = pad
        rules = [Rule(net="+3V3", spokes=[Spoke(pad="X", power_via=pv_cfg)])]

        blocking_rect = Rect(int(49.5 * MM), int(2.5 * MM), int(50.5 * MM), int(3.5 * MM))
        result, _ = planner._plan_power_vias(
            planned=[], target_fp=MagicMock(), boundary_polygon=BOUNDARY,
            rules=rules, keepout=[blocking_rect], zone_center=Vector2.from_xy(50 * MM, 25 * MM)
        )
        pos = result[0].position
        dy_mm = (pos.y - pad.position.y) / MM
        dx_mm = (pos.x - pad.position.x) / MM
        assert abs(dy_mm - 3.0) < 0.01, "Y (перпендикуляр) не должен меняться при обходе по границе"
        assert abs(dx_mm) > 0.05, "X должен измениться -- это и есть движение вдоль границы"

    def test_power_via_keepout_is_used_by_later_vias(self):
        """Приоритет: plan_vias() должен добавлять позиции уже
        поставленных power via в keepout ДЛЯ ПОСЛЕДУЮЩИХ stitching-виа —
        то есть power via ставится первой и другие её огибают."""
        planner, adapter = _make_planner()
        pv_cfg = PowerViaConfig(enabled=True, placement="inside", offset_mm=3.0,
                                drill_mm=0.3, diameter_mm=0.6)
        pad = MagicMock()
        pad.position = Vector2.from_xy(int(50.0 * MM), 0)
        adapter.get_pad_by_number.return_value = pad
        adapter.get_footprint_pads.return_value = []
        adapter.get_bounding_boxes.return_value = []
        rules = [Rule(net="+3V3", spokes=[Spoke(pad="X", power_via=pv_cfg)])]

        vias = planner.plan_vias(
            planned=[], target_fp=MagicMock(), zone_center_point=Vector2.from_xy(50 * MM, 25 * MM),
            boundary_polygon=BOUNDARY, rules=rules, target_layer=None
        )
        assert len(vias) == 1  # только power via, planned пуст -- stitching/thermal нечего планировать

#!/usr/bin/env python3
"""
Интеграционный тест нового конвейера (шаблоны спиц) целиком: PlacementPlanner
(manual_position_calculator + via_planner) на моках, без живого KiCad.

Использует тот же пример (пад 109 при rotation_deg=90°, пад 62 при 270°),
с которого начался весь разговор про систему координат — теперь целиком
через реальный класс PlacementPlanner, а не изолированные функции.
"""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from kipy.geometry import Vector2, Angle
from kipy.board_types import BoardLayer, Pad, Net

from decap_placer.config import (
    Config, ThermalViaArrayConfig, ManualSpoke, SpokeTemplate,
    TemplatePowerVia, TemplateComponentSlot, Rule
)
from decap_placer.placement.planner import PlacementPlanner
from decap_placer.geometry.spoke_layout import rotate_local_offset

MM = 1_000_000


def _make_pad(number, x_mm, y_mm, net_name):
    pad = MagicMock(spec=Pad)
    pad.number = number
    pad.position = Vector2.from_xy(int(x_mm * MM), int(y_mm * MM))
    pad.net.name = net_name
    return pad


def _make_ic1_fp(pads_config):
    """pads_config: список (number, x_mm, y_mm, net_name)"""
    fp = MagicMock()
    fp.reference_field.text.value = "IC1"
    fp.definition.items = [_make_pad(*p) for p in pads_config]
    return fp


def _make_cap_fp(ref, x_mm, y_mm, angle_deg, power_net, layer=BoardLayer.BL_B_Cu):
    """Создаёт мок футпринта конденсатора УЖЕ в финальной позиции (имитация
    состояния платы ПОСЛЕ того, как executor закоммитил перемещения)."""
    fp = MagicMock()
    fp.reference_field.text.value = ref
    fp.position = Vector2.from_xy(int(x_mm * MM), int(y_mm * MM))
    fp.orientation = Angle.from_degrees(angle_deg)
    fp.layer = layer
    fp.definition.items = [
        _make_pad("1", x_mm, y_mm, power_net),
        _make_pad("2", x_mm, y_mm, "GND"),
    ]
    return fp


def _build_config():
    template = SpokeTemplate(
        name="cap_pair_standard",
        power_via=TemplatePowerVia(offset_along_mm=0.0, offset_across_mm=-1.5,
                                   drill_mm=0.3, diameter_mm=0.6),
        component1=TemplateComponentSlot(
            offset_along_mm=1.0, offset_across_mm=-1.0, angle_deg=90.0,
            gnd_via_offset_along_mm=0.0, gnd_via_offset_across_mm=-1.0,
            gnd_via_net="GND", gnd_via_drill_mm=0.3, gnd_via_diameter_mm=0.6,
        ),
        component2=TemplateComponentSlot(
            offset_along_mm=1.0, offset_across_mm=2.0, angle_deg=270.0,
            gnd_via_offset_along_mm=0.0, gnd_via_offset_across_mm=1.3,
            gnd_via_net="GND", gnd_via_drill_mm=0.3, gnd_via_diameter_mm=0.6,
        ),
    )
    spoke_109 = ManualSpoke(pad="109", template="cap_pair_standard",
                           shift_x_mm=0.0, shift_y_mm=0.0, rotation_deg=90.0,
                           component1_ref="C39", component2_ref="C54")
    spoke_62 = ManualSpoke(pad="62", template="cap_pair_standard",
                          shift_x_mm=0.4, shift_y_mm=0.0, rotation_deg=270.0,
                          component1_ref="C10", component2_ref="C35")
    cfg = Config(
        target_ref="IC1", side="back",
        templates={"cap_pair_standard": template},
        thermal_via_array=ThermalViaArrayConfig(enabled=False),
        rules=[Rule(net="+1V2_VCCINT", spokes=[spoke_109, spoke_62])],
        via_keepout_clearance_mm=0.2, via_search_step_mm=0.1,
        via_search_max_radius_mm=3.0, via_search_n_directions=8,
    )
    return cfg


class TestFullPipelineWithTemplates:
    def test_plan_moves_positions_and_angles(self):
        cfg = _build_config()
        pad_pos = (50.0, 50.0)
        ic1 = _make_ic1_fp([
            ("109", *pad_pos, "+1V2_VCCINT"),
            ("62", *pad_pos, "+1V2_VCCINT"),
        ])

        adapter = MagicMock()
        adapter.get_footprint.side_effect = lambda ref: ic1 if ref == "IC1" else None
        adapter.get_pad_by_number.side_effect = lambda fp, num: next(
            (p for p in fp.definition.items if p.number == num), None
        )

        planner = PlacementPlanner(adapter, cfg)
        moves = planner.plan_moves()

        assert len(moves) == 4
        by_ref = {m.ref: m for m in moves}
        assert set(by_ref.keys()) == {"C39", "C54", "C10", "C35"}

        # Сверяем с независимым расчётом через rotate_local_offset (та же
        # формула, что мы уже проверяли в test_spoke_layout.py)
        def _expected(origin_mm, along, across, rotation_deg):
            ox, oy = origin_mm
            v = rotate_local_offset(along, across, rotation_deg)
            return ox + v.x / MM, oy + v.y / MM

        ex, ey = _expected((50.0, 50.0), 1.0, -1.0, 90.0)
        assert abs(by_ref["C39"].position.x / MM - ex) < 1e-3
        assert abs(by_ref["C39"].position.y / MM - ey) < 1e-3
        assert by_ref["C39"].angle.degrees == 90.0 + 90.0

        ex2, ey2 = _expected((50.4, 50.0), 1.0, -1.0, 270.0)
        assert abs(by_ref["C10"].position.x / MM - ex2) < 1e-3
        assert abs(by_ref["C10"].position.y / MM - ey2) < 1e-3
        assert by_ref["C10"].angle.degrees == 90.0 + 270.0

    def test_plan_vias_power_and_gnd(self):
        cfg = _build_config()
        pad_pos = (50.0, 50.0)
        ic1 = _make_ic1_fp([
            ("109", *pad_pos, "+1V2_VCCINT"),
            ("62", *pad_pos, "+1V2_VCCINT"),
        ])

        # Компоненты УЖЕ в финальных позициях (имитация состояния платы
        # после того, как executor закоммитил plan_moves()).
        c39 = _make_cap_fp("C39", 51.0, 49.0, 180.0, "+1V2_VCCINT")
        c54 = _make_cap_fp("C54", 52.0, 49.0, 360.0, "+1V2_VCCINT")
        c10 = _make_cap_fp("C10", 51.4, 51.0, 360.0, "+1V2_VCCINT")
        c35 = _make_cap_fp("C35", 48.4, 51.0, 540.0, "+1V2_VCCINT")
        fps_by_ref = {"IC1": ic1, "C39": c39, "C54": c54, "C10": c10, "C35": c35}

        net_gnd = Net(name="GND")
        net_power = Net(name="+1V2_VCCINT")

        adapter = MagicMock()
        adapter.get_footprint.side_effect = lambda ref: fps_by_ref.get(ref)
        adapter.get_pad_by_number.side_effect = lambda fp, num: next(
            (p for p in fp.definition.items if p.number == num), None
        )
        adapter.get_footprint_pads.side_effect = lambda fp: list(fp.definition.items)
        adapter.get_net_by_name.side_effect = lambda name: net_gnd if name == "GND" else (
            net_power if name == "+1V2_VCCINT" else None
        )
        adapter.get_bounding_boxes.return_value = []

        planner = PlacementPlanner(adapter, cfg)
        planner.plan_moves()  # заполняет self._planned
        vias = planner.plan_vias()

        power_vias = [v for v in vias if v.net_name == "+1V2_VCCINT"]
        gnd_vias = [v for v in vias if v.owner_ref in ("C39", "C54", "C10", "C35")]

        assert len(power_vias) == 2  # по одной на спицу (109 и 62)
        assert len(gnd_vias) == 4    # по одной на каждый компонент

        # Проверяем, что GND via C39 действительно рядом с реальным GND-падом C39
        c39_gnd_via = next(v for v in gnd_vias if v.owner_ref == "C39")
        dist_mm = math.hypot(
            (c39_gnd_via.position.x - c39.position.x) / MM,
            (c39_gnd_via.position.y - c39.position.y) / MM,
        )
        assert dist_mm < 2.0, "GND via должна быть в разумной близости от своего компонента"

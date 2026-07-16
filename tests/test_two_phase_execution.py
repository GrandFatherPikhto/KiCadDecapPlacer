#!/usr/bin/env python3
"""
Регрессия на находку (2026-07-15): cmd_apply вызывал planner.plan()
(plan_moves()+plan_vias() одним куском, без коммита между ними) и затем
executor.execute(moves, vias) одним вызовом. Поскольку GND via в новой
модели берёт РЕАЛЬНЫЙ пад уже перемещённого компонента (via_planner.py),
а не предсказывает его позицию заранее, это означало, что plan_vias()
всегда видел ДОСКУ ДО каких-либо изменений — GND via тихо считалась бы
от старой, неперемещённой позиции.

Тест проверяет именно раздельный вызов execute_moves()/adapter.refresh_board()/
plan_vias()/execute_vias() — как теперь на самом деле сделано в
decap_placer.py:cmd_apply — и что GND via получает АКТУАЛЬНУЮ позицию.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from kipy.geometry import Vector2, Angle
from kipy.board_types import BoardLayer, Pad, Net

from decap_placer.config import (
    Config, ThermalViaArrayConfig, ManualSpoke, SpokeTemplate,
    TemplateComponentSlot, Rule
)
from decap_placer.placement.planner import PlacementPlanner
from decap_placer.placement.executor import BatchExecutor

MM = 1_000_000


def _make_pad(number, x_mm, y_mm, net_name):
    pad = MagicMock(spec=Pad)
    pad.number = number
    pad.position = Vector2.from_xy(int(x_mm * MM), int(y_mm * MM))
    pad.net.name = net_name
    return pad


def test_plan_vias_sees_moved_component_after_refresh():
    template = SpokeTemplate(
        name="t",
        components=[TemplateComponentSlot(
            role="LIGHT",
            offset_along_mm=1.0, offset_across_mm=0.0, angle_deg=0.0,
            gnd_via_offset_along_mm=0.0, gnd_via_offset_across_mm=0.5,
            gnd_via_net="GND",
        )],
    )
    spoke = ManualSpoke(pad="17", template="t", rotation_deg=0.0)
    cfg = Config(
        target_ref="IC1", side="back",
        templates={"t": template},
        thermal_via_array=ThermalViaArrayConfig(enabled=False),
        rules=[Rule(net="+3V3", spokes=[spoke])],
    )

    ic1 = MagicMock()
    ic1.reference_field.text.value = "IC1"
    ic1.definition.items = [_make_pad("17", 50.0, 50.0, "+3V3")]

    # C5 "на старом месте" -- где он был бы, если бы plan_vias() ошибочно
    # прочитал доску ДО коммита перемещений (баг, который мы чиним).
    c5_before = MagicMock()
    c5_before.reference_field.text.value = "C5"
    c5_before.position = Vector2.from_xy(0, 0)
    c5_before.orientation = Angle.from_degrees(0.0)
    c5_before.layer = BoardLayer.BL_F_Cu
    c5_before.definition.items = [_make_pad("2", 0.0, 0.0, "GND"), _make_pad("1", 0.0, 0.0, "+3V3")]

    # C5 "после коммита" -- реальная итоговая позиция (там, где GND via
    # ДОЛЖНА оказаться, если фикс работает).
    c5_after = MagicMock()
    c5_after.reference_field.text.value = "C5"
    c5_after.position = Vector2.from_xy(int(51.0 * MM), int(50.0 * MM))
    c5_after.orientation = Angle.from_degrees(0.0)
    c5_after.layer = BoardLayer.BL_B_Cu
    c5_after.definition.items = [_make_pad("2", 51.0, 50.0, "GND")]

    net_gnd = Net(name="GND")
    net_power = Net(name="+3V3")

    # adapter.get_footprint("C5") сначала отдаёт СТАРОЕ состояние, а после
    # "refresh" -- новое. Имитируем это через side_effect с состоянием.
    state = {"refreshed": False}

    def get_footprint(ref):
        if ref == "IC1":
            return ic1
        if ref == "C5":
            return c5_after if state["refreshed"] else c5_before
        return None

    adapter = MagicMock()
    adapter.get_footprint.side_effect = get_footprint
    adapter.get_footprints.return_value = [ic1, c5_before]
    adapter.get_pad_by_number.side_effect = lambda fp, num: next(
        (p for p in fp.definition.items if p.number == num), None
    )
    adapter.get_footprint_pads.side_effect = lambda fp: list(fp.definition.items)
    adapter.get_field_value.side_effect = lambda fp, name: "LIGHT" if fp is c5_before else None
    adapter.get_net_by_name.side_effect = lambda name: net_gnd if name == "GND" else (
        net_power if name == "+3V3" else None
    )
    adapter.get_bounding_boxes.return_value = []
    adapter.commit_with_retry.return_value = True

    def refresh_board():
        state["refreshed"] = True
    adapter.refresh_board.side_effect = refresh_board

    planner = PlacementPlanner(adapter, cfg)
    executor = BatchExecutor(adapter, cfg, batch_size=10)

    # Тот самый правильный порядок из decap_placer.py:cmd_apply
    moves = planner.plan_moves()
    executor.execute_moves(moves, check_collisions=False)
    adapter.refresh_board()
    vias = planner.plan_vias()

    gnd_vias = [v for v in vias if v.owner_ref == "C5"]
    assert len(gnd_vias) == 1
    via = gnd_vias[0]

    # GND via должна быть рядом с C5_AFTER (51.0, 50.0), а НЕ рядом с
    # C5_BEFORE (0, 0) -- если бы plan_vias() видел старое состояние.
    dist_to_after = ((via.position.x - c5_after.position.x)**2 +
                     (via.position.y - c5_after.position.y)**2) ** 0.5 / MM
    dist_to_before = ((via.position.x - c5_before.position.x)**2 +
                      (via.position.y - c5_before.position.y)**2) ** 0.5 / MM

    assert dist_to_after < 1.0, (
        f"GND via оказалась в {dist_to_after:.2f}мм от РЕАЛЬНОЙ (после коммита) позиции C5 — "
        f"должна быть рядом. Похоже, plan_vias() снова видит старое состояние платы."
    )
    assert dist_to_before > 10.0, (
        "GND via подозрительно близко к СТАРОЙ (до коммита) позиции C5 — "
        "похоже, фикс с refresh_board() между фазами не работает."
    )

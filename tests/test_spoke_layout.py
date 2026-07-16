#!/usr/bin/env python3
"""
Тесты на geometry/spoke_layout.py — развёртка шаблона спицы (локальные
along/across) в абсолютные координаты платы через (сдвиг, поворот).
DecapPlacer 4.0: произвольное число компонентов-ролей вместо component1/2.
"""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kipy.geometry import Vector2

from decap_placer.config import (
    ManualSpoke, SpokeTemplate, TemplatePowerVia, TemplateComponentSlot
)
from decap_placer.geometry.spoke_layout import apply_spoke_geometry, rotate_local_offset

MM = 1_000_000


def _real_rotate(x_mm, y_mm, angle_deg):
    """Ручной расчёт по РЕАЛЬНОЙ формуле kipy Vector2.rotate() (не переизобретаем — сверяем)."""
    theta = math.radians(angle_deg)
    rx = y_mm * math.sin(theta) + x_mm * math.cos(theta)
    ry = y_mm * math.cos(theta) - x_mm * math.sin(theta)
    return rx, ry


class TestRotateLocalOffset:
    def test_zero_rotation_is_identity(self):
        v = rotate_local_offset(1.0, -2.0, 0.0)
        assert abs(v.x / MM - 1.0) < 1e-6
        assert abs(v.y / MM - (-2.0)) < 1e-6

    def test_matches_real_kipy_formula(self):
        for angle in (30.0, 90.0, 137.0, 270.0):
            v = rotate_local_offset(1.5, -0.7, angle)
            ex, ey = _real_rotate(1.5, -0.7, angle)
            assert abs(v.x / MM - ex) < 1e-3, f"angle={angle}: x не сходится"
            assert abs(v.y / MM - ey) < 1e-3, f"angle={angle}: y не сходится"


class TestApplySpokeGeometry:
    def _template(self):
        return SpokeTemplate(
            name="t",
            power_via=TemplatePowerVia(offset_along_mm=0.0, offset_across_mm=-1.5),
            components=[
                TemplateComponentSlot(role="HEAVY", offset_along_mm=1.0, offset_across_mm=-1.0, angle_deg=90.0),
                TemplateComponentSlot(role="LIGHT", offset_along_mm=1.0, offset_across_mm=2.0, angle_deg=270.0),
            ],
        )

    def test_zero_rotation_local_equals_absolute_offset(self):
        pad_pos = Vector2.from_xy(50 * MM, 50 * MM)
        spoke = ManualSpoke(pad="1", template="t", rotation_deg=0.0)
        role_to_ref = {"HEAVY": "C5", "LIGHT": "C30"}
        layout = apply_spoke_geometry(pad_pos, spoke, self._template(), rule_net="GND", role_to_ref=role_to_ref)

        heavy = next(c for c in layout.components if c.role == "HEAVY")
        assert heavy.ref == "C5"
        assert abs((heavy.position.x - pad_pos.x) / MM - 1.0) < 1e-6
        assert abs((heavy.position.y - pad_pos.y) / MM - (-1.0)) < 1e-6
        assert heavy.angle_deg == 90.0

    def test_same_template_different_rotation_gives_consistent_math(self):
        """Один шаблон, два разных поворота (имитация двух разных бортов
        корпуса) — оба должны совпасть с независимым ручным расчётом по
        реальной формуле поворота, без единого захардкоженного знака."""
        pad_pos = Vector2.from_xy(50 * MM, 50 * MM)
        tpl = self._template()
        role_to_ref = {"HEAVY": "C5", "LIGHT": "C30"}

        for rotation_deg, shift_x, shift_y in [(90.0, 0.0, 0.0), (270.0, 0.4, 0.0)]:
            spoke = ManualSpoke(pad="1", template="t", rotation_deg=rotation_deg,
                               shift_x_mm=shift_x, shift_y_mm=shift_y)
            layout = apply_spoke_geometry(pad_pos, spoke, tpl, rule_net="GND", role_to_ref=role_to_ref)

            origin_x_mm = 50.0 + shift_x
            origin_y_mm = 50.0 + shift_y

            ex, ey = _real_rotate(0.0, -1.5, rotation_deg)  # power_via offset
            assert abs(layout.power_via_pos.x / MM - (origin_x_mm + ex)) < 1e-3
            assert abs(layout.power_via_pos.y / MM - (origin_y_mm + ey)) < 1e-3

            heavy = next(c for c in layout.components if c.role == "HEAVY")
            light = next(c for c in layout.components if c.role == "LIGHT")
            assert heavy.angle_deg == 90.0 + rotation_deg
            assert light.angle_deg == 270.0 + rotation_deg

    def test_missing_power_via_is_none(self):
        pad_pos = Vector2.from_xy(0, 0)
        tpl = SpokeTemplate(name="minimal", components=[
            TemplateComponentSlot(role="SOLO", offset_along_mm=1.0)
        ])
        spoke = ManualSpoke(pad="1", template="minimal")
        layout = apply_spoke_geometry(pad_pos, spoke, tpl, rule_net="GND", role_to_ref={"SOLO": "C1"})

        assert layout.power_via_pos is None
        assert len(layout.components) == 1
        assert layout.components[0].ref == "C1"

    def test_role_without_resolved_ref_is_skipped(self):
        """Если role_to_ref не содержит роль из шаблона (пул не выдал ref для
        неё) — соответствующий слот просто не попадает в результат, без падения."""
        pad_pos = Vector2.from_xy(0, 0)
        tpl = self._template()  # роли HEAVY и LIGHT
        layout = apply_spoke_geometry(pad_pos, spoke=ManualSpoke(pad="1", template="t"),
                                      template=tpl, rule_net="GND", role_to_ref={"HEAVY": "C5"})  # LIGHT не разрешена
        assert len(layout.components) == 1
        assert layout.components[0].role == "HEAVY"

    def test_arbitrary_number_of_roles_not_limited_to_two(self):
        """Шаблон на 3 роли (имитация кристалла: XTAL + 2 конденсатора
        нагрузки) — никакого захардкоженного ограничения на количество."""
        pad_pos = Vector2.from_xy(0, 0)
        tpl = SpokeTemplate(name="crystal", components=[
            TemplateComponentSlot(role="XTAL", offset_along_mm=0.0, offset_across_mm=0.0),
            TemplateComponentSlot(role="LOAD_CAP_1", offset_along_mm=-1.0, offset_across_mm=1.0),
            TemplateComponentSlot(role="LOAD_CAP_2", offset_along_mm=1.0, offset_across_mm=1.0),
        ])
        role_to_ref = {"XTAL": "Y1", "LOAD_CAP_1": "C15", "LOAD_CAP_2": "C16"}
        layout = apply_spoke_geometry(pad_pos, ManualSpoke(pad="1", template="crystal"),
                                      tpl, rule_net="GND", role_to_ref=role_to_ref)
        assert len(layout.components) == 3
        refs = {c.ref for c in layout.components}
        assert refs == {"Y1", "C15", "C16"}

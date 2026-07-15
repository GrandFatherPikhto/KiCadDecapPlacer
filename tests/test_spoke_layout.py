#!/usr/bin/env python3
"""
Тесты на geometry/spoke_layout.py — развёртка шаблона спицы (локальные
along/across) в абсолютные координаты платы через (сдвиг, поворот).
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
            component1=TemplateComponentSlot(offset_along_mm=1.0, offset_across_mm=-1.0, angle_deg=90.0),
            component2=TemplateComponentSlot(offset_along_mm=1.0, offset_across_mm=2.0, angle_deg=270.0),
        )

    def test_zero_rotation_local_equals_absolute_offset(self):
        pad_pos = Vector2.from_xy(50 * MM, 50 * MM)
        spoke = ManualSpoke(pad="1", template="t", rotation_deg=0.0,
                           component1_ref="C1", component2_ref="C2")
        layout = apply_spoke_geometry(pad_pos, spoke, self._template(), rule_net="GND")

        assert abs((layout.component1.position.x - pad_pos.x) / MM - 1.0) < 1e-6
        assert abs((layout.component1.position.y - pad_pos.y) / MM - (-1.0)) < 1e-6
        assert layout.component1.angle_deg == 90.0

    def test_same_template_different_rotation_gives_consistent_math(self):
        """Один шаблон, два разных поворота (имитация двух разных бортов
        корпуса) — оба должны совпасть с независимым ручным расчётом по
        реальной формуле поворота, без единого захардкоженного знака."""
        pad_pos = Vector2.from_xy(50 * MM, 50 * MM)
        tpl = self._template()

        for rotation_deg, shift_x, shift_y in [(90.0, 0.0, 0.0), (270.0, 0.4, 0.0)]:
            spoke = ManualSpoke(pad="1", template="t", rotation_deg=rotation_deg,
                               shift_x_mm=shift_x, shift_y_mm=shift_y,
                               component1_ref="C1", component2_ref="C2")
            layout = apply_spoke_geometry(pad_pos, spoke, tpl, rule_net="GND")

            origin_x_mm = 50.0 + shift_x
            origin_y_mm = 50.0 + shift_y

            ex, ey = _real_rotate(0.0, -1.5, rotation_deg)  # power_via offset
            assert abs(layout.power_via_pos.x / MM - (origin_x_mm + ex)) < 1e-3
            assert abs(layout.power_via_pos.y / MM - (origin_y_mm + ey)) < 1e-3

            # Угол компонента = локальный угол шаблона + поворот спицы
            assert layout.component1.angle_deg == 90.0 + rotation_deg
            assert layout.component2.angle_deg == 270.0 + rotation_deg

    def test_missing_slots_are_none(self):
        """Шаблон без power_via и без component2 — соответствующие поля
        в разложении остаются None, не падают с ошибкой."""
        pad_pos = Vector2.from_xy(0, 0)
        tpl = SpokeTemplate(name="minimal",
                            component1=TemplateComponentSlot(offset_along_mm=1.0))
        spoke = ManualSpoke(pad="1", template="minimal", component1_ref="C1")
        layout = apply_spoke_geometry(pad_pos, spoke, tpl, rule_net="GND")

        assert layout.power_via_pos is None
        assert layout.component2 is None
        assert layout.component1 is not None

    def test_component_ref_missing_skips_slot_even_if_template_has_it(self):
        """Если в шаблоне описан component2, но конкретная спица не
        указала component2_ref (роль не занята) — слот не заполняется."""
        pad_pos = Vector2.from_xy(0, 0)
        tpl = self._template()
        spoke = ManualSpoke(pad="1", template="t", component1_ref="C1", component2_ref=None)
        layout = apply_spoke_geometry(pad_pos, spoke, tpl, rule_net="GND")

        assert layout.component1 is not None
        assert layout.component2 is None

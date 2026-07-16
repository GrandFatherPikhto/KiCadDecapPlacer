# decap_placer/geometry/spoke_layout.py
"""
spoke_layout.py — разворачивает шаблон спицы в абсолютные координаты платы.

Порядок применения (зафиксирован в разговоре с пользователем):
  1. Сдвиг (shift_x_mm, shift_y_mm) от центра пада FPGA к нулю спицы —
     обычный плоский перенос, БЕЗ поворота.
  2. Поворот получившегося нуля (и всего содержимого шаблона) на
     rotation_deg — как единое жёсткое тело.

Оба шага — в обычных координатах KiCad. Внутреннее содержимое шаблона
(along/across) описано один раз при rotation_deg=0 (условный эталонный
борт) и одинаково для любой спицы, использующей этот шаблон — поворот
на месте конкретной спицы полностью снимает необходимость менять знаки
смещений вручную под конкретный борт корпуса.

Использует ТУ ЖЕ формулу поворота, что и весь остальной проект
(kipy.geometry.Vector2.rotate(), эмпирически подтверждённую ранее для
конвенции флипа) — не переизобретает вращение самостоятельно.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from kipy.geometry import Vector2, Angle

from ..config import ManualSpoke, SpokeTemplate
from ..utils.units import MM

_ORIGIN = Vector2.from_xy(0, 0)


def rotate_local_offset(along_mm: float, across_mm: float, rotation_deg: float) -> Vector2:
    """
    Поворачивает локальный вектор (along, across) на rotation_deg вокруг
    (0,0) — без переноса, просто повёрнутый вектор смещения в нанометрах.
    """
    local_vec = Vector2.from_xy(int(along_mm * MM), int(across_mm * MM))
    return local_vec.rotate(Angle.from_degrees(rotation_deg), _ORIGIN)


def local_to_absolute(origin: Vector2, along_mm: float, across_mm: float, rotation_deg: float) -> Vector2:
    """origin (уже после shift) + повёрнутый локальный оффсет (along, across)."""
    rotated = rotate_local_offset(along_mm, across_mm, rotation_deg)
    return Vector2.from_xy(origin.x + rotated.x, origin.y + rotated.y)


@dataclass
class ComponentLayout:
    ref: str
    role: str
    position: Vector2
    angle_deg: float
    gnd_via_offset_along_mm: float
    gnd_via_offset_across_mm: float
    gnd_via_net: str
    gnd_via_drill_mm: float
    gnd_via_diameter_mm: float


@dataclass
class SpokeLayout:
    origin: Vector2                                  # ноль спицы (после shift, до поворота)
    power_via_pos: Optional[Vector2] = None
    power_via_net: Optional[str] = None
    power_via_drill_mm: Optional[float] = None
    power_via_diameter_mm: Optional[float] = None
    components: List[ComponentLayout] = field(default_factory=list)


def apply_spoke_geometry(
    pad_position: Vector2,
    spoke: ManualSpoke,
    template: SpokeTemplate,
    rule_net: str,
    role_to_ref: Dict[str, str],
) -> SpokeLayout:
    """
    Считает абсолютные позиции всего, что есть в шаблоне для данной
    спицы. role_to_ref — уже разрешённое СНАРУЖИ (см. component_pool.py)
    сопоставление роль->ref для этой конкретной спицы; эта функция сама
    не решает, какой ref взять на какую роль — только геометрия.

    НЕ включает позиции GND via компонентов — они привязаны к РЕАЛЬНОМУ
    земляному паду компонента после того, как он реально размещён (см.
    geometry/pad_projection.py, используется в via_planner) — здесь
    только геометрия, известная заранее.
    """
    origin = Vector2.from_xy(
        pad_position.x + int(spoke.shift_x_mm * MM),
        pad_position.y + int(spoke.shift_y_mm * MM),
    )

    layout = SpokeLayout(origin=origin)

    if template.power_via is not None:
        pv = template.power_via
        layout.power_via_pos = local_to_absolute(origin, pv.offset_along_mm, pv.offset_across_mm,
                                                 spoke.rotation_deg)
        layout.power_via_net = pv.net or rule_net
        layout.power_via_drill_mm = pv.drill_mm
        layout.power_via_diameter_mm = pv.diameter_mm

    for slot in template.components:
        ref = role_to_ref.get(slot.role)
        if ref is None:
            continue
        layout.components.append(ComponentLayout(
            ref=ref,
            role=slot.role,
            position=local_to_absolute(origin, slot.offset_along_mm, slot.offset_across_mm, spoke.rotation_deg),
            angle_deg=slot.angle_deg + spoke.rotation_deg,
            gnd_via_offset_along_mm=slot.gnd_via_offset_along_mm,
            gnd_via_offset_across_mm=slot.gnd_via_offset_across_mm,
            gnd_via_net=slot.gnd_via_net,
            gnd_via_drill_mm=slot.gnd_via_drill_mm,
            gnd_via_diameter_mm=slot.gnd_via_diameter_mm,
        ))

    return layout

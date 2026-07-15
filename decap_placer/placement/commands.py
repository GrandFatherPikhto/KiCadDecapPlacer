# decap_placer/placement/commands.py
from dataclasses import dataclass
from kipy.board_types import BoardLayer
from kipy.geometry import Vector2, Angle

@dataclass
class MoveCommand:
    ref: str
    position: Vector2
    angle: Angle
    layer: BoardLayer

@dataclass
class ViaCommand:
    position: Vector2
    drill_mm: float
    diameter_mm: float
    net_name: str
    owner_ref: str

@dataclass
class PlacedComponentInfo:
    """
    Информация об одном размещённом компоненте — переносится из planner.py
    (через ManualPositionCalculator) в via_planner.py. rotation_deg — угол
    поворота СПИЦЫ, к которой принадлежит компонент (нужен, чтобы верно
    повернуть локальное смещение GND via, заданное в шаблоне).
    """
    ref: str
    dest: Vector2
    angle_deg: float
    rotation_deg: float
    gnd_via_offset_along_mm: float
    gnd_via_offset_across_mm: float
    gnd_via_net: str
    gnd_via_drill_mm: float
    gnd_via_diameter_mm: float
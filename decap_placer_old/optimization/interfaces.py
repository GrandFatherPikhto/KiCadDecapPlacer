# decap_placer/optimization/interfaces.py

from abc import ABC, abstractmethod
from typing import List, Tuple
from kipy.geometry import Vector2
from kipy.board_types import BoardLayer, FootprintInstance
from ..config import SpokeComponent, Rule


class RawPlacement:
    """Начальное приближение для оптимизатора."""
    def __init__(self, component: SpokeComponent, position: Vector2,
                 direction: Tuple[float, float], angle: float):
        self.component = component
        self.position = position
        self.direction = direction
        self.angle = angle


class FinalPlacement:
    """Результат оптимизации."""
    def __init__(self, component: SpokeComponent, position: Vector2,
                 direction: Tuple[float, float], angle: float):
        self.component = component
        self.position = position
        self.direction = direction
        self.angle = angle


class IOptimizer(ABC):
    @abstractmethod
    def optimize(
        self,
        initial_placements: List[RawPlacement],
        target_fp: FootprintInstance,
        boundary_polygon: List[Vector2],
        rules: List[Rule],
        side: str,
        target_layer: BoardLayer
    ) -> List[FinalPlacement]:
        """
        Запускает оптимизацию.
        initial_placements – начальное приближение (может быть пустым).
        """
        pass
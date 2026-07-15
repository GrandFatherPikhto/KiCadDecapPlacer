# decap_placer/optimization/heuristic_optimizer.py

from typing import List
from .interfaces import IOptimizer, FinalPlacement
from ..placement.services.manual_position_calculator import ManualPositionCalculator
from ..kicad.adapter import KiCadBoardAdapter
from ..config import Config
from kipy.board_types import BoardLayer


class HeuristicOptimizer(IOptimizer):
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config
        self.position_calc = ManualPositionCalculator(adapter, config)

    def optimize(
        self,
        initial_placements,
        target_fp,
        boundary_polygon,
        rules,
        side: str,
        target_layer: BoardLayer
    ) -> List[FinalPlacement]:
        raw = self.position_calc.compute_raw_positions(target_fp, boundary_polygon, rules, side)
        result = []
        for component, dest, direction, angle in raw:
            result.append(FinalPlacement(component, dest, direction, angle))
        return result

    def generate_initial_placements(self, *args, **kwargs):
        return []
# decap_placer/optimization/heuristic_optimizer.py

from typing import List, Optional
from .interfaces import IOptimizer, FinalPlacement
from ..placement.services.position_calculator import PositionCalculator
from ..placement.services.power_pin_orienter import PowerPinOrienter
from ..placement.services.spacing_relaxer import SpacingRelaxer
from ..kicad.adapter import KiCadBoardAdapter
from ..config import Config
from kipy.board_types import BoardLayer


class HeuristicOptimizer(IOptimizer):
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config
        self.position_calc = PositionCalculator(adapter, config)
        self.power_pin_orienter = PowerPinOrienter(adapter, config)
        self.spacing_relaxer = SpacingRelaxer(adapter, config)

    def optimize(
        self,
        initial_placements,  # не используется, оставлен для совместимости интерфейса
        target_fp,
        boundary_polygon,
        rules,
        side: str,
        target_layer: BoardLayer
    ) -> List[FinalPlacement]:
        # 1. Сырые позиции
        raw = self.position_calc.compute_raw_positions(target_fp, boundary_polygon, rules, side)
        # 2. Коррекция углов силового вывода
        raw_corrected = self.power_pin_orienter.adjust_angles(raw, target_fp, target_layer, rules)
        # 3. Релаксация (раздвижка)
        relaxed = self.spacing_relaxer.relax(raw_corrected)
        # 4. Преобразование в FinalPlacement
        result = []
        for new_pos, (component, direction, angle) in relaxed:
            result.append(FinalPlacement(component, new_pos, direction, angle))
        return result

    def _compute_raw_placements(
        self,
        target_fp,
        boundary_polygon,
        rules,
        side: str
    ) -> List:
        """Возвращает сырые позиции без коррекции углов и релаксации."""
        return self.position_calc.compute_raw_positions(target_fp, boundary_polygon, rules, side)

    def generate_initial_placements(
        self,
        target_fp,
        boundary_polygon,
        rules,
        side: str,
        target_layer: Optional[BoardLayer] = None
    ) -> List:
        """
        Возвращает позиции с коррекцией углов, но без релаксации.
        Используется как начальное приближение для NLP-оптимизатора.
        Если target_layer не передан, определяем по side.
        """
        raw = self._compute_raw_placements(target_fp, boundary_polygon, rules, side)
        if target_layer is None:
            target_layer = BoardLayer.BL_B_Cu if side == "back" else BoardLayer.BL_F_Cu
        corrected = self.power_pin_orienter.adjust_angles(raw, target_fp, target_layer, rules)
        return corrected
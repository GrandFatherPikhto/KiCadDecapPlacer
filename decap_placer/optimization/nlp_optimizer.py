# decap_placer/optimization/nlp_optimizer.py
"""
NLP-оптимизатор (заглушка).
В текущей версии делегирует работу эвристическому оптимизатору.
В будущем здесь будет реализована численная оптимизация через scipy.
"""

from typing import List
from kipy.board_types import BoardLayer
from .interfaces import IOptimizer, FinalPlacement, RawPlacement
from .heuristic_optimizer import HeuristicOptimizer
from ..config import Config, Rule
from ..kicad.adapter import KiCadBoardAdapter


class NLPOptimizer(IOptimizer):
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config
        # Временно используем эвристику как fallback
        self._heuristic = HeuristicOptimizer(adapter, config)

    def optimize(
        self,
        initial_placements: List[RawPlacement],
        target_fp,
        boundary_polygon,
        rules: List[Rule],
        side: str,
        target_layer: BoardLayer
    ) -> List[FinalPlacement]:
        """
        Заглушка: вызывает эвристический оптимизатор.
        В будущем заменить на настоящий NLP.
        """
        # Логируем предупреждение, что используется заглушка
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "NLPOptimizer – временная заглушка, используется эвристика. "
            "Для полноценной NLP-оптимизации реализуйте метод _objective и ограничения."
        )
        return self._heuristic.optimize(
            initial_placements,
            target_fp,
            boundary_polygon,
            rules,
            side,
            target_layer
        )
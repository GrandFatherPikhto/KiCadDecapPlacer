# decap_placer/placement/planner.py

import logging
from typing import List, Tuple, Optional
from kipy.board_types import BoardLayer, Pad, FootprintInstance
from kipy.geometry import Vector2, Angle

from ..config import Config
from ..kicad.adapter import KiCadBoardAdapter
from ..utils.units import MM
from .services.via_planner import ViaPlanner
from .services.manual_position_calculator import ManualPositionCalculator
from ..exceptions import ComponentNotFoundError
from .commands import MoveCommand, ViaCommand

logger = logging.getLogger(__name__)

class PlacementPlanner:
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config
        self.position_calc = ManualPositionCalculator(adapter, config)
        self._target_fp = adapter.get_footprint(config.target_ref)
        if self._target_fp is None:
            raise ComponentNotFoundError(f"Целевой компонент {config.target_ref} не найден")
        self._target_layer = BoardLayer.BL_B_Cu if config.side == "back" else BoardLayer.BL_F_Cu
        self._planned = None
        self.via_planner = ViaPlanner(adapter, config)
        logger.info(f"Планировщик инициализирован: target={config.target_ref}, side={config.side}")

    def plan_moves(self) -> List[MoveCommand]:
        if not self.cfg.place_components:
            self._planned = []
            logger.info("place_components=False – перемещения конденсаторов не планируются")
            return []
        placed = self.position_calc.compute_raw_positions(
            self._target_fp,
            self.cfg.rules,
            self.cfg.side
        )
        moves = []
        self._planned = placed
        for info in placed:
            moves.append(MoveCommand(
                ref=info.ref,
                position=info.dest,
                angle=Angle.from_degrees(info.angle_deg),
                layer=self._target_layer
            ))
        logger.info(f"plan_moves завершено: {len(moves)} перемещений")
        return moves

    def plan_vias(self) -> List[ViaCommand]:
        return self.via_planner.plan_vias(
            planned=self._planned,
            target_fp=self._target_fp,
            rules=self.cfg.rules,
            target_layer=self._target_layer
        )

    def plan(self) -> Tuple[List[MoveCommand], List[ViaCommand]]:
        moves = self.plan_moves()
        vias = self.plan_vias()
        return moves, vias
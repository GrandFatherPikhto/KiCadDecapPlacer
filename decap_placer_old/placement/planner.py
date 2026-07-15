# decap_placer/placement/planner.py

import logging
from typing import List, Tuple, Optional
from kipy.board_types import BoardLayer, Pad, FootprintInstance
from kipy.geometry import Vector2, Angle

from ..config import Config
from ..kicad.adapter import KiCadBoardAdapter
from ..utils.units import MM
from .services.via_planner import ViaPlanner
from ..optimization.factory import OptimizerFactory
from ..exceptions import ComponentNotFoundError
from .commands import MoveCommand, ViaCommand

logger = logging.getLogger(__name__)

class PlacementPlanner:
    def __init__(self, adapter: KiCadBoardAdapter, config: Config):
        self.adapter = adapter
        self.cfg = config
        self.optimizer = OptimizerFactory.create(config.optimizer_type, adapter, config)
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
        initial = []
        final = self.optimizer.optimize(
            initial,
            self._target_fp,
            [],  # boundary_polygon больше не нужен
            self.cfg.rules,
            self.cfg.side,
            self._target_layer
        )
        moves = []
        self._planned = []
        for fp in final:
            angle_deg = fp.angle
            angle_obj = Angle.from_degrees(angle_deg)
            moves.append(MoveCommand(
                ref=fp.component.ref,
                position=fp.position,
                angle=angle_obj,
                layer=self._target_layer
            ))
            self._planned.append((fp.component, fp.position, fp.direction, angle_deg))
        logger.info(f"plan_moves завершено: {len(moves)} перемещений")
        return moves

    def plan_vias(self) -> List[ViaCommand]:
        return self.via_planner.plan_vias(
            planned=self._planned,
            target_fp=self._target_fp,
            zone_center_point=Vector2.from_xy(0, 0),  # не используется
            boundary_polygon=[],                      # не используется
            rules=self.cfg.rules,
            target_layer=self._target_layer
        )

    def plan(self) -> Tuple[List[MoveCommand], List[ViaCommand]]:
        moves = self.plan_moves()
        vias = self.plan_vias()
        return moves, vias
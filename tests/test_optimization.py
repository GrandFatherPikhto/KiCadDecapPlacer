#!/usr/bin/env python3
"""
Тесты для модуля optimization.
Проверяют фабрику и эвристический оптимизатор с моками.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, Mock

from kipy.board_types import BoardLayer
from kipy.geometry import Vector2

from decap_placer.config import Config, ViaConfig, ThermalViaArrayConfig, Rule, Spoke, SpokeComponent
from decap_placer.optimization import OptimizerFactory, HeuristicOptimizer, NLPOptimizer
from decap_placer.optimization.interfaces import FinalPlacement, RawPlacement
from decap_placer.utils.units import MM


@pytest.fixture
def mock_adapter():
    return MagicMock()


@pytest.fixture
def config():
    return Config(
        target_ref="IC1",
        boundary_zone="RA_DECAP_ZONE",
        side="back",
        via=ViaConfig(),
        thermal_via_array=ThermalViaArrayConfig(),
        rules=[],
        min_row_spacing_mm=2.0,
        power_pin_facing="away",
        max_spoke_rigid_shift_mm=1.5,
        via_keepout_clearance_mm=0.2,
        via_search_step_mm=0.1,
        via_search_max_radius_mm=3.0,
        via_search_n_directions=8,
        optimizer_type="heuristic",
        relax_max_iterations=10,
        relax_group_tolerance_nm=1000,
        rotation_mode="boundary",   # deprecated, но пока есть
        fixed_angle_deg=0.0,
    )


def test_factory_heuristic(mock_adapter, config):
    """Фабрика создаёт HeuristicOptimizer при 'heuristic'."""
    opt = OptimizerFactory.create("heuristic", mock_adapter, config)
    assert isinstance(opt, HeuristicOptimizer)


def test_factory_nlp(mock_adapter, config):
    """Фабрика создаёт NLPOptimizer при 'nlp'."""
    opt = OptimizerFactory.create("nlp", mock_adapter, config)
    assert isinstance(opt, NLPOptimizer)


def test_factory_unknown(mock_adapter, config):
    """Неизвестный тип вызывает ValueError."""
    with pytest.raises(ValueError, match="Unknown optimizer type"):
        OptimizerFactory.create("unknown", mock_adapter, config)


def test_heuristic_optimizer(mock_adapter, config):
    """
    Проверяем, что HeuristicOptimizer.optimize вызывает сервисы и возвращает FinalPlacement.
    Мокаем все внутренние сервисы.
    """
    # Подменяем сервисы на моки
    opt = HeuristicOptimizer(mock_adapter, config)
    opt.position_calc = MagicMock()
    opt.power_pin_orienter = MagicMock()
    opt.spacing_relaxer = MagicMock()

    # Создаём фейковые данные
    comp = SpokeComponent(ref="C1", placement="outside", offset_mm=1.0)
    raw_result = [(comp, Vector2.from_xy(1_000_000, 2_000_000), (0.0, 1.0), 45.0)]
    opt.position_calc.compute_raw_positions.return_value = raw_result
    opt.power_pin_orienter.adjust_angles.return_value = raw_result  # без изменений
    relaxed_result = [(Vector2.from_xy(1_000_000, 2_000_000), (comp, (0.0, 1.0), 45.0))]
    opt.spacing_relaxer.relax.return_value = relaxed_result

    target_fp = MagicMock()
    boundary_polygon = [Vector2.from_xy(0, 0), Vector2.from_xy(10_000_000, 0),
                        Vector2.from_xy(10_000_000, 10_000_000), Vector2.from_xy(0, 10_000_000)]
    rules = [Rule(net="GND", spokes=[Spoke(pad="1", components=[comp])])]

    result = opt.optimize(
        initial_placements=[],
        target_fp=target_fp,
        boundary_polygon=boundary_polygon,
        rules=rules,
        side="back",
        target_layer=BoardLayer.BL_B_Cu
    )

    # Проверяем, что вернулся список FinalPlacement
    assert len(result) == 1
    assert isinstance(result[0], FinalPlacement)
    assert result[0].component.ref == "C1"
    assert result[0].position.x == 1_000_000
#!/usr/bin/env python3
"""
Тест для проверки базовой работоспособности модуля geometry.
Запускается без KiCad, только логика.
"""

import sys
from pathlib import Path

# Добавляем корень проекта (папку, содержащую decap_placer) в sys.path
# Корень – это parent от tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

from kipy.geometry import Vector2
from decap_placer.geometry import (
    closest_point_on_polygon,
    compute_position,
    build_keepout,
    find_free_point,
    Rect,
    relax_1d,
    relax_positions,
    point_is_clear,
)


def test_closest_point_on_polygon():
    """Проверяем поиск ближайшей точки и нормаль на квадрате."""
    square = [
        Vector2.from_xy(0, 0),
        Vector2.from_xy(10_000_000, 0),  # 10 мм
        Vector2.from_xy(10_000_000, 10_000_000),
        Vector2.from_xy(0, 10_000_000),
    ]
    point = Vector2.from_xy(5_000_000, -1_000_000)  # снизу от квадрата
    closest, normal = closest_point_on_polygon(point, square)
    print(f"[closest_point] closest={closest.x/1e6:.3f}, {closest.y/1e6:.3f} мм, normal={normal}")
    # Ожидаем: ближайшая точка на нижней стороне (5,0), нормаль (0,-1)
    assert abs(closest.x - 5_000_000) < 1e-6
    assert abs(closest.y - 0) < 1e-6
    assert abs(normal[0] - 0) < 1e-6
    assert abs(normal[1] - (-1)) < 1e-6
    print("✅ closest_point_on_polygon OK")


def test_compute_position():
    """Проверяем расчёт позиции по boundary стратегии."""
    square = [
        Vector2.from_xy(0, 0),
        Vector2.from_xy(10_000_000, 0),
        Vector2.from_xy(10_000_000, 10_000_000),
        Vector2.from_xy(0, 10_000_000),
    ]
    pad_pos = Vector2.from_xy(5_000_000, -1_000_000)  # снизу
    center = Vector2.from_xy(5_000_000, 5_000_000)  # центр, не используется

    # outside
    pos, normal = compute_position(center, pad_pos, square, "outside", 0.5)
    print(f"[outside] pos={pos.x/1e6:.3f}, {pos.y/1e6:.3f} мм, normal={normal}")
    # Ожидаем: сдвиг вниз на 0.5 мм от границы (y = -0.5 мм)
    assert abs(pos.x - 5_000_000) < 1e-6
    assert abs(pos.y - (-500_000)) < 1e-6
    assert abs(normal[1] - (-1)) < 1e-6

    # inside
    pos, normal = compute_position(center, pad_pos, square, "inside", 0.3)
    print(f"[inside] pos={pos.x/1e6:.3f}, {pos.y/1e6:.3f} мм, normal={normal}")
    # Ожидаем: сдвиг внутрь на 0.3 мм (y = 0.3 мм)
    assert abs(pos.x - 5_000_000) < 1e-6
    assert abs(pos.y - 300_000) < 1e-6
    assert abs(normal[1] - (-1)) < 1e-6
    print("✅ compute_position OK")


def test_keepout():
    """Проверяем keepout и поиск свободной точки."""
    keepout_rects = [
        Rect(0, 0, 2_000_000, 2_000_000),  # квадрат 2x2 мм
    ]
    ideal = Vector2.from_xy(1_000_000, 1_000_000)  # внутри keepout
    via_radius = 100_000  # 0.1 мм
    free = find_free_point(
        ideal,
        keepout_rects,
        via_radius,
        step_mm=0.1,
        max_radius_mm=2.0,
        preferred_direction=(1, 0)  # пробуем вправо
    )
    print(f"[find_free] free={free.x/1e6:.3f}, {free.y/1e6:.3f} мм")
    assert free is not None
    assert point_is_clear(free, via_radius, keepout_rects)
    print("✅ keepout/find_free_point OK")


def test_relax_1d():
    """Проверяем раздвижку 1D."""
    items = [(0.0, "A"), (1.0, "B"), (1.2, "C")]
    min_gap = 0.5
    result = relax_1d(items, min_gap)
    print(f"[relax_1d] result={result}")
    for i in range(len(result)-1):
        assert result[i+1][0] - result[i][0] >= min_gap - 1e-9
    print("✅ relax_1d OK")


if __name__ == "__main__":
    print("Запуск тестов geometry...")
    test_closest_point_on_polygon()
    test_compute_position()
    test_keepout()
    test_relax_1d()
    print("Все тесты пройдены!")
#!/usr/bin/env python3
"""
Тесты для модуля rules (парсинг и генерация).
Требуют наличия тестовых файлов .net и .kicad_pcb.
Если файлы не найдены – тест пропускается.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from decap_placer.rules import parse_net_file, parse_pcb_file, RulesGenerator


# Пути к тестовым файлам (измените под свои)
TEST_NET = Path(__file__).parent.parent / "test_data" / "test.net"
TEST_PCB = Path(__file__).parent.parent / "test_data" / "test.kicad_pcb"


def test_parse_net_file():
    if not TEST_NET.exists():
        pytest.skip(f"Файл {TEST_NET} не найден")
    nets = parse_net_file(str(TEST_NET))
    assert isinstance(nets, dict)
    assert len(nets) > 0
    print(f"Найдено цепей: {len(nets)}")


def test_parse_pcb_file():
    if not TEST_PCB.exists():
        pytest.skip(f"Файл {TEST_PCB} не найден")
    fp_info, pads_info = parse_pcb_file(str(TEST_PCB))
    assert isinstance(fp_info, dict)
    assert isinstance(pads_info, dict)
    print(f"Найдено футпринтов: {len(fp_info)}")


def test_rules_generator():
    if not TEST_NET.exists() or not TEST_PCB.exists():
        pytest.skip("Тестовые файлы не найдены")
    groups = {
        "+3V3": {"100nF": ["C1", "C2"], "4.7uF": ["C10"]},
        "+1V2": {"100nF": ["C3"], "4.7uF": ["C11"]},
    }
    gen = RulesGenerator(
        net_path=str(TEST_NET),
        pcb_path=str(TEST_PCB),
        target_ref="IC1",
        groups=groups,
    )
    rules = gen.generate()
    assert len(rules) > 0
    yaml_str = gen.generate_yaml()
    assert "rules:" in yaml_str
    print(f"Сгенерировано правил: {len(rules)}")
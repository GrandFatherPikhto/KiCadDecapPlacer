# decap_placer/rules/__init__.py
"""
Генерация правил из netlist и PCB-файлов.
Предоставляет класс RulesGenerator и парсеры файлов.
"""

from .generator import RulesGenerator
from .parser import parse_net_file, parse_pcb_file

__all__ = [
    "RulesGenerator",
    "parse_net_file",
    "parse_pcb_file",
]
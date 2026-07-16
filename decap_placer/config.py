# decap_placer/config.py

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import yaml

logger = logging.getLogger(__name__)


@dataclass
class ThermalViaArrayConfig:
    """Конфигурация массива тепловых via под термопадом IC."""
    enabled: bool = False
    target_ref: str = ""
    pad: str = ""
    net: str = "GND"
    rows: int = 4
    cols: int = 4
    margin_mm: float = 0.5
    pattern: str = "grid"
    drill_mm: float = 0.3
    diameter_mm: float = 0.5


@dataclass
class TemplatePowerVia:
    """
    Power via внутри шаблона спицы — координаты локальные (along/across),
    считаются от нуля шаблона (там же, где сам шаблон крепится к паду FPGA).
    along/across — оси уже ПОВЁРНУТОГО шаблона (см. ManualSpoke.rotation_deg),
    а не координаты платы напрямую.
    """
    offset_along_mm: float = 0.0
    offset_across_mm: float = 0.0
    net: Optional[str] = None  # None = взять из net правила (rule.net)
    drill_mm: float = 0.3
    diameter_mm: float = 0.6


@dataclass
class TemplateComponentSlot:
    """
    Один компонент-слот в шаблоне — роль ('HEAVY'/'LIGHT'/'XTAL'/
    'LOAD_CAP_1' и т.д.), а не конкретный ref. Конкретный ref подбирается
    на этапе расстановки из пула компонентов платы: все футпринты, чей
    РЕАЛЬНЫЙ пад сидит на цепи правила (rule.net) и у кого пользовательское
    поле Role (см. validation/component_pool.py) совпадает с этой ролью.
    Координаты локальные (along/across). GND via этого слота — координаты
    от СОБСТВЕННОГО земляного пада этого компонента (не от нуля шаблона),
    но в той же повёрнутой оси.
    """
    role: str
    offset_along_mm: float = 0.0
    offset_across_mm: float = 0.0
    angle_deg: float = 0.0
    gnd_via_offset_along_mm: float = 0.0
    gnd_via_offset_across_mm: float = 0.0
    gnd_via_net: str = "GND"
    gnd_via_drill_mm: float = 0.3
    gnd_via_diameter_mm: float = 0.6


@dataclass
class SpokeTemplate:
    """
    Шаблон спицы — вся геометрия локальная и поворотоинвариантная:
    описывается один раз при rotation_deg=0 (условный эталонный борт),
    дальше конкретная спица поворачивает его целиком на свой угол.
    Любой из элементов может отсутствовать/быть пустым — например, спица
    без power via, или шаблон всего с одним компонентом.
    """
    name: str
    power_via: Optional[TemplatePowerVia] = None
    components: List[TemplateComponentSlot] = field(default_factory=list)


@dataclass
class ManualSpoke:
    """
    Конкретная спица на конкретном паде FPGA. shift_x_mm/shift_y_mm и
    rotation_deg — ВСЕГДА в обычных координатах KiCad (не локальных),
    подбираются глазами под конкретный борт. Порядок применения: сначала
    сдвиг (shift_x, shift_y) от центра пада к нулю спицы, затем поворот
    получившегося нуля (и всего содержимого шаблона) на rotation_deg.

    ВАЖНО: никаких ref компонентов здесь больше нет — конкретные
    компоненты подбираются автоматически из пула (см.
    placement/services/component_pool.py) по совпадению реальной цепи
    (rule.net) и пользовательского поля Role на компоненте, в порядке
    следования спиц в этом списке.
    """
    pad: str
    template: str
    shift_x_mm: float = 0.0
    shift_y_mm: float = 0.0
    rotation_deg: float = 0.0
    enabled: bool = True


@dataclass
class Rule:
    net: str
    spokes: List[ManualSpoke]


@dataclass
class Config:
    """Главный конфигурационный объект."""
    target_ref: str
    side: str = "back"
    templates: Dict[str, SpokeTemplate] = field(default_factory=dict)
    thermal_via_array: ThermalViaArrayConfig = field(default_factory=ThermalViaArrayConfig)
    rules: List[Rule] = field(default_factory=list)
    place_components: bool = True
    skip_existing_components: bool = False
    # Параметры поиска свободного места -- сейчас используются только для
    # термовиа (у power/GND via ручное позиционирование, поиска нет).
    via_keepout_clearance_mm: float = 0.2
    via_search_step_mm: float = 0.1
    via_search_max_radius_mm: float = 3.0
    via_search_n_directions: int = 8


def _load_template_power_via(data: Optional[Dict[str, Any]]) -> Optional[TemplatePowerVia]:
    if not data:
        return None
    return TemplatePowerVia(
        offset_along_mm=data.get('offset_along_mm', 0.0),
        offset_across_mm=data.get('offset_across_mm', 0.0),
        net=data.get('net'),
        drill_mm=data.get('drill_mm', 0.3),
        diameter_mm=data.get('diameter_mm', 0.6),
    )


def _load_template_component_slot(data: Dict[str, Any]) -> TemplateComponentSlot:
    return TemplateComponentSlot(
        role=data['role'],
        offset_along_mm=data.get('offset_along_mm', 0.0),
        offset_across_mm=data.get('offset_across_mm', 0.0),
        angle_deg=data.get('angle_deg', 0.0),
        gnd_via_offset_along_mm=data.get('gnd_via_offset_along_mm', 0.0),
        gnd_via_offset_across_mm=data.get('gnd_via_offset_across_mm', 0.0),
        gnd_via_net=data.get('gnd_via_net', 'GND'),
        gnd_via_drill_mm=data.get('gnd_via_drill_mm', 0.3),
        gnd_via_diameter_mm=data.get('gnd_via_diameter_mm', 0.6),
    )


def _load_spoke_template(name: str, data: Dict[str, Any]) -> SpokeTemplate:
    return SpokeTemplate(
        name=name,
        power_via=_load_template_power_via(data.get('power_via')),
        components=[_load_template_component_slot(c) for c in data.get('components', [])],
    )


def _load_manual_spoke(data: Dict[str, Any]) -> ManualSpoke:
    return ManualSpoke(
        pad=data['pad'],
        template=data['template'],
        shift_x_mm=data.get('shift_x_mm', 0.0),
        shift_y_mm=data.get('shift_y_mm', 0.0),
        rotation_deg=data.get('rotation_deg', 0.0),
        enabled=data.get('enabled', True),
    )


def load_config(path: str) -> Config:
    logger.info(f"Загрузка конфигурации из {path}")
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    tva_data = data.get('thermal_via_array', {})
    thermal_via = ThermalViaArrayConfig(
        enabled=tva_data.get('enabled', False),
        target_ref=tva_data.get('target_ref', data.get('target_ref', '')),
        pad=tva_data.get('pad', ''),
        net=tva_data.get('net', 'GND'),
        rows=tva_data.get('rows', 4),
        cols=tva_data.get('cols', 4),
        margin_mm=tva_data.get('margin_mm', 0.5),
        pattern=tva_data.get('pattern', 'grid'),
        drill_mm=tva_data.get('drill_mm', 0.3),
        diameter_mm=tva_data.get('diameter_mm', 0.5),
    )

    templates_data = data.get('templates', {})
    templates = {name: _load_spoke_template(name, tdata) for name, tdata in templates_data.items()}

    rules = []
    for rule_data in data.get('rules', []):
        spokes = [_load_manual_spoke(spoke_data) for spoke_data in rule_data.get('spokes', [])]
        rules.append(Rule(net=rule_data['net'], spokes=spokes))

    cfg = Config(
        target_ref=data['target_ref'],
        side=data.get('side', 'back'),
        templates=templates,
        thermal_via_array=thermal_via,
        rules=rules,
        place_components=data.get('place_components', True),
        skip_existing_components=data.get('skip_existing_components', False),
        via_keepout_clearance_mm=data.get('via_keepout_clearance_mm', 0.2),
        via_search_step_mm=data.get('via_search_step_mm', 0.1),
        via_search_max_radius_mm=data.get('via_search_max_radius_mm', 3.0),
        via_search_n_directions=data.get('via_search_n_directions', 8),
    )
    total_spokes = sum(len(r.spokes) for r in cfg.rules)
    logger.debug(f"Конфигурация загружена: target={cfg.target_ref}, side={cfg.side}, "
                 f"шаблонов={len(cfg.templates)}, правил={len(cfg.rules)}, спиц={total_spokes}")
    return cfg

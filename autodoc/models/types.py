"""
Общие типы-псевдонимы, пересекающие границы слоёв.


Размещение здесь гарантирует однонаправленный граф импортов:
    fetchers/ → models/types.py
    enrichment/ → models/types.py
    steps/ → models/types.py
"""

# Маппинг опций Conan: (comp_name, version, channel) → {option_id: options_dict}
OptionsMap = dict[tuple[str, str, str], dict[str, str]]

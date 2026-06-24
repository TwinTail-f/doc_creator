"""
Общие типы-псевдонимы, пересекающие границы слоёв.


Размещение здесь гарантирует однонаправленный граф импортов:
    fetchers/ → models/types.py
    enrichment/ → models/types.py
    steps/ → models/types.py
"""

from typing import NamedTuple


class ReleaseKey(NamedTuple):
    """
    Идентификатор релиза компонента: (имя компонента, версия, channel).

    Один релиз компонента может собираться в нескольких профилях и с
    несколькими наборами опций (несколько ``ConanTask``), но всегда
    описывается ровно одной такой комбинацией полей. Используется как
    ключ группировки/поиска в ``ConanResultAggregator``, ``DataEnricher``
    и в ``OptionsMap`` ниже — вместо анонимного ``tuple[str, str, str]``,
    чтобы смысл каждого поля был виден в коде без обращения к комментарию.
    """

    comp_name: str
    version: str
    channel: str


# Маппинг опций Conan: ReleaseKey → {option_id: options_dict}
OptionsMap = dict[ReleaseKey, dict[str, str]]

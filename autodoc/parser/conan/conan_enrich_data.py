"""
Промежуточные типы данных пакета ``conan/``.

``ConanEnrichData`` — связующая структура между ``Conan2ResultParser``
и ``ConanResultAggregator``. Вынесена в отдельный файл, чтобы агрегатор
не зависел от парсера: оба теперь импортируют из ``conan/types.py``,
а не один из другого.
"""

from dataclasses import dataclass
from typing import Any

from autodoc.models.options import DefaultOptionsSet


@dataclass
class ConanEnrichData:
    """
    Структурированные данные для обогащения моделей ``Release`` и ``ProfileBuild``.

    Заполняется из JSON-ответа ``conan graph info`` для одной задачи.
    Внутренний датакласс — не попадает в доменные модели напрямую.

    Поле ``default_options`` хранит уже типизированные объекты ``DefaultOptionsSet``
    (из поля ``default_options`` в JSON) — конверсия из сырых словарей выполняется
    в момент парсинга, а не при обогащении.

    Поле ``conan_options`` содержит значения из поля ``options`` в JSON
    — итоговые resolved-опции, из которых строится ``TotalOptionsSet``.
    """

    base_ref: str
    rrev: str
    full_version: str
    default_options: list[DefaultOptionsSet]
    patches: list[str]
    dependencies: list[str]
    conan_settings: dict[str, Any]
    package_id: str
    build_url: str
    build_date: str
    conan_options: dict[str, Any]  # из поля "options" вывода conan graph info
    option_id: str  # скопировано из ConanTask.option_id

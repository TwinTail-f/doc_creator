"""Реестр стратегий публикации документации."""

from typing import Any

from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.kit_fixed_strategy import KitFixedPageStrategy
from autodoc.publisher.strategies.kit_latest_strategy import KitLatestPageStrategy
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.profile_centric_strategy import ProfileCentricPageStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy

STRATEGIES: dict[str, type[BasePublishStrategy]] = {
    "passports": PassportsStrategy,
    "release": ReleasePageStrategy,
    "profile_centric": ProfileCentricPageStrategy,
    "kit_fixed": KitFixedPageStrategy,
    "kit_latest": KitLatestPageStrategy,
}
"""Явное сопоставление ключа стратегии её классу.

Чтобы добавить новую стратегию, достаточно добавить одну строку в этот словарь.
"""


def create_strategy(strategy_type: str, **kwargs: Any) -> BasePublishStrategy:
    """
    Создаёт экземпляр стратегии публикации по её типу.

    Args:
        strategy_type: Ключ стратегии (``'passports'``, ``'release'``,
            ``'profile_centric'``, ``'kit_fixed'`` или ``'kit_latest'``).
        **kwargs: Аргументы конструктора выбранной стратегии.

    Returns:
        Готовый экземпляр стратегии.

    Raises:
        ValueError: Если ``strategy_type`` не найден в реестре.
    """
    strategy_cls = STRATEGIES.get(strategy_type)
    if strategy_cls is None:
        raise ValueError(
            f"Неизвестная стратегия {strategy_type!r}. Доступные: {available_strategies()}"
        )
    return strategy_cls(**kwargs)


def single_page_strategy_types() -> list[str]:
    """
    Возвращает отсортированный список ключей одностраничных стратегий.

    Одностраничные стратегии — те, у кого ``IS_SINGLE_PAGE`` равен ``True``
    (``release``, ``profile_centric``, ``kit_fixed``, ``kit_latest``).
    ``passports`` сюда не входит: это стратегия с иерархией страниц.

    Returns:
        Отсортированный список ключей стратегий.
    """
    return sorted(key for key, cls in STRATEGIES.items() if cls.IS_SINGLE_PAGE)


def is_single_page_strategy(strategy_type: str) -> bool:
    """
    Проверяет, что ``strategy_type`` зарегистрирован и является одностраничной стратегией.

    Args:
        strategy_type: Ключ стратегии для проверки.

    Returns:
        ``True``, если ``strategy_type`` есть в реестре и его
        ``IS_SINGLE_PAGE`` равен ``True``.
    """
    strategy_cls = STRATEGIES.get(strategy_type)
    return strategy_cls is not None and strategy_cls.IS_SINGLE_PAGE


def available_strategies() -> list[str]:
    """
    Возвращает отсортированный список зарегистрированных типов стратегий.

    Returns:
        Список ключей стратегий в алфавитном порядке.
    """
    return sorted(STRATEGIES)

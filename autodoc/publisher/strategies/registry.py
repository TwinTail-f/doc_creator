"""Реестр стратегий публикации документации."""

from typing import Any

from autodoc.publisher.strategies.base_publish_strategy import BasePublishStrategy
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy

STRATEGIES: dict[str, type[BasePublishStrategy]] = {
    "passports": PassportsStrategy,
    "release": ReleasePageStrategy,
    "profile_centric": ProfileCentricStrategy,
}
"""Явное сопоставление ключа стратегии её классу.

Чтобы добавить новую стратегию, достаточно добавить одну строку в этот словарь.
"""


def create_strategy(strategy_type: str, **kwargs: Any) -> BasePublishStrategy:
    """
    Создаёт экземпляр стратегии публикации по её типу.

    Args:
        strategy_type: Ключ стратегии (``'passports'``, ``'release'`` или ``'profile_centric'``).
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


def available_strategies() -> list[str]:
    """
    Возвращает отсортированный список зарегистрированных типов стратегий.

    Returns:
        Список ключей стратегий в алфавитном порядке.
    """
    return sorted(STRATEGIES)

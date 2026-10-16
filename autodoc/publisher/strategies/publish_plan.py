"""
Декларативный план публикации: порядок типов и зависимости между ними.

``PUBLISH_PLAN`` задаёт порядок публикации в ``publish all``.
"""

from typing import NamedTuple


class PublishNode(NamedTuple):
    """
    Узел плана публикации одного типа страницы.

    Attributes:
        key: Ключ стратегии из ``registry.STRATEGIES``.
        parent_from: Ключ типа-родителя или ``None``, если родитель задан в конфигурации.
    """

    key: str
    parent_from: str | None = None


PUBLISH_PLAN: tuple[PublishNode, ...] = (
    PublishNode("passports"),
    PublishNode("release"),
    PublishNode("profile_centric", parent_from="release"),
    PublishNode("kit_pinned"),
    PublishNode("kit_latest"),
)


def plan_keys() -> list[str]:
    """Возвращает ключи всех типов в порядке публикации."""
    return [node.key for node in PUBLISH_PLAN]


def keys_with_own_parent() -> list[str]:
    """Возвращает ключи типов, чей родитель задаётся секцией конфига, а не другим типом."""
    return [node.key for node in PUBLISH_PLAN if node.parent_from is None]


def parent_key_of(key: str) -> str | None:
    """
    Возвращает ключ типа-родителя.

    Args:
        key: Ключ типа из ``PUBLISH_PLAN``.

    Returns:
        Ключ типа-родителя или ``None``, если у типа собственный родитель.

    Raises:
        ValueError: Если ``key`` отсутствует в ``PUBLISH_PLAN``.
    """
    for node in PUBLISH_PLAN:
        if node.key == key:
            return node.parent_from
    raise ValueError(f"Тип {key!r} отсутствует в PUBLISH_PLAN")

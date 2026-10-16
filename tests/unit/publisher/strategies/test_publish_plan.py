"""
Контрактные тесты ``PUBLISH_PLAN``: согласованность плана, реестра стратегий и конфига.
"""

import pytest

from autodoc.config.schemas.confluence_config import PublishAllConfig, StrategiesConfig
from autodoc.publisher.strategies import registry
from autodoc.publisher.strategies.publish_plan import (
    PUBLISH_PLAN,
    PublishNode,
    parent_key_of,
    plan_keys,
)


@pytest.mark.contract
def test_publish_plan_keys_match_registry_and_config_sections() -> None:
    """
    Ключи плана, ``registry.STRATEGIES`` и секций ``StrategiesConfig`` совпадают.

    Чек-лист добавления новой страницы состоит из класса стратегии, строки реестра,
    узла плана и секции конфига. Если разработчик забыл один из шагов, множества ключей
    расходятся; сообщение assert-а показывает симметрические разности, чтобы сразу
    было видно, какого шага не хватает. Повторы ключей в плане тоже недопустимы.
    """
    keys = plan_keys()
    plan = set(keys)
    in_registry = set(registry.STRATEGIES)
    in_config = set(StrategiesConfig.model_fields)

    assert len(keys) == len(plan), f"повторы ключей в плане: {keys}"
    assert plan == in_registry, (
        f"план и реестр расходятся: {sorted(plan ^ in_registry)} "
        "(нужны узел PUBLISH_PLAN и строка registry.STRATEGIES)"
    )
    assert plan == in_config, (
        f"план и секции StrategiesConfig расходятся: {sorted(plan ^ in_config)} "
        "(нужны узел PUBLISH_PLAN и секция StrategiesConfig)"
    )


@pytest.mark.contract
@pytest.mark.parametrize(
    "node",
    [pytest.param(n, id=n.key) for n in PUBLISH_PLAN if n.parent_from is not None],
)
def test_publish_plan_parent_precedes_child_and_is_single_page(node: PublishNode) -> None:
    """
    Родитель стоит в плане раньше потомка и является одностраничной стратегией.

    ``publish_all()`` читает ``details[0]["page_id"]`` из отчёта родителя. У многостраничной
    стратегии (например, паспортов) «первая запись» не определяет родителя, а родитель,
    опубликованный позже потомка, на момент публикации потомка ещё не существует.
    """
    keys = plan_keys()

    assert node.parent_from in keys
    assert keys.index(node.parent_from) < keys.index(node.key)
    assert registry.STRATEGIES[node.parent_from].IS_SINGLE_PAGE is True


@pytest.mark.contract
def test_publish_all_default_targets_follow_plan_order() -> None:
    """
    Значение ``targets`` по умолчанию совпадает с порядком плана.

    Без явного ``publish_all`` публикуются все типы; список по умолчанию строится из
    ``plan_keys()``, поэтому новый узел плана попадает в него без правок конфига.
    """
    assert PublishAllConfig().targets == plan_keys()


@pytest.mark.contract
def test_parent_key_of_unknown_key_raises_value_error() -> None:
    """
    ``parent_key_of()`` на неизвестном ключе даёт явную ошибку, а не ``None``.

    ``None`` означает «у типа собственный родитель», поэтому возврат ``None`` для опечатки
    в ключе молча маскировал бы ошибку; ключ должен попасть в текст исключения.
    """
    with pytest.raises(ValueError, match="'kit_unknown'"):
        parent_key_of("kit_unknown")

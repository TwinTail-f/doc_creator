"""
Контрактные тесты ``kwargs_from_config`` стратегий публикации.
"""

import pytest

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.publisher.strategies import registry


@pytest.mark.contract
@pytest.mark.parametrize("key", ["release", "profile_centric", "kit_pinned", "kit_latest"])
def test_single_page_kwargs_from_config_returns_only_page_title(
    minimal_confluence_config: dict,
    key: str,
) -> None:
    """Одностраничные стратегии берут из конфига ровно ``page_title`` своей секции.

    Заголовок задан в секции явно и отличается от значения по умолчанию, чтобы поймать
    подмену дефолтом или чтение чужой секции. Остальные аргументы (шаблон, ссылки на
    паспорта) стратегии подставляют сами, поэтому в результате их быть не должно.
    """
    config = ConfluenceConfigSchema(
        **{
            **minimal_confluence_config,
            "strategies": {key: {"root_parent_name": "P", "page_title": f"Заголовок {key}"}},
        }
    )

    kwargs = registry.STRATEGIES[key].kwargs_from_config(config, key)

    assert kwargs == {"page_title": f"Заголовок {key}"}


@pytest.mark.contract
def test_passports_kwargs_from_config_returns_batch_parameters(
    minimal_confluence_config: dict,
) -> None:
    """Паспорта берут из конфига шаблон и параметры пакетной публикации.

    Значения выбраны нестандартными (``publish_batch_size=7`` и т.д.), чтобы поймать
    подмену значениями по умолчанию. ``template_name`` передаётся явно и равен
    ``PassportsStrategy.DEFAULT_TEMPLATE``, чтобы поведение не зависело от дефолта конструктора.
    """
    config = ConfluenceConfigSchema(
        **{
            **minimal_confluence_config,
            "publish_batch_size": 7,
            "publish_batch_delay_seconds": 1.5,
            "target_release_version": "Platform 9.9",
        }
    )
    strategy_cls = registry.STRATEGIES["passports"]

    kwargs = strategy_cls.kwargs_from_config(config, "passports")

    assert kwargs == {
        "template_name": strategy_cls.DEFAULT_TEMPLATE,
        "batch_size": 7,
        "batch_delay_seconds": 1.5,
        "target_release_version": "Platform 9.9",
    }

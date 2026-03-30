"""Стратегия публикации страницы документации от профилей сборки."""
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer


class ProfileCentricStrategy(
    ReleasePageStrategy,
    strategy_type='profile_centric',
    transformer_cls=ProfileCentricTransformer,
):
    """Публикует профиль-центричную документацию релиза на одной странице."""
    pass

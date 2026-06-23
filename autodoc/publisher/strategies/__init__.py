"""Стратегии публикации документации в Confluence.

Импорт любого символа из этого пакета гарантирует регистрацию всех
конкретных стратегий в ``BasePublishStrategy._registry`` — без
side-effect импортов в вызывающем коде.
"""

from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy

__all__ = [
    "PassportsStrategy",
    "ProfileCentricStrategy",
    "ReleasePageStrategy",
]

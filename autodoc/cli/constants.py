"""Константы CLI-утилиты autodoc."""

from importlib.metadata import PackageNotFoundError, version

from autodoc.publisher.strategies.kit_fixed_strategy import KitFixedPageStrategy
from autodoc.publisher.strategies.kit_latest_strategy import KitLatestPageStrategy
from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy

# Текущая версия утилиты autodoc
try:
    VERSION: str = version("autodoc")
except PackageNotFoundError:
    VERSION = "unknown"

# Имена Jinja2-шаблонов — единственный источник истины в классах стратегий
RELEASE_TEMPLATE: str = ReleasePageStrategy.DEFAULT_TEMPLATE
PROFILE_TEMPLATE: str = ProfileCentricStrategy.DEFAULT_TEMPLATE
PASSPORT_TEMPLATE: str = PassportsStrategy.DEFAULT_TEMPLATE
KIT_FIXED_TEMPLATE: str = KitFixedPageStrategy.DEFAULT_TEMPLATE
KIT_LATEST_TEMPLATE: str = KitLatestPageStrategy.DEFAULT_TEMPLATE

# Заголовок страницы релизной документации по умолчанию
DEFAULT_RELEASE_PAGE_TITLE: str = "Release Documentation"

# Заголовок страницы профильной документации по умолчанию
DEFAULT_PROFILE_PAGE_TITLE: str = "Документация от профилей"

# Заголовки страниц «комплекта встраивания» по умолчанию
DEFAULT_KIT_FIXED_PAGE_TITLE: str = "Комплект для встраивания компонентов platform"
DEFAULT_KIT_LATEST_PAGE_TITLE: str = "Встраивание последних версий компонентов платформы"

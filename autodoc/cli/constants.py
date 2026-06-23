"""Константы CLI-утилиты autodoc."""

from importlib.metadata import PackageNotFoundError, version

from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy

# Текущая версия утилиты autodoc
try:
    VERSION: str = version("autodoc")
except PackageNotFoundError:
    VERSION = "unknown"

# Имена Jinja2-шаблонов — единственный источник истины в классах стратегий
RELEASE_TEMPLATE: str = ReleasePageStrategy.DEFAULT_TEMPLATE
PROFILE_TEMPLATE: str = ProfileCentricStrategy.DEFAULT_TEMPLATE
PASSPORT_TEMPLATE: str = PassportsStrategy.DEFAULT_TEMPLATE

# Заголовок страницы релизной документации по умолчанию
DEFAULT_RELEASE_PAGE_TITLE: str = "Release Documentation"

# Заголовок страницы профильной документации по умолчанию
DEFAULT_PROFILE_PAGE_TITLE: str = "Документация от профилей"

"""
Pydantic-схемы для валидации конфигурационных файлов проекта.
"""
import os

from pydantic import BaseModel, ConfigDict, Field, model_validator

class ParserConfigSchema(BaseModel):
    """Схема валидации ``parser_config.json`` / ``parser_config.yaml``."""

    # Обязательные поля
    platform_version: str = Field(..., description="Версия платформы (например '2.0')")
    platform_branch_name: str = Field(..., description="Ветка в репозитории (например 'develop')")
    tfs_username: str = Field(..., description='Имя пользователя TFS')
    tfs_token: str = Field(..., description='Personal Access Token для TFS')
    # 4.2 было: tfs_DEP_Components_url
    tfs_dep_components_url: str = Field(..., description='Базовый URL проекта DEP_Components в TFS')
    manifests_remotes_path: str = Field(..., description='Путь к директории с манифестами в TFS')

    # Опциональные поля
    artifactory_components_conan2_url: str = Field(
        default='',
        description='URL Artifactory для Conan 2 пакетов',
    )
    profiles_urls: list[str] = Field(
        default_factory=list,
        description='Список URL на YAML-файлы профилей сборки',
    )
    excluded_components: list[str] = Field(
        default_factory=list,
        description='Список компонентов для исключения из обработки',
    )

    # 4.1 Credentials Artifactory — из конфига с fallback на env-переменные
    artifactory_username: str = Field(
        default='',
        description='Пользователь Artifactory (или из env GET_USR)',
    )
    artifactory_password: str = Field(
        default='',
        description='Пароль Artifactory (или из env GET_PWD)',
    )

    # Тайм-ауты
    tfs_request_timeout: int = Field(
        default=15,
        ge=1,
        le=120,
        description='Тайм-аут HTTP-запросов к TFS (секунды)',
    )
    conan_command_timeout: int = Field(
        default=300,
        ge=30,
        le=1800,
        description='Тайм-аут выполнения команд Conan (секунды)',
    )

    # Retry-логика
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description='Максимальное количество retry-попыток для сетевых операций',
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description='Множитель для exponential backoff (1 с, затем 2, 4, 8…)',
    )

    model_config = ConfigDict(extra='allow')

    # 4.1 Fallback на env-переменные если credentials не заданы явно в конфиге
    @model_validator(mode='after')
    def fill_artifactory_credentials_from_env(self) -> 'ParserConfigSchema':
        """Заполняет Artifactory-credentials из env GET_USR / GET_PWD если не заданы."""
        if not self.artifactory_username:
            self.artifactory_username = os.getenv('GET_USR', '')
        if not self.artifactory_password:
            self.artifactory_password = os.getenv('GET_PWD', '')
        return self

class ConfluenceConfigSchema(BaseModel):
    """Схема валидации ``confluence_config.json`` / ``confluence_config.yaml``."""

    url: str = Field(..., description='Базовый URL Confluence')
    token: str = Field(..., description='Atlassian API-токен')
    space: str = Field(..., description='Ключ Space в Confluence')

    username: str | None = Field(default=None, description='Имя пользователя (legacy-аутентификация)')
    password: str | None = Field(default=None, description='Пароль (deprecated)')
    cloud: bool = Field(default=True, description='True — Confluence Cloud, False — Data Center')
    verify_ssl: bool = Field(default=True, description='Проверять SSL-сертификаты')

    parent_id: str | None = Field(default=None, description='ID родительской страницы')
    page_title: str | None = Field(
        default='Сборки компонентов Платформы',
        description='Заголовок главной страницы',
    )
    passports_root_parent_id: str | None = Field(
        default=None,
        description='ID родительской страницы для дерева паспортов',
    )

    confluence_request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description='Тайм-аут HTTP-запросов к Confluence (секунды)',
    )
    target_platform_version: str = Field(
        default='Platform 2.2',
        description="Имя текущей платформы (например 'Platform 2.2')",
    )
    preserve_legacy_platforms: list[str] = Field(
        default_factory=list,
        description='Список имён старых платформ, контент которых нужно сохранить',
    )

    model_config = ConfigDict(extra='allow')

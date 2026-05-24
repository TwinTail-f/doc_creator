"""
Схема конфигурации парсера компонентов.
"""

from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ParserConfigSchema(BaseModel):
    """Схема валидации ``parser_config.json`` / ``parser_config.yaml``."""

    model_config = ConfigDict(extra="allow")

    # Обязательные поля
    platform_version: str = Field(
        ...,
        description='Версия платформы (например "2.0")',
    )
    platform_branch_name: str = Field(
        ...,
        description='Ветка или тег в репозитории (например "develop" или "0")',
    )
    platform_ref_type: Literal["branch", "tag", "commit"] = Field(
        default="branch",
        description='Тип версии: "branch" (по умолчанию), "tag" или "commit"',
    )
    username: str = Field(
        ...,
        description="Имя пользователя TFS / Artifactory (используется в conan remote login и config install)",
    )
    tfs_token: str = Field(
        ...,
        description="Personal Access Token для TFS",
    )

    @field_validator("tfs_token")
    @classmethod
    def tfs_token_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("tfs_token не может быть пустой строкой")
        return v

    artifactory_token: str | None = Field(
        default=None,
        validate_default=True,
        description="PAT-токен Artifactory",
    )
    tfs_collection_url: str = Field(
        ...,
        description="Базовый URL коллекции TFS",
    )

    @field_validator("tfs_collection_url")
    @classmethod
    def normalize_tfs_collection_url(cls, v: str) -> str:
        return v.strip().rstrip("/")

    manifests_remotes_path: str = Field(
        ...,
        description="Путь к директории с манифестами в TFS",
    )
    conan_config_url: str = Field(
        ..., description="URL zip-архива конфигурации Conan в Artifactory"
    )

    platform_base_version: str = Field(
        default="2.0",
        description=(
            'Базовая версия платформы (например "2.0" для релизов 2.x, '
            '"1.6" для релизов 1.6.x). '
            "Используется для фильтрации манифестов"
            "и построения команд conan graph info."
        ),
    )

    # Опциональные поля
    artifactory_components_conan2_url: str = Field(
        default="",
        description="URL Artifactory для Conan 2 пакетов",
    )
    profiles_urls: list[str] = Field(
        default_factory=list,
        description="Список URL на YAML-файлы профилей сборки",
    )
    profile_settings_overrides_file: str | None = Field(
        default=None,
        description=(
            "Путь к файлу переопределений настроек Conan-профилей "
            "(``profile_settings_overrides.yaml`` или ``profile_settings_overrides.json``). "
            "Пример файла: ``configs/examples/profile_settings_overrides.yaml``. "
            "Используется как костыль для Jinja-профилей, читающих env-переменные "
            "(например ``KOS_SDK_VER`` → ``compiler.toolchain_config_id``). "
            "Если не указан или файл не найден — переопределения не применяются."
        ),
    )

    component_names: list[str] = Field(
        default_factory=list,
        description=(
            "Список имён компонентов для фильтрации. "
            "Режим применения определяется полем component_filter_mode."
        ),
    )
    component_filter_mode: Literal["exclude", "include"] = Field(
        default="exclude",
        description=(
            "Режим фильтрации компонентов: "
            '"exclude" — исключить перечисленные компоненты (чёрный список, по умолчанию); '
            '"include" — обрабатывать только перечисленные компоненты (белый список).'
        ),
    )
    exact_range_components: list[str] = Field(
        default_factory=list,
        description=(
            "Список компонентов с нестандартным версионированием, для которых "
            "команда conan graph info формируется с точным числовым диапазоном "
            "[>={version} <{version+1}] вместо стандартного [~{version},include_prerelease]. "
            "Используется для компонентов, у которых формат версии менялся "
            "(например, добавлялся или убирался числовой сегмент) и оператор ~ "
            "даёт некорректный диапазон. Пример: версия 20.11.10 "
            "получит диапазон [>=20.11.10 <20.11.11]."
        ),
    )

    # Тайм-ауты
    tfs_request_timeout: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Тайм-аут HTTP-запросов к TFS (секунды)",
    )
    conan_command_timeout: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Тайм-аут выполнения команд Conan (секунды)",
    )

    # Retry-логика
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Максимальное количество retry-попыток для сетевых операций",
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Множитель для exponential backoff (1 с, затем 2, 4, 8…)",
    )

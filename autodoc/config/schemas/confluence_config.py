"""
Схема конфигурации Confluence.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RootParentFields(BaseModel):
    """Адресация родительской страницы: общие поля для всех стратегий публикации."""

    root_parent_id: str | None = Field(
        default=None,
        description="ID родительской страницы Confluence.",
    )
    root_parent_name: str | None = Field(
        default=None,
        description="Название родительской страницы Confluence.",
    )


class SinglePageDocsFields(RootParentFields):
    """Поля single-page стратегий: адресация родителя + заголовок публикуемой страницы."""

    page_title: str | None = Field(
        default=None,
        description="Заголовок публикуемой страницы.",
    )


class ReleaseDocsFields(SinglePageDocsFields):
    """Поля стратегии release — со своим дефолтным заголовком."""

    page_title: str | None = Field(
        default="Сборки компонентов Платформы",
        description="Заголовок корневой страницы релизной документации.",
    )


class ProfileCentricDocsFields(SinglePageDocsFields):
    """
    Поля стратегии profile_centric. Отдельный класс — по аналогии с ReleaseDocsFields,
    хотя дефолт page_title тот же (None), что и в SinglePageDocsFields; так пара
    (release, profile_centric) выглядит симметрично и в схему легко добавить
    третьей single-page стратегии её собственный дефолт заголовка.
    """


class KitFixedDocsFields(SinglePageDocsFields):
    """Поля стратегии kit_fixed — со своим дефолтным заголовком."""

    page_title: str | None = Field(
        default="Комплект для встраивания компонентов platform",
        description="Заголовок страницы фиксированных версий компонентов по каналам.",
    )


class KitLatestDocsFields(SinglePageDocsFields):
    """Поля стратегии kit_latest — со своим дефолтным заголовком."""

    page_title: str | None = Field(
        default="Встраивание последних версий компонентов платформы",
        description="Заголовок страницы ссылок на последние сборки компонентов по каналам.",
    )


class StrategiesConfig(BaseModel):
    """
    Настройки публикации, сгруппированные по типу стратегии.

    Имена полей класса дословно совпадают с ключами ``registry.STRATEGIES``
    (``"release"``, ``"profile_centric"``, ``"passports"``, ``"kit_fixed"``,
    ``"kit_latest"``) — это специально, чтобы резолвинг ``strategy_type ->
    секция конфига`` был просто ``getattr(strategies, strategy_type)``, без
    отдельной таблицы соответствия где-либо в коде.
    """

    release: ReleaseDocsFields = Field(default_factory=ReleaseDocsFields)
    profile_centric: ProfileCentricDocsFields = Field(default_factory=ProfileCentricDocsFields)
    passports: RootParentFields = Field(default_factory=RootParentFields)
    kit_fixed: KitFixedDocsFields = Field(default_factory=KitFixedDocsFields)
    kit_latest: KitLatestDocsFields = Field(default_factory=KitLatestDocsFields)

    @model_validator(mode="after")
    def _require_root_parent_for_explicit_sections(self) -> "StrategiesConfig":
        """
        Секция, явно присутствующая в конфиге, обязана задавать root_parent_name
        и/или root_parent_id. Секция, которую пользователь вообще не упомянул в файле
        (полагается целиком на CLI-флаги на каждый вызов) — легальна, для неё эта
        проверка не запускается. См. раздел 2.3 спеки.
        """
        for section_name in self.model_fields_set & {
            "release",
            "profile_centric",
            "passports",
            "kit_fixed",
            "kit_latest",
        }:
            section: RootParentFields = getattr(self, section_name)
            if not section.root_parent_id and not section.root_parent_name:
                raise ValueError(
                    f"strategies.{section_name}: укажите root_parent_name или "
                    f"root_parent_id. Либо не указывайте секцию '{section_name}' "
                    "вовсе, если родительская страница всегда передаётся через CLI."
                )
        return self


class ConfluenceConfigSchema(BaseModel):
    """Схема валидации ``confluence_config.json`` / ``confluence_config.yaml``."""

    model_config = ConfigDict(extra="allow")

    url: str = Field(
        ...,
        description="Базовый URL Confluence",
    )
    token: str = Field(
        ...,
        description="Atlassian API-токен",
    )
    space: str = Field(
        ...,
        description="Ключ Space в Confluence",
    )

    verify_ssl: bool = Field(
        default=True,
        description="Проверять SSL-сертификаты",
    )

    strategies: StrategiesConfig = Field(
        default_factory=StrategiesConfig,
        description="Настройки публикации по типам стратегий (release/profile_centric/passports).",
    )

    confluence_request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Тайм-аут HTTP-запросов к Confluence (секунды)",
    )
    publish_batch_size: int = Field(
        default=10,
        ge=1,
        le=200,
        description=(
            "Количество страниц паспортов, публикуемых в одном пакете. "
            "Уменьшите при перегрузках сервера Confluence."
        ),
    )
    publish_batch_delay_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=60.0,
        description=(
            "Задержка в секундах между пакетами при публикации паспортов. " "0 — без задержки."
        ),
    )
    title_conflict_policy: Literal["error", "move"] = Field(
        default="error",
        description=(
            "Поведение при обнаружении страницы с совпадающим заголовком под другим "
            "родителем: 'error' — прервать операцию с исключением (по умолчанию); "
            "'move' — перенести существующую страницу под ожидаемого родителя, "
            "сохранив её текущее содержимое."
        ),
    )
    target_release_version: str = Field(
        default="Platform 2.2",
        description='Подпись текущего релиза (например "Platform 2.2"). '
        "Используется в заголовке паспортов и метке вкладки релиза.",
    )

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        """Проверяет непустоту URL и убирает завершающий слеш."""
        if not v or not v.strip():
            raise ValueError("url не может быть пустым")
        return v.rstrip("/")

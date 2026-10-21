"""
Схема конфигурации Confluence.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autodoc.publisher.strategies.publish_plan import (
    PUBLISH_PLAN,
    keys_with_own_parent,
    plan_keys,
)


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

    page_title: str = Field(
        ...,
        description="Заголовок публикуемой страницы.",
    )

    @field_validator("page_title")
    @classmethod
    def _require_non_blank_page_title(cls, v: str) -> str:
        """Запрещает пустой заголовок и заголовок из одних пробелов."""
        if not v.strip():
            raise ValueError("page_title не может быть пустым")
        return v


class ReleaseDocsFields(SinglePageDocsFields):
    """Поля стратегии release — со своим дефолтным заголовком."""

    page_title: str = Field(
        default="Сборки компонентов Платформы",
        description="Заголовок корневой страницы релизной документации.",
    )


class ProfileCentricDocsFields(SinglePageDocsFields):
    """Поля стратегии profile_centric — со своим дефолтным заголовком."""

    page_title: str = Field(
        default="Документация от профилей",
        description="Заголовок страницы документации в представлении от профилей сборки.",
    )


class KitPinnedDocsFields(SinglePageDocsFields):
    """Поля стратегии kit_pinned — со своим дефолтным заголовком."""

    page_title: str = Field(
        default="Комплект для встраивания компонентов platform",
        description="Заголовок страницы закреплённых версий компонентов по каналам.",
    )


class KitLatestDocsFields(SinglePageDocsFields):
    """Поля стратегии kit_latest — со своим дефолтным заголовком."""

    page_title: str = Field(
        default="Встраивание последних версий компонентов платформы",
        description="Заголовок страницы ссылок на последние сборки компонентов по каналам.",
    )


class StrategiesConfig(BaseModel):
    """
    Настройки публикации, сгруппированные по типу стратегии.

    Имена полей класса дословно совпадают с ключами ``registry.STRATEGIES`` —
    это специально, чтобы резолвинг ``strategy_type ->
    секция конфига`` был просто ``getattr(strategies, strategy_type)``, без
    отдельной таблицы соответствия где-либо в коде.
    """

    release: ReleaseDocsFields = Field(default_factory=ReleaseDocsFields)
    profile_centric: ProfileCentricDocsFields = Field(default_factory=ProfileCentricDocsFields)
    passports: RootParentFields = Field(default_factory=RootParentFields)
    kit_pinned: KitPinnedDocsFields = Field(default_factory=KitPinnedDocsFields)
    kit_latest: KitLatestDocsFields = Field(default_factory=KitLatestDocsFields)

    @model_validator(mode="after")
    def _require_root_parent_for_explicit_sections(self) -> "StrategiesConfig":
        """
        Секция, явно присутствующая в конфиге, обязана задавать root_parent_name
        и/или root_parent_id. Секция, которую пользователь вообще не упомянул в файле
        (полагается целиком на CLI-флаги на каждый вызов) — легальна, для неё эта
        проверка не запускается.
        """
        for section_name in self.model_fields_set & set(plan_keys()):
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
        description="Настройки публикации по типам стратегий.",
    )

    publish_targets: list[str] = Field(
        default_factory=plan_keys,
        min_length=1,
        description=(
            f"Типы публикации для publish targets: {', '.join(plan_keys())}. "
            "По умолчанию — все. Порядок публикации задаётся планом публикации "
            "и от порядка в списке не зависит."
        ),
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

    def missing_root_parents_error(self) -> str | None:
        """
        Проверяет, что у выбранных в ``publish_targets`` типов задан родитель.

        Родитель (``root_parent_name`` или ``root_parent_id``) нужен типам плана без
        ``parent_from``. Типам с ``parent_from`` (профильная страница) он не нужен:
        они публикуются дочерними к странице своего родителя.

        Returns:
            Текст ошибки со всеми секциями без родителя либо ``None``.
        """
        missing = [
            f"strategies.{target}"
            for target in keys_with_own_parent()
            if target in self.publish_targets
            and not getattr(self.strategies, target).root_parent_id
            and not getattr(self.strategies, target).root_parent_name
        ]
        if not missing:
            return None
        return (
            "publish_targets: для выбранных типов не задан root_parent_name или "
            f"root_parent_id: {', '.join(missing)}. Заполните эти секции в конфиге "
            "или уберите соответствующие типы из publish_targets."
        )

    @model_validator(mode="after")
    def _require_root_parents_for_explicit_publish_targets(self) -> "ConfluenceConfigSchema":
        """
        Если ``publish_targets`` явно указан в конфиге, у выбранных типов должен быть родитель.

        Без явного ``publish_targets`` публикуются все типы, но конфиг остаётся валидным:
        он может использоваться только отдельными командами ``publish ...``.
        Тогда наличие родителей проверяет сам ``publish targets`` перед публикацией.
        """
        if "publish_targets" in self.model_fields_set:
            error = self.missing_root_parents_error()
            if error:
                raise ValueError(error)
        return self

    @field_validator("publish_targets")
    @classmethod
    def _validate_publish_targets(cls, targets: list[str]) -> list[str]:
        """Запрещает неизвестные типы, повторы и дочерние типы без родителя из плана."""
        known = plan_keys()
        unknown = list(dict.fromkeys(t for t in targets if t not in known))
        if unknown:
            raise ValueError(
                f"publish_targets: неизвестные типы: {', '.join(unknown)}. "
                f"Допустимые: {', '.join(known)}."
            )
        duplicates = sorted({t for t in targets if targets.count(t) > 1})
        if duplicates:
            raise ValueError(f"publish_targets: повторяющиеся типы: {', '.join(duplicates)}.")
        for node in PUBLISH_PLAN:
            if (
                node.parent_from is not None
                and node.key in targets
                and node.parent_from not in targets
            ):
                raise ValueError(
                    f"publish_targets: '{node.key}' публикуется дочерней страницей "
                    f"'{node.parent_from}', добавьте '{node.parent_from}' "
                    f"или уберите '{node.key}'."
                )
        return targets

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        """Проверяет непустоту URL и убирает завершающий слеш."""
        if not v or not v.strip():
            raise ValueError("url не может быть пустым")
        return v.rstrip("/")

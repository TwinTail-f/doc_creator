"""Абстрактный базовый класс трансформеров данных и миксин для ссылок на паспорта."""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.view_models import ConanVariantView

_DEFAULT_PASSPORT_PATTERN: str | None = None
"""
Шаблон URL паспорта по умолчанию.

Намеренно ``None``: паспортная ссылка всегда должна внедряться
``PassportPageRegistry`` после публикации. До заполнения реестра
ссылка недоступна, поэтому шаблон отображает «—» вместо нерабочего URL.
Передайте явный ``passport_page_pattern`` в конструктор трансформера,
только если вы знаете URL заранее.
"""


class PassportLinkMixin:
    """
    Миксин, добавляющий поддержку ссылок на паспорта компонентов.

    Устраняет дублирование одинаковых ``_DEFAULT_PASSPORT_PATTERN`` и
    ``_passport_link()`` из ``BaseReleaseTransformer`` и
    ``ProfileCentricTransformer``.

    Классы-наследники должны устанавливать ``_include_passport_links``
    и ``_pattern`` в своём ``__init__`` до первого обращения к методу.
    """

    _include_passport_links: bool
    _pattern: str | None

    def _passport_link(self, comp_name: str, version: str) -> str | None:
        """
        Формирует ссылку на паспорт компонента.

        Args:
            comp_name: Имя компонента.
            version: Версия релиза.

        Returns:
            URL паспорта, построенный по ``_pattern``, или ``None``,
            если ссылки отключены (``_include_passport_links is False``)
            либо шаблон не задан (реестр ещё не заполнен).
        """
        if not self._include_passport_links or not self._pattern:
            return None
        return self._pattern.format(
            component_name=comp_name.replace(" ", "+"),
            release_version=version.replace(" ", "+"),
        )


class BaseDataTransformer(ABC):
    """
    Абстрактный базовый класс трансформеров данных.

    Преобразует ``ParsedResult`` в view-model, пригодный для рендеринга
    конкретного шаблона. Следует паттерну Стратегия.
    """

    @staticmethod
    def _build_install_options(
        conan_options: dict[str, Any], component_name: str
    ) -> str:
        """
        Форматирует опции варианта сборки для команды ``conan install``.

        Ключи без разделителя ``':'`` квалифицируются именем компонента
        (``opt`` → ``component_name:opt``). Ключи, уже содержащие ``':'``
        (зависимостные опции вроде ``icu:shared``), остаются без изменений.

        Args:
            conan_options: Словарь опций варианта ``{key: value}``.
            component_name: Имя пакета-владельца для квалификации ключей.

        Returns:
            Строка флагов ``-o pkg:opt=val``, разделённых пробелами,
            или пустая строка, если опций нет.
        """
        if not conan_options:
            return ""
        return " ".join(
            f"-o {k if ':' in k else f'{component_name}:{k}'}={v}"
            for k, v in conan_options.items()
        )

    @staticmethod
    def _build_variant_view(
        variant: Any,
        component_name: str,
        conan_options: dict[str, Any] | None = None,
    ) -> ConanVariantView:
        """
        Преобразует доменный ``ConanVariant`` в ``ConanVariantView`` паблишера.

        Заполняет поле ``install_options`` через ``_build_install_options``,
        квалифицируя ключи именем компонента.

        Args:
            variant: Доменный объект ``ConanVariant``.
            component_name: Имя компонента для квалификации ключей опций.
            conan_options: Разрешённые опции варианта из ``Release.option_sets``
                           (по ``variant.options_ref``). Если ``None`` — пустой словарь.

        Returns:
            Готовый ``ConanVariantView`` с предформатированными опциями.
        """
        opts = conan_options or {}
        return ConanVariantView(
            package_id=variant.package_id,
            build_url=variant.build_url,
            build_date=variant.build_date,
            conan_options=opts,
            install_options=BaseDataTransformer._build_install_options(
                opts, component_name
            ),
        )

    @abstractmethod
    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Преобразует данные в view-model для шаблона.

        Args:
            data: Полный набор данных парсера.

        Returns:
            Словарь с иерархической структурой, готовый для шаблонизатора.
        """

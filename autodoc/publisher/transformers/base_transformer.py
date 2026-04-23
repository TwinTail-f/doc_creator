"""Абстрактный базовый класс трансформеров данных и миксин для ссылок на паспорта."""

from abc import ABC, abstractmethod
from typing import Any, NamedTuple

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.view_models.passports import ConanVariantView

_DEFAULT_PASSPORT_PATTERN: str | None = None
"""
Шаблон URL паспорта по умолчанию.

Намеренно ``None``: паспортная ссылка всегда должна внедряться
``PassportPageRegistry`` после публикации. До заполнения реестра
ссылка недоступна, поэтому шаблон отображает «—» вместо нерабочего URL.
Передайте явный ``passport_page_pattern`` в конструктор трансформера,
только если вы знаете URL заранее.
"""


class _VariantOpts(NamedTuple):
    """Build options for a single Conan variant view."""

    conan_options: dict[str, Any]
    install_options_override: str | None = None


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
    def _build_install_options_from_string(options_str: str) -> str:
        """
        Преобразует строку опций из ``ConanInputOptions.options`` в флаги ``conan install``.

        Входная строка имеет формат ``"pkg:opt=val, pkg:opt2=val2"`` (как хранится
        в конфиге и отображается в таблице конфигураций).
        Результат: ``"-o pkg:opt=val -o pkg:opt2=val2"``.

        Пустая строка означает дефолтные опции — возвращает ``""``.

        Args:
            options_str: Строка опций из ``ConanInputOptions.options``.

        Returns:
            Строка флагов ``-o``, разделённых пробелами, или ``""`` если опций нет.
        """
        if not options_str or not options_str.strip():
            return ""
        parts = [p.strip() for p in options_str.split(",") if p.strip()]

        def _qualify(p: str) -> str:
            if ":" in p:
                pkg, rest = p.split(":", 1)
                if not pkg.endswith("/*"):
                    p = f"{pkg}/*:{rest}"
            return p

        return " ".join(f"-o {_qualify(p)}" for p in parts)

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

        def _qualify_key(k: str) -> str:
            pkg, opt = k.split(":", 1) if ":" in k else (component_name, k)
            if not pkg.endswith("/*"):
                pkg = f"{pkg}/*"
            return f"{pkg}:{opt}"

        return " ".join(f"-o {_qualify_key(k)}={v}" for k, v in conan_options.items())

    @staticmethod
    def _build_variant_view(
        variant: Any,
        component_name: str,
        opts: "_VariantOpts | None" = None,
    ) -> ConanVariantView:
        """
        Преобразует доменный ``ConanVariant`` в ``ConanVariantView`` паблишера.

        Заполняет поле ``install_options``:
        - Если ``opts.install_options_override`` задан, он используется напрямую
          как команда установки (опции из таблицы конфигураций).
        - Иначе строится через ``_build_install_options`` из resolved ``conan_options``.

        Args:
            variant: Доменный объект ``ConanVariant``.
            component_name: Имя компонента для квалификации ключей опций.
            opts: Объект ``_VariantOpts`` с ``conan_options`` и опциональным
                  ``install_options_override``. Если ``None`` — используется
                  пустой набор опций без переопределения.

        Returns:
            Готовый ``ConanVariantView`` с предформатированными опциями.
        """
        resolved_opts = opts or _VariantOpts(conan_options={})
        conan_options = resolved_opts.conan_options
        if resolved_opts.install_options_override is not None:
            install_opts = resolved_opts.install_options_override
        else:
            install_opts = BaseDataTransformer._build_install_options(
                conan_options, component_name
            )
        return ConanVariantView(
            package_id=variant.package_id,
            build_url=variant.build_url,
            build_date=variant.build_date,
            option_ref=variant.options_ref,
            conan_options=conan_options,
            install_options=install_opts,
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

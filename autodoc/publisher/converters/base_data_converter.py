"""Абстрактный базовый класс трансформеров данных."""

from abc import ABC, abstractmethod
from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.passport_link_mixin import _VariantOpts
from autodoc.publisher.view_models.passports import ConanVariantView


class BaseDataConverter(ABC):
    """
    Абстрактный базовый класс трансформеров данных.

    Преобразует ``ParsedResult`` в view-model, пригодный для рендеринга
    конкретного шаблона. Следует паттерну Стратегия.
    """

    @staticmethod
    def _qualify_package_ref(pkg: str) -> str:
        """Добавляет суффикс '/*' к ссылке на пакет, если он отсутствует.

        Args:
            pkg: Имя пакета или ссылка на него.

        Returns:
            Ссылка на пакет с гарантированным суффиксом '/*'.
        """
        return pkg if pkg.endswith("/*") else f"{pkg}/*"

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
            if ":" not in p:
                return p
            pkg, rest = p.split(":", 1)
            return f"{BaseDataConverter._qualify_package_ref(pkg)}:{rest}"

        return " ".join(f"-o {_qualify(p)}" for p in parts)

    @staticmethod
    def _build_install_options(conan_options: dict[str, Any], component_name: str) -> str:
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
            return f"{BaseDataConverter._qualify_package_ref(pkg)}:{opt}"

        return " ".join(f"-o {_qualify_key(k)}={v}" for k, v in conan_options.items())

    @staticmethod
    def _build_profile_definition_map(data: ParsedResult) -> dict[str, Any]:
        """Строит словарь определений профилей, индексированный по имени профиля.

        Args:
            data: Результат парсинга с полем profile_definitions.

        Returns:
            Словарь вида {profile_name: ProfileDefinition}.
        """
        return {pd.profile_name: pd for pd in data.profile_definitions}

    @staticmethod
    def _build_variant_view(
        variant: Any,
        component_name: str,
        opts: "_VariantOpts | None" = None,
    ) -> ConanVariantView:
        """
        Преобразует доменный ``ConanVariant`` в ``ConanVariantView`` паблишера.

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
            install_opts = BaseDataConverter._build_install_options(conan_options, component_name)
        return ConanVariantView(
            package_id=variant.package_id,
            build_url=variant.build_url,
            build_date=variant.build_date,
            options_ref=variant.options_ref,
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

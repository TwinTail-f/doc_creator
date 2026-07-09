"""Абстрактный базовый класс трансформеров данных."""

from abc import ABC, abstractmethod
from typing import Any, NamedTuple

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.view_models.passports import ConanVariantView


class _VariantOpts(NamedTuple):
    """Опции сборки для одного варианта Conan в view-model."""

    conan_options: dict[str, Any]
    install_options_override: str | None = None
    # {имя_опции: дефолтное_значение} компонента (DefaultOptionsSet), для подсветки
    # в UI отличий от дефолта. Если опция здесь не найдена — дефолт считается
    # неизвестным (бейдж остаётся нейтральным).
    default_options: dict[str, Any] = {}


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
        if not options_str.strip():
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
    def _resolve_profile_meta(pd_map: dict[str, Any], profile_name: str) -> tuple[dict[str, Any], str]:
        """
        Резолвит настройки и docker-образ профиля по его имени.

        Args:
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.
            profile_name: Имя искомого профиля.

        Returns:
            Кортеж ``(conan_settings, docker_image)``. Если профиль не найден —
            пустой словарь и пустая строка.
        """
        pd = pd_map.get(profile_name)
        return (dict(pd.conan_settings) if pd else {}, pd.docker_image if pd else "")

    @classmethod
    def _classify_option_badge(cls, value: Any, default_value: Any, has_default: bool) -> str:
        """
        Определяет CSS-класс бейджа опции.

        Базовая реализация не подсвечивает отличия от дефолта — используется
        только теми конвертерами, для которых это осмысленно (см. ``PassportConverter``).

        Args:
            value: Текущее значение опции варианта сборки.
            default_value: Дефолтное значение этой опции у компонента.
            has_default: Найдено ли дефолтное значение для этой опции.

        Returns:
            Имя CSS-класса бейджа (``autodoc-badge-def``).
        """
        return "autodoc-badge-def"

    @classmethod
    def _build_variant_view(
        cls,
        variant: Any,
        component_name: str,
        opts: _VariantOpts | None = None,
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
        defaults = resolved_opts.default_options
        option_badges = {
            name: cls._classify_option_badge(value, defaults.get(name), name in defaults)
            for name, value in conan_options.items()
        }
        if resolved_opts.install_options_override is not None:
            install_opts = resolved_opts.install_options_override
        else:
            install_opts = cls._build_install_options(conan_options, component_name)
        return ConanVariantView(
            package_id=variant.package_id,
            build_url=variant.build_url,
            build_date=variant.build_date,
            options_ref=variant.options_ref,
            conan_options=conan_options,
            option_badges=option_badges,
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

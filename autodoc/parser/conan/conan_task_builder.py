"""
Построитель задач для Conan graph info.
"""

import re

from autodoc.models.component import Component
from autodoc.models.options import ConanInputOptions
from autodoc.parser.conan.models.conan_task import ConanTask
from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides


class ConanTaskBuilder:
    """
    Строит список задач ``ConanTask`` из моделей компонентов.

    Чистый класс без I/O — легко тестируется без запуска Conan.
    Один компонент × одна версия × один профиль × один набор опций
    → одна задача.
    """

    def build(
        self,
        components: list[Component],
        target_platform: str,
        artifactory_base_url: str,
        profile_overrides: ProfileSettingsOverrides | None = None,
        exact_range_components: list[str] | None = None,
    ) -> list[ConanTask]:
        """
        Формирует полный список задач для параллельного выполнения.

        Args:
            components: Список компонентов с заполненными ``build_option_sets``.
            target_platform: Целевая платформа (например ``'2.0'``).
            artifactory_base_url: Базовый URL Artifactory для построения ссылок
                (без завершающего слэша).
            profile_overrides: Переопределения ``-s`` настроек по имени профиля.
                Используется для Jinja-профилей, читающих env-переменные (``os.getenv()``).
                Если ``None`` — переопределения не применяются.
            exact_range_components: Список имён компонентов с нестандартным
                версионированием. Для них вместо ``[~{version},include_prerelease]``
                формируется точный диапазон ``[>={version} <{version+1}]``.
                Актуально для компонентов, у которых формат версии менялся
                (добавление/сокращение числовых сегментов).

        Returns:
            Список задач. Может быть пустым, если у компонентов нет профилей.
        """
        tasks: list[ConanTask] = []
        overrides = profile_overrides or ProfileSettingsOverrides()
        exact_range_set: set[str] = set(exact_range_components or [])

        for comp in components:
            for release in comp.releases:
                input_options: list[ConanInputOptions] = release.build_option_sets or [
                    ConanInputOptions(id="1", options="")
                ]

                use_exact_range = comp.name in exact_range_set
                reference = self._format_reference(
                    name=comp.name,
                    version=release.version,
                    platform=target_platform,
                    channel=release.channel,
                    exact_range=use_exact_range,
                )

                for pb in release.profile_builds:
                    extra_settings = overrides.resolve(pb.profile_name)
                    for conan_input in input_options:
                        opt_list = (
                            [o.strip() for o in conan_input.options.split(",") if o.strip()]
                            if conan_input.options
                            else []
                        )
                        cmd = self._build_cmd(reference, pb.profile_name, opt_list, extra_settings)
                        tasks.append(
                            ConanTask(
                                cmd=cmd,
                                comp_name=comp.name,
                                version=release.version,
                                channel=release.channel,
                                profile_name=pb.profile_name,
                                option_id=conan_input.id,
                                option_str=(
                                    conan_input.options.strip() if conan_input.options else ""
                                ),
                                target_platform=target_platform,
                                artifactory_base_url=artifactory_base_url,
                                release=release,
                                pb=pb,
                            )
                        )

        return tasks

    @staticmethod
    def _calc_upper_bound(numeric_prefix: str) -> str:
        """
        Вычисляет верхнюю границу диапазона, увеличивая последний числовой сегмент на 1.

        Используется для построения диапазонов ``[>=X <Y]``, где Y = X с
        инкрементированным последним сегментом.

        Args:
            numeric_prefix: Строго числовая строка вида ``'8.4'``, ``'20.11.10'``.

        Returns:
            Строка с увеличенным последним сегментом: ``'8.5'``, ``'20.11.11'``.
        """
        parts = numeric_prefix.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)

    def _format_reference(
        self,
        name: str,
        version: str,
        platform: str,
        channel: str,
        exact_range: bool = False,
    ) -> str:
        """
        Формирует Conan-ссылку (requires).

        Для компонентов из ``exact_range_components`` или версий с буквами
        (``8.4p1``, ``1.1.1t``) строит точный диапазон ``[>=version <version+1]``.
        Для чисто числовых версий использует стандартный оператор ``~`` Conan 2.
        Версии без числового префикса (``latest``) подставляются как есть.

        Args:
            name: Имя компонента.
            version: Строка версии (например ``'3.34.1'`` или ``'8.4p1'``).
            platform: Версия целевой платформы (например ``'2.0'``).
            channel: Канал публикации (например ``'stable'``).
            exact_range: Если ``True`` — использовать точный диапазон ``[>=X <X+1]``
                вместо стандартного ``~``.

        Returns:
            Строка Conan-ссылки для передачи в ``--requires``.
        """
        suffix = f"@platform-{platform}/{channel}"
        match = re.match(r"^(\d+(?:\.\d+)*)", version)

        if not match:
            return f"{name}/{version}{suffix}"

        is_pure_numeric = re.match(r"^[\d\.]+$", version)
        if is_pure_numeric and not exact_range:
            return f"{name}/[~{version},include_prerelease]{suffix}"

        upper_bound = self._calc_upper_bound(match.group(1))
        return f"{name}/[>={match.group(1)} <{upper_bound}]{suffix}"

    def _build_cmd(
        self,
        reference: str,
        profile_name: str,
        options: list[str],
        extra_settings: dict[str, str] | None = None,
    ) -> list[str]:
        """
        Собирает список аргументов CLI-команды ``conan graph info``.

        Каждая опция из ``options`` добавляется флагом ``-o``.
        Если опция не содержит ``:``, добавляется префикс ``*:``
        Если опция содержит ``:``, но не ``/*:`` и не начинается на ``*:``,
        имя пакета расширяется до шаблона ``pkg/*:opt``.

        Дополнительные настройки из ``extra_settings`` добавляются флагами ``-s key=value``.
        Используется для Jinja-профилей, читающих env-переменные
        (например ``compiler.toolchain_config_id``).

        Args:
            reference: Conan-ссылка с диапазоном версии.
            profile_name: Имя профиля сборки.
            options: Список отдельных строк опций (может быть пустым списком).
            extra_settings: Словарь дополнительных настроек ``{key: value}``
                для добавления в команду флагами ``-s``. Если ``None`` или пуст —
                игнорируется.

        Returns:
            Список аргументов для передачи в ``subprocess.run``.
        """
        cmd = [
            "conan",
            "graph",
            "info",
            f"--requires={reference}",
            f"-pr={profile_name}",
            "--format=json",
        ]

        # Явные -s настройки для Jinja-профилей, читающих env-переменные
        if extra_settings:
            for key, value in extra_settings.items():
                cmd.extend(["-s", f"{key}={value}"])

        for opt in options:
            cmd.extend(["-o", self._normalize_option(opt)])

        return cmd

    def _normalize_option(self, opt: str) -> str:
        """
        Нормализует одну опцию Conan до формата ``pkg/*:key=val``.

        Args:
            opt: Сырая строка опции (например ``'shared=True'`` или
                ``'mylib:shared=True'``).

        Returns:
            Нормализованная строка опции.
        """
        if ":" in opt:
            if "/*:" not in opt and not opt.startswith("*:"):
                pkg, rest = opt.split(":", 1)
                return f"{pkg}/*:{rest}"
            return opt
        return f"*:{opt}"

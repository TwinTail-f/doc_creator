"""
Построитель задач для Conan graph info.
"""

from dataclasses import dataclass

from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides

# Шаблон Conan version range с поддержкой pre-release версий
_CONAN_REF_TEMPLATE: str = (
    "{name}/[~{version},include_prerelease]@platform-{platform}/{channel}"
)


@dataclass(frozen=True)
class ConanTask:
    """
    Единица задачи для одного вызова ``conan graph info``.

    Хранит готовую CLI-команду и ссылки на модели данных,
    которые будут обогащены после успешного выполнения.

    Attributes:
        cmd: Готовая CLI-команда для передачи в ``subprocess.run``.
        comp_name: Имя компонента.
        version: Версия компонента.
        channel: Канал (например ``'stable'``).
        profile_name: Имя профиля сборки Conan.
        option_id: Идентификатор набора опций.
        option_str: Строка опций через запятую.
        target_platform: Целевая платформа.
        artifactory_base_url: Базовый URL Artifactory для построения ссылок.
        release: Ссылка на объект ``Release`` для последующего обогащения.
        pb: Ссылка на объект ``ProfileBuild`` для последующего обогащения.
    """

    cmd: list[str]
    comp_name: str
    version: str
    channel: str
    profile_name: str
    option_id: str
    option_str: str
    target_platform: str
    artifactory_base_url: str
    release: Release
    pb: ProfileBuild


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
    ) -> list[ConanTask]:
        """
        Формирует полный список задач для параллельного выполнения.

        Args:
            components: Список компонентов с заполненными ``_build_option_sets_internal``.
            target_platform: Целевая платформа (например ``'2.0'``).
            artifactory_base_url: Базовый URL Artifactory для построения ссылок.
            profile_overrides: Переопределения ``-s`` настроек по имени профиля.
                Используется как костыль для Jinja-профилей с ``os.getenv()``.
                Если ``None`` — переопределения не применяются.

        Returns:
            Список задач. Может быть пустым, если у компонентов нет профилей.
        """
        tasks: list[ConanTask] = []
        art_base = artifactory_base_url.rstrip("/")
        overrides = profile_overrides or ProfileSettingsOverrides.empty()

        for comp in components:
            for release in comp.releases:
                options_dict = release._build_option_sets_internal or {"1": ""}

                reference = _CONAN_REF_TEMPLATE.format(
                    name=comp.name,
                    version=release.version,
                    platform=target_platform,
                    channel=release.channel,
                )

                for pb in release.profile_builds:
                    extra_settings = overrides.resolve(pb.profile_name)
                    for opt_id, opt_str in options_dict.items():
                        cmd = self._build_cmd(
                            reference, pb.profile_name, opt_str, extra_settings
                        )
                        tasks.append(
                            ConanTask(
                                cmd=cmd,
                                comp_name=comp.name,
                                version=release.version,
                                channel=release.channel,
                                profile_name=pb.profile_name,
                                option_id=str(opt_id),
                                option_str=opt_str.strip() if opt_str else "",
                                target_platform=target_platform,
                                artifactory_base_url=art_base,
                                release=release,
                                pb=pb,
                            )
                        )

        return tasks

    @staticmethod
    def _build_cmd(
        reference: str,
        profile_name: str,
        opt_str: str,
        extra_settings: dict[str, str] | None = None,
    ) -> list[str]:
        """
        Собирает список аргументов CLI-команды ``conan graph info``.

        Каждая опция из ``opt_str`` (через запятую) добавляется флагом ``-o``.
        Если опция не содержит ``:``, добавляется префикс ``*:``
        Если опция содержит ``:``, но не ``/*:`` и не начинается на ``*:``,
        имя пакета расширяется до шаблона ``pkg/*:opt``.

        Дополнительные настройки из ``extra_settings`` добавляются флагами ``-s key=value``.
        Используется как костыль для Jinja-профилей, требующих env-переменные
        (например ``compiler.toolchain_config_id``).

        Args:
            reference: Conan-ссылка с диапазоном версии.
            profile_name: Имя профиля сборки.
            opt_str: Строка опций через запятую (может быть пустой).
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

        # Костыль: явные -s настройки для профилей с os.getenv() в Jinja-шаблонах
        if extra_settings:
            for key, value in extra_settings.items():
                cmd.extend(["-s", f"{key}={value}"])

        if opt_str:
            for raw_opt in opt_str.split(","):
                opt = raw_opt.strip()
                if not opt:
                    continue
                cmd.extend(["-o", ConanTaskBuilder._normalize_option(opt)])

        return cmd

    @staticmethod
    def _normalize_option(opt: str) -> str:
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

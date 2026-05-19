"""
Построитель задач для Conan graph info.
"""

import re

from autodoc.models.component import Component
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

                reference = self._format_reference(
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
    
    def _format_reference(self, name: str, version: str, platform: str, channel: str) -> str:
        """
        Формирует Conan-ссылку (requires).
        Умеет работать с кастомными версиями (например, 8.4p1), вычисляя верхнюю
        границу диапазона на стороне Python, чтобы избежать падения Conan 2.
        """
        # 1. Если версия соответствует строгому SemVer (только цифры и точки)
        # Conan 2 отлично справляется с оператором ~ самостоятельно.
        if re.match(r"^[\d\.]+$", version):
            return f"{name}/[~{version},include_prerelease]@platform-{platform}/{channel}"
        
        # 2. Если версия содержит буквы (например, '8.4p1' или '1.1.1t')
        # Извлекаем чисто числовой префикс с помощью регулярки. 
        match = re.match(r"^(\d+(?:\.\d+)*)", version)
        if match:
            numeric_prefix = match.group(1) # '8.4'
            parts = numeric_prefix.split('.')
            
            # Увеличиваем последнюю цифру на 1 (8.4 -> 8.5)
            parts[-1] = str(int(parts[-1]) + 1)
            upper_bound = '.'.join(parts)   # '8.5'
            
            # Вручную формируем диапазон: [>=8.4p1 <8.5,include_prerelease]
            return (
                f"{name}/[>={version} <{upper_bound}]"
                f"@platform-{platform}/{channel}"
            )

        # 3. Фолбэк для версий, вообще не начинающихся с цифр (например "latest") 
        return f"{name}/{version}@platform-{platform}/{channel}"

    def _build_cmd(
        self,
        reference: str,
        profile_name: str,
        opt_str: str = "",
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

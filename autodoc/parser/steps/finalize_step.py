"""
Шаг пайплайна: финализация и валидация данных.
"""

import datetime

from pydantic import ValidationError as PydanticValidationError

from autodoc.exceptions import ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component, ProfileDefinition
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.base import BaseParseStep
from autodoc.parser.pipeline.context import PipelineContext


class FinalizeStep(BaseParseStep):
    """
    Шаг 6: Финализирует данные и формирует ParsedResult.

    Выполняет: вычисление ``is_header_only``, фильтрацию профилей
    с ``exists=False``, сортировку и сборку ``ParsedResult``.
    Файлы не сохраняет — это делает ``ComponentParser`` при ``save_intermediate=True``.
    """

    name = "Финализация и валидация данных"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """
        Финализирует результаты пайплайна.

        Вычисляет флаги ``is_header_only``, удаляет профили с ``exists=False``,
        сортирует компоненты по имени и собирает ``ParsedResult``.

        Args:
            ctx: Контекст пайплайна с накопленными компонентами.
        """
        self._compute_header_only_flags(ctx.components, ctx.profile_definitions)
        ctx.components.sort(key=lambda c: c.name.lower())

        removed = self._filter_empty_profiles(ctx.components)
        if removed:
            logger.info(f"Удалено {removed} профилей с exists=False.")

        ctx.profile_definitions = self._deduplicate_profile_definitions(ctx.profile_definitions)
        ctx.result = self._build_result(ctx)

    # SHA1 от пустой строки — стандартный нулевой package_id Conan.
    # Conan выставляет его для header-only пакетов.
    _NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

    @staticmethod
    def _compute_header_only_flags(
        components: list[Component],
        profile_definitions: list[ProfileDefinition],
    ) -> None:
        """
        Устанавливает флаг ``is_header_only`` для каждого ``Release``.

        Критерий: ВСЕ варианты во всех профилях имеют нулевой package_id
        (``da39a3ee5e6b4b0d3255bfef95601890afd80709`` - SHA1 от пустой строки).
        Именно такой package_id Conan выставляет header-only пакетам.

        Если у релиза нет ни одного варианта — флаг устанавливается в ``False``.

        Args:
            components: Список компонентов для обработки.
            profile_definitions: Не используется, оставлен для совместимости сигнатуры.
        """
        null_id = FinalizeStep._NULL_PACKAGE_ID

        for comp in components:
            for release in comp.releases:
                all_variants = [
                    variant
                    for pb in release.profile_builds
                    for variant in pb.variants
                ]

                if not all_variants:
                    release.is_header_only = False
                    continue

                release.is_header_only = all(
                    variant.package_id == null_id for variant in all_variants
                )

    @staticmethod
    def _filter_empty_profiles(components: list[Component]) -> int:
        """
        Удаляет записи ``ProfileBuild`` с ``exists=False`` из всех релизов.

        Args:
            components: Список компонентов для обработки.

        Returns:
            Количество удалённых записей профилей.
        """
        removed = 0
        for comp in components:
            for release in comp.releases:
                before = len(release.profile_builds)
                release.profile_builds = [
                    pb for pb in release.profile_builds if pb.exists
                ]
                removed += before - len(release.profile_builds)
        return removed

    @staticmethod
    def _deduplicate_profile_definitions(
        definitions: list[ProfileDefinition],
    ) -> list[ProfileDefinition]:
        """Deduplicates by profile_name, keeping the last-written entry."""
        seen: dict[str, ProfileDefinition] = {}
        for pd in definitions:
            seen[pd.profile_name] = pd
        return list(seen.values())

    @staticmethod
    def _build_result(ctx: PipelineContext) -> ParsedResult:
        """
        Собирает финальный ``ParsedResult`` из контекста пайплайна.

        Создаёт объект результата с временной меткой, версией платформы
        и списком компонентов. При ошибке Pydantic-валидации бросает
        ``ParsingError`` с понятным описанием — без стектрейса.

        Args:
            ctx: Контекст пайплайна с финализированными компонентами.

        Returns:
            Валидированный ``ParsedResult``.

        Raises:
            ParsingError: Если Pydantic-валидация не прошла.
        """
        try:
            result = ParsedResult(
                generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                platform_version=ctx.config.platform_version,
                profile_definitions=ctx.profile_definitions,   # NEW
                components=ctx.components,
            )
            logger.info(f"Данные валидированы. {len(result.components)} компонентов.")
            return result
        except PydanticValidationError as e:
            raise ParsingError(f"FinalizeStep: валидация данных не прошла: {e}") from e

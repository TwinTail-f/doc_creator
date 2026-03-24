"""
Шаг пайплайна: финализация и валидация данных.
"""
import datetime
from typing import List

from autodoc.exceptions import ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.base import BaseParseStep, PipelineContext


class FinalizeStep(BaseParseStep):
    """
    Шаг 6: Финализирует данные и формирует ParsedResult.

    Выполняет: вычисление ``is_header_only``, фильтрацию профилей
    с ``exists=False``, сортировку и сборку ``ParsedResult``.
    Файлы не сохраняет — это делает ``ComponentParser`` при ``save_intermediate=True``.
    """

    name = 'Финализация и валидация данных'
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        self._compute_header_only_flags(ctx.components)
        ctx.components.sort(key=lambda c: c.name.lower())

        removed = self._filter_empty_profiles(ctx.components)
        if removed:
            logger.info('FinalizeStep: удалено %d профилей с exists=False.', removed)

        ctx.result = self._build_result(ctx)

    # ------------------------------------------------------------------

    @staticmethod
    def _compute_header_only_flags(components: List[Component]) -> None:
        for comp in components:
            for release in comp.releases:
                profile_builds = release.profile_builds
                if not profile_builds:
                    release.is_header_only = False
                    continue
                all_set_empty = all(not pb.conan_settings for pb in profile_builds)
                has_empty_opts = any(
                    not variant.conan_options
                    for pb in profile_builds
                    for variant in pb.variants
                )
                release.is_header_only = all_set_empty and has_empty_opts

    @staticmethod
    def _filter_empty_profiles(components: List[Component]) -> int:
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
    def _build_result(ctx: PipelineContext) -> ParsedResult:
        """
        3.4 Убрана двойная сериализация model_dump() + model_validate().
        ParsedResult принимает объекты Component напрямую.
        """
        try:
            result = ParsedResult(
                generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                platform_version=ctx.config.platform_version,
                components=ctx.components,
            )
            logger.info(
                'FinalizeStep: данные валидированы. %d компонентов.',
                len(result.components),
            )
            return result
        except Exception as e:
            raise ParsingError(
                'FinalizeStep: валидация данных не прошла: %s' % e
            ) from e

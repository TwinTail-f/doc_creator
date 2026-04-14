"""
Шаг пайплайна: HTTP HEAD-проверка доступности сборок в Artifactory.
"""

import requests

from autodoc.infrastructure.logger import logger
from autodoc.infrastructure.parallel_executor import ParallelExecutor
from autodoc.models.component import Component, ConanVariant, ProfileBuild
from autodoc.parser.clients.protocols import IArtifactoryClient
from autodoc.parser.steps.base import BaseParseStep, PipelineContext

_VALIDATION_MAX_WORKERS: int = 20
_HTTP_STATUS_NOT_FOUND: int = 404
_LOG_PROGRESS_INTERVAL: int = 100


class ArtifactoryValidationStep(BaseParseStep):
    """
    Шаг 5: Проверяет доступность ссылок на сборки в Artifactory (HTTP HEAD).

    Варианты, вернувшие 404, удаляются из ``ProfileBuild.variants``.
    При сетевых ошибках вариант считается живым — чтобы не удалять данные
    из-за временных проблем сети.

    Получает ``ArtifactoryClient`` из ``PipelineContext`` — SSL-подавление
    инкапсулировано внутри ``client.head()``.

    Шаг некритический.
    """

    name = "Валидация ссылок Artifactory"
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        """
        Собирает все ``build_url`` вариантов и проверяет их параллельно.

        Args:
            ctx: Контекст пайплайна с обогащёнными компонентами.
        """
        variants_to_check = self._collect_variants(ctx.components)

        if not variants_to_check:
            logger.info("Нет ссылок для проверки.")
            return

        logger.info(f"Проверяем {len(variants_to_check)} ссылок…")

        client: IArtifactoryClient | None = ctx.artifactory_client
        if client is None:
            logger.warning("ArtifactoryClient не задан — валидация пропущена.")
            return
        dead_variants = self._check_urls_parallel(variants_to_check, client)
        self._remove_dead_variants(dead_variants)

        logger.info(f"Удалено {len(dead_variants)} недоступных вариантов (HTTP 404).")

    @staticmethod
    def _collect_variants(
        components: list[Component],
    ) -> list[tuple[ProfileBuild, ConanVariant, str]]:
        """
        Собирает все варианты с непустыми ``build_url`` для проверки.

        Преобразует UI-ссылки Artifactory в API-ссылки (замена пути).

        Args:
            components: Список компонентов с профилями и вариантами.

        Returns:
            Список кортежей ``(ProfileBuild, ConanVariant, api_url)`` для проверки.
        """
        result = []
        for comp in components:
            for release in comp.releases:
                for pb in release.profile_builds:
                    for variant in pb.variants:
                        if variant.build_url:
                            api_url = variant.build_url.replace(
                                "/ui/repos/tree/General/", "/artifactory/"
                            )
                            result.append((pb, variant, api_url))
        return result

    @staticmethod
    def _check_urls_parallel(
        variants_to_check: list[tuple[ProfileBuild, ConanVariant, str]],
        client: IArtifactoryClient,
    ) -> list[tuple[ProfileBuild, ConanVariant]]:
        """
        Проверяет доступность URL параллельно через ``ParallelExecutor``.

        При HTTP 404 вариант добавляется в список мёртвых.
        При сетевых ошибках вариант считается живым.

        Args:
            variants_to_check: Список кортежей ``(pb, variant, url)`` для проверки.
            client: Экземпляр ``ArtifactoryClient`` для HEAD-запросов.

        Returns:
            Список кортежей ``(ProfileBuild, ConanVariant)`` с недоступными вариантами.
        """

        def check_one(
            item: tuple[ProfileBuild, ConanVariant, str],
        ) -> tuple[ProfileBuild, ConanVariant, bool]:
            pb, variant, url = item
            try:
                resp = client.head(url)
                if resp.status_code == _HTTP_STATUS_NOT_FOUND:
                    return pb, variant, False
            except requests.RequestException:
                pass  # при сетевом сбое считаем вариант живым
            return pb, variant, True

        executor = ParallelExecutor(
            max_workers=_VALIDATION_MAX_WORKERS,
            log_progress_interval=_LOG_PROGRESS_INTERVAL,
            log_level="debug",
        )
        raw_results = executor.execute(
            check_one,
            variants_to_check,
            task_label="ссылок Artifactory",
        )

        dead: list[tuple[ProfileBuild, ConanVariant]] = []
        for result in raw_results:
            if result is None:
                continue
            pb, variant, is_valid = result
            if not is_valid:
                dead.append((pb, variant))

        return dead

    @staticmethod
    def _remove_dead_variants(
        dead_variants: list[tuple[ProfileBuild, ConanVariant]],
    ) -> None:
        """
        Удаляет недоступные варианты из соответствующих ``ProfileBuild``.

        Args:
            dead_variants: Список кортежей ``(ProfileBuild, ConanVariant)`` для удаления.
        """
        for pb, variant in dead_variants:
            if variant in pb.variants:
                pb.variants.remove(variant)

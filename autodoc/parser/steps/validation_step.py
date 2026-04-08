"""
Шаг пайплайна: HTTP HEAD-проверка доступности сборок в Artifactory.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component, ConanVariant, ProfileBuild
from autodoc.parser.clients.artifactory_client import ArtifactoryClient
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

        client = ctx.artifactory_client
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
        client: ArtifactoryClient,
    ) -> list[tuple[ProfileBuild, ConanVariant]]:
        """
        Проверяет доступность URL параллельно через ``ThreadPoolExecutor``.

        При HTTP 404 вариант добавляется в список мёртвых.
        При сетевых ошибках вариант считается живым.

        Args:
            variants_to_check: Список кортежей ``(pb, variant, url)`` для проверки.
            client: Экземпляр ``ArtifactoryClient`` для HEAD-запросов.

        Returns:
            Список кортежей ``(ProfileBuild, ConanVariant)`` с недоступными вариантами.
        """
        dead: list[tuple[ProfileBuild, ConanVariant]] = []

        def check_one(item: tuple[ProfileBuild, ConanVariant, str]):
            pb, variant, url = item
            try:
                resp = client.head(url)
                if resp.status_code == _HTTP_STATUS_NOT_FOUND:
                    return pb, variant, False
            except requests.RequestException:
                pass  # при сетевом сбое считаем вариант живым
            return pb, variant, True

        completed = 0
        total = len(variants_to_check)
        with ThreadPoolExecutor(max_workers=_VALIDATION_MAX_WORKERS) as executor:
            future_map = {
                executor.submit(check_one, item): item for item in variants_to_check
            }
            for future in as_completed(future_map):
                pb, variant, is_valid = future.result()
                completed += 1
                if completed % _LOG_PROGRESS_INTERVAL == 0 or completed == total:
                    logger.debug(f"Проверено {completed}/{total} ссылок…")
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

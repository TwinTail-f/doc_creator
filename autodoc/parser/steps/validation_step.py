"""
Шаг пайплайна: HTTP HEAD-проверка доступности сборок в Artifactory.
"""
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import requests        # 3.1 нужен для requests.RequestException
import urllib3

from autodoc.infrastructure.http_client import create_retryable_session
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component, ConanVariant, ProfileBuild
from autodoc.parser.steps.base import BaseParseStep, PipelineContext

_VALIDATION_MAX_WORKERS = 20
_HEAD_TIMEOUT = 10


class ArtifactoryValidationStep(BaseParseStep):
    """
    Шаг 5: Проверяет доступность ссылок на сборки в Artifactory (HTTP HEAD).

    Варианты, вернувшие 404, удаляются из ``ProfileBuild.variants``.
    При сетевых ошибках вариант считается живым — чтобы не удалять данные
    из-за временных лагов сети.

    Credentials берутся из ``ctx.config.artifactory_username/password``.
    Шаг некритический.
    """

    name = 'Валидация ссылок Artifactory'
    is_critical = False

    def execute(self, ctx: PipelineContext) -> None:
        """
        Собирает все ``build_url`` вариантов и проверяет их параллельно.

        3.11 urllib3.disable_warnings перенесён внутрь execute()
        и обёрнут в warnings.catch_warnings() — не глушит предупреждения
        для всего процесса, только для этого шага.

        Args:
            ctx: Контекст пайплайна с обогащёнными компонентами.
        """
        variants_to_check = self._collect_variants(ctx.components)

        if not variants_to_check:
            logger.info('ArtifactoryValidationStep: нет ссылок для проверки.')
            return

        logger.info(
            'ArtifactoryValidationStep: проверяем %d ссылок…',
            len(variants_to_check),
        )

        # 3.11 Suppress только на время этого шага, не глобально
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)
            session = create_retryable_session(
                username=ctx.config.artifactory_username,
                token=ctx.config.artifactory_password,
                max_retries=1,
                timeout=_HEAD_TIMEOUT,
            )
            session.verify = False  # внутренние серверы могут иметь самоподписанные сертификаты

        dead_variants = self._check_urls_parallel(variants_to_check, session)
        self._remove_dead_variants(dead_variants)

        logger.info(
            'ArtifactoryValidationStep: удалено %d недоступных вариантов (HTTP 404).',
            len(dead_variants),
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _collect_variants(
        components: List[Component],
    ) -> List[Tuple[ProfileBuild, ConanVariant, str]]:
        result = []
        for comp in components:
            for release in comp.releases:
                for pb in release.profile_builds:
                    for variant in pb.variants:
                        if variant.build_url:
                            api_url = variant.build_url.replace(
                                '/ui/repos/tree/General/', '/artifactory/'
                            )
                            result.append((pb, variant, api_url))
        return result

    @staticmethod
    def _check_urls_parallel(
        variants_to_check: List[Tuple[ProfileBuild, ConanVariant, str]],
        session,
    ) -> List[Tuple[ProfileBuild, ConanVariant]]:
        dead: List[Tuple[ProfileBuild, ConanVariant]] = []

        def check_one(item: Tuple[ProfileBuild, ConanVariant, str]):
            pb, variant, url = item
            try:
                resp = session.head(url, allow_redirects=True, timeout=_HEAD_TIMEOUT)
                if resp.status_code == 404:
                    return pb, variant, False
            except requests.RequestException:
                pass  # при сетевом сбое считаем вариант живым
            return pb, variant, True

        completed = 0
        total = len(variants_to_check)
        with ThreadPoolExecutor(max_workers=_VALIDATION_MAX_WORKERS) as executor:
            future_map = {executor.submit(check_one, item): item for item in variants_to_check}
            for future in as_completed(future_map):
                pb, variant, is_valid = future.result()
                completed += 1
                if completed % 100 == 0 or completed == total:
                    logger.debug('Проверено %d/%d ссылок…', completed, total)
                if not is_valid:
                    dead.append((pb, variant))

        return dead

    @staticmethod
    def _remove_dead_variants(
        dead_variants: List[Tuple[ProfileBuild, ConanVariant]],
    ) -> None:
        for pb, variant in dead_variants:
            if variant in pb.variants:
                pb.variants.remove(variant)

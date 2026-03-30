"""
Фетчер манифестов компонентов: скачивание .properties-файлов из TFS.
Разбор в доменные модели делегируется ManifestParser.
"""
from pathlib import Path

from autodoc.exceptions import ParsingError
from autodoc.models.component import Component
from autodoc.parser.parsers.manifest_parser import ManifestParser
from autodoc.parser.steps.base import BaseTFSFetcher, FetchResult, PipelineContext

_MANIFESTS_REPO = 'platform'


class ManifestFetcher(BaseTFSFetcher[list[Component]]):
    """
    Скачивает .properties-файлы манифестов из TFS и делегирует парсинг ManifestParser.

    Двухфазовый: сначала configure(ctx), потом fetch(tmp_dir, excluded).
    """

    def configure(self, ctx: PipelineContext) -> None:
        """Сохраняет нужные данные из ctx.config."""
        from autodoc.parser.tfs_client import TFSClient
        self._tfs = TFSClient.get_instance()
        self._base_url = ctx.config.tfs_dep_components_url.rstrip('/')
        self._manifests_remotes_path = ctx.config.manifests_remotes_path
        self._platform_branch_name = ctx.config.platform_branch_name
        self._platform_version = ctx.config.platform_version
        self._configured = True

    def fetch(self, tmp_dir: Path, excluded: list[str]) -> FetchResult[list[Component]]:
        """Типизированная точка входа — делегирует в _guarded_fetch."""
        return self._guarded_fetch(tmp_dir=tmp_dir, excluded=excluded)

    def _do_fetch(self, tmp_dir: Path, excluded: list[str]) -> FetchResult[list[Component]]:
        """
        Скачивает .properties-файлы из TFS, затем передаёт их ManifestParser.

        Raises:
            ParsingError: Если в директории не найдено ни одного .properties-файла.
        """
        tmp_dir.mkdir(parents=True, exist_ok=True)

        items_url = '%s/_apis/git/repositories/%s/items' % (self._base_url, _MANIFESTS_REPO)
        self._tfs.download_properties(
            items_url=items_url,
            remote_path=self._manifests_remotes_path,
            branch=self._platform_branch_name,
            output_dir=str(tmp_dir),
        )

        properties_files = list(tmp_dir.glob('*.properties'))
        if not properties_files:
            raise ParsingError(
                'ManifestFetcher: в директории %s не найдено .properties-файлов '
                'после скачивания из TFS.' % tmp_dir
            )

        parser = ManifestParser(target_platform=self._platform_version)
        components, warnings = parser.parse(properties_files, excluded)
        return FetchResult(value=components, warnings=warnings)

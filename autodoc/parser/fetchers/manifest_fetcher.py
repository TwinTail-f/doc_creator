"""
Фетчер манифестов компонентов: скачивание .properties-файлов из TFS.
Разбор в доменные модели делегируется ManifestParser.
"""

from pathlib import Path

from autodoc.exceptions import ParsingError
from autodoc.models.component import Component
from autodoc.parser.parsers.manifest_parser import ManifestParser
from autodoc.parser.fetchers.base_tfs_fetcher import BaseTFSFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.clients.tfs_client_enums import VersionType
from autodoc.parser.pipeline.context import PipelineContext

_MANIFESTS_REPO: str = "platform"
_MANIFESTS_PROJECT: str = "DEP_Components"


class ManifestFetcher(BaseTFSFetcher[list[Component]]):
    """
    Скачивает .properties-файлы манифестов из TFS и делегирует парсинг ManifestParser.

    Двухфазовый: сначала ``configure(ctx)``, потом ``fetch(tmp_dir, excluded)``.
    """

    def __init__(self) -> None:
        """Инициализирует фетчер; перед вызовом ``fetch()`` необходимо вызвать ``configure(ctx)``."""
        super().__init__()
        self._base_url: str = ""
        self._manifests_remotes_path: str = ""
        self._platform_branch_name: str = ""
        self._platform_version: str = ""
        self._platform_base_version: str = ""
        self._platform_ref_type: VersionType = VersionType.BRANCH

    def configure(self, ctx: PipelineContext) -> None:
        """
        Инициализирует фетчер из контекста пайплайна.

        Получает ``TFSClient`` из контекста и сохраняет параметры конфигурации.

        Args:
            ctx: Контекст пайплайна с заполненной конфигурацией и клиентами.
        """
        self._tfs = ctx.tfs_client
        self._base_url = ctx.config.tfs_collection_url.rstrip("/")
        self._manifests_remotes_path = ctx.config.manifests_remotes_path
        self._platform_branch_name = ctx.config.platform_branch_name
        self._platform_version = ctx.config.platform_version
        self._platform_base_version = ctx.config.platform_base_version
        self._platform_ref_type = VersionType(ctx.config.platform_ref_type)

    def fetch(self, tmp_dir: Path, excluded: list[str]) -> FetchResult[list[Component]]:
        """
        Скачивает .properties-файлы из TFS, затем передаёт их ManifestParser.

        Args:
            tmp_dir: Временная директория для сохранения скачанных файлов.
            excluded: Список имён компонентов, которые нужно исключить из парсинга.

        Returns:
            ``FetchResult`` со списком компонентов и предупреждениями.

        Raises:
            ParsingError: Если в директории не найдено ни одного .properties-файла.
        """
        tmp_dir.mkdir(parents=True, exist_ok=True)

        items_url = f"{self._base_url}/{_MANIFESTS_PROJECT}/_apis/git/repositories/{_MANIFESTS_REPO}/items"
        self._tfs.download_properties(
            items_url=items_url,
            remote_path=self._manifests_remotes_path,
            branch=self._platform_branch_name,
            output_dir=str(tmp_dir),
            version_type=self._platform_ref_type,
        )

        properties_files = list(tmp_dir.glob("*.properties"))
        if not properties_files:
            raise ParsingError(
                f"ManifestFetcher: в директории {tmp_dir} не найдено .properties-файлов "
                "после скачивания из TFS."
            )

        parser = ManifestParser(
            target_platform=self._platform_base_version,
            tfs_collection_url=self._base_url,
        )
        components, warnings = parser.parse(properties_files, excluded)
        return FetchResult(value=components, warnings=warnings)

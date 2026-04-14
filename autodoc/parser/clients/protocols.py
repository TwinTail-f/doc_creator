"""
Abstract interfaces (Protocols) for parser infrastructure dependencies.

Using ``typing.Protocol`` (structural subtyping) means neither ``TFSClient``
nor ``ArtifactoryClient`` requires any code change — they satisfy these
interfaces implicitly.

Pipeline steps and ``PipelineContext`` depend on these Protocols, not on
concrete infrastructure classes.
"""

from typing import Any, Protocol, runtime_checkable

import requests


@runtime_checkable
class IArtifactoryClient(Protocol):
    """
    Interface for checking artifact availability in Artifactory.

    Covers only the ``head()`` method used by ``ArtifactoryValidationStep``.
    ``ArtifactoryClient`` satisfies this interface structurally.
    """

    def head(self, url: str) -> requests.Response:
        """Perform an HTTP HEAD request and return the response."""
        ...


@runtime_checkable
class ITFSClient(Protocol):
    """
    Interface for reading files and directory listings from TFS.

    Covers the three public methods used by fetcher classes.
    ``TFSClient`` satisfies this interface structurally.
    """

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type: Any = None,
    ) -> None:
        """Download all ``.properties`` files from a TFS directory."""
        ...

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type: Any = None,
    ) -> requests.Response:
        """Retrieve a single file's content from TFS."""
        ...

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion: Any = None,
        version_type: Any = None,
    ) -> list[dict[str, Any]]:
        """Return a list of items (files and folders) from a TFS repository."""
        ...

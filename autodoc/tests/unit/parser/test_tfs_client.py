"""
Unit-тесты для TFSClient.

Покрывают:
- инициализацию и передачу параметров в сессию
- все публичные методы (download_properties, get_file_content, get_items)
- обработку сетевых ошибок

Все тесты используют моки — сетевых запросов нет.
"""

import pytest
import requests
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import ConfigError, NetworkError
from autodoc.parser.clients.tfs_client import RecursionLevel, TFSClient, VersionType

_TFS_SESSION_PATH = "autodoc.parser.clients.tfs_client.create_retryable_session"


# ---------------------------------------------------------------------------
# VersionType enum
# ---------------------------------------------------------------------------


class TestVersionType:
    """Тесты перечисления VersionType."""

    def test_branch_value(self) -> None:
        """VersionType.BRANCH имеет значение 'branch'."""
        assert VersionType.BRANCH.value == "branch"

    def test_tag_value(self) -> None:
        """VersionType.TAG имеет значение 'tag'."""
        assert VersionType.TAG.value == "tag"

    def test_commit_value(self) -> None:
        """VersionType.COMMIT имеет значение 'commit'."""
        assert VersionType.COMMIT.value == "commit"

    def test_construct_from_string(self) -> None:
        """VersionType конструируется из строки."""
        assert VersionType("tag") is VersionType.TAG
        assert VersionType("branch") is VersionType.BRANCH
        assert VersionType("commit") is VersionType.COMMIT

    def test_invalid_value_raises(self) -> None:
        """Неизвестное значение вызывает ValueError."""
        with pytest.raises(ValueError):
            VersionType("unknown")


# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------


def _make_mock_session() -> MagicMock:
    """Возвращает сконфигурированный mock сессии."""
    session = MagicMock()
    session.params = {}
    return session


# ---------------------------------------------------------------------------
# Инициализация
# ---------------------------------------------------------------------------


class TestTFSClientInit:
    """Тесты корректной инициализации TFSClient."""

    def test_session_created_with_correct_params(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """create_retryable_session вызывается с параметрами из конфига."""
        mock_session = _make_mock_session()
        with patch(_TFS_SESSION_PATH, return_value=mock_session) as mock_factory:
            TFSClient(minimal_config)

        mock_factory.assert_called_once_with(
            username=minimal_config.tfs_username or None,
            token=minimal_config.tfs_token,
            max_retries=minimal_config.max_retries,
            backoff_factor=minimal_config.retry_backoff_factor,
            timeout=minimal_config.tfs_request_timeout,
        )

    def test_api_version_set_in_session_params(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """После инициализации session.params содержит api-version."""
        mock_session = _make_mock_session()
        with patch(_TFS_SESSION_PATH, return_value=mock_session):
            client = TFSClient(minimal_config)

        assert client.session.params == {"api-version": "7.1"}

    def test_raises_config_error_if_no_token(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """ConfigError если tfs_token пустой."""
        bad = minimal_config.model_copy(update={"tfs_token": ""})
        with pytest.raises(ConfigError, match="tfs_token"):
            TFSClient(bad)

    def test_works_without_username(self, minimal_config: ParserConfigSchema) -> None:
        """TFSClient инициализируется без tfs_username — PAT-аутентификация."""
        mock_session = _make_mock_session()
        config_no_user = minimal_config.model_copy(update={"tfs_username": ""})
        with patch(_TFS_SESSION_PATH, return_value=mock_session):
            client = TFSClient(config_no_user)
        assert client is not None

    def test_each_call_creates_independent_instance(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """Каждый вызов TFSClient(config) возвращает новый независимый экземпляр."""
        with patch(_TFS_SESSION_PATH, return_value=_make_mock_session()):
            first = TFSClient(minimal_config)
            second = TFSClient(minimal_config)

        assert first is not second


# ---------------------------------------------------------------------------
# get_file_content
# ---------------------------------------------------------------------------


class TestGetFileContent:
    """Тесты метода TFSClient.get_file_content."""

    @pytest.fixture
    def client(self, minimal_config: ParserConfigSchema) -> TFSClient:
        with patch(_TFS_SESSION_PATH, return_value=_make_mock_session()):
            return TFSClient(minimal_config)

    def test_returns_response_object(self, client: TFSClient) -> None:
        """get_file_content возвращает объект ответа от session.get."""
        mock_response = MagicMock(spec=requests.Response)
        client.session.get.return_value = mock_response

        result = client.get_file_content(
            "https://tfs.example.com/items",
            "/path/to/file.yaml",
            "develop",
        )

        assert result is mock_response

    def test_passes_correct_params_to_session(self, client: TFSClient) -> None:
        """get_file_content передаёт path, branch и versionType в параметрах GET-запроса."""
        client.session.get.return_value = MagicMock(spec=requests.Response)

        client.get_file_content(
            "https://tfs.example.com/items",
            "/components/lib.yaml",
            "main",
        )

        client.session.get.assert_called_once_with(
            "https://tfs.example.com/items",
            params={
                "path": "/components/lib.yaml",
                "versionDescriptor.version": "main",
                "versionDescriptor.versionType": "branch",
            },
        )

    def test_default_version_type_is_branch(self, client: TFSClient) -> None:
        """По умолчанию versionDescriptor.versionType=branch."""
        client.session.get.return_value = MagicMock(spec=requests.Response)

        client.get_file_content("https://tfs.example.com/items", "/f.yaml", "develop")

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["versionDescriptor.versionType"] == "branch"

    def test_tag_version_type_sent_in_params(self, client: TFSClient) -> None:
        """При version_type=TAG передаётся versionDescriptor.versionType=tag."""
        client.session.get.return_value = MagicMock(spec=requests.Response)

        client.get_file_content(
            "https://tfs.example.com/items",
            "/f.yaml",
            "0",
            version_type=VersionType.TAG,
        )

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["versionDescriptor.versionType"] == "tag"
        assert kwargs["params"]["versionDescriptor.version"] == "0"

    def test_commit_version_type_sent_in_params(self, client: TFSClient) -> None:
        """При version_type=COMMIT передаётся versionDescriptor.versionType=commit."""
        client.session.get.return_value = MagicMock(spec=requests.Response)
        sha = "a" * 40

        client.get_file_content(
            "https://tfs.example.com/items",
            "/f.yaml",
            sha,
            version_type=VersionType.COMMIT,
        )

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["versionDescriptor.versionType"] == "commit"

    def test_raises_network_error_on_request_exception(self, client: TFSClient) -> None:
        """NetworkError возникает при requests.RequestException."""
        client.session.get.side_effect = requests.exceptions.ConnectionError(
            "conn refused"
        )

        with pytest.raises(NetworkError, match="Ошибка запроса файла"):
            client.get_file_content(
                "https://tfs.example.com/items", "/file.yaml", "develop"
            )


# ---------------------------------------------------------------------------
# get_items
# ---------------------------------------------------------------------------


class TestGetItems:
    """Тесты метода TFSClient.get_items."""

    @pytest.fixture
    def client(self, minimal_config: ParserConfigSchema) -> TFSClient:
        with patch(_TFS_SESSION_PATH, return_value=_make_mock_session()):
            return TFSClient(minimal_config)

    def _mock_response(self, items: list) -> MagicMock:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {"value": items}
        return resp

    def test_returns_list_of_items(self, client: TFSClient) -> None:
        """get_items возвращает список из поля 'value' ответа."""
        expected = [{"path": "/a.yaml"}, {"path": "/b.yaml"}]
        client.session.get.return_value = self._mock_response(expected)

        result = client.get_items("https://tfs.example.com/items", "develop")

        assert result == expected

    def test_default_recursion_is_full(self, client: TFSClient) -> None:
        """По умолчанию recursionLevel=Full."""
        client.session.get.return_value = self._mock_response([])

        client.get_items("https://tfs.example.com/items", "main")

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["recursionLevel"] == "Full"

    def test_default_version_type_is_branch(self, client: TFSClient) -> None:
        """По умолчанию versionDescriptor.versionType=branch."""
        client.session.get.return_value = self._mock_response([])

        client.get_items("https://tfs.example.com/items", "develop")

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["versionDescriptor.versionType"] == "branch"

    def test_tag_version_type_sent_in_params(self, client: TFSClient) -> None:
        """При version_type=TAG передаётся versionDescriptor.versionType=tag."""
        client.session.get.return_value = self._mock_response([])

        client.get_items(
            "https://tfs.example.com/items",
            "0",
            version_type=VersionType.TAG,
        )

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["versionDescriptor.versionType"] == "tag"
        assert kwargs["params"]["versionDescriptor.version"] == "0"

    def test_custom_recursion_level_passed(self, client: TFSClient) -> None:
        """Кастомный уровень рекурсии передаётся в запрос."""
        client.session.get.return_value = self._mock_response([])

        client.get_items(
            "https://tfs.example.com/items",
            "develop",
            recursion=RecursionLevel.ONE_LEVEL,
        )

        _, kwargs = client.session.get.call_args
        assert kwargs["params"]["recursionLevel"] == "OneLevel"

    def test_raises_network_error_on_request_exception(self, client: TFSClient) -> None:
        """NetworkError возникает при requests.RequestException."""
        client.session.get.side_effect = requests.exceptions.Timeout("timed out")

        with pytest.raises(NetworkError, match="Ошибка запроса структуры репозитория"):
            client.get_items("https://tfs.example.com/items", "develop")

    def test_returns_empty_list_when_value_missing(self, client: TFSClient) -> None:
        """Возвращает пустой список если 'value' отсутствует в ответе."""
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {}
        client.session.get.return_value = resp

        result = client.get_items("https://tfs.example.com/items", "develop")

        assert result == []


# ---------------------------------------------------------------------------
# download_properties
# ---------------------------------------------------------------------------


class TestDownloadProperties:
    """Тесты метода TFSClient.download_properties."""

    @pytest.fixture
    def client(self, minimal_config: ParserConfigSchema) -> TFSClient:
        with patch(_TFS_SESSION_PATH, return_value=_make_mock_session()):
            return TFSClient(minimal_config)

    def _items_response(self, items: list) -> MagicMock:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {"value": items}
        return resp

    def test_downloads_properties_files_to_directory(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """Скачивает .properties файлы и сохраняет их в output_dir."""
        list_resp = self._items_response(
            [
                {"path": "/remotes/comp.properties", "isFolder": False},
            ]
        )
        file_resp = MagicMock(spec=requests.Response)
        file_resp.text = "key=value\n"
        client.session.get.side_effect = [list_resp, file_resp]

        client.download_properties(
            "https://tfs.example.com/items",
            "/remotes",
            "develop",
            str(tmp_path),
        )

        written = tmp_path / "comp.properties"
        assert written.exists()
        assert written.read_text() == "key=value\n"

    def test_skips_non_properties_files(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """Файлы без расширения .properties пропускаются."""
        list_resp = self._items_response(
            [
                {"path": "/remotes/readme.md", "isFolder": False},
                {"path": "/remotes/comp.properties", "isFolder": False},
            ]
        )
        file_resp = MagicMock(spec=requests.Response)
        file_resp.text = "x=1\n"
        client.session.get.side_effect = [list_resp, file_resp]

        client.download_properties(
            "https://tfs.example.com/items", "/remotes", "develop", str(tmp_path)
        )

        assert len(list(tmp_path.glob("*.properties"))) == 1
        assert not (tmp_path / "readme.md").exists()

    def test_skips_folders(self, client: TFSClient, tmp_path: Path) -> None:
        """Элементы с isFolder=True пропускаются."""
        list_resp = self._items_response(
            [
                {"path": "/remotes/subdir", "isFolder": True},
                {"path": "/remotes/a.properties", "isFolder": False},
            ]
        )
        file_resp = MagicMock(spec=requests.Response)
        file_resp.text = "a=1\n"
        client.session.get.side_effect = [list_resp, file_resp]

        client.download_properties(
            "https://tfs.example.com/items", "/remotes", "develop", str(tmp_path)
        )

        assert len(list(tmp_path.iterdir())) == 1

    def test_raises_network_error_on_list_failure(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """NetworkError если не удалось получить список файлов."""
        client.session.get.side_effect = requests.exceptions.ConnectionError("down")

        with pytest.raises(NetworkError, match="Ошибка при получении списка файлов"):
            client.download_properties(
                "https://tfs.example.com/items", "/remotes", "develop", str(tmp_path)
            )

    def test_continues_on_single_file_download_failure(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """Если скачивание одного файла упало — остальные файлы всё равно скачиваются."""
        list_resp = self._items_response(
            [
                {"path": "/remotes/a.properties", "isFolder": False},
                {"path": "/remotes/b.properties", "isFolder": False},
            ]
        )
        ok_resp = MagicMock(spec=requests.Response)
        ok_resp.text = "b=2\n"
        client.session.get.side_effect = [
            list_resp,
            requests.exceptions.Timeout("timeout"),
            ok_resp,
        ]

        client.download_properties(
            "https://tfs.example.com/items", "/remotes", "develop", str(tmp_path)
        )

        assert (tmp_path / "b.properties").exists()
        assert not (tmp_path / "a.properties").exists()

    def test_passes_scope_path_and_branch_in_list_request(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """Запрос списка файлов содержит scopePath, ветку, versionType и recursionLevel."""
        list_resp = self._items_response([])
        client.session.get.return_value = list_resp

        client.download_properties(
            "https://tfs.example.com/items",
            "/components/remotes",
            "feature/xyz",
            str(tmp_path),
        )

        client.session.get.assert_called_once()
        _, kwargs = client.session.get.call_args
        params = kwargs["params"]
        assert params["scopePath"] == "/components/remotes"
        assert params["versionDescriptor.version"] == "feature/xyz"
        assert params["versionDescriptor.versionType"] == "branch"
        assert params["recursionLevel"] == "OneLevel"

    def test_tag_version_type_sent_in_list_request(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """При version_type=TAG список файлов запрашивается с versionType=tag."""
        client.session.get.return_value = self._items_response([])

        client.download_properties(
            "https://tfs.example.com/items",
            "/remotes",
            "0",
            str(tmp_path),
            version_type=VersionType.TAG,
        )

        _, kwargs = client.session.get.call_args
        params = kwargs["params"]
        assert params["versionDescriptor.versionType"] == "tag"
        assert params["versionDescriptor.version"] == "0"

    def test_tag_version_type_forwarded_to_file_download(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """version_type=TAG прокидывается в запрос каждого отдельного файла."""
        list_resp = self._items_response(
            [{"path": "/remotes/comp.properties", "isFolder": False}]
        )
        file_resp = MagicMock(spec=requests.Response)
        file_resp.text = "k=v\n"
        client.session.get.side_effect = [list_resp, file_resp]

        client.download_properties(
            "https://tfs.example.com/items",
            "/remotes",
            "0",
            str(tmp_path),
            version_type=VersionType.TAG,
        )

        # Second call is the individual file download
        file_call_kwargs = client.session.get.call_args_list[1][1]
        assert file_call_kwargs["params"]["versionDescriptor.versionType"] == "tag"
        assert file_call_kwargs["params"]["versionDescriptor.version"] == "0"

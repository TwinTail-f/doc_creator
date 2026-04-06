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
from autodoc.parser.clients.tfs_client import RecursionLevel, TFSClient

_TFS_SESSION_PATH = "autodoc.parser.clients.tfs_client.create_retryable_session"


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

    def test_session_created_with_correct_params(self, minimal_config: ParserConfigSchema) -> None:
        """create_retryable_session вызывается с параметрами из конфига."""
        mock_session = _make_mock_session()
        with patch(_TFS_SESSION_PATH, return_value=mock_session) as mock_factory:
            TFSClient(minimal_config)

        mock_factory.assert_called_once_with(
            username=minimal_config.tfs_username,
            token=minimal_config.tfs_token,
            max_retries=minimal_config.max_retries,
            backoff_factor=minimal_config.retry_backoff_factor,
            timeout=minimal_config.tfs_request_timeout,
        )

    def test_api_version_set_in_session_params(self, minimal_config: ParserConfigSchema) -> None:
        """После инициализации session.params содержит api-version."""
        mock_session = _make_mock_session()
        with patch(_TFS_SESSION_PATH, return_value=mock_session):
            client = TFSClient(minimal_config)

        assert client.session.params == {"api-version": "7.1"}

    def test_raises_config_error_if_no_username(self, minimal_config: ParserConfigSchema) -> None:
        """ConfigError если tfs_username пустой."""
        bad = minimal_config.model_copy(update={"tfs_username": ""})
        with pytest.raises(ConfigError, match="учётные данные не переданы"):
            TFSClient(bad)

    def test_raises_config_error_if_no_token(self, minimal_config: ParserConfigSchema) -> None:
        """ConfigError если tfs_token пустой."""
        bad = minimal_config.model_copy(update={"tfs_token": ""})
        with pytest.raises(ConfigError, match="учётные данные не переданы"):
            TFSClient(bad)

    def test_raises_config_error_if_both_credentials_missing(
        self, minimal_config: ParserConfigSchema
    ) -> None:
        """ConfigError если оба поля аутентификации пустые."""
        bad = minimal_config.model_copy(update={"tfs_username": "", "tfs_token": ""})
        with pytest.raises(ConfigError):
            TFSClient(bad)

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
        """get_file_content передаёт path и branch в параметрах GET-запроса."""
        client.session.get.return_value = MagicMock(spec=requests.Response)

        client.get_file_content(
            "https://tfs.example.com/items",
            "/components/lib.yaml",
            "main",
        )

        client.session.get.assert_called_once_with(
            "https://tfs.example.com/items",
            params={"path": "/components/lib.yaml", "versionDescriptor.version": "main"},
        )

    def test_raises_network_error_on_request_exception(self, client: TFSClient) -> None:
        """NetworkError возникает при requests.RequestException."""
        client.session.get.side_effect = requests.exceptions.ConnectionError("conn refused")

        with pytest.raises(NetworkError, match="ошибка запроса файла"):
            client.get_file_content("https://tfs.example.com/items", "/file.yaml", "develop")


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

        with pytest.raises(NetworkError, match="ошибка запроса структуры репозитория"):
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
        list_resp = self._items_response([
            {"path": "/remotes/comp.properties", "isFolder": False},
        ])
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
        list_resp = self._items_response([
            {"path": "/remotes/readme.md", "isFolder": False},
            {"path": "/remotes/comp.properties", "isFolder": False},
        ])
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
        list_resp = self._items_response([
            {"path": "/remotes/subdir", "isFolder": True},
            {"path": "/remotes/a.properties", "isFolder": False},
        ])
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

        with pytest.raises(NetworkError, match="ошибка при получении списка файлов"):
            client.download_properties(
                "https://tfs.example.com/items", "/remotes", "develop", str(tmp_path)
            )

    def test_continues_on_single_file_download_failure(
        self, client: TFSClient, tmp_path: Path
    ) -> None:
        """Если скачивание одного файла упало — остальные файлы всё равно скачиваются."""
        list_resp = self._items_response([
            {"path": "/remotes/a.properties", "isFolder": False},
            {"path": "/remotes/b.properties", "isFolder": False},
        ])
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
        """Запрос списка файлов содержит scopePath, ветку и recursionLevel."""
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
        assert params["recursionLevel"] == "OneLevel"

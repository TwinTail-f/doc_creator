"""Юнит-тесты для классов Conan runner.

Охватывает: Conan2Runner, ConanEnvironmentManager, BaseConanRunner.
Все вызовы subprocess.run и shutil замокированы — бинарный файл conan не требуется.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.base_conan_runner import BaseConanRunner
from autodoc.parser.conan.conan2_runner import Conan2Runner
from autodoc.parser.conan.conan_environment_manager import ConanEnvironmentManager
from autodoc.parser.conan.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.models.conan_task import ConanTask

_PACKAGE_REF: str = "zlib/1.2.13"
_TIMEOUT_SEC: int = 30
_CONFIG_URL: str = "https://art.example.com/conan-config.zip"
_USERNAME: str = "testuser"
_PASSWORD: str = "test-pat-token"


def _make_task() -> ConanTask:
    """
    Создаёт минимальный ConanTask для тестов runner.

    Returns:
        Готовая к использованию задача ConanTask для zlib/1.2.13.
    """
    release = Release(
        version="1.2.13",
        platform="2.0",
        channel="fast",
        profile_builds=[],
    )
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return ConanTask(
        cmd=["conan", "graph", "info", "--format=json", "zlib/1.2.13@"],
        comp_name="zlib",
        version="1.2.13",
        channel="fast",
        profile_name="hw-linux-x86_64-gcc10_2",
        option_id="default",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


def _make_runner(tmp_path: Path) -> Conan2Runner:
    """
    Создаёт Conan2Runner, используя tmp_path как каталог-шаблон.

    Args:
        tmp_path: Временная директория, используемая как conan_home_template.

    Returns:
        Готовый к использованию экземпляр Conan2Runner.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    return Conan2Runner(timeout=_TIMEOUT_SEC, conan_home_template=tmp_path)


@pytest.mark.infrastructure
def test_conan2_runner_raises_on_missing_conan_binary(tmp_path: Path) -> None:
    """Conan2Runner.run() возвращает success=False, когда 'conan' отсутствует в PATH.

    Runner не должен пробрасывать FileNotFoundError — он использует shutil.which
    перед subprocess.run и возвращает результат-ошибку с диагностическим сообщением.
    """
    runner = _make_runner(tmp_path)
    with patch("shutil.which", return_value=None):
        result: ConanRawResult = runner.run(_make_task())
    assert result.success is False
    assert result.error  # сообщение об ошибке непустое


@pytest.mark.infrastructure
def test_conan2_runner_returns_failure_on_timeout(tmp_path: Path) -> None:
    """Conan2Runner.run() возвращает success=False при истечении времени ожидания subprocess.

    TimeoutExpired не должен пробрасываться — runner перехватывает его и возвращает
    результат-ошибку, чтобы вызывающий код мог накапливать ошибки вместо падения.
    """
    runner = _make_runner(tmp_path)
    with (
        patch("shutil.which", return_value="/usr/bin/conan"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="conan", timeout=_TIMEOUT_SEC),
        ),
    ):
        result: ConanRawResult = runner.run(_make_task())
    assert result.success is False
    assert result.error  # сообщение об ошибке непустое


@pytest.mark.infrastructure
def test_conan2_runner_clean_cache_success(tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
    """clean_cache() не бросает исключений при успешном завершении и использует шаблонный CONAN_HOME напрямую."""
    runner = _make_runner(tmp_path)
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="", stdout=""))

    runner.clean_cache()

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == Conan2Runner._CLEAN_CACHE_CMD
    # clean_cache() использует сам шаблонный каталог, а не свежую временную копию
    # (в отличие от run(), который всегда копирует во временный каталог).
    assert kwargs["env"]["CONAN_HOME"] == str(tmp_path)


@pytest.mark.infrastructure
def test_conan2_runner_clean_cache_non_critical_failure(tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
    """clean_cache() не бросает исключений, если conan вернул ненулевой код (некритичная ошибка)."""
    runner = _make_runner(tmp_path)
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stderr="cache empty", stdout=""),
    )

    # Не должно бросать исключение
    runner.clean_cache()


@pytest.mark.infrastructure
def test_conan2_runner_clean_cache_timeout(tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
    """clean_cache() не бросает исключений при истечении времени ожидания subprocess."""
    runner = _make_runner(tmp_path)
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="conan", timeout=Conan2Runner._CLEAN_CACHE_TIMEOUT),
    )

    # Не должно бросать исключение
    runner.clean_cache()


@pytest.mark.infrastructure
def test_conan2_runner_run_non_json_stdout_returns_failure_with_preview(
    tmp_path: Path, mocker
) -> None:  # type: ignore[no-untyped-def]
    """run() при не-JSON stdout возвращает success=False с сообщением, включающим превью исходного stdout."""
    runner = _make_runner(tmp_path)
    fake_stdout = "<warning>not actually json this time</warning>"
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout=fake_stdout, stderr=""),
    )

    result: ConanRawResult = runner.run(_make_task())

    assert result.success is False
    assert result.data is None
    assert "JSON" in result.error
    assert fake_stdout in result.error


@pytest.mark.infrastructure
def test_conan2_runner_run_nonzero_returncode_delegates_to_extract_error_message(
    tmp_path: Path, mocker
) -> None:  # type: ignore[no-untyped-def]
    """run() при ненулевом returncode передаёт stderr в _extract_error_message и возвращает его результат."""
    runner = _make_runner(tmp_path)
    stderr = "some INFO preamble\nERROR: something broke"
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr=stderr),
    )

    result: ConanRawResult = runner.run(_make_task())

    assert result.success is False
    assert "ERROR: something broke" in result.error
    assert "some INFO preamble" not in result.error


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_copies_config(mocker) -> None:  # type: ignore[no-untyped-def]
    """Успешный setup() выполняет установку конфигурации Conan через 'conan config install'.

    Ранее тест ошибочно описывался как проверка вызова shutil.copytree —
    копирование через shutil.copytree на самом деле происходит внутри
    Conan2Runner.run(), а не в ConanEnvironmentManager.setup(). Здесь
    проверяется реальное поведение setup(): установка конфигурации через CLI-команду
    'conan config install' (в дополнение к последующему логину в remotes).
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch("tempfile.mkdtemp", return_value="/tmp/conan_setup_test")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="[]")

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    manager.setup()

    install_calls = [
        call for call in mock_run.call_args_list if call.args[0][:3] == ["conan", "config", "install"]
    ]
    assert len(install_calls) == 1


@pytest.mark.infrastructure
def test_conan_environment_manager_cleanup_removes_directory(
    tmp_path: Path, mocker
) -> None:  # type: ignore[no-untyped-def]
    """cleanup() удаляет каталог настройки, созданный setup().

    Гарантирует, что временный домашний каталог Conan удаляется после использования,
    что важно для предотвращения накопления больших каталогов на агентах CI.
    """
    mock_which = mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="[]")
    setup_dir: Path = tmp_path / "conan_setup_fake"
    setup_dir.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=str(setup_dir))
    mock_rmtree = mocker.patch("shutil.rmtree")

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    manager.setup()
    manager.cleanup()

    mock_rmtree.assert_called_once()
    called_path = Path(mock_rmtree.call_args[0][0])
    assert called_path == setup_dir


@pytest.mark.infrastructure
def test_conan_environment_manager_cleanup_safe_if_setup_never_called() -> None:
    """cleanup() идемпотентен и не вызывает исключений, если setup() никогда не вызывался.

    Свежий ConanEnvironmentManager не имеет каталога настройки; cleanup() должен
    обрабатывать это корректно, чтобы вызывающий код мог использовать его безопасно
    в блоках finally без дополнительных проверок.
    """
    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    # Не должно бросать исключение
    manager.cleanup()


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_is_idempotent_on_double_call(tmp_path: Path, mocker) -> None:
    """Повторный вызов setup() на одном и том же ConanEnvironmentManager завершается без ошибок.

    ConanEnvironmentManager не вызывает исключение при повторном setup — он просто
    перезаписывает _setup_dir новым временным каталогом. Этот тест документирует
    данное поведение, чтобы любое будущее изменение, добавляющее исключение при
    повторном вызове setup, было сразу заметно.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="[]")

    first_dir: Path = tmp_path / "first"
    second_dir: Path = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    # mkdtemp возвращает разные пути при последовательных вызовах
    mocker.patch(
        "tempfile.mkdtemp",
        side_effect=[str(first_dir), str(second_dir)],
    )

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    # Оба вызова должны завершиться без исключений
    manager.setup()
    manager.setup()
    # После второго setup() _setup_dir указывает на второй каталог
    assert manager._setup_dir == second_dir


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_raises_when_remote_list_fails(tmp_path: Path, mocker) -> None:
    """Если получение списка remotes завершилось ошибкой, setup() пробрасывает исключение и выполняет очистку.

    Установка конфигурации к этому моменту уже прошла успешно, поэтому setup()
    обязан удалить созданный временный каталог перед тем, как пробросить ошибку,
    чтобы не оставлять после себя недоиспользуемые директории на агентах CI.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    setup_dir: Path = tmp_path / "setup_dir"
    setup_dir.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=str(setup_dir))
    mock_rmtree = mocker.patch("shutil.rmtree")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            MagicMock(returncode=0, stdout="", stderr=""),  # установка конфигурации conan
            MagicMock(returncode=1, stdout="", stderr="remote list failed"),  # список remotes
        ],
    )

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)

    with pytest.raises(RuntimeError):
        manager.setup()

    mock_rmtree.assert_called_once()


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_raises_when_remote_login_fails(tmp_path: Path, mocker) -> None:
    """Если логин в один из remotes завершился ошибкой, setup() пробрасывает исключение и выполняет очистку.

    Установка конфигурации и получение списка remotes к этому моменту уже прошли
    успешно, поэтому setup() обязан удалить созданный временный каталог перед тем,
    как пробросить ошибку, чтобы не оставлять после себя недоиспользуемые
    директории на агентах CI.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    setup_dir: Path = tmp_path / "setup_dir"
    setup_dir.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=str(setup_dir))
    mock_rmtree = mocker.patch("shutil.rmtree")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            MagicMock(returncode=0, stdout="", stderr=""),  # установка конфигурации conan
            MagicMock(returncode=0, stdout='[{"name": "art-remote"}]', stderr=""),  # список remotes
            MagicMock(returncode=1, stdout="", stderr="login failed"),  # логин в remote
        ],
    )

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)

    with pytest.raises(RuntimeError):
        manager.setup()

    mock_rmtree.assert_called_once()


@pytest.mark.business_logic
def test_conan_environment_manager_install_config_raises_on_invalid_url(mocker) -> None:
    """setup() отклоняет config_url без схемы и хоста ещё до обращения к conan CLI.

    URL конфигурации всегда должен содержать схему и хост, поскольку в него
    встраиваются учётные данные для скачивания архива из Artifactory; заведомо
    некорректный URL не должен приводить к неявному сбою внутри conan CLI.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_run = mocker.patch("subprocess.run")

    manager = ConanEnvironmentManager("not-a-valid-url", _USERNAME, _PASSWORD)

    with pytest.raises(RuntimeError, match="config_url"):
        manager.setup()

    mock_run.assert_not_called()

"""Юнит-тесты для классов Conan runner.

Охватывает: Conan2Runner, ConanEnvironmentManager.
"""

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.conan2_runner import Conan2Runner
from autodoc.parser.conan.conan_environment_manager import ConanEnvironmentManager
from autodoc.parser.conan.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.models.conan_task import ConanTask

_TIMEOUT_SEC: int = 30
_CONFIG_URL: str = "https://art.example.com/conan-config.zip"
_USERNAME: str = "testuser"
_PASSWORD: str = "test-pat-token"


@pytest.fixture
def conan_task() -> ConanTask:
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


@pytest.fixture
def conan2_runner(tmp_path: Path) -> Conan2Runner:
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
def test_conan2_runner_returns_failure_on_timeout(
    conan2_runner: Conan2Runner,
    conan_task: ConanTask,
    mocker: MockerFixture,
) -> None:
    """Conan2Runner.run() возвращает success=False при истечении времени ожидания subprocess.

    TimeoutExpired не должен пробрасываться — runner перехватывает его и возвращает
    результат-ошибку, чтобы вызывающий код мог накапливать ошибки вместо падения.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="conan", timeout=_TIMEOUT_SEC),
    )

    result: ConanRawResult = conan2_runner.run(conan_task)

    assert result.success is False
    assert result.error  # сообщение об ошибке непустое


@pytest.mark.infrastructure
def test_conan2_runner_clean_cache_success(
    conan2_runner: Conan2Runner,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """clean_cache() не бросает исключений при успешном завершении и использует шаблонный CONAN_HOME напрямую."""
    mock_run = mocker.patch(
        "subprocess.run", return_value=MagicMock(returncode=0, stderr="", stdout="")
    )

    conan2_runner.clean_cache()

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["conan", "remove", "*", "-c"]
    # clean_cache() использует сам шаблонный каталог, а не свежую временную копию
    # (в отличие от run(), который всегда копирует во временный каталог).
    assert kwargs["env"]["CONAN_HOME"] == str(tmp_path)


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "run_kwargs",
    [
        # conan вернул ненулевой код возврата (некритичная ошибка)
        pytest.param(
            {"return_value": MagicMock(returncode=1, stderr="cache empty", stdout="")},
            id="non-critical-failure",
        ),
        # subprocess.run истёк по таймауту
        pytest.param(
            {
                "side_effect": subprocess.TimeoutExpired(
                    cmd="conan", timeout=Conan2Runner._CLEAN_CACHE_TIMEOUT
                )
            },
            id="timeout",
        ),
    ],
)
def test_conan2_runner_clean_cache_swallows_failures(
    conan2_runner: Conan2Runner,
    mocker: MockerFixture,
    run_kwargs: dict,
) -> None:
    """clean_cache() не бросает исключений ни при ненулевом коде возврата
    conan, ни при истечении времени ожидания subprocess."""
    mocker.patch("subprocess.run", **run_kwargs)

    conan2_runner.clean_cache()


@pytest.mark.infrastructure
def test_conan2_runner_run_valid_json_returns_success_with_parsed_data(
    conan2_runner: Conan2Runner,
    conan_task: ConanTask,
    mocker: MockerFixture,
) -> None:
    """run() при returncode=0 и валидном JSON на stdout возвращает
    ConanRawResult(success=True, data=<разобранный JSON>) — это самый частый
    в проде путь (returncode=0)."""
    parsed_payload = {"graph": {"nodes": {"0": {"name": "zlib"}}}}
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout=json.dumps(parsed_payload), stderr=""),
    )

    result: ConanRawResult = conan2_runner.run(conan_task)

    assert result.success is True
    assert result.data == parsed_payload
    assert result.error == ""


@pytest.mark.infrastructure
def test_conan2_runner_run_non_json_stdout_returns_failure_with_preview(
    conan2_runner: Conan2Runner,
    conan_task: ConanTask,
    mocker: MockerFixture,
) -> None:
    """run() при не-JSON stdout возвращает success=False с сообщением, включающим превью исходного stdout."""
    fake_stdout = "<warning>not actually json this time</warning>"
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout=fake_stdout, stderr=""),
    )

    result: ConanRawResult = conan2_runner.run(conan_task)

    assert result.success is False
    assert result.data is None
    assert "JSON" in result.error
    assert fake_stdout in result.error


@pytest.mark.infrastructure
def test_conan2_runner_run_nonzero_returncode_delegates_to_extract_error_message(
    conan2_runner: Conan2Runner,
    conan_task: ConanTask,
    mocker: MockerFixture,
) -> None:
    """run() при ненулевом returncode передаёт stderr в _extract_error_message и
    возвращает его результат: _extract_error_message обрезает stderr до
    среза, начинающегося с первого вхождения маркера "error:" (регистронезависимо),
    отбрасывая предшествующий preamble-вывод."""
    stderr = "some INFO preamble\nERROR: something broke"
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr=stderr),
    )

    result: ConanRawResult = conan2_runner.run(conan_task)

    assert result.success is False
    assert "ERROR: something broke" in result.error
    assert "some INFO preamble" not in result.error


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_copies_config(mocker: MockerFixture) -> None:
    """Успешный setup() выполняет установку конфигурации Conan через 'conan config install'.
    Здесь проверяется реальное поведение setup(): установка конфигурации через CLI-команду
    'conan config install' (в дополнение к последующему логину в remotes).
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mocker.patch("tempfile.mkdtemp", return_value="/tmp/conan_setup_test")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="[]")

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    manager.setup()

    install_calls = [
        call
        for call in mock_run.call_args_list
        if call.args[0][:3] == ["conan", "config", "install"]
    ]
    assert len(install_calls) == 1


@pytest.mark.infrastructure
def test_conan_environment_manager_cleanup_removes_directory(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """cleanup() удаляет каталог настройки, созданный setup().

    Проверяет, что временный домашний каталог Conan удаляется после использования,
    что важно для предотвращения накопления больших каталогов на агентах CI.
    """
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
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
    в блоках finally без дополнительных проверок. Идемпотентность здесь проверяется
    буквально — двумя подряд вызовами: одного вызова недостаточно, чтобы отличить
    "безопасно один раз" от "безопасно повторно".
    """
    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    # Не должно бросать исключение — ни при первом, ни при повторном вызове
    manager.cleanup()
    manager.cleanup()


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_can_be_called_twice_without_raising(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Повторный вызов setup() на одном и том же ConanEnvironmentManager не бросает исключение.

    Это НЕ идемпотентность в строгом смысле (f(f(x)) == f(x)): второй вызов
    создаёт совершенно новый временный каталог и возвращает его путь, а
    старый каталог (first_dir) при этом остаётся на диске — менеджер теряет
    на него ссылку, ничего не удаляя. Тест сознательно проверяет и фиксирует
    именно это (см. assert first_dir.exists() ниже) — что реального
    повторного использования/чистки тут нет, только отсутствие исключения.
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
    second_home = manager.setup()
    # После второго setup() возвращённый путь указывает на второй каталог
    assert second_home == second_dir
    # А первый каталог никуда не делся — это утечка, а не идемпотентность.
    # Если это поведение когда-нибудь исправят (например, setup() станет
    # сначала звать self.cleanup()), этот assert упадёт и тест придётся
    # обновить осознанно, а не молча.
    assert first_dir.exists()


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_raises_when_remote_list_fails(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Если получение списка remotes завершилось ошибкой, setup() пробрасывает исключение и выполняет очистку.

    Установка конфигурации к этому моменту уже прошла успешно, поэтому setup()
    обязан удалить созданный временный каталог перед тем, как пробросить ошибку.
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
def test_conan_environment_manager_setup_raises_when_remote_login_fails(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Если логин в один из remotes завершился ошибкой, setup() пробрасывает исключение и выполняет очистку.

    Установка конфигурации и получение списка remotes к этому моменту уже прошли
    успешно, поэтому setup() обязан удалить созданный временный каталог перед тем,
    как пробросить ошибку.
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


@pytest.mark.infrastructure
def test_conan_environment_manager_install_config_raises_on_invalid_url(
    mocker: MockerFixture,
) -> None:
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


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_raises_when_conan_not_in_path(
    mocker: MockerFixture,
) -> None:
    """setup() пробрасывает RuntimeError, если утилита 'conan' не найдена в PATH,
    и не пытается создавать временную директорию или обращаться к conan CLI."""
    mocker.patch("shutil.which", return_value=None)
    mock_mkdtemp = mocker.patch("tempfile.mkdtemp")
    mock_run = mocker.patch("subprocess.run")

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)

    with pytest.raises(RuntimeError, match="PATH"):
        manager.setup()

    mock_mkdtemp.assert_not_called()
    mock_run.assert_not_called()


@pytest.mark.infrastructure
def test_conan_environment_manager_install_config_cleans_up_before_raising_on_subprocess_failure(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Если сама команда 'conan config install' завершилась ненулевым кодом,
    _install_config вызывает self.cleanup() (удаляет временный CONAN_HOME) перед
    тем, как пробросить RuntimeError — иначе временная директория осталась бы
    на диске навсегда, так как вызывающий код (setup()) выполнить cleanup()
    в этом случае уже не успевает."""
    mocker.patch("shutil.which", return_value="/usr/bin/conan")
    setup_dir: Path = tmp_path / "setup_dir"
    setup_dir.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=str(setup_dir))
    mock_rmtree = mocker.patch("shutil.rmtree")
    mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="config install failed"),
    )

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)

    with pytest.raises(RuntimeError, match="conan config install"):
        manager.setup()

    mock_rmtree.assert_called_once()
    called_path = Path(mock_rmtree.call_args[0][0])
    assert called_path == setup_dir


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "stderr, expected",
    [
        pytest.param(
            "warning: deprecated option used\nnothing critical here",
            "warning: deprecated option used\nnothing critical here",
            id="no-error-marker-returns-stripped-stderr",
        ),
        pytest.param(
            "INFO: preamble\nERROR: something broke",
            "ERROR: something broke",
            id="error-marker-present-returns-suffix",
        ),
    ],
)
def test_extract_error_message(stderr: str, expected: str, tmp_path: Path) -> None:
    """_extract_error_message возвращает срез stderr с маркера 'error:',
    либо весь stderr (обрезанный), если маркера нет."""
    runner = Conan2Runner(timeout=_TIMEOUT_SEC, conan_home_template=tmp_path)
    assert runner._extract_error_message(stderr) == expected

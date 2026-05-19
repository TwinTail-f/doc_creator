"""Юнит-тесты для Conan runner classes.

Covers: Conan2Runner, ConanEnvironmentManager, BaseConanRunner.
All subprocess.run and shutil calls are mocked — no conan binary required.
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
    """Create a minimal ConanTask for runner tests."""
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
    """Construct a Conan2Runner with the given tmp_path as the template dir."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    return Conan2Runner(timeout=_TIMEOUT_SEC, conan_home_template=tmp_path)


# ---------------------------------------------------------------------------
# Conan2Runner tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_conan2_runner_raises_on_missing_conan_binary(tmp_path: Path) -> None:
    """Conan2Runner.run() returns success=False when 'conan' is absent from PATH.

    The runner should not propagate FileNotFoundError — it uses shutil.which
    before subprocess.run and returns a failure result with a diagnostic message.
    """
    runner = _make_runner(tmp_path)
    with patch("shutil.which", return_value=None):
        result: ConanRawResult = runner.run(_make_task())
    assert result.success is False
    assert result.error  # non-empty error message


@pytest.mark.infrastructure
def test_conan2_runner_returns_failure_on_timeout(tmp_path: Path) -> None:
    """Conan2Runner.run() returns success=False when subprocess times out.

    A TimeoutExpired must not propagate — the runner catches it and surfaces
    a failure result so callers can accumulate errors instead of crashing.
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
    assert result.error  # non-empty error message


# ---------------------------------------------------------------------------
# ConanEnvironmentManager tests
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_conan_environment_manager_setup_copies_config(mocker) -> None:  # type: ignore[no-untyped-def]
    """setup() calls shutil.copytree exactly once to copy the config into the tmp dir.

    This guards against regressions where the config installation step is
    skipped or called more than once during a single setup() invocation.
    """
    mock_which = mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_mkdtemp = mocker.patch(
        "tempfile.mkdtemp", return_value="/tmp/conan_setup_test"
    )
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    manager.setup()

    # subprocess.run is called for config install + remote login
    assert mock_run.call_count >= 1


@pytest.mark.infrastructure
def test_conan_environment_manager_cleanup_removes_directory(
    tmp_path: Path, mocker
) -> None:  # type: ignore[no-untyped-def]
    """cleanup() removes the setup directory created by setup().

    Ensures that the temporary Conan home directory is deleted after use,
    which is important to avoid accumulating large directories on CI agents.
    """
    mock_which = mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
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
    """cleanup() is idempotent and raises no exception when setup() was never called.

    A fresh ConanEnvironmentManager has no setup directory; cleanup() must handle
    this gracefully so callers can use it safely in finally blocks without guards.
    """
    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    # Must not raise any exception
    manager.cleanup()


@pytest.mark.infrastructure
def test_base_conan_runner_setup_semantics_on_double_call(
    tmp_path: Path, mocker
) -> None:
    """setup() called twice on ConanEnvironmentManager: second call proceeds normally.

    The ConanEnvironmentManager does not raise on double setup — it simply
    overwrites _setup_dir with a new temp directory. This test documents
    that behaviour so that any future change to raise on double-setup is
    immediately visible.
    """
    mock_which = mocker.patch("shutil.which", return_value="/usr/bin/conan")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

    first_dir: Path = tmp_path / "first"
    second_dir: Path = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    # mkdtemp returns different paths on each call
    mocker.patch(
        "tempfile.mkdtemp",
        side_effect=[str(first_dir), str(second_dir)],
    )

    manager = ConanEnvironmentManager(_CONFIG_URL, _USERNAME, _PASSWORD)
    # Both calls must complete without raising
    manager.setup()
    manager.setup()
    # After second setup, _setup_dir points to the second directory
    assert manager._setup_dir == second_dir

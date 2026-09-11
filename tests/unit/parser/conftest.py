"""
Общие тестовые фикстуры и заглушки для autodoc/tests/unit/parser/.

FakeTFSClient — заглушка-пустышка для реального TFSClient. Отдельные тестовые
модули наследуются от него и переопределяют только нужные методы, делая
тестовую поверхность минимальной и явной.

CallbackStep / FailingStep / FinalizeOnlyStep / FakeManifestStep — общий набор
двойников BaseParseStep для тестов пайплайна (test_parser.py,
test_pipeline_failures.py, test_pipeline_integration.py). Раньше каждый файл
заводил собственные почти одинаковые локальные классы для одних и тех же трёх
сценариев («шаг падает», «шаг завершает результат», «шаг наблюдает за ctx») —
вынесены сюда, чтобы новый тест собирал нужный пайплайн из готовых кубиков,
а не писал очередной одноразовый подкласс.
"""

from collections.abc import Callable
import datetime
from pathlib import Path
import shutil

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.parsed_result import ParsedResult
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ProfileConanData,
)
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base_parse_step import BaseParseStep


# Фикстуры конфигурации / путей
@pytest.fixture
def parser_config(valid_parser_config: dict) -> ParserConfigSchema:
    """Минимальная корректная ParserConfigSchema для юнит-тестов (без реальных сетевых вызовов)."""
    return ParserConfigSchema(**valid_parser_config)


#: Путь к общим тестовым ресурсам в tests/unit/parser/resources/.
#: Не фикстура: путь чисто детерминирован (Path(__file__).parent) и не
#: нуждается ни в изоляции между тестами, ни в переопределении — таскать
#: такое значение через параметры функций pytest незачем, проще импортировать
#: константу напрямую (см. NULL_PACKAGE_ID ниже — тот же принцип).
RESOURCES_DIR: Path = Path(__file__).parent / "resources"


@pytest.fixture
def real_manifests_dir() -> Path:
    """Path to real .properties files under tests/unit/parser/resources/manifests/."""
    return RESOURCES_DIR / "manifests"


# Фикстуры Component / Release (общие для steps/, enrichment/, test_pipeline.py)
@pytest.fixture
def manifest_release() -> Release:
    """Release для openssl 1.0.0 на платформе 2.0 / канал 'tech'."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb],
    )


@pytest.fixture
def manifest_component(manifest_release: Release) -> Component:
    """Component с именем 'openssl', оборачивающий manifest_release."""
    return Component(name="openssl", releases=[manifest_release])


class FakeTFSClient:
    """
    Заглушка-пустышка для TFSClient.

    Каждый метод возвращает безопасное пустое значение по умолчанию, чтобы
    подклассам нужно было переопределять только один-два метода, нужных для теста.

    Сигнатуры методов зеркалируют реальный TFSClient, поэтому код с проверкой
    типов может использовать FakeTFSClient как замену в тестах.

    ``get_file_content`` настраивается через конструктор (``content``,
    ``status_code``, ``exception``), а список ``get_items`` — через ``items``:
    для простых сценариев ``FakeTFSClient(content=..., status_code=...)``,
    ``FakeTFSClient(exception=...)`` для имитации сетевого сбоя или
    ``FakeTFSClient(items=[...])`` для настройки списка элементов.
    """

    _content: bytes = b""
    _status_code: int = 200
    _exception: Exception | None = None
    _items: list = []

    def __init__(
        self,
        content: bytes = b"",
        status_code: int = 200,
        exception: Exception | None = None,
        items: list | None = None,
    ) -> None:
        """
        Args:
            content: Байты, возвращаемые как тело ответа get_file_content.
            status_code: HTTP-код статуса ответа get_file_content.
            exception: Если задано, get_file_content поднимает это исключение
                вместо возврата ответа (имитация сетевого сбоя).
            items: Список item-словарей, возвращаемых get_items. По умолчанию
                пустой список.
        """
        self._content = content
        self._status_code = status_code
        self._exception = exception
        self._items = items if items is not None else []

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type=None,
    ) -> requests.Response:
        """
        Возвращает ответ с настроенными в конструкторе content/status_code (по умолчанию — пустой 200)
        либо поднимает настроенное в конструкторе исключение.

        Собирается как настоящий ``requests.Response`` (а не MagicMock), чтобы
        ``raise_for_status()`` реально поднимал ``HTTPError`` при status_code >= 400 —
        как это делает реальный TFSClient.
        """
        if self._exception is not None:
            raise self._exception
        resp = requests.Response()
        resp.status_code = self._status_code
        resp._content = self._content
        return resp

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion=None,
        version_type=None,
    ) -> list:
        """Возвращает список элементов, настроенный в конструкторе (по умолчанию — пустой)."""
        return self._items

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Ничего не делает по умолчанию (файлы не записываются)."""


#: SHA-1 пустой строки — сигнальный package_id Conan для header-only пакетов.
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def make_component(
    name: str = "mylib",
    version: str = "1.0",
    channel: str = "fast",
    profiles: list[str] | None = None,
    git_url: str = "",
    is_header_only: bool = False,
) -> Component:
    """
    Фабрика Component, создающая один Release с запрошенными профилями.

    Отражает перенос полей ``git_url`` и ``is_header_only`` из ``Release``
    в ``Component``, произведённый в рамках рефакторинга DE/FS.

    Args:
        name: Имя компонента, используется и как имя пакета Conan, и как
            поле ``Component.name``.
        version: Строка версии релиза (например, ``"1.0"``).
        channel: Имя канала Conan (например, ``"fast"``).
        profiles: Список имён профилей, привязываемых к релизу. По умолчанию
            ``["hw-linux-x86_64"]``.
        git_url: URL git-репозитория — теперь хранится на ``Component``, а не на ``Release``.
        is_header_only: Флаг header-only — теперь хранится на ``Component``.

    Returns:
        Полностью собранный ``Component`` с одним ``Release`` и одним
        ``ProfileBuild`` на каждый элемент ``profiles``.
    """
    profile_names = profiles or ["hw-linux-x86_64"]
    pbs = [ProfileBuild(profile_name=p) for p in profile_names]
    release = Release(
        version=version,
        platform="2.2",
        channel=channel,
        conan_reference="",
        artifactory_url="",
        profile_builds=pbs,
    )
    return Component(
        name=name,
        description="",
        git_project="Proj",
        git_repo="repo",
        git_url=git_url,
        is_header_only=is_header_only,
        releases=[release],
    )


def make_conan_variant(
    package_id: str = "abc123",
    options_ref: str = "1",
) -> ConanVariant:
    """
    Минимальная фабрика ``ConanVariant`` с разумными значениями по умолчанию.

    Args:
        package_id: Хеш пакета Conan (используйте ``NULL_PACKAGE_ID`` для
            сценариев header-only).
        options_ref: Строка-идентификатор, ссылающаяся на ``TotalOptionsSet``.

    Returns:
        Экземпляр ``ConanVariant``, готовый к использованию в тестах обогащения.
    """
    return ConanVariant(
        package_id=package_id,
        build_url="http://art/pkg",
        build_date="2024-01-01",
        options_ref=options_ref,
    )


class CopyingAllFakeTFSClient(FakeTFSClient):
    """Копирует все .properties-файлы из исходной директории в output_dir при вызове download_properties."""

    def __init__(self, source_dir: Path) -> None:
        """
        Args:
            source_dir: Директория с .properties-файлами для копирования.
        """
        self._source_dir = source_dir

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Копирует все .properties-файлы из source_dir в output_dir."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for f in self._source_dir.glob("*.properties"):
            shutil.copy(f, out / f.name)


# Двойники BaseParseStep, общие для всех тестов пайплайна.
class CallbackStep(BaseParseStep):
    """
    Шаг-двойник: выполняет переданный callback вместо реальной логики.

    Закрывает большинство сценариев «нужно понаблюдать за ctx» или «шаг
    ничего не делает» без отдельного подкласса на каждый тест — поведение
    целиком определяется тем, что делает ``callback``. Если он бросает
    исключение, это ведёт себя как отказавший шаг (см. также ``FailingStep``
    для чисто «падающих» сценариев, где не нужен сам callback).

    Examples:
        Наблюдение (однострочный callback можно передать лямбдой)::

            seen = []
            CallbackStep(lambda ctx: seen.append(len(ctx.components)))

        Наблюдение + побочный эффект (для многострочной логики — обычная
        функция, а не лямбда)::

            def _observe(ctx: PipelineContext) -> None:
                for comp in ctx.components:
                    seen.append(comp.name)

            CallbackStep(_observe, name="observe_after_manifest")
    """

    name = "callback_step"

    def __init__(
        self,
        callback: Callable[[PipelineContext], None] | None = None,
        *,
        name: str = "callback_step",
        is_critical: bool = False,
        record: list[str] | None = None,
        record_as: str | None = None,
    ) -> None:
        """
        Args:
            callback: Вызывается из execute() с текущим ctx. None — шаг ничего не делает.
            name: Имя шага (для логов/диагностики этого конкретного двойника).
            is_critical: Останавливает ли отказ этого шага пайплайн.
            record: Если задан, execute() добавляет в этот список ``record_as`` (или
                ``name``) до вызова callback — фиксирует сам факт и порядок выполнения
                шага без отдельной функции-замыкания в тесте.
            record_as: Значение, добавляемое в ``record``. По умолчанию — ``name``.
        """
        self.name = name
        self.is_critical = is_critical
        self._callback = callback
        self._record = record
        self._record_as = record_as if record_as is not None else name

    def execute(self, ctx: PipelineContext) -> None:
        """Опционально фиксирует своё выполнение в ``record``, затем вызывает callback."""
        if self._record is not None:
            self._record.append(self._record_as)
        if self._callback is not None:
            self._callback(ctx)


class FailingStep(BaseParseStep):
    """
    Шаг-двойник: execute() всегда поднимает заданное исключение.

    ``is_critical`` настраивается через конструктор, поэтому один класс
    покрывает и критичные, и некритичные сценарии отказа пайплайна.
    """

    name = "failing_step"

    def __init__(
        self,
        exception: Exception,
        *,
        is_critical: bool = False,
        record: list[str] | None = None,
        record_as: str = "fail",
    ) -> None:
        """
        Args:
            exception: Экземпляр исключения, поднимаемый в execute().
            is_critical: Останавливает ли этот отказ пайплайн.
            record: Если задан, execute() добавляет в этот список ``record_as``
                до того, как поднять исключение — фиксирует сам факт попытки
                выполнения без отдельной функции-замыкания в тесте.
            record_as: Значение, добавляемое в ``record``.
        """
        self.is_critical = is_critical
        self._exception = exception
        self._record = record
        self._record_as = record_as

    def execute(self, ctx: PipelineContext) -> None:
        """Опционально фиксирует попытку в ``record``, затем безусловно поднимает исключение."""
        if self._record is not None:
            self._record.append(self._record_as)
        raise self._exception


class FinalizeOnlyStep(BaseParseStep):
    """
    Шаг-двойник финализации: заполняет ctx.result минимальным ParsedResult.

    Нужен, чтобы ComponentParser.parse() не поднимал исключение об
    отсутствующем результате в тестах, которые проверяют что-то другое
    (порядок шагов, накопление ошибок и т.п.) и которым сам факт наличия
    результата важнее его содержимого.
    """

    name = "finalize_only_step"

    def __init__(
        self,
        *,
        record: list[str] | None = None,
        record_as: str = "finalize",
    ) -> None:
        """
        Args:
            record: Если задан, execute() добавляет в этот список ``record_as``
                до заполнения ``ctx.result`` — фиксирует сам факт выполнения
                без отдельной функции-замыкания в тесте.
            record_as: Значение, добавляемое в ``record``.
        """
        self._record = record
        self._record_as = record_as

    def execute(self, ctx: PipelineContext) -> None:
        """Опционально фиксирует выполнение в ``record``, затем заполняет ctx.result."""
        if self._record is not None:
            self._record.append(self._record_as)
        ctx.result = ParsedResult(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            platform_version=ctx.config.platform_version,
        )


class FakeManifestStep(BaseParseStep):
    """
    Шаг-двойник ManifestStep: заполняет ctx.components одним минимальным компонентом.

    Имитирует реальный ManifestStep, чтобы последующие шаги, ожидающие
    заполненный ctx.components, могли работать без реального TFS-ввода-вывода.
    """

    name = "fake_manifest_step"
    is_critical = True

    def execute(self, ctx: PipelineContext) -> None:
        """Заполняет ctx.components одним минимальным компонентом с одним релизом/профилем."""
        pb = ProfileBuild(profile_name="hw-linux-x86_64")
        release = Release(
            version="1.0",
            platform="2.0",
            channel="fast",
            conan_reference="",
            artifactory_url="",
            profile_builds=[pb],
        )
        comp = Component(
            name="mylib",
            description="",
            git_project="P",
            git_repo="r",
            git_url="",
            is_header_only=False,
            releases=[release],
        )
        ctx.components = [comp]


def record_profile_build_states(
    ctx: PipelineContext, *, record: list[tuple[str, bool, int]]
) -> None:
    """
    Callback для CallbackStep: пишет (comp.name, pb.exists, len(pb.variants)) для каждого ProfileBuild.

    Вставляется как наблюдатель между реальными шагами полного пайплайна
    (см. test_pipeline_integration.py), чтобы проверить форму ctx в конкретной
    точке, не модифицируя сам пайплайн. В тесте привязывается к своему списку
    через ``functools.partial(record_profile_build_states, record=...)``.
    """
    for comp in ctx.components:
        for release in comp.releases:
            for pb in release.profile_builds:
                record.append((comp.name, pb.exists, len(pb.variants)))


def record_option_counts(ctx: PipelineContext, *, record: dict[tuple, int]) -> None:
    """
    Callback для CallbackStep: пишет len(release.build_option_sets) по ключу (comp, version, channel).

    В тесте привязывается к своему словарю через
    ``functools.partial(record_option_counts, record=...)``.
    """
    for comp in ctx.components:
        for release in comp.releases:
            key = (comp.name, release.version, release.channel)
            record[key] = len(release.build_option_sets)


def build_conan_enrichment_for(
    components: list[Component],
    name_predicate: Callable[[Component], bool],
    variant: ConanVariant,
) -> FetchResult:
    """
    Строит FetchResult[ConanEnrichmentResult], дающий один variant каждому profile_build
    компонентов, удовлетворяющих name_predicate.

    Вызывается внутри side_effect у пропатченного ConanFetcher.fetch — поэтому
    получает живые объекты ProfileBuild (созданные ManifestStep) и может
    использовать id(pb) как ключ, ожидаемый DataEnricher.apply_conan_results().

    Args:
        components: ctx.components на момент вызова fetch() (передаются side_effect'ом).
        name_predicate: Отбирает компоненты, которым нужно обогащение (например,
            ``lambda c: "nlohmann" in c.name.lower()``).
        variant: ConanVariant, присваиваемый каждому подходящему profile_build.

    Returns:
        FetchResult без предупреждений, оборачивающий собранный ConanEnrichmentResult.
    """
    result = ConanEnrichmentResult()
    for comp in components:
        if not name_predicate(comp):
            continue
        for release in comp.releases:
            for pb in release.profile_builds:
                result.profile_data[id(pb)] = ProfileConanData(
                    conan_settings={}, exists=True, variants=[variant]
                )
    return FetchResult(value=result, warnings=[])

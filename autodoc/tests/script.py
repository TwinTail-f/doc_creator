"""
Translate all docstrings and comments in test files from English to Russian.
Also removes numbered prefixes like "1.1 — " from comments.
"""
import ast
import tokenize
import io
import re
from pathlib import Path

# ============================================================
# TRANSLATION TABLE
# Keys = original English text (raw value, without quotes)
# Values = Russian translation
# ============================================================

TRANS = {
    # ── test_models.py ──────────────────────────────────────────────────────
    "Unit tests for autodoc.models.component.\n\nCovers: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.":
        "Юнит-тесты для autodoc.models.component.\n\nОхватывает: _parse_option_str, ConanInputOptions, ProfileBuild, Release, Component.",
    "_parse_option_str removes the package prefix from every key.":
        "_parse_option_str удаляет префикс пакета из каждого ключа.",
    "_parse_option_str returns an empty dict for an empty input string.":
        "_parse_option_str возвращает пустой словарь для пустой входной строки.",
    "_parse_option_str accepts keys that carry no package prefix.":
        "_parse_option_str принимает ключи без префикса пакета.",
    "_parse_option_str strips the wildcard prefix (mylib/*:key) and keeps the bare key.":
        "_parse_option_str удаляет префикс с символом подстановки (mylib/*:key) и оставляет чистый ключ.",
    "ConanInputOptions.parsed_options is auto-populated from the options string on construction.":
        "ConanInputOptions.parsed_options автоматически заполняется из строки options при создании.",
    "ConanInputOptions.parsed_options remains empty when options is an empty string.":
        "ConanInputOptions.parsed_options остаётся пустым, если options — пустая строка.",
    "ConanInputOptions.parsed_options is not overwritten when it is explicitly provided.":
        "ConanInputOptions.parsed_options не перезаписывается, если он задан явно.",
    "ProfileBuild.exists defaults to False when not explicitly set.":
        "ProfileBuild.exists по умолчанию равен False, если не задан явно.",
    "Release.build_option_sets and profile_builds default to [] and is_header_only to False.":
        "Release.build_option_sets и profile_builds по умолчанию [], is_header_only — False.",
    "Component round-trips correctly through model_dump and model_validate.":
        "Component корректно проходит сериализацию и десериализацию через model_dump и model_validate.",

    # ── test_artifactory_client.py ──────────────────────────────────────────
    "\nUnit tests for autodoc/parser/clients/artifactory_client.py.\n\nAll HTTP I/O is mocked — no real network calls are made.\n":
        "\nЮнит-тесты для autodoc/parser/clients/artifactory_client.py.\n\nВесь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.\n",
    "Instantiate ArtifactoryClient from a minimal valid parser config.":
        "Создаёт ArtifactoryClient из минимальной корректной конфигурации парсера.",
    "ArtifactoryClient.head returns the HTTP response on a successful HEAD request.":
        "ArtifactoryClient.head возвращает HTTP-ответ при успешном HEAD-запросе.",
    "ArtifactoryClient sets verify=False on the session, disabling SSL verification.":
        "ArtifactoryClient устанавливает verify=False для сессии, отключая проверку SSL.",
    "ArtifactoryClient structurally satisfies the IArtifactoryClient Protocol.":
        "ArtifactoryClient структурно удовлетворяет протоколу IArtifactoryClient.",
    "TFSClient structurally satisfies the ITFSClient Protocol.":
        "TFSClient структурно удовлетворяет протоколу ITFSClient.",

    # ── test_tfs_client.py ──────────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/clients/tfs_client.py.\n\nAll HTTP I/O is mocked — no real network calls are made.\n":
        "\nЮнит-тесты для autodoc/parser/clients/tfs_client.py.\n\nВесь HTTP-ввод/вывод замокан — реальных сетевых вызовов нет.\n",
    "Return a mock requests.Response with the given status code and content.":
        "Возвращает мок requests.Response с заданным кодом статуса и содержимым.",
    "Instantiate TFSClient from a minimal valid parser config.":
        "Создаёт TFSClient из минимальной корректной конфигурации парсера.",
    "TFSClient.get_file_content returns the HTTP response on success.":
        "TFSClient.get_file_content возвращает HTTP-ответ при успехе.",
    "TFSClient.get_file_content wraps RequestException into NetworkError.":
        "TFSClient.get_file_content оборачивает RequestException в NetworkError.",
    "TFSClient.get_items returns the list extracted from the 'value' key.":
        "TFSClient.get_items возвращает список, извлечённый из ключа 'value'.",
    "TFSClient.get_items raises NetworkError when the session raises RequestException.":
        "TFSClient.get_items вызывает NetworkError, когда сессия бросает RequestException.",
    "\n    download_properties writes .properties files to tmp_path and skips other extensions.\n\n    The listing response provides two items; only the .properties one is written.":
        "\n    download_properties записывает .properties-файлы в tmp_path и пропускает другие расширения.\n\n    Ответ листинга содержит два элемента; записывается только .properties-файл.",
    "download_properties propagates NetworkError when the listing request fails.":
        "download_properties пробрасывает NetworkError при сбое запроса листинга.",

    # ── test_profile_overrides.py ───────────────────────────────────────────
    "\nUnit tests for autodoc/parser/conan/profile_overrides.py.\n\nCovers ProfileSettingsOverrides: from_file(), resolve(), is_empty(),\nempty(), and multi-entry merge behaviour.":
        "\nЮнит-тесты для autodoc/parser/conan/profile_overrides.py.\n\nОхватывает ProfileSettingsOverrides: from_file(), resolve(), is_empty(),\nempty() и поведение слияния нескольких записей.",
    "Write a dict as JSON to a temp file and return the path.":
        "Записывает словарь как JSON во временный файл и возвращает путь.",
    "from_file() with a valid JSON file resolves the exact profile name correctly.":
        "from_file() с корректным JSON-файлом правильно разрешает точное имя профиля.",
    "from_file() with a nonexistent path returns an empty instance.":
        "from_file() с несуществующим путём возвращает пустой экземпляр.",
    "from_file() with malformed JSON content returns an empty instance.":
        "from_file() с некорректным JSON возвращает пустой экземпляр.",
    "resolve() with the exact profile name as listed in config returns settings.":
        "resolve() с точным именем профиля из конфига возвращает настройки.",
    "resolve() falls back to basename match when full path is used as profile name.\n\n    The source code performs a basename (Path.name) lookup as a secondary step.\n    A profile stored as 'hw-linux-x86_64.jinja' should be found when queried\n    via '/some/path/to/hw-linux-x86_64.jinja'.":
        "resolve() использует сопоставление по basename, когда полный путь используется как имя профиля.\n\n    Исходный код выполняет поиск по basename (Path.name) в качестве вторичного шага.\n    Профиль, хранящийся как 'hw-linux-x86_64.jinja', должен находиться при запросе\n    через '/some/path/to/hw-linux-x86_64.jinja'.",
    "resolve() with an unknown profile name returns an empty dict.":
        "resolve() с неизвестным именем профиля возвращает пустой словарь.",
    "ProfileSettingsOverrides.empty() produces an instance where is_empty() is True.":
        "ProfileSettingsOverrides.empty() создаёт экземпляр, для которого is_empty() возвращает True.",
    "is_empty() returns False when overrides have been loaded from a valid file.":
        "is_empty() возвращает False, если переопределения загружены из корректного файла.",
    "Two entries for the same profile name are merged into a single settings dict.":
        "Две записи для одного имени профиля объединяются в единый словарь настроек.",

    # ── test_result_aggregator.py ───────────────────────────────────────────
    "\nUnit tests for autodoc/parser/conan/result_aggregator.py.\n\nCovers ConanResultAggregator.aggregate() — success path, failure\nskipping, and result structure. No subprocess or I/O.":
        "\nЮнит-тесты для autodoc/parser/conan/result_aggregator.py.\n\nОхватывает ConanResultAggregator.aggregate() — успешный путь, пропуск\nсбоев и структуру результата. Без subprocess и ввода/вывода.",
    "Return a minimal ConanTask for aggregation tests.":
        "Возвращает минимальный ConanTask для тестов агрегации.",
    "Return a minimal ConanEnrichData for mocking the parser.":
        "Возвращает минимальный ConanEnrichData для мокирования парсера.",
    "A successful raw result produces an entry in ConanEnrichmentResult.release_data.":
        "Успешный сырой результат создаёт запись в ConanEnrichmentResult.release_data.",
    "Parser.parse() is never called for raw results with success=False.":
        "Parser.parse() никогда не вызывается для сырых результатов с success=False.",
    "A None entry in raw_results does not raise and leaves release_data empty.":
        "Запись None в raw_results не вызывает исключения и оставляет release_data пустым.",
    "When parser returns None (Binary: Missing), profile_data.exists == False.":
        "Когда парсер возвращает None (Binary: Missing), profile_data.exists == False.",
    "total_tasks and succeeded counters reflect the number of tasks and successes.":
        "Счётчики total_tasks и succeeded отражают количество задач и успехов.",

    # ── test_result_parser.py ───────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/conan/result_parser.py.\n\nCovers ConanResultParser.parse() — happy path, missing-binary,\nmissing-node, root-node skipping, and field extraction.\nJSON fixtures are loaded via the shared resources_dir fixture.":
        "\nЮнит-тесты для autodoc/parser/conan/result_parser.py.\n\nОхватывает ConanResultParser.parse() — успешный путь, отсутствующий\nбинарник, отсутствующий узел, пропуск корневого узла и извлечение полей.\nJSON-фикстуры загружаются через общую фикстуру resources_dir.",
    "Minimal ConanTask targeting benchmark/1.9.4.549 in graph_info_success.json.":
        "Минимальный ConanTask для benchmark/1.9.4.549 из graph_info_success.json.",
    "Parsed contents of graph_info_success.json.":
        "Разобранное содержимое graph_info_success.json.",
    "Parsed contents of graph_info_missing.json (libyang with binary=Missing).":
        "Разобранное содержимое graph_info_missing.json (libyang с binary=Missing).",
    "parse() returns ConanEnrichData with the expected package_id on success.":
        "parse() возвращает ConanEnrichData с ожидаемым package_id при успехе.",
    "parse() returns None when the target node has binary='Missing'.":
        "parse() возвращает None, когда целевой узел имеет binary='Missing'.",
    "parse() returns None when no node matches comp_name.":
        "parse() возвращает None, когда ни один узел не совпадает с comp_name.",
    "Node '0' with name=null is never matched, even when it's the only node.":
        "Узел '0' с name=null никогда не совпадает, даже если он единственный.",
    "base_ref starts with 'benchmark/' and contains no '#' revision hash.":
        "base_ref начинается с 'benchmark/' и не содержит хеша ревизии '#'.",
    "conan_settings is a non-empty dict containing at least 'os' or 'arch'.":
        "conan_settings — непустой словарь, содержащий как минимум 'os' или 'arch'.",
    "A node with default_options=null must yield an empty default_options list.":
        "Узел с default_options=null должен возвращать пустой список default_options.",

    # ── test_task_builder.py ────────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/conan/task_builder.py.\n\nCovers ConanTaskBuilder.build() — task enumeration, field population,\nand option-string normalization. No I/O; no subprocess calls.":
        "\nЮнит-тесты для autodoc/parser/conan/task_builder.py.\n\nОхватывает ConanTaskBuilder.build() — перебор задач, заполнение полей\nи нормализацию строк опций. Без ввода/вывода и вызовов subprocess.",
    "Build a Release with the given profiles and internal option sets.":
        "Создаёт Release с заданными профилями и внутренними наборами опций.",
    "Build a Component with optional releases list.":
        "Создаёт Component с необязательным списком релизов.",
    "One component × one release × two profiles → two tasks.":
        "Один компонент × один релиз × два профиля → две задачи.",
    "Release with no options configured → one task with option_id '1'.":
        "Релиз без настроенных опций → одна задача с option_id '1'.",
    "One profile × two option sets → two tasks.":
        "Один профиль × два набора опций → две задачи.",
    "The first --requires= element of cmd must contain the component name.":
        "Первый элемент --requires= в cmd должен содержать имя компонента.",
    "Bare 'shared=True' must be prefixed with '*:' in the cmd.":
        "Голое 'shared=True' должно быть дополнено префиксом '*:' в cmd.",
    "'mylib:shared=True' must be expanded to 'mylib/*:shared=True'.":
        "'mylib:shared=True' должно быть расширено до 'mylib/*:shared=True'.",
    "'mylib/*:shared=True' must not be double-wildcarded.":
        "'mylib/*:shared=True' не должно быть дважды заменено символом подстановки.",
    "Empty component list must return empty task list.":
        "Пустой список компонентов должен возвращать пустой список задач.",
    "All ConanTask scalar fields must match source model values.":
        "Все скалярные поля ConanTask должны совпадать со значениями исходной модели.",

    # ── conftest.py ─────────────────────────────────────────────────────────
    "\nShared test fixtures and fakes for autodoc/tests/unit/parser/.\n\nFakeTFSClient is a no-op stand-in for the real TFSClient.  Individual test\nmodules subclass it and override only the methods they need, keeping the\ntest surface minimal and explicit.":
        "\nОбщие тестовые фикстуры и заглушки для autodoc/tests/unit/parser/.\n\nFakeTFSClient — заглушка-пустышка для реального TFSClient. Отдельные тестовые\nмодули наследуются от него и переопределяют только нужные методы, делая\nтестовую поверхность минимальной и явной.",
    "Minimal valid ParserConfigSchema for unit tests (no real network calls).":
        "Минимальная корректная ParserConfigSchema для юнит-тестов (без реальных сетевых вызовов).",
    "Path to the shared test-resource files under tests/unit/parser/resources/.":
        "Путь к общим тестовым ресурсам в tests/unit/parser/resources/.",
    "A fully-initialised PipelineContext backed by parser_config and a tmp_path.":
        "Полностью инициализированный PipelineContext на основе parser_config и tmp_path.",
    "A Release for openssl 1.0.0 on platform 2.0 / channel 'tech'.":
        "Release для openssl 1.0.0 на платформе 2.0 / канал 'tech'.",
    "A Component named 'openssl' that wraps manifest_release.":
        "Component с именем 'openssl', оборачивающий manifest_release.",
    "Minimal Artifactory client stub that records head() calls.":
        "Минимальная заглушка клиента Artifactory, записывающая вызовы head().",
    "Default 200-OK fake Artifactory client; tests use .__class__(status_code=N) for variants.":
        "Фейковый клиент Artifactory по умолчанию (200 OK); тесты используют .__class__(status_code=N) для вариантов.",
    "\n    No-op fake for TFSClient.\n\n    Every method returns a safe, empty default so that subclasses only need\n    to override the one or two methods relevant to the test being written.\n\n    Method signatures mirror the real TFSClient so that type-checked code\n    can use FakeTFSClient as a drop-in replacement in tests.":
        "\n    Заглушка-пустышка для TFSClient.\n\n    Каждый метод возвращает безопасное пустое значение по умолчанию, чтобы\n    подклассам нужно было переопределять только один-два метода, нужных для теста.\n\n    Сигнатуры методов зеркалируют реальный TFSClient, поэтому код с проверкой\n    типов может использовать FakeTFSClient как замену в тестах.",
    "Return an empty 200 response by default.":
        "Возвращает пустой ответ 200 по умолчанию.",
    "Return an empty item list by default.":
        "Возвращает пустой список элементов по умолчанию.",
    "Do nothing by default (no files written).":
        "Ничего не делает по умолчанию (файлы не записываются).",

    # ── enrichment/conftest.py ──────────────────────────────────────────────
    "\nFixtures for autodoc/tests/unit/parser/enrichment/.\n\nmanifest_component, manifest_release are inherited from the parent\ntests/unit/parser/conftest.py and available here automatically.":
        "\nФикстуры для autodoc/tests/unit/parser/enrichment/.\n\nmanifest_component и manifest_release наследуются из родительского\ntests/unit/parser/conftest.py и доступны здесь автоматически.",
    "A minimal ConanVariant for use in apply_conan_results tests.":
        "Минимальный ConanVariant для использования в тестах apply_conan_results.",

    # ── test_data_enricher.py ───────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/enrichment/data_enricher.py.\n\nCovers DataEnricher.apply_options(), apply_docker_links(), and\napply_conan_results(). Uses fixtures from unit/parser/conftest.py where\navailable; component-level fixtures are built inline for clarity.":
        "\nЮнит-тесты для autodoc/parser/enrichment/data_enricher.py.\n\nОхватывает DataEnricher.apply_options(), apply_docker_links() и\napply_conan_results(). Использует фикстуры из unit/parser/conftest.py там,\nгде доступны; фикстуры уровня компонента строятся инлайн для ясности.",
    "Return a (Component, Release, ProfileBuild) triple for enrichment tests.":
        "Возвращает тройку (Component, Release, ProfileBuild) для тестов обогащения.",
    "Build a ConanEnrichmentResult that covers the given component/release/pb.":
        "Строит ConanEnrichmentResult, охватывающий заданный component/release/pb.",
    "apply_options() sets _build_option_sets_internal and build_option_sets.":
        "apply_options() устанавливает _build_option_sets_internal и build_option_sets.",
    "apply_options() with an empty options_map leaves build_option_sets unchanged.":
        "apply_options() с пустым options_map оставляет build_option_sets без изменений.",
    "apply_options() with two option sets creates two ConanInputOptions entries.":
        "apply_options() с двумя наборами опций создаёт две записи ConanInputOptions.",
    "apply_docker_links() appends a new ProfileDefinition when none exists.":
        "apply_docker_links() добавляет новый ProfileDefinition, если его ещё нет.",
    "apply_docker_links() updates docker_image on an existing ProfileDefinition.":
        "apply_docker_links() обновляет docker_image в существующем ProfileDefinition.",
    "apply_docker_links() with empty docker_links creates a ProfileDefinition with\n    an empty docker_image — the profile is registered but no URL is set.":
        "apply_docker_links() с пустым docker_links создаёт ProfileDefinition\n    с пустым docker_image — профиль регистрируется, но URL не задан.",
    "apply_conan_results() writes base_ref into release.conan_reference.":
        "apply_conan_results() записывает base_ref в release.conan_reference.",
    "apply_conan_results() sets pb.exists=True and populates pb.variants.":
        "apply_conan_results() устанавливает pb.exists=True и заполняет pb.variants.",
    "apply_conan_results() creates a new ProfileDefinition with conan_settings.":
        "apply_conan_results() создаёт новый ProfileDefinition с conan_settings.",
    "Non-empty conan_settings on an existing ProfileDefinition are not erased by empty data.":
        "Непустые conan_settings в существующем ProfileDefinition не стираются пустыми данными.",
    "apply_conan_results() leaves conan_reference empty when release_data has no match.":
        "apply_conan_results() оставляет conan_reference пустым, если release_data не содержит совпадений.",

    # ── test_docker_fetcher.py ──────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/fetchers/docker_fetcher.py.\n\nStrategy: provide a fake TFS client whose get_file_content returns controlled\nYAML content. DockerParser is NOT mocked — the full DockerFetcher → DockerParser\nchain is exercised.":
        "\nЮнит-тесты для autodoc/parser/fetchers/docker_fetcher.py.\n\nСтратегия: предоставляется фейковый TFS-клиент, чей get_file_content возвращает\nуправляемое содержимое YAML. DockerParser НЕ мокируется — тестируется вся\nцепочка DockerFetcher → DockerParser.",
    "FakeTFSClient that returns a configurable response from get_file_content.":
        "FakeTFSClient, возвращающий настраиваемый ответ из get_file_content.",
    "\n        Args:\n            content: Bytes returned as the response body.\n            status_code: HTTP status code of the response.\n        ":
        "\n        Args:\n            content: Байты, возвращаемые как тело ответа.\n            status_code: HTTP-код статуса ответа.\n        ",
    "Return a response with the configured status code and content.":
        "Возвращает ответ с настроенным кодом статуса и содержимым.",
    "FakeTFSClient whose get_file_content raises requests.ConnectionError.":
        "FakeTFSClient, чей get_file_content вызывает requests.ConnectionError.",
    "Simulate a network-level failure (caught by DockerFetcher).":
        "Имитирует сетевой сбой (перехватывается DockerFetcher).",
    "Build a minimal PipelineContext with the given fake TFS client.":
        "Строит минимальный PipelineContext с заданным фейковым TFS-клиентом.",
    "DockerFetcher returns a docker link for each profile found in the YAML.":
        "DockerFetcher возвращает docker-ссылку для каждого профиля, найденного в YAML.",
    "DockerFetcher.fetch with an empty URL list returns an empty links map.":
        "DockerFetcher.fetch с пустым списком URL возвращает пустую карту ссылок.",
    "\n    DockerFetcher skips a URL when get_file_content raises a RequestException.\n\n    The exception is caught internally; the result is an empty links map and\n    the fetcher does not propagate the error.":
        "\n    DockerFetcher пропускает URL, когда get_file_content вызывает RequestException.\n\n    Исключение перехватывается внутри; результат — пустая карта ссылок,\n    ошибка не пробрасывается.",
    "\n    DockerFetcher skips a URL when the response body is not valid YAML.\n\n    The YAMLError is caught internally; the result is an empty links map and\n    the fetcher does not propagate the error.":
        "\n    DockerFetcher пропускает URL, когда тело ответа не является корректным YAML.\n\n    YAMLError перехватывается внутри; результат — пустая карта ссылок,\n    ошибка не пробрасывается.",

    # ── test_fetcher_base.py ────────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/fetchers/base.py.\n\nCovers FetchResult data class and the BaseTFSFetcher two-phase invariant.":
        "\nЮнит-тесты для autodoc/parser/fetchers/base.py.\n\nОхватывает датакласс FetchResult и двухфазный инвариант BaseTFSFetcher.",
    "Minimal concrete BaseTFSFetcher subclass for testing the base class invariants.":
        "Минимальный конкретный подкласс BaseTFSFetcher для тестирования инвариантов базового класса.",
    "Store the TFS client from context (standard BaseTFSFetcher pattern).":
        "Сохраняет TFS-клиент из контекста (стандартный шаблон BaseTFSFetcher).",
    "Return an empty result; not exercised in base-class tests.":
        "Возвращает пустой результат; не используется в тестах базового класса.",
    "FetchResult exposes the provided value and warnings list.":
        "FetchResult предоставляет переданные value и список warnings.",
    "FetchResult.warnings defaults to an empty list when not supplied.":
        "FetchResult.warnings по умолчанию является пустым списком, если не задан.",
    "_tfs attribute is None immediately after construction, before configure().":
        "Атрибут _tfs равен None сразу после создания, до вызова configure().",

    # ── test_manifest_fetcher.py ────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/fetchers/manifest_fetcher.py.\n\nStrategy: provide fake TFS clients that write real-looking .properties content\ninto tmp_dir without network I/O. ManifestParser is NOT mocked — the full\nManifestFetcher → ManifestParser chain is exercised.":
        "\nЮнит-тесты для autodoc/parser/fetchers/manifest_fetcher.py.\n\nСтратегия: предоставляются фейковые TFS-клиенты, записывающие реалистичное\n.properties-содержимое в tmp_dir без сетевого ввода/вывода. ManifestParser\nНЕ мокируется — тестируется вся цепочка ManifestFetcher → ManifestParser.",
    "FakeTFSClient that writes a .properties file into output_dir on download_properties.":
        "FakeTFSClient, записывающий .properties-файл в output_dir при вызове download_properties.",
    "\n        Args:\n            content: Text to write into the .properties file.\n            filename: Name of the file created inside output_dir.":
        "\n        Args:\n            content: Текст для записи в .properties-файл.\n            filename: Имя файла, создаваемого внутри output_dir.",
    "Write the configured content into output_dir as a .properties file.":
        "Записывает настроенное содержимое в output_dir как .properties-файл.",
    "FakeTFSClient that copies a real .properties file into output_dir.":
        "FakeTFSClient, копирующий реальный .properties-файл в output_dir.",
    "\n        Args:\n            source_file: Path to the real .properties file to copy.\n        ":
        "\n        Args:\n            source_file: Путь к реальному .properties-файлу для копирования.\n        ",
    "Copy the source file into output_dir, preserving its filename.":
        "Копирует исходный файл в output_dir, сохраняя его имя.",
    "Build a PipelineContext with the given fake TFS client.":
        "Строит PipelineContext с заданным фейковым TFS-клиентом.",
    "ManifestFetcher returns exactly one component when given valid .properties content.":
        "ManifestFetcher возвращает ровно один компонент при корректном .properties-содержимом.",
    "ManifestFetcher returns no components when the component name is excluded.":
        "ManifestFetcher не возвращает компоненты, если имя компонента исключено.",
    "After configure(), the fetcher's internal _tfs reference is not None.":
        "После configure() внутренняя ссылка _tfs в fetcher не равна None.",
    "\n    ManifestFetcher raises ParsingError when download_properties writes no files.\n\n    The underlying FakeTFSClient (no-op) produces an empty directory, which the\n    fetcher treats as a fatal configuration or network problem.":
        "\n    ManifestFetcher вызывает ParsingError, когда download_properties не записывает файлы.\n\n    Базовый FakeTFSClient (заглушка) создаёт пустую директорию, которую\n    fetcher воспринимает как фатальную ошибку конфигурации или сети.",
    "ManifestFetcher returns components when given a real .properties file.":
        "ManifestFetcher возвращает компоненты при передаче реального .properties-файла.",

    # ── test_options_fetcher.py ─────────────────────────────────────────────
    "\nUnit tests for autodoc/parser/fetchers/options_fetcher.py.\n\nStrategy: subclass FakeTFSClient to control what get_items and\nget_file_content return, then verify the OptionsMap built by the fetcher.":
        "\nЮнит-тесты для autodoc/parser/fetchers/options_fetcher.py.\n\nСтратегия: наследуемся от FakeTFSClient, чтобы управлять возвращаемыми\nзначениями get_items и get_file_content, затем проверяем OptionsMap.",
    "\n    FakeTFSClient whose get_items and get_file_content return configurable data.\n\n    Useful for testing the full OptionsFetcher pipeline.":
        "\n    FakeTFSClient, чьи get_items и get_file_content возвращают настраиваемые данные.\n\n    Полезен для тестирования всего пайплайна OptionsFetcher.",
    "\n        Args:\n            items: List of item dicts returned by get_items.\n            content: Raw bytes returned as response body by get_file_content.":
        "\n        Args:\n            items: Список словарей элементов, возвращаемых get_items.\n            content: Сырые байты, возвращаемые как тело ответа get_file_content.",
    "Return the pre-configured item list.":
        "Возвращает заранее настроенный список элементов.",
    "Return a 200 response with the pre-configured content.":
        "Возвращает ответ 200 с заранее настроенным содержимым.",
    "Build a minimal Component with one Release.":
        "Строит минимальный Component с одним Release.",
    "OptionsFetcher maps (name, version, channel) → parsed options on success.":
        "OptionsFetcher отображает (name, version, channel) → разобранные опции при успехе.",
    "\n    When get_items returns no items, OptionsFetcher inserts a default options entry.\n\n    The OptionsParser.pick_options fallback returns {\"1\": \"\"} when no channel-\n    specific or global options are available.":
        "\n    Когда get_items не возвращает элементов, OptionsFetcher добавляет запись опций по умолчанию.\n\n    Запасной вариант OptionsParser.pick_options возвращает {\"1\": \"\"}, если нет\n    канало-специфичных или глобальных опций.",
    "\n    OptionsFetcher does not raise when get_file_content returns invalid JSON.\n\n    The OptionsParser logs a warning internally and returns an empty options dict.\n    The fetcher continues and returns the default fallback for that release.":
        "\n    OptionsFetcher не вызывает исключений, когда get_file_content возвращает некорректный JSON.\n\n    OptionsParser логирует предупреждение внутри и возвращает пустой словарь опций.\n    Fetcher продолжает работу и возвращает значение по умолчанию для данного релиза.",

    # ── test_docker_parser.py ───────────────────────────────────────────────
    "Unit tests for autodoc.parser.parsers.docker_parser.DockerParser.\n\nCovers: extract_from_yaml, extract_docker_image, add_aliases.\nAll tests operate on in-memory dicts — no I/O required.":
        "Юнит-тесты для autodoc.parser.parsers.docker_parser.DockerParser.\n\nОхватывает: extract_from_yaml, extract_docker_image, add_aliases.\nВсе тесты работают с in-memory словарями — ввод/вывод не требуется.",
    "extract_from_yaml maps the arch key to a plain-string docker image URL.":
        "extract_from_yaml сопоставляет ключ arch с URL docker-образа в виде простой строки.",
    "extract_from_yaml extracts the image URL when docker value is a dict with an 'image' key.":
        "extract_from_yaml извлекает URL образа, когда docker-значение — словарь с ключом 'image'.",
    "extract_from_yaml ignores entries with the reserved 'common' key.":
        "extract_from_yaml игнорирует записи с зарезервированным ключом 'common'.",
    "extract_from_yaml skips arch entries that carry no 'docker' field.":
        "extract_from_yaml пропускает записи arch, не содержащие поле 'docker'.",
    "extract_from_yaml registers a docker image for every item in a list profile_host.":
        "extract_from_yaml регистрирует docker-образ для каждого элемента списка profile_host.",
    "add_aliases inserts full path, filename, stem, and parent/stem for a nested .jinja name.":
        "add_aliases добавляет полный путь, имя файла, stem и parent/stem для вложённого .jinja-имени.",
    "add_aliases maps a flat (non-nested) name without adding a parent/stem key.":
        "add_aliases отображает плоское (невложенное) имя без добавления ключа parent/stem.",
    "add_aliases leaves the links dict unchanged when name is an empty string.":
        "add_aliases оставляет словарь links без изменений, когда name — пустая строка.",
    "extract_docker_image returns '' when the docker field value is None.":
        "extract_docker_image возвращает '', если значение поля docker равно None.",

    # ── test_manifest_parser.py ─────────────────────────────────────────────
    "Unit tests for autodoc.parser.parsers.manifest_parser.ManifestParser.\n\nCovers: parse, _parse_single_file, _build_releases.\nReal .properties files are read from resources_dir fixture.\nCustom / edge-case content is written to tmp_path.":
        "Юнит-тесты для autodoc.parser.parsers.manifest_parser.ManifestParser.\n\nОхватывает: parse, _parse_single_file, _build_releases.\nРеальные .properties-файлы читаются из фикстуры resources_dir.\nПользовательское/граничное содержимое записывается в tmp_path.",
    "Write content to a .properties file in tmp_path and return the path.":
        "Записывает содержимое в .properties-файл в tmp_path и возвращает путь.",
    "ManifestParser returns one component with two profile_builds for a valid file.":
        "ManifestParser возвращает один компонент с двумя profile_builds для корректного файла.",
    "ManifestParser silently skips a .properties file that has no 'name' key.":
        "ManifestParser молча пропускает .properties-файл, не содержащий ключ 'name'.",
    "ManifestParser omits components whose name appears in the excluded list.":
        "ManifestParser пропускает компоненты, чьё имя присутствует в списке исключений.",
    "ManifestParser returns no components when all platform versions mismatch the target.":
        "ManifestParser не возвращает компоненты, если все версии платформы не совпадают с целевой.",
    "ManifestParser records a warning and returns no components for a non-existent file.":
        "ManifestParser записывает предупреждение и не возвращает компоненты для несуществующего файла.",
    "ManifestParser creates one release per matching component-version / platform pair.":
        "ManifestParser создаёт один релиз для каждой совпадающей пары компонент-версия / платформа.",
    "ManifestParser sets release.channel to the part after the first '-' in the platform version.":
        "ManifestParser устанавливает release.channel равным части после первого '-' в версии платформы.",
    "ManifestParser sets release.channel to '' when the platform version has no '-' suffix.":
        "ManifestParser устанавливает release.channel в '', если версия платформы не имеет суффикса '-'.",
    "ManifestParser builds release.git_url as '<project>/_git/<repo>'.":
        "ManifestParser строит release.git_url в виде '<project>/_git/<repo>'.",
    "ManifestParser skips a version pair that has no matching profiles key.":
        "ManifestParser пропускает пару версий, для которой нет совпадающего ключа profiles.",
    "ManifestParser accumulates components from multiple valid files.":
        "ManifestParser накапливает компоненты из нескольких корректных файлов.",
    "ManifestParser correctly parses the real openssl.properties resource file.":
        "ManifestParser корректно разбирает реальный файл ресурса openssl.properties.",

    # ── test_options_parser.py ──────────────────────────────────────────────
    "Unit tests for autodoc.parser.parsers.options_parser.OptionsParser.\n\nCovers: select_ci_prefix, parse_file, pick_options.\nReal options JSON files are read from resources_dir fixture.":
        "Юнит-тесты для autodoc.parser.parsers.options_parser.OptionsParser.\n\nОхватывает: select_ci_prefix, parse_file, pick_options.\nРеальные JSON-файлы опций читаются из фикстуры resources_dir.",
    "select_ci_prefix returns '/ci-2.0/' when both v2 and v1.6 paths are present.":
        "select_ci_prefix возвращает '/ci-2.0/', когда присутствуют пути v2 и v1.6.",
    "select_ci_prefix returns '/ci-1.6/' when only v1.6 paths are present.":
        "select_ci_prefix возвращает '/ci-1.6/', когда присутствуют только пути v1.6.",
    "select_ci_prefix returns '' when no recognised CI directory is found.":
        "select_ci_prefix возвращает '', когда не найдена ни одна известная CI-директория.",
    "select_ci_prefix returns '' for an empty input list.":
        "select_ci_prefix возвращает '' для пустого входного списка.",
    "parse_file correctly extracts the channel segment from the path.":
        "parse_file корректно извлекает сегмент канала из пути.",
    "parse_file returns channel=None when the path has no subdirectory after the prefix.":
        "parse_file возвращает channel=None, когда путь не имеет поддиректории после префикса.",
    "parse_file returns (None, {}) when the JSON text cannot be parsed.":
        "parse_file возвращает (None, {}), когда JSON-текст не может быть разобран.",
    "parse_file strips leading/trailing whitespace from each option string value.":
        "parse_file удаляет ведущие и завершающие пробелы из каждого строкового значения опции.",
    "parse_file omits entries whose value is not a string (e.g. integers).":
        "parse_file пропускает записи, значение которых не является строкой (например, целые числа).",
    "pick_options returns channels[channel] when the channel key exists.":
        "pick_options возвращает channels[channel], когда ключ канала существует.",
    "pick_options returns the 'global' entry when the requested channel is absent.":
        "pick_options возвращает запись 'global', когда запрошенный канал отсутствует.",
    "pick_options returns {'1': ''} when neither channels nor global is present.":
        "pick_options возвращает {'1': ''}, когда отсутствуют и channels, и global.",
    "pick_options falls back to global when channel is an empty string.":
        "pick_options использует global, когда channel — пустая строка.",
    "OptionsParser.parse_file reads a real options.json and returns correct mapping.":
        "OptionsParser.parse_file читает реальный options.json и возвращает корректное отображение.",
    "OptionsParser.parse_file handles a file with one empty-string option without error.":
        "OptionsParser.parse_file обрабатывает файл с одной пустой опцией без ошибок.",

    # ── steps/test_conan_step.py ────────────────────────────────────────────
    "Unit tests for autodoc/parser/steps/conan_step.py.":
        "Юнит-тесты для autodoc/parser/steps/conan_step.py.",
    "Controllable fake fetcher for ConanEnrichStep unit tests.":
        "Управляемый фейковый fetcher для юнит-тестов ConanEnrichStep.",
    "\n        Args:\n            value: The ConanEnrichmentResult to return from fetch().\n            warnings: Optional list of warning strings.":
        "\n        Args:\n            value: ConanEnrichmentResult, возвращаемый из fetch().\n            warnings: Необязательный список строк предупреждений.",
    "Record that configure was called.":
        "Записывает факт вызова configure.",
    "Return controlled FetchResult.":
        "Возвращает управляемый FetchResult.",
    "ctx.intermediate['conan_report'] is populated after execute.":
        "ctx.intermediate['conan_report'] заполняется после execute.",
    "ConanEnrichStep is a non-critical pipeline step.":
        "ConanEnrichStep является некритичным шагом пайплайна.",
    "Warnings from the fetcher do not cause an exception.":
        "Предупреждения от fetcher не вызывают исключений.",

    # ── steps/test_docker_step.py ───────────────────────────────────────────
    "Unit tests for autodoc/parser/steps/docker_step.py.":
        "Юнит-тесты для autodoc/parser/steps/docker_step.py.",
    "Controllable fake fetcher for DockerResolveStep unit tests.":
        "Управляемый фейковый fetcher для юнит-тестов DockerResolveStep.",
    "\n        Args:\n            value: The docker links map to return from fetch().\n            warnings: Optional list of warning strings.":
        "\n        Args:\n            value: Карта docker-ссылок, возвращаемая из fetch().\n            warnings: Необязательный список строк предупреждений.",
    "ctx.intermediate['docker_links'] is populated with the fetcher result.":
        "ctx.intermediate['docker_links'] заполняется результатом fetcher.",
    "DataEnricher.apply_docker_links adds a ProfileDefinition entry for the component's profile.":
        "DataEnricher.apply_docker_links добавляет запись ProfileDefinition для профиля компонента.",
    "DockerResolveStep is a non-critical pipeline step.":
        "DockerResolveStep является некритичным шагом пайплайна.",

    # ── steps/test_finalize_step.py ─────────────────────────────────────────
    "Unit tests for autodoc/parser/steps/finalize_step.py.":
        "Юнит-тесты для autodoc/parser/steps/finalize_step.py.",
    "Create a ConanVariant with the null (header-only) package_id.":
        "Создаёт ConanVariant с нулевым (только заголовок) package_id.",
    "Create a ConanVariant with a non-null package_id.":
        "Создаёт ConanVariant с ненулевым package_id.",
    "Build a minimal Release with the given profile_builds.":
        "Строит минимальный Release с заданными profile_builds.",
    "Build a minimal Component wrapping a single Release.":
        "Строит минимальный Component, оборачивающий один Release.",
    "is_header_only is True when all variants across all profiles have the null package_id.":
        "is_header_only равен True, когда все варианты всех профилей имеют нулевой package_id.",
    "is_header_only is False when at least one variant has a real package_id.":
        "is_header_only равен False, когда хотя бы один вариант имеет реальный package_id.",
    "is_header_only is False when a release has no variants at all.":
        "is_header_only равен False, когда у релиза нет вариантов вообще.",
    "ProfileBuild entries with exists=False are removed during finalization.":
        "Записи ProfileBuild с exists=False удаляются в процессе финализации.",
    "Components are sorted alphabetically by name (case-insensitive) after finalization.":
        "Компоненты сортируются алфавитно по имени (без учёта регистра) после финализации.",
    "ProfileDefinition entries with the same profile_name are deduplicated (last-write-wins).":
        "Записи ProfileDefinition с одинаковым profile_name дедуплицируются (побеждает последняя запись).",
    "ctx.result is populated with a valid ParsedResult after execute.":
        "ctx.result заполняется корректным ParsedResult после execute.",
    "_build_result wraps a Pydantic ValidationError into a ParsingError.":
        "_build_result оборачивает Pydantic ValidationError в ParsingError.",

    # ── steps/test_manifest_step.py ─────────────────────────────────────────
    "Unit tests for autodoc/parser/steps/manifest_step.py.":
        "Юнит-тесты для autodoc/parser/steps/manifest_step.py.",
    "Controllable fake fetcher for ManifestStep unit tests.":
        "Управляемый фейковый fetcher для юнит-тестов ManifestStep.",
    "\n        Args:\n            value: The component list to return from fetch().\n            warnings: Optional list of warning strings.":
        "\n        Args:\n            value: Список компонентов, возвращаемый из fetch().\n            warnings: Необязательный список строк предупреждений.",
    "Happy path: ctx.components is populated from fetcher result.":
        "Успешный путь: ctx.components заполняется из результата fetcher.",
    "Warnings from fetcher are passed through without raising an exception.":
        "Предупреждения от fetcher передаются без вызова исключений.",
    "configure() is called on the fetcher before execute() returns.":
        "configure() вызывается на fetcher до завершения execute().",
    "ManifestStep.name is set and non-empty.":
        "ManifestStep.name задан и не пуст.",
    "ManifestStep is a critical pipeline step.":
        "ManifestStep является критичным шагом пайплайна.",

    # ── steps/test_options_step.py ──────────────────────────────────────────
    "Unit tests for autodoc/parser/steps/options_step.py.":
        "Юнит-тесты для autodoc/parser/steps/options_step.py.",
    "Controllable fake fetcher for OptionsResolveStep unit tests.":
        "Управляемый фейковый fetcher для юнит-тестов OptionsResolveStep.",
    "\n        Args:\n            value: The options map to return from fetch().\n            warnings: Optional list of warning strings.":
        "\n        Args:\n            value: Карта опций, возвращаемая из fetch().\n            warnings: Необязательный список строк предупреждений.",
    "ctx.intermediate['options_map'] is populated with the fetcher result.":
        "ctx.intermediate['options_map'] заполняется результатом fetcher.",
    "DataEnricher.apply_options is called: matching component release gets build_option_sets.":
        "DataEnricher.apply_options вызывается: совпадающий релиз компонента получает build_option_sets.",
    "OptionsResolveStep is a non-critical pipeline step.":
        "OptionsResolveStep является некритичным шагом пайплайна.",

    # ── steps/test_validation_step.py ──────────────────────────────────────
    "Unit tests for autodoc/parser/steps/validation_step.py.":
        "Юнит-тесты для autodoc/parser/steps/validation_step.py.",
    "Build a minimal Component → Release → ProfileBuild → ConanVariant tree.":
        "Строит минимальное дерево Component → Release → ProfileBuild → ConanVariant.",
    "Fake Artifactory client that records head() calls and returns a fixed status.":
        "Фейковый клиент Artifactory, записывающий вызовы head() и возвращающий фиксированный статус.",
    "\n        Args:\n            status_code: HTTP status code to return.\n        ":
        "\n        Args:\n            status_code: Возвращаемый HTTP-код статуса.\n        ",
    "Record the URL and return configured response.":
        "Записывает URL и возвращает настроенный ответ.",
    "Fake Artifactory client whose head() always raises RequestException.":
        "Фейковый клиент Artifactory, чей head() всегда вызывает RequestException.",
    "Raise a network error unconditionally.":
        "Безусловно вызывает сетевую ошибку.",
    "A variant whose build_url returns HTTP 404 is removed from pb.variants.":
        "Вариант, чей build_url возвращает HTTP 404, удаляется из pb.variants.",
    "A variant whose build_url returns HTTP 200 is kept in pb.variants.":
        "Вариант, чей build_url возвращает HTTP 200, остаётся в pb.variants.",
    "The UI URL is transformed to an API URL before calling client.head().":
        "UI URL преобразуется в API URL перед вызовом client.head().",
    "A network exception during HEAD check does not remove the variant (fail-open).":
        "Сетевое исключение во время проверки HEAD не удаляет вариант (fail-open).",
    "A variant with an empty build_url is not checked at all (head() never called).":
        "Вариант с пустым build_url не проверяется вообще (head() никогда не вызывается).",
    "When artifactory_client is None, the step completes without exception.":
        "Когда artifactory_client равен None, шаг завершается без исключений.",
    "_collect_variants gathers all variants across all components and profiles.":
        "_collect_variants собирает все варианты по всем компонентам и профилям.",

    # ── test_parser.py ──────────────────────────────────────────────────────
    "Unit tests for autodoc/parser/parser.py (ComponentParser).":
        "Юнит-тесты для autodoc/parser/parser.py (ComponentParser).",
    "Fake pipeline step that records execution order and optionally raises.":
        "Фейковый шаг пайплайна, записывающий порядок выполнения и опционально вызывающий исключение.",
    "\n        Args:\n            side_effect: Exception to raise when execute() is called. None → no-op.\n        ":
        "\n        Args:\n            side_effect: Исключение для вызова при execute(). None → нет действий.\n        ",
    "Execute fake step; optionally raise a configured exception.":
        "Выполняет фейковый шаг; опционально вызывает настроенное исключение.",
    "Fake FinalizeStep that populates ctx.result with a minimal ParsedResult.":
        "Фейковый FinalizeStep, заполняющий ctx.result минимальным ParsedResult.",
    "Populate ctx.result with a minimal valid ParsedResult.":
        "Заполняет ctx.result минимальным корректным ParsedResult.",
    "Non-critical step that always raises ParsingError.":
        "Некритичный шаг, всегда вызывающий ParsingError.",
    "Always raise to simulate a non-critical failure.":
        "Всегда вызывает исключение для имитации некритичного сбоя.",
    "Happy path: parse() returns a ParsedResult when FakeFinalize populates ctx.result.":
        "Успешный путь: parse() возвращает ParsedResult, когда FakeFinalize заполняет ctx.result.",
    "A critical step failure raises ParsingError and subsequent steps are not executed.":
        "Сбой критичного шага вызывает ParsingError, последующие шаги не выполняются.",
    "A non-critical step failure is swallowed and the pipeline continues to completion.":
        "Сбой некритичного шага поглощается, и пайплайн продолжает работу до завершения.",
    "The tmp_dir is removed after a successful parse (finally block).":
        "tmp_dir удаляется после успешного парсинга (блок finally).",
    "The tmp_dir is removed even when a critical step raises (finally block).":
        "tmp_dir удаляется даже когда критичный шаг вызывает исключение (блок finally).",
    "If no step populates ctx.result, parse() raises ParsingError after all steps complete.":
        "Если ни один шаг не заполняет ctx.result, parse() вызывает ParsingError после завершения всех шагов.",
    "with_steps_excluded factory method removes all instances of the specified step class.":
        "Фабричный метод with_steps_excluded удаляет все экземпляры указанного класса шагов.",
    "When a tfs_client is injected via constructor, TFSClient.__init__ is never called.":
        "Когда tfs_client передаётся через конструктор, TFSClient.__init__ никогда не вызывается.",
    "parse(save_intermediate=True) writes at least one JSON file into the intermediate dir.":
        "parse(save_intermediate=True) записывает хотя бы один JSON-файл в директорию intermediate.",

    # ── test_pipeline.py ────────────────────────────────────────────────────
    "Unit tests for autodoc/parser/pipeline/context.py and BaseParseStep.":
        "Юнит-тесты для autodoc/parser/pipeline/context.py и BaseParseStep.",
    "PipelineContext initializes with empty components and result=None.":
        "PipelineContext инициализируется с пустыми components и result=None.",
    "to_snapshot_dict omits 'docker_links' from intermediate but reports its count.":
        "to_snapshot_dict исключает 'docker_links' из intermediate, но сообщает его количество.",
    "to_snapshot_dict includes components_count matching len(ctx.components).":
        "to_snapshot_dict включает components_count, равный len(ctx.components).",
    "to_snapshot_dict converts tuple keys in intermediate dicts to string representations.":
        "to_snapshot_dict преобразует ключи-кортежи в промежуточных словарях в строковые представления.",
    "Defining a BaseParseStep subclass with an empty name raises TypeError at class definition.":
        "Определение подкласса BaseParseStep с пустым именем вызывает TypeError при определении класса.",
    "Step with empty name — should raise at class definition.":
        "Шаг с пустым именем — должен вызывать исключение при определении класса.",
    "No-op execute for the bad step.":
        "Пустой execute для некорректного шага.",
}

# ── Comment translations (raw text after #) ─────────────────────────────────
COMMENT_TRANS = {
    # general
    "# Module-level constants": "# Константы уровня модуля",
    "# Constants": "# Константы",
    "# Helpers": "# Вспомогательные функции",
    "# Helper": "# Вспомогательная функция",
    "# Local fixtures": "# Локальные фикстуры",
    "# Local helpers / fixtures": "# Локальные вспомогательные функции / фикстуры",
    "# Local fake TFS client": "# Локальный фейковый TFS-клиент",
    "# Local fake clients": "# Локальные фейковые клиенты",
    "# Local fake clients — defined here, NOT in conftest (per ownership rules)": "# Локальные фейковые клиенты — определены здесь, НЕ в conftest (по правилам владения)",
    "# Local fake TFS clients": "# Локальные фейковые TFS-клиенты",
    "# Fake Fetcher": "# Фейковый Fetcher",
    "# Fake pipeline steps": "# Фейковые шаги пайплайна",
    "# Fake Artifactory client (used by validation_step tests)": "# Фейковый клиент Artifactory (используется в тестах validation_step)",
    "# Tests": "# Тесты",
    "# Tests: PipelineContext": "# Тесты: PipelineContext",
    "# Tests: BaseParseStep": "# Тесты: BaseParseStep",
    "# Sentinel empty result used across tests": "# Сигнальный пустой результат, используемый в тестах",
    "# Config / path fixtures": "# Фикстуры конфигурации / путей",
    "# Pipeline context fixture (used by steps/ and test_pipeline.py)": "# Фикстура контекста пайплайна (используется в steps/ и test_pipeline.py)",
    "# Component / Release fixtures (shared across steps/, enrichment/, test_pipeline.py)": "# Фикстуры Component / Release (общие для steps/, enrichment/, test_pipeline.py)",
    "# Minimal concrete subclass used only in these tests": "# Минимальный конкретный подкласс, используемый только в этих тестах",
    "# Shared properties content (platform 2.0-tech, component \"openssl\")": "# Общее содержимое properties (платформа 2.0-tech, компонент \"openssl\")",
    # inline
    "# graph_info_missing.json targets libyang": "# graph_info_missing.json нацелен на libyang",
    "# _build_option_sets_internal is empty by default": "# _build_option_sets_internal пуст по умолчанию",
    "# cmd contains [..., \"-o\", \"*:shared=True\", ...]": "# cmd содержит [..., \"-o\", \"*:shared=True\", ...]",
    "# Ensure no double-wildcarded variant exists": "# Убеждаемся, что дважды замаскированный вариант отсутствует",
    "# Use a full path whose basename matches the stored profile name": "# Используем полный путь, basename которого совпадает с именем сохранённого профиля",
    "# no duplicate created": "# дубликат не создаётся",
    "# The profile entry is always upserted; docker_image is empty when the": "# Запись профиля всегда обновляется/вставляется; docker_image пуст, если",
    "# profile name is absent from docker_links.": "# имя профиля отсутствует в docker_links.",
    "# New profile_data carries empty conan_settings": "# Новый profile_data содержит пустые conan_settings",
    "# A well-formed TFS URL that contains /_git/ so DockerFetcher does not skip it.": "# Корректный TFS URL, содержащий /_git/, чтобы DockerFetcher его не пропустил.",
    "# query parameters: path (YAML file path) and version (branch prefixed with GB).": "# параметры запроса: path (путь к YAML-файлу) и version (ветка с префиксом GB).",
    "# no-op: writes nothing": "# заглушка: ничего не записывает",
    "# Path constants that satisfy OptionsParser's path filters:": "# Константы путей, удовлетворяющие фильтрам путей OptionsParser:",
    "#   - must end with \"options.json\"": "#   - должны заканчиваться на \"options.json\"",
    "#   - must contain \"/conan/\"": "#   - должны содержать \"/conan/\"",
    "#   - must contain \"/ci-2.0/\" for the CI-prefix selection": "#   - должны содержать \"/ci-2.0/\" для выбора CI-префикса",
    "# No crash; the key exists with the default fallback value.": "# Без исключений; ключ существует со значением запасного варианта.",
    "# Fetcher must not raise; the release key must still be present.": "# Fetcher не должен вызывать исключений; ключ релиза должен присутствовать.",
    "# must not raise": "# не должен вызывать исключений",
    "# manifest_component has profile_name=\"hw-linux-x86_64-gcc10_2\"": "# manifest_component имеет profile_name=\"hw-linux-x86_64-gcc10_2\"",
    "# Create a real pydantic.ValidationError instance to use as side_effect": "# Создаём реальный экземпляр pydantic.ValidationError для использования как side_effect",
    "# type: ignore[arg-type]": "# type: ignore[arg-type]",  # keep as-is
    "# Key must match the fixture: name=\"openssl\", version=\"1.0.0\", channel=\"tech\"": "# Ключ должен совпадать с фикстурой: name=\"openssl\", version=\"1.0.0\", channel=\"tech\"",
    "# Build 2 components × 2 profiles × 1 variant each → 4 collected": "# Строим 2 компонента × 2 профиля × 1 вариант каждый → 4 собранных",
    "# falsy → __init_subclass__ raises": "# ложное значение → __init_subclass__ вызывает исключение",
    # apply_ section markers
    "# apply_options — 4.1": "# apply_options",
    "# apply_docker_links — 4.4": "# apply_docker_links",
    "# apply_conan_results — 4.7": "# apply_conan_results",
}

# Numbered section patterns to strip number from (after translating the body)
# e.g. "# 1.1 — text" → "# text"  (strip "N.N — " prefix)


def strip_number_prefix(text: str) -> str:
    """Remove leading 'N.N — ' or 'N.N — ' from a comment line."""
    return re.sub(r'^(# )\d+\.\d+ — ', r'\1', text)


def translate_comment(tok_str: str) -> str:
    """Translate a comment token (including the leading #)."""
    # Exact match first
    if tok_str in COMMENT_TRANS:
        result = COMMENT_TRANS[tok_str]
    else:
        result = tok_str
    # Strip numbered prefix
    result = strip_number_prefix(result)
    return result


def translate_docstring_value(val: str) -> str:
    """Translate a raw docstring value (no quotes)."""
    if val in TRANS:
        return TRANS[val]
    return val


# ── Tokenize-based replacement ───────────────────────────────────────────────

def get_docstring_linenos(source: str) -> set:
    """Return set of (lineno, col_offset) for all docstring nodes."""
    positions = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return positions
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                positions.add((node.body[0].lineno, node.body[0].col_offset))
    return positions


def process_file(filepath: Path) -> None:
    source = filepath.read_text("utf-8")
    if not source.strip():
        return

    docstring_positions = get_docstring_linenos(source)

    # Collect replacements: list of (start_offset, end_offset, new_text)
    replacements = []

    lines = source.splitlines(keepends=True)
    line_offsets = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    def pos_to_offset(row, col):
        return line_offsets[row - 1] + col

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            start = pos_to_offset(*tok.start)
            end = pos_to_offset(*tok.end)
            translated = translate_comment(tok.string)
            if translated != tok.string:
                replacements.append((start, end, translated))
            else:
                # Maybe just strip number prefix even if not in dict
                stripped = strip_number_prefix(tok.string)
                if stripped != tok.string:
                    replacements.append((start, end, stripped))

        elif tok.type == tokenize.STRING:
            if (tok.start[0], tok.start[1]) in docstring_positions:
                start = pos_to_offset(*tok.start)
                end = pos_to_offset(*tok.end)
                # Reconstruct: detect quote style
                raw = tok.string
                for q in ('"""', "'''", '"', "'"):
                    if raw.startswith(q):
                        quote = q
                        break
                else:
                    continue
                inner = raw[len(quote):-len(quote)]
                translated_inner = translate_docstring_value(inner)
                if translated_inner != inner:
                    new_raw = quote + translated_inner + quote
                    replacements.append((start, end, new_raw))

    # Apply replacements from end to start
    replacements.sort(key=lambda x: x[0], reverse=True)
    result = source
    for start, end, new_text in replacements:
        result = result[:start] + new_text + result[end:]

    filepath.write_text(result, "utf-8")


if __name__ == "__main__":
    py_files = sorted(Path('/home/claude/tests').rglob('*.py'))
    for fp in py_files:
        process_file(fp)
        print(f"OK: {fp}")
    print("Done!")
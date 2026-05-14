# Use Case → Test Mapping

Maps business use case labels to the test functions that verify them.
Update this file whenever a UC label is added or a test is renamed.

## Parser — Conan

| UC Label | Description | Test File | Test Function |
|---|---|---|---|
| UC-G-1 | Header-only component: NULL_PACKAGE_ID is the SHA1 of empty string | tests/unit/parser/conan/test_result_parser.py | test_result_parser_nlohmann_json_package_id_equals_null_sha1 |
| UC-G-2 | Two versions, same channel: patchelf 0.16.1 matches the same graph node as 0.18.0 | tests/unit/parser/conan/test_result_parser.py | test_result_parser_patchelf_016_version_uses_same_channel |
| UC-G-3 | Standard component, one version per channel: sqlite3 fast base_ref format is correct | tests/unit/parser/conan/test_result_parser.py | test_result_parser_sqlite3_fast_base_ref_format |
| UC-G-4 | Pure fast channel component with no transitive dependencies: apr/1.7.6 | tests/unit/parser/conan/test_result_parser.py | test_result_parser_apr_has_no_dependencies |
| UC-G-5 | Dependencies: libnetfilter_queue dependency names are plain (no version or @) | tests/unit/parser/conan/test_result_parser.py | test_result_parser_libnetfilter_queue_deps_are_plain_names |
| UC-G-6 | Binary=Missing: parse() returns None when the target node has binary='Missing' (poco) | tests/unit/parser/conan/test_result_parser.py | test_result_parser_poco_missing_binary_returns_none |
| UC-G-7 | Version-range resolution error: stunnel returns None and error message is preserved | tests/unit/parser/conan/test_result_parser.py, tests/unit/parser/conan/test_result_aggregator.py | test_result_parser_stunnel_error_graph_returns_none, test_aggregator_records_version_range_error_message |

## Parser — Manifest

| UC Label | Description | Test File | Test Function |
|---|---|---|---|
| UC-M-1 | Header-only component, single fast channel | tests/unit/parser/parsers/test_manifest_parser.py, tests/unit/parser/fetchers/test_manifest_fetcher.py | (see UC-M-1 comment blocks) |
| UC-M-2 | Component built purely in one channel (fast) | tests/unit/parser/parsers/test_manifest_parser.py | (see UC-M-2 comment block) |
| UC-M-3 | Component with two versions in one channel (tech) | tests/unit/parser/parsers/test_manifest_parser.py, tests/unit/parser/fetchers/test_manifest_fetcher.py | (see UC-M-3 comment blocks) |
| UC-M-4 | Standard component built in two channels (fast + slow) | tests/unit/parser/parsers/test_manifest_parser.py, tests/unit/parser/steps/test_options_step.py | (see UC-M-4 comment blocks) |
| UC-M-5 | Component from another team's TFS repository (read-only access) | tests/unit/parser/parsers/test_manifest_parser.py, tests/unit/parser/fetchers/test_manifest_fetcher.py, tests/unit/parser/steps/test_options_step.py | (see UC-M-5 comment blocks) |

## Parser — Options

| UC Label | Description | Test File | Test Function |
|---|---|---|---|
| UC-O-1 | Only ci-1.6 present (fallback) OR only ci-2.0 present | tests/unit/parser/parsers/test_options_parser.py, tests/unit/parser/fetchers/test_options_fetcher.py | (see UC-O-1 comment blocks) |
| UC-O-2 | ci-2.0 / ci-1.6 with channel sub-directories (fast/slow) | tests/unit/parser/parsers/test_options_parser.py, tests/unit/parser/fetchers/test_options_fetcher.py | (see UC-O-2 comment blocks) |
| UC-O-3 | Flat options.json (no channel sub-directory) | tests/unit/parser/parsers/test_options_parser.py | (see UC-O-3 comment block) |

## Publisher

*(Add UC labels as they are introduced)*

---

*To add a new UC: (1) add a row here, (2) add a `# UC-X-N` comment
above the corresponding test function.*

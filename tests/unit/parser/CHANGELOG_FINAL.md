# CHANGELOG_FINAL — `tests/unit/parser` Remediation (Parts 1–6)

> **Note on scope of this document.** Only the archive delivered at the end
> of Part 5 (containing Parts 1–5's changes already applied) was available
> as the starting point for Part 6. The individual `CHANGELOG_PART_1.md`
> through `CHANGELOG_PART_5.md` files were **not** included in that archive
> and so could not be merged verbatim into this document. This file
> therefore documents **Part 6 in full detail** (the 4 files in scope for
> this part, plus the pool-wide sweeps), and lists the **29 files of the
> full pool** so a reviewer can see what the complete deliverable covers.
> Anyone holding the Part 1–5 changelogs should append them above this
> section to get the complete per-part history; nothing in Part 6
> contradicts or reverts earlier parts' work.

---

## Part 6 of 6 (this part) — Detailed Changes

### 1. `test_parser.py`

**Removed:**
- `test_component_parser_with_steps_excluded_removes_step_class` — removed
  in favor of `test_with_steps_excluded_removes_class_not_instance` (kept in
  `test_pipeline_failures.py`). Confirmed by direct comparison: the kept
  version asserts both the absence of `ConanEnrichStep` **and** that the
  total step count dropped by exactly one, i.e. strictly more coverage than
  the removed test, which only asserted absence.

**Markers:** no marker corrections needed for this file beyond the above.

**Added (missing scenarios on `ComponentParser`):**
- `test_component_parser_save_intermediate_oserror_logged_not_raised`
  (`infrastructure`) — asserts `_save_intermediate`'s own `OSError` handling
  is caught and logged, not propagated, by patching `Path.write_text` to
  raise `OSError` and confirming `parse(save_intermediate=True)` still
  returns a `ParsedResult`.
- `test_component_parser_default_pipeline_step_order` (`contract`) —
  asserts `_default_pipeline()` returns steps in the documented order
  Manifest → Options → Conan → Docker → Validation → Finalize. This guards
  a real regression risk (silent step reordering) that had zero direct
  coverage before.
- `test_component_parser_uses_injected_artifactory_client`
  (`infrastructure`) — symmetric counterpart to the existing
  `test_component_parser_uses_injected_tfs_client`; patches
  `ArtifactoryClient.__init__` and asserts it's never called when an
  `artifactory_client` is injected via the constructor.

### 2. `test_pipeline.py`

**Ambiguous markers — resolved:**
- `test_pipeline_context_construction` — left as `contract`, no change (it
  guards the mutable-default-argument bug class despite being tautological
  with dataclass defaults).
- `test_pipeline_context_snapshot_includes_components_count` — kept as
  `business_logic` (no marker change), for consistency with its sibling
  `test_pipeline_context_snapshot_excludes_docker_links` in the same file:
  both describe the same contractual behavior of `to_snapshot_dict()` (what
  ends up in the diagnostic snapshot), even though the `components_count`
  implementation itself is a plain `len()`. A short comment documenting this
  reasoning was added to the docstring.

**Added (missing scenario on `PipelineContext.to_snapshot_dict`):**
- `test_pipeline_context_snapshot_handles_non_dict_intermediate`
  (`business_logic`) — deliberate positive-case test asserting a non-dict
  value stored in `ctx.intermediate` passes through `to_snapshot_dict()`
  unchanged. (Observation: the production code already handled this
  correctly via its `else` branch — this was a coverage gap, not a bug.)

No removals in this file.

### 3. `test_pipeline_failures.py`

**Removed (redundant):**
- `test_manifest_step_failure_stops_pipeline_no_result` — 3-way redundant
  with `test_critical_failure_stops_pipeline` (same file) and
  `test_component_parser_critical_step_failure_raises_parsing_error`
  (`test_parser.py`).
- `test_finalize_step_failure_stops_pipeline` — minor positional variant of
  the same redundant cluster.
- `test_tmp_dir_cleaned_up_in_finally_block_on_error` — redundant with
  `test_component_parser_cleans_up_tmp_dir_on_failure` (`test_parser.py`).

**Removed (synthetic-fake cluster, converted to real integration coverage
instead of keeping one):**
- `test_conan_step_failure_pipeline_continues`
- `test_docker_step_failure_pipeline_continues`
- `test_options_step_failure_pipeline_continues`
- `test_validation_step_failure_pipeline_continues`

  **Judgment call:** the spec allowed keeping one of these four (converted
  to a real-step integration test) or removing all four in favor of new
  real coverage in `test_pipeline_integration.py`. All four were removed:
  the four synthetic fakes (named after real steps but not exercising them)
  added no coverage beyond
  `test_component_parser_non_critical_step_failure_continues` /
  `test_non_critical_failure_does_not_block_next_step`, and the new
  `test_full_pipeline_raises_parsing_error_when_no_manifests_found` in
  `test_pipeline_integration.py` (see below) now supplies real,
  production-step coverage of a critical-step failure propagating through
  the actual pipeline, which is a strictly stronger replacement for this
  cluster's intent.

**Rewritten (dead code removed):**
- `test_non_critical_failure_does_not_block_next_step` — previously built
  three separate `steps`/`parser` pairs (`steps`, `steps2`, `steps3`), of
  which only the third (`steps3`/`parser3`) was ever executed and asserted
  on; the first two were dead code, and the function contained narrative
  Russian "debugging diary" comments describing why the test was structured
  this way. Rewritten to contain only the working `steps3` scenario
  (renamed to `steps`/`parser`), with one short Russian docstring sentence
  and no narrative comments.

**Kept as-is:**
- `test_with_steps_excluded_removes_class_not_instance` — confirmed as the
  version kept per the `test_parser.py` cross-reference; no changes needed.

### 4. `test_pipeline_integration.py`

**Same-file DRY dedup:**
- Removed the unused `_AlwaysOkArtifactoryClient` nested inside
  `_make_parser_with_real_steps`; the module-level `_AlwaysOkArtifactoryClient`
  (defined later in the file, near the `BL-E2E` tests) was already the one
  actually referenced and used. Not extracted to `conftest.py` per the
  spec — this was a same-file duplicate, already fine at module level once
  the nested copy was deleted.

**Added (missing scenarios, integration-level, real production pipeline):**
- `test_full_pipeline_raises_parsing_error_when_no_manifests_found`
  (`integration`) — a real critical-step failure (the real `ManifestFetcher`
  raising `ParsingError` when it finds zero `.properties` files after
  `download_properties()` copies nothing) propagating through the actual
  production step chain end-to-end. Uses the plain `FakeTFSClient` (which
  is a no-op on `download_properties`) rather than `CopyingAllFakeTFSClient`,
  so the manifests directory the fetcher inspects is genuinely empty. This
  is the intended real-coverage replacement for the four synthetic tests
  removed from `test_pipeline_failures.py` above.
- `test_full_pipeline_save_intermediate_writes_real_files` (`integration`) —
  `save_intermediate=True` exercised through the real 6-step production
  pipeline (previously only unit-tested with fake steps in `test_parser.py`).
  Asserts exactly 6 snapshot JSON files are written, one per real step.
- `test_full_pipeline_removes_dead_variant_on_404` (`integration`) — patches
  `ConanFetcher.fetch` to attach a `ConanVariant` with a `build_url` to one
  `patchelf` profile build, and supplies an Artifactory client stub that
  returns HTTP 404 specifically for that URL (200 for everything else).
  Asserts the dead variant is absent from `pb.variants` after the real
  `ArtifactoryValidationStep` runs, while the owning component/profile
  build survives (`exists=True`, so `FinalizeStep` doesn't prune it). The
  existing fake Artifactory client in this file always returns 200, so this
  path (`ArtifactoryValidationStep._remove_dead_variants`) had no full-pipeline
  coverage before this test.

No removals flagged for this file beyond the same-file dedup above.

### Pool-wide sweeps (Workflow steps 5–6, authorized exceptions to the
4-file scope for this part)

- **Stray-file sweep:** `find tests/unit/parser -name '*.backup' -o -name
  '*.bak' -o -name '*.orig'` returned nothing. The one confirmed stray file
  from this pool (`parsers/test_manifest_parser.py.backup`) was already
  removed in Part 4; no further stray files were found.
- **`__init__.py` emptiness sweep:** every `__init__.py` under
  `tests/unit/parser/**` (8 files: `parser/`, `parsers/`, `enrichment/`,
  `fetchers/`, `conan/`, `clients/`, `steps/`, `utils/`) was checked and
  confirmed completely empty (0 bytes). No changes needed.

### Final full-pool validation

`pytest tests/unit/parser -v` was run as the final check. **376 tests
passed; 3 pre-existing failures remain, all in files outside this part's
scope** (and outside all of Parts 1–6's assigned file lists, since they
sit in `clients/` and `fetchers/`, whose remediation was covered by earlier
parts):

- `tests/unit/parser/clients/test_artifactory_client.py::test_artifactory_client_head_disables_ssl_verification`
  — asserts `client.session.verify is False`, but the actual session's
  `verify` attribute is `True` in this environment. **Found bug, not
  fixed** (per Guardrails: do not change `autodoc/parser/**` production
  behavior to make a test pass, and this file is outside Part 6's scope to
  edit). Needs investigation into whether `ArtifactoryClient`/`RetryableSession`
  actually disables SSL verification as documented, or whether the test's
  expectation is stale.
- `tests/unit/parser/fetchers/test_conan_fetcher.py::test_conan_fetcher_returns_empty_on_empty_component_list`
  and `::test_conan_fetcher_aggregation_errors_in_result` — both fail with
  `NameError: name 'ConanEnrichmentResult' is not defined`; the symbol is
  used in the test body but never imported. **Found bug, not fixed** — this
  file is outside Part 6's scope (not one of the 4 files listed for this
  part), so per Guardrails it was left as-is and is flagged here for a
  human reviewer to route to whichever earlier part owns
  `tests/unit/parser/fetchers/test_conan_fetcher.py`.

These three failures pre-date Part 6 and were not introduced by any change
in this part — none of the edits above touch `clients/` or `fetchers/`.

---

## Full pool — file list (all 29 files)

The following files make up the complete `tests/unit/parser/**` remediation
pool referenced across Parts 1–6. Files marked **(Part 6)** are detailed
above; all others were remediated in Parts 1–5, whose individual changelogs
were not available to merge into this document (see note at the top).

1. `tests/unit/parser/test_parser.py` — **(Part 6)**
2. `tests/unit/parser/test_pipeline.py` — **(Part 6)**
3. `tests/unit/parser/test_pipeline_failures.py` — **(Part 6)**
4. `tests/unit/parser/test_pipeline_integration.py` — **(Part 6)**
5. `tests/unit/parser/test_cli.py` *(Parts 1–5 — see prior changelogs)*
6. `tests/unit/parser/test_config_manager.py` *(Parts 1–5)*
7. `tests/unit/parser/clients/test_artifactory_client.py` *(Parts 1–5 — see
   Observation above: one test currently fails in this environment)*
8. `tests/unit/parser/clients/test_tfs_client.py` *(Parts 1–5)*
9. `tests/unit/parser/conan/test_conan2_result_parser.py` *(Parts 1–5)*
10. `tests/unit/parser/conan/test_result_aggregator.py` *(Parts 1–5)*
11. `tests/unit/parser/enrichment/test_data_enricher.py` *(Parts 1–5)*
12. `tests/unit/parser/fetchers/conftest.py` *(Parts 1–5, shared fixtures
    created in Part 3)*
13. `tests/unit/parser/fetchers/test_conan_fetcher.py` *(Parts 1–5 — see
    Observation above: two tests currently fail with `NameError` in this
    environment, likely a missing import)*
14. `tests/unit/parser/fetchers/test_manifest_fetcher.py` *(Parts 1–5)*
15. `tests/unit/parser/parsers/test_manifest_parser.py` *(Parts 1–5; the
    stray `test_manifest_parser.py.backup` sibling was deleted in Part 4)*
16. `tests/unit/parser/steps/conftest.py` *(Parts 1–5)*
17. `tests/unit/parser/steps/test_conan_step.py` *(Parts 1–5)*
18. `tests/unit/parser/steps/test_docker_step.py` *(Parts 1–5)*
19. `tests/unit/parser/steps/test_finalize_step.py` *(Parts 1–5)*
20. `tests/unit/parser/steps/test_manifest_step.py` *(Parts 1–5)*
21. `tests/unit/parser/steps/test_options_step.py` *(Parts 1–5)*
22. `tests/unit/parser/steps/test_validation_step.py` *(Parts 1–5)*
23. `tests/unit/parser/utils/test_properties_reader.py` *(Parts 1–5)*
24. `tests/unit/parser/conftest.py` *(Parts 1–5, shared root fixtures)*
25–29. Remaining `__init__.py` files across `parser/`, `parsers/`,
    `enrichment/`, `fetchers/`, `conan/`, `clients/`, `steps/`, `utils/`
    packages *(confirmed empty in this part's pool-wide sweep, see above)*.

> If the individual Part 1–5 changelogs are located, their "what was
> removed / what markers changed / what tests were added / judgment calls"
> sections should be inserted under each corresponding file entry above to
> complete this document as originally specified.

---

## Summary of judgment calls made in Part 6

| # | Item | Decision | Reasoning |
|---|---|---|---|
| 1 | `test_component_parser_with_steps_excluded_removes_step_class` vs `test_with_steps_excluded_removes_class_not_instance` | Removed the former | Confirmed strictly weaker coverage by direct comparison |
| 2 | `test_pipeline_context_snapshot_includes_components_count` marker | Kept `business_logic` | Consistency with sibling snapshot test in same file |
| 3 | Four synthetic step-failure tests in `test_pipeline_failures.py` | Removed all four (not just kept one) | Real replacement coverage added in `test_pipeline_integration.py` |
| 4 | `test_non_critical_failure_does_not_block_next_step` | Rewrote in place | Two of three step/parser triples were dead code with debugging-diary comments |
| 5 | SSL-verification test failure | Left failing, documented as found bug | Outside Part 6 file scope; must not alter production code to force a pass |
| 6 | `ConanEnrichmentResult` NameError failures | Left failing, documented as found bug | Outside Part 6 file scope (missing import in a file not on this part's list) |

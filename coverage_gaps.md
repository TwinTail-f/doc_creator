# Отчёт о пробелах в покрытии

Всего: строки 99%, ветки 98%. Файлов с пробелами: 13 из 118.

Ниже — только код вокруг непокрытых строк/веток, отсортировано от худшего покрытия к лучшему. Особое внимание — пометкам `путь ошибки (raise/except)`.

---

## `autodoc\__main__.py`
_строки: 0%, ветки: 0%, непокрытых строк: 5, непокрытых веток: 2_
Связанный тест: **не найден автоматически — проверить вручную**

### `(модульный уровень)` — строки 10-10
```python
    8: """
    9: 
   10: from autodoc.cli.app import cli  # НЕ ПОКРЫТО
   11: 
   12: 
```

### `main` — строки 13-14
```python
   11: 
   12: 
   13: def main() -> None:  # НЕ ПОКРЫТО
   14:     cli(obj={})  # НЕ ПОКРЫТО
   15: 
   16: 
```

### `(модульный уровень)` — строки 17-18
```python
   15: 
   16: 
   17: if __name__ == "__main__":  # НЕ ПОКРЫТО
   18:     main()  # НЕ ПОКРЫТО
```
- ветка 17 → выход из функции ни разу не выполнялась в тестах
- ветка 17 → 18 ни разу не выполнялась в тестах

---

## `autodoc\exceptions.py`
_строки: 77%, ветки: 100%, непокрытых строк: 3, непокрытых веток: 0_
Связанный тест: **не найден автоматически — проверить вручную**

### `ComponentParsingError.__init__` — строки 45-47
```python
   43:             original_error: Оригинальное исключение-причина (опционально).
   44:         """
   45:         self.component_name = component_name  # НЕ ПОКРЫТО
   46:         self.original_error = original_error  # НЕ ПОКРЫТО
   47:         super().__init__(f'Компонент "{component_name}": {message}')  # НЕ ПОКРЫТО
   48: 
   49: 
```

---

## `autodoc\cli\constants.py`
_строки: 85%, ветки: 100%, непокрытых строк: 2, непокрытых веток: 0_
Связанный тест: **не найден автоматически — проверить вручную**

### `(модульный уровень)` — строки 12-13
```python
   10: try:
   11:     VERSION: str = version("autodoc")
   12: except PackageNotFoundError:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   13:     VERSION = "unknown"  # НЕ ПОКРЫТО
   14: 
   15: # Имена Jinja2-шаблонов — единственный источник истины в классах стратегий
```

---

## `autodoc\parser\utils\properties_reader.py`
_строки: 90%, ветки: 85%, непокрытых строк: 3, непокрытых веток: 3_
Связанный тест: `tests\unit\parser\utils\test_properties_reader.py`

### `_logical_lines` — строки 40-43
```python
   38:                     yield line
   39:         # Последняя строка, если файл не заканчивается переводом строки
   40:         if pending:
   41:             line = pending.strip()  # НЕ ПОКРЫТО
   42:             if line and not line.startswith("#"):  # НЕ ПОКРЫТО
   43:                 yield line  # НЕ ПОКРЫТО
   44: 
   45: 
```
- ветка 40 → 41 ни разу не выполнялась в тестах
- ветка 42 → выход из функции ни разу не выполнялась в тестах
- ветка 42 → 43 ни разу не выполнялась в тестах

---

## `autodoc\config\manager.py`
_строки: 96%, ветки: 88%, непокрытых строк: 2, непокрытых веток: 4_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConfigManager.list_available_configs` — строки 104-105
```python
  102:         """
  103:         result: dict[str, list[str]] = {key: [] for key in self._EXT_TO_KEY.values()}
  104:         if not self.configs_dir.is_dir():
  105:             return result  # НЕ ПОКРЫТО
  106:         examples_path = self.configs_dir / self.EXAMPLES_SUBDIR
  107:         for item in self.configs_dir.iterdir():
```
- ветка 104 → 105 ни разу не выполнялась в тестах

### `ConfigManager.list_available_configs` — строки 107-107
```python
  105:             return result  # НЕ ПОКРЫТО
  106:         examples_path = self.configs_dir / self.EXAMPLES_SUBDIR
  107:         for item in self.configs_dir.iterdir():
  108:             if item == examples_path:  # пропускаем examples/
  109:                 continue
```
- ветка 110 → 107 ни разу не выполнялась в тестах

### `ConfigManager.list_available_configs` — строки 110-110
```python
  108:             if item == examples_path:  # пропускаем examples/
  109:                 continue
  110:             if item.is_file() and item.suffix.lower() in self.SUPPORTED_FORMATS:
  111:                 result[self._EXT_TO_KEY[item.suffix.lower()]].append(item.name)
  112:         return result
```
- ветка 110 → 107 ни разу не выполнялась в тестах

### `ConfigManager.list_example_configs` — строки 126-127
```python
  124:         if not examples_dir.is_dir():
  125:             return result
  126:         for item in examples_dir.iterdir():
  127:             if item.is_file() and item.suffix.lower() in self.SUPPORTED_FORMATS:
  128:                 result[self._EXT_TO_KEY[item.suffix.lower()]].append(item.name)
  129:         return result
```
- ветка 127 → 126 ни разу не выполнялась в тестах

### `ConfigManager._parse_file` — строки 227-228
```python
  225:             ConfigError: При любой ошибке чтения или парсинга.
  226:         """
  227:         if not filepath.is_file():
  228:             raise ConfigError(f"Путь не указывает на файл: {filepath.name}")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  229: 
  230:         try:
```
- ветка 227 → 228 ни разу не выполнялась в тестах

---

## `autodoc\models\options.py`
_строки: 97%, ветки: 88%, непокрытых строк: 0, непокрытых веток: 1_
Связанный тест: `tests\unit\parser\fetchers\test_options_fetcher.py`

### `_parse_option_str` — строки 25-26
```python
   23:     if not option_str:
   24:         return result
   25:     for part in option_str.split(","):
   26:         if "=" in part:
   27:             k, v = part.split("=", 1)
   28:             key = k.split(":")[-1].strip()
```
- ветка 26 → 25 ни разу не выполнялась в тестах

---

## `autodoc\parser\conan\conan_environment_manager.py`
_строки: 97%, ветки: 93%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConanEnvironmentManager._login_remote` — строки 133-133
```python
  131:             env=env,
  132:         )
  133:         if result.returncode != 0:
  134:             # Conan иногда пишет детали ошибки в stdout вместо stderr.
  135:             error = result.stderr.strip() or result.stdout.strip()
```
- ветка 133 → 141 ни разу не выполнялась в тестах

### `ConanEnvironmentManager._login_remote` — строки 141-141
```python
  139:                 f"(код {result.returncode}): {error}"
  140:             )
  141:         logger.info(f'Авторизация в "{remote_name}" прошла успешно.')  # НЕ ПОКРЫТО
  142: 
  143:     def _install_config(self, env: dict[str, str]) -> None:
```
- ветка 133 → 141 ни разу не выполнялась в тестах

---

## `autodoc\common\retryable_session.py`
_строки: 98%, ветки: 83%, непокрытых строк: 0, непокрытых веток: 1_
Связанный тест: `tests\unit\common\test_retryable_session.py`

### `create_pat_session` — строки 133-133
```python
  131:         timeout=timeout,
  132:     )
  133:     if token:
  134:         session.auth = (_PAT_DEFAULT_USERNAME, token)
  135:         logger.debug("Настроена PAT-аутентификация (username не задан)")
```
- ветка 133 → 136 ни разу не выполнялась в тестах

### `create_pat_session` — строки 136-136
```python
  134:         session.auth = (_PAT_DEFAULT_USERNAME, token)
  135:         logger.debug("Настроена PAT-аутентификация (username не задан)")
  136:     return session
  137: 
  138: 
```
- ветка 133 → 136 ни разу не выполнялась в тестах

---

## `autodoc\parser\enrichment\data_enricher.py`
_строки: 98%, ветки: 97%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: `tests\unit\parser\enrichment\test_data_enricher.py`

### `DataEnricher.apply_conan_results` — строки 128-129
```python
  126:                                 profile_definitions.append(entry)
  127:                             # не затираем непустые данные пустыми
  128:                             elif pb_data.conan_settings:
  129:                                 pd_map[pname].conan_settings = pb_data.conan_settings  # НЕ ПОКРЫТО
```
- ветка 128 → 129 ни разу не выполнялась в тестах

---

## `autodoc\parser\fetchers\options_fetcher.py`
_строки: 98%, ветки: 96%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: `tests\unit\parser\fetchers\test_options_fetcher.py`

### `OptionsFetcher._fetch_options_for_repo` — строки 181-182
```python
  179: 
  180:         for opt_path in options_paths:
  181:             if target_ci not in opt_path:
  182:                 continue  # НЕ ПОКРЫТО
  183:             self._load_single_options_file(items_url, opt_path, branch, target_ci, repo_data)
  184: 
```
- ветка 181 → 182 ни разу не выполнялась в тестах

---

## `autodoc\parser\conan\profile_overrides.py`
_строки: 99%, ветки: 100%, непокрытых строк: 1, непокрытых веток: 0_
Связанный тест: `tests\unit\parser\conan\test_profile_overrides.py`

### `ProfileSettingsOverrides.from_dict` — строки 103-103
```python
  101:             Заполненный экземпляр ``ProfileSettingsOverrides``.
  102:         """
  103:         return cls._parse(raw, source="<dict>")  # НЕ ПОКРЫТО
  104: 
  105:     def resolve(self, profile_name: str) -> dict[str, str]:
```

---

## `autodoc\publisher\legacy_content\html_utils.py`
_строки: 99%, ветки: 97%, непокрытых строк: 0, непокрытых веток: 1_
Связанный тест: `tests\unit\publisher\legacy_content\test_html_utils.py`

### `_parse_h2_version_sections` — строки 137-137
```python
  135: 
  136:     # Находим контент между заголовками версий
  137:     for (header, version), (next_header, _) in zip_longest(
  138:         headers, headers[1:], fillvalue=(None, None)
  139:     ):
```
- ветка 140 → 137 ни разу не выполнялась в тестах

### `_parse_h2_version_sections` — строки 140-140
```python
  138:         headers, headers[1:], fillvalue=(None, None)
  139:     ):
  140:         if content := _html_until(chain([header], header.next_siblings), next_header):
  141:             sections[version] = content
  142: 
```
- ветка 140 → 137 ни разу не выполнялась в тестах

---

## `autodoc\publisher\clients\confluence_client.py`
_строки: 99%, ветки: 95%, непокрытых строк: 0, непокрытых веток: 1_
Связанный тест: `tests\unit\publisher\clients\test_confluence_client.py`

### `ConfluenceClient._build_payload` — строки 412-412
```python
  410:             },
  411:         }
  412:         if parent_id:
  413:             payload["ancestors"] = [{"id": parent_id}]
  414:         if space:
```
- ветка 412 → 414 ни разу не выполнялась в тестах

### `ConfluenceClient._build_payload` — строки 414-414
```python
  412:         if parent_id:
  413:             payload["ancestors"] = [{"id": parent_id}]
  414:         if space:
  415:             payload["space"] = {"key": space}
  416:         return payload
```
- ветка 412 → 414 ни разу не выполнялась в тестах

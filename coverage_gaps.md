# Отчёт о пробелах в покрытии

Всего: строки 95%, ветки 90%. Файлов с пробелами: 31 из 118.

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

## `autodoc\parser\conan\result_aggregator.py`
_строки: 76%, ветки: 61%, непокрытых строк: 21, непокрытых веток: 14_
Связанный тест: `tests\unit\parser\conan\test_result_aggregator.py`

### `ConanResultAggregator._build_final_result` — строки 199-200
```python
  197:         for task in tasks:
  198:             pb_id = id(task.pb)
  199:             if pb_id in visited_pbs:
  200:                 continue  # НЕ ПОКРЫТО
  201:             visited_pbs.add(pb_id)
  202: 
```
- ветка 199 → 200 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 297-297
```python
  295:             Список ``ConanComponentReport``, упорядоченный по компонентам.
  296:         """
  297:         comp_map: dict[ReleaseKey, ConanComponentReport] = {}  # НЕ ПОКРЫТО
  298: 
  299:         for task, raw in zip(tasks, raw_results):  # НЕ ПОКРЫТО
```

### `ConanResultAggregator.build_execution_report` — строки 299-301
```python
  297:         comp_map: dict[ReleaseKey, ConanComponentReport] = {}  # НЕ ПОКРЫТО
  298: 
  299:         for task, raw in zip(tasks, raw_results):  # НЕ ПОКРЫТО
  300:             key = ReleaseKey(task.comp_name, task.version, task.channel)  # НЕ ПОКРЫТО
  301:             comp_report = comp_map.setdefault(  # НЕ ПОКРЫТО
  302:                 key,
  303:                 ConanComponentReport(
```
- ветка 299 → 300 ни разу не выполнялась в тестах
- ветка 299 → 343 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 310-310
```python
  308:             )
  309: 
  310:             profile_report = comp_report.profiles.setdefault(  # НЕ ПОКРЫТО
  311:                 task.profile_name,
  312:                 ConanProfileReport(profile_name=task.profile_name),
```

### `ConanResultAggregator.build_execution_report` — строки 315-316
```python
  313:             )
  314: 
  315:             if raw is None:  # НЕ ПОКРЫТО
  316:                 record = ConanCommandRecord(  # НЕ ПОКРЫТО
  317:                     command=" ".join(task.cmd),
  318:                     status="FAILED",
```
- ветка 315 → 316 ни разу не выполнялась в тестах
- ветка 315 → 321 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 321-324
```python
  319:                     error="Результат не получен (внутренняя ошибка).",
  320:                 )
  321:             elif raw.success:  # НЕ ПОКРЫТО
  322:                 binary_status = self._extract_binary_status(raw.data, task.comp_name)  # НЕ ПОКРЫТО
  323:                 if binary_status == "Missing":  # НЕ ПОКРЫТО
  324:                     record = ConanCommandRecord(  # НЕ ПОКРЫТО
  325:                         command=" ".join(task.cmd),
  326:                         status="BINARY_MISSING",
```
- ветка 315 → 321 ни разу не выполнялась в тестах
- ветка 321 → 322 ни разу не выполнялась в тестах
- ветка 321 → 335 ни разу не выполнялась в тестах
- ветка 323 → 324 ни разу не выполнялась в тестах
- ветка 323 → 330 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 330-330
```python
  328:                     )
  329:                 else:
  330:                     record = ConanCommandRecord(  # НЕ ПОКРЫТО
  331:                         command=" ".join(task.cmd),
  332:                         status="SUCCESS",
```
- ветка 323 → 330 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 335-335
```python
  333:                     )
  334:             else:
  335:                 record = ConanCommandRecord(  # НЕ ПОКРЫТО
  336:                     command=" ".join(task.cmd),
  337:                     status="FAILED",
```
- ветка 321 → 335 ни разу не выполнялась в тестах

### `ConanResultAggregator.build_execution_report` — строки 341-341
```python
  339:                 )
  340: 
  341:             profile_report.commands.append(record)  # НЕ ПОКРЫТО
  342: 
  343:         return list(comp_map.values())  # НЕ ПОКРЫТО
```

### `ConanResultAggregator.build_execution_report` — строки 343-343
```python
  341:             profile_report.commands.append(record)  # НЕ ПОКРЫТО
  342: 
  343:         return list(comp_map.values())  # НЕ ПОКРЫТО
  344: 
  345:     def _extract_binary_status(self, data: dict[str, Any] | None, comp_name: str) -> str:
```
- ветка 299 → 343 ни разу не выполнялась в тестах

### `ConanResultAggregator._extract_binary_status` — строки 360-364
```python
  358:             или пустая строка, если узел не найден или данные недоступны.
  359:         """
  360:         if not data:  # НЕ ПОКРЫТО
  361:             return ""  # НЕ ПОКРЫТО
  362:         nodes = data.get("graph", {}).get("nodes", {})  # НЕ ПОКРЫТО
  363:         target = next((n for n in nodes.values() if n.get("name") == comp_name), None)  # НЕ ПОКРЫТО
  364:         return target.get("binary", "") if target else ""  # НЕ ПОКРЫТО
  365: 
  366: 
```
- ветка 360 → 361 ни разу не выполнялась в тестах
- ветка 360 → 362 ни разу не выполнялась в тестах

### `_ProfileBuildAggregator.apply_enrich` — строки 408-408
```python
  406:         self.conan_settings = enrich.conan_settings
  407: 
  408:         if self.first_enrich is None and enrich.base_ref:
  409:             self.first_enrich = enrich
  410: 
```
- ветка 408 → 411 ни разу не выполнялась в тестах

### `_ProfileBuildAggregator.apply_enrich` — строки 411-411
```python
  409:             self.first_enrich = enrich
  410: 
  411:         if enrich.option_id and enrich.option_id not in self.resolved_options_by_id:
  412:             self.resolved_options_by_id[enrich.option_id] = enrich.conan_options
  413: 
```
- ветка 408 → 411 ни разу не выполнялась в тестах
- ветка 411 → 414 ни разу не выполнялась в тестах

### `_ProfileBuildAggregator.apply_enrich` — строки 414-414
```python
  412:             self.resolved_options_by_id[enrich.option_id] = enrich.conan_options
  413: 
  414:         self.all_dependencies.update(enrich.dependencies)
  415:         self.all_patches.update(enrich.patches)
  416: 
```
- ветка 411 → 414 ни разу не выполнялась в тестах

### `_ProfileBuildAggregator.apply_enrich` — строки 417-417
```python
  415:         self.all_patches.update(enrich.patches)
  416: 
  417:         if enrich.package_id and enrich.package_id not in self.unique_variants:
  418:             self.unique_variants[enrich.package_id] = ConanVariant(
  419:                 package_id=enrich.package_id,
```
- ветка 417 → выход из функции ни разу не выполнялась в тестах

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

## `autodoc\common\logger.py`
_строки: 84%, ветки: 67%, непокрытых строк: 7, непокрытых веток: 4_
Связанный тест: `tests\unit\common\test_logger.py`

### `clear_logs_dir` — строки 131-137
```python
  129:         Список удалённых путей (пустой, если директории нет или удалять нечего).
  130:     """
  131:     if not logs_dir.exists():  # НЕ ПОКРЫТО
  132:         return []  # НЕ ПОКРЫТО
  133:     deleted: list[Path] = []  # НЕ ПОКРЫТО
  134:     for path in sorted(logs_dir.glob("*.log")):  # НЕ ПОКРЫТО
  135:         path.unlink()  # НЕ ПОКРЫТО
  136:         deleted.append(path)  # НЕ ПОКРЫТО
  137:     return deleted  # НЕ ПОКРЫТО
  138: 
  139: 
```
- ветка 131 → 132 ни разу не выполнялась в тестах
- ветка 131 → 133 ни разу не выполнялась в тестах
- ветка 134 → 135 ни разу не выполнялась в тестах
- ветка 134 → 137 ни разу не выполнялась в тестах

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

## `autodoc\parser\conan\conan2_result_parser.py`
_строки: 86%, ветки: 77%, непокрытых строк: 12, непокрытых веток: 10_
Связанный тест: **не найден автоматически — проверить вручную**

### `Conan2ResultParser._extract_ref_info` — строки 114-115
```python
  112:         full_version = fallback_version
  113: 
  114:         if not full_ref:
  115:             return "", rrev, full_version  # НЕ ПОКРЫТО
  116: 
  117:         try:
```
- ветка 114 → 115 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_ref_info` — строки 119-120
```python
  117:         try:
  118:             recipe_ref = RecipeReference.loads(full_ref)
  119:         except ConanException as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  120:             logger.warning(  # НЕ ПОКРЫТО
  121:                 f'Conan2ResultParser: не удалось разобрать ref "{full_ref}" ({e}); '
  122:                 "base_ref будет пустым."
```

### `Conan2ResultParser._extract_ref_info` — строки 124-124
```python
  122:                 "base_ref будет пустым."
  123:             )
  124:             return "", rrev, full_version  # НЕ ПОКРЫТО
  125: 
  126:         base_ref = str(recipe_ref)
```

### `Conan2ResultParser._extract_ref_info` — строки 127-129
```python
  125: 
  126:         base_ref = str(recipe_ref)
  127:         if not rrev and recipe_ref.revision:
  128:             rrev = recipe_ref.revision  # НЕ ПОКРЫТО
  129:         if recipe_ref.user:
  130:             full_version = str(recipe_ref.version)
  131: 
```
- ветка 127 → 128 ни разу не выполнялась в тестах
- ветка 129 → 132 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_ref_info` — строки 132-132
```python
  130:             full_version = str(recipe_ref.version)
  131: 
  132:         return base_ref, rrev, full_version
  133: 
  134:     def _extract_default_options(self, node: dict[str, Any]) -> list[DefaultOptionsSet]:
```
- ветка 129 → 132 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_patches` — строки 180-181
```python
  178:         # и собираем имена файлов без учёта ключа; дубликаты удаляем через dict.fromkeys.
  179:         patches_dict: dict[str, Any] = node.get("conandata", {}).get("patches", {})
  180:         if not isinstance(patches_dict, dict):
  181:             return []  # НЕ ПОКРЫТО
  182: 
  183:         extracted: list[str] = []
```
- ветка 180 → 181 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_patches` — строки 185-189
```python
  183:         extracted: list[str] = []
  184:         for patch_list in patches_dict.values():
  185:             if not isinstance(patch_list, list):
  186:                 continue  # НЕ ПОКРЫТО
  187:             for p in patch_list:
  188:                 if not isinstance(p, dict):
  189:                     continue  # НЕ ПОКРЫТО
  190:                 patch_file = p.get("patch_file", "")
  191:                 if patch_file:
```
- ветка 185 → 186 ни разу не выполнялась в тестах
- ветка 188 → 189 ни разу не выполнялась в тестах
- ветка 191 → 187 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_patches` — строки 191-191
```python
  189:                     continue  # НЕ ПОКРЫТО
  190:                 patch_file = p.get("patch_file", "")
  191:                 if patch_file:
  192:                     extracted.append(Path(patch_file).name)
  193: 
```
- ветка 191 → 187 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_dependencies` — строки 209-209
```python
  207:         # Обходим все узлы графа (включая транзитивные), а не только прямые зависимости.
  208:         deps: list[str] = []
  209:         for node in nodes.values():
  210:             name: str = node.get("name", "")
  211:             if not name or name == comp_name or name == "conanfile":
```
- ветка 223 → 209 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_dependencies` — строки 214-215
```python
  212:                 continue
  213:             ref: str = node.get("ref", "")
  214:             if not ref:
  215:                 continue  # НЕ ПОКРЫТО
  216:             try:
  217:                 dep_name = RecipeReference.loads(ref).name
```
- ветка 214 → 215 ни разу не выполнялась в тестах

### `Conan2ResultParser._extract_dependencies` — строки 218-219
```python
  216:             try:
  217:                 dep_name = RecipeReference.loads(ref).name
  218:             except ConanException as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  219:                 logger.warning(  # НЕ ПОКРЫТО
  220:                     f'Conan2ResultParser: не удалось разобрать ref зависимости "{ref}" ({e}); пропускаем.'
  221:                 )
```

### `Conan2ResultParser._extract_dependencies` — строки 222-223
```python
  220:                     f'Conan2ResultParser: не удалось разобрать ref зависимости "{ref}" ({e}); пропускаем.'
  221:                 )
  222:                 continue  # НЕ ПОКРЫТО
  223:             if dep_name and dep_name != comp_name:
  224:                 deps.append(dep_name)
  225:         return sorted(set(deps))
```
- ветка 223 → 209 ни разу не выполнялась в тестах

### `Conan2ResultParser._build_artifactory_url` — строки 252-252
```python
  250:             f"/{task.comp_name}/{full_version}/{task.channel}/{rrev}"
  251:         )
  252:         if package_id:
  253:             url += f"/package/{package_id}"
  254:         return url
```
- ветка 252 → 254 ни разу не выполнялась в тестах

### `Conan2ResultParser._build_artifactory_url` — строки 254-254
```python
  252:         if package_id:
  253:             url += f"/package/{package_id}"
  254:         return url
  255: 
  256:     def _extract_build_date(self, node: dict[str, Any]) -> str:
```
- ветка 252 → 254 ни разу не выполнялась в тестах

---

## `autodoc\config\manager.py`
_строки: 88%, ветки: 79%, непокрытых строк: 9, непокрытых веток: 7_
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

### `ConfigManager.validate_config_file` — строки 163-164
```python
  161:         """
  162:         path = Path(filepath)
  163:         if not path.exists():
  164:             raise ConfigError(f"Файл не найден: {filepath}")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  165: 
  166:         suffix = path.suffix.lower()
```
- ветка 163 → 164 ни разу не выполнялась в тестах

### `ConfigManager.validate_config_file` — строки 167-168
```python
  165: 
  166:         suffix = path.suffix.lower()
  167:         if suffix not in self.SUPPORTED_FORMATS:
  168:             raise ConfigError(  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  169:                 f"Неподдерживаемый формат: {suffix}. " f"Поддерживаемые: {self.SUPPORTED_FORMATS}"
  170:             )
```
- ветка 167 → 168 ни разу не выполнялась в тестах

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

### `ConfigManager._parse_file` — строки 238-241
```python
  236:         except json.JSONDecodeError as e:
  237:             raise ConfigError(f"Некорректный JSON в {filepath.name}: {e}") from e
  238:         except yaml.YAMLError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  239:             raise ConfigError(f"Некорректный YAML в {filepath.name}: {e}") from e  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  240:         except OSError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  241:             raise ConfigError(f"Ошибка чтения {filepath.name}: {e}") from e  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  242: 
  243:         if not isinstance(data, dict):
```

### `ConfigManager._parse_file` — строки 243-244
```python
  241:             raise ConfigError(f"Ошибка чтения {filepath.name}: {e}") from e  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  242: 
  243:         if not isinstance(data, dict):
  244:             raise ConfigError(  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  245:                 f"Файл {filepath.name} должен содержать объект (dict), "
  246:                 f"получен {type(data).__name__}"
```
- ветка 243 → 244 ни разу не выполнялась в тестах

---

## `autodoc\parser\conan\conan_environment_manager.py`
_строки: 89%, ветки: 79%, непокрытых строк: 5, непокрытых веток: 3_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConanEnvironmentManager.setup` — строки 60-61
```python
   58:                           из подпроцессов завершился с ненулевым кодом возврата.
   59:         """
   60:         if not shutil.which("conan"):
   61:             raise RuntimeError("Утилита conan не найдена в PATH.")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   62: 
   63:         self._setup_dir = Path(tempfile.mkdtemp(prefix="conan_setup_"))
```
- ветка 60 → 61 ни разу не выполнялась в тестах

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

### `ConanEnvironmentManager._install_config` — строки 172-175
```python
  170:             env=env,
  171:         )
  172:         if result.returncode != 0:
  173:             error = result.stderr.strip() or result.stdout.strip()  # НЕ ПОКРЫТО
  174:             self.cleanup()  # НЕ ПОКРЫТО
  175:             raise RuntimeError(  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  176:                 f"conan config install завершился с ошибкой (код {result.returncode}): {error}"
  177:             )
```
- ветка 172 → 173 ни разу не выполнялась в тестах

---

## `autodoc\publisher\clients\models\confluence_page.py`
_строки: 89%, ветки: 100%, непокрытых строк: 2, непокрытых веток: 0_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConfluencePage.from_api` — строки 42-43
```python
   40:         try:
   41:             version_number = int(version_block.get("number", 0))
   42:         except (TypeError, ValueError):  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   43:             version_number = 0  # НЕ ПОКРЫТО
   44:         return cls(
   45:             id=str(data["id"]),
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

## `autodoc\publisher\clients\confluence_client.py`
_строки: 91%, ветки: 91%, непокрытых строк: 10, непокрытых веток: 2_
Связанный тест: `tests\unit\publisher\clients\test_confluence_client.py`

### `ConfluenceClient.get_page` — строки 92-94
```python
   90:         try:
   91:             data = self._transport.get_content(page_id, expand)
   92:         except ConfluenceError:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   93:             logger.error(f"Ошибка при получении страницы (ID={page_id})")  # НЕ ПОКРЫТО
   94:             raise  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   95:         return ConfluencePage.from_api(data)
   96: 
```

### `ConfluenceClient.resolve_existing_page_id` — строки 157-159
```python
  155:         try:
  156:             moved = self._resolve_title_conflict(existing, parent_id, title, body_html=None)
  157:         except ConfluenceError:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  158:             logger.error(f"Ошибка при переносе страницы {title!r} (parent_id={parent_id})")  # НЕ ПОКРЫТО
  159:             raise  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  160:         return moved.id
  161: 
```

### `ConfluenceClient._find_page_in_subtree` — строки 232-232
```python
  230:         """
  231:         existing = self.find_page(title, space=space, expand=expand)
  232:         if existing and parent_id and not existing.is_descendant_of(parent_id):
  233:             logger.warning(
  234:                 f"Страница {title!r} найдена в другом дереве "
```
- ветка 232 → 238 ни разу не выполнялась в тестах

### `ConfluenceClient._find_page_in_subtree` — строки 238-238
```python
  236:             )
  237:             return None
  238:         return existing  # НЕ ПОКРЫТО
  239: 
  240:     def _resolve_title_conflict(
```
- ветка 232 → 238 ни разу не выполнялась в тестах

### `ConfluenceClient.create_page` — строки 317-319
```python
  315:         try:
  316:             data = self._transport.create_content(payload, title)
  317:         except ConfluenceError:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  318:             logger.error(f"Ошибка при создании страницы {title!r} (parent_id={parent_id})")  # НЕ ПОКРЫТО
  319:             raise  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  320: 
  321:         page_id = str(data.get("id", ""))
```

### `ConfluenceClient._build_payload` — строки 406-406
```python
  404:             },
  405:         }
  406:         if parent_id:
  407:             payload["ancestors"] = [{"id": parent_id}]
  408:         if space:
```
- ветка 406 → 408 ни разу не выполнялась в тестах

### `ConfluenceClient._build_payload` — строки 408-408
```python
  406:         if parent_id:
  407:             payload["ancestors"] = [{"id": parent_id}]
  408:         if space:
  409:             payload["space"] = {"key": space}
  410:         return payload
```
- ветка 406 → 408 ни разу не выполнялась в тестах

---

## `autodoc\cli\helpers.py`
_строки: 92%, ветки: 100%, непокрытых строк: 6, непокрытых веток: 0_
Связанный тест: `tests\unit\cli\test_helpers.py`

### `load_parsed_data` — строки 81-83
```python
   79:     try:
   80:         raw = data_file.read_text(encoding="utf-8")
   81:     except UnicodeDecodeError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   82:         logger.debug(f"Не удалось прочитать {data_file} как UTF-8: {e}")  # НЕ ПОКРЫТО
   83:         raise ValidationError(  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   84:             f"Файл {data_file} повреждён: содержимое не в кодировке UTF-8. "
   85:             'Запустите "parse" заново.'
```

### `load_parsed_data` — строки 87-89
```python
   85:             'Запустите "parse" заново.'
   86:         ) from e
   87:     except OSError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   88:         logger.debug(f"Не удалось прочитать {data_file}: {e}")  # НЕ ПОКРЫТО
   89:         raise DocGeneratorError(f"Не удалось прочитать файл {data_file}: {e}") from e  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   90: 
   91:     if not raw.strip():
```

---

## `autodoc\cli\app.py`
_строки: 92%, ветки: 75%, непокрытых строк: 2, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `cli` — строки 48-50
```python
   46:     cfgs = configs_dir.resolve() if configs_dir else base / "configs"
   47: 
   48:     if not cfgs.exists():
   49:         console.print(f"❌ Директория конфигов не найдена: {cfgs}", style="red bold")  # НЕ ПОКРЫТО
   50:         sys.exit(1)  # НЕ ПОКРЫТО
   51: 
   52:     ctx.obj = CliCtx(base, cfgs, verbose)
```
- ветка 48 → 49 ни разу не выполнялась в тестах

---

## `autodoc\publisher\page_manager\hierarchy_manager.py`
_строки: 92%, ветки: 100%, непокрытых строк: 3, непокрытых веток: 0_
Связанный тест: `tests\unit\publisher\page_manager\test_hierarchy_manager.py`

### `PageHierarchyManager._resolve_existing_page_id` — строки 148-150
```python
  146:                 space=space, parent_id=parent_id, title=title
  147:             )
  148:         except ConfluenceError:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  149:             logger.error(f"Не удалось найти существующую страницу {title!r} (parent_id={parent_id})")  # НЕ ПОКРЫТО
  150:             raise  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  151: 
  152:     def _create_page(self, *, space: str, parent_id: str, title: str, body_html: str) -> str:
```

---

## `autodoc\common\retryable_session.py`
_строки: 92%, ветки: 67%, непокрытых строк: 1, непокрытых веток: 2_
Связанный тест: `tests\unit\common\test_retryable_session.py`

### `create_bearer_session` — строки 104-104
```python
  102:         timeout=timeout,
  103:     )
  104:     if token:
  105:         session.headers["Authorization"] = f"Bearer {token}"
  106:         logger.debug("Настроена Bearer-аутентификация")
```
- ветка 104 → 107 ни разу не выполнялась в тестах

### `create_bearer_session` — строки 107-107
```python
  105:         session.headers["Authorization"] = f"Bearer {token}"
  106:         logger.debug("Настроена Bearer-аутентификация")
  107:     return session
  108: 
  109: 
```
- ветка 104 → 107 ни разу не выполнялась в тестах

### `create_retryable_session` — строки 163-164
```python
  161:         Настроенная сессия с retry-логикой.
  162:     """
  163:     if bearer and token:
  164:         return create_bearer_session(  # НЕ ПОКРЫТО
  165:             token=token,
  166:             max_retries=max_retries,
```
- ветка 163 → 164 ни разу не выполнялась в тестах

---

## `autodoc\cli\commands\config.py`
_строки: 93%, ветки: 93%, непокрытых строк: 4, непокрытых веток: 1_
Связанный тест: `tests\unit\cli\test_config_command.py`

### `config_validate` — строки 73-73
```python
   71:     # Первая схема, которая успешно валидируется, считается подходящей.
   72:     validation_errors: list[str] = []
   73:     for schema_cls, schema_name in _CONFIG_SCHEMAS:
   74:         try:
   75:             schema_cls(**raw)
```
- ветка 73 → 82 ни разу не выполнялась в тестах

### `config_validate` — строки 76-78
```python
   74:         try:
   75:             schema_cls(**raw)
   76:         except PydanticValidationError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   77:             validation_errors.append(f"схема {schema_name}: {e}")  # НЕ ПОКРЫТО
   78:             continue  # НЕ ПОКРЫТО
   79:         console.print(f"✅ Pydantic валидация пройдена (схема: {schema_name})", style="green")
   80:         return
```

### `config_validate` — строки 82-82
```python
   80:         return
   81: 
   82:     console.print(  # НЕ ПОКРЫТО
   83:         "⚠️  JSON/YAML синтаксически корректен, но не соответствует "
   84:         "ни одной известной схеме:\n" + "\n".join(validation_errors),
```
- ветка 73 → 82 ни разу не выполнялась в тестах

---

## `autodoc\config\schemas\confluence_config.py`
_строки: 93%, ветки: 50%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConfluenceConfigSchema._normalize_url` — строки 107-108
```python
  105:     def _normalize_url(cls, v: str) -> str:
  106:         """Проверяет непустоту URL и убирает завершающий слеш."""
  107:         if not v or not v.strip():
  108:             raise ValueError("url не может быть пустым")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  109:         return v.rstrip("/")
```
- ветка 107 → 108 ни разу не выполнялась в тестах

---

## `autodoc\parser\conan\conan2_runner.py`
_строки: 94%, ветки: 83%, непокрытых строк: 2, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `Conan2Runner.run` — строки 98-98
```python
   96:             try:
   97:                 parsed = json.loads(result.stdout)
   98:                 return ConanRawResult(success=True, data=parsed, error="")  # НЕ ПОКРЫТО
   99:             except json.JSONDecodeError as e:
  100:                 return ConanRawResult(
```

### `Conan2Runner._extract_error_message` — строки 147-147
```python
  145:         # обрезаем до первого вхождения "error:" для более чистого сообщения.
  146:         idx = stderr.lower().find("error:")
  147:         if idx != -1:
  148:             return stderr[idx:]
  149:         return stderr.strip()  # НЕ ПОКРЫТО
```
- ветка 147 → 149 ни разу не выполнялась в тестах

### `Conan2Runner._extract_error_message` — строки 149-149
```python
  147:         if idx != -1:
  148:             return stderr[idx:]
  149:         return stderr.strip()  # НЕ ПОКРЫТО
```
- ветка 147 → 149 ни разу не выполнялась в тестах

---

## `autodoc\config\schemas\parser_config.py`
_строки: 95%, ветки: 50%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `ParserConfigSchema.tfs_token_not_empty` — строки 155-156
```python
  153:     @classmethod
  154:     def tfs_token_not_empty(cls, v: str) -> str:
  155:         if not v:
  156:             raise ValueError("tfs_token не может быть пустой строкой")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  157:         return v
  158: 
```
- ветка 155 → 156 ни разу не выполнялась в тестах

---

## `autodoc\publisher\strategies\single_page_strategy.py`
_строки: 95%, ветки: 75%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `SinglePagePublishStrategy.__init__` — строки 62-63
```python
   60:         """
   61:         super().__init__(confluence_client, document_builder, parsed_data, space)
   62:         if not page_title:
   63:             raise ValueError("page_title не может быть пустым")  # НЕ ПОКРЫТО — путь ошибки (raise/except)
   64:         self._page_title: str = page_title
   65:         self._template_name: str = template_name
```
- ветка 62 → 63 ни разу не выполнялась в тестах

---

## `autodoc\parser\enrichment\data_enricher.py`
_строки: 96%, ветки: 91%, непокрытых строк: 1, непокрытых веток: 3_
Связанный тест: `tests\unit\parser\enrichment\test_data_enricher.py`

### `DataEnricher.apply_docker_links` — строки 62-62
```python
   60:         """
   61:         pd_map: dict[str, ProfileDefinition] = {}
   62:         if profile_definitions is not None:
   63:             pd_map = {pd.profile_name: pd for pd in profile_definitions}
   64: 
```
- ветка 62 → 65 ни разу не выполнялась в тестах

### `DataEnricher.apply_docker_links` — строки 65-65
```python
   63:             pd_map = {pd.profile_name: pd for pd in profile_definitions}
   64: 
   65:         for comp in components:
   66:             for release in comp.releases:
   67:                 for pb in release.profile_builds:
```
- ветка 62 → 65 ни разу не выполнялась в тестах

### `DataEnricher.apply_docker_links` — строки 67-67
```python
   65:         for comp in components:
   66:             for release in comp.releases:
   67:                 for pb in release.profile_builds:
   68:                     pname = pb.profile_name
   69:                     docker_url = docker_links.get(pname, "")
```
- ветка 70 → 67 ни разу не выполнялась в тестах

### `DataEnricher.apply_docker_links` — строки 70-70
```python
   68:                     pname = pb.profile_name
   69:                     docker_url = docker_links.get(pname, "")
   70:                     if profile_definitions is not None:
   71:                         if pname not in pd_map:
   72:                             entry = ProfileDefinition(profile_name=pname, docker_image=docker_url)
```
- ветка 70 → 67 ни разу не выполнялась в тестах

### `DataEnricher.apply_conan_results` — строки 128-129
```python
  126:                                 profile_definitions.append(entry)
  127:                             # не затираем непустые данные пустыми
  128:                             elif pb_data.conan_settings:
  129:                                 pd_map[pname].conan_settings = pb_data.conan_settings  # НЕ ПОКРЫТО
```
- ветка 128 → 129 ни разу не выполнялась в тестах

---

## `autodoc\publisher\page_manager\passport_link_injector.py`
_строки: 96%, ветки: 94%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `inject_links` — строки 97-98
```python
   95:     for comp in view_model.get("components", []):
   96:         comp_name = comp.get("name")
   97:         if not comp_name or comp_name not in passport_pages:
   98:             continue  # НЕ ПОКРЫТО
   99:         release_versions = {rel.get("version") for rel in comp.get("releases", [])}
  100:         comp["passport_versions"] = {
```
- ветка 97 → 98 ни разу не выполнялась в тестах

---

## `autodoc\common\parallel_executor.py`
_строки: 96%, ветки: 94%, непокрытых строк: 2, непокрытых веток: 1_
Связанный тест: `tests\unit\common\test_parallel_executor.py`

### `ParallelExecutor._execute_in_batches` — строки 135-137
```python
  133: 
  134:             is_last_batch = batch_num == total_batches
  135:             if self._batch_delay > 0 and not is_last_batch:
  136:                 logger.debug(f"Пауза {self._batch_delay}с перед следующим пакетом")  # НЕ ПОКРЫТО
  137:                 time.sleep(self._batch_delay)  # НЕ ПОКРЫТО
  138: 
  139:         return results
```
- ветка 135 → 136 ни разу не выполнялась в тестах

---

## `autodoc\parser\parsers\manifest_parser.py`
_строки: 96%, ветки: 91%, непокрытых строк: 2, непокрытых веток: 3_
Связанный тест: `tests\unit\parser\parsers\test_manifest_parser.py`

### `ManifestParser.parse` — строки 85-86
```python
   83: 
   84:         for result in file_results:
   85:             if result is None:
   86:                 continue  # НЕ ПОКРЫТО
   87:             warnings.extend(result.warnings)
   88:             if result.is_excluded:
```
- ветка 85 → 86 ни разу не выполнялась в тестах

### `ManifestParser._parse_single_file` — строки 144-144
```python
  142:         # Это намеренное поведение. Чтобы не включить ни одного, нужно передать непустой
  143:         # список, не совпадающий ни с одним именем компонента.
  144:         elif filter_mode == "include":
  145:             if component_names and name not in component_names:
  146:                 logger.debug(f"Компонент {name} пропущен — не в белом списке (режим include)")
```
- ветка 144 → 149 ни разу не выполнялась в тестах

### `ManifestParser._parse_single_file` — строки 149-149
```python
  147:                 return _FileParseResult(is_excluded=True)
  148: 
  149:         releases = self._build_releases(props)
  150:         if not releases:
  151:             return _FileParseResult()
```
- ветка 144 → 149 ни разу не выполнялась в тестах

### `ManifestParser._parse_single_file` — строки 158-158
```python
  156:         if self._tfs_collection_url and git_project and git_repo:
  157:             component_git_url = f"{self._tfs_collection_url}/{git_project}/_git/{git_repo}"
  158:         elif git_repo_part:
  159:             component_git_url = git_repo_part
  160:         else:
```
- ветка 158 → 161 ни разу не выполнялась в тестах

### `ManifestParser._parse_single_file` — строки 161-161
```python
  159:             component_git_url = git_repo_part
  160:         else:
  161:             component_git_url = ""  # НЕ ПОКРЫТО
  162: 
  163:         component = Component(
```
- ветка 158 → 161 ни разу не выполнялась в тестах

---

## `autodoc\parser\steps\validation_step.py`
_строки: 97%, ветки: 92%, непокрытых строк: 1, непокрытых веток: 2_
Связанный тест: `tests\unit\parser\steps\test_validation_step.py`

### `ArtifactoryValidationStep._check_urls_parallel` — строки 132-133
```python
  130:         dead: list[tuple[ProfileBuild, ConanVariant]] = []
  131:         for result in raw_results:
  132:             if result is None:
  133:                 continue  # НЕ ПОКРЫТО
  134:             pb, variant, is_valid = result
  135:             if not is_valid:
```
- ветка 132 → 133 ни разу не выполнялась в тестах

### `ArtifactoryValidationStep._remove_dead_variants` — строки 150-151
```python
  148:             dead_variants: Список кортежей ``(ProfileBuild, ConanVariant)`` для удаления.
  149:         """
  150:         for pb, variant in dead_variants:
  151:             if variant in pb.variants:
  152:                 pb.variants.remove(variant)
```
- ветка 151 → 150 ни разу не выполнялась в тестах

---

## `autodoc\parser\steps\finalize_step.py`
_строки: 97%, ветки: 100%, непокрытых строк: 2, непокрытых веток: 0_
Связанный тест: `tests\unit\parser\steps\test_finalize_step.py`

### `FinalizeStep._build_result` — строки 160-161
```python
  158:             logger.info(f"Данные валидированы. {len(result.components)} компонентов.")
  159:             return result
  160:         except PydanticValidationError as e:  # НЕ ПОКРЫТО — путь ошибки (raise/except)
  161:             raise ParsingError(f"FinalizeStep: валидация данных не прошла: {e}") from e  # НЕ ПОКРЫТО — путь ошибки (raise/except)
```

---

## `autodoc\publisher\converters\base_data_converter.py`
_строки: 97%, ветки: 88%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: `tests\unit\publisher\converters\test_base_data_converter.py`

### `BaseDataConverter._build_install_options_from_string._qualify` — строки 80-81
```python
   78: 
   79:         def _qualify(p: str) -> str:
   80:             if ":" not in p:
   81:                 return p  # НЕ ПОКРЫТО
   82:             pkg, rest = p.split(":", 1)
   83:             return f"{BaseDataConverter._qualify_package_ref(pkg)}:{rest}"
```
- ветка 80 → 81 ни разу не выполнялась в тестах

---

## `autodoc\parser\conan\conan_task_builder.py`
_строки: 97%, ветки: 95%, непокрытых строк: 1, непокрытых веток: 1_
Связанный тест: **не найден автоматически — проверить вручную**

### `ConanTaskBuilder._format_reference` — строки 146-147
```python
  144:         match = re.match(r"^(\d+(?:\.\d+)*)", version)
  145: 
  146:         if not match:
  147:             return f"{name}/{version}{suffix}"  # НЕ ПОКРЫТО
  148: 
  149:         is_pure_numeric = re.match(r"^[\d\.]+$", version)
```
- ветка 146 → 147 ни разу не выполнялась в тестах

---

## `autodoc\publisher\legacy_content\html_utils.py`
_строки: 98%, ветки: 94%, непокрытых строк: 0, непокрытых веток: 2_
Связанный тест: `tests\unit\publisher\legacy_content\test_html_utils.py`

### `_parse_h2_version_sections` — строки 124-124
```python
  122:     soup = _to_bs_obj(html)
  123:     headers: list[tuple[Tag, str]] = []
  124:     for h in soup.find_all(["h2", "h3"]):
  125:         match = _VERSION_RE.search(h.get_text())
  126:         if match is not None:
```
- ветка 126 → 124 ни разу не выполнялась в тестах

### `_parse_h2_version_sections` — строки 126-126
```python
  124:     for h in soup.find_all(["h2", "h3"]):
  125:         match = _VERSION_RE.search(h.get_text())
  126:         if match is not None:
  127:             headers.append((h, match.group(0)))
  128: 
```
- ветка 126 → 124 ни разу не выполнялась в тестах

### `_parse_h2_version_sections` — строки 137-138
```python
  135: 
  136:     # Находим контент между заголовками версий
  137:     for (header, version), (next_header, _) in zip_longest(headers, headers[1:], fillvalue=(None, None)):
  138:         if content := _html_until(chain([header], header.next_siblings), next_header):
  139:             sections[version] = content
  140: 
```
- ветка 138 → 137 ни разу не выполнялась в тестах

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

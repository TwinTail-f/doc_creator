# autodoc

Инструмент автоматической генерации и публикации документации компонентов платформы.

Собирает данные из TFS (манифесты, опции Conan, Docker-профили),
обогащает их через `conan graph info`, валидирует и публикует в Confluence.

---

## Требования

- Python 3.11+
- Conan 2.x (доступен в PATH)
- Доступ к TFS и Confluence

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Конфигурация

Скопируй примеры конфигов и заполни:

```bash
cp configs/parser_config.json.example configs/parser_config.json
cp configs/confluence_config.json.example configs/confluence_config.json
```

#### Обязательные поля `parser_config.json`

| Поле | Описание |
|------|----------|
| `platform_version` | Версия платформы, например `"2.2"` |
| `platform_branch_name` | Ветка или тег в TFS, например `"develop"` |
| `username` | Имя пользователя TFS / Artifactory |
| `tfs_token` | Personal Access Token (PAT) для TFS |
| `tfs_collection_url` | Базовый URL коллекции TFS, например `"https://tfs.company.com/tfs/DefaultCollection"` |
| `manifests_remotes_path` | Путь к директории с манифестами в репозитории |
| `conan_config_url` | URL zip-архива конфигурации Conan в Artifactory |
| `artifactory_token` | PAT-токен Artifactory |

#### Опциональные поля `parser_config.json`

| Поле | По умолчанию | Описание |
|------|-------------|----------|
| `platform_base_version` | `"2.0"` | Базовая версия платформы, используется для фильтрации манифестов |
| `platform_ref_type` | `"branch"` | Тип ссылки в TFS: `"branch"`, `"tag"` или `"commit"` |
| `artifactory_components_conan2_url` | `""` | URL Artifactory для Conan 2 пакетов |
| `profiles_urls` | `[]` | Список URL на YAML-файлы профилей сборки |
| `component_filter_mode` | `"exclude"` | Режим фильтрации компонентов: `"exclude"` или `"include"` (см. ниже) |
| `component_names` | `[]` | Список имён компонентов для фильтрации (см. ниже) |
| `profile_settings_overrides_file` | — | Путь к файлу переопределений настроек Conan-профилей (см. ниже) |
| `tfs_request_timeout` | `15` | Тайм-аут HTTP-запросов к TFS (секунды) |
| `conan_command_timeout` | `300` | Тайм-аут выполнения команд Conan (секунды) |
| `max_retries` | `3` | Максимальное количество retry-попыток |
| `retry_backoff_factor` | `2.0` | Множитель для exponential backoff |

#### Фильтрация компонентов

Два поля управляют тем, какие компоненты попадут в обработку:

**`component_filter_mode`** — определяет режим работы:
- `"exclude"` *(по умолчанию)* — обрабатываются все компоненты, **кроме** перечисленных в `component_names`
- `"include"` — обрабатываются **только** компоненты, перечисленные в `component_names`

**`component_names`** — список имён компонентов (значение поля `name` из `.properties`-файла манифеста, точное совпадение).

Примеры:

```json
// Пропустить два компонента, остальные обработать
"component_filter_mode": "exclude",
"component_names": ["sqlite3", "apr-util"]
```

```json
// Обработать только эти два компонента, остальные пропустить
"component_filter_mode": "include",
"component_names": ["openssl", "zlib"]
```

```json
// Оба поля пустые / не указаны — обрабатываются все компоненты
"component_filter_mode": "exclude",
"component_names": []
```

#### Переопределения настроек Conan-профилей (опционально)

Некоторые Jinja-профили читают настройки через `os.getenv()` (например `KOS_SDK_VER` → `compiler.toolchain_config_id`). Если нужные переменные окружения не заданы, Conan не может собрать граф зависимостей.

Файл `profile_settings_overrides.json` позволяет задать такие настройки явно, не трогая окружение. Он указывается в `parser_config.json`:

```json
"profile_settings_overrides_file": "configs/profile_settings_overrides.json"
```

Структура файла — список групп, каждая связывает профили с набором `-s` настроек:

```json
{
  "overrides": [
    {
      "profiles": ["kos-x86_64-pc-clang.jinja", "mobile-kos-x86_64-pc.jinja"],
      "settings": {
        "compiler.toolchain_config_id": "kos-x86_64-2.1.2.31"
      }
    },
    {
      "profiles": ["mobile-kos-aarch64.jinja"],
      "settings": {
        "compiler.toolchain_config_id": "kos-aarch64-2.1.0.49",
        "compiler.version": "12"
      }
    }
  ]
}
```

Готовый пример с комментариями: `configs/profile_settings_overrides.json.example`.

Если поле не указано или файл не найден — переопределения не применяются, поведение не меняется.

#### Обязательные поля `confluence_config.json`

| Поле | Описание |
|------|----------|
| `url` | Базовый URL Confluence, например `"https://confluence.example.com"` |
| `token` | Atlassian API-токен |
| `space` | Ключ пространства в Confluence |
| `parent_id` | ID родительской страницы для релизной документации |
| `passports_root_parent_id` | ID корневой страницы для иерархии паспортов |

#### Опциональные поля `confluence_config.json`

| Поле | По умолчанию | Описание |
|------|-------------|----------|
| `verify_ssl` | `true` | Проверять SSL-сертификаты |
| `page_title` | `"Сборки компонентов Платформы"` | Заголовок главной страницы релиза |
| `target_release_version` | `"Platform 2.2"` | Подпись текущего релиза — используется в заголовках паспортов и метке вкладки релиза |
| `confluence_request_timeout` | `30` | Тайм-аут HTTP-запросов к Confluence (секунды) |
| `publish_batch_size` | `10` | Количество паспортов, публикуемых за один пакет |
| `publish_batch_delay_seconds` | `0.0` | Задержка между пакетами (секунды). Увеличьте при перегрузке сервера |

---

### 3. Запуск

#### Парсинг — собрать данные компонентов

```bash
python -m autodoc.cli parse
```

Результат сохраняется в `data/parsed_data.json`. Все последующие команды `publish` читают этот файл.

```bash
# Пропустить тяжёлые шаги для быстрой отладки
python -m autodoc.cli parse --skip-conan --skip-validation

# Сохранять снимок состояния после каждого шага пайплайна
python -m autodoc.cli parse --save-intermediate
```

#### Публикация релизной документации (вид от компонентов)

```bash
python -m autodoc.cli publish release

# Переопределить заголовок страницы
python -m autodoc.cli publish release --page-title "Платформа 2.2"

# Без ссылок на паспорта компонентов
python -m autodoc.cli publish release --no-passport-links
```

#### Публикация профиль-центричной документации (вид от профилей сборки)

```bash
python -m autodoc.cli publish profile

python -m autodoc.cli publish profile --page-title "Профили 2.2" --no-passport-links
```

#### Публикация паспортов компонентов

```bash
# ID корневой страницы берётся из passports_root_parent_id конфига
python -m autodoc.cli publish passports

# Или передать явно
python -m autodoc.cli publish passports --root-page 987654321
```

#### Паспорта + релизная страница за один вызов

```bash
python -m autodoc.cli publish all --root-page 987654321 --page-title "Платформа 2.2"
```

#### Утилиты

```bash
# Список конфигурационных файлов в configs/
python -m autodoc.cli config list

# Валидация конфига (автоматически определяет схему — parser или confluence)
python -m autodoc.cli config validate parser_config.json

# Версия и список возможностей
python -m autodoc.cli info
```

---

## Флаги CLI

### Глобальные флаги (перед командой)

| Флаг | Описание |
|------|----------|
| `--base-dir` | Корневая директория проекта (по умолчанию — текущая) |
| `--configs-dir` | Директория с конфигами (по умолчанию `<base-dir>/configs`) |
| `-v`, `--verbose` | Подробный вывод логов |

### `parse`

| Флаг | Описание |
|------|----------|
| `--config` | Имя файла конфига парсера (по умолчанию ищется автоматически) |
| `--save-intermediate` | Сохранять JSON-снапшоты состояния после каждого шага пайплайна |
| `--skip-conan` | Пропустить шаг Conan graph info |
| `--skip-validation` | Пропустить HTTP-проверку ссылок в Artifactory |

### `publish release` и `publish profile`

| Флаг | Описание |
|------|----------|
| `--page-title` | Заголовок страницы (переопределяет `page_title` из конфига) |
| `--no-passport-links` | Не вставлять ссылки на паспорта компонентов |

### `publish passports`

| Флаг | Описание |
|------|----------|
| `--root-page` | ID корневой страницы иерархии паспортов (переопределяет `passports_root_parent_id` из конфига) |

### `publish all`

| Флаг | Описание |
|------|----------|
| `--root-page` | ID корневой страницы паспортов |
| `--page-title` | Заголовок итоговой релизной страницы |
| `--no-passport-links` | Не вставлять ссылки на паспорта в релизную страницу |

---

## Архитектура

Проект разбит на два независимых домена:

```
autodoc/
├── parser/      — сбор данных из TFS + Conan + Docker
└── publisher/   — публикация в Confluence
```

**Пайплайн парсера** (последовательность шагов):

```
ManifestStep → OptionsResolveStep → ConanEnrichStep
    → DockerResolveStep → ArtifactoryValidationStep → FinalizeStep
```

Каждый шаг — изолированный объект, общается с остальными только через `PipelineContext`.
`ConanEnrichStep` и `ArtifactoryValidationStep` убираются из пайплайна при передаче флагов `--skip-conan` / `--skip-validation`.

**Стратегии публикации** регистрируются через Python-метакласс (`__init_subclass__`) и создаются по строковому ключу фабричным методом `BasePublishStrategy.create()`:

| Стратегия | Команда CLI | Описание |
|-----------|-------------|----------|
| `release` | `publish release` | Одна страница: все компоненты с их релизами и профилями |
| `profile_centric` | `publish profile` | Одна страница: вид по профилям сборки → каналам → компонентам |
| `passports` | `publish passports` | Иерархия страниц: Корень → Компонент → Версия |

`publish all` последовательно выполняет `passports`, затем `release` — после первого шага генерируется карта ID страниц паспортов, которую `release` использует для вставки ссылок.

---

## Структура конфигов

```
configs/
├── parser_config.json       — настройки парсера (TFS, Conan, платформа)
└── confluence_config.json   — настройки публикации (Confluence URL, токен, space)
```

Поддерживаемые форматы: `.json`, `.yaml`, `.yml`.
Если файл не указан явно, он ищется автоматически в директории `configs/`.

---

## Шаблоны

Jinja2-шаблоны для страниц Confluence хранятся в `autodoc/publisher/rendering/templates/`.
Используется Confluence Storage Format (AUI-макросы, вкладки).

```
autodoc/publisher/rendering/templates/
├── release_doc_full.jinja2       — полная документация релиза
├── release_doc_minimal.jinja2    — минимальная документация
├── profile_centric.jinja2        — профиль-центричный вид
├── release_doc_combined.jinja2   — комбинированный вид
└── component_passport.jinja2     — паспорт компонента
```

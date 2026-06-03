# autodoc

Инструмент автоматической генерации и публикации документации компонентов платформы.

Собирает данные из TFS (манифесты, опции Conan, Docker-профили),
обогащает их через `conan graph info`, валидирует и публикует в Confluence.

> [!WARNING]
> Этот README-файл является **черновым наброском**.
> В нём описаны настройки и функционал, реализованные на текущий момент.

---

## Требования

- Linux (рекомендуемая платформа; Unicode-эмодзи в выводе могут не отображаться в консоли Windows)
- Python 3.11+
- Conan 2.x (доступен в PATH) (на текущий момент реализация поддерживает только conan 2.x)
- Доступ к TFS и Confluence

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -e ".[dev]"
```

### 2. Конфигурация

Скопируй примеры конфигов и заполни:

```bash
cp configs/examples/parser_config.yaml configs/parser_config.yaml
cp configs/examples/confluence_config.yaml configs/confluence_config.yaml
```

#### Обязательные поля `parser_config.yaml`

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

#### Опциональные поля `parser_config.yaml`

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

```yaml
# Пропустить два компонента, остальные обработать
component_filter_mode: "exclude"
component_names:
  - "sqlite3"
  - "apr-util"
```

```yaml
# Обработать только эти два компонента, остальные пропустить
component_filter_mode: "include"
component_names:
  - "openssl"
  - "zlib"
```

```yaml
# Оба поля пустые / не указаны — обрабатываются все компоненты
component_filter_mode: "exclude"
component_names: []
```

#### Переопределения настроек Conan-профилей (опционально)

Некоторые Jinja-профили читают настройки через `os.getenv()` (например `KOS_SDK_VER` → `compiler.toolchain_config_id`). Если нужные переменные окружения не заданы, Conan не может собрать граф зависимостей.

Файл `profile_settings_overrides.yaml` позволяет задать такие настройки явно, не трогая окружение. Он указывается в `parser_config.yaml`:

```yaml
profile_settings_overrides_file: "configs/profile_settings_overrides.yaml"
```

Структура файла — список групп, каждая связывает профили с набором `-s` настроек:

```yaml
overrides:
  - profiles:
      - "kos-x86_64-pc-clang.jinja"
      - "mobile-kos-x86_64-pc.jinja"
    settings:
      compiler.toolchain_config_id: "kos-x86_64-2.1.2.31"
  - profiles:
      - "mobile-kos-aarch64.jinja"
    settings:
      compiler.toolchain_config_id: "kos-aarch64-2.1.0.49"
      compiler.version: "12"
```

Готовый пример с комментариями: `configs/examples/profile_settings_overrides.yaml`
(JSON-вариант: `configs/examples/profile_settings_overrides.json`).

Если поле не указано или файл не найден — переопределения не применяются, поведение не меняется.

#### Обязательные поля `confluence_config.yaml`

| Поле | Описание |
|------|----------|
| `url` | Базовый URL Confluence, например `"https://confluence.example.com"` |
| `token` | Atlassian API-токен |
| `space` | Ключ пространства в Confluence |
| `parent_id` | ID родительской страницы для релизной документации |
| `passports_root_parent_id` | ID корневой страницы для иерархии паспортов |

#### Опциональные поля `confluence_config.yaml`

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
python autodoc parse
```

Результат сохраняется в `data/parsed_data.json`. Все последующие команды `publish` читают этот файл.

```bash
# Пропустить тяжёлые шаги для быстрой отладки
python autodoc parse --skip-conan --skip-validation

# Сохранять снимок состояния после каждого шага пайплайна + отладочную информацию
python autodoc parse --save-intermediate
```

#### Публикация релизной документации 

```bash
python autodoc publish release

# Переопределить заголовок страницы
python autodoc publish release --page-title "Платформа 2.2"

# Без ссылок на паспорта компонентов
python autodoc publish release --no-passport-links
```

#### Публикация профиль-центричной документации 

```bash
python autodoc publish profile

python autodoc publish profile --page-title "Профили 2.2" --no-passport-links
```

#### Публикация паспортов компонентов

```bash
# ID корневой страницы берётся из passports_root_parent_id конфига
python autodoc publish passports

# Или передать явно
python autodoc publish passports --root-page 987654321
```

#### Паспорта + релизная страница за один вызов

```bash
python autodoc publish all --root-page 987654321 --page-title "Платформа 2.2"
```

#### Утилиты

```bash
# Список конфигурационных файлов в configs/
python autodoc config list

# Валидация конфига (автоматически определяет схему — parser или confluence)
python autodoc config validate parser_config.yaml

# Версия и список возможностей
python autodoc info
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
├── main.py      — точка входа CLI (тонкая обёртка)
├── cli/         — все команды и группы Click
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
├── parser_config.yaml        — настройки парсера (TFS, Conan, платформа)
├── confluence_config.yaml    — настройки публикации (Confluence URL, токен, space)
└── examples/                 — файлы-примеры для копирования
    ├── parser_config.yaml
    ├── parser_config.json
    ├── confluence_config.yaml
    ├── confluence_config.json
    ├── profile_settings_overrides.yaml
    └── profile_settings_overrides.json
```

Первичный формат: `.yaml`. Поддерживаются также `.yml` и `.json` (обратная совместимость).
Если файл не указан явно, он ищется автоматически — YAML имеет приоритет над JSON.

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

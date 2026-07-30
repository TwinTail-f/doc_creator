# autodoc

Инструмент автоматической генерации и публикации документации компонентов платформы.

Собирает данные из TFS (манифесты, опции Conan, Docker-профили), обогащает их через
`conan graph info`, валидирует и публикует в Confluence.

> [!WARNING]
> Этот README-файл является **черновым наброском**.
> В нём описаны настройки и функционал, реализованные на текущий момент.

## Оглавление

- [Требования](#требования)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
  - [Конфигурация парсера](#конфигурация-парсера)
  - [Конфигурация публикации в Confluence](#конфигурация-публикации-в-confluence)
  - [Структура директории configs/](#структура-директории-configs)
- [Команды CLI](#команды-cli)
  - [Глобальные флаги](#глобальные-флаги)
  - [parse](#parse)
  - [publish release](#publish-release)
  - [publish profile](#publish-profile)
  - [publish passports](#publish-passports)
  - [publish all](#publish-all)
  - [config](#config)
  - [info](#info)
  - [logs clear](#logs-clear)
- [Логирование](#логирование)
- [Архитектура](#архитектура)
- [Шаблоны и оформление](#шаблоны-и-оформление)

---

## Требования

- Linux (рекомендуемая платформа; Unicode-эмодзи в выводе могут не отображаться в консоли Windows)
- Python 3.12+
- Conan 2.x, доступный в PATH (на текущий момент реализация поддерживает только Conan 2.x)
- Доступ к TFS и Confluence


### Стили страниц (CSS)

Confluence REST API не позволяет опубликовать кастомный CSS вместе со страницей — единственный
способ применить произвольные стили через API — встраивать их инлайн в тело каждой страницы,
что заметно раздувает её размер.

Полноценная кастомизация оформления в Confluence возможна только двумя способами:

- **через дополнительные плагины (макросы)** — если в Confluence появится подходящий
  плагин, публикацию можно будет переписать на него и отказаться от обходного варианта с общей
  таблицей стилей;
- **через Таблицу стилей CSS пространства** — текущий рабочий вариант.

Файлы со стилями лежат в `autodoc/publisher/rendering/styles/` (`_styles_base.jinja2` — общие
стили, `_styles_passport.jinja2` — стили, специфичные для паспорта компонента).

Чтобы стили применились, нужно попросить Владельца пространства Confluence добавить их
содержимое в Таблицу стилей пространства:

**Инструменты для пространства → Внешний вид → Таблица стилей** → вставить содержимое обоих
файлов между тегами `<style>` и `</style>`.
---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -e ".[dev]"
```

> [!NOTE]
> `pip install -e .` регистрирует консольный скрипт `autodoc`, поэтому вместо
> `python autodoc ...` можно использовать `autodoc ...` (например, `autodoc parse`).
> Ниже везде используется форма `python autodoc ...`, актуальная при запуске без установки пакета.

### 2. Конфигурация

Скопируйте примеры конфигов и заполните их:

```bash
cp configs/examples/parser_config.yaml configs/parser_config.yaml
cp configs/examples/confluence_config.yaml configs/confluence_config.yaml
```

Полное описание всех полей — в разделе [«Конфигурация»](#конфигурация) ниже.

### 3. Первый запуск

```bash
# 1. Собрать данные компонентов
python autodoc parse

# 2. Опубликовать паспорта компонентов и релизную страницу
python autodoc publish all
```

Полный список команд, флагов и примеров — в разделе [«Команды CLI»](#команды-cli).

---

## Конфигурация

Первичный формат конфигов — `.yaml`. Поддерживаются также `.yml` и `.json` (обратная
совместимость). Если файл не указан явно, он ищется автоматически — YAML имеет приоритет
над JSON.

### Конфигурация парсера

Файл: `configs/parser_config.yaml` (пример: `configs/examples/parser_config.yaml`).

#### Обязательные поля

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

#### Опциональные поля

| Поле | По умолчанию | Описание |
|------|-------------|----------|
| `platform_base_version` | `"2.0"` | Базовая версия платформы, используется для фильтрации манифестов |
| `platform_ref_type` | `"branch"` | Тип ссылки в TFS: `"branch"`, `"tag"` или `"commit"` |
| `artifactory_components_conan2_url` | `""` | URL Artifactory для Conan 2 пакетов |
| `profiles_urls` | `[]` | Список URL на YAML-файлы профилей сборки |
| `component_filter_mode` | `"exclude"` | Режим фильтрации компонентов: `"exclude"` или `"include"` (см. ниже) |
| `component_names` | `[]` | Список имён компонентов для фильтрации (см. ниже) |
| `exact_range_components` | `[]` | Список компонентов с нестандартным версионированием (см. ниже) |
| `component_branch_overrides` | `{}` | Переопределения имён веток TFS для отдельных компонентов (см. ниже) |
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

#### Компоненты с нестандартным версионированием (опционально)

**`exact_range_components`** — список имён компонентов, для которых команда `conan graph info`
формирует **точный числовой диапазон** `[>={version} <{version+1}]` вместо стандартного
`[~{version},include_prerelease]`.

Нужно для компонентов, у которых менялся формат версии (добавлялся/убирался числовой
сегмент) — в этом случае оператор `~` даёт некорректный диапазон.

```yaml
exact_range_components:
  - "some-component"
```

Пример: версия `20.11.10` для такого компонента получит диапазон `[>=20.11.10 <20.11.11]`.

#### Переопределения веток TFS для отдельных компонентов (опционально)

**`component_branch_overrides`** — словарь переопределений имён веток TFS. Ключ — имя
компонента, значение — шаблон ветки с плейсхолдером `{version}` (Python `str.format`).

Используется, когда ветка компонента не совпадает с универсальным шаблоном
`release_{version}` — например, компонент живёт в том же репозитории, что и базовый, но
имеет собственный суффикс ветки.

```yaml
component_branch_overrides:
  sqlite3_extension: "release_{version}_ext"  # → ветка release_3.34.1_ext
```

Если поле не указано или пустое — для всех компонентов используется шаблон по умолчанию.

#### Переопределения настроек Conan-профилей (опционально)

Некоторые Jinja-профили читают настройки через `os.getenv()` (например `KOS_SDK_VER` →
`compiler.toolchain_config_id`). Если нужные переменные окружения не заданы, Conan не может
собрать граф зависимостей.

Файл `profile_settings_overrides.yaml` позволяет задать такие настройки явно, не трогая
окружение. Он указывается в `parser_config.yaml`:

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

### Конфигурация публикации в Confluence

Файл: `configs/confluence_config.yaml` (пример: `configs/examples/confluence_config.yaml`).

#### Обязательные поля

| Поле | Описание |
|------|----------|
| `url` | Базовый URL Confluence, например `"https://confluence.example.com"` |
| `token` | Atlassian API-токен |
| `space` | Ключ пространства в Confluence |

#### Адресация страниц

Для каждой пары укажите `*_name` (по названию), `*_id` (по ID) или оба. Правила
приоритета между CLI, конфигом, `*_name` и `*_id` — общие для всех команд публикации
и описаны один раз в разделе [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id).

| Поле | Описание |
|------|----------|
| `strategies.release.root_parent_name` | Название корневой родительской страницы релизной документации |
| `strategies.release.root_parent_id` | ID корневой родительской страницы релизной документации |
| `strategies.profile_centric.root_parent_name` | Название корневой родительской страницы документации от профилей |
| `strategies.profile_centric.root_parent_id` | ID корневой родительской страницы документации от профилей |
| `strategies.passports.root_parent_name` | Название корневой страницы иерархии паспортов |
| `strategies.passports.root_parent_id` | ID корневой страницы иерархии паспортов |

Все три пары задают **родителя**, под которым публикуемые страницы будут созданы в дереве
Confluence — сам инструмент эти страницы не создаёт, только ищет их по названию (или ID (число в url у страницы) )
в пространстве `space` и публикует свой контент как дочерние страницы. Например, если в
Confluence уже существует страница «Паспорта компонентов» и вы хотите, чтобы паспорта
компонентов появились под ней:

```yaml
strategies:
  passports:
    root_parent_name: "Паспорта компонентов"
```

После `python autodoc publish passports` в дереве появится:

```
Паспорта компонентов      ← strategies.passports.root_parent_name (уже существовала)
└── sqlite3               ← эта и дочерние страницы содадутся автоматически
    └──sqlite 3.34.1
        └──Документация sqlite 3.34.1
```

Для публикации релизной документации (Например существует страница  «Релиз Platrorm 2.x»):

```yaml
strategies:
  release:
    root_parent_name: "Релиз Platrorm 2.x"
```

После `python autodoc publish release` в дереве появится:

```
Релиз Platrorm 2.x                            ← strategies.release.root_parent_name (уже существовала)
└── Документация к релизу Платформы 2.2.0     ← будет создана страница с релизной документацией 
```

#### Опциональные поля

| Поле | По умолчанию | Описание |
|------|-------------|----------|
| `verify_ssl` | `true` | Проверять SSL-сертификаты |
| `strategies.release.page_title` | `"Сборки компонентов Платформы"` | Заголовок корневой страницы релизной документации |
| `strategies.profile_centric.page_title` | — | Заголовок страницы профиль-центричной документации |
| `target_release_version` | `"Platform 2.2"` | Подпись текущего релиза — используется в заголовках паспортов и метке вкладки релиза |
| `confluence_request_timeout` | `30` | Тайм-аут HTTP-запросов к Confluence (секунды) |
| `publish_batch_size` | `10` | Количество паспортов, публикуемых за один пакет |
| `publish_batch_delay_seconds` | `0.0` | Задержка между пакетами (секунды). Увеличьте при перегрузке сервера |
| `title_conflict_policy` | `"error"` | Поведение при обнаружении страницы с совпадающим заголовком под другим родителем: `"error"` — прервать с исключением, `"move"` — перенести существующую страницу под ожидаемого родителя, сохранив содержимое |

Приоритет источников заголовка страницы (от высшего к низшему): флаг `--page-title` из CLI →
`strategies.profile_centric.page_title` / `strategies.release.page_title` из конфига → встроенный
заголовок по умолчанию (`"Документация от профилей"` для `publish profile`, `"Сборки компонентов
Платформы"` для `publish release`). Первый заданный источник побеждает, остальные игнорируются.

### Структура директории configs/

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

---

## Команды CLI

> [!TIP]
> Если значение флага (например, `--root-page-name`, `--passports-root-parent-name`
> или `--additional-page-profile-name`) содержит пробелы, обязательно оборачивайте
> его в кавычки: `--root-page-name "Моя страница"`. Без кавычек shell разобьёт
> значение на несколько отдельных аргументов, и команда завершится ошибкой.

### Приоритет CLI и конфига для root page name и id

Для всех команд публикации (`release`, `profile`, `passports`, `all`) корневую/родительскую
страницу можно задать по названию (`*_name`) и/или по ID (`*_id`), и в CLI-флагах, и в
конфигурации — оба варианта разрешено указывать одновременно, в том числе вместе друг с
другом (например, `--root-page-name` вместе с `--root-page-id`).

Итоговое значение определяется двумя правилами:

```
CLI > Config
*_name > *_id
```

* Если хотя бы одно из значений (название или ID) задано через CLI-флаг — конфигурация
  для этой пары полностью игнорируется, даже если в ней самой есть противоречие между
  `*_name` и `*_id`.
* Внутри источника, который в итоге используется (CLI либо конфиг), при одновременном
  указании названия и ID побеждает название.
* Если название и ID (внутри одного и того же используемого источника) указывают на
  разные страницы Confluence — публикация не останавливается: используется страница,
  найденная по названию, а в лог выводится предупреждение об этом расхождении.
* Предупреждение всегда относится только к тому источнику, который реально
  использовался в данном запуске: если конфликт возник в CLI-параметрах — предупреждение
  про CLI; если конфликт есть только в конфигурации, но применяется значение из CLI —
  предупреждение по конфигурации не выводится.

Пример: `--root-page-name "Документация к релизу 2.2" --root-page-id 123456789` — если
ID страницы «Документация к релизу 2.2» действительно равен `123456789`, это просто
подтверждение одной и той же страницы; если это разные страницы — будет использована
страница «Документация к релизу 2.2», а в лог попадёт предупреждение о расхождении.

### Глобальные флаги

Указываются перед именем команды.

| Флаг | Описание |
|------|----------|
| `--base-dir` | Корневая директория проекта (по умолчанию — текущая) |
| `--configs-dir` | Директория с конфигами (по умолчанию `<base-dir>/configs`) |
| `-v`, `--verbose` | Подробный вывод логов |

### `parse`

Собирает данные компонентов из TFS, Conan и Docker. Результат сохраняется в
`data/parsed_data.json` — все последующие команды `publish` читают этот файл.

| Флаг | Описание |
|------|----------|
| `--config` | Имя файла конфига парсера (по умолчанию ищется автоматически) |
| `--save-intermediate` | Сохранять JSON-снапшоты состояния после каждого шага пайплайна |
| `--skip-conan` | Пропустить шаг Conan graph info |
| `--skip-validation` | Пропустить HTTP-проверку ссылок в Artifactory |

```bash
python autodoc parse

# Пропустить тяжёлые шаги для быстрой отладки
python autodoc parse --skip-conan --skip-validation

# Сохранять снимок состояния после каждого шага пайплайна + отладочную информацию
python autodoc parse --save-intermediate
```

### `publish release`

Публикует релизную документацию: одна страница со всеми компонентами, их релизами и
профилями.

| Флаг | Описание |
|------|----------|
| `--page-title` | Заголовок страницы. Переопределяет `strategies.release.page_title` из конфига |
| `--root-page-name "Название"` | Название родительской страницы (переопределяет `strategies.release.root_parent_name`). Если содержит пробелы — заключите в кавычки. Приоритет над конфигом и `--root-page-id` — см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id) |
| `--root-page-id ID` | ID родительской страницы (переопределяет `strategies.release.root_parent_id`). Можно указывать вместе с `--root-page-name` |
| `--no-passport-links` | Не вставлять ссылки на паспорта компонентов |

```bash
# Использовать параметры из конфига
python autodoc publish release

# Переопределить заголовок страницы
python autodoc publish release --page-title "Платформа 2.2"

# Переопределить корневую страницу через название
python autodoc publish release --root-page-name "Документация к релизу 2.2"

# Переопределить через ID (альтернатива)
python autodoc publish release --root-page-id 123456789

# Без ссылок на паспорта компонентов
python autodoc publish release --no-passport-links
```

### `publish profile`

Публикует профиль-центричную документацию: одна страница с видом по профилям сборки →
каналам → компонентам.

| Флаг | Описание |
|------|----------|
| `--page-title` | Заголовок страницы. Переопределяет `strategies.profile_centric.page_title` из конфига |
| `--root-page-name "Название"` | Название родительской страницы (переопределяет `strategies.profile_centric.root_parent_name`). Если содержит пробелы — заключите в кавычки. Приоритет над конфигом и `--root-page-id` — см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id) |
| `--root-page-id ID` | ID родительской страницы (переопределяет `strategies.profile_centric.root_parent_id`). Можно указывать вместе с `--root-page-name` |
| `--no-passport-links` | Не вставлять ссылки на паспорта компонентов |

```bash
# Использовать параметры из конфига
# (заголовок — strategies.profile_centric.page_title, родительская страница —
#  strategies.profile_centric.root_parent_name / strategies.profile_centric.root_parent_id)
python autodoc publish profile

# Переопределить заголовок страницы
python autodoc publish profile --page-title "Профили 2.2"

# Переопределить родительскую страницу через название
python autodoc publish profile --root-page-name "Документация платформы 2.2"

# Переопределить через ID (альтернатива)
python autodoc publish profile --root-page-id 123456789

# Без ссылок на паспорта
python autodoc publish profile --no-passport-links
```

### `publish passports`

Публикует иерархию страниц паспортов компонентов: Корень → Компонент → Версия.

| Флаг | Описание |
|------|----------|
| `--passports-root-parent-name "Название"` | Название корневой страницы иерархии паспортов (переопределяет конфиг). Если содержит пробелы — заключите в кавычки. Приоритет над конфигом и `--passports-root-parent-id` — см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id) |
| `--passports-root-parent-id ID` | ID корневой страницы иерархии паспортов (переопределяет конфиг). Можно указывать вместе с `--passports-root-parent-name` |

```bash
# Корневая страница берётся из конфига (strategies.passports.root_parent_name или strategies.passports.root_parent_id)
python autodoc publish passports

# Переопределить корневую страницу через название
python autodoc publish passports --passports-root-parent-name "Паспорта компонентов"

# Переопределить через ID (альтернатива)
python autodoc publish passports --passports-root-parent-id 987654321
```

### `publish all`

Последовательно выполняет `publish passports`, затем `publish release`: паспорта и
релизная страница за один вызов, со сквозными ссылками между ними.

Пары `--passports-root-parent-name`/`--passports-root-parent-id` и
`--release-root-page-name`/`--release-root-page-id` независимы друг от друга — правила
приоритета (см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id))
применяются к каждой паре отдельно.

| Флаг | Описание |
|------|----------|
| `--passports-root-parent-name "Название"` | Название корневой страницы иерархии паспортов (переопределяет конфиг). Приоритет над конфигом и `--passports-root-parent-id` — см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id) |
| `--passports-root-parent-id ID` | ID корневой страницы иерархии паспортов (переопределяет конфиг). Можно указывать вместе с `--passports-root-parent-name` |
| `--release-root-page-name "Название"` | Название корневой родительской страницы релизной документации (переопределяет конфиг). Приоритет над конфигом и `--release-root-page-id` — см. [Приоритет CLI и конфига для root page name и id](#приоритет-cli-и-конфига-для-root-page-name-и-id) |
| `--release-root-page-id ID` | ID корневой родительской страницы релизной документации (переопределяет конфиг). Можно указывать вместе с `--release-root-page-name` |
| `--release-doc-page-name` | Заголовок страницы релизной документации (переопределяет `strategies.release.page_title` из конфига) |
| `--with-additional-page-profile` | Опубликовать дополнительную страницу в представлении от профилей (дочернюю к странице релиза) |
| `--additional-page-profile-name "Название"` | Заголовок дополнительной страницы профилей. Требует `--with-additional-page-profile` |
| `--no-passport-links` | Не вставлять ссылки на паспорта в страницы документации |

```bash
# Все параметры берутся из конфига
python autodoc publish all

# Переопределить корневые страницы через названия
python autodoc publish all \
  --passports-root-parent-name "Паспорта компонентов" \
  --release-root-page-name "Документация к релизу 2.2" \
  --release-doc-page-name "Платформа 2.2"

# Переопределить через ID (альтернатива)
python autodoc publish all \
  --passports-root-parent-id 987654321 \
  --release-doc-page-name "Платформа 2.2"

# Опубликовать с дополнительной страницей в представлении от профилей
python autodoc publish all \
  --with-additional-page-profile \
  --additional-page-profile-name "Документация от профилей"

# Без ссылок на паспорта
python autodoc publish all --no-passport-links
```

### `config`

```bash
# Список конфигурационных файлов в configs/
python autodoc config list

# Валидация конфига (автоматически определяет схему — parser или confluence)
python autodoc config validate parser_config.yaml
```

### `info`

```bash
# Версия и список возможностей
python autodoc info
```

### `logs clear`

Удаляет все файлы `*.log` из `<base-dir>/logs/`. Если файлов нет или директория
отсутствует — команда просто сообщит об этом и завершится без ошибки.

| Флаг | Описание |
|------|----------|
| `--yes`, `-y` | Не запрашивать подтверждение перед удалением |

```bash
# Спросит подтверждение
python autodoc logs clear

# Без подтверждения
python autodoc logs clear --yes
```

---

## Логирование

Логгер (`autodoc/common/logger.py`) настроен единым образом для всех модулей и используется
и парсером, и паблишером.

**Консоль** — уровень `INFO` и выше, с раскраской:

| Уровень | Цвет |
|---------|------|
| `DEBUG`, `INFO` | обычный |
| `WARNING` | жёлтый |
| `ERROR`, `CRITICAL` | красный |

Раскраска отключается автоматически, если вывод перенаправлен не в терминал (например,
`> run.log` или лог в CI) — в этом случае в поток попадает обычный текст без ANSI-кодов.

**Файл** — каждый запуск `parse` или любой команды `publish ...` дополнительно пишет один
файл уровня `DEBUG` и выше в `<base-dir>/logs/`:

```
logs/
├── parser-2026-05-27T11-40-59.log
└── publisher-2026-05-27T11-41-32.log
```

- Имя файла: `{parser|publisher}-{ГГГГ-ММ-ДДTчч-мм-сс}.log`; метка времени фиксируется один
  раз, в момент старта команды.
- Файл всегда обычный текст, без ANSI-кодов — его удобно открывать в редакторе, `grep`-ать
  или прикладывать как артефакт CI.
- Директория `logs/` создаётся автоматически при первом запуске.
- `config` и `info` файл лога не создают — они не запускают пайплайн парсера/паблишера.
- Ротация логов между запусками не производится — один файл на запуск. Для очистки
  накопившихся файлов используйте [`autodoc logs clear`](#logs-clear).

---

## Архитектура

Архитектура проекта представлена следующим образом:

```
autodoc/
├── __main__.py  — точка входа CLI (тонкая обёртка)
├── cli/         — все команды и группы Click
├── common/      — общие утилиты (логгер, retry-сессия, parallel executor)
├── parser/      — сбор данных из TFS + Conan + Docker
└── publisher/   — публикация в Confluence
```

`parser` и `publisher` — независимые друг от друга пакеты: `parser` ничего не знает о
Confluence, `publisher` ничего не знает о TFS/Conan. Единственная точка их соприкосновения —
файл `data/parsed_data.json`, который `parser` пишет, а `publisher` читает. `cli` и `common`
используются обоими.

Рядом с проектом (не внутри пакета `autodoc/`) во время работы CLI появляются рабочие
директории:

```
<base-dir>/
├── data/  — data/parsed_data.json (результат parse, вход для publish)
└── logs/  — файлы логов по одному на запуск parse/publish (см. «Логирование»)
```

**Пайплайн парсера** (последовательность шагов):

```
ManifestStep → OptionsResolveStep → ConanEnrichStep
    → DockerResolveStep → ArtifactoryValidationStep → FinalizeStep
```

Каждый шаг — изолированный объект, общается с остальными только через `PipelineContext`.
`ConanEnrichStep` и `ArtifactoryValidationStep` убираются из пайплайна при передаче флагов
`--skip-conan` / `--skip-validation`.

**Стратегии публикации** регистрируются явным словарём `STRATEGIES` в
`autodoc/publisher/strategies/registry.py` и создаются по строковому ключу функцией
`create_strategy()`:

| Стратегия | Команда CLI | Описание |
|-----------|-------------|----------|
| `release` | `publish release` | Одна страница: все компоненты с их релизами и профилями |
| `profile_centric` | `publish profile` | Одна страница: вид по профилям сборки → каналам → компонентам |
| `passports` | `publish passports` | Иерархия страниц: Корень → Компонент → Версия |

`publish all` последовательно выполняет `passports`, затем `release` — после первого шага
генерируется карта ID страниц паспортов, которую `release` использует для вставки ссылок.

---

## Шаблоны и оформление

### Jinja2-шаблоны

Хранятся в `autodoc/publisher/rendering/templates/`. Используется Confluence Storage
Format (AUI-макросы, вкладки).

```
autodoc/publisher/rendering/templates/
├── release_doc.jinja2        — страница релиза (компонентный вид)
├── profile_centric.jinja2    — профиль-центричный вид
├── component_passport.jinja2 — паспорт компонента
└── _platform_intro.jinja2    — вспомогательный partial (вводный блок платформы)
```

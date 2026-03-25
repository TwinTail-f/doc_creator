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
| `platform_version` | Версия платформы, например `"2.0"` |
| `platform_branch_name` | Ветка в TFS, например `"develop"` |
| `tfs_username` | Имя пользователя TFS |
| `tfs_token` | Personal Access Token (PAT) |
| `tfs_dep_components_url` | Базовый URL проекта DEP_Components в TFS |
| `manifests_remotes_path` | Путь к директории с манифестами в репозитории |

#### Credentials Artifactory (для валидации ссылок на сборки)

Два способа — приоритет у конфига:

```json
{
  "artifactory_username": "your_user",
  "artifactory_password": "your_password"
}
```

или через переменные окружения:

```bash
export GET_USR=your_user
export GET_PWD=your_password
```

#### Обязательные поля `confluence_config.json`

| Поле | Описание |
|------|----------|
| `url` | Базовый URL Confluence, например `"https://confluence.example.com"` |
| `token` | Atlassian API-токен |
| `space` | Ключ пространства в Confluence |

---

### 3. Запуск

#### Парсинг — собрать данные компонентов

```bash
python -m autodoc.cli parse
```

Результат сохраняется в `data/parsed_data.json`.

#### Публикация итоговой страницы релиза

```bash
python -m autodoc.cli publish release --view full --page-title "Платформа 2.0"
```

#### Публикация паспортов компонентов

```bash
python -m autodoc.cli publish passports --root-page <PAGE_ID>
```

#### Паспорта + итоговая страница за один вызов

```bash
python -m autodoc.cli publish all --root-page <PAGE_ID> --page-title "Платформа 2.0"
```

---

## Дополнительные флаги

### `parse`

| Флаг | Описание |
|------|----------|
| `--save-intermediate` | Сохранять JSON-снапшоты состояния после каждого шага пайплайна |
| `--skip-conan` | Пропустить шаг Conan graph info (полезно для быстрой отладки) |
| `--skip-validation` | Пропустить HTTP-проверку ссылок в Artifactory |

### `publish release`

| Флаг | Описание |
|------|----------|
| `--view` | Вид документа: `full` (по умолчанию), `minimal`, `profile_centric`, `combined` |
| `--page-title` | Заголовок страницы (переопределяет `page_title` из конфига) |
| `--no-passport-links` | Отключить ссылки на паспорта компонентов |

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
Шаги `--skip-conan` и `--skip-validation` убираются из пайплайна при передаче флага.

**Стратегии публикации** регистрируются через Python-метакласс и создаются по строковому ключу:

| Ключ | Описание |
|------|----------|
| `full_release` | Полная документация релиза |
| `minimal_release` | Без вариантов сборки |
| `profile_centric` | Вид по профилям сборки |
| `full_combined` | Компоненты + профили на одной странице |
| `passports` | Иерархия паспортов компонентов |

Подробное описание архитектуры и всех классов: см. `ARCHITECTURE.md`.

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

Jinja2-шаблоны для страниц Confluence хранятся в `autodoc/publisher/rendering/autodoc/publisher/rendering/templates/`.
Используется Confluence Storage Format (AUI-макросы, вкладки).

```
autodoc/publisher/rendering/templates/
├── release_doc_full.jinja2       — полная документация релиза
├── release_doc_minimal.jinja2    — минимальная документация
├── profile_centric.jinja2        — профиль-центричный вид
├── release_doc_combined.jinja2   — комбинированный вид
└── component_passport.jinja2     — паспорт компонента
```

# Проверка исторической таблицы правителей

Исследовательский проект по плакату **«Правители государства с древнейших времен»**. Начат 10 октября 2026 года. Подготовлен к публичной публикации; фотография остаётся в закрытом Google Drive.

## Исторический атлас · GitHub Pages

**[Открыть сайт: Правители советского периода, 1917–1991](https://dmitry-dev-pet.github.io/rulers-chronology-audit/)**

В новой версии доступны три переключаемых представления:

- **Плакат — основной экран**: компактная таблица с буквальными строками 097–106 исходного листа. Исправления выделены, но оригинал не переписывается.
- **Линии власти**: общая синхронизированная календарная ось для руководства партией, правительства и государственных органов. Пересекающиеся сроки отображаются одновременно.
- **Исследование**: подробные записи, оговорки и ссылки на источники.

[Описание интерфейса](docs/VIEW_MODES.md) · [GitHub Pages](docs/PAGES.md) · [workflow публикации](.github/workflows/publish-pages.yml).

Сайт не содержит исходное фото: по договорённости оно остаётся в закрытом Google Drive. Успешная техническая проверка не означает независимой научной проверки дат.

## GitHub Actions

[![Soviet chronology audit](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/actions/workflows/soviet-audit.yml/badge.svg)](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/actions/workflows/soviet-audit.yml)

**[Запуски проверки и сборки отчёта](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/actions/workflows/soviet-audit.yml)** · [Как устроен workflow](docs/ACTIONS.md).

Проверка формата данных, дат, идентификаторов и ссылок на источники; сборка HTML с тремя параллельными хронологиями, JSON и четырёх CSV. Результат успешного запуска — артефакт `soviet-chronology-report`, без исходной фотографии. Это техническая проверка структуры, **не автоматическое доказательство исторической достоверности**.

Runner — GitHub-hosted Ubuntu, без Mac, внешних языковых моделей и пользовательских секретов. Запуск при push, pull request, вручную и при переводе репозитория в public. В приватном состоянии job пропускается для исключения расхода закрытой квоты; skipped не означает успешную проверку.

## Советский период: актуальная версия

**[Три параллельные хронологии, 1917–1991](research/soviet-parallel-chronology.md): партия, правительство, высшие государственные органы.**

[Машиночитаемые данные JSON](data/soviet-parallel-chronology.json) · [Источники и границы проверки](research/soviet-parallel-sources.md) · [Уточнения к первому разбору](research/soviet-period-corrections.md).

Новая версия уточняет коллегиальное устройство ЦИК, совмещение должностей, три замещения Кузнецовым и неоднозначные переходы 1923, 1953 и 1991 годов. Не все персональные назначения независимо проверены по оригиналам актов; спорные и предварительные записи явно отмечены.

## Оригинальное фото

[Исходная фотография в Google Drive — доступ только с разрешением владельца](https://drive.google.com/file/d/1rHAcVH5_UuuqWRX0L76K7eay0KxYCt8u/view).

`1000428575.jpg`, JPEG, 1152 × 1536, 464 782 байта. SHA-256: `6c487e9427658f711cb41b930db2fadd06bb4b921423ab0b1b5bab4416a1c6ee`.

По решению пользователя оригинал хранится в Google Drive, а в GitHub — исследовательские данные, ссылки и контрольная сумма. Публичность репозитория не меняет разрешения Drive. Ни workflow, ни HTML-артефакт не получают исходную фотографию. Подробности: [GOOGLE_DRIVE_SOURCE.md](assets/original/GOOGLE_DRIVE_SOURCE.md), [photo-metadata.json](assets/original/photo-metadata.json).

## Другие материалы

- [Буквальная расшифровка 106 строк](data/poster-transcription.tsv) и [служебные строки плаката](data/section-markers.md). Исходные ошибки оставлены без исправлений.
- [Первоначальные замечания](research/initial-audit.md), [реестр](data/claim-register.csv), [исходные источники](research/source-index.md).
- Первый советский разбор: [текст](research/soviet-period-audit.md), [CSV](data/soviet-period-review.csv), [источники](research/soviet-period-sources.md). Читать вместе с [уточнениями](research/soviet-period-corrections.md).
- [Контекст](docs/context.md), [дальнейшая работа](NEXT_STEPS.md), [проверка локальной копии фото](scripts/verify_original_photo.py).

**Полная независимая проверка всех 106 строк не завершена.** Не смешивать буквальное чтение плаката, справочную хронологию должностей и интерпретацию фактической политической власти.

Задачи: [#1 — оригинал сохранён](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/1), [#2 — историческая проверка](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/2).

# Проверка и публикация исторического атласа 1617–1991

`.github/workflows/soviet-audit.yml` — исторически названный workflow офлайн-проверки всей исследовательской структуры. Запускает `python3 -m unittest discover -s tests -v`, затем строго по порядку:

```sh
python3 scripts/soviet_audit.py --revision local
python3 -m scripts.extend_century
python3 -m scripts.extend_romanovs
```

Слои независимы: буквальная фотографическая расшифровка `data/poster-transcription.tsv` неизменна; новые данные XVI–XVIII, XIX и советского периода хранятся отдельно. Тесты проверяют структурную целостность, согласованность с оригинальной таблицей и источниками, но **не научную истинность каждой датировки**.

Публичный отчёт — `index.html`, `site.css`, `site.js`, JSON, шесть CSV (включая `imperial.csv` и `romanov.csv`), README и контрольные суммы — всего **14 текстовых файлов**. Рабочая цепочка Pages `.github/workflows/publish-pages.yml` запускается только из `main` или вручную, с разрешениями `contents:read`, `pages:write`, `id-token:write`. Перед развёртыванием отвергает лишние файлы, исходный JPEG и закрытые Drive URL. Для размещения используется GitHub-hosted Ubuntu, без Mac runner и токенов личных аккаунтов.

Итоговый сайт: https://dmitry-dev-pet.github.io/rulers-chronology-audit/ . Успешный CI показывает прохождение тестов и публикации, а не первичную архивную аттестацию событий XVII–XX веков.

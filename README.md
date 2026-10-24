# Claude Anime Pets — Opus & Astra

Две аниме-девочки живут на рабочем столе Windows поверх всех окон:
- **Opus** (рыжая) — реагирует на действия Claude Code через хуки;
- **Astra** (чёрные волосы, кошачьи ушки) — управляется через `%TEMP%\codex_state.txt` (например, из Codex).

Они гуляют, кодят на ноутбуке, думают, радуются, злятся, спят ночью и иногда встречаются вдвоём.
Над головой — пузырь по действию: `</>` правки, `>_` команды, `?` поиск, `www` веб, `♥` готово.

## Запуск
```
pip install pillow
pythonw anime_pets.py
```
ЛКМ — перетащить, двойной клик — порадовать, ПКМ — меню.

## Хуки Claude Code
Скопируй блок из `hooks.json` в раздел `"hooks"` файла `~/.claude/settings.json`.
Хуки пишут состояние (`think`, `code`, `run`, `search`, `web`, `surprise`, `happy`) в `%TEMP%\clawd_state.txt`.

Состояния вручную: `idle walk code run search web think happy surprise angry look sleep coffee peek`.

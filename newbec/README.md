# newbec

Новый backend для поиска произведения по названию и преобразования машинных нот в гитарную табулатуру.

## API

```text
GET /health
GET /api/song?title=J.S.%20Bach%20Invention%201
GET /api/sources
GET /
```

Ответы имеют `status`:

- `ok` — найден MIDI/MusicXML и построена табулатура;
- `unsupported` — произведение или машинный файл не найден;
- `invalid` — не передано название.

Запуск:

```bash
python3 -m newbec.server
```

Логи пишутся в `newbec/newbec.log` и одновременно выводятся в консоль.

Порядок поиска: Mutopia, IMSLP и 10 гитарных каталогов: Tarakanov, ClassClef, Classical Guitar Sheet Music, Dirk's Guitar Page, Classtab, Daisyfield, John Wakelin, Heartistry, Practito и Free-scores.com. Список доступен через `GET /api/sources`.

Адаптеры каталогов работают в read-only режиме: находят страницу произведения, проверяют гитарную принадлежность и возвращают ссылку на MIDI/MusicXML/PDF. MIDI и MusicXML сразу превращаются в табулатуру; PDF пока только фиксируется как найденная страница и не конвертируется автоматически. Файлы намеренно не сохраняются.

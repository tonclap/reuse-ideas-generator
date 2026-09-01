# Рецепт вызова: изображение + JSON-схема в одном запросе — Алексей

Задача [T-02 (#17)](../../../issues/17), проверено **01.09.2026**. Транспорт — OpenRouter
([D-010](../COMMON_DECISION.md)). Это вход для [T-03 (#12)](../../../issues/12) и
[T-09 (#20)](../../../issues/20): рецепт лежит файлом, чтобы код не писался под догадку.

## Ответ на вопрос задачи

**Связка проходит.** Изображение и `response_format` с JSON-схемой уходят в одном вызове
`POST /chat/completions`, ответ приходит валидный по схеме. Два вызова, оба `http=200`,
`finish_reason: stop`, оба ответа проверены библиотекой `jsonschema` — валидны.

Проверялось только это. Ни качество идей, ни пригодность маршрута по цене — нет.

## Маршрут

| | |
| --- | --- |
| Модель | `google/gemini-2.5-flash-lite` |
| Провайдер | Google AI Studio, тег (slug) `google-ai-studio` |
| Эндпоинт | `POST https://openrouter.ai/api/v1/chat/completions` |

Маршрут выбран **по карточке эндпоинта, а не модели** — по D-010 поддержка схем это
свойство связки модель+провайдер:

```bash
curl -s https://openrouter.ai/api/v1/models/google/gemini-2.5-flash-lite/endpoints \
| jq -r '.data.endpoints[] | "\(.tag)  so=\((.supported_parameters|index("structured_outputs"))!=null)"'
```

На 01.09.2026 у всех пяти эндпоинтов этой модели `structured_outputs: true`. Проверены
заодно `openai/gpt-5-nano` (4 эндпоинта) и `mistralai/mistral-small-3.2-24b-instruct`
(2 эндпоинта) — там тоже везде `true`. Полная таблица кандидатов — не здесь, это
[T-11 (#23)](../../../issues/23).

**Провайдер закреплён в запросе**, иначе маршрутизация уйдёт на другой эндпоинт и рецепт
перестанет воспроизводиться:

```json
"provider": { "only": ["google-ai-studio"], "allow_fallbacks": false, "require_parameters": true }
```

- `only` принимает **тег** эндпоинта, а не `provider_name`. У Google AI Studio три тега
  (`google-ai-studio`, `/flex`, `/priority`) с разной ценой; закрепление сработало на базовый —
  видно по счёту: 281 промпт-токен × `1e-7` = `$0.0000281`, ровно тариф базового тега.
- `allow_fallbacks: false` — без него при отказе провайдера ответ придёт с другого маршрута молча.
- `require_parameters: true` — маршрут обязан поддерживать переданные параметры, а не глотать
  `response_format` молча.

## Заголовки

```
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json
```

Ключ — из `.env` ([D-027 ред. 2](../COMMON_DECISION.md): у каждого свой). `HTTP-Referer` и
`X-Title` не нужны, вызов без них проходит.

## Кодирование изображения

Отдельного поля под файл нет — изображение идёт **элементом массива `content`** того же
сообщения, что и текст, как **data URL**:

```json
{ "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,<BASE64>" } }
```

- `<BASE64>` — без переносов строк: `base64 -w0 input/item_15.jpg`.
- MIME в префиксе обязателен и должен совпадать с файлом (`file -b --mime-type`). У всего
  набора в `input/` это `image/jpeg`.
- Порядок в массиве: сначала `text`, затем `image_url` — так проверено.
- Проверенный размер: 40 718 байт → 54 292 символа base64 → тело запроса 55 585 байт.
  Весь промпт (текст + изображение) — 281 токен.

Ограничения по размеру и по числу изображений в одном сообщении **не проверялись** — на
наборе `input/` (15–67 КБ, 500 px) вопрос не возникает.

## Форма `response_format`

Схема здесь **нарочно игрушечная** и с будущей схемой T-03 не пересекается — зависимости
между задачами быть не должно. Значение имеет форма обёртки, а не поля:

```json
"response_format": {
  "type": "json_schema",
  "json_schema": {
    "name": "smoke_probe",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "dominant_color": { "type": "string",  "description": "Преобладающий цвет в кадре, одним словом" },
        "object_count":   { "type": "integer", "description": "Сколько отдельных физических предметов видно в кадре" },
        "is_indoor":      { "type": "boolean", "description": "true, если снято в помещении" }
      },
      "required": ["dominant_color", "object_count", "is_indoor"],
      "additionalProperties": false
    }
  }
}
```

Ответ приходит **строкой в `choices[0].message.content`** — это текст, его надо
`json.loads`, отдельного разобранного объекта в ответе нет.

## Воспроизвести руками

```bash
cd /path/to/reuse-ideas-generator
set -a; . ./.env; set +a
B64=$(base64 -w0 input/item_15.jpg)

curl -s https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(cat <<JSON
{
  "model": "google/gemini-2.5-flash-lite",
  "provider": { "only": ["google-ai-studio"], "allow_fallbacks": false, "require_parameters": true },
  "usage": { "include": true },
  "max_tokens": 300,
  "temperature": 0,
  "messages": [
    { "role": "user", "content": [
      { "type": "text", "text": "Опиши это изображение по схеме. Отвечай только про то, что видно в кадре." },
      { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,$B64" } }
    ] }
  ],
  "response_format": { "type": "json_schema", "json_schema": { "name": "smoke_probe", "strict": true,
    "schema": { "type": "object",
      "properties": {
        "dominant_color": { "type": "string" },
        "object_count":   { "type": "integer" },
        "is_indoor":      { "type": "boolean" } },
      "required": ["dominant_color", "object_count", "is_indoor"],
      "additionalProperties": false } } }
}
JSON
)" | jq -r '.provider, .choices[0].message.content, (.usage.cost|tostring)'
```

`"usage": { "include": true }` возвращает стоимость вызова в `usage.cost` — иначе цену
приходится считать самому.

## Что получено

Фото брались не `item_10`/`item_13` — они поимённо зашиты в пункт 3 критерия
[D-011](../COMMON_DECISION.md), и трогать их до прогона нельзя.

`item_15` (рамка-коллаж в пузырчатой плёнке на полу):

```json
{ "dominant_color": "brown", "object_count": 1, "is_indoor": true }
```

`item_03` (пять бокалов на подоконнике против света) — контрольный вызов:

```json
{ "dominant_color": "green", "object_count": 5, "is_indoor": true }
```

Контрольный вызов здесь не для качества, а чтобы отличить **«изображение дошло»** от
**«схема заполнена наугад»**: поля подобраны так, что ответ на них без картинки не даётся.
Пять бокалов сосчитаны верно, зелень за окном — преобладающий цвет кадра. Схема заполнена
по изображению, а не по одному тексту промпта.

## Стоимость

`$0.0000397` + `$0.0000405` = **`$0.00008` за оба вызова** (`usage.cost`, счёт Алексея по
D-027 ред. 2). Счётчик в `GET /api/v1/credits` отстаёт от `usage.cost` на несколько минут —
сверяться лучше по ответу.

## Чего этот рецепт не покрывает

Пишу явно, чтобы T-03 и T-09 не приняли проверенное за большее, чем оно есть:

- **Схема из трёх скалярных полей.** Вложенные объекты и массивы (идеи → шаги, оценка затрат)
  на этом маршруте **не проверялись**. Схеме T-03 нужен свой прогон — на этом же маршруте
  он дешёвый.
- **Одно изображение в сообщении.** Несколько за раз не пробовал.
- **Один маршрут.** Что связка проходит на прочих эндпоинтах — не проверено; для них
  повторить тот же smoke-test.
- **Ни цена, ни качество ответа.** Это T-11/T-14, и `gemini-2.5-flash-lite` здесь выбран как
  проверенный дешёвый маршрут для smoke-теста, а не как кандидат в прогон.
- **Скрипт не коммитился** — по D-003 код идёт через PR, а T-02 сделана прямым push. Блок
  «Воспроизвести руками» выше — полная замена скрипту.

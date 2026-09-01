# Changelog — reuse-ideas-generator

Формат: `дата · описание`.
Каждая запись = деплой или значимое изменение поведения.

## [Unreleased]

- 2026-09-01 · Проверена связка «фото + JSON-схема» в одном запросе (T-02, [#17](../../issues/17)):
  маршрут `google/gemini-2.5-flash-lite` через провайдера `google-ai-studio` принимает
  изображение и `response_format: json_schema` в одном вызове, ответ валиден по схеме.
  Рецепт вызова — [research/RECIPE_CALL_meta1ex.md](research/RECIPE_CALL_meta1ex.md); пункт
  в [about/KNOWN_ISSUES.md](about/KNOWN_ISSUES.md) закрыт для этого маршрута.
- 2026-09-01 · Та же связка проверена на опциональном **локальном** маршруте (llama.cpp
  b10731 + Gemma 4 12B QAT, `--mmproj`): изображение и схема проходят в одном вызове, ответ
  валиден, картинка прочитана. Форма `response_format` совпадает с OpenRouter — вложенная;
  плоская форма из README llama.cpp **молча игнорируется**. Модель рассуждающая: при малом
  `max_tokens` `content` приходит пустым. Подробности —
  [research/LOCAL_ROUTE_meta1ex.md](research/LOCAL_ROUTE_meta1ex.md). Тестовый путь:
  расходится с D-010 (локальное плечо там отклонено) и решением не оформлен.

## 2026-06-06

- Начало проекта: Генератор идей повторного использования контента

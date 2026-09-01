# Changelog — reuse-ideas-generator

Формат: `дата · описание`.
Каждая запись = деплой или значимое изменение поведения.

## [Unreleased]

- 2026-09-01 · Проверена связка «фото + JSON-схема» в одном запросе (T-02, [#17](../../issues/17)):
  маршрут `google/gemini-2.5-flash-lite` через провайдера `google-ai-studio` принимает
  изображение и `response_format: json_schema` в одном вызове, ответ валиден по схеме.
  Рецепт вызова — [research/RECIPE_CALL_meta1ex.md](research/RECIPE_CALL_meta1ex.md); пункт
  в [about/KNOWN_ISSUES.md](about/KNOWN_ISSUES.md) закрыт для этого маршрута.
- 2026-09-01 · Заведён опциональный **локальный** маршрут (llama.cpp + Gemma 4 12B QAT) —
  пока разведкой: [research/LOCAL_ROUTE_meta1ex.md](research/LOCAL_ROUTE_meta1ex.md). Связка
  на нём **не проверена**, сервер был недоступен. Расходится с D-010 (локальное плечо там
  отклонено) и решением не оформлено.

## 2026-06-06

- Начало проекта: Генератор идей повторного использования контента

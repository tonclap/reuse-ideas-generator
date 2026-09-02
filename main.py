"""Прогон набора фотографий через маршрут OpenRouter.

Читает все изображения из input/, на каждое делает один вызов с system prompt (T-04)
и JSON-схемой (T-03), складывает СЫРЫЕ ответы в output/<run-id>/item_XX.json и пишет
лог прогона в output/<run-id>/run.json.

Осознанно НЕ делает (ограничение стадии, TASK_DESC.md): бота, базу, repair-loop при
невалидном ответе, повторные попытки при сбое сети и тесты. Невалидный ответ и упавший
вызов записываются как факт и не чинятся — иначе прогон начнёт скрывать то, что должен
измерять.

Два независимых прогона на фото (D-014) — задача T-10; здесь один вызов на снимок.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import jsonschema
import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def load_config() -> dict:
    load_dotenv(ROOT / ".env")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def encode_image(path: Path) -> str:
    """Изображение уходит элементом content как data URL (рецепт T-02).

    MIME берётся из расширения и обязан совпадать с файлом: маршрут формат не угадывает.
    """
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{payload}"


def build_payload(config: dict, system_prompt: str, schema: dict, image_url: str) -> dict:
    route = config["route"]
    return {
        "model": route["model"],
        "provider": {
            "only": [route["provider_tag"]],
            "allow_fallbacks": route["allow_fallbacks"],
            "require_parameters": route["require_parameters"],
        },
        "temperature": route["temperature"],
        "max_tokens": route["max_tokens"],
        "usage": {"include": True},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "reuse_ideas", "strict": True, "schema": schema},
        },
    }


def check_answer(body: dict, schema: dict) -> dict:
    """Разбирает ответ маршрута. Ничего не чинит — только называет, что пришло."""
    result = {"finish_reason": None, "cost": None, "parsed": None, "valid": False, "error": None}
    try:
        choice = body["choices"][0]
    except (KeyError, IndexError):
        result["error"] = "в ответе нет choices"
        return result

    result["finish_reason"] = choice.get("finish_reason")
    result["cost"] = (body.get("usage") or {}).get("cost")

    content = (choice.get("message") or {}).get("content")
    if not content:
        result["error"] = "пустой content"
        return result

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        result["error"] = f"content не разбирается как JSON: {exc}"
        return result

    result["parsed"] = parsed
    try:
        jsonschema.validate(parsed, schema)
        result["valid"] = True
    except jsonschema.ValidationError as exc:
        result["error"] = f"ответ не валиден по схеме: {exc.message}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Прогон фотографий из input/ по маршруту из config.yaml"
    )
    parser.add_argument("items", nargs="*", help="имена без расширения (item_01 …); по умолчанию все")
    parser.add_argument("--run-id", help="идентификатор прогона; по умолчанию отметка времени")
    parser.add_argument("--dry-run", action="store_true", help="показать план и не делать вызовов")
    args = parser.parse_args()

    config = load_config()
    route = config["route"]

    input_dir = ROOT / config.get("input_dir", "input")
    photos = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if args.items:
        wanted = set(args.items)
        photos = [p for p in photos if p.stem in wanted]
        missing = wanted - {p.stem for p in photos}
        if missing:
            print(f"нет таких файлов в {input_dir}: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    if not photos:
        print(f"в {input_dir} нет изображений", file=sys.stderr)
        return 2

    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / config.get("output_dir", "output") / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        # Повторный запуск не затирает предыдущий: run-id уникален по времени. Явно
        # переданный --run-id на непустую папку — ошибка, а не повод молча смешать
        # два прогона в одном месте.
        print(f"папка прогона уже существует и не пуста: {run_dir}", file=sys.stderr)
        return 2

    system_prompt = (ROOT / config["prompt_path"]).read_text(encoding="utf-8")
    schema = json.loads((ROOT / config["schema_path"]).read_text(encoding="utf-8"))

    print(f"прогон {run_id}: {len(photos)} фото, маршрут {route['model']} @ {route['provider_tag']}")
    if args.dry_run:
        print("  --dry-run, вызовов нет:", ", ".join(p.stem for p in photos))
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "нет OPENROUTER_API_KEY: положи ключ в .env (D-027 ред. 2 — ключ у каждого свой)",
            file=sys.stderr,
        )
        return 2

    run_dir.mkdir(parents=True)
    log = {
        "run_id": run_id,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "route": route,
        "prompt_path": config["prompt_path"],
        "schema_path": config["schema_path"],
        "photos": len(photos),
        "items": [],
    }
    total_cost = 0.0
    failed = 0

    for photo in photos:
        started = time.monotonic()
        entry: dict = {"item": photo.stem, "file": photo.name}
        try:
            response = requests.post(
                route["endpoint"],
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=build_payload(config, system_prompt, schema, encode_image(photo)),
                timeout=route["timeout_sec"],
            )
            entry["http"] = response.status_code
            body = response.json()
            # Сырой ответ сохраняется целиком и ДО разбора: если разбор упадёт, ответ
            # всё равно останется на диске.
            (run_dir / f"{photo.stem}.json").write_text(
                json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if response.status_code != 200:
                entry["error"] = f"http {response.status_code}: {json.dumps(body, ensure_ascii=False)[:300]}"
            else:
                checked = check_answer(body, schema)
                entry.update({k: checked[k] for k in ("finish_reason", "cost", "valid", "error")})
                if checked["parsed"] is not None:
                    (run_dir / f"{photo.stem}.answer.json").write_text(
                        json.dumps(checked["parsed"], ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                total_cost += checked["cost"] or 0.0
        except (requests.RequestException, ValueError) as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"

        entry["seconds"] = round(time.monotonic() - started, 2)
        if entry.get("error") or not entry.get("valid"):
            failed += 1
        log["items"].append(entry)
        print(f"  {photo.stem}: {'ok' if entry.get('valid') else 'СБОЙ — ' + str(entry.get('error'))}"
              f" ({entry['seconds']} c)")

    log["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    log["total_cost"] = round(total_cost, 6)
    log["failed"] = failed
    (run_dir / "run.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"готово: {len(photos) - failed}/{len(photos)} валидных, ${total_cost:.6f}, {run_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

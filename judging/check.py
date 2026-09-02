#!/usr/bin/env python3
"""Machine half of the judging protocol (task T-06, issue #14).

Runs after a run, on saved answers. Checks the three conditions that a JSON
Schema in strict mode cannot express, then prints a worksheet for the human
half: which visible_details entry each idea leans on.

Usage:
    python3 judging/check.py judging/calibration/*.json
    python3 judging/check.py --schema schema/response.schema.json output/run-1/*.json

The --schema flag is optional: the schema lives in an unmerged pull request,
so the three checks must work without it.
"""

import argparse
import json
import sys
from pathlib import Path

MAX_TEXT = 68


def short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def filled(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check_applicability(answer: dict) -> list[str]:
    """M1: reuse_applicable=false => ideas empty and not_applicable_reason filled."""
    failures = []
    applicable = answer.get("reuse_applicable")
    ideas = answer.get("ideas") or []
    reason = answer.get("not_applicable_reason")
    if applicable is False:
        if ideas:
            failures.append(f"reuse_applicable=false, но идей {len(ideas)}, а должно быть 0")
        if not filled(reason):
            failures.append("reuse_applicable=false, но not_applicable_reason пуст")
    elif applicable is True and reason is not None:
        # Mirror half, beyond the three checks named in the task statement.
        failures.append("сверх постановки: reuse_applicable=true, но not_applicable_reason заполнен")
    return failures


def check_undetermined(answer: dict) -> list[str]:
    """M2: category=undetermined => clarifying_question is not null."""
    if answer.get("category") != "undetermined":
        return []
    if not filled(answer.get("clarifying_question")):
        return ["category=undetermined, но clarifying_question пуст"]
    return []


def match_detail(visible_detail: str, details: list) -> tuple[int | None, bool]:
    """M3: find the visible_details entry copied verbatim into the idea's field.

    Returns the entry index (longest match wins) and whether a colon follows
    the copy, as the schema requires.
    """
    best, best_len = None, -1
    for index, entry in enumerate(details):
        if isinstance(entry, str) and entry and visible_detail.startswith(entry):
            if len(entry) > best_len:
                best, best_len = index, len(entry)
    if best is None:
        return None, False
    rest = visible_detail[best_len:].lstrip()
    return best, rest.startswith(":")


def check_answer(answer: dict) -> dict:
    details = answer.get("visible_details") or []
    ideas = answer.get("ideas") or []

    failures = check_applicability(answer) + check_undetermined(answer)
    notes, links = [], []
    for number, idea in enumerate(ideas, start=1):
        field = idea.get("visible_detail") or ""
        index, has_colon = match_detail(field, details)
        links.append(index)
        if index is None:
            failures.append(f"идея {number}: visible_detail не начинается копией записи — «{short(field)}»")
        elif not has_colon:
            notes.append(f"идея {number}: копия есть, двоеточия после неё нет")
    return {"failures": failures, "notes": notes, "links": links, "details": details, "ideas": ideas}


def print_report(path: Path, answer: dict, result: dict, schema_verdict: str | None) -> None:
    print(f"\n── {path} " + "─" * max(0, 60 - len(str(path))))
    verdict = "НАРУШЕНИЯ" if result["failures"] else "чисто"
    print(f"  машина: {verdict}")
    for failure in result["failures"]:
        print(f"    ✗ {failure}")
    for note in result["notes"]:
        print(f"    · {note}")
    if schema_verdict:
        print(f"    схема: {schema_verdict}")

    question = "есть" if filled(answer.get("clarifying_question")) else "нет"
    mark = "есть" if filled(answer.get("uncertainty_note")) else "нет"
    print(
        f"  ответ: category={answer.get('category')} · reuse_applicable={answer.get('reuse_applicable')}"
        f" · идей {len(result['ideas'])} · вопрос {question} · пометка {mark}"
    )

    print("  признаки — судит человек:")
    if not result["details"]:
        print("    (список пуст)")
    for index, entry in enumerate(result["details"]):
        leaning = [str(n) for n, link in enumerate(result["links"], start=1) if link == index]
        tail = f"   ← идеи {', '.join(leaning)}" if leaning else ""
        print(f"    [{index}] {short(entry)}{tail}")
    if result["ideas"]:
        print("  идеи:")
        for number, idea in enumerate(result["ideas"], start=1):
            print(f"    {number}. {short(idea.get('idea', ''))}")
    if filled(answer.get("clarifying_question")):
        print(f"  вопрос: {short(answer['clarifying_question'])}")
    if filled(answer.get("uncertainty_note")):
        print(f"  пометка: {short(answer['uncertainty_note'])}")
    if filled(answer.get("not_applicable_reason")):
        print(f"  отказ: {short(answer['not_applicable_reason'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Три машинные проверки протокола судейства.")
    parser.add_argument("files", nargs="+", type=Path, help="JSON-ответы модели")
    parser.add_argument("--schema", type=Path, default=None, help="response.schema.json, если он под рукой")
    args = parser.parse_args()

    validator = None
    if args.schema:
        import jsonschema

        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)

    dirty = 0
    for path in args.files:
        answer = json.loads(path.read_text(encoding="utf-8"))
        result = check_answer(answer)
        schema_verdict = None
        if validator is not None:
            errors = sorted(validator.iter_errors(answer), key=lambda e: e.path)
            schema_verdict = "ok" if not errors else "; ".join(short(e.message) for e in errors[:3])
            if errors:
                result["failures"].append("не проходит схему")
        print_report(path, answer, result, schema_verdict)
        if result["failures"]:
            dirty += 1

    print(f"\nИтого: файлов {len(args.files)}, с машинными нарушениями {dirty}")
    return 1 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())

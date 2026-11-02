import json
from pathlib import Path

from openai import OpenAI

from app import db
from app.agents import Orchestrator


def check(case, out):
    errors = []
    used = [t["tool"] for t in out["trace"]]
    if out["intent"] != case["expect_intent"]:
        errors.append(f"intent {out['intent']} != {case['expect_intent']}")
    for t in case.get("expect_tools", []):
        if t not in used:
            errors.append(f"missing tool {t}")
    for t in case.get("forbid_tools", []):
        if t in used:
            errors.append(f"forbidden tool used: {t}")
    for word in case.get("reply_not_contains", []):
        if word.lower() in out["reply"].lower():
            errors.append(f"reply leaked: {word}")
    return errors


def main():
    orch = Orchestrator(OpenAI())
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    passed = 0
    for i, case in enumerate(cases):
        db.init_db()  # clean data for each case
        out = orch.handle(f"eval-{i}", case["customer_id"], case["message"])
        errors = check(case, out)
        passed += not errors
        print(f"[{'PASS' if not errors else 'FAIL'}] {case['name']}", *errors, sep="\n   " if errors else "")
    print(f"\n{passed}/{len(cases)} cases passed")


if __name__ == "__main__":
    main()
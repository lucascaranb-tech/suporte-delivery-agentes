"""Avalia o sistema com o modelo de verdade (usa a API da OpenAI).

    python -m evals.run_evals                 # roda cada caso uma vez
    python -m evals.run_evals --runs 3        # roda cada caso 3 vezes (o modelo varia)
    python -m evals.run_evals --case late_order_refund
"""
import argparse
import json
import sys
from pathlib import Path

from openai import OpenAI

from app import db
from app.agents import Orchestrator

CASES_PATH = Path(__file__).parent / "cases.json"


def check(case, turns):
    """turns: saída de handle() para cada mensagem do caso, na ordem."""
    errors = []
    last = turns[-1]
    used = [t["tool"] for turn in turns for t in turn["trace"]]
    replies = " ".join(turn["reply"] for turn in turns).lower()

    if "expect_intent" in case and last["intent"] != case["expect_intent"]:
        errors.append(f"intent {last['intent']} != {case['expect_intent']}")
    for t in case.get("expect_tools", []):
        if t not in used:
            errors.append(f"missing tool {t}")
    for t in case.get("forbid_tools", []):
        if t in used:
            errors.append(f"forbidden tool used: {t}")
    for word in case.get("reply_not_contains", []):
        if word.lower() in replies:
            errors.append(f"reply leaked: {word}")

    refunds = [r["amount"] for r in db.query_all("SELECT amount FROM refunds")]
    if "expect_refund_amount" in case:
        esperado = case["expect_refund_amount"]
        if len(refunds) != 1 or abs(refunds[0] - esperado) > 0.005:
            errors.append(f"refunds {refunds} != [{esperado}]")
    if case.get("expect_no_refund") and refunds:
        errors.append(f"unexpected refund {refunds}")
    if "expect_tickets" in case:
        tickets = db.query_one("SELECT COUNT(*) AS n FROM tickets")["n"]
        if tickets != case["expect_tickets"]:
            errors.append(f"tickets {tickets} != {case['expect_tickets']}")
    return errors


def run_case(orch, case, session_id):
    db.reset_db()  # dados limpos para cada execução
    turns = [orch.handle(session_id, case["customer_id"], msg) for msg in case["messages"]]
    return check(case, turns)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="execuções por caso")
    parser.add_argument("--case", help="roda só o caso com esse nome")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if args.case:
        cases = [c for c in cases if c["name"] == args.case]
        if not cases:
            sys.exit(f"Caso não encontrado: {args.case}")

    orch = Orchestrator(OpenAI())
    total_ok = 0
    for i, case in enumerate(cases):
        falhas = []
        for run in range(args.runs):
            erros = run_case(orch, case, f"eval-{i}-{run}")
            if erros:
                falhas.append(erros)
        ok = args.runs - len(falhas)
        total_ok += ok == args.runs
        status = "PASS" if not falhas else "FAIL"
        print(f"[{status}] {case['name']} ({ok}/{args.runs})")
        if falhas:
            print("   " + "\n   ".join(falhas[0]))

    print(f"\n{total_ok}/{len(cases)} cases passed")
    sys.exit(0 if total_ok == len(cases) else 1)


if __name__ == "__main__":
    main()

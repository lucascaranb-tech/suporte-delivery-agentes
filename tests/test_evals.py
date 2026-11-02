from app import db, tools
from evals.run_evals import check

TODAS = ["get_order", "issue_refund", "escalate_to_human"]


def saida(intent="problem", ferramentas=(), reply="ok"):
    return {"intent": intent, "reply": reply, "trace": [{"tool": t, "args": {}, "result": {}} for t in ferramentas]}


def test_aceita_reembolso_com_valor_esperado():
    tools.run_tool("issue_refund", "c1", {"order_id": "A101", "reason_code": "late_delivery"}, TODAS)
    caso = {"expect_intent": "problem", "expect_tools": ["issue_refund"], "expect_refund_amount": 7.7}
    assert check(caso, [saida(ferramentas=["issue_refund"])]) == []


def test_reprova_valor_errado_ou_ausente():
    assert check({"expect_refund_amount": 7.7}, [saida()])  # nenhum reembolso feito
    tools.issue_refund("c1", "A101", "wrong_or_spoiled_food", description="veio errado")  # 38,50
    assert check({"expect_refund_amount": 7.7}, [saida()])


def test_reprova_reembolso_indevido_e_ferramenta_proibida():
    tools.issue_refund("c1", "A101", "late_delivery")
    erros = check({"expect_no_refund": True, "forbid_tools": ["issue_refund"]},
                  [saida(ferramentas=["issue_refund"])])
    assert len(erros) == 2


def test_confere_intencao_da_ultima_mensagem_e_ferramentas_de_todas():
    turnos = [saida("general", ["get_order"]), saida("problem", ["issue_refund"])]
    caso = {"expect_intent": "problem", "expect_tools": ["get_order", "issue_refund"]}
    assert check(caso, turnos) == []


def test_confere_vazamento_e_tickets():
    assert check({"reply_not_contains": ["Açaí"]}, [saida(reply="Seu pedido tem Açaí")])
    tools.issue_refund("c1", "A100", "wrong_or_spoiled_food", description="pizza estragada")
    assert check({"expect_tickets": 1, "expect_no_refund": True}, [saida()]) == []
    assert check({"expect_tickets": 2}, [saida()])


def test_casos_de_eval_sao_validos_e_consistentes_com_os_dados():
    import json
    from pathlib import Path

    casos = json.loads((Path(__file__).parent.parent / "evals" / "cases.json").read_text(encoding="utf-8"))
    assert len({c["name"] for c in casos}) == len(casos)
    clientes = {r["customer_id"] for r in db.query_all("SELECT customer_id FROM orders")}
    for c in casos:
        assert c["customer_id"] in clientes and c["messages"], c["name"]
    por_nome = {c["name"]: c for c in casos}
    # Os valores esperados nos evals precisam bater com o que o código calcula
    assert tools.issue_refund("c1", "A101", "late_delivery")["amount"] == por_nome["late_order_refund"]["expect_refund_amount"]
    db.reset_db()
    assert tools.issue_refund("c1", "A101", "missing_item", item_name="batata")["amount"] == \
        por_nome["missing_item_two_turns"]["expect_refund_amount"]

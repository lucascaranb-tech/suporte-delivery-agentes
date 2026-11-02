from app import config, db, tools

TODAS = ["get_order", "list_my_orders", "search_policy", "issue_refund", "escalate_to_human"]


def reembolsos():
    return db.query_all("SELECT * FROM refunds")


def tickets():
    return db.query_all("SELECT * FROM tickets")


def test_total_dos_pedidos_bate_com_a_soma_dos_itens():
    for o in db.query_all("SELECT id FROM orders"):
        pedido = tools.get_order("c1", o["id"]) if o["id"] != "B200" else tools.get_order("c2", "B200")
        assert round(sum(i["price"] for i in pedido["items"]), 2) == pedido["total"]


# ---------- isolamento entre clientes ----------

def test_cliente_nao_ve_pedido_de_outro():
    assert tools.get_order("c1", "B200") == {"error": "order_not_found"}
    assert tools.issue_refund("c1", "B200", "wrong_or_spoiled_food", description="veio errado") == {
        "error": "order_not_found"
    }
    assert tools.escalate_to_human("c1", "B200", "teste") == {"error": "order_not_found"}
    assert reembolsos() == [] and tickets() == []


def test_id_do_pedido_aceita_minuscula():
    assert tools.get_order("c1", "a101")["id"] == "A101"


def test_lista_apenas_pedidos_do_proprio_cliente():
    ids = {o["id"] for o in tools.list_my_orders("c1")["orders"]}
    assert ids == {"A100", "A101", "A102"}


# ---------- atraso ----------

def test_atraso_acima_de_30_min_reembolsa_20_por_cento():
    r = tools.issue_refund("c1", "A101", "late_delivery")
    assert r["status"] == "refunded" and r["amount"] == 7.70
    assert [x["amount"] for x in reembolsos()] == [7.70]


def test_pedido_no_prazo_nao_tem_direito_a_reembolso_por_atraso():
    r = tools.issue_refund("c1", "A100", "late_delivery")
    assert r["error"] == "not_eligible"
    assert reembolsos() == []


def test_atraso_exatamente_no_limite_nao_reembolsa(monkeypatch):
    db.execute("UPDATE orders SET delay_minutes=30 WHERE id='A101'")
    assert tools.issue_refund("c1", "A101", "late_delivery")["error"] == "not_eligible"


def test_segundo_reembolso_do_mesmo_pedido_e_bloqueado():
    tools.issue_refund("c1", "A101", "late_delivery")
    assert tools.issue_refund("c1", "A101", "wrong_or_spoiled_food", description="veio frio") == {
        "error": "already_refunded"
    }
    assert len(reembolsos()) == 1


# ---------- item faltando ----------

def test_item_faltando_reembolsa_o_preco_do_item():
    r = tools.issue_refund("c1", "A101", "missing_item", item_name="batata")
    assert r["status"] == "refunded" and r["amount"] == 8.60


def test_nome_do_item_ignora_acento_e_maiuscula():
    assert tools.issue_refund("c1", "A101", "missing_item", item_name="BATATA MEDIA")["amount"] == 8.60


def test_item_faltando_exige_nome_e_que_ele_exista_no_pedido():
    assert tools.issue_refund("c1", "A101", "missing_item")["error"] == "item_name_required"
    assert tools.issue_refund("c1", "A101", "missing_item", item_name="a")["error"] == "item_name_required"
    r = tools.issue_refund("c1", "A101", "missing_item", item_name="sushi")
    assert r["error"] == "item_not_in_order" and "X-Bacon" in r["items"]
    assert reembolsos() == []


# ---------- comida errada ou estragada ----------

def test_comida_errada_reembolsa_ate_100_por_cento():
    r = tools.issue_refund("c1", "A101", "wrong_or_spoiled_food", description="veio fria e errada")
    assert r["status"] == "refunded" and r["amount"] == 38.50


def test_comida_errada_com_percentual_parcial():
    r = tools.issue_refund("c1", "A101", "wrong_or_spoiled_food", description="veio fria", percentage=50)
    assert r["amount"] == 19.25


def test_comida_errada_valida_descricao_e_percentual():
    assert tools.issue_refund("c1", "A101", "wrong_or_spoiled_food")["error"] == "description_required"
    for pct in (0, 101, "abc", None):
        r = tools.issue_refund("c1", "A101", "wrong_or_spoiled_food", description="veio errada", percentage=pct)
        assert r["error"] == "invalid_percentage"
    assert reembolsos() == []


# ---------- regras gerais ----------

def test_pedido_em_andamento_nao_pode_ser_reembolsado():
    assert tools.issue_refund("c1", "A102", "late_delivery") == {"error": "order_not_delivered"}


def test_motivo_fora_da_politica_e_recusado():
    r = tools.issue_refund("c1", "A100", "regret")
    assert r["error"] == "invalid_reason"
    assert reembolsos() == []


def test_acima_do_limite_vai_para_atendente_e_nao_reembolsa():
    r = tools.issue_refund("c1", "A100", "wrong_or_spoiled_food", description="pizza estragada")
    assert r["status"] == "needs_human_approval" and r["amount"] == 62.90
    assert reembolsos() == []
    assert len(tickets()) == 1 and tickets()[0]["summary"].startswith("[REEMBOLSO]")


def test_pedir_de_novo_nao_cria_ticket_duplicado():
    primeiro = tools.issue_refund("c1", "A100", "wrong_or_spoiled_food", description="pizza estragada")
    segundo = tools.issue_refund("c1", "A100", "wrong_or_spoiled_food", description="pizza estragada")
    assert primeiro["ticket_id"] == segundo["ticket_id"]
    assert len(tickets()) == 1


def test_limite_automatico_e_configuravel(monkeypatch):
    monkeypatch.setattr(config, "AUTO_REFUND_LIMIT", 5.0)
    r = tools.issue_refund("c1", "A101", "late_delivery")  # 7,70 > 5
    assert r["status"] == "needs_human_approval"


# ---------- run_tool ----------

def test_modelo_nao_consegue_passar_valor_nem_customer_id():
    r = tools.run_tool("issue_refund", "c1", {"order_id": "A100", "reason_code": "late_delivery", "amount": 40},
                       TODAS)
    assert r == {"error": "invalid_arguments"}
    r = tools.run_tool("get_order", "c1", {"order_id": "B200", "customer_id": "c2"}, TODAS)
    assert r == {"error": "invalid_arguments"}
    assert reembolsos() == []


def test_ferramenta_fora_da_lista_do_agente_e_recusada():
    r = tools.run_tool("issue_refund", "c1", {"order_id": "A101", "reason_code": "late_delivery"},
                       ["get_order"])
    assert r == {"error": "tool_not_allowed"}
    assert reembolsos() == []


def test_erro_inesperado_na_ferramenta_nao_derruba(monkeypatch):
    def quebra(customer_id, order_id):
        raise RuntimeError("falha")

    monkeypatch.setitem(tools.REGISTRY, "get_order", quebra)
    assert tools.run_tool("get_order", "c1", {"order_id": "A101"}, TODAS) == {"error": "internal_error"}


def test_toda_chamada_vai_para_a_auditoria():
    tools.run_tool("get_order", "c1", {"order_id": "A101"}, TODAS)
    tools.run_tool("issue_refund", "c1", {"order_id": "A101", "reason_code": "late_delivery"}, TODAS)
    tools.run_tool("get_order", "c1", {"order_id": "A101"}, ["issue_refund"])  # recusada, mas auditada
    assert [r["tool"] for r in db.query_all("SELECT tool FROM audit_log ORDER BY id")] == [
        "get_order", "issue_refund", "get_order",
    ]


def test_schema_do_reembolso_nao_tem_valor_nem_customer_id():
    props = tools.SCHEMAS["issue_refund"]["function"]["parameters"]["properties"]
    assert "amount" not in props and "customer_id" not in props
    assert props["reason_code"]["enum"] == list(tools.REFUND_REASONS)
    for esquema in tools.SCHEMAS.values():
        assert "customer_id" not in esquema["function"]["parameters"]["properties"]


# ---------- banco ----------

def test_init_db_nao_apaga_dados_existentes():
    tools.issue_refund("c1", "A101", "late_delivery")
    db.init_db()
    assert len(reembolsos()) == 1


def test_init_db_recria_banco_em_formato_antigo():
    tools.issue_refund("c1", "A101", "late_delivery")
    c = db._conn()
    c.execute("PRAGMA user_version = 1")
    c.commit()
    c.close()
    db.init_db()
    assert reembolsos() == []

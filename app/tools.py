import json
import logging
import unicodedata

from . import config, db

log = logging.getLogger(__name__)

# Definido pelo Orchestrator na inicialização
policy_index = None

REFUND_REASONS = ("late_delivery", "missing_item", "wrong_or_spoiled_food")


def _norm(texto):
    texto = unicodedata.normalize("NFKD", str(texto).strip().lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _own_order(customer_id, order_id):
    o = db.query_one(
        "SELECT * FROM orders WHERE id=? AND customer_id=?",
        (str(order_id).upper(), customer_id),
    )
    if o:
        o["items"] = json.loads(o["items"])
    return o


def get_order(customer_id, order_id):
    o = _own_order(customer_id, order_id)
    return o if o else {"error": "order_not_found"}


def list_my_orders(customer_id):
    rows = db.query_all(
        "SELECT id, restaurant, status, total FROM orders WHERE customer_id=?",
        (customer_id,),
    )
    return {"orders": rows}


def search_policy(customer_id, query):
    if policy_index is None:
        return {"error": "policy_unavailable"}
    return {"policy": policy_index.search(query)}


def _create_ticket(customer_id, order_id, summary):
    return db.execute(
        "INSERT INTO tickets(customer_id, order_id, summary) VALUES (?,?,?)",
        (customer_id, order_id, summary),
    )


def escalate_to_human(customer_id, order_id, summary):
    o = _own_order(customer_id, order_id)
    if not o:
        return {"error": "order_not_found"}
    return {"status": "escalated", "ticket_id": _create_ticket(customer_id, o["id"], summary)}


def _calcular_reembolso(o, reason_code, item_name, description, percentage):
    """Aplica a política de reembolso. Devolve {'amount', 'detail'} ou {'error', ...}.
    O valor nunca vem do modelo nem do cliente."""
    if reason_code == "late_delivery":
        if o["delay_minutes"] <= config.LATE_MINUTES:
            return {
                "error": "not_eligible",
                "detail": f"Atraso de {o['delay_minutes']} min; a política exige mais de {config.LATE_MINUTES} min.",
            }
        pct = round(config.LATE_REFUND_RATE * 100)
        return {
            "amount": o["total"] * config.LATE_REFUND_RATE,
            "detail": f"atraso de {o['delay_minutes']} min: {pct}% do pedido",
        }

    if reason_code == "missing_item":
        alvo = _norm(item_name or "")
        if len(alvo) < 3:
            return {"error": "item_name_required"}
        achados = [i for i in o["items"] if alvo in _norm(i["name"]) or _norm(i["name"]) in alvo]
        nomes = [i["name"] for i in o["items"]]
        if not achados:
            return {"error": "item_not_in_order", "items": nomes}
        if len(achados) > 1:
            return {"error": "ambiguous_item", "items": [i["name"] for i in achados]}
        return {"amount": achados[0]["price"], "detail": f"item faltando: {achados[0]['name']}"}

    if reason_code == "wrong_or_spoiled_food":
        if not description or len(description.strip()) < 5:
            return {"error": "description_required"}
        try:
            pct = int(percentage)
        except (TypeError, ValueError):
            return {"error": "invalid_percentage"}
        if not 1 <= pct <= 100:
            return {"error": "invalid_percentage"}
        return {
            "amount": o["total"] * pct / 100,
            "detail": f"comida errada/estragada, {pct}% do pedido: {description.strip()}",
        }

    return {"error": "invalid_reason", "allowed": list(REFUND_REASONS)}


def issue_refund(customer_id, order_id, reason_code, item_name=None, description=None, percentage=100):
    o = _own_order(customer_id, order_id)
    if not o:
        return {"error": "order_not_found"}
    if o["status"] != "delivered":
        return {"error": "order_not_delivered"}
    if db.query_one("SELECT id FROM refunds WHERE order_id=?", (o["id"],)):
        return {"error": "already_refunded"}

    calculo = _calcular_reembolso(o, reason_code, item_name, description, percentage)
    if "error" in calculo:
        return calculo
    amount = round(calculo["amount"], 2)

    # Regra de negócio rígida, aplicada no código (não só no prompt)
    if amount > config.AUTO_REFUND_LIMIT:
        pendente = db.query_one(
            "SELECT id FROM tickets WHERE order_id=? AND summary LIKE '[REEMBOLSO]%'", (o["id"],)
        )
        ticket_id = pendente["id"] if pendente else _create_ticket(
            customer_id, o["id"], f"[REEMBOLSO] R$ {amount:.2f} - {calculo['detail']}"
        )
        return {"status": "needs_human_approval", "amount": amount, "ticket_id": ticket_id}

    db.execute(
        "INSERT INTO refunds(order_id, amount, reason) VALUES (?,?,?)",
        (o["id"], amount, calculo["detail"]),
    )
    return {"status": "refunded", "amount": amount, "rule": calculo["detail"]}


REGISTRY = {
    "get_order": get_order,
    "list_my_orders": list_my_orders,
    "search_policy": search_policy,
    "escalate_to_human": escalate_to_human,
    "issue_refund": issue_refund,
}


def _schema(name, description, props=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props or {},
                "required": required or [],
            },
        },
    }


# customer_id NÃO aparece em nenhum schema: o servidor injeta.
# issue_refund também não recebe valor: o código calcula pela política.
SCHEMAS = {
    "get_order": _schema(
        "get_order", "Get status, items (with prices), total and delay of one order of the customer.",
        {"order_id": {"type": "string"}}, ["order_id"]),
    "list_my_orders": _schema(
        "list_my_orders", "List the recent orders of the customer."),
    "search_policy": _schema(
        "search_policy", "Search the company refund and delivery policies.",
        {"query": {"type": "string"}}, ["query"]),
    "escalate_to_human": _schema(
        "escalate_to_human", "Open a ticket for a human agent when the case is out of policy or unclear.",
        {"order_id": {"type": "string"}, "summary": {"type": "string"}}, ["order_id", "summary"]),
    "issue_refund": _schema(
        "issue_refund",
        "Request a refund for a delivered order. The system calculates the amount from the company "
        "policy; never try to set an amount. Only call after checking the order and the policy.",
        {
            "order_id": {"type": "string"},
            "reason_code": {"type": "string", "enum": list(REFUND_REASONS)},
            "item_name": {"type": "string", "description": "Only for missing_item: which item was missing"},
            "description": {"type": "string", "description": "Only for wrong_or_spoiled_food: what was wrong"},
            "percentage": {
                "type": "integer", "minimum": 1, "maximum": 100,
                "description": "Only for wrong_or_spoiled_food: share of the order to refund (default 100)",
            },
        },
        ["order_id", "reason_code"]),
}


def run_tool(name, customer_id, args, allowed):
    if name not in allowed or name not in REGISTRY:
        result = {"error": "tool_not_allowed"}
    else:
        try:
            result = REGISTRY[name](customer_id, **args)
        except TypeError:
            result = {"error": "invalid_arguments"}
        except Exception:
            log.exception("Falha na ferramenta %s", name)
            result = {"error": "internal_error"}
    db.execute(
        "INSERT INTO audit_log(customer_id, tool, args, result) VALUES (?,?,?,?)",
        (customer_id, name, json.dumps(args, ensure_ascii=False), json.dumps(result, ensure_ascii=False)),
    )
    return result

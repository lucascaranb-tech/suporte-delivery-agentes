import json
from . import db
from .config import AUTO_REFUND_LIMIT

# Set by the Orchestrator at startup
policy_index = None


def _own_order(customer_id, order_id):
    return db.query_one(
        "SELECT * FROM orders WHERE id=? AND customer_id=?",
        (str(order_id).upper(), customer_id),
    )


def get_order(customer_id, order_id):
    o = _own_order(customer_id, order_id)
    if not o:
        return {"error": "order_not_found"}
    o["items"] = json.loads(o["items"])
    return o


def list_my_orders(customer_id):
    rows = db.query_all(
        "SELECT id, restaurant, status, total FROM orders WHERE customer_id=?",
        (customer_id,),
    )
    return {"orders": rows}


def search_policy(customer_id, query):
    return {"policy": policy_index.search(query)}


def escalate_to_human(customer_id, order_id, summary):
    tid = db.execute(
        "INSERT INTO tickets(customer_id, order_id, summary) VALUES (?,?,?)",
        (customer_id, order_id, summary),
    )
    return {"status": "escalated", "ticket_id": tid}


def issue_refund(customer_id, order_id, amount, reason):
    o = _own_order(customer_id, order_id)
    if not o:
        return {"error": "order_not_found"}
    if o["status"] != "delivered":
        return {"error": "order_not_delivered"}
    if amount <= 0 or amount > o["total"]:
        return {"error": "invalid_amount", "order_total": o["total"]}
    if db.query_one("SELECT id FROM refunds WHERE order_id=?", (o["id"],)):
        return {"error": "already_refunded"}
    # Hard business rule, enforced in code (not only in the prompt)
    if amount > AUTO_REFUND_LIMIT:
        ticket = escalate_to_human(customer_id, o["id"], f"Refund R$ {amount:.2f}: {reason}")
        return {"status": "needs_human_approval", **ticket}
    db.execute(
        "INSERT INTO refunds(order_id, amount, reason) VALUES (?,?,?)",
        (o["id"], amount, reason),
    )
    return {"status": "refunded", "amount": amount}


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


# Note: customer_id is NOT in any schema. The server injects it.
SCHEMAS = {
    "get_order": _schema(
        "get_order", "Get status, items, total and delay of one order of the customer.",
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
        "issue_refund", "Refund a delivered order. Only after checking the order and the policy.",
        {"order_id": {"type": "string"},
         "amount": {"type": "number", "description": "Amount in BRL"},
         "reason": {"type": "string"}},
        ["order_id", "amount", "reason"]),
}


def run_tool(name, customer_id, args, allowed):
    if name not in allowed or name not in REGISTRY:
        result = {"error": "tool_not_allowed"}
    else:
        try:
            result = REGISTRY[name](customer_id, **args)
        except TypeError:
            result = {"error": "invalid_arguments"}
    db.execute(
        "INSERT INTO audit_log(customer_id, tool, args, result) VALUES (?,?,?,?)",
        (customer_id, name, json.dumps(args, ensure_ascii=False), json.dumps(result, ensure_ascii=False)),
    )
    return result
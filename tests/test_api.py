import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.agents import Orchestrator
from tests.conftest import ClienteFalso, PoliticaFalsa, resposta, triagem


@pytest.fixture
def api(monkeypatch):
    """Sem o lifespan: o orquestrador é montado com um cliente falso (sem API)."""
    cliente = ClienteFalso([triagem("general"), resposta(content="Olá!")] * 3)
    main.state["orch"] = Orchestrator(cliente, policy_index=PoliticaFalsa())
    yield TestClient(main.app)
    main.state.clear()


def test_health(api):
    assert api.get("/health").json() == {"ok": True}


def test_chat_responde(api):
    r = api.post("/chat", json={"session_id": "s1", "customer_id": "c1", "message": "oi"})
    assert r.status_code == 200 and r.json()["reply"] == "Olá!"


def test_chat_recusa_sessao_de_outro_cliente(api):
    api.post("/chat", json={"session_id": "s1", "customer_id": "c1", "message": "oi"})
    r = api.post("/chat", json={"session_id": "s1", "customer_id": "c2", "message": "oi"})
    assert r.status_code == 403


@pytest.mark.parametrize("corpo", [
    {"session_id": "s1", "customer_id": "c1", "message": ""},
    {"session_id": "s1", "customer_id": "c1", "message": "x" * 1001},
    {"session_id": "", "customer_id": "c1", "message": "oi"},
    {"session_id": "s1", "customer_id": "c" * 33, "message": "oi"},
    {"session_id": "s1", "message": "oi"},
])
def test_chat_valida_a_entrada(api, corpo):
    assert api.post("/chat", json=corpo).status_code == 422


def test_audit_bloqueado_sem_admin_token_configurado(api, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    assert api.get("/audit").status_code == 403
    assert api.get("/audit", headers={"X-Admin-Token": ""}).status_code == 403


def test_audit_exige_o_token_certo(api, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "segredo")
    assert api.get("/audit").status_code == 403
    assert api.get("/audit", headers={"X-Admin-Token": "errado"}).status_code == 403
    r = api.get("/audit", headers={"X-Admin-Token": "segredo"})
    assert r.status_code == 200 and r.json() == []

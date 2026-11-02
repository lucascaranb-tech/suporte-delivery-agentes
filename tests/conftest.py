import json
from types import SimpleNamespace

import pytest

from app import db, tools


@pytest.fixture(autouse=True)
def banco_isolado(tmp_path, monkeypatch):
    """Cada teste usa um banco temporário novo, com os dados de exemplo."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "teste.db")
    db.reset_db()
    yield


class PoliticaFalsa:
    def search(self, query, k=2):
        return ["## Política de teste"]


class ClienteFalso:
    """Imita client.chat.completions.create devolvendo respostas roteirizadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.respostas.pop(0)


def resposta(content=None, tool_calls=None):
    def dump(exclude_none=True):
        return {"role": "assistant", "content": content}

    msg = SimpleNamespace(content=content, tool_calls=tool_calls, model_dump=dump)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def triagem(intent):
    return resposta(content=json.dumps({"intent": intent}))


def chamada(nome, args, call_id="call_1"):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=nome, arguments=json.dumps(args))
    )


@pytest.fixture
def politica_falsa(monkeypatch):
    monkeypatch.setattr(tools, "policy_index", PoliticaFalsa())
    return PoliticaFalsa()

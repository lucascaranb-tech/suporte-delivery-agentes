import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

from . import config, db
from .agents import Orchestrator, SessionOwnerError

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    state["orch"] = Orchestrator(OpenAI())
    yield


app = FastAPI(title="Delivery Support Agents", lifespan=lifespan)


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    customer_id: str = Field(min_length=1, max_length=32)  # em produção viria do token de login
    message: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(body: ChatIn):
    try:
        return state["orch"].handle(body.session_id, body.customer_id, body.message)
    except SessionOwnerError:
        raise HTTPException(status_code=403, detail="Essa sessão pertence a outro cliente.")


@app.get("/audit")
def audit(x_admin_token: str = Header(default="")):
    """Só responde com o ADMIN_TOKEN configurado e enviado no header X-Admin-Token."""
    if not config.ADMIN_TOKEN or not secrets.compare_digest(
        x_admin_token.encode(), config.ADMIN_TOKEN.encode()
    ):
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    return db.query_all("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")

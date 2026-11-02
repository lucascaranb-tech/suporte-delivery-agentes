from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

from . import db
from .agents import Orchestrator

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    state["orch"] = Orchestrator(OpenAI())
    yield


app = FastAPI(title="Delivery Support Agents", lifespan=lifespan)


class ChatIn(BaseModel):
    session_id: str
    customer_id: str  # in production this comes from the auth token
    message: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(body: ChatIn):
    return state["orch"].handle(body.session_id, body.customer_id, body.message)


@app.get("/audit")
def audit():
    return db.query_all("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50")
# Delivery Support Agents

A multi-agent customer support system for food delivery, built with Python, FastAPI and the OpenAI API (gpt-4o-mini).

A customer writes about a late order, a missing item or a refund. A triage agent understands the intent and sends the chat to the right specialist agent. The agent uses tools to read the order, check the company policy and issue a refund, or escalate to a human.

## Why this project

This is my third AI agent project, after a restaurant order agent and a digital bank agent. Here I focus on what makes agents safe and reliable in production:

- Multi-agent routing (triage agent + specialist agents)
- Tool calling with a small set of tools per agent
- RAG over policy documents (embeddings + cosine similarity)
- Guardrails: PII masking, prompt injection detection, hard refund limit in code
- Audit log of every tool call
- Automatic evals to test agent behavior

## Architecture

    Customer message
          |
     Guardrails (mask CPF/card, detect injection)
          |
     Triage agent --> unsafe --> safe fixed reply
          |
     tracking / problem / general
          |
     Specialist agent <--> Tools (orders, policy RAG, refund, escalate)
          |
     Reply + tool trace + audit log

## Key design decisions

1. **The LLM never sends customer_id.** The server injects it into every tool call. The model cannot read orders of another customer, even if the user asks.
2. **Business rules live in code, not only in the prompt.** The refund limit (R$ 50), the duplicate refund check and the order ownership check are in `tools.py`. If the model makes a mistake, the code still protects the money.
3. **Least privilege.** Each agent only has the tools it needs. The tracking agent cannot refund.
4. **Evals first.** `evals/cases.json` has cases for normal flows, data leaks, prompt injection and refund abuse.

## Run it

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # add your OpenAI key
    uvicorn app.main:app --reload

Try it:

    curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
      -d '{"session_id":"s1","customer_id":"c1","message":"Meu pedido A101 chegou 45 min atrasado, quero reembolso"}'

Run the evals:

    python -m evals.run_evals

## Project structure

- `app/agents.py` - triage, specialist agents, tool-calling loop
- `app/tools.py` - tools, schemas, business rules, audit log
- `app/rag.py` - policy search with embeddings
- `app/guardrails.py` - PII masking and injection detection
- `evals/` - test cases and eval runner

## Next steps

- Add authentication (JWT) to get customer_id
- Replace SQLite with PostgreSQL and the in-memory index with pgvector
- Add tracing (OpenTelemetry or Langfuse) and cost metrics
- Add a human-in-the-loop dashboard for escalated tickets
- Add more eval cases and an LLM-as-judge for tone and quality
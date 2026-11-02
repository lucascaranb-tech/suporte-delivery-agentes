import os
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = "text-embedding-3-small"
AUTO_REFUND_LIMIT = float(os.getenv("AUTO_REFUND_LIMIT", "50"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

MAX_AGENT_STEPS = 5
MAX_HISTORY = 10
TRIAGE_HISTORY = 4
MAX_SESSIONS = 1000

# Regras de reembolso aplicadas no código (espelham app/policies.md)
LATE_MINUTES = 30
LATE_REFUND_RATE = 0.20

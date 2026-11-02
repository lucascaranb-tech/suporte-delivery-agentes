import os
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = "text-embedding-3-small"
AUTO_REFUND_LIMIT = float(os.getenv("AUTO_REFUND_LIMIT", "50"))
MAX_AGENT_STEPS = 5
MAX_HISTORY = 10
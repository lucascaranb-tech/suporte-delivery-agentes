import numpy as np
from .config import EMBED_MODEL


class PolicyIndex:
    """Tiny in-memory RAG: one chunk per '## ' section of the policy file."""

    def __init__(self, client, path):
        self.client = client
        text = path.read_text(encoding="utf-8")
        self.chunks = [c.strip() for c in text.split("\n## ") if c.strip()]
        self.chunks = [c if c.startswith("##") else "## " + c for c in self.chunks]
        resp = client.embeddings.create(model=EMBED_MODEL, input=self.chunks)
        self.vecs = np.array([e.embedding for e in resp.data])

    def search(self, query, k=2):
        q = self.client.embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding
        q = np.array(q)
        sims = self.vecs @ q / (np.linalg.norm(self.vecs, axis=1) * np.linalg.norm(q))
        top = np.argsort(sims)[::-1][:k]
        return [self.chunks[i] for i in top]
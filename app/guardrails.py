import re

INJECTION = re.compile(
    r"(ignore|ignora|esque[cç]a|desconsidere).{0,40}(instru|regras|prompt|anterior)"
    r"|system prompt|modo desenvolvedor|developer mode",
    re.IGNORECASE,
)
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def mask_pii(text: str) -> str:
    text = CARD.sub("[CARTAO]", text)
    return CPF.sub("[CPF]", text)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION.search(text))


UNSAFE_REPLY = (
    "Não consigo ajudar com esse tipo de pedido. "
    "Posso ajudar a acompanhar um pedido ou resolver um problema com ele."
)
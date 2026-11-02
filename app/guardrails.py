import re

INJECTION = re.compile(
    r"(ignor[ae]|esque[cç]a|desconsidere|disregard|forget|override)"
    r".{0,40}(instru|regras|prompt|anterior|acima|previous|above|rules)"
    r"|system prompt|prompt do sistema|modo desenvolvedor|developer mode",
    re.IGNORECASE,
)
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
CPF_FORMATADO = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
ONZE_DIGITOS = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d) * (n + 1 - i) for i, d in enumerate(digitos[:n]))
        if (soma * 10 % 11) % 10 != int(digitos[n]):
            return False
    return True


def _mascarar_se_cpf(m):
    return "[CPF]" if _cpf_valido(m.group()) else m.group()


def mask_pii(text: str) -> str:
    """Mascara cartão e CPF. Com 11 dígitos sem pontuação só mascara se o CPF for válido,
    para não esconder números de celular."""
    text = CARD.sub("[CARTAO]", text)
    text = CPF_FORMATADO.sub("[CPF]", text)
    return ONZE_DIGITOS.sub(_mascarar_se_cpf, text)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION.search(text))


UNSAFE_REPLY = (
    "Não consigo ajudar com esse tipo de pedido. "
    "Posso ajudar a acompanhar um pedido ou resolver um problema com ele."
)

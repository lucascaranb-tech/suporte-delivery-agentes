# Agentes para Suporte em Entregas

- Sistema de suporte pós-venda para delivery, feito com Python, FastAPI e a API da OpenAI (gpt-4o-mini)
- Um agente de triagem identifica a intenção do cliente (acompanhar pedido, problema, dúvida) e encaminha para o agente especialista
- Cada agente só usa as ferramentas da sua lista: consultar pedido, buscar política (RAG), reembolsar e escalar para um atendente
- O valor do reembolso é calculado pelo código a partir da política, e não pelo modelo

## Por que este projeto?

Este é o meu terceiro projeto com agentes de IA, depois de pedidos em restaurante e de um banco digital. O foco aqui é o que torna um agente seguro para produção:

- Roteamento entre agentes (triagem com o histórico da conversa + especialistas)
- Tool calling com um conjunto restrito de ferramentas para cada agente
- RAG sobre o documento de políticas (embeddings e similaridade de cosseno)
- Regras de negócio no código: reembolso calculado pela política, teto de reembolso automático, um reembolso por pedido
- Guardrails: mascaramento de CPF e cartão, detecção de prompt injection, isolamento de dados por cliente
- Registro de auditoria de todas as chamadas de ferramenta (`/audit` protegido por token)
- Testes automatizados sem API (pytest) e evals com o modelo de verdade

## Arquitetura

```
cliente -> FastAPI (/chat)
             |
             v
   Guardrails: mascara CPF/cartão, detecta injeção
             |
             v
   Triagem (LLM, vê as últimas mensagens da sessão)
             |
   +---------+------------------+--------------+
   v                            v              v
tracking                     problem         general        unsafe
get_order                    get_order       search_policy  (recusa)
list_my_orders               list_my_orders
                             search_policy
                             issue_refund  <- valor calculado no código
                             escalate_to_human
             |
             v
   audit log (SQLite) em toda chamada de ferramenta
```

## Regras aplicadas no código

- `customer_id` não aparece no schema de nenhuma ferramenta: o servidor injeta o valor, e um pedido de outro cliente retorna `order_not_found`
- `issue_refund` recebe o motivo e não recebe valor; um argumento `amount` enviado pelo modelo é recusado
- `late_delivery`: só com atraso acima de 30 min, e o valor é 20% do pedido
- `missing_item`: exige o nome do item, que precisa estar no pedido, e o valor é o preço dele
- `wrong_or_spoiled_food`: exige descrição do problema, com até 100% do pedido
- Pedido que não foi entregue não é reembolsado, e cada pedido tem no máximo um reembolso
- Reembolso acima de `AUTO_REFUND_LIMIT` (R$ 50 por padrão) abre um ticket para um atendente e não é pago; pedir de novo não cria ticket duplicado
- Cada `session_id` pertence ao cliente que o criou; outro cliente recebe 403
- O número de sessões em memória tem limite, e o `/audit` só responde com o `ADMIN_TOKEN` correto

## Estrutura do projeto

```
suporte-delivery-agentes/
├── app/
│   ├── agents.py       # triagem, agentes e orquestração
│   ├── config.py       # variáveis de ambiente e regras de reembolso
│   ├── db.py           # banco SQLite com pedidos de exemplo
│   ├── guardrails.py   # injeção de prompt e mascaramento de CPF/cartão
│   ├── main.py         # API FastAPI (/chat, /audit, /health)
│   ├── policies.md     # políticas usadas no RAG
│   ├── rag.py          # embeddings e busca de políticas
│   └── tools.py        # ferramentas e regras de reembolso
├── evals/
│   ├── cases.json      # casos de teste com o modelo
│   └── run_evals.py    # executa os casos e mostra PASS/FAIL
├── tests/              # testes sem API (pytest)
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── .gitignore
```

## Como rodar

### 1. Clonar e entrar na pasta

```
git clone https://github.com/lucascaranb-tech/suporte-delivery-agentes.git
cd suporte-delivery-agentes
```

### 2. Criar e ativar o ambiente virtual

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Mac ou Linux:

```
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```
pip install -r requirements-dev.txt
```

### 4. Configurar o `.env`

Copie o `.env.example` para `.env` e preencha:

```
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-4o-mini
AUTO_REFUND_LIMIT=50
ADMIN_TOKEN=um-valor-so-seu
```

- O `.env` não vai para o GitHub (está no `.gitignore`)
- Sem `ADMIN_TOKEN`, a rota `/audit` fica bloqueada

### 5. Subir a API

```
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000/docs` para testar as rotas.

## Exemplo de uso

Requisição em `POST /chat`:

```
{
  "session_id": "s1",
  "customer_id": "c1",
  "message": "Meu pedido A101 chegou 45 minutos atrasado, quero reembolso"
}
```

Resposta esperada (resumida):

- `intent`: `problem`
- `trace`: `get_order`, `search_policy`, `issue_refund`
- Reembolso de 20% sobre R$ 38,50, ou seja, **R$ 7,70**, calculado pelo código

Auditoria (só com o token configurado no `.env`):

```
GET /audit
X-Admin-Token: um-valor-so-seu
```

## Testes

```
pytest
```

- 71 testes que não usam a API
- Cobrem as regras de reembolso, o isolamento entre clientes, as ferramentas permitidas por agente, os guardrails, as sessões e a rota `/audit`
- O fluxo do modelo é simulado com um cliente falso roteirizado

## Evals

```
python -m evals.run_evals
python -m evals.run_evals --runs 3
python -m evals.run_evals --case late_order_refund
```

- Usam a API da OpenAI de verdade
- Cada caso confere a intenção, as ferramentas usadas, o valor reembolsado, os tickets abertos e se a resposta vazou dados de outro cliente
- Há casos com duas mensagens (item faltando) e com valor sugerido pelo cliente
- `--runs N` repete cada caso N vezes, porque o modelo varia entre execuções
'''
## Teste dos Evals
<img width="1636" height="846" alt="image" src="https://github.com/user-attachments/assets/34549706-12b3-4cd5-ae49-b3ee401206b2" />



## Tecnologias

- Python 3.10+
- FastAPI e Uvicorn
- OpenAI API (gpt-4o-mini e text-embedding-3-small)
- SQLite
- NumPy (similaridade de cosseno no RAG)
- pytest

## Limitações

- O `customer_id` vem no corpo da requisição; em produção viria do token de login
- As sessões ficam na memória, então reiniciar a API apaga o histórico das conversas
- A detecção de injeção usa regex e é só a primeira camada; a proteção principal é o isolamento por cliente e as regras no código
- A política de reembolso existe em dois lugares: `app/policies.md` (para o RAG) e `app/config.py` (para o cálculo)
- O banco é um SQLite de demonstração, com 4 pedidos de exemplo

## Próximos passos

- Trocar o SQLite por PostgreSQL
- Containerizar com Docker
- Autenticação real dos clientes
- Página de chat no navegador

## Autor

Lucas Caram Bueno · [LinkedIn](https://www.linkedin.com/in/lucas-caram1810) · [GitHub](https://github.com/lucascaranb-tech)

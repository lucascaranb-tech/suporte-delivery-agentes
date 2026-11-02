# Agentes para Suporte em Entregas

Um sistema de suporte ao cliente baseado em múltiplos agentes para serviços de entrega de comida, desenvolvido com Python, FastAPI e a API da OpenAI (gpt-4o-mini).

Quando um cliente entra em contato relatando um atraso no pedido, um item faltante ou solicitando um reembolso, um "agente de triagem" identifica a intenção e encaminha o atendimento para o agente especialista adequado. Esse agente utiliza ferramentas específicas para consultar os detalhes do pedido, verificar as políticas da empresa e realizar o reembolso — ou, se necessário, escalar o caso para um atendente humano.

## Por que este projeto?

Este é o meu terceiro projeto envolvendo agentes de IA, após desenvolver soluções para pedidos em restaurantes e para um banco digital. O foco aqui está nos elementos que tornam os agentes seguros e confiáveis ​​para um ambiente de produção:

- Roteamento entre múltiplos agentes (agente de triagem + agentes especialistas)
- Uso de ferramentas (*tool calling*), com um conjunto restrito de funcionalidades para cada agente
- RAG (*Retrieval-Augmented Generation*) aplicado a documentos de políticas (utilizando *embeddings* e similaridade de cosseno)
- Mecanismos de proteção (*guardrails*): mascaramento de dados sensíveis (PII), detecção de *prompt injection* e limites rígidos para reembolsos definidos no código
- Registro de auditoria (*audit log*) de todas as chamadas de ferramentas
- Avaliações automatizadas (*evals*) para testar o comportamento dos agentes
cliente -> FastAPI (/chat)
             |
             v
        Classificador de intenção
             |
   +---------+-----------+-----------+
   v                     v           v
Agente de pedido    Agente de      Guardrails
(get_order)         política       (unsafe)
                    (RAG)
             |
             v
     issue_refund + audit log (SQLite)
```

## Estrutura do projeto

```
delivery-support-agents/
├── app/
│   ├── agents.py       # orquestração dos agentes
│   ├── config.py       # variáveis de ambiente
│   ├── db.py           # banco SQLite com pedidos de exemplo
│   ├── guardrails.py   # detecção de prompt injection e limites
│   ├── main.py         # API FastAPI (/chat, /audit)
│   ├── policies.md     # políticas usadas no RAG
│   ├── rag.py          # embeddings e busca de políticas
│   └── tools.py        # ferramentas: get_order, search_policy, issue_refund
├── evals/
│   ├── cases.json      # casos de teste
│   └── run_evals.py    # executa os casos e mostra PASS/FAIL
├── requirements.txt
├── .env.example
└── .gitignore
```

## Como rodar

### 1. Clonar e entrar na pasta

```
git clone https://github.com/lucascaranb-tech/delivery-support-agents.git
cd delivery-support-agents
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
pip install -r requirements.txt
```

### 4. Configurar a chave da OpenAI

Copie o `.env.example` para `.env` e preencha:

```
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-4o-mini
AUTO_REFUND_LIMIT=50
```

O arquivo `.env` não vai para o GitHub (está no `.gitignore`).

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
- Reembolso de 20% sobre R$ 38,50, ou seja, **R$ 7,70**

## Testes (evals)

```
python -m evals.run_evals
```

Resultado atual: **Eval result: 5/5 cases passed**

Casos cobertos: `tracking_simple`, `late_order_refund`, `other_customer_order`, `prompt_injection` e `regret_no_refund`.

## Tecnologias

- Python 3.10+
- FastAPI e Uvicorn
- OpenAI API (gpt-4o-mini)
- SQLite
- Embeddings para RAG

## Próximos passos

- Trocar o SQLite por PostgreSQL
- Adicionar testes unitários com pytest
- Containerizar com Docker
- Adicionar autenticação dos clientes

## Autor

Lucas Caram Bueno · [LinkedIn](www.linkedin.com/in/lucas-caram1810) · [GitHub](https://github.com/lucascaranb-tech)

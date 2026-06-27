# Sprint 2 — UFMS Apoia MDA e MAPA (Meta 3)

API inteligente que recebe um processo mapeado em **BPMN** e um **PDF** descritivo desse processo e identifica automaticamente oportunidades de automação administrativa, gerando um documento estruturado com justificativas, benefícios e impactos para cada candidata.

**Squad 1:** Emily Flores · Arthur Schneider · Davi Gaborim · Wellington Cintra

---

## Como funciona

Você envia dois arquivos para a API e ela executa um pipeline de 9 etapas orquestradas pelo LangGraph, chamando um LLM via OpenRouter em cada etapa que precisa de análise de linguagem.

```
BPMN + PDF
    ↓
[1] ingestao_arquivos            → valida extensão, tamanho e existência dos arquivos
[2] analisar_bpmn                → lê o XML do .bpmn, extrai nós, raias, gateways e fluxos
[3] extrair_pdf                  → extrai o texto do PDF página por página
[4] bpmn_para_linguagem_natural  → LLM converte o BPMN em narrativa em português
[5] pdf_para_json                → LLM estrutura o PDF em JSON (unidade, normas, metas...)
[6] gerar_candidatas             → LLM analisa tudo e propõe as automações candidatas
[7] revisar_critica              → LLM revisa as candidatas, corrige duplicatas e vagas
[8] validar_schema               → Pydantic valida; se falhar, pede reparo ao LLM (até 3x)
[9] renderizar_saidas            → salva todos os artefatos em /saidas/
```

### Dois pipelines obrigatórios

O parâmetro `pipeline` controla o que é enviado ao LLM na etapa de geração:

| Valor | O que vai no prompt |
|-------|---------------------|
| `natural` | Narrativa em texto corrido (Entrega 1) |
| `json` | JSON estruturado do BPMN + JSON estruturado do PDF (Entrega 2) |
| `both` | Executa os dois e salva intermediários de ambos (padrão) |

### O que é salvo em disco

```
saidas/
├── intermediarios/
│   ├── bpmn_normalizado.xml        ← BPMN limpo (sem elementos visuais)
│   ├── narrativa_bpmn.txt          ← narrativa gerada pelo LLM (Entrega 1)
│   ├── pdf_texto_extraido.txt      ← texto bruto extraído do PDF
│   ├── bpmn_estruturado.json       ← BPMN como JSON estruturado (Entrega 2)
│   ├── pdf_estruturado.json        ← PDF como JSON documental (Entrega 2)
│   └── prompt_usado.txt            ← exatamente o que foi enviado ao LLM
├── automacoes_YYYYMMDD_HHMMSS.json ← JSON de auditoria com todas as automações
└── automacoes_YYYYMMDD_HHMMSS.md   ← documento final em Markdown
```

---

## Estrutura do projeto

```
Sprint2/
├── app/
│   ├── agente/
│   │   ├── llm.py          ← função call_llm (reaproveitada da Sprint 1)
│   │   ├── config.py       ← lê OPENROUTER_API_KEY e LLM_MODEL do .env
│   │   ├── logger.py       ← logger com saída em terminal e JSON
│   │   ├── grafo.py        ← monta e compila o grafo LangGraph
│   │   └── nos/            ← um arquivo .py por nó do grafo
│   ├── api/
│   │   ├── main.py         ← cria a aplicação FastAPI
│   │   └── rotas.py        ← endpoints da API
│   └── schemas/
│       └── modelos.py      ← todos os schemas Pydantic v2
├── prompts/                ← prompts versionados em Markdown
│   ├── bpmn_para_linguagem_natural.md
│   ├── pdf_para_json.md
│   ├── gerar_automacoes_candidatas.md
│   └── revisar_critica.md
├── testes/                 ← testes com pytest
├── entradas/               ← coloque aqui os arquivos .bpmn e .pdf para teste
├── saidas/                 ← gerado automaticamente na execução
├── cli.py                  ← execução por linha de comando
├── requirements.txt
├── .env.example            ← modelo do arquivo de configuração
└── .gitignore
```

---

## Instalação

### Pré-requisitos

- Python 3.11 ou superior
- Conta no [OpenRouter](https://openrouter.ai) com créditos disponíveis

### Passo a passo

**1. Clone o repositório e entre na pasta**

```bash
git clone <url-do-repositorio>
cd Sprint2
```

**2. Crie e ative um ambiente virtual**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python -m venv venv
source venv/bin/activate
```

**3. Instale as dependências**

```bash
pip install -r requirements.txt
```

**4. Configure as variáveis de ambiente**

Copie o arquivo de exemplo e preencha com sua chave:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux / macOS
```

Abra o `.env` e edite:

```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=google/gemma-4-31b-it
```

> **Importante:** o arquivo `.env` já está no `.gitignore` e nunca deve ser commitado. Cada membro do time cria o seu próprio `.env` localmente. A chave do OpenRouter é pessoal — não compartilhe.

---

## Como executar

### Via API (FastAPI)

```bash
uvicorn app.api.main:app --reload
```

A API sobe em `http://localhost:8000`. Acesse `http://localhost:8000/docs` para ver a documentação interativa.

**Enviar arquivos para análise:**

```bash
curl -X POST http://localhost:8000/analisar-processo \
  -F "bpmn_file=@entradas/processo.bpmn" \
  -F "pdf_file=@entradas/descritivo.pdf" \
  -F "pipeline=both"
```

**Consultar o resultado de um run:**

```bash
curl http://localhost:8000/runs/{run_id}
```

**Baixar um artefato gerado:**

```bash
curl http://localhost:8000/runs/{run_id}/download/automacoes_YYYYMMDD_HHMMSS.md \
  -o resultado.md
```

### Via CLI (linha de comando)

Útil para testes rápidos sem precisar subir o servidor:

```bash
python cli.py --bpmn entradas/processo.bpmn --pdf entradas/descritivo.pdf --pipeline both
```

Opções disponíveis:

| Opção | Descrição | Padrão |
|-------|-----------|--------|
| `--bpmn` | Caminho para o arquivo .bpmn | obrigatório |
| `--pdf` | Caminho para o arquivo .pdf | obrigatório |
| `--pipeline` | `natural`, `json` ou `both` | `both` |

---

## Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/health` | Status da API e versão |
| `POST` | `/analisar-processo` | Envia BPMN + PDF e executa a análise |
| `GET` | `/runs/{run_id}` | Consulta status e artefatos de um run |
| `GET` | `/runs/{run_id}/download/{artefato}` | Baixa um artefato gerado |

---

## Como alterar os prompts

Os prompts ficam em `/prompts/` como arquivos Markdown. Para ajustar o comportamento do agente, edite o arquivo correspondente:

| Arquivo | Quando é usado |
|---------|----------------|
| `bpmn_para_linguagem_natural.md` | Converte o BPMN em narrativa administrativa |
| `pdf_para_json.md` | Estrutura o texto do PDF em JSON |
| `gerar_automacoes_candidatas.md` | Gera as automações candidatas |
| `revisar_critica.md` | Revisa e corrige as candidatas geradas |

> Após alterar um prompt, basta rodar a CLI ou a API novamente — não precisa reiniciar nada.

---

## Como trocar o modelo LLM

Edite a variável `LLM_MODEL` no seu `.env`. Qualquer modelo disponível no OpenRouter funciona:

```
LLM_MODEL=google/gemma-4-31b-it
LLM_MODEL=anthropic/claude-sonnet-4-5
LLM_MODEL=openai/gpt-4o-mini
```

Consulte os modelos disponíveis em [openrouter.ai/models](https://openrouter.ai/models).

---

## Testes

```bash
pytest testes/
```

Os testes cobrem:
- Validação dos schemas Pydantic (tipos inválidos, campos obrigatórios)
- Upload sem arquivo obrigatório
- Upload com extensão errada

---

## Observações para o time

- **Nunca commite o `.env`** — ele está no `.gitignore` por segurança.
- Os arquivos em `saidas/` também estão no `.gitignore` — são gerados localmente em cada execução.
- Para adicionar um novo nó ao grafo, crie o arquivo em `app/agente/nos/`, importe em `grafo.py` e adicione com `grafo.add_node(...)` e `grafo.add_edge(...)`.
- O estado que passa entre os nós é o `EstadoGrafo` em `app/schemas/modelos.py` — se precisar de um novo campo, adicione lá.
- O `llm.py` já tem retry automático (3 tentativas) e captura de tokens. Não chame o OpenRouter diretamente — sempre use `call_llm()`.

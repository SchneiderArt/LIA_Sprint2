# Sprint 2 — Entrega 2: Identificação de Automações a partir de BPMN e PDF

**Projeto:** UFMS Apoia MDA e MAPA — Meta 3  
**Coordenação:** Prof. Dr. Bruno Magalhães Nogueira — Faculdade de Computação / UFMS  
**Time A — Squad 1**

| Integrante | GitHub | Responsabilidade |
|---|---|---|
| Arthur Schneider | [@SchneiderArt](https://github.com/SchneiderArt) | Orquestração LangGraph + Integração OpenRouter |
| Davi Gaborim | [@davigaborim](https://github.com/davigaborim) | Entrega 1 — Pipeline de Linguagem Natural |
| Emily Flores | [@Emily-Flo223](https://github.com/Emily-Flo223) | Entrega 2 — Pipeline JSON + Schemas Pydantic |
| Wellington Cintra | [@wellingtoncintra](https://github.com/wellingtoncintra) | API FastAPI + CLI + Testes + Apresentação |

---

## O que este projeto faz

Recebe um arquivo **BPMN** (processo institucional) e um **PDF** (descritivo do processo) e identifica automaticamente oportunidades de automação administrativa, gerando:

- Documento final em **Markdown e PDF** com as automações candidatas
- **JSON de auditoria** com todas as evidências usadas
- **Intermediários auditáveis** (JSONs estruturados do BPMN e do PDF)

---

## Estrutura do projeto

```
projeto/
├── app/
│   ├── graph.py                  # Grafo LangGraph — orquestra todo o pipeline
│   ├── schemas.py                # Schemas Pydantic v2 (ProcessoJSON, DocumentoPDFJSON, AutomationCandidateJSON...)
│   ├── cli.py                    # Interface de linha de comando (CLI)
│   ├── openrouter.py             # Cliente OpenRouter centralizado
│   ├── prompts.py                # Loader de prompts versionados
│   ├── render_pdf.py             # Geração do documento final em PDF (ReportLab)
│   └── nodes/
│       ├── ingest_files.py       # Valida arquivos de entrada (extensão, tamanho, path traversal)
│       ├── parse_bpmn_to_json.py # BPMN → ProcessoJSON (defusedxml + networkx)
│       ├── extract_pdf_to_json.py# PDF → DocumentoPDFJSON (PyMuPDF)
│       ├── build_prompt_context.py# Combina os dois JSONs em contexto único
│       ├── generate_candidates.py # LLM gera automações candidatas
│       ├── critic_review_node.py  # LLM revisa lacunas e generalizações
│       ├── validate_schema.py     # Pydantic v2 valida saída + nó repair_output
│       └── render_outputs.py      # Gera Markdown, PDF e JSON de auditoria
├── prompts/
│   ├── system_automation_analyst.md
│   ├── bpmn_to_json.md
│   ├── pdf_to_json.md
│   ├── bpmn_to_natural_language.md
│   ├── generate_automation_candidates.md
│   └── critic_review.md
├── entradas/
│   ├── Análise Processual e Tributária/
│   ├── Apuração de Acumulação de Cargos/
│   ├── Gestão da Folha de Pagamento/
│   └── ... (11 processos no total)
├── testes/
├── run.py                        # Ponto de entrada CLI
├── requirements.txt
├── .env                          # Variáveis de ambiente (não commitado)
└── .gitignore
```

---

## Pré-requisitos

- Python 3.11 ou superior
- Conta no [OpenRouter](https://openrouter.ai) com chave de API

---

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/SchneiderArt/LIA_Sprint2.git
cd LIA_Sprint2

# 2. Criar e ativar ambiente virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
```

---

## Configuração

Abra o arquivo `.env` e preencha sua chave do OpenRouter:

```env
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
```

As demais variáveis já têm valores padrão:

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it` | Modelo LLM utilizado |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base da API |
| `OPENROUTER_TIMEOUT_SECONDS` | `120` | Timeout das chamadas ao LLM |
| `MAX_REPAIR_ATTEMPTS` | `3` | Tentativas de reparo de schema |
| `MAX_FILE_SIZE_BYTES` | `10485760` | Tamanho máximo por arquivo (10 MB) |

> **Modelos disponíveis no OpenRouter:** `openai/gpt-4o-mini`, `openai/gpt-4o`, `anthropic/claude-sonnet-4-6`, `google/gemma-4-31b-it` (gratuito com limites). Lista completa em https://openrouter.ai/models

---

## Como executar

A CLI é o ponto de entrada principal. Pode ser chamada via `run.py` (raiz do projeto) ou diretamente como módulo Python (`python -m app.cli`). Os dois são equivalentes.

### Ver todos os parâmetros disponíveis

```powershell
python run.py --help
```

### Modo completo — pipeline JSON (Entrega 2)

```powershell
python run.py --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" --pdf "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"
```

Equivalente explícito com `--pipeline`:
```powershell
python run.py --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" --pdf "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf" --pipeline json
```

### Modo dry-run — sem LLM (testa parsing sem gastar créditos)

```powershell
python run.py --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" --pdf "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf" --dry-run
```

### Definir run-id manualmente (útil para testes automatizados)

```powershell
python run.py --bpmn "entradas/Vacância/Verificação de Pendências.bpmn" --pdf "entradas/Vacância/vacancia.pdf" --run-id analise-vacancia-001
```

### Logs detalhados

```powershell
python run.py --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" --pdf "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf" --verbose
```

### Parâmetros disponíveis

| Parâmetro | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `--bpmn` | ✅ | — | Caminho para o arquivo `.bpmn` |
| `--pdf` | ✅ | — | Caminho para o arquivo `.pdf` |
| `--pipeline` | ❌ | `json` | `json` (Entrega 2) · `natural` (Entrega 1, em dev) · `both` (em dev) |
| `--run-id` | ❌ | gerado automaticamente | Identificador da execução |
| `--dry-run` | ❌ | `false` | Roda sem LLM — só parsing e extração |
| `--saida` | ❌ | `saidas/` | Pasta de saída dos artefatos |
| `--verbose` | ❌ | `false` | Logs detalhados de cada nó |

### Outros processos disponíveis

```powershell
# Apuração de Acumulação de Cargos
python run.py --bpmn "entradas/Apuração de Acumulação de Cargos/Apuração de acumulação de cargos.bpmn" --pdf "entradas/Apuração de Acumulação de Cargos/apuracao-de-acumulacao-de-cargos.pdf"

# Regularidade Fiscal
python run.py --bpmn "entradas/Regularidade Fiscal/Certidões Fiscais.bpmn" --pdf "entradas/Regularidade Fiscal/regularidade-fiscal.pdf"

# Vacância — Verificação de Pendências
python run.py --bpmn "entradas/Vacância/Verificação de Pendências.bpmn" --pdf "entradas/Vacância/vacancia.pdf"

# Gestão da Folha de Pagamento
python run.py --bpmn "entradas/Gestão da Folha de Pagamento/Gestão da Folha de Pagamento.bpmn" --pdf "entradas/Gestão da Folha de Pagamento/gestao-da-folha-de-pagamento.pdf"
```

---

## Saídas geradas

Após a execução, a pasta `saidas/` contém:

```
saidas/
├── documento_final.md            # Documento com as 7 seções obrigatórias (Markdown)
├── documento_final.pdf           # Mesmo documento em PDF (ReportLab)
├── auditoria.json                # Automações + evidências usadas
└── intermediarios/
    ├── bpmn_estruturado.json     # ProcessoJSON extraído do BPMN
    ├── pdf_estruturado.json      # DocumentoPDFJSON extraído do PDF
    └── prompt_usado.txt          # Prompt enviado ao LLM (para auditoria)
```

### Estrutura do documento final

O documento segue a estrutura obrigatória da sprint:

1. **Identificação do processo** — nome, arquivos, data, unidade, resumo executivo
2. **Leitura do BPMN** — raias, atividades, gateways, documentos, loops
3. **Leitura do PDF** — descrição, procedimentos, normas, indicadores, metas
4. **Lista de automações candidatas** — tabela-resumo com prioridade e impacto
5. **Detalhamento por automação** — todos os 13 campos obrigatórios (gatilho, entradas, saídas, como automatizar, justificativa, benefícios, impactos, riscos, métricas)
6. **Riscos e limitações gerais**
7. **Recomendações de priorização**

---

## Pipeline — como funciona

```
Entrada (BPMN + PDF)
        ↓
  ingest_files          — valida extensão, tamanho, path traversal
        ↓
  parse_bpmn_to_json    — BPMN → ProcessoJSON (defusedxml + networkx)
        ↓
  extract_pdf_to_json   — PDF → DocumentoPDFJSON (PyMuPDF)
        ↓
  build_prompt_context  — combina os dois JSONs
        ↓
  generate_candidates   — LLM gera automações (OpenRouter)
        ↓
  critic_review         — LLM revisa lacunas e generalizações
        ↓
  validate_schema       — Pydantic v2 valida saída
        ↓ (se falhar)
  repair_output         — LLM corrige erros de schema (até 3 tentativas)
        ↓
  render_outputs        — gera Markdown + PDF + JSON de auditoria
        ↓
      Saída
```

---

## Tipos de automação identificados

| Tipo | Quando é usado |
|---|---|
| **RPA** | Tarefas repetitivas, cliques, formulários, consultas em sistemas sem API |
| **Agente de IA** | Interpretação textual, classificação, geração de parecer, análise de conformidade |
| **Híbrida** | Combinação de coleta mecânica (RPA) com julgamento inteligente (IA) |
| **API/Integração** | Sistemas com API oficial disponível |

---

## Status de implementação

| Etapa | Descrição | Status |
|---|---|---|
| 1 | Estrutura do projeto | ✅ Concluído |
| 2 | Schemas Pydantic v2 | ✅ Concluído |
| 3 | Parser BPMN → JSON | ✅ Concluído |
| 4 | Extrator PDF → JSON | ✅ Concluído |
| 5 | Prompts versionados | ✅ Concluído |
| 6 | Grafo LangGraph | ✅ Concluído |
| 7 | Integração OpenRouter | ✅ Concluído |
| 8 | Renderização Markdown + PDF | ✅ Concluído |
| 9 | API FastAPI | 🔄 Em desenvolvimento |
| 10 | CLI completa | ✅ Concluído |
| 11 | Testes (pytest) | 🔄 Em desenvolvimento |
| 12 | Docker + documentação final | 🔄 Em desenvolvimento |

---

## Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Orquestração de agente | LangGraph 1.2.6 |
| Fornecedor LLM | OpenRouter (via SDK openai) |
| Schemas e validação | Pydantic v2 |
| BPMN / XML seguro | defusedxml + lxml |
| Grafo de processo | networkx |
| Extração de PDF | PyMuPDF (fitz) |
| Documento final | ReportLab (PDF) + Markdown |
| Ambiente | python-dotenv + .env |

---

## Segurança

- Chave do OpenRouter nunca hardcoded — sempre via `.env`
- `.env` protegido pelo `.gitignore`
- Parsing XML com `defusedxml` (sem entidades externas — previne XXE)
- Validação de path traversal em todos os caminhos de entrada
- Limite de tamanho de arquivo configurável via `.env`
- Conteúdo enviado pelo usuário nunca executado

---

## Referências

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)
- [LangGraph Quickstart](https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/)
- [LangGraph Low Level Concepts](https://langchain-ai.github.io/langgraph/concepts/low_level/)
- [Pydantic v2 Models](https://docs.pydantic.dev/latest/concepts/models/)
- [FastAPI Request Files](https://fastapi.tiangolo.com/tutorial/request-files/)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)

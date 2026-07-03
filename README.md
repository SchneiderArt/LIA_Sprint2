# Identificação de Automações a partir de BPMN e PDF

> Agente de IA que lê um processo administrativo institucional — modelado em **BPMN 2.0** e descrito em **PDF** — e identifica automaticamente oportunidades concretas de automação (RPA, Agente de IA, Híbrida ou API/Integração), gerando um relatório auditável em Markdown, PDF e JSON.

**Projeto acadêmico** — UFMS Apoia MDA e MAPA / Meta 3 · Faculdade de Computação (FACOM/UFMS) · Sprint 2 · Time A — Squad 1
Coordenação: Prof. Dr. Bruno Magalhães Nogueira

---

## Sumário

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como executar](#como-executar)
- [Fluxo de funcionamento](#fluxo-de-funcionamento)
- [Estrutura dos dados e saídas](#estrutura-dos-dados-e-saídas)
- [Modelos de IA](#modelos-de-ia)
- [API HTTP](#api-http)
- [Interface Streamlit](#interface-streamlit)
- [Testes](#testes)
- [Logs](#logs)
- [Segurança](#segurança)
- [Desenvolvimento e contribuição](#desenvolvimento-e-contribuição)
- [Limitações conhecidas](#limitações-conhecidas)
- [Melhorias futuras](#melhorias-futuras)
- [Equipe](#equipe)
- [Licença](#licença)

---

## Visão geral

Universidades federais executam dezenas de processos administrativos repetitivos — apuração de acumulação de cargos, gestão da folha de pagamento, regularidade fiscal, provimento de vagas, prestação de contas de convênios, entre outros. Esses processos costumam estar documentados de duas formas complementares:

- Um **arquivo `.bpmn`** (BPMN 2.0, tipicamente exportado do Bizagi) com o fluxo formal: raias, atividades, gateways, eventos e objetos de dados.
- Um **PDF descritivo** com a finalidade do processo, procedimentos, amparo legal, indicadores, metas e responsáveis.

Este projeto recebe esses dois insumos, os transforma em representações estruturadas, e usa um agente de LLM orquestrado por **LangGraph** para propor automações candidatas ancoradas em atividades reais do processo. Cada automação é acompanhada de gatilho, entradas, saídas, tipo, justificativa, benefícios, impactos, riscos, métricas de sucesso e prioridade sugerida.

O resultado não é uma lista genérica de ideias: cada candidata é rastreável até o BPMN e o PDF de origem, e todo o material intermediário (JSONs estruturados, prompt enviado ao modelo) é persistido em disco para auditoria.

O sistema oferece **três formas de uso** sobre o mesmo motor de pipeline:

1. **CLI** (`run.py`) — execução reprodutível por linha de comando, ideal para avaliação e testes automatizados.
2. **API HTTP** (FastAPI) — upload de BPMN + PDF via `POST`, consulta de status e download dos artefatos gerados.
3. **Painel Streamlit** — executa e compara lado a lado as duas abordagens de análise (linguagem natural × JSON estruturado) sobre os processos de exemplo.

---

## Funcionalidades

- **Parsing seguro de BPMN 2.0** → `ProcessoJSON`: extração de raias, nós (atividades, eventos, gateways, subprocessos, chamadas, objetos de dados), arestas de sequência com condições, detecção de loops e ordenação topológica das atividades via `networkx`.
- **Extração estruturada de PDF** → `DocumentoPDFJSON`: título, unidade responsável, descrição, procedimentos, amparo legal, links, indicadores (com fórmula, fonte, frequência e metas), metas gerais e responsáveis. O extrator lida com o template Bizagi em que os rótulos de seção aparecem **depois** do conteúdo que nomeiam (mapeamento reverso).
- **Geração de automações candidatas** por LLM, com validação estrita de schema.
- **Revisão crítica automática** (nó *critic*) que verifica lacunas, generalizações, duplicidades e ausência de impacto administrativo.
- **Validação e auto-reparo de schema**: a saída do LLM é validada por Pydantic v2; se inválida, um nó de reparo reenvia os erros ao modelo para correção, com número máximo de tentativas configurável.
- **Renderização multiformato**: documento final em **Markdown** e **PDF** (ReportLab) seguindo as 7 seções obrigatórias da sprint, mais um **JSON de auditoria**.
- **Três pipelines**: `json` (estruturado), `natural` (linguagem natural) e `both` (executa os dois e gera um documento comparativo).
- **Modo `--dry-run`**: roda todo o parsing e a extração sem chamar o LLM (não consome créditos), útil para validar arquivos de entrada.
- **Isolamento por execução**: cada run grava seus artefatos em `saidas/<run_id>/`, sem colisão entre execuções.
- **API HTTP** com upload, consulta de status e download seguro de artefatos.
- **Painel comparativo** em Streamlit com métricas determinísticas e leitura qualitativa por LLM.

---

## Arquitetura

O sistema é um **grafo de estado** (LangGraph). Um objeto `EstadoGrafo` (Pydantic) percorre uma sequência de nós; cada nó lê e escreve campos desse estado. Arestas condicionais interrompem o fluxo (`END`) assim que qualquer nó registra um erro, e implementam o laço de reparo de schema.

```mermaid
flowchart TD
    subgraph entrada [Entrada]
        A["BPMN (.bpmn) + PDF (.pdf)"]
    end

    A --> B[ingest_files<br/>valida extensão, tamanho, path traversal]
    B --> C[parse_bpmn_to_json<br/>BPMN → ProcessoJSON]
    C --> D[extract_pdf_to_json<br/>PDF → DocumentoPDFJSON]
    D --> E[build_prompt_context<br/>combina os dois JSONs]
    E --> F[generate_candidates<br/>LLM gera automações]
    F --> G[critic_review<br/>LLM revisa lacunas]
    G --> H{validate_schema<br/>Pydantic v2}
    H -->|válido| J[render_outputs<br/>Markdown + PDF + auditoria]
    H -->|inválido| I[repair_output<br/>LLM corrige schema]
    I --> H
    J --> K["Saída: saidas/&lt;run_id&gt;/"]

    B -.erro.-> X([END])
    C -.erro.-> X
    D -.erro.-> X
    E -.erro.-> X
    F -.erro.-> X
    G -.erro.-> X
    H -.máx. tentativas.-> X
```

**Pipeline `natural` (linguagem natural).** Substitui os nós de estruturação por versões baseadas em texto: `parse_bpmn_xml` (normaliza o XML e resolve as raias por coordenada do diagrama) → `extract_pdf_text` (texto bruto por página) → `bpmn_to_natural_language` (LLM converte o fluxo em narrativa administrativa) → `build_prompt_context_natural`. A partir de `generate_candidates` o fluxo é idêntico ao pipeline JSON, terminando em `render_outputs_natural`.

**Pipeline `both`.** Executa os dois grafos com o mesmo `run_id` e, ao final, chama `render_outputs_both` para produzir um documento comparativo. Os artefatos ficam separados por subpasta de abordagem (`json/`, `natural/`, `comparativo/`).

Um ponto de projeto importante: **a API, a CLI e o Streamlit compartilham exatamente o mesmo motor** (`app.graph.executar_pipeline`). A API não reprocessa nem relocaliza nada — os nós já gravam os arquivos com escopo de execução, e a API apenas lê o disco.

---

## Estrutura do projeto

```
.
├── run.py                       # Ponto de entrada da CLI (wrapper de app/cli.py)
├── streamlit_app.py             # Painel comparativo Natural × JSON
├── requirements.txt
├── .gitignore
│
├── app/
│   ├── cli.py                   # Interface de linha de comando (argparse)
│   ├── graph.py                 # Grafos LangGraph (json, natural, both) + executar_pipeline
│   ├── schemas.py               # Schemas Pydantic v2 + EstadoGrafo
│   ├── openrouter.py            # Cliente LLM centralizado (OpenRouter via SDK openai)
│   ├── prompts.py               # Loader de prompts versionados + montagem de contexto
│   ├── render_pdf.py            # Markdown → PDF (ReportLab)
│   │
│   ├── nodes/                   # Nós do grafo
│   │   ├── ingest_files.py                 # valida entradas
│   │   ├── parse_bpmn_to_json.py           # BPMN → ProcessoJSON (Entrega 2)
│   │   ├── extract_pdf_to_json.py          # PDF → DocumentoPDFJSON (Entrega 2)
│   │   ├── build_prompt_context.py         # contexto JSON
│   │   ├── parse_bpmn_xml.py               # BPMN normalizado (Entrega 1)
│   │   ├── extract_pdf_text.py             # texto bruto do PDF (Entrega 1)
│   │   ├── bpmn_to_natural_language.py     # BPMN → narrativa (Entrega 1)
│   │   ├── build_prompt_context_natural.py # contexto natural
│   │   ├── generate_candidates.py          # LLM gera automações (compartilhado)
│   │   ├── critic_review_node.py           # LLM revisa (compartilhado)
│   │   ├── validate_schema.py              # validate_schema + repair_output
│   │   ├── render_outputs.py               # artefatos do pipeline JSON
│   │   ├── render_outputs_natural.py       # artefatos do pipeline natural
│   │   └── render_outputs_both.py          # documento comparativo
│   │
│   ├── api/                     # Camada HTTP
│   │   ├── main.py              # instância FastAPI
│   │   ├── rotas.py             # endpoints (/health, /analisar-processo, /runs/...)
│   │   ├── seguranca.py         # validação de upload + XML seguro
│   │   ├── armazenamento.py     # persistência das entradas
│   │   └── utils/config.py      # (cópia legada — ver "Limitações conhecidas")
│   │
│   └── utils/
│       └── config.py            # Fonte única de caminhos run-scoped (usado por todo o app)
│
├── prompts/                     # Prompts versionados em Markdown
│   ├── system_automation_analyst.md
│   ├── bpmn_to_json.md
│   ├── pdf_to_json.md
│   ├── bpmn_to_natural_language.md
│   ├── generate_automation_candidates.md
│   └── critic_review.md
│
├── entradas/                    # 11 processos de exemplo (BPMN + PDF)
│   ├── Análise Processual e Tributária/
│   ├── Apuração de Acumulação de Cargos/
│   ├── Gestão da Folha de Pagamento/
│   └── ...
│
├── testes/                      # Suíte pytest
│   ├── conftest.py
│   └── test_pipeline_natural.py
│
└── saidas/                      # Artefatos gerados (ignorado pelo git)
```

### Responsabilidade de cada diretório

| Diretório | Responsabilidade |
|---|---|
| `app/` | Todo o código da aplicação. |
| `app/nodes/` | Nós do grafo — cada arquivo é uma etapa isolada e testável do pipeline. |
| `app/api/` | Camada HTTP (FastAPI): recepção de arquivos, segurança de upload, download de artefatos. |
| `app/utils/` | Configuração centralizada de caminhos (`config.py`) — fonte única de verdade sobre onde cada arquivo é lido e gravado. |
| `prompts/` | Prompts do LLM versionados como arquivos `.md`, carregados em tempo de execução por `app/prompts.py`. |
| `entradas/` | Processos institucionais de exemplo, cada um com um ou mais `.bpmn` e um `.pdf`. |
| `testes/` | Testes automatizados (pytest). |
| `saidas/` | Saída de cada execução, isolada por `run_id`. Não versionado. |

---

## Tecnologias utilizadas

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ (compatível com 3.12) |
| Orquestração do agente | LangGraph |
| Provedor de LLM | OpenRouter (compatível com a API da OpenAI, via SDK `openai`) |
| Schemas e validação | Pydantic v2 |
| Parsing de XML/BPMN seguro | `defusedxml` + `lxml` |
| Grafo de processo (loops, ordenação) | `networkx` |
| Extração de PDF | PyMuPDF (`fitz`) |
| Geração de PDF final | ReportLab |
| API HTTP | FastAPI + Uvicorn + `python-multipart` |
| Painel comparativo | Streamlit + Plotly + Pandas |
| Ambiente / segredos | `python-dotenv` (`.env`) |
| Testes / lint | `pytest` · `ruff` |

> As dependências em `requirements.txt` **não têm versões fixadas**, por decisão do projeto, para garantir a disponibilidade de *wheels* em Python 3.12+.

---

## Instalação

Pré-requisitos: **Python 3.11 ou superior** e uma conta no [OpenRouter](https://openrouter.ai) com chave de API.

```bash
# 1. Clonar o repositório
git clone <URL-do-repositório>
cd <pasta-do-projeto>

# 2. Criar e ativar um ambiente virtual
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

# 3. Instalar as dependências
pip install -r requirements.txt
```

Não há etapa de banco de dados nem download de modelos: o LLM é acessado remotamente via OpenRouter, e não há persistência em banco (o estado das execuções da API é mantido em memória e no sistema de arquivos).

---

## Configuração

Toda a configuração é feita por variáveis de ambiente, tipicamente em um arquivo `.env` na raiz do projeto (não versionado — protegido pelo `.gitignore`). O projeto **não inclui um `.env.example`**; crie o arquivo manualmente:

```env
OPENROUTER_API_KEY=sk-or-v1-sua-chave-real-aqui
```

A única variável obrigatória é `OPENROUTER_API_KEY`. As demais têm valores padrão embutidos no código:

| Variável | Padrão (no código) | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY` | *(vazio — obrigatória)* | Chave de API do OpenRouter. Obtenha em https://openrouter.ai/keys |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Modelo LLM utilizado. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base da API (compatível com OpenAI). |
| `OPENROUTER_TIMEOUT_SECONDS` | `120` | Timeout (em segundos) das chamadas ao LLM. |
| `OPENROUTER_APP_URL` | `https://github.com/ufms-sprint2` | Header `HTTP-Referer` de identificação no OpenRouter. |
| `OPENROUTER_APP_NAME` | `UFMS Apoia MDA Sprint 2` | Header `X-Title` de identificação no OpenRouter. |
| `MAX_REPAIR_ATTEMPTS` | `3` | Tentativas máximas de reparo de schema antes de abortar. |
| `MAX_FILE_SIZE_BYTES` | `10485760` (10 MB) | Tamanho máximo por arquivo de entrada. |

> **Sobre o modelo padrão:** o valor real definido no código (`app/openrouter.py`) é `openai/gpt-4o-mini`. Qualquer identificador de modelo válido do OpenRouter pode ser usado, por exemplo `openai/gpt-4o`, `anthropic/claude-sonnet-4-6` ou outros. A lista completa está em https://openrouter.ai/models. Como o pipeline exige saída estruturada e faz auto-reparo de schema, modelos com boa aderência a instruções e JSON tendem a produzir menos tentativas de reparo.

---

## Como executar

A CLI é o ponto de entrada principal. Pode ser chamada via `run.py` (na raiz) ou diretamente como módulo (`python -m app.cli`) — os dois são equivalentes. **Execute sempre a partir da raiz do projeto**, pois os prompts e os caminhos de saída são resolvidos de forma relativa.

### Ver todos os parâmetros

```bash
python run.py --help
```

### Execução padrão (pipeline JSON — Entrega 2)

```bash
python run.py \
  --bpmn "entradas/Análise Processual e Tributária/Análise.bpmn" \
  --pdf  "entradas/Análise Processual e Tributária/analise-processual-e-tributaria.pdf"
```

### Escolher o pipeline explicitamente

```bash
# Linguagem natural (Entrega 1)
python run.py --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> --pipeline natural

# Executa as duas abordagens e gera o comparativo
python run.py --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> --pipeline both
```

### Modo dry-run (sem LLM, não consome créditos)

```bash
python run.py --bpmn <arquivo.bpmn> --pdf <arquivo.pdf> --dry-run
```

O dry-run executa `ingest_files → parse_bpmn_to_json → extract_pdf_to_json → build_prompt_context` e imprime um resumo (raias, atividades, gateways, loops, procedimentos, indicadores…), salvando apenas os intermediários. É a forma recomendada de validar um novo par BPMN/PDF antes de gastar tokens.

### Outras opções

```bash
# Definir o run_id manualmente (útil para testes automatizados)
python run.py --bpmn <...> --pdf <...> --run-id analise-vacancia-001

# Pasta de saída personalizada (padrão: saidas/)
python run.py --bpmn <...> --pdf <...> --saida minhas_saidas

# Logs detalhados de cada nó
python run.py --bpmn <...> --pdf <...> --verbose
```

### Parâmetros da CLI

| Parâmetro | Obrigatório | Padrão | Descrição |
|---|---|---|---|
| `--bpmn` | ✅ | — | Caminho para o arquivo `.bpmn`. |
| `--pdf` | ✅ | — | Caminho para o arquivo `.pdf`. |
| `--pipeline` | ❌ | `json` | `json`, `natural` ou `both`. |
| `--run-id` | ❌ | gerado automaticamente | Identificador da execução. |
| `--dry-run` | ❌ | `false` | Roda parsing e extração sem chamar o LLM. |
| `--saida` | ❌ | `saidas` | Pasta raiz de saída dos artefatos. |
| `--verbose` | ❌ | `false` | Eleva o nível de log para DEBUG. |

A CLI retorna **código de saída 0** em sucesso e **1** em erro, o que a torna adequada para scripts de CI/CD.

> **Nota sobre `--dry-run`:** neste modo o parâmetro `--pipeline` é ignorado; o dry-run sempre exercita a rota de estruturação (JSON).

---

## Fluxo de funcionamento

Para o pipeline padrão (`json`), do início ao fim:

1. **`ingest_files`** — confere que `--bpmn` e `--pdf` existem, têm a extensão certa, não estão vazios, não excedem o limite de tamanho e não contêm padrões de *path traversal* (caminhos absolutos, `..`, arquivos ocultos).
2. **`parse_bpmn_to_json`** — lê o BPMN com `defusedxml`, mapeia tags BPMN 2.0 para tipos de nó, monta o grafo com `networkx`, detecta loops, ordena as atividades topologicamente e produz um `ProcessoJSON`, salvo em `intermediarios/json/bpmn_estruturado.json`.
3. **`extract_pdf_to_json`** — extrai o texto com PyMuPDF, aplica o mapeamento reverso de seções do template Bizagi, monta o `DocumentoPDFJSON` e o salva em `intermediarios/json/pdf_estruturado.json`.
4. **`build_prompt_context`** — combina os dois JSONs em um único contexto de usuário (blocos `[PROCESSO_JSON]` / `[DOCUMENTO_PDF_JSON]`), salvo em `intermediarios/json/prompt_usado.txt`.
5. **`generate_candidates`** — envia o *system prompt* (`system_automation_analyst.md`) + a instrução (`generate_automation_candidates.md`) + o contexto ao LLM, com temperatura baixa (0.2) para consistência.
6. **`critic_review`** — reenvia as candidatas ao LLM com o prompt de crítica, buscando lacunas, generalizações e duplicidades.
7. **`validate_schema`** — limpa e valida a saída com Pydantic v2. Se válida, popula `estado.candidatos`; se não, registra os erros.
8. **`repair_output`** (condicional) — se a validação falhar, envia a lista de erros ao LLM pedindo correção **apenas do schema**, sem alterar o conteúdo. Volta a `validate_schema`, respeitando `MAX_REPAIR_ATTEMPTS`.
9. **`render_outputs`** — gera `documento_final.md`, `documento_final.pdf` e `auditoria.json` na pasta de artefatos da execução.

Qualquer erro registrado por um nó encerra o grafo imediatamente (`END`), retornando o estado com a lista de erros.

---

## Estrutura dos dados e saídas

Cada execução grava seus arquivos sob `saidas/<run_id>/`, isolando entradas, intermediários e artefatos, e separando por abordagem:

```
saidas/<run_id>/
├── entradas/                     # cópia controlada dos arquivos recebidos
│   ├── processo.bpmn
│   └── descritivo.pdf
├── intermediarios/
│   ├── json/                     # bpmn_estruturado.json, pdf_estruturado.json, prompt_usado.txt
│   └── natural/                  # bpmn_normalizado.xml, pdf_texto_extraido.txt, narrativa_bpmn.txt, ...
└── artefatos/
    ├── json/                     # documento_final.md, documento_final.pdf, auditoria.json
    ├── natural/                  # (idem, para o pipeline natural)
    └── comparativo/              # (idem, apenas no modo both)
```

Numa execução simples (`json` **ou** `natural`) existe apenas a subpasta da abordagem correspondente. No modo `both` existem `json/`, `natural/` e `comparativo/`.

### Schemas de dados (Pydantic v2)

Definidos em `app/schemas.py`:

| Schema | Papel |
|---|---|
| `NodeJSON` | Nó do BPMN: `id`, `tipo`, `nome`, `lane`, documentos relacionados, entradas, saídas, observações. |
| `EdgeJSON` | Aresta de sequência: `id`, `source`, `target`, `label`, `condicao`. |
| `ProcessoJSON` | Processo completo: `process_id`, `nome`, `origem_arquivo`, `lanes`, `nodes`, `edges`, `data_objects`, `gateways`, `loops_detectados`, `atividades_ordenadas`. |
| `IndicadorJSON` | Indicador do PDF: `nome`, `formula`, `fonte_dados`, `frequencia`, `metas`. |
| `DocumentoPDFJSON` | Descritivo do PDF: `titulo`, `unidade_responsavel`, `descricao`, `procedimentos`, `amparo_legal`, `links`, `indicadores`, `metas`, `responsaveis`, `observacoes`. |
| `AutomationCandidateJSON` | Automação candidata: `id`, `nome`, `atividades_envolvidas`, `tipo_automacao`, `proposta`, `justificativa`, `beneficios`, `impactos`, `riscos`, `metricas`, `prioridade`, `justificativa_prioridade`, `gatilho`, `entradas`, `saidas`, `como_automatizar`. |
| `RunMetadata` | Resposta da API: `run_id`, `status`, `pipeline`, `avisos`, `erros`, `quantidade_automacoes`, `artefatos`. |
| `EstadoGrafo` | Estado tipado que percorre o grafo LangGraph. |

Enumerações auxiliares: `TipoNo`, `TipoGateway`, `TipoAutomacao` (`RPA`, `Agente de IA`, `Híbrida`, `API/Integração`), `Prioridade` (`baixa`, `média`, `alta`, `muito alta`) e `RunStatus`.

### Documento final

O `documento_final.md` segue as 7 seções obrigatórias da sprint: identificação do processo, leitura do BPMN, leitura do PDF, lista de automações candidatas (tabela-resumo), detalhamento por automação, riscos e limitações gerais, e recomendações de priorização. O `auditoria.json` contém `run_id`, `pipeline`, data da análise, o `ProcessoJSON`, o `DocumentoPDFJSON`, os candidatos, avisos, artefatos e o número de tentativas de reparo.

### Tipos de automação reconhecidos

| Tipo | Quando é aplicado |
|---|---|
| **RPA** | Tarefas repetitivas e determinísticas: cliques, formulários, consultas em sistemas sem API. |
| **Agente de IA** | Interpretação textual, classificação, geração de parecer, análise de conformidade. |
| **Híbrida** | Coleta mecânica (RPA) combinada com julgamento inteligente (IA). |
| **API/Integração** | Sistemas com API oficial ou exportação estruturada disponível. |

---

## Modelos de IA

O projeto **não treina nem hospeda modelos**: usa LLMs de terceiros por inferência remota, via OpenRouter (compatível com a API da OpenAI). Toda a integração está centralizada em `app/openrouter.py` (`chamar_llm`), consumida pelos nós `generate_candidates`, `critic_review`, `repair_output` e `bpmn_to_natural_language`.

- **Entrada do modelo:** *system prompt* + instrução + contexto estruturado (JSON do BPMN e do PDF) ou narrativo, conforme o pipeline. Os prompts são versionados em `prompts/*.md`.
- **Saída do modelo:** JSON com a lista de automações candidatas, posteriormente limpo (remoção de cercas de código Markdown) e validado por Pydantic v2.
- **Parâmetros:** temperatura `0.2` e `max_tokens` `8000` por padrão; modelo, timeout e URL base configuráveis por `.env`.
- **Robustez:** o laço `validate_schema ⇄ repair_output` corrige automaticamente saídas malformadas até `MAX_REPAIR_ATTEMPTS`.

Não há OCR: PDFs baseados em imagem (escaneados) não são suportados nesta versão.

---

## API HTTP

Subir o servidor de desenvolvimento (a partir da raiz do projeto):

```bash
uvicorn app.api.main:app --reload
```

Documentação interativa (Swagger) em `http://127.0.0.1:8000/docs`.

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Verificação de disponibilidade. Retorna `{"status": "ok", "versao": "1.0.0"}`. |
| `POST` | `/analisar-processo` | Recebe `bpmn_file`, `pdf_file` (multipart) e o campo `pipeline` (`json` \| `natural` \| `both`, padrão `json`). Roda o pipeline e retorna um `RunMetadata`. |
| `GET` | `/runs/{run_id}` | Consulta os metadados de uma execução (do registro em memória). |
| `GET` | `/runs/{run_id}/download/{artefato}` | Baixa um artefato. O código do artefato é o caminho relativo dentro de `artefatos/`, no formato `<abordagem>/<arquivo>` (ex.: `json/documento_final.pdf`). |

### Exemplo

```bash
curl -X POST http://127.0.0.1:8000/analisar-processo \
  -F "bpmn_file=@entradas/Vacância/Verificação de Pendências.bpmn" \
  -F "pdf_file=@entradas/Vacância/vacancia.pdf" \
  -F "pipeline=json"
```

A resposta inclui `run_id`, `status`, contagem de automações por abordagem e o mapa de `artefatos` (código → caminho). Use o `run_id` para consultar o status ou baixar cada artefato.

### Segurança e autenticação

A API **não possui autenticação** — foi concebida para uso local/acadêmico. Todos os uploads passam por validação de extensão, limite de tamanho (leitura em blocos, aborta cedo), rejeição de arquivos vazios e verificação de XML seguro (`defusedxml`, bloqueando XXE e *billion laughs*). O download tem trava anti *path traversal*: o alvo precisa estar contido em `artefatos/`. O registro de execuções é mantido em memória, então **o status é perdido ao reiniciar o servidor**, mas o download continua funcionando (lê do disco).

---

## Interface Streamlit

`streamlit_app.py` é um painel que executa os dois pipelines (`json` e `natural`) sobre os processos de exemplo em `entradas/` e os compara por três caminhos independentes:

1. **Métricas objetivas e determinísticas**, calculadas sobre os campos estruturados de cada `AutomationCandidateJSON` e do documento final, seguindo os critérios da sprint — sem depender do LLM.
2. **Leitura qualitativa** por um LLM, que analisa o documento final completo de cada abordagem.
3. **Análise macro** entre todos os processos, indicando em que tipo de processo cada abordagem tende a se sair melhor.

Executar (a partir da raiz):

```bash
streamlit run streamlit_app.py
```

---

## Testes

A suíte usa **pytest** e cobre os nós da Entrega 1 (linguagem natural) contra os arquivos de exemplo em `entradas/` — normalização de BPMN, extração de texto de PDF e montagem de contexto — além de um teste ponta a ponta sem LLM.

```bash
pytest -q
```

Os testes que dependem do LLM só rodam se `OPENROUTER_API_KEY` estiver configurada de verdade (não com o placeholder); caso contrário, são automaticamente ignorados (`skip`) para não consumir créditos. Alguns testes usam caminhos com caracteres acentuados (ex.: `Análise.bpmn`); certifique-se de que o repositório foi clonado preservando a codificação UTF-8 dos nomes de arquivo, ou esses testes não localizarão os *fixtures*.

---

## Logs

O projeto usa o módulo padrão `logging`, configurado na CLI no formato `HH:MM:SS | NÍVEL | módulo | mensagem`. O nível padrão é `INFO`; a flag `--verbose` eleva todos os loggers do namespace `app` para `DEBUG`. **Os logs são emitidos no console (stdout/stderr)** — não há gravação em arquivo. Cada nó registra o que produziu e onde salvou; erros e avisos também são acumulados no `EstadoGrafo` e impressos no resumo final da execução.

---

## Segurança

- **Segredos fora do código:** a chave do OpenRouter é lida de `.env`, nunca *hardcoded*. O `.env` é ignorado pelo git.
- **Parsing de XML seguro:** o BPMN é lido com `defusedxml`, que bloqueia entidades externas (XXE) e expansão de entidades (*billion laughs*). O conteúdo é apenas analisado, nunca executado.
- **Proteção contra path traversal:** tanto o nó `ingest_files` quanto o endpoint de download rejeitam caminhos absolutos, `..` e alvos fora das pastas permitidas.
- **Validação de uploads:** extensão, tamanho máximo (leitura em blocos) e rejeição de arquivos vazios, com o mesmo limite (`MAX_FILE_SIZE_BYTES`) na API e no grafo.
- **Nome de arquivo controlado:** os uploads são salvos com nomes fixos (`processo.bpmn`, `descritivo.pdf`), nunca com o nome enviado pelo usuário.

---

## Desenvolvimento e contribuição

- **Padrão de nós:** cada etapa do pipeline é uma função `func(estado: EstadoGrafo) -> EstadoGrafo` em `app/nodes/`. Para adicionar uma etapa, crie o nó, registre-o no grafo em `app/graph.py` e adicione a aresta condicional correspondente.
- **Prompts versionados:** edite os arquivos em `prompts/` — eles são carregados em tempo de execução por `app/prompts.py`, sem necessidade de tocar no código Python.
- **Caminhos:** use sempre os helpers de `app/utils/config.py` em vez de montar strings de caminho manualmente.
- **Lint:** o projeto declara `ruff` como dependência de qualidade (`ruff check .`), embora não haja um arquivo de configuração de lint versionado.
- **Fluxo sugerido:** rode o `--dry-run` e a suíte `pytest` antes de abrir um PR; garanta que a CLI retorne código 0 no processo de exemplo.

---

## Limitações conhecidas

Levantadas diretamente do código durante a auditoria:

- **Sem OCR:** PDFs escaneados (sem camada de texto) não são suportados. O extrator assume o template do Bizagi, com rótulos de seção em estilo *footer*; PDFs com outra estrutura podem ser extraídos de forma incompleta.
- **Status da API em memória:** o registro de execuções (`GET /runs/{run_id}`) é volátil e se perde ao reiniciar o servidor. O download, por ler do disco, sobrevive ao reinício.
- **Sem autenticação na API:** destinada a uso local/acadêmico.
- **Config duplicada:** existe uma cópia legada de `config.py` em `app/api/utils/`, com um arquivo `__init__ .py` cujo nome contém um espaço indevido. Todo o código importa de fato `app/utils/config.py`; a cópia da API não é usada e pode ser removida com segurança.
- **Dependência de LLM externo:** a qualidade e o custo das automações dependem do modelo escolhido no OpenRouter e da disponibilidade da API.
- **Codificação de nomes de arquivo:** alguns *fixtures* de teste e entradas usam nomes acentuados; ambientes que não preservem UTF-8 nos nomes de arquivo podem falhar ao localizá-los.
- **Sem versões fixadas:** por decisão de projeto, `requirements.txt` não fixa versões, o que facilita a instalação mas reduz a reprodutibilidade exata.

---

## Melhorias futuras

Sugestões observadas durante a análise (não são funcionalidades existentes):

- Adicionar um `.env.example` documentando todas as variáveis.
- Remover a cópia morta de `app/api/utils/config.py` e corrigir o `__init__ .py` com espaço no nome.
- Empacotar a execução com **Docker/`docker-compose`** e adicionar um pipeline de **CI** (lint + testes) — ambos ausentes hoje, apesar de mencionados como metas da sprint.
- Fixar versões das dependências (ou usar *lockfile*) para reprodutibilidade.
- Ampliar a suíte de testes para cobrir também o pipeline JSON e os nós de renderização.
- Persistir o registro de execuções da API (banco leve ou arquivo) para o status sobreviver a reinícios.
- Suporte opcional a OCR para PDFs escaneados.
- Adicionar um arquivo `LICENSE`.

---

## Equipe

| Integrante | GitHub |
|---|---|
| Arthur Schneider | [@SchneiderArt](https://github.com/SchneiderArt) |
| Davi Gaborim | [@davigaborim](https://github.com/davigaborim) | 
| Emily Flores | [@Emily-Flo223](https://github.com/Emily-Flo223) | 
| Wellington Cintra | [@wellingtoncintra](https://github.com/wellingtoncintra) |

---

## Referências

- [OpenRouter — Quickstart](https://openrouter.ai/docs/quickstart)
- [LangGraph — conceitos de baixo nível](https://langchain-ai.github.io/langgraph/concepts/low_level/)
- [Pydantic v2 — Models](https://docs.pydantic.dev/latest/concepts/models/)
- [FastAPI — Request Files](https://fastapi.tiangolo.com/tutorial/request-files/)
- [PyMuPDF — documentação](https://pymupdf.readthedocs.io/)

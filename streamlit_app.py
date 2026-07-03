"""
streamlit_app.py — Comparativo Natural (Entrega 1) vs JSON (Entrega 2)
Sprint 2 — UFMS Apoia MDA e MAPA / Meta 3

Roda os dois pipelines já existentes no projeto para os processos
selecionados e compara as duas abordagens por três caminhos independentes:

1. Métricas OBJETIVAS e determinísticas, calculadas em cima dos campos
   estruturados de cada AutomationCandidateJSON e do documento final,
   usando exatamente os critérios definidos pelo documento da Sprint 2
   (seção 9 — modelo do documento final; seção 9.1 — campos obrigatórios
   por automação; seção 9.2 — critérios de separação). Isso NÃO depende
   de LLM e não pode ser enviesado por quantidade de itens.
2. Uma leitura qualitativa complementar feita por um LLM, que lê o
   documento final COMPLETO de cada abordagem (não um resumo).
3. Uma análise macro entre todos os processos processados, tentando
   explicar (com base só nos dados coletados) em que tipo de processo
   cada abordagem tende a se sair melhor.

Cada processo aparece como um card resumido; clique em "Ver detalhes"
para abrir o resultado completo em uma janela cheia (st.dialog).

Como rodar (raiz do projeto, onde está o run.py):
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.graph import construir_grafo_json, construir_grafo_natural  # noqa: E402
from app.openrouter import chamar_llm  # noqa: E402
from app.schemas import AutomationCandidateJSON, DocumentoPDFJSON, EstadoGrafo, ProcessoJSON  # noqa: E402

ENTRADAS_DIR = Path("entradas")


def descobrir_processos() -> list[dict]:
    processos: list[dict] = []
    if not ENTRADAS_DIR.exists():
        return processos
    for pasta in sorted(p for p in ENTRADAS_DIR.iterdir() if p.is_dir()):
        pdfs = sorted(pasta.glob("*.pdf"))
        bpmns = sorted(pasta.glob("*.bpmn"))
        if len(pdfs) != 1 or not bpmns:
            continue
        for bpmn in bpmns:
            rotulo = pasta.name if len(bpmns) == 1 else f"{pasta.name} — {bpmn.stem}"
            processos.append(
                {"id": f"{pasta.name}/{bpmn.stem}", "label": rotulo, "bpmn": str(bpmn), "pdf": str(pdfs[0])}
            )
    return processos


def rodar_pipeline(grafo, caminho_bpmn: str, caminho_pdf: str, run_id: str, nome_saida: str) -> EstadoGrafo:
    resultado = grafo.invoke(
        EstadoGrafo(
            run_id=run_id, caminho_bpmn=caminho_bpmn, caminho_pdf=caminho_pdf, nome_saida=nome_saida
        ).model_dump()
    )
    return EstadoGrafo.model_validate(resultado)


# ---------------------------------------------------------------------------
# Leitura do documento final completo (não um resumo)
# ---------------------------------------------------------------------------

_MAX_CHARS_POR_DOC = 40_000


def _ler_documento_md(caminho: str | None) -> str:
    if not caminho or not Path(caminho).exists():
        return "(documento final não encontrado)"
    texto = Path(caminho).read_text(encoding="utf-8")
    if len(texto) <= _MAX_CHARS_POR_DOC:
        return texto
    metade = _MAX_CHARS_POR_DOC // 2
    return texto[:metade] + "\n\n[... documento truncado por tamanho ...]\n\n" + texto[-metade:]


# ---------------------------------------------------------------------------
# Métricas objetivas e determinísticas (seções 9, 9.1 e 9.2 do documento)
# ---------------------------------------------------------------------------

_CAMPOS_9_1 = [
    "atividades_envolvidas", "gatilho", "entradas", "saidas", "como_automatizar",
    "proposta", "justificativa", "beneficios", "impactos", "riscos",
    "metricas", "justificativa_prioridade",
]

_FRASES_VAGAS = [
    "melhora a eficiência", "reduz erros", "aumenta a produtividade", "otimiza o processo",
    "melhora o processo", "agiliza o processo", "maior eficiência", "melhora a qualidade",
    "reduz o tempo", "melhora a gestão", "facilita o trabalho", "torna mais eficiente",
    "reduz retrabalho", "melhora a comunicação", "aumenta a eficiência", "traz mais agilidade",
    "melhora o desempenho", "ganho de eficiência",
]

_SECOES_OBRIGATORIAS = [
    ("Identificação do processo", r"identifica[cç][aã]o do processo"),
    ("Leitura do BPMN", r"leitura do bpmn"),
    ("Leitura do PDF", r"leitura do pdf"),
    ("Lista de automações candidatas", r"(lista de )?automa[cç][oõ]es candidatas"),
    ("Seção individual por automação", r"(se[cç][aã]o individual|detalhamento).{0,20}automa"),
    ("Riscos e limitações", r"riscos e limita[cç][oõ]es"),
    ("Recomendações de priorização", r"recomenda[cç][oõ]es de prioriza[cç][aã]o"),
]

PESOS_METRICAS = {
    "completude": 0.20,
    "especificidade": 0.15,
    "rastreabilidade": 0.20,
    "agrupamento": 0.15,
    "cobertura": 0.15,
    "estrutura": 0.10,
    "quantidade": 0.05,
}

ROTULOS_METRICAS = {
    "completude": "Completude dos campos obrigatórios (§9.1)",
    "especificidade": "Especificidade (baixa generalização)",
    "rastreabilidade": "Rastreabilidade (evidências do BPMN e do PDF)",
    "agrupamento": "Coerência de agrupamento (§9.2)",
    "cobertura": "Cobertura das atividades do BPMN",
    "estrutura": "Estrutura do documento final (§9)",
    "quantidade": "Quantidade de automações (peso baixo, auxiliar)",
}


def _preenchido(valor) -> bool:
    if isinstance(valor, list):
        return len(valor) > 0 and all(len(str(v).strip()) >= 3 for v in valor)
    if valor is None:
        return False
    return len(str(valor).strip()) >= 8


def completude_media(candidatos: list[AutomationCandidateJSON]) -> float:
    if not candidatos:
        return 0.0
    total = len(_CAMPOS_9_1)
    soma = sum(sum(1 for campo in _CAMPOS_9_1 if _preenchido(getattr(c, campo))) / total for c in candidatos)
    return soma / len(candidatos)


def especificidade_media(candidatos: list[AutomationCandidateJSON]) -> float:
    if not candidatos:
        return 0.0
    notas = []
    for c in candidatos:
        texto = " ".join([c.justificativa, c.proposta, *c.beneficios, *c.impactos]).lower()
        n_palavras = max(1, len(texto.split()))
        hits = sum(texto.count(f) for f in _FRASES_VAGAS)
        densidade_por_100 = hits / (n_palavras / 100)
        notas.append(max(0.0, 1 - min(1.0, densidade_por_100 / 3)))
    return sum(notas) / len(notas)


def _tokens_pdf(doc: DocumentoPDFJSON | None) -> list[str]:
    if not doc:
        return []
    tokens = list(doc.amparo_legal or []) + [i.nome for i in (doc.indicadores or [])] + list(doc.metas or [])
    if doc.unidade_responsavel:
        tokens.append(doc.unidade_responsavel)
    return [t.lower() for t in tokens if t and len(t) >= 4]


def rastreabilidade_media(
    candidatos: list[AutomationCandidateJSON], atividades_reais: list[str], tokens_pdf: list[str]
) -> float:
    if not candidatos:
        return 0.0
    acertos = 0
    for c in candidatos:
        ativ_txt = " ".join(c.atividades_envolvidas).lower()
        if atividades_reais:
            bpmn_ok = any(a.lower() in ativ_txt or ativ_txt in a.lower() for a in atividades_reais if a)
        else:
            bpmn_ok = bool(c.atividades_envolvidas)
        texto_evid = (c.justificativa + " " + c.proposta).lower()
        pdf_ok = any(tok in texto_evid for tok in tokens_pdf) if tokens_pdf else False
        if bpmn_ok and pdf_ok:
            acertos += 1
    return acertos / len(candidatos)


def agrupamento_score(candidatos: list[AutomationCandidateJSON]) -> float:
    if not candidatos:
        return 0.0
    razoaveis = sum(1 for c in candidatos if 1 <= len(c.atividades_envolvidas) <= 4)
    return razoaveis / len(candidatos)


def cobertura_bpmn(candidatos: list[AutomationCandidateJSON], atividades_reais: list[str]) -> float | None:
    if not atividades_reais:
        return None
    cobertas = set()
    for c in candidatos:
        for a in c.atividades_envolvidas:
            al = a.lower()
            for real in atividades_reais:
                if real and (al in real.lower() or real.lower() in al):
                    cobertas.add(real.lower())
    return len(cobertas) / len(atividades_reais)


def estrutura_documento(md_texto: str) -> float:
    if not md_texto:
        return 0.0
    texto = md_texto.lower()
    achadas = sum(1 for _, padrao in _SECOES_OBRIGATORIAS if re.search(padrao, texto))
    return achadas / len(_SECOES_OBRIGATORIAS)


def montar_metricas(
    candidatos: list[AutomationCandidateJSON],
    md_texto: str,
    atividades_reais: list[str],
    tokens_pdf: list[str],
    n_max: int,
) -> dict:
    valores = {
        "completude": completude_media(candidatos),
        "especificidade": especificidade_media(candidatos),
        "rastreabilidade": rastreabilidade_media(candidatos, atividades_reais, tokens_pdf),
        "agrupamento": agrupamento_score(candidatos),
        "cobertura": cobertura_bpmn(candidatos, atividades_reais),
        "estrutura": estrutura_documento(md_texto),
        "quantidade": (len(candidatos) / n_max) if n_max else 0.0,
    }
    pesos_validos = {k: PESOS_METRICAS[k] for k, v in valores.items() if v is not None}
    soma_pesos = sum(pesos_validos.values()) or 1.0
    composto = sum(valores[k] * pesos_validos[k] for k in pesos_validos) / soma_pesos
    for k in valores:
        if valores[k] is None:
            valores[k] = 0.0
    valores["composto"] = composto
    return valores


def definir_vencedor_objetivo(m_json: dict, m_nat: dict, margem: float = 0.02) -> str:
    diff = m_json["composto"] - m_nat["composto"]
    if abs(diff) < margem:
        return "empate"
    return "json" if diff > 0 else "natural"


# ---------------------------------------------------------------------------
# Análise qualitativa complementar por LLM (lê o documento completo)
# ---------------------------------------------------------------------------


def _limpar_json(texto: str) -> str:
    texto = re.sub(r"```(?:json)?\s*", "", texto)
    texto = re.sub(r"```", "", texto)
    inicio = texto.find("{")
    return texto[inicio:].strip() if inicio > 0 else texto.strip()


def analisar_diferenca(nome_processo: str, md_json: str, md_natural: str) -> dict:
    system_prompt = (
        "Você é um avaliador técnico independente de documentos de automação de "
        "processos administrativos. Você receberá dois documentos finais completos "
        "(Markdown), gerados a partir do mesmo processo por duas abordagens de "
        "pipeline diferentes. Leia os dois documentos INTEIROS de ponta a ponta — "
        "identificação do processo, leitura do BPMN, leitura do descritivo em PDF, "
        "lista de automações, detalhamento de cada automação, riscos/limitações e "
        "recomendações de priorização — e não apenas a lista/quantidade de "
        "automações candidatas. Avalie qualidade real: especificidade das "
        "justificativas, uso concreto de evidências do BPMN e do PDF, coerência "
        "entre as seções, profundidade do detalhamento por automação (gatilho, "
        "entradas, saídas, como automatizar, riscos, métricas) e ausência de "
        "generalizações vagas. Quantidade de automações listadas NÃO é, por si só, "
        "sinal de qualidade superior. Responda APENAS com um JSON válido, sem "
        "markdown, no formato:\n"
        '{"vencedor": "A" | "B" | "empate", '
        '"analise": "<3-5 frases explicando as diferenças de especificidade, uso de '
        'evidências do processo e qualidade das justificativas entre A e B, com base '
        'no documento completo>"}'
    )
    user_prompt = (
        f"Processo: {nome_processo}\n\n"
        f"=== DOCUMENTO A (completo) ===\n{md_json}\n\n"
        f"=== DOCUMENTO B (completo) ===\n{md_natural}\n"
    )
    resposta = chamar_llm(system_prompt=system_prompt, user_prompt=user_prompt, temperatura=0.1, max_tokens=800)
    dados = json.loads(_limpar_json(resposta))
    vencedor_map = {"A": "json", "B": "natural", "empate": "empate"}
    return {"vencedor": vencedor_map.get(dados.get("vencedor"), "empate"), "analise": dados.get("analise", "")}


# ---------------------------------------------------------------------------
# Análise macro entre todos os processos processados
# ---------------------------------------------------------------------------


def montar_resumos_para_meta_analise(resultados: dict) -> list[dict]:
    resumos = []
    for r in resultados.values():
        if r.get("erro_json") or r.get("erro_natural") or not r.get("metricas_json"):
            continue
        resumos.append(
            {
                "processo": r["label"],
                "perfil_estrutural_bpmn": r.get("perfil_processo", {}),
                "n_automacoes_json": len(r["json"]),
                "n_automacoes_natural": len(r["natural"]),
                "metricas_json": {k: round(v, 3) for k, v in r["metricas_json"].items()},
                "metricas_natural": {k: round(v, 3) for k, v in r["metricas_natural"].items()},
                "diferenca_nota_composta_json_menos_natural": round(
                    r["metricas_json"]["composto"] - r["metricas_natural"]["composto"], 3
                ),
                "vencedor_objetivo": r["vencedor_objetivo"],
            }
        )
    return resumos


def analisar_padroes_gerais(resumos: list[dict]) -> str:
    """Pede ao LLM uma leitura macro, honesta e criteriosa dos resultados de
    TODOS os processos já processados, tentando explicar em que tipo de
    processo cada abordagem tende a se sair melhor — só com base nos dados
    numéricos fornecidos, sem inventar informação."""
    system_prompt = (
        "Você é um metodólogo de pesquisa aplicada, especialista em comparação "
        "empírica de pipelines de IA para automação de processos administrativos "
        "institucionais. Você vai receber um resumo estruturado em JSON com os "
        "resultados de N processos, cada um avaliado por duas abordagens "
        "concorrentes — 'json' (representação intermediária estruturada) e "
        "'natural' (narrativa em linguagem natural) — segundo 7 métricas "
        "objetivas e determinísticas (0 a 1, sem intervenção de LLM):\n"
        "- completude: % de campos obrigatórios da automação (§9.1) realmente preenchidos;\n"
        "- especificidade: ausência de frases genéricas/vagas nas justificativas e benefícios;\n"
        "- rastreabilidade: se a automação cita evidência real do BPMN E do PDF, não genérica;\n"
        "- agrupamento: coerência ao agrupar atividades numa automação (nem tudo junto, nem tudo separado), conforme §9.2;\n"
        "- cobertura: % das atividades do BPMN endereçadas por alguma automação;\n"
        "- estrutura: presença das 7 seções obrigatórias do documento final (§9);\n"
        "- quantidade: número relativo de automações geradas (peso baixo, auxiliar).\n"
        "Cada processo também traz um perfil estrutural do BPMN de origem: número "
        "de atividades, raias (lanes), gateways/decisões e loops detectados.\n\n"
        "Sua tarefa é escrever uma análise MACRO, criteriosa e HONESTA — não "
        "confirmatória — que:\n"
        "1. Diga se existe um padrão consistente de qual abordagem tende a vencer "
        "no conjunto de processos, ou se o resultado é misto/inconclusivo.\n"
        "2. Para os processos em que uma abordagem venceu com folga, aponte, com "
        "base SOMENTE nos números e no perfil estrutural fornecidos, quais fatores "
        "plausíveis explicam essa vitória (ex.: processos com muitos gateways/"
        "decisões podem se beneficiar da representação estruturada porque ela "
        "força o preenchimento explícito de atividades_envolvidas e gatilho por "
        "automação; processos com poucas atividades e descrição em PDF rica em "
        "contexto podem favorecer a narrativa em linguagem natural, que preserva "
        "nuance sem fragmentar o texto em campos rígidos). NÃO invente causas que "
        "não sejam sustentadas pelos números fornecidos — se não for possível "
        "explicar com segurança, diga isso explicitamente em vez de especular.\n"
        "3. Aponte qual das 7 métricas mais frequentemente decide o resultado "
        "entre as duas abordagens neste conjunto (a que mais varia entre json e "
        "natural), e o que isso sugere sobre o ponto forte estrutural de cada "
        "pipeline.\n"
        "4. Se a amostra tiver poucos processos (menos de 3), diga isso sem meias "
        "palavras e explique por que generalizações são limitadas nesse caso.\n"
        "5. NÃO adote nem sugira nenhuma conclusão predefinida. Se os dados "
        "mostrarem consistentemente uma abordagem perdendo — inclusive a "
        "estruturada em JSON —, diga isso exatamente como está, mesmo que "
        "contrarie a hipótese de que uma representação estruturada deveria ser "
        "superior. A honestidade da leitura é mais importante do que confirmar "
        "qualquer expectativa prévia sobre o resultado.\n\n"
        "Responda em Markdown, em português, com exatamente estas seções:\n"
        "## Padrão geral observado\n"
        "## Quando a abordagem JSON tende a se sair melhor\n"
        "## Quando a abordagem em linguagem natural tende a se sair melhor\n"
        "## Métrica que mais explica a diferença\n"
        "## Limitações da amostra\n"
        "## Recomendação metodológica para a sprint\n"
        "Seja direto, use os números fornecidos como evidência (cite valores "
        "quando fizer uma afirmação) e evite generalizações vazias."
    )
    user_prompt = "Resumo estruturado dos processos avaliados:\n\n" + json.dumps(resumos, ensure_ascii=False, indent=2)
    return chamar_llm(system_prompt=system_prompt, user_prompt=user_prompt, temperatura=0.2, max_tokens=1800)


# ---------------------------------------------------------------------------
# UI — helpers de renderização
# ---------------------------------------------------------------------------


def _grafico_barras(rotulos: list[str], valores: list[float], altura: int = 220) -> go.Figure:
    fig = go.Figure(go.Bar(x=rotulos, y=valores, marker_color=["#4C78A8", "#F58518"]))
    fig.update_layout(height=altura, margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
    return fig


def _grafico_metricas(m_json: dict, m_nat: dict) -> go.Figure:
    chaves = list(PESOS_METRICAS.keys())
    fig = go.Figure()
    fig.add_trace(go.Bar(name="JSON", x=[ROTULOS_METRICAS[k] for k in chaves], y=[m_json[k] for k in chaves], marker_color="#4C78A8"))
    fig.add_trace(go.Bar(name="Natural", x=[ROTULOS_METRICAS[k] for k in chaves], y=[m_nat[k] for k in chaves], marker_color="#F58518"))
    fig.update_layout(
        barmode="group", height=380, yaxis=dict(range=[0, 1], tickformat=".0%"),
        margin=dict(t=10, b=100, l=10, r=10), legend=dict(orientation="h", y=1.1),
    )
    return fig


def _renderizar_candidato(c: AutomationCandidateJSON) -> None:
    st.markdown(f"**{c.id} — {c.nome}**  ·  `{c.tipo_automacao.value}`  ·  prioridade: `{c.prioridade.value}`")
    st.markdown(f"- **Atividades envolvidas:** {', '.join(c.atividades_envolvidas) or '—'}")
    st.markdown(f"- **Gatilho:** {c.gatilho or '—'}")
    st.markdown(f"- **Entradas:** {', '.join(c.entradas) or '—'}")
    st.markdown(f"- **Saídas:** {', '.join(c.saidas) or '—'}")
    st.markdown(f"- **Como automatizar:** {c.como_automatizar or '—'}")
    st.markdown(f"- **Proposta:** {c.proposta or '—'}")
    st.markdown(f"- **Justificativa:** {c.justificativa or '—'}")
    st.markdown(f"- **Benefícios:** {', '.join(c.beneficios) or '—'}")
    st.markdown(f"- **Impactos:** {', '.join(c.impactos) or '—'}")
    st.markdown(f"- **Riscos:** {', '.join(c.riscos) or '—'}")
    st.markdown(f"- **Métricas de sucesso:** {', '.join(c.metricas) or '—'}")
    st.markdown(f"- **Justificativa da prioridade:** {c.justificativa_prioridade or '—'}")
    st.divider()


@st.dialog("Detalhes do processo", width="large")
def abrir_detalhes(r: dict) -> None:
    st.subheader(r["label"])

    n_json, n_natural = len(r["json"]), len(r["natural"])
    c1, c2 = st.columns(2)
    c1.metric("Automações — JSON", n_json)
    c2.metric("Automações — Natural", n_natural)
    st.plotly_chart(_grafico_barras(["JSON", "Natural"], [n_json, n_natural]), use_container_width=True, config={"displayModeBar": False})

    m_json, m_nat = r["metricas_json"], r["metricas_natural"]
    st.markdown("**Qualidade — critérios objetivos (§9 / §9.1 / §9.2 do documento da sprint)**")
    cc1, cc2 = st.columns(2)
    cc1.metric("Nota composta — JSON", f"{m_json['composto']*100:.1f}%")
    cc2.metric("Nota composta — Natural", f"{m_nat['composto']*100:.1f}%")
    st.plotly_chart(_grafico_metricas(m_json, m_nat), use_container_width=True, config={"displayModeBar": False})

    vencedor_obj = r["vencedor_objetivo"]
    rotulo_obj = {
        "json": "🏆 JSON venceu pelos critérios objetivos",
        "natural": "🏆 Natural venceu pelos critérios objetivos",
        "empate": "Empate técnico pelos critérios objetivos (diferença < 2 pontos)",
    }[vencedor_obj]
    (st.success if vencedor_obj != "empate" else st.warning)(rotulo_obj)

    if r.get("analise"):
        vencedor_ia = r["analise"]["vencedor"]
        rotulo_ia = {"json": "Parecer da IA: JSON teve melhor qualidade", "natural": "Parecer da IA: Natural teve melhor qualidade", "empate": "Parecer da IA: empate"}[vencedor_ia]
        st.info(f"**{rotulo_ia}** (leitura do documento completo) — {r['analise']['analise']}")
    elif r.get("analise_erro"):
        st.caption(f"Parecer qualitativo indisponível: {r['analise_erro']}")

    aba_metricas, aba_json, aba_natural, aba_doc_json, aba_doc_natural = st.tabs(
        ["Métricas detalhadas", "Candidatos — JSON", "Candidatos — Natural", "Documento — JSON", "Documento — Natural"]
    )

    with aba_metricas:
        linhas = [
            {"Critério": ROTULOS_METRICAS[k], "Peso": f"{PESOS_METRICAS[k]*100:.0f}%", "JSON": f"{m_json[k]*100:.1f}%", "Natural": f"{m_nat[k]*100:.1f}%"}
            for k in PESOS_METRICAS
        ]
        linhas.append({"Critério": "Nota composta", "Peso": "100%", "JSON": f"{m_json['composto']*100:.1f}%", "Natural": f"{m_nat['composto']*100:.1f}%"})
        st.table(linhas)

    with aba_json:
        for c in r["json"] or []:
            _renderizar_candidato(c)
        if not r["json"]:
            st.caption("Nenhuma automação candidata gerada.")

    with aba_natural:
        for c in r["natural"] or []:
            _renderizar_candidato(c)
        if not r["natural"]:
            st.caption("Nenhuma automação candidata gerada.")

    with aba_doc_json:
        st.markdown(r.get("md_json", "(indisponível)"))

    with aba_doc_natural:
        st.markdown(r.get("md_natural", "(indisponível)"))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Natural vs JSON", layout="wide")
st.title("Natural vs JSON")
st.caption("Comparativo dos dois pipelines da Sprint 2 — métricas objetivas (§9/§9.1/§9.2) + parecer qualitativo por IA.")

if "resultados" not in st.session_state:
    st.session_state.resultados = {}
if "analise_geral" not in st.session_state:
    st.session_state.analise_geral = None
if "analise_geral_erro" not in st.session_state:
    st.session_state.analise_geral_erro = None

processos = descobrir_processos()

with st.sidebar:
    selecionados = st.multiselect("Processos", options=[p["label"] for p in processos])
    usar_ia = st.checkbox("Parecer qualitativo por IA (complementar)", value=True)
    col_a, col_b = st.columns(2)
    processar = col_a.button("Processar", type="primary")
    if col_b.button("Limpar"):
        st.session_state.resultados = {}
        st.session_state.analise_geral = None
        st.session_state.analise_geral_erro = None
        st.rerun()

if processar and selecionados:
    mapa = {p["label"]: p for p in processos}
    grafo_json = construir_grafo_json()
    grafo_natural = construir_grafo_natural()
    st.session_state.analise_geral = None
    st.session_state.analise_geral_erro = None

    for label in selecionados:
        proc = mapa[label]
        with st.spinner(f"Processando {label}..."):
            sufixo = uuid.uuid4().hex[:6]
            base = f"st-{sufixo}"
            r = {"label": label}

            try:
                e_json = rodar_pipeline(grafo_json, proc["bpmn"], proc["pdf"], f"{base}-j", f"{base}_j")
                r["json"] = e_json.candidatos
                r["erro_json"] = "; ".join(e_json.erros) if e_json.erros else None
            except Exception as exc:
                e_json = None
                r["json"], r["erro_json"] = [], str(exc)

            try:
                e_nat = rodar_pipeline(grafo_natural, proc["bpmn"], proc["pdf"], f"{base}-n", f"{base}_n")
                r["natural"] = e_nat.candidatos
                r["erro_natural"] = "; ".join(e_nat.erros) if e_nat.erros else None
            except Exception as exc:
                e_nat = None
                r["natural"], r["erro_natural"] = [], str(exc)

            r["analise"] = None
            if not r["erro_json"] and not r["erro_natural"]:
                md_json = _ler_documento_md(e_json.artefatos.get("documento_final_md"))
                md_natural = _ler_documento_md(e_nat.artefatos.get("documento_final_md"))
                r["md_json"], r["md_natural"] = md_json, md_natural

                processo_ref: ProcessoJSON | None = e_json.processo_json or e_nat.processo_json
                pdf_ref: DocumentoPDFJSON | None = e_json.documento_pdf_json or e_nat.documento_pdf_json
                atividades_reais = list(processo_ref.atividades_ordenadas) if processo_ref else []
                tokens_pdf = _tokens_pdf(pdf_ref)
                n_max = max(len(r["json"]), len(r["natural"]), 1)

                if processo_ref:
                    r["perfil_processo"] = {
                        "atividades": len(atividades_reais),
                        "lanes": len(processo_ref.lanes),
                        "gateways": len(processo_ref.gateways),
                        "loops": len(processo_ref.loops_detectados),
                    }
                else:
                    r["perfil_processo"] = {}

                r["metricas_json"] = montar_metricas(r["json"], md_json, atividades_reais, tokens_pdf, n_max)
                r["metricas_natural"] = montar_metricas(r["natural"], md_natural, atividades_reais, tokens_pdf, n_max)
                r["vencedor_objetivo"] = definir_vencedor_objetivo(r["metricas_json"], r["metricas_natural"])

                if usar_ia:
                    try:
                        r["analise"] = analisar_diferenca(label, md_json, md_natural)
                    except Exception as exc:
                        r["analise_erro"] = str(exc)

        st.session_state.resultados[proc["id"]] = r

resultados = st.session_state.resultados
if not resultados:
    st.info("Selecione processos na barra lateral e clique em **Processar**.")
    st.stop()

# ---------------------------------------------------------------------------
# Grade de cards — clique em "Ver detalhes" para abrir em tela cheia
# ---------------------------------------------------------------------------
itens = list(resultados.items())
colunas = st.columns(2)
for idx, (pid, r) in enumerate(itens):
    with colunas[idx % 2]:
        with st.container(border=True):
            st.markdown(f"**{r['label']}**")
            if r.get("erro_json") or r.get("erro_natural"):
                st.error(r.get("erro_json") or r.get("erro_natural"))
                continue

            m_json, m_nat = r["metricas_json"], r["metricas_natural"]
            c1, c2 = st.columns(2)
            c1.metric("JSON", f"{m_json['composto']*100:.0f}%", help=f"{len(r['json'])} automações")
            c2.metric("Natural", f"{m_nat['composto']*100:.0f}%", help=f"{len(r['natural'])} automações")

            vencedor_obj = r["vencedor_objetivo"]
            emoji_badge = {"json": "🏆 JSON venceu", "natural": "🏆 Natural venceu", "empate": "🤝 Empate técnico"}[vencedor_obj]
            st.caption(emoji_badge)

            if st.button("Ver detalhes", key=f"detalhes-{pid}", use_container_width=True):
                abrir_detalhes(r)

# ---------------------------------------------------------------------------
# Análise macro entre todos os processos processados
# ---------------------------------------------------------------------------
st.divider()
st.subheader("📊 Análise geral entre os processos processados")

resumos_validos = montar_resumos_para_meta_analise(resultados)
if not resumos_validos:
    st.caption("Processe ao menos um processo com sucesso para gerar a análise geral.")
else:
    if len(resumos_validos) < 3:
        st.caption(
            f"⚠️ Amostra pequena ({len(resumos_validos)} processo(s) válido(s)) — os padrões abaixo tendem a ser "
            "indicativos, não conclusivos. Processe mais processos para uma leitura mais robusta."
        )
    if st.button("Gerar análise geral entre os processos"):
        with st.spinner("Analisando padrões entre os processos..."):
            try:
                st.session_state.analise_geral = analisar_padroes_gerais(resumos_validos)
                st.session_state.analise_geral_erro = None
            except Exception as exc:
                st.session_state.analise_geral_erro = str(exc)

    if st.session_state.analise_geral:
        st.markdown(st.session_state.analise_geral)
    elif st.session_state.analise_geral_erro:
        st.error(f"Não foi possível gerar a análise geral: {st.session_state.analise_geral_erro}")
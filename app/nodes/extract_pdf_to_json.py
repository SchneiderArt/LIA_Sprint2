"""
Nó LangGraph: extract_pdf_to_json
Etapa 4 da Entrega 2 — Sprint 2

Responsabilidades (conforme documento da sprint, seções 4, 7 e 7.1):
  - Extrair o texto do PDF usando PyMuPDF (seção 11)
  - Preservar títulos e seções quando possível (seção 4, camada 3)
  - Identificar: normas, unidade responsável, procedimentos,
    indicadores (com fórmula, fonte, frequência, metas), links,
    responsáveis, metas gerais e observações (seção 4, camada 3)
  - Converter para DocumentoPDFJSON validado por Pydantic v2 (seção 4, camada 5)
  - Salvar em /saidas/intermediarios/pdf_estruturado.json (seção 7.1, passo 6)
  - Registrar warnings quando o PDF tiver texto ruim ou páginas vazias (seção 8.2)
  - OCR não é obrigatório nesta sprint (seção 8.2)

Observação de implementação:
  Os PDFs da sprint são exportados pelo Bizagi com um template onde os
  RÓTULOS DE SEÇÃO aparecem DEPOIS do conteúdo que nomeiam (footer-style).
  O extrator usa mapeamento reverso: para cada rótulo conhecido, o conteúdo
  que o precede é o conteúdo daquela seção.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import fitz  # PyMuPDF

from app.utils import config
from app.schemas import DocumentoPDFJSON, EstadoGrafo, IndicadorJSON

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rótulos de seção conhecidos no template Bizagi dos PDFs da sprint.
# Aparecem APÓS o conteúdo que descrevem (footer-style).
# ---------------------------------------------------------------------------
ROTULOS_SECAO = {
    "Descrição",
    "Procedimentos",
    "Amparo Legal",
    "Links",
    "Informações Complementares",
    "Informações complementares",
    "Ficha de Indicadores",
    "Descrição do Indicador",
    "Unidade Gestora",
    "Fórmula de cálculo",
    "Fonte / Forma de coleta de dados",
    "Parâmetro",
    "Unidade de Medida",
    "Observações Adicionais (recomendações)",
    "Observações Adicionais",
    "Frequência de medição",
    "Responsáveis",
    "Metas",
    "Controle de Versões",
}

# Padrões de norma/amparo legal
PADROES_NORMA = [
    r"IN\s+\w+\s+n[oº°]?\s*[\d.]+/\d+",
    r"Instrução Normativa\s+\w+\s+n[oº°]?\s*[\d.]+/\d+",
    r"Lei\s+(?:Complementar\s+)?n[oº°\.]*\s*[\d.]+(?:/\d+)?",
    r"Decreto(?:-Lei)?\s+n[oº°\.]*\s*[\d.]+(?:/\d+)?",
    r"Portaria\s+[\w/]+\s+n[oº°\.]*\s*[\d.,]+(?:/\d+)?",
    r"Portaria\s+n[oº°\.]*\s*[\d.,]+(?:/\d+)?",
    r"Emenda\s+Constitucional\s+n[oº°\.]*\s*[\d.]+(?:/\d+)?",
    r"Resolução\s+n[oº°\.]*\s*[\d.,]+(?:/\d+)?",
    r"Acórdão\s+n[oº°\.]*\s*[\d.]+/\d+",
    r"Nota\s+(?:Técnica|Informativa)[^\n]{0,80}",
    r"Medida\s+Provisória\s+n[oº°\.]*\s*[\d.,]+(?:/\d+)?",
]
RE_NORMA = re.compile("|".join(PADROES_NORMA), re.IGNORECASE)
RE_URL   = re.compile(r"https?://[^\s\)\"\'\<\>]+")
RE_META  = re.compile(
    r".{0,60}(?:alcançar|atingir|índice de|cobertura de|meta[:\s]+).{0,120}(?:%|por\s*cento)",
    re.IGNORECASE,
)
RE_FREQ  = re.compile(
    r"^(?:trimestral|semestral|anual|mensal|bimestral|quinzenal|semanal|diária?)\.?$",
    re.IGNORECASE,
)
RE_INDICADOR_TITULO = re.compile(r"^Indicador\s+(\d+)\s*[-–]\s*(.+)", re.IGNORECASE)
RE_FORMULA = re.compile(
    r"(?:=\s*[\(\(]|dividid[ao]\s+por|multiplicad[ao]\s+por|percentual\s*=).{10,400}",
    re.IGNORECASE,
)
RE_RESPONSAVEL = re.compile(
    r"(?:Chefe|Secretári[ao]|Diretor[a]?|Coordenador[a]?|Gestor[a]?|Pró-Reitor[a]?)"
    r".{0,120}(?:UFMS|Progep|Serp|Dipag|SEAL|DIFC|PROPLAN|Seqv|Sesem|Sefin|Proad|Sead|Sepag)",
    re.IGNORECASE,
)
RE_CONTROLE_VERSOES = re.compile(
    r"(?:Revisão #\d+|Criado\s+\d+|Atualizado\s+\d+|Versão\s+inicial|"
    r"^\d{1,2}/\d{2}/\d{4}$|^Versão$|^Data$|^Autor$|^Revisor$|^Aprovador$|"
    r"\[Caso não seja)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classe auxiliar para representar as linhas com metadados
# ---------------------------------------------------------------------------

class Linha:
    def __init__(self, texto: str, pagina: int):
        self.texto = texto.replace("\xa0", " ").strip()
        self.pagina = pagina
        self.is_rotulo = self.texto in ROTULOS_SECAO

    def __repr__(self):
        return f"Linha(p{self.pagina}, rotulo={self.is_rotulo}, '{self.texto[:50]}')"


# ---------------------------------------------------------------------------
# Extração de texto por página com PyMuPDF
# ---------------------------------------------------------------------------

def _extrair_linhas(caminho_pdf: str) -> tuple[list[Linha], list[str]]:
    """
    Abre o PDF com PyMuPDF e retorna (lista_de_Linha, avisos).
    Registra warnings para páginas vazias (seção 8.2 do documento).
    """
    avisos: list[str] = []
    linhas: list[Linha] = []

    try:
        doc = fitz.open(caminho_pdf)
    except Exception as exc:
        raise ValueError(f"Não foi possível abrir o PDF: {exc}") from exc

    for i, page in enumerate(doc):
        texto_pagina = page.get_text()
        if not texto_pagina or not texto_pagina.strip():
            avisos.append(f"PDF: página {i + 1} vazia ou sem texto extraível.")
            continue
        for linha_texto in texto_pagina.splitlines():
            linha_texto_strip = linha_texto.replace("\xa0", " ").strip()
            if linha_texto_strip:
                linhas.append(Linha(linha_texto_strip, i + 1))

    doc.close()

    total_chars = sum(len(l.texto) for l in linhas)
    if total_chars < 100:
        avisos.append(
            "PDF com texto insuficiente. O documento pode ser escaneado. "
            "OCR não é obrigatório nesta sprint (seção 8.2)."
        )

    return linhas, avisos


# ---------------------------------------------------------------------------
# Mapeamento reverso: rótulo → bloco de conteúdo que o precede
# ---------------------------------------------------------------------------

def _mapear_secoes(linhas: list[Linha]) -> dict[str, list[str]]:
    """
    Constrói {nome_rotulo: [linhas_de_conteudo]}.

    No template Bizagi, o rótulo aparece APÓS o conteúdo que nomeia.
    A estratégia é: para cada rótulo na posição i, o bloco de conteúdo
    que o precede vai do último rótulo até i-1.

    Quando múltiplos rótulos aparecem consecutivos (sem conteúdo entre eles),
    o bloco de conteúdo antes do primeiro rótulo é atribuído proporcionalmente:
    o rótulo mais próximo ao conteúdo recebe o bloco.
    """
    secoes: dict[str, list[str]] = {r: [] for r in ROTULOS_SECAO}
    # Adicionar entradas para indicadores (não conhecidos a priori)
    secoes["_titulo_processo"] = []
    secoes["_indicadores_raw"] = []

    n = len(linhas)
    i = 0

    while i < n:
        linha = linhas[i]

        # Detectar título de indicador (rótulo especial com conteúdo inline)
        m_ind = RE_INDICADOR_TITULO.match(linha.texto)
        if m_ind:
            # Juntar linhas consecutivas que completam o nome do indicador
            nome_ind = m_ind.group(2).strip()
            j = i + 1
            while j < n and not linhas[j].is_rotulo and not RE_INDICADOR_TITULO.match(linhas[j].texto):
                proximo = linhas[j].texto
                # Parar se a próxima linha parece ser um novo bloco de conteúdo (longa)
                if len(proximo) > 60 or proximo in ROTULOS_SECAO:
                    break
                # Continuar acumulando se é continuação do título
                if not RE_NORMA.search(proximo) and not RE_URL.search(proximo):
                    nome_ind += " " + proximo
                    j += 1
                else:
                    break
            secoes["_indicadores_raw"].append(f"__IND__{nome_ind.strip()}")
            i = j
            continue

        # Rótulo de seção normal
        if linha.is_rotulo:
            i += 1
            continue

        # Linha de conteúdo — procurar até onde vai antes do próximo rótulo/indicador
        bloco: list[str] = []
        while i < n and not linhas[i].is_rotulo and not RE_INDICADOR_TITULO.match(linhas[i].texto):
            bloco.append(linhas[i].texto)
            i += 1

        if not bloco:
            continue

        # Identificar qual rótulo vem logo após este bloco
        rotulo_seguinte = None
        if i < n:
            if linhas[i].is_rotulo:
                rotulo_seguinte = linhas[i].texto
            elif RE_INDICADOR_TITULO.match(linhas[i].texto):
                rotulo_seguinte = "Ficha de Indicadores"

        # Heurística: associar bloco ao rótulo correto por padrão de conteúdo
        _classificar_bloco(bloco, secoes, rotulo_seguinte)

    return secoes


def _classificar_bloco(
    bloco: list[str],
    secoes: dict[str, list[str]],
    rotulo_hint: str | None,
) -> None:
    """
    Classifica um bloco de linhas nas seções corretas usando:
    1. Rótulo seguinte como dica principal
    2. Padrão de conteúdo como fallback
    """
    texto_bloco = " ".join(bloco)

    # Se o rótulo seguinte é "Descrição do Indicador", "Unidade Gestora", etc.
    # o bloco atual é conteúdo do rótulo SEGUINTE (que aparecerá depois)
    # No template Bizagi, o bloco aparece ANTES do seu rótulo.

    if rotulo_hint in secoes:
        # O conteúdo do bloco pertence ao rótulo que aparece DEPOIS dele.
        # Mas múltiplos rótulos podem seguir o mesmo bloco — dividir por padrão.
        pass

    # Classificação por padrão de conteúdo (independente do rótulo)
    for linha in bloco:
        texto = linha.strip()
        if not texto:
            continue

        # Título do processo (curto, aparece antes dos rótulos "Descrição"/"Procedimentos")
        # Ignorar linhas de controle de versões
        if RE_CONTROLE_VERSOES.search(texto):
            continue

        # Frequência de medição
        if RE_FREQ.match(texto):
            secoes.setdefault("Frequência de medição", []).append(texto)
            continue

        # Responsável
        if RE_RESPONSAVEL.search(texto):
            secoes.setdefault("Responsáveis", []).append(texto)
            continue

        # Meta com percentual
        if RE_META.search(texto):
            secoes.setdefault("Metas", []).append(texto)
            continue

        # Norma/amparo legal
        if RE_NORMA.search(texto) and len(texto) < 200:
            secoes.setdefault("Amparo Legal", []).append(texto)
            continue

        # URL/link
        if RE_URL.search(texto):
            # Incluir também como link preservando a linha completa
            secoes.setdefault("Links", []).append(texto)
            continue

        # Fórmula de cálculo
        if RE_FORMULA.search(texto):
            secoes.setdefault("Fórmula de cálculo", []).append(texto)
            continue

        # Unidade gestora (valor, não o rótulo)
        if rotulo_hint == "Unidade Gestora" or (
            re.match(r"^Secretari[ao]|^Divisão|^Coordenação|^Diretori[ao]|^Seção|^Setor",
                     texto, re.IGNORECASE)
            and ("UFMS" in texto or "/" in texto)
        ):
            secoes.setdefault("Unidade Gestora", []).append(texto)
            continue

        # Conteúdo da seção "Observações Adicionais"
        if rotulo_hint == "Observações Adicionais (recomendações)":
            secoes.setdefault("Observações Adicionais (recomendações)", []).append(texto)
            continue

        # Fonte de dados
        if rotulo_hint == "Fonte / Forma de coleta de dados":
            secoes.setdefault("Fonte / Forma de coleta de dados", []).append(texto)
            continue

        # Descrição do indicador
        if rotulo_hint == "Descrição do Indicador":
            secoes.setdefault("Descrição do Indicador", []).append(texto)
            continue

        # Procedimentos: linhas longas com verbos imperativos ou numerados
        if (
            len(texto) > 30
            and re.match(
                r"^(?:Passo\s+\d+|[A-ZÁÉÍÓÚÃÕÇ][a-záéíóúãõç]{2,}\s)",
                texto,
            )
        ):
            secoes.setdefault("Procedimentos", []).append(texto)
            continue

        # Tudo que sobrar e for parágrafo vai para Descrição
        if len(texto) > 40 and rotulo_hint in ("Descrição", None):
            secoes.setdefault("Descrição", []).append(texto)
            continue

        # Fallback: se tiver um rótulo hint válido, usa ele
        if rotulo_hint and rotulo_hint in secoes:
            secoes[rotulo_hint].append(texto)


# ---------------------------------------------------------------------------
# Extração de título e unidade
# ---------------------------------------------------------------------------

def _extrair_titulo_e_unidade(
    linhas: list[Linha],
    nome_arquivo: str,
    secoes: dict[str, list[str]],
) -> tuple[str, str]:
    """
    Extrai título do processo e unidade responsável.
    - Título: linha(s) curtas que aparecem logo antes do rótulo 'Descrição'
    - Unidade: conteúdo da chave 'Unidade Gestora' ou padrão em texto
    """
    # Título: procurar linhas curtas antes do rótulo "Descrição"
    titulo_partes: list[str] = []
    for i, linha in enumerate(linhas):
        if linha.texto == "Descrição" and linha.is_rotulo:
            # Olhar para trás: pegar apenas linhas CURTAS (≤60 chars) que
            # precedem imediatamente o rótulo "Descrição".
            # O título do processo é sempre curto e aparece logo antes.
            j = i - 1
            candidatos = []
            while j >= 0 and not linhas[j].is_rotulo:
                t = linhas[j].texto
                # Parar se linha longa (conteúdo de seção) ou termina com pontuação
                # (fim de frase = conteúdo, não título)
                if len(t) > 60:
                    break
                if t.endswith((".",";"," ")) or re.search(r"\w\.$", t):
                    break
                if (
                    3 < len(t) <= 60
                    and not RE_NORMA.search(t)
                    and not RE_URL.search(t)
                    and not RE_CONTROLE_VERSOES.search(t)
                ):
                    candidatos.insert(0, t)
                j -= 1
                if len(candidatos) >= 3:
                    break
            titulo_partes = candidatos
            break

    titulo = " ".join(titulo_partes).strip() if titulo_partes else ""
    if not titulo:
        # Fallback: nome do arquivo formatado
        titulo = re.sub(r"[-_]", " ", nome_arquivo).title()

    # Unidade gestora
    unidade_linhas = secoes.get("Unidade Gestora", [])
    if unidade_linhas:
        unidade = unidade_linhas[0].strip().rstrip(".")
    else:
        # Fallback: procurar em todo o texto
        for linha in linhas:
            t = linha.texto
            if re.match(r"^Secretari[ao].{0,120}(?:UFMS|/\w+/\w+)", t, re.IGNORECASE):
                unidade = t.strip().rstrip(".")
                break
        else:
            unidade = "Não identificada"

    return titulo, unidade


# ---------------------------------------------------------------------------
# Extração de procedimentos
# ---------------------------------------------------------------------------

def _extrair_procedimentos(linhas: list[Linha], secoes: dict[str, list[str]]) -> list[str]:
    """
    Extrai procedimentos. Prioriza a classificação por padrão (Passo N, verbos)
    e complementa com linhas longas classificadas na seção Procedimentos.
    Remove duplicatas e linhas de rótulo.
    """
    itens: list[str] = []
    visto: set[str] = set()

    for linha in secoes.get("Procedimentos", []):
        l = linha.strip().rstrip(";")
        if l and l not in visto and l not in ROTULOS_SECAO:
            itens.append(l)
            visto.add(l)

    # Complementar com linhas longas não classificadas que parecem procedimentos
    for linha in linhas:
        t = linha.texto
        if (
            not linha.is_rotulo
            and t not in visto
            and len(t) > 30
            and t not in ROTULOS_SECAO
            and not RE_NORMA.search(t)
            and not RE_URL.search(t)
            and not RE_CONTROLE_VERSOES.search(t)
            and not RE_META.search(t)
            and not RE_FREQ.match(t)
            and re.match(
                r"^(?:Passo\s+\d+|Após|Acessar|Inserir|Gerar|Baixar|Incluir|Atribuir|"
                r"Verificar|Cadastrar|Solicitar|Encaminhar|Informar|Emitir|Salvar|Anexar)",
                t,
                re.IGNORECASE,
            )
        ):
            itens.append(t.rstrip(";"))
            visto.add(t)

    return itens


# ---------------------------------------------------------------------------
# Extração de indicadores
# ---------------------------------------------------------------------------

def _extrair_indicadores(linhas: list[Linha], secoes: dict[str, list[str]]) -> list[IndicadorJSON]:
    """
    Extrai indicadores de desempenho.
    Os títulos são marcados com '__IND__' na lista _indicadores_raw.
    Para cada indicador, coleta fórmula, fonte, frequência e metas.
    """
    indicadores: list[IndicadorJSON] = []

    titulos_raw = [
        s.replace("__IND__", "").strip()
        for s in secoes.get("_indicadores_raw", [])
        if s.startswith("__IND__")
    ]

    if not titulos_raw:
        return indicadores

    formulas    = secoes.get("Fórmula de cálculo", [])
    fontes      = secoes.get("Fonte / Forma de coleta de dados", [])
    frequencias = secoes.get("Frequência de medição", [])
    metas_raw   = secoes.get("Metas", [])
    descricoes  = secoes.get("Descrição do Indicador", [])

    for idx, nome in enumerate(titulos_raw):
        # Fórmula: usar primeira linha que contém a expressão matemática.
        # Não agregar todas as linhas — evita misturar com fonte de dados.
        formula: str | None = None
        for linha in linhas:
            t = linha.texto
            if (
                not linha.is_rotulo
                and RE_FORMULA.search(t)
                and len(t) < 500
                and not RE_CONTROLE_VERSOES.search(t)
            ):
                formula = t.strip()
                break
        # Complementar com linhas da seção "Fórmula de cálculo" se não encontrado
        if not formula and formulas:
            formula = formulas[0].strip() or None

        # Fonte de dados
        fonte: str | None = " ".join(fontes).strip() or None

        # Frequência
        frequencia: str | None = None
        if frequencias:
            frequencia = frequencias[0].rstrip(".")

        # Filtrar metas: excluir linhas de controle de versões
        metas_filtradas = [
            m for m in metas_raw
            if not RE_CONTROLE_VERSOES.search(m)
            and len(m) > 5
        ]

        indicadores.append(IndicadorJSON(
            nome=nome,
            formula=formula,
            fonte_dados=fonte,
            frequencia=frequencia,
            metas=metas_filtradas,
        ))

    return indicadores


# ---------------------------------------------------------------------------
# Extração de links (URLs)
# ---------------------------------------------------------------------------

def _extrair_links(linhas: list[Linha]) -> list[str]:
    """
    Extrai e reconstrói URLs, incluindo URLs quebradas em múltiplas linhas.
    """
    urls: list[str] = []
    buffer_url = ""

    for linha in linhas:
        t = linha.texto
        # Linha contém início de URL
        if "http" in t:
            m = RE_URL.search(t)
            if m:
                url = m.group(0)
                # URL incompleta (termina com hífen ou barra e é curta)
                if url.endswith("-") or (len(url) < 40 and not url.endswith("/")):
                    buffer_url = url
                else:
                    buffer_url = ""
                    if url not in urls:
                        urls.append(url)
        elif buffer_url:
            # Continuação de URL quebrada na linha anterior
            url_completa = buffer_url.rstrip("-") + t.lstrip()
            if url_completa not in urls:
                urls.append(url_completa)
            buffer_url = ""

    return urls


# ---------------------------------------------------------------------------
# Extração de amparo legal
# ---------------------------------------------------------------------------

def _extrair_amparo_legal(linhas: list[Linha], secoes: dict[str, list[str]]) -> list[str]:
    """
    Extrai normas do bloco Amparo Legal e de padrões regex no texto.
    """
    normas: list[str] = []
    visto: set[str] = set()

    for n in secoes.get("Amparo Legal", []):
        n_clean = n.strip().rstrip(";").rstrip(".")
        if n_clean and n_clean not in visto:
            normas.append(n_clean)
            visto.add(n_clean)

    # Complementar via regex sobre todas as linhas
    # Exigir que a norma comece no início da linha (evita falsos positivos em meio de frase)
    RE_NORMA_INICIO = re.compile(
        r"^(?:IN|Instrução Normativa|Lei|Decreto|Portaria|Emenda|Resolução|"
        r"Acórdão|Nota Técnica|Nota Informativa|Medida Provisória|Art\.|Arts\.)",
        re.IGNORECASE,
    )
    for linha in linhas:
        if linha.is_rotulo:
            continue
        t = linha.texto.strip()
        if RE_NORMA_INICIO.match(t) and RE_NORMA.search(t):
            norma = t.rstrip(";").rstrip(".")
            if norma and norma not in visto and len(norma) < 200:
                normas.append(norma)
                visto.add(norma)

    return normas


# ---------------------------------------------------------------------------
# Extração de responsáveis e metas
# ---------------------------------------------------------------------------

def _extrair_responsaveis(secoes: dict[str, list[str]]) -> list[str]:
    resp: list[str] = []
    visto: set[str] = set()
    for r in secoes.get("Responsáveis", []):
        r_clean = r.strip().rstrip(".")
        if r_clean and r_clean not in visto and not RE_CONTROLE_VERSOES.search(r_clean):
            resp.append(r_clean)
            visto.add(r_clean)
    return resp


def _extrair_metas(secoes: dict[str, list[str]]) -> list[str]:
    metas: list[str] = []
    visto: set[str] = set()
    for m in secoes.get("Metas", []):
        m_clean = m.strip()
        if (
            m_clean
            and m_clean not in visto
            and not RE_CONTROLE_VERSOES.search(m_clean)
            and len(m_clean) > 8
        ):
            metas.append(m_clean)
            visto.add(m_clean)
    return metas


def _extrair_descricao(secoes: dict[str, list[str]], linhas: list[Linha]) -> str:
    """
    Extrai a descrição geral: parágrafo(s) iniciais do documento.
    Usa as linhas classificadas em 'Descrição' e complementa com
    as primeiras linhas longas do documento.
    """
    partes = secoes.get("Descrição", [])
    if partes:
        return " ".join(partes)[:2000]

    # Fallback: primeiras linhas longas não classificadas como norma/url/meta
    fallback: list[str] = []
    for linha in linhas[:30]:
        t = linha.texto
        if (
            not linha.is_rotulo
            and len(t) > 40
            and not RE_NORMA.search(t)
            and not RE_URL.search(t)
            and not RE_CONTROLE_VERSOES.search(t)
            and not RE_META.search(t)
        ):
            fallback.append(t)
        if len(fallback) >= 5:
            break
    return " ".join(fallback)[:2000]


def _extrair_observacoes(secoes: dict[str, list[str]]) -> str | None:
    obs = secoes.get("Observações Adicionais (recomendações)", []) or \
          secoes.get("Observações Adicionais", [])
    return " ".join(obs).strip() or None


# ---------------------------------------------------------------------------
# Função principal de extração
# ---------------------------------------------------------------------------

def extrair_pdf(caminho_pdf: str | Path) -> tuple[DocumentoPDFJSON, list[str]]:
    """
    Lê um arquivo PDF com PyMuPDF e retorna (DocumentoPDFJSON, lista_de_avisos).

    Extrai e estrutura: título, unidade responsável, descrição, procedimentos,
    amparo legal, links, indicadores (com fórmula, fonte, frequência, metas),
    metas gerais, responsáveis e observações.

    Preserva títulos e seções usando o mapeamento reverso do template Bizagi
    (rótulo aparece DEPOIS do conteúdo). Registra warnings para páginas
    vazias (seção 8.2).
    """
    caminho = Path(caminho_pdf)
    avisos: list[str] = []

    linhas, avisos_pdf = _extrair_linhas(str(caminho))
    avisos.extend(avisos_pdf)

    if not linhas:
        raise ValueError("Nenhum texto pôde ser extraído do PDF.")

    # Mapear seções pelo template Bizagi
    secoes = _mapear_secoes(linhas)

    # Extrair cada campo
    titulo, unidade = _extrair_titulo_e_unidade(linhas, caminho.stem, secoes)
    descricao       = _extrair_descricao(secoes, linhas)
    procedimentos   = _extrair_procedimentos(linhas, secoes)
    amparo_legal    = _extrair_amparo_legal(linhas, secoes)
    links           = _extrair_links(linhas)
    indicadores     = _extrair_indicadores(linhas, secoes)
    metas           = _extrair_metas(secoes)
    responsaveis    = _extrair_responsaveis(secoes)
    observacoes     = _extrair_observacoes(secoes)

    # Warnings de campos vazios relevantes (seção 8.2)
    if not procedimentos:
        avisos.append("PDF: nenhum procedimento identificado.")
    if not amparo_legal:
        avisos.append("PDF: nenhum amparo legal identificado.")
    if not indicadores:
        avisos.append("PDF: nenhum indicador de desempenho identificado.")

    logger.debug(
        "extract_pdf: titulo=%s | unidade=%s | procedimentos=%d | normas=%d | indicadores=%d",
        titulo, unidade, len(procedimentos), len(amparo_legal), len(indicadores),
    )
    logger.debug("extract_pdf: links=%s", links)
    documento = DocumentoPDFJSON(
        titulo=titulo,
        unidade_responsavel=unidade,
        descricao=descricao,
        procedimentos=procedimentos,
        amparo_legal=amparo_legal,
        links=links,
        indicadores=indicadores,
        metas=metas,
        responsaveis=responsaveis,
        observacoes=observacoes,
    )

    return documento, avisos


# ---------------------------------------------------------------------------
# Nó do LangGraph
# ---------------------------------------------------------------------------

def extract_pdf_to_json(estado: EstadoGrafo) -> EstadoGrafo:
    """
    Nó LangGraph: extrai o PDF descritivo e popula estado.documento_pdf_json.
    Salva intermediário em /saidas/intermediarios/pdf_estruturado.json
    conforme exigido pela seção 7.1 (passo 6) do documento da sprint.
    """
    caminho = estado.caminho_pdf
    if not caminho:
        estado.erros.append("extract_pdf_to_json: caminho_pdf não definido no estado.")
        return estado

    if not os.path.isfile(caminho):
        estado.erros.append(f"extract_pdf_to_json: arquivo não encontrado — {caminho}")
        return estado

    try:
        documento, avisos = extrair_pdf(caminho)
    except ValueError as exc:
        estado.erros.append(f"extract_pdf_to_json: erro de extração — {exc}")
        return estado
    except Exception as exc:
        estado.erros.append(f"extract_pdf_to_json: erro inesperado — {exc}")
        return estado

    estado.avisos.extend(avisos)

    # Salvar intermediário (Entrega 2 / JSON) — run-scoped via config
    saida_dir = config.garantir(config.pasta_intermediarios(estado.run_id, config.JSON))
    saida_path = saida_dir / "pdf_estruturado.json"

    try:
        with open(saida_path, "w", encoding="utf-8") as f:
            json.dump(documento.model_dump(), f, ensure_ascii=False, indent=2)
        estado.artefatos["pdf_estruturado"] = str(saida_path)
        logger.info("pdf_estruturado.json salvo em %s", saida_path)
    except OSError as exc:
        estado.avisos.append(
            f"extract_pdf_to_json: não foi possível salvar intermediário — {exc}"
        )

    estado.documento_pdf_json = documento
    return estado

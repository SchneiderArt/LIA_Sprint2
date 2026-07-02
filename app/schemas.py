"""
Schemas Pydantic v2 da Sprint 2 - Entrega 2
Definidos conforme o documento de especificação da sprint:
  - ProcessoJSON
  - NodeJSON
  - EdgeJSON
  - DocumentoPDFJSON
  - AutomationCandidateJSON

Usados para validar entradas, intermediários e saídas do LLM.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerações auxiliares
# ---------------------------------------------------------------------------


class TipoNo(str, Enum):
    """Tipos possíveis de nó em um fluxo BPMN 2.0."""

    ATIVIDADE = "atividade"
    EVENTO_INICIO = "evento_inicio"
    EVENTO_FIM = "evento_fim"
    EVENTO_INTERMEDIARIO = "evento_intermediario"
    GATEWAY = "gateway"
    SUBPROCESSO = "subprocesso"
    CHAMADA = "chamada"
    OBJETO_DADO = "objeto_dado"


class TipoGateway(str, Enum):
    """Tipos de gateway BPMN."""

    EXCLUSIVO = "exclusivo"       # XOR
    PARALELO = "paralelo"         # AND
    INCLUSIVO = "inclusivo"       # OR
    BASEADO_EVENTO = "baseado_evento"
    COMPLEXO = "complexo"


class TipoAutomacao(str, Enum):
    """
    Tipos de automação conforme definido na seção 5 do documento da sprint.
    """

    RPA = "RPA"
    AGENTE_IA = "Agente de IA"
    HIBRIDA = "Híbrida"
    API_INTEGRACAO = "API/Integração"


class Prioridade(str, Enum):
    """Prioridades possíveis para uma automação candidata (seção 9.1)."""

    BAIXA = "baixa"
    MEDIA = "média"
    ALTA = "alta"
    MUITO_ALTA = "muito alta"


# ---------------------------------------------------------------------------
# NodeJSON
# Campos mínimos conforme seção 7.1 do documento da sprint.
# ---------------------------------------------------------------------------


class NodeJSON(BaseModel):
    """
    Representa um nó do processo BPMN.
    Campos mínimos obrigatórios: id, tipo, nome, lane,
    documentos_relacionados, entradas, saidas, observacoes.
    """

    id: str = Field(
        description="Identificador único do nó, conforme definido no BPMN."
    )
    tipo: TipoNo = Field(
        description="Tipo do nó: atividade, gateway, evento, etc."
    )
    nome: str = Field(
        description="Nome legível do nó, extraído do atributo 'name' do BPMN."
    )
    lane: Optional[str] = Field(
        default=None,
        description="Nome da raia (lane/pool) à qual o nó pertence."
    )
    documentos_relacionados: list[str] = Field(
        default_factory=list,
        description="IDs ou nomes de dataObjects/dataObjectReferences associados ao nó."
    )
    entradas: list[str] = Field(
        default_factory=list,
        description="IDs dos nós de origem que enviam fluxo para este nó."
    )
    saidas: list[str] = Field(
        default_factory=list,
        description="IDs dos nós de destino que recebem fluxo deste nó."
    )
    observacoes: Optional[str] = Field(
        default=None,
        description="Informações adicionais relevantes extraídas do BPMN ou inferidas."
    )


# ---------------------------------------------------------------------------
# EdgeJSON
# Campos mínimos conforme seção 7.1 do documento da sprint.
# ---------------------------------------------------------------------------


class EdgeJSON(BaseModel):
    """
    Representa uma aresta de sequência (sequenceFlow) do BPMN.
    Campos mínimos obrigatórios: id, source, target, label, condicao.
    """

    id: str = Field(
        description="Identificador único da aresta, conforme o BPMN."
    )
    source: str = Field(
        description="ID do nó de origem do fluxo."
    )
    target: str = Field(
        description="ID do nó de destino do fluxo."
    )
    label: Optional[str] = Field(
        default=None,
        description="Rótulo visível na aresta, se houver (ex: 'Sim', 'Não', 'Correto')."
    )
    condicao: Optional[str] = Field(
        default=None,
        description="Expressão ou descrição da condição de disparo do fluxo, quando aplicável."
    )


# ---------------------------------------------------------------------------
# ProcessoJSON
# Campos mínimos conforme seção 7.1 do documento da sprint.
# ---------------------------------------------------------------------------


class ProcessoJSON(BaseModel):
    """
    Representação estruturada completa de um processo BPMN.
    Campos mínimos obrigatórios: process_id, nome, origem_arquivo,
    lanes, nodes, edges, data_objects, gateways,
    loops_detectados, atividades_ordenadas.
    """

    process_id: str = Field(
        description="ID do processo conforme definido no elemento <process> do BPMN."
    )
    nome: str = Field(
        description="Nome legível do processo."
    )
    origem_arquivo: str = Field(
        description="Nome ou caminho do arquivo .bpmn de origem."
    )
    lanes: list[str] = Field(
        default_factory=list,
        description="Nomes de todas as raias (lanes/pools) identificadas no processo."
    )
    nodes: list[NodeJSON] = Field(
        default_factory=list,
        description="Lista de todos os nós do processo (atividades, eventos, gateways)."
    )
    edges: list[EdgeJSON] = Field(
        default_factory=list,
        description="Lista de todas as arestas de sequência do processo."
    )
    data_objects: list[str] = Field(
        default_factory=list,
        description="Nomes ou IDs dos objetos de dados (dataObject / dataObjectReference) presentes no BPMN."
    )
    gateways: list[dict] = Field(
        default_factory=list,
        description=(
            "Lista de gateways identificados. Cada item contém ao menos: "
            "id, tipo (TipoGateway), nome e as condições de saída."
        )
    )
    loops_detectados: list[list[str]] = Field(
        default_factory=list,
        description=(
            "Ciclos detectados no grafo do processo via networkx. "
            "Cada item é uma lista de IDs de nós que formam o ciclo."
        )
    )
    atividades_ordenadas: list[str] = Field(
        default_factory=list,
        description=(
            "IDs das atividades em ordem topológica de execução, "
            "calculada via networkx. Vazia se houver ciclos que impeçam ordenação completa."
        )
    )


# ---------------------------------------------------------------------------
# DocumentoPDFJSON
# Campos mínimos conforme seção 7.1 do documento da sprint.
# ---------------------------------------------------------------------------


class IndicadorJSON(BaseModel):
    """Sub-schema para indicadores extraídos do PDF descritivo do processo."""

    nome: str = Field(description="Nome do indicador.")
    formula: Optional[str] = Field(
        default=None,
        description="Fórmula de cálculo do indicador, quando presente no PDF."
    )
    fonte_dados: Optional[str] = Field(
        default=None,
        description="Sistema ou fonte de onde os dados do indicador são obtidos."
    )
    frequencia: Optional[str] = Field(
        default=None,
        description="Periodicidade de apuração do indicador (ex: trimestral, mensal)."
    )
    metas: list[str] = Field(
        default_factory=list,
        description="Metas numéricas ou textuais associadas ao indicador."
    )


class DocumentoPDFJSON(BaseModel):
    """
    Representação estruturada do descritivo do processo extraído do PDF.
    Campos mínimos obrigatórios: titulo, unidade_responsavel, descricao,
    procedimentos, amparo_legal, links, indicadores, metas,
    responsaveis, observacoes.
    """

    titulo: str = Field(
        description="Título do documento ou do processo descrito no PDF."
    )
    unidade_responsavel: str = Field(
        description="Unidade gestora responsável pelo processo (ex: SEAL/DIFC/PROPLAN)."
    )
    descricao: str = Field(
        description="Descrição geral e finalidade do processo conforme o PDF."
    )
    procedimentos: list[str] = Field(
        default_factory=list,
        description="Lista de procedimentos descritos no documento."
    )
    amparo_legal: list[str] = Field(
        default_factory=list,
        description="Normas, leis, instruções normativas e demais bases legais mencionadas."
    )
    links: list[str] = Field(
        default_factory=list,
        description="URLs ou referências a sistemas externos mencionados no PDF."
    )
    indicadores: list[IndicadorJSON] = Field(
        default_factory=list,
        description="Indicadores de desempenho do processo extraídos do PDF."
    )
    metas: list[str] = Field(
        default_factory=list,
        description="Metas gerais do processo mencionadas no PDF (além das vinculadas a indicadores específicos)."
    )
    responsaveis: list[str] = Field(
        default_factory=list,
        description="Nomes, cargos ou unidades identificados como responsáveis por etapas do processo."
    )
    observacoes: Optional[str] = Field(
        default=None,
        description="Informações adicionais relevantes extraídas do PDF que não se encaixam nos campos acima."
    )


# ---------------------------------------------------------------------------
# AutomationCandidateJSON
# Campos mínimos conforme seção 7.1 e campos obrigatórios da seção 9.1.
# ---------------------------------------------------------------------------


class AutomationCandidateJSON(BaseModel):
    """
    Proposta de automação candidata identificada pelo agente.
    Campos mínimos (seção 7.1): id, nome, atividades_envolvidas,
    tipo_automacao, proposta, justificativa, beneficios, impactos,
    riscos, metricas, prioridade.

    Campos adicionais obrigatórios pela seção 9.1: gatilho, entradas,
    saidas, como_automatizar, beneficios_administrativos,
    impactos_gestao, riscos_dependencias, metrica_sucesso.
    """

    id: str = Field(
        description="Identificador único da automação (ex: 'AUT-001')."
    )
    nome: str = Field(
        description="Nome claro e descritivo da automação candidata."
    )
    atividades_envolvidas: list[str] = Field(
        description=(
            "Uma ou mais atividades do BPMN cobertas por esta automação. "
            "Usar os nomes das atividades conforme aparecem no BPMN."
        )
    )
    tipo_automacao: TipoAutomacao = Field(
        description="Classificação da automação: RPA, Agente de IA, Híbrida ou API/Integração."
    )
    proposta: str = Field(
        description="Descrição concreta do que a automação faz."
    )
    justificativa: str = Field(
        description=(
            "Por que a automação é válida, com base no que foi identificado "
            "no BPMN e no PDF descritivo do processo."
        )
    )
    beneficios: list[str] = Field(
        description="Lista de benefícios esperados da automação."
    )
    impactos: list[str] = Field(
        description="Efeitos esperados na gestão, indicadores e governança."
    )
    riscos: list[str] = Field(
        description=(
            "Dependências técnicas, riscos operacionais, jurídicos ou de qualidade "
            "que podem afetar a implementação."
        )
    )
    metricas: list[str] = Field(
        description="Indicadores possíveis para medir se a automação trouxe resultado."
    )
    prioridade: Prioridade = Field(
        description="Prioridade sugerida: baixa, média, alta ou muito alta."
    )
    justificativa_prioridade: str = Field(
        description="Justificativa curta para a prioridade atribuída."
    )

    # Campos adicionais obrigatórios pela seção 9.1 do documento
    gatilho: str = Field(
        description=(
            "Evento que inicia a automação: chegada de processo, upload, "
            "alteração de status, demanda periódica, etc."
        )
    )
    entradas: list[str] = Field(
        description=(
            "Documentos, campos, sistemas, dados ou decisões necessários "
            "para que a automação seja executada."
        )
    )
    saidas: list[str] = Field(
        description=(
            "Artefatos produzidos pela automação: relatório, checklist, guia, "
            "parecer, alerta, registro, atualização ou arquivo anexado."
        )
    )
    como_automatizar: str = Field(
        description=(
            "Passo a passo técnico em alto nível de como a automação seria implementada, "
            "sem depender de credenciais reais."
        )
    )


# ---------------------------------------------------------------------------
# Schemas de entrada da API (seção 8 do documento)
# ---------------------------------------------------------------------------


class RunStatus(str, Enum):
    """Status possíveis de uma execução da API."""

    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class RunMetadata(BaseModel):
    """
    Metadados retornados pela API após o POST em /analisar-processo
    e consultados em GET /runs/{run_id}.
    Conforme seção 8.1 do documento da sprint.
    """

    run_id: str = Field(description="Identificador único da execução.")
    status: RunStatus = Field(description="Status atual da execução.")
    pipeline: str = Field(
        description="Abordagem executada: 'natural', 'json' ou 'both'."
    )
    avisos: list[str] = Field(
        default_factory=list,
        description="Warnings registrados durante o processamento (ex: PDF com texto ruim)."
    )
    erros: list[str] = Field(
        default_factory=list,
        description="Erros encontrados durante a execução, se houver."
    )
    quantidade_automacoes: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Quantidade de automações encontradas por abordagem. "
            "Ex: {'json': 4} ou {'natural': 3, 'json': 4} no modo 'both'."
        )
    )
    artefatos: dict[str, str] = Field(
        default_factory=dict,
        description="Caminhos ou links para os artefatos gerados (documento final, JSON de auditoria, intermediários)."
    )


# ---------------------------------------------------------------------------
# Schema do estado do grafo LangGraph (usado em graph.py)
# ---------------------------------------------------------------------------


class EstadoGrafo(BaseModel):
    """
    Estado tipado do grafo LangGraph para a Entrega 2.
    Cada nó lê e escreve campos deste estado.
    """

    run_id: str = Field(description="ID da execução corrente.")

    # Prefixo usado pelo render_outputs para nomear os artefatos de saída.
    # Em modo "both", cada grafo usa um prefixo diferente para não sobrescrever.
    nome_saida: str = Field(default="documento_final")

    # Caminhos dos arquivos de entrada
    caminho_bpmn: Optional[str] = Field(default=None)
    caminho_pdf: Optional[str] = Field(default=None)

    # Intermediários da Entrega 2
    processo_json: Optional[ProcessoJSON] = Field(default=None)
    documento_pdf_json: Optional[DocumentoPDFJSON] = Field(default=None)

    # Intermediários da Entrega 1
    bpmn_normalizado_xml: Optional[str] = Field(default=None)
    pdf_texto_extraido: Optional[str] = Field(default=None)
    narrativa_bpmn: Optional[str] = Field(default=None)
    prompt_usado_natural: Optional[str] = Field(default=None)

    # Prompt montado para o LLM
    prompt_usado: Optional[str] = Field(default=None)

    # Saída do LLM antes e depois da validação
    candidatos_raw: Optional[str] = Field(
        default=None,
        description="Saída bruta do LLM antes da validação Pydantic."
    )
    candidatos: list[AutomationCandidateJSON] = Field(
        default_factory=list,
        description="Automações candidatas validadas. No modo both: natural primeiro, json depois."
    )
    # Preenchidos apenas no modo 'both', para a API contar automações por abordagem.
    candidatos_json: list[AutomationCandidateJSON] = Field(
        default_factory=list,
        description="Automações da Entrega 2 (JSON) — usado no modo both."
    )
    candidatos_natural: list[AutomationCandidateJSON] = Field(
        default_factory=list,
        description="Automações da Entrega 1 (natural) — usado no modo both."
    )

    # Controle de validação e reparo
    erros_validacao: list[str] = Field(
        default_factory=list,
        description="Erros de schema retornados pelo Pydantic, usados no nó de reparo."
    )
    tentativas_reparo: int = Field(
        default=0,
        description="Contador de tentativas de reparo para evitar loop infinito."
    )

    # Avisos e erros gerais
    avisos: list[str] = Field(default_factory=list)
    erros: list[str] = Field(default_factory=list)

    # Caminhos dos artefatos gerados
    artefatos: dict[str, str] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

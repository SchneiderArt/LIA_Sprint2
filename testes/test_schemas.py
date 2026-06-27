import pytest
from pydantic import ValidationError
from app.schemas.modelos import AutomacaoCandidataJSON, DocumentoAutomacoes


def test_automacao_candidata_valida():
    dados = {
        "id": "AUT-001",
        "nome": "Triagem documental",
        "atividades_envolvidas": ["Analisar documentação"],
        "tipo_automacao": "Híbrida",
        "gatilho": "Chegada de processo no SEI",
        "entradas": ["Processo SEI", "Nota fiscal"],
        "saidas": ["Checklist de conformidade"],
        "como_automatizar": "Agente de IA verifica campos obrigatórios",
        "justificativa": "Atividade manual e repetitiva",
        "beneficios": ["Redução de retrabalho"],
        "impactos": ["Melhora rastreabilidade"],
        "riscos": ["Qualidade do OCR"],
        "metrica_de_sucesso": "% de processos sem erro na primeira análise",
        "prioridade": "Alta",
        "prioridade_justificativa": "Alto volume diário",
    }
    a = AutomacaoCandidataJSON(**dados)
    assert a.id == "AUT-001"
    assert a.tipo_automacao == "Híbrida"


def test_tipo_automacao_invalido():
    with pytest.raises(ValidationError):
        AutomacaoCandidataJSON(
            id="AUT-001",
            nome="Teste",
            atividades_envolvidas=[],
            tipo_automacao="Robô",  # inválido
            gatilho="",
            entradas=[],
            saidas=[],
            como_automatizar="",
            justificativa="",
            beneficios=[],
            impactos=[],
            riscos=[],
            metrica_de_sucesso="",
            prioridade="Alta",
            prioridade_justificativa="",
        )

# Prompt — Geração de Automações Candidatas

## Instrução

Você receberá dois JSONs estruturados de um processo institucional:

1. **ProcessoJSON**: representação estruturada do fluxo BPMN (raias, atividades, gateways, documentos, fluxos).
2. **DocumentoPDFJSON**: representação estruturada do descritivo do processo (finalidade, procedimentos, normas, indicadores, metas, responsáveis).

Sua tarefa é analisar esses dois insumos em conjunto e identificar **todas as oportunidades reais de automação** presentes no processo. Para cada oportunidade, gere um objeto `AutomationCandidateJSON` completo.

## Schema obrigatório de saída

Responda **somente** com um array JSON válido de objetos `AutomationCandidateJSON`, sem texto antes ou depois, sem blocos de código markdown, sem comentários. Cada objeto deve ter exatamente esta estrutura:

```
[
  {
    "id": "AUT-001",
    "nome": "string — nome claro e descritivo da automação",
    "atividades_envolvidas": ["string — nomes das atividades do BPMN cobertas por esta automação"],
    "tipo_automacao": "RPA | Agente de IA | Híbrida | API/Integração",
    "proposta": "string — descrição concreta do que a automação executa",
    "justificativa": "string — por que esta automação é válida com base no BPMN e no PDF",
    "beneficios": ["string — cada benefício esperado"],
    "impactos": ["string — cada efeito esperado em indicadores, governança ou qualidade"],
    "riscos": ["string — cada dependência técnica, risco operacional, jurídico ou de qualidade"],
    "metricas": ["string — cada indicador para medir se a automação trouxe resultado"],
    "prioridade": "baixa | média | alta | muito alta",
    "justificativa_prioridade": "string — justificativa curta para a prioridade",
    "gatilho": "string — evento que inicia a automação",
    "entradas": ["string — cada documento, campo, sistema ou dado necessário"],
    "saidas": ["string — cada artefato produzido pela automação"],
    "como_automatizar": "string — passo a passo técnico em alto nível"
  }
]
```

## Tipos de automação — quando usar cada um

| Tipo | Critério de aplicação | Exemplos |
|------|----------------------|---------|
| **RPA** | Tarefa repetitiva, determinística, baseada em cliques, formulários, consultas web ou sistemas sem API clara | Consultar página, baixar documento, preencher formulário, emitir guia em site estável, anexar arquivo |
| **Agente de IA** | Tarefa que exige interpretação textual, classificação, extração de regras, comparação de documentos, geração de parecer ou análise de conformidade | Analisar conformidade documental, resumir processo, classificar tipo de erro, redigir relatório |
| **Híbrida** | Combinação de coleta/execução mecânica (RPA) com julgamento textual ou geração de conteúdo (IA) | RPA coleta documentos e agente avalia inconsistências; agente calcula proposta e RPA anexa relatório |
| **API/Integração** | Sistema de origem possui API oficial, exportação estruturada ou integração segura disponível | Buscar dados em endpoint, consumir planilha institucional, consultar cadastro por serviço autorizado |

## Regras de geração de candidatas

### Regras de separação (seção 9.2 do documento)
- **Não agrupe** automações diferentes apenas porque aparecem no mesmo processo.
- **Agrupe** atividades somente quando houver dependência operacional clara entre elas no fluxo BPMN.
- **Gere automação separada** quando houver mudança de sistema, mudança de natureza da tarefa (ex: de coleta para análise) ou mudança de benefício esperado.
- **Prefira separar** e justificar a relação quando houver dúvida.
- **Explicite** sempre se uma automação depende de outra ou pode ser implementada isoladamente.

### Regras de qualidade
- Use **nomes reais das atividades** do BPMN em `atividades_envolvidas` — nunca parafrasear.
- A `justificativa` deve referenciar explicitamente elementos do BPMN (atividade, gateway, documento) E do PDF (procedimento, norma, indicador ou meta).
- O `gatilho` deve ser específico: "chegada de processo no SEI", "upload de arquivo pelo usuário", "alteração de status no SIAPE", "demanda periódica trimestral", etc.
- As `entradas` devem listar sistemas, documentos e campos reais mencionados no BPMN ou PDF.
- As `saidas` devem ser artefatos concretos: checklist, relatório, guia de recolhimento, parecer, alerta, atualização de registro.
- O `como_automatizar` deve ter ao menos 3 passos técnicos em alto nível. Não mencionar credenciais reais.
- Os `beneficios` e `impactos` devem ser específicos ao processo — não genéricos como "reduz tempo" sem contexto.
- Os `riscos` devem mencionar dependências reais: MFA, sistemas legados sem API, qualidade documental variável, necessidade de validação humana, risco jurídico.
- A `metrica` deve ser mensurável e relacionada ao indicador do PDF quando existir.
- A `prioridade` deve considerar: volume de ocorrências, grau de repetitividade, impacto em indicadores e complexidade de implementação.

### Cobertura mínima esperada
- Analise **cada atividade** do BPMN individualmente antes de agrupar.
- Analise **cada gateway** para identificar oportunidades de automação de decisão.
- Analise **cada objeto de dados** para identificar automação de coleta ou geração.
- Analise **os indicadores do PDF** para identificar automação de mensuração e relatório.
- Analise **o amparo legal** para identificar automação de verificação de conformidade.

## Entrada que você receberá

```
[PROCESSO_JSON]
{conteúdo do ProcessoJSON}
[/PROCESSO_JSON]

[DOCUMENTO_PDF_JSON]
{conteúdo do DocumentoPDFJSON}
[/DOCUMENTO_PDF_JSON]
```

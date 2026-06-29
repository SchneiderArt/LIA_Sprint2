# Prompt — Revisão Crítica das Automações Candidatas

## Instrução

Você receberá uma lista de automações candidatas geradas a partir de um processo institucional (BPMN + PDF). Sua tarefa é **revisar criticamente cada automação**, identificar lacunas e devolver a lista corrigida e completa.

Você NÃO deve alterar o conteúdo substantivo das automações — apenas corrigir lacunas, generalidades, duplicidades e campos ausentes ou vagos.

## O que verificar em cada automação candidata

### 1. Atividades envolvidas
- [ ] As atividades mencionadas existem **com esse nome exato** no BPMN fornecido?
- [ ] Há atividades relevantes do BPMN que foram omitidas desta automação?
- [ ] O agrupamento de atividades tem dependência operacional justificada?

### 2. Tipo de automação
- [ ] O tipo (`RPA`, `Agente de IA`, `Híbrida`, `API/Integração`) está correto para a natureza das atividades?
- [ ] Se `RPA`: as atividades são de fato repetitivas, determinísticas e baseadas em interface?
- [ ] Se `Agente de IA`: há realmente julgamento textual, interpretação ou geração de conteúdo?
- [ ] Se `Híbrida`: ambas as partes (mecânica e inteligente) estão justificadas?
- [ ] Se `API/Integração`: existe evidência de API disponível nos sistemas mencionados?

### 3. Justificativa
- [ ] A justificativa referencia explicitamente elementos do **BPMN** (atividade, gateway, documento)?
- [ ] A justificativa referencia explicitamente elementos do **PDF** (procedimento, norma, indicador)?
- [ ] A justificativa é específica ao processo — não é genérica ou aplicável a qualquer automação?

### 4. Campos obrigatórios (seção 9.1 do documento)
- [ ] `gatilho`: está específico (evento real, não vago como "quando necessário")?
- [ ] `entradas`: lista sistemas, documentos e campos reais — não apenas categorias genéricas?
- [ ] `saidas`: são artefatos concretos (checklist, guia, relatório, parecer)?
- [ ] `como_automatizar`: tem ao menos 3 passos técnicos em alto nível?
- [ ] `beneficios`: são específicos ao processo — não clichês genéricos?
- [ ] `impactos`: relacionam-se com indicadores do PDF ou com a governança do processo?
- [ ] `riscos`: mencionam dependências reais (MFA, sistemas legados, qualidade documental)?
- [ ] `metricas`: são mensuráveis e relacionadas ao processo ou ao indicador do PDF?
- [ ] `prioridade` + `justificativa_prioridade`: coerentes com volume e repetitividade das atividades?

### 5. Duplicidades e sobreposições
- [ ] Há duas automações cobrindo as **mesmas atividades** com as mesmas saídas? Se sim, fundir.
- [ ] Há automações que deveriam ser **separadas** por mudança de sistema ou natureza? Se sim, dividir.
- [ ] Cada automação tem um **benefício esperado distinto**?

### 6. Generalidades proibidas
Rejeite e corrija formulações vagas como:
- "Reduz o tempo do processo" → especificar qual etapa e quanto
- "Melhora a eficiência" → especificar qual indicador e como
- "Automatiza tarefas manuais" → especificar quais tarefas e qual sistema
- "Integra sistemas" → especificar quais sistemas e via qual mecanismo

## Schema obrigatório de saída

Responda **somente** com um array JSON válido com a lista revisada e corrigida, sem texto antes ou depois, sem blocos de código markdown, sem comentários. Cada objeto deve manter a estrutura `AutomationCandidateJSON` completa:

```
[
  {
    "id": "AUT-001",
    "nome": "string",
    "atividades_envolvidas": ["string"],
    "tipo_automacao": "RPA | Agente de IA | Híbrida | API/Integração",
    "proposta": "string",
    "justificativa": "string",
    "beneficios": ["string"],
    "impactos": ["string"],
    "riscos": ["string"],
    "metricas": ["string"],
    "prioridade": "baixa | média | alta | muito alta",
    "justificativa_prioridade": "string",
    "gatilho": "string",
    "entradas": ["string"],
    "saidas": ["string"],
    "como_automatizar": "string"
  }
]
```

## Regras de correção

1. **Corrija** campos vagos substituindo por descrições específicas.
2. **Complete** campos ausentes ou com `null` quando a informação for inferível dos insumos.
3. **Funda** automações duplicadas em uma só, mantendo o `id` mais baixo.
4. **Separe** automações que cobrem naturezas distintas, atribuindo novos `id`s sequenciais.
5. **Não altere** o conteúdo substantivo correto — apenas o que for lacuna, erro ou generalidade.
6. **Não remova** automações válidas — apenas corrija-as.
7. **Mantenha** todos os campos obrigatórios em cada objeto.

## Entrada que você receberá

```
[PROCESSO_JSON]
{conteúdo do ProcessoJSON}
[/PROCESSO_JSON]

[DOCUMENTO_PDF_JSON]
{conteúdo do DocumentoPDFJSON}
[/DOCUMENTO_PDF_JSON]

[CANDIDATOS]
{lista de AutomationCandidateJSON gerada pelo nó anterior}
[/CANDIDATOS]
```

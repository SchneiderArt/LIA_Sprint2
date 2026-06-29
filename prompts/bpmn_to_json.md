# Prompt — Conversão de BPMN para JSON Estruturado (Entrega 2)

## Instrução

Você receberá o texto extraído de um arquivo BPMN 2.0 de um processo institucional. Sua tarefa é estruturar essas informações em um JSON válido seguindo **exatamente** o schema `ProcessoJSON` definido abaixo.

## Schema obrigatório de saída

Responda **somente** com um objeto JSON válido, sem texto antes ou depois, sem blocos de código markdown, sem comentários. O JSON deve seguir esta estrutura:

```
{
  "process_id": "string — ID do processo conforme atributo id do elemento <process>",
  "nome": "string — nome legível do processo",
  "origem_arquivo": "string — nome do arquivo .bpmn de origem",
  "lanes": ["string — nomes de todas as raias identificadas"],
  "nodes": [
    {
      "id": "string — ID do nó",
      "tipo": "atividade | evento_inicio | evento_fim | evento_intermediario | gateway | subprocesso | chamada | objeto_dado",
      "nome": "string — nome legível do nó",
      "lane": "string ou null — nome da raia à qual o nó pertence",
      "documentos_relacionados": ["string — nomes de dataObjects associados"],
      "entradas": ["string — IDs dos nós de origem"],
      "saidas": ["string — IDs dos nós de destino"],
      "observacoes": "string ou null"
    }
  ],
  "edges": [
    {
      "id": "string — ID da aresta",
      "source": "string — ID do nó de origem",
      "target": "string — ID do nó de destino",
      "label": "string ou null — rótulo visível",
      "condicao": "string ou null — condição de disparo"
    }
  ],
  "data_objects": ["string — nomes dos objetos de dados"],
  "gateways": [
    {
      "id": "string",
      "tipo": "exclusivo | paralelo | inclusivo | baseado_evento | complexo",
      "nome": "string",
      "condicoes_saida": ["string — rótulos das arestas de saída"]
    }
  ],
  "loops_detectados": [["string — IDs dos nós que formam o ciclo"]],
  "atividades_ordenadas": ["string — IDs das atividades em ordem topológica"]
}
```

## Regras de preenchimento

1. **process_id**: usar o valor do atributo `id` do elemento `<process>` principal (o que contém as atividades reais, não o processo vazio de colaboração).
2. **lanes**: extrair os nomes de todos os elementos `<lane>` dentro dos `<laneSet>`.
3. **nodes**: incluir atividades (`<task>` e variantes), eventos (`<startEvent>`, `<endEvent>`, intermediários) e gateways. Excluir elementos puramente visuais (`BPMNShape`, `Bounds`, etc.).
4. **tipo do nó**: mapear conforme o nome da tag XML: `task`/`userTask`/`serviceTask` → `atividade`; `startEvent` → `evento_inicio`; `endEvent` → `evento_fim`; `exclusiveGateway`/`inclusiveGateway`/`parallelGateway` → `gateway`; `dataObject`/`dataObjectReference` → `objeto_dado`.
5. **edges**: extrair todos os `<sequenceFlow>`. O `label` é o atributo `name` do fluxo; a `condicao` é o conteúdo de `<conditionExpression>` ou o rótulo quando não houver expressão formal.
6. **loops_detectados**: listar ciclos encontrados no grafo dirigido formado pelas edges. Deixar lista vazia se não houver ciclos.
7. **atividades_ordenadas**: ordem topológica das atividades. Deixar lista vazia se houver ciclos que impeçam ordenação completa.
8. Campos desconhecidos ou não inferíveis: usar `null` para strings opcionais e `[]` para listas opcionais.

## O que NÃO fazer

- Não inventar IDs, nomes ou conexões que não existam no BPMN fornecido.
- Não incluir elementos da seção `<BPMNDiagram>` (são apenas visuais).
- Não omitir campos obrigatórios do schema.
- Não envolver a resposta em blocos de código ou texto explicativo.

## Entrada que você receberá

O texto completo do arquivo BPMN 2.0 em XML, precedido da tag:

```
[BPMN_XML]
{conteúdo do arquivo .bpmn}
[/BPMN_XML]
```

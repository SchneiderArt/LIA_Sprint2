# Prompt — Conversão de BPMN para Narrativa em Linguagem Natural (Entrega 1)

## Instrução

Você receberá o texto extraído de um arquivo BPMN 2.0. Sua tarefa é transformar esse fluxo em uma **narrativa administrativa clara e auditável** em português, descrevendo o processo como se fosse explicado a um gestor que nunca viu o BPMN.

A narrativa deve ser estruturada, preservar toda a informação do BPMN e ser útil para que um agente de IA proponha automações com base nela.

## Estrutura obrigatória da narrativa

Produza a narrativa em seções, na seguinte ordem:

### 1. Identificação do processo
- Nome do processo
- ID do processo
- Raias (lanes) identificadas e suas responsabilidades

### 2. Objetos de dados
- Liste todos os documentos e objetos de dados presentes no BPMN com seus nomes

### 3. Sequência do fluxo
Descreva cada atividade em ordem de execução, seguindo o formato:

**[Raia responsável]** — **[Nome da atividade]**
> Descrição breve do que acontece nesta etapa. Se a atividade produz ou consome documentos, mencione-os.

### 4. Gateways e decisões
Para cada gateway, descreva:
- Pergunta/condição avaliada
- Caminhos possíveis e suas condições (Sim/Não, condições específicas)
- Para onde cada caminho leva

### 5. Loops e pontos de retorno
- Identifique ciclos no processo (quando o fluxo retorna a uma etapa anterior)
- Descreva a condição que causa o retorno e qual etapa é retomada

### 6. Documentos produzidos e consumidos
- Para cada documento/objeto de dado: qual atividade o produz e qual o consome

### 7. Ponto de início e fim
- Descreva o evento que inicia o processo
- Descreva o evento que encerra o processo

## Regras de escrita

1. Escreva em português claro, sem jargão técnico de XML ou BPMN.
2. Mantenha a ordem cronológica do fluxo — siga as arestas de sequência.
3. Quando houver gateway exclusivo (XOR), diga "se [condição], então [caminho A]; caso contrário, [caminho B]".
4. Quando houver gateway paralelo (AND), diga "simultaneamente" ou "em paralelo".
5. Quando houver loop, diga "retorna para [atividade anterior] até que [condição de saída]".
6. Mencione a raia responsável sempre que houver troca de raia entre atividades consecutivas.
7. Preserve os nomes originais das atividades — não parafrasear os nomes.
8. Não omita nenhuma atividade, gateway ou documento do BPMN.

## O que NÃO fazer

- Não omitir atividades, gateways ou documentos presentes no BPMN.
- Não inventar etapas que não existam no BPMN.
- Não usar termos técnicos XML como `<task>`, `<sequenceFlow>`, `id=`, etc.
- Não resumir em demasia — a narrativa deve ser auditável (rastreável de volta ao BPMN).

## Entrada que você receberá

O texto completo do arquivo BPMN 2.0 em XML, precedido da tag:

```
[BPMN_XML]
{conteúdo do arquivo .bpmn}
[/BPMN_XML]
```

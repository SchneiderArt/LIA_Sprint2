# Prompt — Conversão de Descritivo de Processo (PDF) para JSON Estruturado (Entrega 2)

## Instrução

Você receberá o texto extraído de um documento PDF que descreve um processo institucional. Sua tarefa é estruturar essas informações em um JSON válido seguindo **exatamente** o schema `DocumentoPDFJSON` definido abaixo.

## Observação sobre o template dos PDFs

Os PDFs desta sprint seguem um template exportado pelo Bizagi onde os **rótulos de seção aparecem após o conteúdo que descrevem** (padrão footer). Ou seja:

- O conteúdo da seção "Descrição" aparece **antes** da palavra "Descrição" no texto.
- O conteúdo da seção "Procedimentos" aparece **antes** da palavra "Procedimentos".
- O mesmo vale para "Amparo Legal", "Links", "Ficha de Indicadores", "Responsáveis", "Metas", etc.

Leia o texto completo e associe cada bloco de conteúdo ao seu rótulo de seção correspondente com base nessa estrutura.

## Schema obrigatório de saída

Responda **somente** com um objeto JSON válido, sem texto antes ou depois, sem blocos de código markdown, sem comentários. O JSON deve seguir esta estrutura:

```
{
  "titulo": "string — título do processo conforme o documento",
  "unidade_responsavel": "string — unidade gestora responsável pelo processo",
  "descricao": "string — descrição geral e finalidade do processo",
  "procedimentos": [
    "string — cada procedimento listado no documento"
  ],
  "amparo_legal": [
    "string — cada norma, lei, instrução normativa ou base legal mencionada"
  ],
  "links": [
    "string — cada URL mencionada no documento"
  ],
  "indicadores": [
    {
      "nome": "string — nome do indicador (ex: 'Indicador 1 - Nome do Indicador')",
      "formula": "string ou null — fórmula de cálculo do indicador",
      "fonte_dados": "string ou null — sistema ou fonte de coleta dos dados",
      "frequencia": "string ou null — periodicidade de apuração (ex: trimestral)",
      "metas": ["string — cada meta numérica ou textual associada ao indicador"]
    }
  ],
  "metas": [
    "string — metas gerais do processo além das vinculadas a indicadores específicos"
  ],
  "responsaveis": [
    "string — nome, cargo ou unidade identificada como responsável"
  ],
  "observacoes": "string ou null — informações adicionais relevantes"
}
```

## Regras de preenchimento

1. **titulo**: nome do processo conforme aparece no documento (geralmente linha curta antes do rótulo "Descrição").
2. **unidade_responsavel**: secretaria, diretoria ou setor responsável pelo processo. Procurar após o rótulo "Unidade Gestora" ou em menções explícitas no texto.
3. **descricao**: bloco de texto introdutório que descreve a finalidade do processo. Não incluir procedimentos ou normas neste campo.
4. **procedimentos**: itens da seção "Procedimentos". Manter cada item como uma entrada separada na lista. Preservar a ordem original.
5. **amparo_legal**: extrair cada norma individualmente: leis, decretos, instruções normativas, portarias, resoluções, acordãos, notas técnicas. Um item por norma.
6. **links**: URLs completas. Reconstruir URLs quebradas por quebra de linha concatenando as partes.
7. **indicadores**: cada bloco "Indicador N - Nome" vira um objeto. Extrair fórmula (bloco "Fórmula de cálculo"), fonte (bloco "Fonte / Forma de coleta de dados"), frequência (bloco "Frequência de medição") e metas (bloco "Metas"). Excluir linhas de "Controle de Versões" das metas.
8. **metas**: metas gerais (ex: trimestres, percentuais) que aparecem no bloco "Metas". Excluir metadados de revisão ("Revisão #1", "Criado em...", etc.).
9. **responsaveis**: cargos e nomes identificados no bloco "Responsáveis".
10. **observacoes**: conteúdo do bloco "Observações Adicionais" quando presente. `null` se ausente.

## O que NÃO fazer

- Não incluir metadados de controle de versão nas metas ou procedimentos (ex: "Revisão #1", "Criado 16 janeiro 2024", "Versão inicial").
- Não inventar informações ausentes no texto.
- Não omitir campos obrigatórios do schema — usar listas vazias `[]` ou `null` quando o campo não for identificável.
- Não envolver a resposta em blocos de código ou texto explicativo.

## Entrada que você receberá

O texto completo extraído do PDF, precedido da tag:

```
[PDF_TEXTO]
{texto extraído do PDF, página por página}
[/PDF_TEXTO]
```

# Desenho · Motor de regras de duplicatas

Data: 23/10/2026 · Desafio 1 do Hackathon Ideen 2026 · Prazo: segunda, 26/10, às 9h

Fonte da verdade do problema: `ENUNCIADO.md` do kit (`hackathon-2026-d1-kit.zip`). Este documento não repete as 12 regras; ele diz como o motor as aplica.

## Intenção

Um programa de linha de comando que classifica cada duplicata pela primeira regra satisfeita, na ordem da tabela, com as regras guardadas num arquivo fora do código. A banca ranqueia por acertos num conjunto surpresa com casos de borda e desempata pelo tempo total do comando, com 1 CPU.

Decisão da Giovana: nesta fase a prioridade é **um motor correto**. Robustez para uso real e um formato de regras pensado para pessoas de negócio ficam para depois.

## Objetivos

1. Acertar 100% no set pequeno e no set grande do kit.
2. Acertar os casos de borda da seção "Semântica" do enunciado, cobertos por uma bateria de testes própria, porque a massa do kit não tem nenhum campo ausente, tipo errado ou data inválida.
3. Trocar, reordenar ou criar regras editando só o arquivo de regras.
4. Dockerfile que roda o motor com `--entrada <arquivo>`; evidências do `medir.py`; README com as cinco seções do molde.
5. Depois de 1 a 4: reduzir o tempo, medido dentro do Docker com `--cpus=1`.

## Fora do escopo

- Servidor HTTP, interface de edição de regras, deploy (excluídos pelo desafio).
- Formato de regras para pessoas de negócio editarem (decisão da Giovana, fica para depois).
- Bônus "saída diz quais regras dispararam" e "segundo domínio": só se sobrar tempo depois dos objetivos.

## O que não pode acontecer

- **Normalizar dados.** `"cancelada"`, `"15000.00"`, `"false"` e `5102` sem aspas não satisfazem as condições; o motor é literal.
- **Usar a data do sistema.** A referência é 2026-10-23 e vem do arquivo de regras.
- **Regra no código.** Nenhum código, limite ou valor de domínio (`R07`, `500000`, `AGRO`) aparece no motor.
- **IA dentro do motor.** As regras são traduzidas por nós para um formato estruturado; o motor não interpreta português.

## Restrições

- Python, decisão da Giovana. Python 3.13 instalado na máquina; imagem Docker `python:3.13-slim` (minha escolha).
- Só biblioteca padrão no motor (minha escolha: zero dependência, imagem pequena, inicialização rápida). Uma biblioteca de JSON mais rápida só entra se a medição mostrar ganho relevante, e com a semântica revalidada.
- Contrato fixo: `motor --entrada entrada.jsonl > saida.txt`; uma linha por duplicata no stdout, `id:<id> - regra: <código>`; `SEM_REGRA` quando nada bate; ordem das linhas livre.
- Só dados fictícios; nenhum segredo no repositório (varredura de segredos ativa).

## Como o motor funciona

### Fluxo

1. Lê o arquivo de regras uma vez e o compila em funções Python, uma por regra, em ordem.
2. Lê a entrada linha a linha.
3. Para cada duplicata, chama as funções em ordem e para na primeira que devolver verdadeiro.
4. Acumula a saída e escreve no stdout de uma vez.

### Linha de comando

- `--entrada <arquivo>`: obrigatório.
- `--regras <arquivo>`: opcional; padrão é o arquivo de regras de duplicatas que vem no repositório, para que o comando da banca funcione sem esse parâmetro.

### Formato do arquivo de regras (JSON)

```json
{
  "regras": [
    { "codigo": "R07", "categoria": "Alto valor",
      "quando": { "ou": [
        { "campo": "financeiro.valor", "tipo": "numero", "op": "maior_igual", "valor": 500000 },
        { "e": [
          { "campo": "sacado.segmento", "tipo": "texto", "op": "igual", "valor": "AGRO" },
          { "campo": "financeiro.valor", "tipo": "numero", "op": "maior_igual", "valor": 200000 } ] } ] } }
  ],
  "sem_regra": "SEM_REGRA"
}
```

- `regras` é uma lista: a posição na lista é a ordem de avaliação.
- `quando` é uma condição simples ou uma combinação `{"e": [...]}` / `{"ou": [...]}`, aninháveis.
- Cada condição simples declara o `tipo` esperado do campo: `numero`, `texto`, `data` ou `booleano`. O tipo é o que permite aplicar a semântica 1 sem o motor conhecer o domínio.
- O lado direito é `valor` (constante) ou `outro_campo` (caminho de outro campo, para R05 `valor_pago < valor` e R08 `uf_origem ≠ uf_destino`). O outro campo é validado com o mesmo `tipo`.
- A data de referência entra como `valor` do tipo `data` (`"2026-10-23"`) na condição de R05.

### Operadores

| Operador | Significado | Tipos |
|---|---|---|
| `igual` / `diferente` | igualdade exata | todos |
| `em` | igual a algum valor de uma lista | texto |
| `menor`, `menor_igual`, `maior`, `maior_igual` | comparação; `≤` e `≥` incluem o limite | numero, data |
| `comeca_com` | prefixo | texto |
| `vazio` | ausente, `null` ou `""` | não declara tipo |

Esse é o conjunto que as 12 regras usam; não haverá operador sem regra que o use.

### Semântica dos valores (a parte que decide o ranking)

- **Caminho:** `a.b.c` desce por objetos. Se algum nível estiver ausente, for `null` ou não for objeto, o campo é ausente.
- **Validação de tipo antes de comparar.** Se o valor do campo (ou do `outro_campo`) não for do tipo declarado, a condição é **falsa**, inclusive `diferente`.
  - `numero`: `int` ou `float` do JSON, **excluindo `bool`** (em Python, `True` é `int`) e excluindo `NaN`/`Infinity` (o `json` do Python os aceita; minha escolha tratá-los como não número).
  - `texto`: `str`, comparação exata, sensível a maiúsculas.
  - `data`: `str` no formato exato `AAAA-MM-DD` (verificado por expressão regular, porque `date.fromisoformat` do Python 3.11+ aceita outros formatos como `20261023`) **e** data válida no calendário. Datas válidas são comparadas como texto.
  - `booleano`: só `true`/`false` do JSON. "É falso" é `igual` a `false` com tipo `booleano`.
- **`vazio`** é a única condição que fica verdadeira com campo ausente.
- **E/OU** seguem a estrutura do arquivo; uma condição falsa por dado esquisito só falsifica a si mesma.

### Casos que o enunciado não define (minhas escolhas, registradas no README)

| Caso | Comportamento |
|---|---|
| Linha vazia | Ignorada |
| Linha que não é JSON válido, ou JSON que não é objeto | Ignorada, aviso no stderr com o número da linha; o motor não para. Não há tentativa de extrair o `id` de uma linha quebrada: o enunciado promete um objeto JSON por linha |
| `id` ausente | Ignorada, aviso no stderr |
| `id` texto | Escrito sem aspas (`"7"` vira `id:7`), para casar com a leitura do `medir.py` |
| `id` número | Escrito como o Python o decodifica (`7` vira `7`; um decimal sai como `str(float)`) |
| `id` repetido | Cada linha é classificada e escrita; sem deduplicação |
| Chave repetida no mesmo objeto | Vale a última (comportamento padrão do `json` do Python) |
| Arquivo de regras inválido (operador ou tipo desconhecido) | O motor para antes de ler a entrada, com mensagem clara e código de saída diferente de zero |

## Estrutura do repositório

| Caminho | O que é |
|---|---|
| `motor.py` | Ponto de entrada da linha de comando e o motor (arquivo único enquanto couber em leitura de 5 minutos) |
| `regras/duplicatas.json` | As 12 regras traduzidas |
| `tests/` | Testes com `unittest` da biblioteca padrão: semântica por tipo, cada regra isolada, conflitos de ordem e a comparação com o gabarito do set pequeno |
| `kit/` | `medir.py` e `dados/` do kit, para reproduzir sem baixar nada (o set grande compactado tem 25 MB) |
| `Dockerfile` | `python:3.13-slim`, copia `motor.py` e `regras/`, `ENTRYPOINT` no motor |
| `evidencias/` | Saída do `medir.py` nos dois sets, rodado via Docker com `--cpus=1` |
| `.gitattributes` | Força LF, porque o desenvolvimento é em Windows e o contêiner é Linux |
| `docs/diario-ia.md` | Registro de onde a IA acelerou ou errou |

## Verificação

- Testes de semântica escritos **antes** do motor, a partir da seção "Semântica" do enunciado, com um caso por armadilha (minúsculo, número em texto, `bool` como número, `NaN`, data inválida, data em outro formato, CFOP numérico, `migo` como `"false"`/`0`, bloco inteiro `null`, `≠` com um lado ausente, OU com um lado ausente, `vazio` com ausente, `null`, `""` e `" "`).
- `medir.py` nos dois sets: 100% de acertos, zero ids ausentes, zero linhas inválidas.
- Prova do "genérico": um teste troca o arquivo de regras (por exemplo, inverte a ordem de R01 e R11) e confere que a classificação muda sem tocar no motor.

## Desempenho (só depois da correção)

Medir primeiro, mudar depois. Candidatos, nesta ordem: compilar as regras em funções (já no desenho), escrever a saída de uma vez, ler a entrada em bloco, iniciar o Python sem o módulo `site` no contêiner. Cada mudança é medida com o `medir.py` via Docker e só fica se os testes continuarem passando.

## Deixado para quem constrói

Nomes internos, organização das funções dentro de `motor.py`, mensagens de erro, a forma exata de compilar condições em funções e a ordem das otimizações.

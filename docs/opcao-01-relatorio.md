# Opção 1: relatório de resultados

Branch `opcao-01`, a partir de `feat/motor` (2c77384). Data: 25/10/2026.

## Resumo

- Acerto: 100% no set pequeno (100/100) e no grande (200.000/200.000), igual à base.
- Tempo no Docker com `--cpus=1`, base e opção 1 medidas alternadas na mesma janela: a base ficou em 25,1 a 25,5s de mediana e a opção 1 em 5,8 a 9,8s. Isso dá entre 2,6 e 4,4 vezes mais rápido.
- A estimativa de 2,5 a 3s de tempo total não se confirmou neste ambiente. O trabalho do motor dentro do container (parse, regras e saída) ficou em 2,1 a 3,9s, perto do estimado. Sobram cerca de 2,6s para ler o arquivo pelo volume do Docker Desktop no Windows e cerca de 1,2s para subir o container, e a estimativa não contava esses dois custos.
- O risco descrito para o `orjson` estava parcialmente errado e foi tratado (detalhe abaixo).
- A troca também corrigiu três entradas que derrubavam a base inteira, com saída vazia.

## O que mudou

| Parte | Antes | Agora |
|---|---|---|
| Leitura | arquivo texto, linha a linha | `read()` do arquivo inteiro em bytes, `split(b"\n")` |
| Parse | `json.loads` | `orjson.loads`; `json.loads` só nas linhas que o orjson recusa ou que podem ter perdido precisão |
| Regras | árvore de closures Python chamadas por condição | o JSON de regras vira o código-fonte de uma função `classificar(doc)`, compilada uma vez na inicialização |
| Imagem | `python:3.13-slim` | a mesma, com `orjson==3.11.9` instalado no build (+14 MB) |

As regras continuam em `regras/duplicatas.json`, sem mudança no formato. A função gerada lê cada objeto intermediário (`logistica`, `financeiro`, ...) uma vez, troca o que for ausente, nulo ou não objeto por um dicionário vazio e testa tipo e valor em linha. O código gerado pode ser inspecionado com `carregar_classificador(...)[0].fonte`.

`compilar_condicao` e `carregar_regras` continuam existindo com a mesma assinatura e passam pelo mesmo gerador, então os testes antigos exercitam o código novo. Sem `orjson` instalado, o motor cai para `json` e continua correto, só mais lento.

## O risco do orjson, conferido

| Entrada | json | orjson | Tratamento |
|---|---|---|---|
| `NaN`, `Infinity`, `1e400` | aceita (nan/inf) | recusa | releitura com json; o número não é finito e a condição dá falso |
| `"\ud800"` (surrogate solto) | aceita | recusa | releitura com json |
| aninhamento de 5.000 níveis | `RecursionError` | recusa | linha ignorada com aviso |
| inteiro acima de 64 bits (`18446744073709551616`) | inteiro exato | **aceita e devolve float** `1.8446744073709552e+19`, sem erro | ver abaixo |
| chave duplicada | fica a última | fica a última | igual |

A proposta dizia que o orjson recusa inteiros acima de 64 bits. Ele aceita e arredonda. O fallback "só nas linhas que falharem" deixaria passar dois erros:

1. Um `id` desses sairia como `id:1.8446744073709552e+19`.
2. Dois valores enormes que diferem só no fim ficam iguais em float, e `valor_pago < valor` (R05) muda de resultado.

Correção: na função gerada para o caminho rápido, todo campo numérico que chega como float de módulo ≥ 2^63 levanta `Reler`, e a linha é relida com json e classificada pela versão exata. Um `id` float também força releitura. Na massa normal isso custa uma comparação por campo numérico. Varrer o arquivo com regex atrás desses números custava de 0,5 a 1,5s e foi descartado.

## Defeitos da base corrigidos de passagem

Cada uma destas linhas derrubava a base inteira, com saída vazia e zero acertos no conjunto todo:

| Linha | Base | Opção 1 |
|---|---|---|
| `"valor": 1000…0` (400 dígitos) | `OverflowError` em `math.isfinite` | número válido, classifica (R07) |
| `[[[[…]]]]` com 5.000 níveis | `RecursionError` | aviso "JSON inválido" e segue |
| byte UTF-8 inválido em qualquer linha | `UnicodeDecodeError` no arquivo inteiro | aviso "JSON inválido" naquela linha e segue |

Além disso, `\r` sozinho continua separando linhas, como no modo texto da base, e a saída usa `errors="backslashreplace"` para um id com surrogate solto não derrubar a escrita.

## Testes

- 54 testes da base: passam sem alteração.
- 9 testes novos, 63 no total, todos passando em três ambientes: Python 3.13 local com orjson, local sem orjson e dentro da imagem Docker.
  - `tests/test_gerado.py`: compara a função gerada com uma leitura literal da seção Semântica, escrita só com `resolver` e `valido`, no set pequeno e em 20.000 duplicatas mutadas ao acaso (campos ausentes, nulos, tipo trocado, limites, NaN, inf, inteiros de 70 bits).
  - `tests/test_cli.py`: inteiro acima de 64 bits, valores enormes em R05, NaN, Infinity e surrogate, UTF-8 inválido, aninhamento profundo, `\r` sozinho e inteiro de 400 dígitos.

## Medições

Arquivos completos em `evidencias/opcao-01/`. Imagens `motor-base-01` (base 2c77384) e `motor-opcao-01`, `--cpus=1`, rodadas alternadas.

| Rodada | Imagem | Repetições | Mediana (s) |
|---|---|---|---|
| grande 1 | opção 1 | 5 | 9,819 |
| grande 2 | base | 5 | 25,533 |
| grande 3 | opção 1 | 5 | 5,836 |
| grande 4 | base | 3 | 25,071 |
| grande 5 | opção 1 | 3 | 7,823 |
| pequeno | opção 1 | 5 | 1,495 |
| pequeno | base | 5 | 1,714 |

Decomposição dentro do container, na mesma janela:

| Etapa | Base | Opção 1 |
|---|---|---|
| ler o arquivo do volume | 5,8 a 6,8s (linha a linha, com decodificação) | 2,6s (em bloco) |
| parse, regras e saída | 5,3 a 5,9s | 2,1 a 3,9s |

## Limites desta medição

- A máquina estava carregada: outras sessões compilavam Go e Rust na mesma pasta e ao mesmo tempo. A base, que marcou 15,97s na evidência anterior, marcou cerca de 25s aqui. Os números absolutos estão inflados; a comparação vale entre base e opção 1 da mesma janela. A dispersão da opção 1 (5,2 a 10,9s) também vem disso.
- Não medi a opção 1 com a máquina ociosa. Se a proporção se mantiver, ela ficaria perto de 5s contra os 16s da base, mas isso é projeção.
- A leitura pelo volume do Docker Desktop no Windows custa cerca de 2,6s sozinha. Na máquina da banca esse custo pode ser outro, para mais ou para menos, e ele pesa igual para qualquer linguagem.
- O `orjson` é instalado do PyPI no build, com versão fixa e sem hash. Se a banca construir a imagem sem rede, o build falha. Fixar o hash (`--require-hashes`) ou levar a wheel no repositório resolve isso.

## Próximos passos possíveis

- Medir de novo com a máquina sem outras cargas para ter o número absoluto.
- Desligar o coletor de lixo durante o laço: no teste local o efeito ficou dentro do ruído e não entrou.
- Escrever a saída em bytes direto em `sys.stdout.buffer`: ganho pequeno, não medido.

# Motor de regras de duplicatas escriturais

Hackathon Ideen 2026 · Desafio 1 · Motor de regras plataformizado · Individual

> Status: em construção. Prazo: segunda, 26/10/2026, às 9h.

## 1. O problema

<!-- Uma frase. -->

_A preencher._

## 2. O que eu fiz

<!-- A solução e o fluxo. Alguém precisa entender o motor em 5 minutos. -->

### Visão geral

_A preencher._

### Fluxo

1. Lê as regras: _arquivo e formato a definir_.
2. Lê a entrada (`entrada.jsonl`, uma duplicata por linha).
3. Avalia as regras em ordem; a primeira satisfeita classifica.
4. Escreve a saída no stdout: `id:1 - regra: R07`.

### Formato das regras

<!-- Onde ficam, como se escreve uma condição, como trocar ou reordenar sem mexer no motor. -->

_A preencher._

### Estrutura do repositório

| Caminho | O que é |
|---|---|
| _a definir_ | código do motor |
| _a definir_ | regras traduzidas, fora do código |
| `Dockerfile` | roda o motor com `--entrada <arquivo>` |
| `evidencias/` | saída do `medir.py` nos dois conjuntos |
| `docs/diario-ia.md` | registro de onde a IA errou, feito durante o trabalho |

### Decisões e limites

<!-- O que ficou de fora e por quê; o que o enunciado não especifica e como foi resolvido. -->

| Tema | Decisão |
|---|---|
| Servidor HTTP, interface de edição de regras, deploy | Fora do escopo, conforme o desafio |
| _ex.: linha malformada na entrada_ | _a definir_ |

## 3. Como reproduzir

<!-- Passo a passo para outra pessoa rodar sem precisar de mim. Testar em máquina limpa. -->

### Pré-requisitos

_A preencher._

### Rodar com Docker (como a banca)

```bash
docker build -t motor .
```

```bash
docker run --rm --cpus=1 -v <pasta>:/dados motor --entrada /dados/entrada.jsonl > saida.txt
```

### Medir contra o gabarito

```bash
python medir.py --set pequeno --cmd "docker run --rm --cpus=1 -v {dir}:/dados motor --entrada /dados/{arquivo}"
```

```bash
python medir.py --set grande --cmd "docker run --rm --cpus=1 -v {dir}:/dados motor --entrada /dados/{arquivo}"
```

### Testes

_A preencher._

## 4. Evidências

<!-- O que rodou e o resultado. Números copiados da saída real, com o arquivo em evidencias/. -->

| Conjunto | Casos | Acertos | Mediana (s) | Arquivo |
|---|---|---|---|---|
| Pequeno | 100 | _a medir_ | _a medir_ | `evidencias/` |
| Grande | 200.000 | _a medir_ | _a medir_ | `evidencias/` |

Máquina da medição: _a preencher_.

### Casos de borda

<!-- A massa do kit não traz campo ausente, tipo errado nem data inválida. Os testes próprios cobrem a seção "Semântica" do enunciado. -->

_A preencher._

## 5. Onde a IA errou

<!-- Erros concretos e como foram corrigidos. Detalhes em docs/diario-ia.md. -->

| O que a IA fez | Por que estava errado | Como corrigi |
|---|---|---|
| _a preencher_ | | |

## Bônus

- [ ] A saída diz quais regras dispararam
- [ ] Um segundo domínio, sem mudar código
- [ ] Testes automatizados

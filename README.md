# Motor de regras de duplicatas escriturais

Hackathon Ideen 2026 · Desafio 1 · Motor de regras plataformizado · Individual

## 1. O problema

Classificar duplicatas escriturais com regras de negócio espalhadas em if/else não escala nem se explica, e cada mudança de regra obriga a mexer no código.

## 2. O que eu fiz

Um motor em Python (`motor.py`) que classifica cada duplicata pela primeira regra satisfeita. As regras ficam em `regras/duplicatas.json`; o motor não conhece nenhuma regra de domínio.

### Fluxo

1. **Regras:** lê o JSON de regras, valida e transforma tudo numa única função Python, compilada uma vez.
2. **Entrada:** lê o arquivo inteiro de uma vez.
3. **Leitura de cada linha:** o `orjson` converte o texto JSON da linha num objeto Python. Ele só lê; quem decide a regra é o passo seguinte.
4. **Classificação:** a função gerada testa as regras em ordem; a primeira satisfeita classifica, nenhuma dá `SEM_REGRA`.
5. **Saída:** `id:1 - regra: R07` no stdout.

### Formato das regras

```json
{
  "codigo": "R06",
  "categoria": "Garantia relevante",
  "quando": { "e": [
    { "campo": "financeiro.tipo_negociacao", "tipo": "texto", "op": "em", "valor": ["CSFD", "PENR"] },
    { "campo": "financeiro.valor", "tipo": "numero", "op": "maior_igual", "valor": 100000 }
  ] }
}
```

- `tipo`: `numero`, `texto`, `data`, `booleano`. Valor de outro tipo torna a condição falsa.
- `op`: `igual`, `diferente`, `menor`, `menor_igual`, `maior`, `maior_igual`, `em`, `comeca_com`, `vazio`.
- `outro_campo` compara dois campos da duplicata; `e` / `ou` combinam condições.

Trocar, reordenar ou acrescentar regra é só editar o JSON. Exemplo em `regras/exemplo_ordem_invertida.json`:

```bash
python motor.py --entrada entrada.jsonl --regras regras/exemplo_ordem_invertida.json
```

### Estrutura do repositório

| Caminho | O que é |
|---|---|
| `motor.py` | motor |
| `regras/` | regras do desafio e exemplo de reordenação |
| `Dockerfile` | imagem `python:3.13-slim` + `orjson` |
| `tests/` | 63 testes automatizados |
| `evidencias/opcao-01/` | saída do `medir.py` |
| `docs/` | diário de uso da IA e relatório técnico |

### Decisões

| Tema | Decisão |
|---|---|
| Linguagem | Python, por segurança de acerto. Uma versão em Go mais rápida existe na branch `opcao-02`, fora da entrega |
| Leitura do JSON | `orjson`, por ser a etapa mais lenta; volta ao `json` padrão nas linhas que o `orjson` recusa ou em números acima de 64 bits |
| Linha inválida ou sem `id` | ignorada com aviso no stderr; o resto segue |
| Build | instala `orjson` do PyPI, precisa de rede |

## 3. Como reproduzir

Pré-requisitos: Docker e Python 3.13.

```bash
docker build -t motor .
```

```bash
docker run --rm --cpus=1 -v <pasta>:/dados motor --entrada /dados/entrada.jsonl > saida.txt
```

```bash
python kit/medir.py --set grande --cmd "docker run --rm --cpus=1 -v {dir}:/dados motor --entrada /dados/{arquivo}"
```

```bash
python -m unittest discover -s tests
```

## 4. Evidências

| Conjunto | Casos | Acertos | Mediana (s) |
|---|---|---|---|
| Pequeno | 100 | 100% | 0,88 |
| Grande | 200.000 | 100% | 4,54 |

Windows 11, Docker Desktop (WSL2), `--cpus=1`, 5 execuções, imagem construída do zero a partir da `main`. Arquivo em `evidencias/opcao-01/final.txt`.

A versão anterior do motor, em Python com `json` padrão, marcou cerca de 16s nesta mesma máquina. No Docker Desktop do Windows, ler a entrada pela pasta montada custa cerca de 2,6s e subir o container cerca de 1s.

**Casos de borda:** a massa do kit não traz dados sujos. Os testes cobrem a seção "Semântica" do enunciado: número como texto, booleano como `"false"`, data inválida, CFOP numérico, `diferente` com campo ausente, `vazio` com `""` e limites de `≥` e `>`.

## 5. Onde a IA errou

| O que a IA fez | Por que estava errado | Como corrigi |
|---|---|---|
| Disse que o `orjson` recusa inteiros acima de 64 bits | Ele aceita e arredonda sem erro, o que mudaria `id` e a R05 | Linhas com esses números são relidas com `json`; testes em `test_cli.py` |
| Estimou 2,5 a 3s no Docker | Deixou de fora a leitura pela pasta montada e a subida do container | Medição por etapa dentro do container |

Detalhes em `docs/diario-ia.md`.

## Bônus

- [ ] A saída diz quais regras dispararam
- [ ] Um segundo domínio, sem mudar código
- [x] Testes automatizados

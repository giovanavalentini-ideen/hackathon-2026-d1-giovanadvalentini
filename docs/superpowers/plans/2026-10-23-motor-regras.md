# Motor de regras de duplicatas · Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI em Python que classifica cada duplicata do `entrada.jsonl` pela primeira regra satisfeita, com as regras num JSON fora do código.

**Architecture:** `motor.py` tem três camadas: semântica de valores (resolver caminho, validar tipo), compilação do JSON de regras em funções `dict -> bool`, e a CLI que lê linha a linha e escreve a saída de uma vez. `regras/duplicatas.json` traz as 12 regras. Testes com `unittest`, escritos antes de cada camada.

**Tech Stack:** Python 3.13, só biblioteca padrão; Docker `python:3.13-slim`.

**Spec:** `docs/superpowers/specs/2026-10-23-motor-regras-design.md` (o enunciado oficial é `kit/ENUNCIADO.md`, copiado na Task 1).

## Global Constraints

- Contrato: `motor --entrada entrada.jsonl > saida.txt`; uma linha por duplicata no stdout: `id:<id> - regra: <código>`; `SEM_REGRA` quando nada bate.
- Data de referência `2026-10-23`, vinda do arquivo de regras; o motor nunca usa a data do sistema.
- Nenhum código, limite ou valor de domínio (`R07`, `500000`, `AGRO`) dentro de `motor.py`.
- Só biblioteca padrão no motor.
- Tipos: `numero` = `int`/`float` exceto `bool` e não finitos; `texto` = `str` exato; `data` = `str` casando `^\d{4}-\d{2}-\d{2}$` e válida no calendário; `booleano` = `True`/`False`.
- Tipo inválido ou campo ausente: condição falsa, inclusive `diferente`. Só `vazio` fica verdadeiro com ausente (`None`, ausente ou `""`).
- Comandos rodam na raiz do repositório. Testes: `python -m unittest discover -s tests -v`.
- Arquivos de texto com LF (`.gitattributes`).
- Mensagens de commit terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Entrada com BOM UTF-8 ou acentos, gerada no Windows:** a primeira linha deve ser lida normalmente; abrir com `encoding="utf-8-sig"`. Teste na Task 4.
2. **Rodar o motor a partir de outra pasta** (como o `medir.py` faz): o arquivo de regras padrão é resolvido pela pasta do `motor.py`, não pelo diretório atual. Teste na Task 4.
3. **Número no limite escrito como decimal** (`500000.0`) ou inteiro (`500000`): os dois disparam `maior_igual 500000`. Teste na Task 3.
4. **Arquivo de regras com `e`/`ou` vazio:** `all([])` seria verdadeiro e classificaria tudo; deve ser `ErroRegras`. Teste na Task 2.
5. **Linhas terminadas em `\r\n`:** classificadas normalmente; a saída é sempre `\n`. Teste na Task 4.

---

### Task 1: Base do repositório e semântica de valores

**Files:**
- Create: `.gitattributes`, `kit/` (cópia de `medir.py`, `README.md`, `ENUNCIADO.md` e `dados/` do kit extraído em `C:/Users/ADMINI~1/AppData/Local/Temp/claude/C--Users-Administrador--claude-spares-spare-XDSVx0/d2b197e9-9cb0-473f-883c-8eae702ed1e8/scratchpad/kit/hackathon-2026-d1-kit/`), `motor.py`
- Test: `tests/test_semantica.py`

**Interfaces:**
- Produces: `AUSENTE` (sentinela única); `resolver(doc: dict, caminho: tuple[str, ...]) -> object` (devolve `AUSENTE` se algum nível faltar, for `None` ou não for `dict`); `valido(valor: object, tipo: str) -> bool` para `tipo` em `{"numero", "texto", "data", "booleano"}`.

- [ ] **Step 1: Criar `.gitattributes` com `* text=auto eol=lf` e `*.gz binary`, e copiar o kit para `kit/`**

- [ ] **Step 2: Escrever os testes**

```python
import unittest
from motor import AUSENTE, resolver, valido

class Resolver(unittest.TestCase):
    def test_caminho_aninhado(self):
        self.assertEqual(resolver({"a": {"b": 5}}, ("a", "b")), 5)
    def test_ausente_nulo_e_nao_objeto(self):
        for doc in ({}, {"a": None}, {"a": "x"}, {"a": {}}):
            self.assertIs(resolver(doc, ("a", "b")), AUSENTE)
    def test_folha_nula_e_ausente(self):
        self.assertIs(resolver({"a": None}, ("a",)), AUSENTE)

class Valido(unittest.TestCase):
    def test_numero(self):
        self.assertTrue(valido(5, "numero")); self.assertTrue(valido(5.5, "numero"))
        for v in (True, False, "15000.00", float("nan"), float("inf"), AUSENTE):
            self.assertFalse(valido(v, "numero"), v)
    def test_texto(self):
        self.assertTrue(valido("", "texto"))
        for v in (5102, None, True, AUSENTE):
            self.assertFalse(valido(v, "texto"), v)
    def test_data(self):
        self.assertTrue(valido("2026-10-23", "data")); self.assertTrue(valido("2024-02-29", "data"))
        for v in ("2026-02-30", "2026-1-5", "20261023", "2026-10-23T00:00", " 2026-10-23", 20261023, AUSENTE):
            self.assertFalse(valido(v, "data"), v)
    def test_booleano(self):
        self.assertTrue(valido(True, "booleano")); self.assertTrue(valido(False, "booleano"))
        for v in ("false", 0, 1, None, AUSENTE):
            self.assertFalse(valido(v, "booleano"), v)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m unittest tests.test_semantica -v`
Expected: FAIL com `ModuleNotFoundError` ou `ImportError` de `motor`.

- [ ] **Step 4: Implementar `AUSENTE`, `resolver` e `valido` em `motor.py`**

Data: regex compilada uma vez mais `datetime.date.fromisoformat` dentro de `try`. Número: `type(v) in (int, float) and math.isfinite(v)`.

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m unittest tests.test_semantica -v`
Expected: todos OK.

- [ ] **Step 6: Commit (inclui o desenho e este plano)**

```bash
git add .gitattributes kit motor.py tests docs/superpowers
git commit -m "Adiciona kit, semântica de valores e testes"
```

---

### Task 2: Compilação de condições e carga de regras

**Files:**
- Modify: `motor.py`
- Test: `tests/test_condicoes.py`

**Interfaces:**
- Consumes: `resolver`, `valido`, `AUSENTE` (Task 1).
- Produces: `class ErroRegras(Exception)`; `compilar_condicao(cond: dict) -> Callable[[dict], bool]`; `carregar_regras(caminho: str) -> tuple[list[tuple[str, Callable[[dict], bool]]], str]` (lista ordenada de `(codigo, funcao)` e o texto de `sem_regra`).

Formato de condição (do desenho): simples `{"campo", "tipo", "op", "valor" | "outro_campo"}`, `vazio` como `{"campo", "op": "vazio"}`, combinações `{"e": [...]}` e `{"ou": [...]}`. Operadores: `igual`, `diferente` (todos os tipos), `em` (texto, `valor` é lista), `menor`, `menor_igual`, `maior`, `maior_igual` (numero, data), `comeca_com` (texto), `vazio`. Caminhos são separados por `.` uma vez, na compilação.

- [ ] **Step 1: Escrever os testes**

```python
import json, os, tempfile, unittest
from motor import ErroRegras, compilar_condicao, carregar_regras

def c(**k): return compilar_condicao(k)

class Operadores(unittest.TestCase):
    def test_igual_exato(self):
        f = c(campo="s", tipo="texto", op="igual", valor="ATIVA")
        self.assertTrue(f({"s": "ATIVA"})); self.assertFalse(f({"s": "ativa"})); self.assertFalse(f({}))
    def test_diferente_com_ausente_ou_tipo_errado_e_falso(self):
        f = c(campo="a", tipo="texto", op="diferente", outro_campo="b")
        self.assertTrue(f({"a": "SP", "b": "MT"}))
        self.assertFalse(f({"a": "SP"})); self.assertFalse(f({"a": "SP", "b": 35})); self.assertFalse(f({"a": "SP", "b": "SP"}))
    def test_limites(self):
        self.assertTrue(c(campo="v", tipo="numero", op="maior_igual", valor=100)({"v": 100}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior", valor=100)({"v": 100}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior_igual", valor=100)({"v": "150"}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior_igual", valor=1)({"v": True}))
    def test_data_menor(self):
        f = c(campo="d", tipo="data", op="menor", valor="2026-10-23")
        self.assertTrue(f({"d": "2026-10-22"})); self.assertFalse(f({"d": "2026-10-23"})); self.assertFalse(f({"d": "2026-02-30"}))
    def test_em_e_comeca_com(self):
        self.assertTrue(c(campo="t", tipo="texto", op="em", valor=["A", "B"])({"t": "B"}))
        f = c(campo="cfop", tipo="texto", op="comeca_com", valor="5")
        self.assertTrue(f({"cfop": "5102"})); self.assertFalse(f({"cfop": 5102})); self.assertFalse(f({"cfop": "6102"}))
    def test_booleano(self):
        f = c(campo="m", tipo="booleano", op="igual", valor=False)
        self.assertTrue(f({"m": False})); self.assertFalse(f({"m": 0})); self.assertFalse(f({"m": "false"}))
    def test_vazio(self):
        f = c(campo="x.t", op="vazio")
        for d in ({}, {"x": None}, {"x": {"t": None}}, {"x": {"t": ""}}):
            self.assertTrue(f(d), d)
        for d in ({"x": {"t": " "}}, {"x": {"t": 0}}, {"x": {"t": "ACTO"}}):
            self.assertFalse(f(d), d)
    def test_e_ou_parcial(self):
        f = compilar_condicao({"ou": [{"campo": "a", "tipo": "texto", "op": "igual", "valor": "X"},
                                      {"campo": "b", "tipo": "texto", "op": "igual", "valor": "Y"}]})
        self.assertTrue(f({"b": "Y"}))
        g = compilar_condicao({"e": [{"campo": "a", "tipo": "texto", "op": "igual", "valor": "X"},
                                     {"campo": "b", "op": "vazio"}]})
        self.assertTrue(g({"a": "X"})); self.assertFalse(g({"a": "X", "b": "Z"}))

class Invalidas(unittest.TestCase):
    def test_rejeita(self):
        for cond in ({"campo": "a", "tipo": "texto", "op": "parece"},
                     {"campo": "a", "tipo": "moeda", "op": "igual", "valor": 1},
                     {"campo": "a", "tipo": "texto", "op": "maior", "valor": "x"},
                     {"e": []}, {"ou": []}):
            with self.assertRaises(ErroRegras, msg=cond): compilar_condicao(cond)

class Carga(unittest.TestCase):
    def test_ordem_e_sem_regra(self):
        doc = {"sem_regra": "SEM_REGRA", "regras": [
            {"codigo": "A", "quando": {"campo": "x", "op": "vazio"}},
            {"codigo": "B", "quando": {"campo": "x", "tipo": "texto", "op": "igual", "valor": "1"}}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(doc, f)
        try:
            regras, sem = carregar_regras(f.name)
            self.assertEqual([r[0] for r in regras], ["A", "B"]); self.assertEqual(sem, "SEM_REGRA")
        finally:
            os.unlink(f.name)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m unittest tests.test_condicoes -v`
Expected: FAIL com `ImportError` de `ErroRegras`.

- [ ] **Step 3: Implementar `ErroRegras`, `compilar_condicao` e `carregar_regras` em `motor.py`**

Cada condição vira uma closure; os valores constantes e o caminho são preparados na compilação. Toda comparação valida o tipo dos dois lados antes de usar o operador do módulo `operator`. `carregar_regras` lê com `encoding="utf-8"` e levanta `ErroRegras` se faltar `regras`, `codigo` ou `quando`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m unittest discover -s tests -v`
Expected: todos OK.

- [ ] **Step 5: Commit**

```bash
git add motor.py tests/test_condicoes.py
git commit -m "Compila condições do arquivo de regras em funções"
```

---

### Task 3: As 12 regras de duplicatas

**Files:**
- Create: `regras/duplicatas.json`
- Test: `tests/test_regras_duplicatas.py`

**Interfaces:**
- Consumes: `carregar_regras` (Task 2).
- Produces: `regras/duplicatas.json` no formato da Task 2, com `sem_regra: "SEM_REGRA"`, R01 a R12 nesta ordem e cada regra com `codigo`, `categoria` e `quando`.

Tradução da tabela do `kit/ENUNCIADO.md`, com o tipo de cada campo:

| Regra | Condição |
|---|---|
| R01 | `status` texto `em` [CANCELADA, LIQUIDADA] |
| R02 | ou: `logistica.status_entrega` igual DEVOLVIDA; `manifestacao.tipo` igual RCOP |
| R03 | `manifestacao.tipo` em [RCAV, RCQQ, RCVN, RCVL] |
| R04 | e: `logistica.status_entrega` igual AVARIADA; `manifestacao.tipo` vazio |
| R05 | e: `data_vencimento` data menor `2026-10-23`; `financeiro.valor_pago` numero menor `outro_campo` `financeiro.valor` |
| R06 | e: `financeiro.tipo_negociacao` em [CSFD, PENR]; `financeiro.valor` maior_igual 100000 |
| R07 | ou: `financeiro.valor` maior_igual 500000; e(`sacado.segmento` igual AGRO; `financeiro.valor` maior_igual 200000) |
| R08 | e: `logistica.uf_origem` texto diferente `outro_campo` `logistica.uf_destino`; `fiscal.cfop` comeca_com "5" |
| R09 | e: `logistica.modal` igual AEREO; `logistica.peso_kg` maior 500 |
| R10 | e: `logistica.status_entrega` igual ENTREGUE; `logistica.migo` booleano igual false |
| R11 | e: `manifestacao.tipo` igual ACTO; `logistica.migo` booleano igual true |
| R12 | e: `pagamento.instrumento` igual PPIX; `sacador.porte` em [ME, EPP]; `financeiro.valor` menor_igual 5000 |

- [ ] **Step 1: Escrever os testes**

Helper no topo do arquivo: `classificar_doc(doc) -> str`, que carrega `regras/duplicatas.json` uma vez e devolve o código da primeira função verdadeira ou `SEM_REGRA`. `BASE` é uma duplicata que não dispara nenhuma regra (copiar a linha `id:1` de `kit/dados/pequeno/entrada.jsonl`, que o gabarito marca `SEM_REGRA`); cada teste aplica um ajuste com uma função `com(**caminhos)` que devolve uma cópia profunda alterada.

```python
class CadaRegra(unittest.TestCase):
    def test_base_sem_regra(self): self.assertEqual(classificar_doc(BASE), "SEM_REGRA")
    def test_r01(self): self.assertEqual(classificar_doc(com(status="LIQUIDADA")), "R01")
    def test_r01_minusculo_nao_dispara(self): self.assertEqual(classificar_doc(com(status="liquidada")), "SEM_REGRA")
    def test_r02_por_manifestacao(self): self.assertEqual(classificar_doc(com(**{"manifestacao.tipo": "RCOP", "logistica.status_entrega": None})), "R02")
    def test_r04_bloco_manifestacao_ausente(self): self.assertEqual(classificar_doc(com(**{"logistica.status_entrega": "AVARIADA", "manifestacao": None})), "R04")
    def test_r05_texto_no_valor(self): self.assertEqual(classificar_doc(com(**{"data_vencimento": "2026-10-22", "financeiro.valor": "27821.81", "financeiro.valor_pago": 0.0})), "SEM_REGRA")
    def test_r07_limite_int_e_float(self):
        for v in (500000, 500000.0): self.assertEqual(classificar_doc(com(**{"financeiro.valor": v, "financeiro.valor_pago": v})), "R07")
    def test_r08_uf_ausente(self): self.assertEqual(classificar_doc(com(**{"logistica.uf_destino": None})), "SEM_REGRA")
    def test_r10_migo_texto(self): self.assertEqual(classificar_doc(com(**{"logistica.migo": "false"})), "SEM_REGRA")

class Ordem(unittest.TestCase):
    def test_r01_vence_r11(self): self.assertEqual(classificar_doc(com(status="CANCELADA", **{"manifestacao.tipo": "ACTO", "logistica.migo": True})), "R01")
    def test_minusculo_cai_para_r11(self): self.assertEqual(classificar_doc(com(status="cancelada", **{"manifestacao.tipo": "ACTO", "logistica.migo": True})), "R11")

class SetPequeno(unittest.TestCase):
    def test_bate_com_gabarito(self):
        # lê kit/dados/pequeno/entrada.jsonl e gabarito.txt; assertEqual do dicionário id -> regra
        ...
```

Ajustes em `com` usam caminho com `.`; valor `None` grava `null` (não remove a chave). Adicionar um teste positivo para cada regra restante (R03, R06, R09, R12), no mesmo estilo, com os valores mínimos que a disparam.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m unittest tests.test_regras_duplicatas -v`
Expected: FAIL por `regras/duplicatas.json` inexistente.

- [ ] **Step 3: Escrever `regras/duplicatas.json` pela tabela acima**

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m unittest discover -s tests -v`
Expected: todos OK, incluindo `test_bate_com_gabarito`.

- [ ] **Step 5: Commit**

```bash
git add regras tests/test_regras_duplicatas.py
git commit -m "Traduz as 12 regras de duplicatas para o arquivo de regras"
```

---

### Task 4: Linha de comando

**Files:**
- Modify: `motor.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `carregar_regras`, `ErroRegras` (Task 2); `regras/duplicatas.json` (Task 3).
- Produces: `classificar(linhas: Iterable[str], regras, sem_regra: str, avisar: Callable[[str], None]) -> list[str]` (linhas de saída sem `\n`); `main(argv: list[str] | None = None) -> int`. Uso: `python motor.py --entrada <arquivo> [--regras <arquivo>]`. Padrão de `--regras`: `regras/duplicatas.json` relativo à pasta de `motor.py`.

Saída: `id:<id> - regra: <código>`. `id` texto sai sem aspas; `id` número sai como `str(valor)`. Linha vazia: ignorada sem aviso. JSON inválido, não objeto ou sem `id`: ignorada com aviso `linha <n>: <motivo>` no stderr. `ErroRegras`: mensagem no stderr, retorno 2, nada no stdout.

- [ ] **Step 1: Escrever os testes**

Rodar o motor por `subprocess.run([sys.executable, MOTOR, ...], cwd=<pasta temporária>)`, com `MOTOR` como caminho absoluto. Isso prova a Review Focus 2.

```python
def test_contrato_basico(self):      # 2 linhas → "id:1 - regra: SEM_REGRA" e "id:2 - regra: R01"
def test_bom_crlf_e_acento(self):     # arquivo escrito em bytes: b"\xef\xbb\xbf" + linha com "São" + b"\r\n"; classifica todas; stdout sem "\r"
def test_linha_invalida_nao_para(self):  # "{quebrado", "[1]", '{"x":1}' e uma válida → só a válida no stdout; 3 avisos no stderr; retorno 0
def test_id_texto_sem_aspas(self):    # {"id": "7", ...} → "id:7 - regra: ..."
def test_id_repetido(self):           # duas linhas com id 5 → duas linhas de saída
def test_regras_invalidas(self):      # --regras com op desconhecido → retorno 2, stdout vazio
def test_roda_de_outra_pasta(self):   # sem --regras, cwd temporário → retorno 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL (motor sem `main`).

- [ ] **Step 3: Implementar `classificar` e `main` em `motor.py`, com `if __name__ == "__main__": sys.exit(main())`**

Abrir a entrada com `encoding="utf-8-sig"` e `newline=None`; escrever tudo com um único `sys.stdout.write("\n".join(saida) + "\n")` depois de `sys.stdout.reconfigure(newline="\n")`, para não gerar `\r\n` no Windows.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m unittest discover -s tests -v`
Expected: todos OK.

- [ ] **Step 5: Validar com o kit, sem Docker**

Run: `python kit/medir.py --set pequeno --cmd "python motor.py --entrada {entrada}"` e depois `--set grande`
Expected: `acertos: 100 (100.00%)` e `acertos: 200000 (100.00%)`; `ids ausentes: 0`; `linhas inválidas: 0`.

- [ ] **Step 6: Commit**

```bash
git add motor.py tests/test_cli.py
git commit -m "Adiciona linha de comando do motor"
```

---

### Task 5: Docker, prova de genérico e evidências

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `regras/exemplo_ordem_invertida.json`, `evidencias/pequeno.txt`, `evidencias/grande.txt`
- Test: `tests/test_generico.py`

**Interfaces:**
- Consumes: `main` (Task 4).
- Produces: imagem `motor` com `ENTRYPOINT ["python", "/app/motor.py"]`, que aceita `--entrada /dados/<arquivo>`.

- [ ] **Step 1: Escrever o teste de genérico**

`regras/exemplo_ordem_invertida.json` é `duplicatas.json` com R11 movida para antes de R01. O teste roda o motor com `--regras` apontando para ele sobre uma duplicata `CANCELADA` com `ACTO` e `migo: true` e espera `R11`. Com as regras padrão, a mesma duplicata dá `R01`.

- [ ] **Step 2: Rodar e ver passar**

Run: `python -m unittest tests.test_generico -v`
Expected: OK (nenhuma mudança no motor é necessária; se falhar, o motor tem regra embutida).

- [ ] **Step 3: Escrever `Dockerfile` (`python:3.13-slim`, `WORKDIR /app`, copia `motor.py` e `regras/`) e `.dockerignore` (exclui `kit/`, `tests/`, `docs/`, `evidencias/`, `.git/`)**

- [ ] **Step 4: Gerar as evidências via Docker com 1 CPU**

Run:
```bash
docker build -t motor .
```
```bash
python kit/medir.py --set pequeno --cmd "docker run --rm --cpus=1 -v {dir}:/dados motor --entrada /dados/{arquivo}" > evidencias/pequeno.txt
```
```bash
python kit/medir.py --set grande --cmd "docker run --rm --cpus=1 -v {dir}:/dados motor --entrada /dados/{arquivo}" > evidencias/grande.txt
```
Expected: 100% de acertos nos dois arquivos, zero ids ausentes e zero linhas inválidas. Anotar no topo de cada arquivo a máquina (CPU, sistema, versão do Docker).

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore regras/exemplo_ordem_invertida.json tests/test_generico.py evidencias
git commit -m "Adiciona Dockerfile, prova de genérico e evidências"
```

---

### Task 6: README e diário

**Files:**
- Modify: `README.md`, `docs/diario-ia.md`

- [ ] **Step 1: Preencher as seções 2 a 5 do `README.md`** com o fluxo, o formato das regras (o exemplo de R07), a tabela de operadores e tipos, a tabela de casos não definidos do desenho, os comandos de reprodução (testes, `medir.py` local e via Docker) e os números reais de `evidencias/`. A seção 5 sai do `docs/diario-ia.md`.

- [ ] **Step 2: Conferir a reprodução numa pasta limpa**

Run: `git clone` do repositório numa pasta temporária, depois `docker build -t motor .` e o comando do set pequeno do README.
Expected: 100% de acertos sem passos fora do README.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/diario-ia.md
git commit -m "Preenche README com solução, reprodução e evidências"
```

---

### Task 7: Desempenho (depois das Tasks 1 a 6)

**Files:**
- Modify: `motor.py`, `Dockerfile`, `evidencias/grande.txt`, `README.md`

Cada tentativa é uma rodada: medir com o comando Docker do set grande, mudar uma coisa, rodar `python -m unittest discover -s tests -v`, medir de novo, manter só se a mediana cair e os testes passarem. Candidatos na ordem do desenho: ler a entrada em bloco (`f.read().splitlines()`), iniciar o Python com `-S` no `ENTRYPOINT`, reduzir chamadas por condição (pré-resolver o primeiro nível do caminho). Registrar cada rodada (antes, depois, mantida ou não) no README.

- [ ] **Step 1: Medição de base registrada**
- [ ] **Step 2: Uma rodada por candidato, com commit quando mantida**

```bash
git add motor.py Dockerfile evidencias README.md
git commit -m "Otimiza <o quê>: mediana <antes>s → <depois>s"
```

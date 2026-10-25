"""Compara o motor Go com o motor Python em linhas do set pequeno com defeitos plantados.

Uso: python tests/comparar_motores.py --go ./motor [--casos 20000] [--semente 1]

Cada linha recebe de 1 a 4 mutações sobre os campos que as regras usam: tipo trocado,
nulo, campo ausente, data inválida, valor no limite, chave repetida, NaN, escape unicode.
Sai com código 1 se as duas saídas divergirem em alguma linha.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR_PY = os.path.join(RAIZ, "motor.py")
PEQUENO = os.path.join(RAIZ, "kit", "dados", "pequeno", "entrada.jsonl")

CAMPOS = [
    "status", "data_vencimento", "sacador.porte", "sacado.segmento",
    "financeiro.valor", "financeiro.valor_pago", "financeiro.tipo_negociacao",
    "pagamento.instrumento", "fiscal.cfop", "logistica.modal", "logistica.uf_origem",
    "logistica.uf_destino", "logistica.peso_kg", "logistica.status_entrega",
    "logistica.migo", "manifestacao.tipo",
]
BLOCOS = ["sacador", "sacado", "financeiro", "pagamento", "fiscal", "logistica", "manifestacao"]

VALORES = {
    "status": ["ATIVA", "LIQUIDADA", "CANCELADA", "ativa", "Cancelada", " LIQUIDADA", ""],
    "data_vencimento": ["2026-10-22", "2026-10-23", "2026-10-24", "2026-02-30", "2024-02-29",
                        "2023-02-29", "2026-1-5", "20261022", "2026-10-22T00:00:00", "22/10/2026",
                        "0000-01-01", "2026-13-01", "2026-00-10", "", 20261022],
    "sacador.porte": ["ME", "EPP", "MEDIA", "GRANDE", "me", "Me", ""],
    "sacado.segmento": ["AGRO", "agro", "VAREJO", " AGRO", ""],
    "financeiro.tipo_negociacao": ["CSFD", "PENR", "CSCO", "csfd", ""],
    "pagamento.instrumento": ["PPIX", "ppix", "BOLETO", "TRCR", ""],
    "fiscal.cfop": ["5102", "6102", 5102, 5.102, "05102", " 5102", "5", ""],
    "logistica.modal": ["AEREO", "aereo", "AÉREO", "RODOVIARIO", ""],
    "logistica.uf_origem": ["SP", "MT", "sp", "", 35],
    "logistica.uf_destino": ["SP", "MT", "sp", "", 35],
    "logistica.status_entrega": ["ENTREGUE", "DEVOLVIDA", "AVARIADA", "EM_TRANSITO", "entregue", ""],
    "logistica.migo": [True, False, "true", "false", 0, 1, "", []],
    "manifestacao.tipo": ["ACTO", "RCOP", "RCAV", "RCQQ", "RCVN", "RCVL", "ANTC", "acto", "", " "],
}
NUMEROS = [0, 0.0, -0.0, 1, 499.99, 500, 500.0, 500.01, 4999.99, 5000, 5000.0, 5000.01,
           99999.99, 100000, 100000.0, 100000.01, 199999.99, 200000, 500000, 499999.99,
           1e5, 5e5, 10 ** 20, -1, "100000", "5000.00", True, False]
CRUS = ["NaN", "Infinity", "-Infinity", "1e400", "-1e400", "1E5", "5.0E5", "1e-400",
        "100000.000000000000001", "123456789012345678901234567890"]


def pegar(doc, caminho):
    alvo = doc
    for p in caminho[:-1]:
        if type(alvo.get(p)) is not dict:
            alvo[p] = {}
        alvo = alvo[p]
    return alvo


def mutar(doc, rnd):
    """Aplica uma mutação ao dicionário; devolve um trecho cru a injetar no texto, se houver."""
    tipo = rnd.random()
    campo = rnd.choice(CAMPOS)
    caminho = campo.split(".")
    alvo = pegar(doc, caminho)
    folha = caminho[-1]
    if tipo < 0.12:
        alvo[folha] = None
    elif tipo < 0.22:
        alvo.pop(folha, None)
    elif tipo < 0.30:
        doc[rnd.choice(BLOCOS)] = rnd.choice([None, [], "x", 1, {}])
    elif tipo < 0.65:
        if campo in VALORES:
            alvo[folha] = rnd.choice(VALORES[campo])
        else:
            alvo[folha] = rnd.choice(NUMEROS)
    elif tipo < 0.72:
        alvo[folha] = rnd.choice(NUMEROS)
    elif tipo < 0.82:
        if folha in ("valor", "valor_pago", "peso_kg"):
            return ("cru", caminho, rnd.choice(CRUS))
        alvo[folha] = rnd.choice(VALORES.get(campo, NUMEROS))
    elif tipo < 0.90:
        valor = rnd.choice(VALORES.get(campo, NUMEROS))
        return ("repetida", caminho, json.dumps(valor))
    else:
        valor = alvo.get(folha)
        if type(valor) is str and valor:
            return ("escape", caminho, valor)
    return None


def serializar(doc, extra):
    texto = json.dumps(doc, ensure_ascii=False)
    for tipo, caminho, crua in extra:
        bloco = caminho[0] if len(caminho) > 1 else None
        if tipo == "repetida":
            chave = json.dumps(caminho[-1])
            if bloco and type(doc.get(bloco)) is dict:
                # repete a chave dentro do bloco, antes do fechamento dele
                marca = json.dumps(bloco) + ": "
                i = texto.find(marca)
                if i < 0:
                    continue
                fim = texto.index("}", i)
                sep = ", " if texto[fim - 1] != "{" else ""
                texto = texto[:fim] + sep + chave + ": " + crua + texto[fim:]
            elif not bloco:
                texto = texto[:-1] + ", " + chave + ": " + crua + "}"
        elif tipo in ("cru", "escape"):
            alvo = doc
            for p in caminho[:-1]:
                alvo = alvo.get(p) if type(alvo) is dict else None
            if type(alvo) is not dict or caminho[-1] not in alvo:
                continue
            atual = json.dumps(alvo[caminho[-1]], ensure_ascii=False)
            chave = json.dumps(caminho[-1]) + ": "
            novo = crua if tipo == "cru" else '"' + "".join(f"\\u{ord(c):04x}" for c in crua) + '"'
            i = texto.find(chave + atual)
            if i >= 0:
                texto = texto[:i] + chave + novo + texto[i + len(chave) + len(atual):]
    return texto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", required=True, help="binário do motor Go")
    ap.add_argument("--casos", type=int, default=20000)
    ap.add_argument("--semente", type=int, default=1)
    a = ap.parse_args()
    rnd = random.Random(a.semente)
    with open(PEQUENO, encoding="utf-8") as f:
        base = [json.loads(l) for l in f if l.strip()]

    linhas = []
    for n in range(1, a.casos + 1):
        doc = json.loads(json.dumps(rnd.choice(base)))
        doc["id"] = n
        extra = [e for e in (mutar(doc, rnd) for _ in range(rnd.randint(1, 4))) if e]
        linhas.append(serializar(doc, extra))
    # linhas que nem chegam a ser classificadas
    linhas += ['{"id": 900001, "status": "CANCELADA",}', "[1, 2]", "", "   ", '{"status": "CANCELADA"}',
               '{"id": null}', '{"id": "abc", "status": "LIQUIDADA"}', '{"id": 900002.5}',
               '{"id": 9e2}', '{"id": 900003, "id": 900004}']

    with tempfile.TemporaryDirectory() as pasta:
        entrada = os.path.join(pasta, "entrada.jsonl")
        with open(entrada, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(linhas) + "\n")
        py = subprocess.run([sys.executable, MOTOR_PY, "--entrada", entrada], capture_output=True)
        go = subprocess.run([a.go, "--entrada", entrada, "--regras",
                             os.path.join(RAIZ, "regras", "duplicatas.json")], capture_output=True)
    if py.returncode != 0 or go.returncode != 0:
        sys.exit(f"falha: python {py.returncode} {py.stderr[-500:]!r} / go {go.returncode} {go.stderr[-500:]!r}")
    saida_py = py.stdout.decode("utf-8").splitlines()
    saida_go = go.stdout.decode("utf-8").splitlines()
    divergentes = [(p, g) for p, g in zip(saida_py, saida_go) if p != g]
    contagem = {}
    for l in saida_py:
        contagem[l.rsplit(" ", 1)[-1]] = contagem.get(l.rsplit(" ", 1)[-1], 0) + 1
    print(f"linhas geradas:   {len(linhas)}")
    print(f"saídas python:    {len(saida_py)}")
    print(f"saídas go:        {len(saida_go)}")
    print(f"avisos iguais:    {py.stderr == go.stderr}")
    print(f"divergências:     {len(divergentes) + abs(len(saida_py) - len(saida_go))}")
    print("regras (python):  " + ", ".join(f"{k}={v}" for k, v in sorted(contagem.items())))
    for p, g in divergentes[:10]:
        print(f"  python: {p}  |  go: {g}")
    if divergentes or len(saida_py) != len(saida_go):
        sys.exit(1)


if __name__ == "__main__":
    main()

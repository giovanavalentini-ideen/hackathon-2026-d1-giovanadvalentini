"""Motor de regras: classifica cada linha de um JSON Lines pela primeira regra satisfeita.

As regras vêm de um arquivo JSON; este módulo não conhece nenhuma regra de domínio.
"""
import argparse
import datetime
import json
import math
import operator
import os
import re
import sys

AUSENTE = object()

_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def resolver(doc, caminho):
    """Desce por objetos aninhados; qualquer nível ausente, nulo ou não objeto dá AUSENTE."""
    atual = doc
    for chave in caminho:
        if type(atual) is not dict:
            return AUSENTE
        atual = atual.get(chave, AUSENTE)
        if atual is None:
            return AUSENTE
    return atual


def _numero(v):
    return (type(v) is int or type(v) is float) and math.isfinite(v)


def _texto(v):
    return type(v) is str


def _data(v):
    if type(v) is not str or not _DATA.fullmatch(v):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _booleano(v):
    return type(v) is bool


VALIDADORES = {"numero": _numero, "texto": _texto, "data": _data, "booleano": _booleano}


def valido(valor, tipo):
    return VALIDADORES[tipo](valor)


class ErroRegras(Exception):
    pass


def _em(valor, opcoes):
    return valor in opcoes


def _comeca_com(valor, prefixo):
    return valor.startswith(prefixo)


# operador -> (função de comparação, tipos aceitos)
OPERADORES = {
    "igual": (operator.eq, {"numero", "texto", "data", "booleano"}),
    "diferente": (operator.ne, {"numero", "texto", "data", "booleano"}),
    "menor": (operator.lt, {"numero", "data"}),
    "menor_igual": (operator.le, {"numero", "data"}),
    "maior": (operator.gt, {"numero", "data"}),
    "maior_igual": (operator.ge, {"numero", "data"}),
    "em": (_em, {"texto"}),
    "comeca_com": (_comeca_com, {"texto"}),
}


def _caminho(cond):
    campo = cond.get("campo")
    if type(campo) is not str or not campo:
        raise ErroRegras(f"condição sem 'campo': {cond}")
    return tuple(campo.split("."))


def _vazio(cond):
    caminho = _caminho(cond)

    def teste(doc):
        v = resolver(doc, caminho)
        return v is AUSENTE or (type(v) is str and v == "")
    return teste


def _comparacao(cond):
    caminho = _caminho(cond)
    op, tipo = cond.get("op"), cond.get("tipo")
    if tipo not in VALIDADORES:
        raise ErroRegras(f"tipo desconhecido {tipo!r}: {cond}")
    if op not in OPERADORES:
        raise ErroRegras(f"operador desconhecido {op!r}: {cond}")
    compara, tipos = OPERADORES[op]
    if tipo not in tipos:
        raise ErroRegras(f"operador {op!r} não aceita tipo {tipo!r}: {cond}")
    eh = VALIDADORES[tipo]

    if "outro_campo" in cond:
        if op == "em":
            raise ErroRegras(f"'em' exige 'valor' com lista: {cond}")
        outro = _caminho({"campo": cond["outro_campo"]})

        def teste(doc):
            a = resolver(doc, caminho)
            if not eh(a):
                return False
            b = resolver(doc, outro)
            return eh(b) and compara(a, b)
        return teste

    if "valor" not in cond:
        raise ErroRegras(f"condição sem 'valor' nem 'outro_campo': {cond}")
    constante = cond["valor"]
    if op == "em":
        if type(constante) is not list or not constante or not all(eh(x) for x in constante):
            raise ErroRegras(f"'em' exige lista não vazia de {tipo}: {cond}")
        constante = frozenset(constante)
    elif not eh(constante):
        raise ErroRegras(f"'valor' não é do tipo {tipo}: {cond}")

    def teste(doc):
        a = resolver(doc, caminho)
        return eh(a) and compara(a, constante)
    return teste


def _combinacao(chave, cond):
    partes = cond[chave]
    if type(partes) is not list or not partes:
        raise ErroRegras(f"'{chave}' exige lista não vazia: {cond}")
    testes = [compilar_condicao(p) for p in partes]
    if chave == "e":
        def teste(doc):
            for t in testes:
                if not t(doc):
                    return False
            return True
    else:
        def teste(doc):
            for t in testes:
                if t(doc):
                    return True
            return False
    return teste


def compilar_condicao(cond):
    """Transforma uma condição do arquivo de regras numa função doc -> bool."""
    if type(cond) is not dict:
        raise ErroRegras(f"condição não é objeto: {cond!r}")
    for chave in ("e", "ou"):
        if chave in cond:
            return _combinacao(chave, cond)
    if cond.get("op") == "vazio":
        return _vazio(cond)
    return _comparacao(cond)


def carregar_regras(caminho):
    """Lê o arquivo de regras e devolve ([(codigo, teste), ...] em ordem, texto de sem_regra)."""
    try:
        with open(caminho, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise ErroRegras(f"não foi possível ler {caminho}: {e}") from e
    if type(doc) is not dict or type(doc.get("regras")) is not list:
        raise ErroRegras("o arquivo de regras precisa ter a lista 'regras'")
    regras = []
    for r in doc["regras"]:
        if type(r) is not dict or type(r.get("codigo")) is not str or "quando" not in r:
            raise ErroRegras(f"regra precisa de 'codigo' e 'quando': {r!r}")
        regras.append((r["codigo"], compilar_condicao(r["quando"])))
    return regras, doc.get("sem_regra", "SEM_REGRA")


def classificar(linhas, regras, sem_regra, avisar):
    """Devolve as linhas de saída 'id:<id> - regra: <código>' na ordem da entrada."""
    saida = []
    for n, texto in enumerate(linhas, 1):
        if not texto.strip():
            continue
        try:
            doc = json.loads(texto)
        except ValueError:
            avisar(f"linha {n}: JSON inválido")
            continue
        if type(doc) is not dict:
            avisar(f"linha {n}: não é um objeto JSON")
            continue
        ident = doc.get("id")
        if ident is None:
            avisar(f"linha {n}: sem id")
            continue
        codigo = sem_regra
        for cod, teste in regras:
            if teste(doc):
                codigo = cod
                break
        saida.append(f"id:{ident} - regra: {codigo}")
    return saida


REGRAS_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regras", "duplicatas.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classifica duplicatas pela primeira regra satisfeita.")
    parser.add_argument("--entrada", required=True, help="arquivo JSON Lines, uma duplicata por linha")
    parser.add_argument("--regras", default=REGRAS_PADRAO, help="arquivo de regras (padrão: regras/duplicatas.json)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")

    def avisar(msg):
        print(msg, file=sys.stderr)

    try:
        regras, sem_regra = carregar_regras(args.regras)
    except ErroRegras as e:
        avisar(f"erro nas regras: {e}")
        return 2
    with open(args.entrada, encoding="utf-8-sig") as f:
        saida = classificar(f, regras, sem_regra, avisar)
    if saida:
        sys.stdout.write("\n".join(saida) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

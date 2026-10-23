"""Motor de regras: classifica cada linha de um JSON Lines pela primeira regra satisfeita.

As regras vêm de um arquivo JSON; este módulo não conhece nenhuma regra de domínio.
"""
import datetime
import math
import re

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

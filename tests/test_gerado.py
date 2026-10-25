"""O classificador gerado precisa concordar com uma leitura direta do arquivo de regras."""
import copy
import json
import operator
import os
import random
import unittest

from motor import (AUSENTE, Reler, _ler_regras, gerar_classificador, resolver, valido)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGRAS, SEM_REGRA = _ler_regras(os.path.join(RAIZ, "regras", "duplicatas.json"))
RAPIDA = gerar_classificador(REGRAS, SEM_REGRA, rapido=True)
EXATA = gerar_classificador(REGRAS, SEM_REGRA)

with open(os.path.join(RAIZ, "kit", "dados", "pequeno", "entrada.jsonl"), encoding="utf-8") as _f:
    BASES = [json.loads(l) for l in _f if l.strip()]

COMPARA = {"igual": operator.eq, "diferente": operator.ne, "menor": operator.lt,
           "menor_igual": operator.le, "maior": operator.gt, "maior_igual": operator.ge,
           "em": lambda a, b: a in b, "comeca_com": lambda a, b: a.startswith(b)}


def referencia(cond, doc):
    """Interpretação literal da seção Semântica do enunciado, sem nada gerado."""
    if "e" in cond:
        return all(referencia(c, doc) for c in cond["e"])
    if "ou" in cond:
        return any(referencia(c, doc) for c in cond["ou"])
    a = resolver(doc, cond["campo"].split("."))
    if cond["op"] == "vazio":
        return a is AUSENTE or a == ""
    if not valido(a, cond["tipo"]):
        return False
    if "outro_campo" in cond:
        b = resolver(doc, cond["outro_campo"].split("."))
        if not valido(b, cond["tipo"]):
            return False
    else:
        b = cond["valor"]
    return COMPARA[cond["op"]](a, b)


def classificar_referencia(doc):
    for codigo, quando in REGRAS:
        if referencia(quando, doc):
            return codigo
    return SEM_REGRA


def _campos(cond):
    if "e" in cond or "ou" in cond:
        for c in cond.get("e", cond.get("ou")):
            yield from _campos(c)
        return
    yield cond["campo"]
    if "outro_campo" in cond:
        yield cond["outro_campo"]


CAMPOS = sorted({c for _, q in REGRAS for c in _campos(q)} | {"logistica", "financeiro", "manifestacao"})
VALORES = [None, "", " ", "ATIVA", "CANCELADA", "LIQUIDADA", "cancelada", "DEVOLVIDA", "AVARIADA",
           "ENTREGUE", "RCOP", "RCAV", "ACTO", "CSFD", "PENR", "AGRO", "AEREO", "PPIX", "ME", "EPP",
           "SP", "MT", "5102", "6102", 5102, "2026-10-22", "2026-10-23", "2026-02-30", "2026-1-01",
           0, 1, 500, 500.0001, 5000, 5000.01, 99999.99, 100000, 100000.0, 200000, 499999.99, 500000,
           -1, 1e300, 2 ** 70, -(2 ** 70), True, False, "true", "false", "15000.00", float("nan"),
           float("inf"), float("-inf"), [], {}, ["CSFD"], {"tipo": "ACTO"}]


def _ajustar(doc, campo, valor, rnd):
    *pais, folha = campo.split(".")
    alvo = doc
    for p in pais:
        if type(alvo.get(p)) is not dict:
            alvo[p] = {}
        alvo = alvo[p]
    if rnd.random() < 0.15:
        alvo.pop(folha, None)
    else:
        alvo[folha] = valor


class GeradoIgualReferencia(unittest.TestCase):
    def test_set_pequeno(self):
        for doc in BASES:
            esperado = classificar_referencia(doc)
            self.assertEqual(EXATA(doc), esperado, doc["id"])
            self.assertEqual(RAPIDA(doc), esperado, doc["id"])

    def test_mutacoes_aleatorias(self):
        rnd = random.Random(2026)
        for i in range(20000):
            doc = copy.deepcopy(rnd.choice(BASES))
            for _ in range(rnd.randint(1, 6)):
                _ajustar(doc, rnd.choice(CAMPOS), rnd.choice(VALORES), rnd)
            esperado = classificar_referencia(doc)
            self.assertEqual(EXATA(doc), esperado, (i, doc))
            try:
                self.assertEqual(RAPIDA(doc), esperado, (i, doc))
            except Reler:
                pass  # float >= 2**63: o motor relê a linha com json e usa EXATA

    def test_rapida_pede_releitura_de_float_enorme(self):
        doc = copy.deepcopy(BASES[0])
        doc["financeiro"]["valor"] = 1.8446744073709552e19
        doc["status"] = "ATIVA"
        with self.assertRaises(Reler):
            RAPIDA(doc)


if __name__ == "__main__":
    unittest.main()

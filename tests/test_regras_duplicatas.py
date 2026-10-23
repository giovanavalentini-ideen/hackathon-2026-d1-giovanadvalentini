import copy
import json
import os
import unittest

from motor import carregar_regras

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGRAS, SEM_REGRA = carregar_regras(os.path.join(RAIZ, "regras", "duplicatas.json"))
PEQUENO = os.path.join(RAIZ, "kit", "dados", "pequeno")

# Linha id:1 do set pequeno, que o gabarito marca SEM_REGRA.
with open(os.path.join(PEQUENO, "entrada.jsonl"), encoding="utf-8") as _f:
    BASE = json.loads(_f.readline())


def classificar_doc(doc):
    for codigo, teste in REGRAS:
        if teste(doc):
            return codigo
    return SEM_REGRA


def com(**ajustes):
    """Cópia de BASE com campos trocados; a chave usa '.' como separador e None grava null."""
    doc = copy.deepcopy(BASE)
    for caminho, valor in ajustes.items():
        *pais, folha = caminho.split(".")
        alvo = doc
        for p in pais:
            alvo = alvo[p]
        alvo[folha] = valor
    return doc


class CadaRegra(unittest.TestCase):
    def test_base_sem_regra(self):
        self.assertEqual(classificar_doc(BASE), "SEM_REGRA")

    def test_r01(self):
        self.assertEqual(classificar_doc(com(status="LIQUIDADA")), "R01")

    def test_r01_minusculo_nao_dispara(self):
        self.assertEqual(classificar_doc(com(status="liquidada")), "SEM_REGRA")

    def test_r02_por_entrega(self):
        self.assertEqual(classificar_doc(com(**{"logistica.status_entrega": "DEVOLVIDA"})), "R02")

    def test_r02_por_manifestacao(self):
        self.assertEqual(classificar_doc(com(**{"manifestacao.tipo": "RCOP", "logistica.status_entrega": None})), "R02")

    def test_r03(self):
        self.assertEqual(classificar_doc(com(**{"manifestacao.tipo": "RCVN"})), "R03")

    def test_r04_texto_vazio(self):
        self.assertEqual(classificar_doc(com(**{"logistica.status_entrega": "AVARIADA", "manifestacao.tipo": ""})), "R04")

    def test_r04_bloco_manifestacao_ausente(self):
        self.assertEqual(classificar_doc(com(**{"logistica.status_entrega": "AVARIADA", "manifestacao": None})), "R04")

    def test_r05(self):
        self.assertEqual(classificar_doc(com(**{"data_vencimento": "2026-10-22", "financeiro.valor_pago": 0.0})), "R05")

    def test_r05_vence_na_data_de_referencia(self):
        self.assertEqual(classificar_doc(com(**{"data_vencimento": "2026-10-23", "financeiro.valor_pago": 0.0})), "SEM_REGRA")

    def test_r05_texto_no_valor(self):
        self.assertEqual(classificar_doc(com(**{"data_vencimento": "2026-10-22", "financeiro.valor": "27821.81",
                                                "financeiro.valor_pago": 0.0})), "SEM_REGRA")

    def test_r06(self):
        self.assertEqual(classificar_doc(com(**{"financeiro.tipo_negociacao": "PENR", "financeiro.valor": 100000,
                                                "financeiro.valor_pago": 100000})), "R06")

    def test_r07_limite_int_e_float(self):
        for v in (500000, 500000.0):
            self.assertEqual(classificar_doc(com(**{"financeiro.valor": v, "financeiro.valor_pago": v})), "R07", v)

    def test_r07_agro(self):
        self.assertEqual(classificar_doc(com(**{"sacado.segmento": "AGRO", "financeiro.valor": 200000,
                                                "financeiro.valor_pago": 200000})), "R07")

    def test_r08(self):
        self.assertEqual(classificar_doc(com(**{"logistica.uf_destino": "PR"})), "R08")

    def test_r08_uf_ausente(self):
        self.assertEqual(classificar_doc(com(**{"logistica.uf_destino": None})), "SEM_REGRA")

    def test_r08_cfop_numerico(self):
        self.assertEqual(classificar_doc(com(**{"logistica.uf_destino": "PR", "fiscal.cfop": 5102})), "SEM_REGRA")

    def test_r09_e_limite(self):
        self.assertEqual(classificar_doc(com(**{"logistica.modal": "AEREO", "logistica.peso_kg": 500.1})), "R09")
        self.assertEqual(classificar_doc(com(**{"logistica.modal": "AEREO", "logistica.peso_kg": 500})), "SEM_REGRA")

    def test_r10(self):
        self.assertEqual(classificar_doc(com(**{"logistica.migo": False})), "R10")

    def test_r10_migo_texto(self):
        self.assertEqual(classificar_doc(com(**{"logistica.migo": "false"})), "SEM_REGRA")

    def test_r11(self):
        self.assertEqual(classificar_doc(com(**{"manifestacao.tipo": "ACTO"})), "R11")

    def test_r12_limite(self):
        self.assertEqual(classificar_doc(com(**{"pagamento.instrumento": "PPIX", "sacador.porte": "EPP",
                                                "financeiro.valor": 5000, "financeiro.valor_pago": 5000})), "R12")


class Ordem(unittest.TestCase):
    def test_r01_vence_r11(self):
        self.assertEqual(classificar_doc(com(status="CANCELADA", **{"manifestacao.tipo": "ACTO"})), "R01")

    def test_minusculo_cai_para_r11(self):
        self.assertEqual(classificar_doc(com(status="cancelada", **{"manifestacao.tipo": "ACTO"})), "R11")


class SetPequeno(unittest.TestCase):
    def test_bate_com_gabarito(self):
        esperado = {}
        with open(os.path.join(PEQUENO, "gabarito.txt"), encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    ident, regra = linha.split(" - regra: ")
                    esperado[ident.split(":")[1]] = regra.strip()
        obtido = {}
        with open(os.path.join(PEQUENO, "entrada.jsonl"), encoding="utf-8") as f:
            for linha in f:
                doc = json.loads(linha)
                obtido[str(doc["id"])] = classificar_doc(doc)
        self.assertEqual(obtido, esperado)


if __name__ == "__main__":
    unittest.main()

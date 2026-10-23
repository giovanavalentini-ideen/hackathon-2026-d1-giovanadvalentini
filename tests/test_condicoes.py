import json
import os
import tempfile
import unittest

from motor import ErroRegras, carregar_regras, compilar_condicao


def c(**k):
    return compilar_condicao(k)


class Operadores(unittest.TestCase):
    def test_igual_exato(self):
        f = c(campo="s", tipo="texto", op="igual", valor="ATIVA")
        self.assertTrue(f({"s": "ATIVA"}))
        self.assertFalse(f({"s": "ativa"}))
        self.assertFalse(f({}))

    def test_diferente_com_ausente_ou_tipo_errado_e_falso(self):
        f = c(campo="a", tipo="texto", op="diferente", outro_campo="b")
        self.assertTrue(f({"a": "SP", "b": "MT"}))
        self.assertFalse(f({"a": "SP"}))
        self.assertFalse(f({"a": "SP", "b": 35}))
        self.assertFalse(f({"a": "SP", "b": "SP"}))

    def test_limites(self):
        self.assertTrue(c(campo="v", tipo="numero", op="maior_igual", valor=100)({"v": 100}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior", valor=100)({"v": 100}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior_igual", valor=100)({"v": "150"}))
        self.assertFalse(c(campo="v", tipo="numero", op="maior_igual", valor=1)({"v": True}))

    def test_menor_entre_campos(self):
        f = c(campo="pago", tipo="numero", op="menor", outro_campo="valor")
        self.assertTrue(f({"pago": 0.0, "valor": 10}))
        self.assertFalse(f({"pago": 10, "valor": 10}))
        self.assertFalse(f({"pago": 0.0, "valor": "10"}))

    def test_data_menor(self):
        f = c(campo="d", tipo="data", op="menor", valor="2026-10-23")
        self.assertTrue(f({"d": "2026-10-22"}))
        self.assertFalse(f({"d": "2026-10-23"}))
        self.assertFalse(f({"d": "2026-02-30"}))

    def test_em_e_comeca_com(self):
        self.assertTrue(c(campo="t", tipo="texto", op="em", valor=["A", "B"])({"t": "B"}))
        self.assertFalse(c(campo="t", tipo="texto", op="em", valor=["A", "B"])({"t": "b"}))
        f = c(campo="cfop", tipo="texto", op="comeca_com", valor="5")
        self.assertTrue(f({"cfop": "5102"}))
        self.assertFalse(f({"cfop": 5102}))
        self.assertFalse(f({"cfop": "6102"}))

    def test_booleano(self):
        f = c(campo="m", tipo="booleano", op="igual", valor=False)
        self.assertTrue(f({"m": False}))
        self.assertFalse(f({"m": 0}))
        self.assertFalse(f({"m": "false"}))
        g = c(campo="m", tipo="booleano", op="igual", valor=True)
        self.assertFalse(g({"m": 1}))

    def test_vazio(self):
        f = c(campo="x.t", op="vazio")
        for d in ({}, {"x": None}, {"x": {"t": None}}, {"x": {"t": ""}}):
            self.assertTrue(f(d), d)
        for d in ({"x": {"t": " "}}, {"x": {"t": 0}}, {"x": {"t": "ACTO"}}):
            self.assertFalse(f(d), d)

    def test_e_ou_parcial(self):
        f = compilar_condicao({"ou": [
            {"campo": "a", "tipo": "texto", "op": "igual", "valor": "X"},
            {"campo": "b", "tipo": "texto", "op": "igual", "valor": "Y"}]})
        self.assertTrue(f({"b": "Y"}))
        g = compilar_condicao({"e": [
            {"campo": "a", "tipo": "texto", "op": "igual", "valor": "X"},
            {"campo": "b", "op": "vazio"}]})
        self.assertTrue(g({"a": "X"}))
        self.assertFalse(g({"a": "X", "b": "Z"}))


class Invalidas(unittest.TestCase):
    def test_rejeita(self):
        for cond in ({"campo": "a", "tipo": "texto", "op": "parece", "valor": "x"},
                     {"campo": "a", "tipo": "moeda", "op": "igual", "valor": 1},
                     {"campo": "a", "tipo": "texto", "op": "maior", "valor": "x"},
                     {"campo": "a", "tipo": "texto", "op": "igual"},
                     {"campo": "a", "tipo": "numero", "op": "igual", "valor": "10"},
                     {"e": []}, {"ou": []}, {}):
            with self.assertRaises(ErroRegras, msg=cond):
                compilar_condicao(cond)


class Carga(unittest.TestCase):
    def _arquivo(self, doc):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(doc, f)
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_ordem_e_sem_regra(self):
        regras, sem = carregar_regras(self._arquivo({"sem_regra": "SEM_REGRA", "regras": [
            {"codigo": "A", "quando": {"campo": "x", "op": "vazio"}},
            {"codigo": "B", "quando": {"campo": "x", "tipo": "texto", "op": "igual", "valor": "1"}}]}))
        self.assertEqual([r[0] for r in regras], ["A", "B"])
        self.assertEqual(sem, "SEM_REGRA")
        self.assertTrue(regras[0][1]({}))

    def test_estrutura_invalida(self):
        for doc in ({}, {"regras": [{"quando": {"campo": "x", "op": "vazio"}}]},
                    {"regras": [{"codigo": "A"}]}):
            with self.assertRaises(ErroRegras, msg=doc):
                carregar_regras(self._arquivo(doc))


if __name__ == "__main__":
    unittest.main()

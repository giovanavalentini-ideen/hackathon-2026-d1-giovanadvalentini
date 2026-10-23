import unittest

from motor import AUSENTE, resolver, valido


class Resolver(unittest.TestCase):
    def test_caminho_aninhado(self):
        self.assertEqual(resolver({"a": {"b": 5}}, ("a", "b")), 5)

    def test_ausente_nulo_e_nao_objeto(self):
        for doc in ({}, {"a": None}, {"a": "x"}, {"a": {}}):
            self.assertIs(resolver(doc, ("a", "b")), AUSENTE, doc)

    def test_folha_nula_e_ausente(self):
        self.assertIs(resolver({"a": None}, ("a",)), AUSENTE)


class Valido(unittest.TestCase):
    def test_numero(self):
        self.assertTrue(valido(5, "numero"))
        self.assertTrue(valido(5.5, "numero"))
        for v in (True, False, "15000.00", float("nan"), float("inf"), AUSENTE):
            self.assertFalse(valido(v, "numero"), v)

    def test_texto(self):
        self.assertTrue(valido("", "texto"))
        for v in (5102, None, True, AUSENTE):
            self.assertFalse(valido(v, "texto"), v)

    def test_data(self):
        self.assertTrue(valido("2026-10-23", "data"))
        self.assertTrue(valido("2024-02-29", "data"))
        for v in ("2026-02-30", "2026-1-5", "20261023", "2026-10-23T00:00",
                  " 2026-10-23", "2026-10-23\n", 20261023, AUSENTE):
            self.assertFalse(valido(v, "data"), v)

    def test_booleano(self):
        self.assertTrue(valido(True, "booleano"))
        self.assertTrue(valido(False, "booleano"))
        for v in ("false", 0, 1, None, AUSENTE):
            self.assertFalse(valido(v, "booleano"), v)


if __name__ == "__main__":
    unittest.main()

import json
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(RAIZ, "motor.py")

ATIVA = {"id": 1, "status": "ATIVA"}
CANCELADA = {"id": 2, "status": "CANCELADA"}


def linha(doc):
    return json.dumps(doc, ensure_ascii=False)


class Cli(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)

    def rodar(self, conteudo, *extra):
        entrada = os.path.join(self.pasta.name, "entrada.jsonl")
        with open(entrada, "wb") as f:
            f.write(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
        return subprocess.run([sys.executable, MOTOR, "--entrada", entrada, *extra],
                              cwd=self.pasta.name, capture_output=True)

    def saida(self, p):
        return p.stdout.decode("utf-8").splitlines()

    def test_contrato_basico(self):
        p = self.rodar(linha(ATIVA) + "\n" + linha(CANCELADA) + "\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.saida(p), ["id:1 - regra: SEM_REGRA", "id:2 - regra: R01"])

    def test_bom_crlf_e_acento(self):
        corpo = (linha({"id": 1, "status": "CANCELADA", "obs": "São Paulo"}) + "\r\n"
                 + linha(ATIVA | {"id": 2}) + "\r\n").encode("utf-8")
        p = self.rodar(b"\xef\xbb\xbf" + corpo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn(b"\r", p.stdout)
        self.assertEqual(self.saida(p), ["id:1 - regra: R01", "id:2 - regra: SEM_REGRA"])

    def test_linha_invalida_nao_para(self):
        p = self.rodar("{quebrado\n[1]\n" + '{"x": 1}\n' + "\n" + linha(CANCELADA) + "\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.saida(p), ["id:2 - regra: R01"])
        avisos = p.stderr.decode("utf-8").splitlines()
        self.assertEqual(len(avisos), 3, avisos)
        self.assertTrue(avisos[0].startswith("linha 1:"), avisos)

    def test_id_texto_sem_aspas(self):
        p = self.rodar(linha({"id": "7", "status": "ATIVA"}) + "\n")
        self.assertEqual(self.saida(p), ["id:7 - regra: SEM_REGRA"])

    def test_id_repetido(self):
        p = self.rodar(linha(ATIVA | {"id": 5}) + "\n" + linha(CANCELADA | {"id": 5}) + "\n")
        self.assertEqual(self.saida(p), ["id:5 - regra: SEM_REGRA", "id:5 - regra: R01"])

    def test_entrada_vazia(self):
        p = self.rodar("")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, b"")

    def test_regras_invalidas(self):
        regras = os.path.join(self.pasta.name, "regras.json")
        with open(regras, "w", encoding="utf-8") as f:
            json.dump({"regras": [{"codigo": "X", "quando": {"campo": "a", "tipo": "texto", "op": "parece", "valor": "b"}}]}, f)
        p = self.rodar(linha(ATIVA) + "\n", "--regras", regras)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, b"")
        self.assertIn(b"parece", p.stderr)

    def test_roda_de_outra_pasta(self):
        p = self.rodar(linha(CANCELADA) + "\n")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.saida(p), ["id:2 - regra: R01"])


if __name__ == "__main__":
    unittest.main()

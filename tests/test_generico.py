import json
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(RAIZ, "motor.py")
INVERTIDA = os.path.join(RAIZ, "regras", "exemplo_ordem_invertida.json")

# Satisfaz R01 (CANCELADA) e R11 (ACTO com migo verdadeiro).
DUPLICATA = {"id": 1, "status": "CANCELADA", "manifestacao": {"tipo": "ACTO"}, "logistica": {"migo": True}}


class Generico(unittest.TestCase):
    def rodar(self, *extra):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = os.path.join(pasta, "entrada.jsonl")
            with open(entrada, "w", encoding="utf-8") as f:
                f.write(json.dumps(DUPLICATA) + "\n")
            p = subprocess.run([sys.executable, MOTOR, "--entrada", entrada, *extra], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.decode("utf-8").strip()

    def test_regras_padrao_classificam_r01(self):
        self.assertEqual(self.rodar(), "id:1 - regra: R01")

    def test_trocar_a_ordem_no_arquivo_muda_a_classificacao(self):
        self.assertEqual(self.rodar("--regras", INVERTIDA), "id:1 - regra: R11")


if __name__ == "__main__":
    unittest.main()

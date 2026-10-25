"""Motor de regras: classifica cada linha de um JSON Lines pela primeira regra satisfeita.

As regras vêm de um arquivo JSON; este módulo não conhece nenhuma regra de domínio.
Na inicialização, o arquivo de regras vira o código-fonte de uma função Python, que é
compilada uma vez e chamada para cada linha.
"""
import argparse
import datetime
import functools
import json
import math
import os
import re
import sys
import types

try:
    import orjson
except ImportError:  # sem orjson, o motor continua correto, só mais lento
    orjson = None

AUSENTE = object()

_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def resolver(doc, caminho):
    """Desce por objetos aninhados; qualquer nível ausente, nulo ou não objeto dá AUSENTE.

    É a semântica de referência; o código gerado por gerar_classificador faz o mesmo
    trocando objetos ausentes por um dicionário vazio e tratando None como ausente.
    """
    atual = doc
    for chave in caminho:
        if type(atual) is not dict:
            return AUSENTE
        atual = atual.get(chave, AUSENTE)
        if atual is None:
            return AUSENTE
    return atual


def _numero(v):
    return type(v) is int or (type(v) is float and math.isfinite(v))


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


class Reler(Exception):
    """O orjson pode ter arredondado um inteiro acima de 64 bits; a linha precisa do json."""


# operador -> (operador Python, tipos aceitos)
OPERADORES = {
    "igual": ("==", {"numero", "texto", "data", "booleano"}),
    "diferente": ("!=", {"numero", "texto", "data", "booleano"}),
    "menor": ("<", {"numero", "data"}),
    "menor_igual": ("<=", {"numero", "data"}),
    "maior": (">", {"numero", "data"}),
    "maior_igual": (">=", {"numero", "data"}),
    "em": (None, {"texto"}),
    "comeca_com": (None, {"texto"}),
}

# O orjson lê inteiros de -2**63 a 2**64-1 sem perda; fora disso devolve float.
_LIMITE = 2.0 ** 63


def _reler(v):
    """Float finito de módulo >= 2**63 vindo do orjson: pode ser um inteiro arredondado."""
    if -math.inf < v < math.inf:
        raise Reler
    return False


def _caminho(cond):
    campo = cond.get("campo")
    if type(campo) is not str or not campo:
        raise ErroRegras(f"condição sem 'campo': {cond}")
    return tuple(campo.split("."))


class _Gerador:
    """Traduz condições em expressões Python sobre `doc`.

    Cada objeto intermediário de um caminho (`logistica` em `logistica.migo`) é lido uma vez
    no início da função e trocado por um dicionário vazio quando ausente, nulo ou não objeto;
    a folha é lida com .get(), e None faz o papel de AUSENTE.
    """

    def __init__(self, rapido):
        self.rapido = rapido
        self.pais = {}
        self.prologo = []
        self.constantes = {}
        self.n = 0

    def _pai(self, prefixo):
        if not prefixo:
            return "doc"
        if prefixo not in self.pais:
            avo = self._pai(prefixo[:-1])
            nome = f"p{len(self.pais)}"
            self.pais[prefixo] = nome
            self.prologo.append(f"{nome} = {avo}.get({prefixo[-1]!r})")
            self.prologo.append(f"if type({nome}) is not dict: {nome} = VAZIO")
        return self.pais[prefixo]

    def _ler(self, caminho):
        """Devolve (nome temporário, expressão que lê o campo e guarda no temporário)."""
        self.n += 1
        t = f"t{self.n}"
        return t, f"({t} := {self._pai(caminho[:-1])}.get({caminho[-1]!r}))"

    def _constante(self, v):
        if type(v) in (str, int, float):
            return repr(v)
        nome = f"K{len(self.constantes)}"
        self.constantes[nome] = v
        return nome

    def _valido(self, tipo, t, leitura):
        if tipo == "texto":
            return f"type({leitura}) is str"
        if tipo == "booleano":
            return f"type({leitura}) is bool"
        if tipo == "data":
            return f"(type({leitura}) is str and data_valida({t}))"
        if self.rapido:
            return f"(type({leitura}) is int or (type({t}) is float and (-LIMITE < {t} < LIMITE or reler({t}))))"
        return f"(type({leitura}) is int or (type({t}) is float and -INF < {t} < INF))"

    def expressao(self, cond):
        if type(cond) is not dict:
            raise ErroRegras(f"condição não é objeto: {cond!r}")
        for chave, junta in (("e", " and "), ("ou", " or ")):
            if chave in cond:
                partes = cond[chave]
                if type(partes) is not list or not partes:
                    raise ErroRegras(f"'{chave}' exige lista não vazia: {cond}")
                return "(" + junta.join(self.expressao(p) for p in partes) + ")"
        if cond.get("op") == "vazio":
            t, leitura = self._ler(_caminho(cond))
            return f"({leitura} is None or {t} == '')"
        return self._comparacao(cond)

    def _comparacao(self, cond):
        caminho = _caminho(cond)
        op, tipo = cond.get("op"), cond.get("tipo")
        if tipo not in VALIDADORES:
            raise ErroRegras(f"tipo desconhecido {tipo!r}: {cond}")
        if op not in OPERADORES:
            raise ErroRegras(f"operador desconhecido {op!r}: {cond}")
        simbolo, tipos = OPERADORES[op]
        if tipo not in tipos:
            raise ErroRegras(f"operador {op!r} não aceita tipo {tipo!r}: {cond}")
        eh = VALIDADORES[tipo]
        t, leitura = self._ler(caminho)

        if "outro_campo" in cond:
            if op == "em":
                raise ErroRegras(f"'em' exige 'valor' com lista: {cond}")
            u, outra = self._ler(_caminho({"campo": cond["outro_campo"]}))
            if op == "comeca_com":
                compara = f"{t}.startswith({u})"
            else:
                compara = f"{t} {simbolo} {u}"
            return f"({self._valido(tipo, t, leitura)} and {self._valido(tipo, u, outra)} and {compara})"

        if "valor" not in cond:
            raise ErroRegras(f"condição sem 'valor' nem 'outro_campo': {cond}")
        constante = cond["valor"]
        if op == "em":
            if type(constante) is not list or not constante or not all(eh(x) for x in constante):
                raise ErroRegras(f"'em' exige lista não vazia de {tipo}: {cond}")
            compara = f"{t} in {self._constante(frozenset(constante))}"
        elif not eh(constante):
            raise ErroRegras(f"'valor' não é do tipo {tipo}: {cond}")
        elif op == "comeca_com":
            compara = f"{t}.startswith({self._constante(constante)})"
        else:
            compara = f"{t} {simbolo} {self._constante(constante)}"
        return f"({self._valido(tipo, t, leitura)} and {compara})"

    def compilar(self, nome, corpo):
        linhas = [f"def {nome}(doc):"]
        linhas += ["    " + l for l in self.prologo]
        linhas += ["    " + l for l in corpo]
        espaco = {
            "VAZIO": types.MappingProxyType({}),
            "LIMITE": _LIMITE,
            "INF": math.inf,
            "reler": _reler,
            "data_valida": _data_valida,
            **self.constantes,
        }
        fonte = "\n".join(linhas) + "\n"
        exec(compile(fonte, "<regras>", "exec"), espaco)
        funcao = espaco[nome]
        funcao.fonte = fonte
        return funcao


_data_valida = functools.lru_cache(maxsize=4096)(_data)


def compilar_condicao(cond):
    """Transforma uma condição do arquivo de regras numa função doc -> bool."""
    g = _Gerador(rapido=False)
    expr = g.expressao(cond)
    return g.compilar("teste", [f"return {expr}"])


def gerar_classificador(regras, sem_regra, rapido=False):
    """Gera uma única função doc -> código da primeira regra satisfeita (ou sem_regra).

    Com rapido=True, a função levanta Reler quando um campo numérico pode ter sido
    arredondado pelo orjson.
    """
    g = _Gerador(rapido)
    corpo = []
    for codigo, quando in regras:
        corpo.append(f"if {g.expressao(quando)}:")
        corpo.append(f"    return {codigo!r}")
    corpo.append(f"return {sem_regra!r}")
    return g.compilar("classificar", corpo)


def _ler_regras(caminho):
    """Lê o arquivo de regras e devolve ([(codigo, condição), ...] em ordem, texto de sem_regra)."""
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
        regras.append((r["codigo"], r["quando"]))
    sem_regra = doc.get("sem_regra", "SEM_REGRA")
    if type(sem_regra) is not str:
        raise ErroRegras(f"'sem_regra' precisa ser texto: {sem_regra!r}")
    return regras, sem_regra


def carregar_regras(caminho):
    """Lê o arquivo de regras e devolve ([(codigo, teste), ...] em ordem, texto de sem_regra)."""
    regras, sem_regra = _ler_regras(caminho)
    return [(codigo, compilar_condicao(quando)) for codigo, quando in regras], sem_regra


def carregar_classificador(caminho):
    """Devolve (função para docs do orjson, função para docs do json)."""
    regras, sem_regra = _ler_regras(caminho)
    return gerar_classificador(regras, sem_regra, rapido=True), gerar_classificador(regras, sem_regra)


def _json_exato(texto):
    return json.loads(texto.decode("utf-8"))


def classificar(dados, rapida, exata, avisar, loads=orjson.loads if orjson else None):
    """Recebe o arquivo inteiro em bytes e devolve as linhas 'id:<id> - regra: <código>' na ordem.

    Cada linha passa primeiro pelo orjson; se ele recusar (NaN, Infinity, surrogates soltos,
    número fora do double), a linha passa pelo json da biblioteca padrão, que é a referência.
    """
    if dados.startswith(b"\xef\xbb\xbf"):
        dados = dados[3:]
    if b"\r" in dados:
        dados = dados.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    saida = []
    anotar = saida.append
    for n, texto in enumerate(dados.split(b"\n"), 1):
        exato = loads is None
        if not exato:
            try:
                doc = loads(texto)
            except ValueError:
                exato = True
        if exato:
            try:
                doc = _json_exato(texto)
            except (ValueError, RecursionError):
                if texto.decode("utf-8", "replace").strip():
                    avisar(f"linha {n}: JSON inválido")
                continue
        if type(doc) is not dict:
            avisar(f"linha {n}: não é um objeto JSON")
            continue
        ident = doc.get("id")
        if ident is None:
            avisar(f"linha {n}: sem id")
            continue
        if exato:
            codigo = exata(doc)
        else:
            try:
                if type(ident) is float:
                    raise Reler
                codigo = rapida(doc)
            except Reler:
                doc = _json_exato(texto)
                ident = doc["id"]
                codigo = exata(doc)
        anotar(f"id:{ident} - regra: {codigo}")
    return saida


REGRAS_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regras", "duplicatas.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classifica duplicatas pela primeira regra satisfeita.")
    parser.add_argument("--entrada", required=True, help="arquivo JSON Lines, uma duplicata por linha")
    parser.add_argument("--regras", default=REGRAS_PADRAO, help="arquivo de regras (padrão: regras/duplicatas.json)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n", errors="backslashreplace")

    def avisar(msg):
        print(msg, file=sys.stderr)

    try:
        rapida, exata = carregar_classificador(args.regras)
    except ErroRegras as e:
        avisar(f"erro nas regras: {e}")
        return 2
    with open(args.entrada, "rb") as f:
        dados = f.read()
    saida = classificar(dados, rapida, exata, avisar)
    if saida:
        sys.stdout.write("\n".join(saida) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

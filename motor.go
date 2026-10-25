package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
)

// teste é uma condição compilada: recebe os campos lidos da linha, um por slot.
type teste func(vals []valor) bool

type regra struct {
	codigo string
	teste  teste
}

type motor struct {
	regras   []regra
	semRegra string
	raiz     *no
	slotID   int
	nSlots   int
}

type ErroRegras struct{ msg string }

func (e *ErroRegras) Error() string { return e.msg }

func erro(formato string, args ...any) error {
	return &ErroRegras{fmt.Sprintf(formato, args...)}
}

var tiposValidos = map[string]bool{"numero": true, "texto": true, "data": true, "booleano": true}

// operador -> tipos aceitos
var operadores = map[string]map[string]bool{
	"igual":       {"numero": true, "texto": true, "data": true, "booleano": true},
	"diferente":   {"numero": true, "texto": true, "data": true, "booleano": true},
	"menor":       {"numero": true, "data": true},
	"menor_igual": {"numero": true, "data": true},
	"maior":       {"numero": true, "data": true},
	"maior_igual": {"numero": true, "data": true},
	"em":          {"texto": true},
	"comeca_com":  {"texto": true},
}

func valido(v valor, tipo string) bool {
	switch tipo {
	case "numero":
		return v.tipo == numero
	case "texto":
		return v.tipo == texto
	case "data":
		return v.tipo == texto && dataValida(v.bruto)
	case "booleano":
		return v.tipo == booleano
	}
	return false
}

// constante converte um valor do arquivo de regras para a mesma forma dos campos lidos.
func constante(x any) valor {
	switch c := x.(type) {
	case string:
		return valor{tipo: texto, bruto: []byte(c)}
	case bool:
		return valor{tipo: booleano, b: c}
	case json.Number:
		return novoNumero([]byte(c), !strings.ContainsAny(string(c), ".eE"))
	}
	return valor{tipo: outro}
}

// comparar devolve <0, 0 ou >0; para booleano só a igualdade importa.
func comparar(a, b valor, tipo string) int {
	switch tipo {
	case "numero":
		return compararNumeros(a, b)
	case "booleano":
		if a.b == b.b {
			return 0
		}
		return 1
	}
	return bytes.Compare(a.bruto, b.bruto)
}

var comparacoes = map[string]func(int) bool{
	"igual":       func(c int) bool { return c == 0 },
	"diferente":   func(c int) bool { return c != 0 },
	"menor":       func(c int) bool { return c < 0 },
	"menor_igual": func(c int) bool { return c <= 0 },
	"maior":       func(c int) bool { return c > 0 },
	"maior_igual": func(c int) bool { return c >= 0 },
}

// compilador registra cada caminho usado pelas regras num slot.
type compilador struct {
	slots    map[string]int
	caminhos [][]string
}

func (c *compilador) slot(campo string) int {
	if s, ok := c.slots[campo]; ok {
		return s
	}
	s := len(c.caminhos)
	c.slots[campo] = s
	c.caminhos = append(c.caminhos, strings.Split(campo, "."))
	return s
}

func (c *compilador) caminho(cond map[string]any, chave string) (int, error) {
	campo, ok := cond[chave].(string)
	if !ok || campo == "" {
		return 0, erro("condição sem 'campo': %v", cond)
	}
	return c.slot(campo), nil
}

// compilar transforma uma condição do arquivo de regras numa função.
func (c *compilador) compilar(x any) (teste, error) {
	cond, ok := x.(map[string]any)
	if !ok {
		return nil, erro("condição não é objeto: %v", x)
	}
	for _, chave := range []string{"e", "ou"} {
		if _, tem := cond[chave]; tem {
			return c.combinacao(chave, cond)
		}
	}
	if op, _ := cond["op"].(string); op == "vazio" {
		s, err := c.caminho(cond, "campo")
		if err != nil {
			return nil, err
		}
		return func(vals []valor) bool {
			v := vals[s]
			return v.tipo == ausente || (v.tipo == texto && len(v.bruto) == 0)
		}, nil
	}
	return c.comparacao(cond)
}

func (c *compilador) comparacao(cond map[string]any) (teste, error) {
	s, err := c.caminho(cond, "campo")
	if err != nil {
		return nil, err
	}
	op, _ := cond["op"].(string)
	tipo, _ := cond["tipo"].(string)
	if !tiposValidos[tipo] {
		return nil, erro("tipo desconhecido %q: %v", cond["tipo"], cond)
	}
	tipos, ok := operadores[op]
	if !ok {
		return nil, erro("operador desconhecido %q: %v", cond["op"], cond)
	}
	if !tipos[tipo] {
		return nil, erro("operador %q não aceita tipo %q: %v", op, tipo, cond)
	}

	if _, tem := cond["outro_campo"]; tem {
		if op == "em" {
			return nil, erro("'em' exige 'valor' com lista: %v", cond)
		}
		outro, err := c.caminho(cond, "outro_campo")
		if err != nil {
			return nil, err
		}
		if op == "comeca_com" {
			return func(vals []valor) bool {
				a, b := vals[s], vals[outro]
				return a.tipo == texto && b.tipo == texto && bytes.HasPrefix(a.bruto, b.bruto)
			}, nil
		}
		satisfaz := comparacoes[op]
		return func(vals []valor) bool {
			a, b := vals[s], vals[outro]
			return valido(a, tipo) && valido(b, tipo) && satisfaz(comparar(a, b, tipo))
		}, nil
	}

	bruto, tem := cond["valor"]
	if !tem {
		return nil, erro("condição sem 'valor' nem 'outro_campo': %v", cond)
	}
	if op == "em" {
		lista, ok := bruto.([]any)
		if !ok || len(lista) == 0 {
			return nil, erro("'em' exige lista não vazia de %s: %v", tipo, cond)
		}
		opcoes := map[string]bool{}
		for _, x := range lista {
			k := constante(x)
			if !valido(k, tipo) {
				return nil, erro("'em' exige lista não vazia de %s: %v", tipo, cond)
			}
			opcoes[string(k.bruto)] = true
		}
		return func(vals []valor) bool {
			a := vals[s]
			return a.tipo == texto && opcoes[string(a.bruto)]
		}, nil
	}
	k := constante(bruto)
	if !valido(k, tipo) {
		return nil, erro("'valor' não é do tipo %s: %v", tipo, cond)
	}
	if op == "comeca_com" {
		return func(vals []valor) bool {
			a := vals[s]
			return a.tipo == texto && bytes.HasPrefix(a.bruto, k.bruto)
		}, nil
	}
	satisfaz := comparacoes[op]
	return func(vals []valor) bool {
		a := vals[s]
		return valido(a, tipo) && satisfaz(comparar(a, k, tipo))
	}, nil
}

func (c *compilador) combinacao(chave string, cond map[string]any) (teste, error) {
	partes, ok := cond[chave].([]any)
	if !ok || len(partes) == 0 {
		return nil, erro("'%s' exige lista não vazia: %v", chave, cond)
	}
	testes := make([]teste, len(partes))
	for i, p := range partes {
		t, err := c.compilar(p)
		if err != nil {
			return nil, err
		}
		testes[i] = t
	}
	if chave == "e" {
		return func(vals []valor) bool {
			for _, t := range testes {
				if !t(vals) {
					return false
				}
			}
			return true
		}, nil
	}
	return func(vals []valor) bool {
		for _, t := range testes {
			if t(vals) {
				return true
			}
		}
		return false
	}, nil
}

// lerJSON decodifica o arquivo inteiro, preservando números como texto.
func lerJSON(r io.Reader) (any, error) {
	dec := json.NewDecoder(r)
	dec.UseNumber()
	var doc any
	if err := dec.Decode(&doc); err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err != io.EOF {
		return nil, fmt.Errorf("conteúdo extra depois do JSON")
	}
	return doc, nil
}

// carregarRegras lê o arquivo de regras e compila cada condição, na ordem do arquivo.
func carregarRegras(caminho string) (*motor, error) {
	f, err := os.Open(caminho)
	if err != nil {
		return nil, erro("não foi possível ler %s: %v", caminho, err)
	}
	defer f.Close()
	x, err := lerJSON(f)
	if err != nil {
		return nil, erro("não foi possível ler %s: %v", caminho, err)
	}
	doc, ok := x.(map[string]any)
	if !ok {
		return nil, erro("o arquivo de regras precisa ter a lista 'regras'")
	}
	lista, ok := doc["regras"].([]any)
	if !ok {
		return nil, erro("o arquivo de regras precisa ter a lista 'regras'")
	}
	c := &compilador{slots: map[string]int{}}
	m := &motor{semRegra: "SEM_REGRA", slotID: c.slot("id")}
	if sr, tem := doc["sem_regra"]; tem {
		m.semRegra = fmt.Sprint(sr)
	}
	for _, item := range lista {
		r, ok := item.(map[string]any)
		codigo, ehTexto := r["codigo"].(string)
		_, temQuando := r["quando"]
		if !ok || !ehTexto || !temQuando {
			return nil, erro("regra precisa de 'codigo' e 'quando': %v", item)
		}
		t, err := c.compilar(r["quando"])
		if err != nil {
			return nil, err
		}
		m.regras = append(m.regras, regra{codigo, t})
	}
	m.raiz = novaArvore(c.caminhos)
	m.nSlots = len(c.caminhos)
	return m, nil
}

var bom = []byte("\xef\xbb\xbf")

// classificar escreve 'id:<id> - regra: <código>' para cada linha, na ordem da entrada.
func (m *motor) classificar(dados []byte, w *bufio.Writer, avisar func(string)) {
	dados = bytes.TrimPrefix(dados, bom)
	l := leitor{vals: make([]valor, m.nSlots)}
	for n := 1; len(dados) > 0; n++ {
		var linha []byte
		linha, dados = proximaLinha(dados)
		if linhaVazia(linha) {
			continue
		}
		clear(l.vals)
		l.b, l.i = linha, 0
		tipo, ok := l.documento(m.raiz)
		if !ok {
			avisar(fmt.Sprintf("linha %d: JSON inválido", n))
			continue
		}
		if tipo != objeto {
			avisar(fmt.Sprintf("linha %d: não é um objeto JSON", n))
			continue
		}
		id := l.vals[m.slotID]
		if id.tipo == ausente {
			avisar(fmt.Sprintf("linha %d: sem id", n))
			continue
		}
		codigo := m.semRegra
		for _, r := range m.regras {
			if r.teste(l.vals) {
				codigo = r.codigo
				break
			}
		}
		w.WriteString("id:")
		w.WriteString(textoID(id))
		w.WriteString(" - regra: ")
		w.WriteString(codigo)
		w.WriteByte('\n')
	}
}

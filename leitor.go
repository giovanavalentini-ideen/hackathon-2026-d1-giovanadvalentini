package main

import (
	"bytes"
	"math"
	"math/big"
	"strconv"
	"unicode"
	"unicode/utf16"
	"unicode/utf8"
)

// tipoValor é o tipo JSON de um campo lido. O valor zero, ausente, cobre campo
// que não existe, null e caminho que passa por algo que não é objeto.
type tipoValor uint8

const (
	ausente tipoValor = iota
	texto
	numero // número JSON finito
	booleano
	objeto
	outro // lista, NaN, Infinity, número fora da faixa do float
)

// valor é um campo lido da linha. Número guarda o token e o float, como o Python o enxergaria.
type valor struct {
	tipo    tipoValor
	b       bool
	inteiro bool // número sem ponto nem expoente: no Python, int
	exato   bool // f representa o número sem perda; senão a comparação usa big.Rat
	f       float64
	bruto   []byte // texto já decodificado, token do número, ou o trecho original do JSON
}

// no é um nó da árvore dos caminhos que as regras usam. Só esses campos são guardados;
// o resto da linha é apenas validado.
type no struct {
	chave    string
	filhos   []*no
	tamanhos uint64 // bit n ligado: algum filho tem chave de n bytes
	slot     int    // -1 quando o caminho até aqui não é usado por nenhuma regra
	sub      []int  // slots deste nó e de todos abaixo dele
}

func novaArvore(caminhos [][]string) *no {
	raiz := &no{slot: -1}
	for slot, caminho := range caminhos {
		atual := raiz
		for _, chave := range caminho {
			prox := atual.filho([]byte(chave))
			if prox == nil {
				prox = &no{chave: chave, slot: -1}
				atual.filhos = append(atual.filhos, prox)
				if len(chave) < 64 {
					atual.tamanhos |= 1 << len(chave)
				}
			}
			atual = prox
		}
		atual.slot = slot
	}
	preencherSub(raiz)
	return raiz
}

// filho procura a chave entre os filhos; o filtro por tamanho descarta quase toda chave
// que não interessa sem comparar bytes.
func (n *no) filho(chave []byte) *no {
	if len(chave) < 64 && n.tamanhos&(1<<len(chave)) == 0 {
		return nil
	}
	for _, f := range n.filhos {
		if f.chave == string(chave) {
			return f
		}
	}
	return nil
}

func preencherSub(n *no) []int {
	if n.slot >= 0 {
		n.sub = append(n.sub, n.slot)
	}
	for _, f := range n.filhos {
		n.sub = append(n.sub, preencherSub(f)...)
	}
	return n.sub
}

// leitor percorre uma linha JSON validando tudo e guardando só os campos da árvore.
// Segue o json do Python: chave repetida vale a última, NaN e Infinity são aceitos.
type leitor struct {
	b    []byte
	i    int
	vals []valor
}

func (l *leitor) ws() {
	for l.i < len(l.b) {
		switch l.b[l.i] {
		case ' ', '\t', '\n', '\r':
			l.i++
		default:
			return
		}
	}
}

// documento lê a linha inteira e devolve o tipo do valor de topo.
func (l *leitor) documento(raiz *no) (tipoValor, bool) {
	l.ws()
	t, ok := l.valor(raiz)
	if !ok {
		return 0, false
	}
	l.ws()
	return t, l.i == len(l.b)
}

func (l *leitor) literal(s string) bool {
	if bytes.HasPrefix(l.b[l.i:], []byte(s)) {
		l.i += len(s)
		return true
	}
	return false
}

func (l *leitor) valor(n *no) (tipoValor, bool) {
	if l.i >= len(l.b) {
		return 0, false
	}
	var dst *valor
	if n != nil && n.slot >= 0 {
		dst = &l.vals[n.slot]
	}
	ini := l.i
	var tipo tipoValor
	switch c := l.b[l.i]; {
	case c == '"':
		raw, esc, ok := l.texto()
		if !ok {
			return 0, false
		}
		if dst != nil {
			if esc {
				raw = decodificar(raw)
			}
			*dst = valor{tipo: texto, bruto: raw}
		}
		return texto, true
	case c == '-' || (c >= '0' && c <= '9'):
		if l.literal("-Infinity") {
			if dst != nil {
				*dst = valor{tipo: outro, bruto: []byte("-inf")}
			}
			return outro, true
		}
		tok, inteiro, ok := l.numero()
		if !ok {
			return 0, false
		}
		if dst != nil {
			*dst = novoNumero(tok, inteiro)
			return dst.tipo, true
		}
		return numero, true
	case c == '{':
		if !l.objeto(n) {
			return 0, false
		}
		tipo = objeto
	case c == '[':
		if !l.lista() {
			return 0, false
		}
		tipo = outro
	case l.literal("true"), l.literal("false"):
		if dst != nil {
			*dst = valor{tipo: booleano, b: c == 't'}
		}
		return booleano, true
	case l.literal("null"):
		return ausente, true
	case l.literal("NaN"):
		if dst != nil {
			*dst = valor{tipo: outro, bruto: []byte("nan")}
		}
		return outro, true
	case l.literal("Infinity"):
		if dst != nil {
			*dst = valor{tipo: outro, bruto: []byte("inf")}
		}
		return outro, true
	default:
		return 0, false
	}
	if dst != nil {
		*dst = valor{tipo: tipo, bruto: l.b[ini:l.i]}
	}
	return tipo, true
}

func (l *leitor) objeto(n *no) bool {
	l.i++
	l.ws()
	if l.i < len(l.b) && l.b[l.i] == '}' {
		l.i++
		return true
	}
	for {
		if l.i >= len(l.b) || l.b[l.i] != '"' {
			return false
		}
		raw, esc, ok := l.texto()
		if !ok {
			return false
		}
		var filho *no
		if n != nil && n.filhos != nil {
			if esc {
				raw = decodificar(raw)
			}
			if filho = n.filho(raw); filho != nil {
				// chave repetida: a última ocorrência substitui tudo o que veio antes
				for _, s := range filho.sub {
					l.vals[s] = valor{}
				}
			}
		}
		l.ws()
		if l.i >= len(l.b) || l.b[l.i] != ':' {
			return false
		}
		l.i++
		l.ws()
		if _, ok := l.valor(filho); !ok {
			return false
		}
		l.ws()
		if l.i >= len(l.b) {
			return false
		}
		switch l.b[l.i] {
		case '}':
			l.i++
			return true
		case ',':
			l.i++
			l.ws()
		default:
			return false
		}
	}
}

func (l *leitor) lista() bool {
	l.i++
	l.ws()
	if l.i < len(l.b) && l.b[l.i] == ']' {
		l.i++
		return true
	}
	for {
		if _, ok := l.valor(nil); !ok {
			return false
		}
		l.ws()
		if l.i >= len(l.b) {
			return false
		}
		switch l.b[l.i] {
		case ']':
			l.i++
			return true
		case ',':
			l.i++
			l.ws()
		default:
			return false
		}
	}
}

func ehHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

// especial marca os bytes que interrompem uma string JSON: aspas, barra e controle.
var especial = func() (t [256]bool) {
	for c := 0; c < 0x20; c++ {
		t[c] = true
	}
	t['"'], t['\\'] = true, true
	return t
}()

// texto lê uma string JSON e devolve o conteúdo cru entre as aspas.
func (l *leitor) texto() (raw []byte, esc bool, ok bool) {
	b := l.b
	i := l.i + 1
	ini := i
	for {
		for i < len(b) && !especial[b[i]] {
			i++
		}
		if i >= len(b) || b[i] < 0x20 {
			return nil, false, false
		}
		if b[i] == '"' {
			l.i = i + 1
			return b[ini:i], esc, true
		}
		esc = true
		if i+1 >= len(b) {
			return nil, false, false
		}
		switch b[i+1] {
		case '"', '\\', '/', 'b', 'f', 'n', 'r', 't':
			i += 2
		case 'u':
			if i+6 > len(b) || !ehHex(b[i+2]) || !ehHex(b[i+3]) || !ehHex(b[i+4]) || !ehHex(b[i+5]) {
				return nil, false, false
			}
			i += 6
		default:
			return nil, false, false
		}
	}
}

// decodificar resolve os escapes de uma string JSON já validada.
func decodificar(raw []byte) []byte {
	out := make([]byte, 0, len(raw))
	for i := 0; i < len(raw); {
		c := raw[i]
		if c != '\\' {
			out = append(out, c)
			i++
			continue
		}
		switch raw[i+1] {
		case 'b':
			out = append(out, '\b')
		case 'f':
			out = append(out, '\f')
		case 'n':
			out = append(out, '\n')
		case 'r':
			out = append(out, '\r')
		case 't':
			out = append(out, '\t')
		case 'u':
			r := rune(hex4(raw[i+2:]))
			i += 6
			if utf16.IsSurrogate(r) && i+6 <= len(raw) && raw[i] == '\\' && raw[i+1] == 'u' {
				if par := utf16.DecodeRune(r, rune(hex4(raw[i+2:]))); par != utf8.RuneError {
					r = par
					i += 6
				}
			}
			out = utf8.AppendRune(out, r)
			continue
		default: // '"', '\\', '/'
			out = append(out, raw[i+1])
		}
		i += 2
	}
	return out
}

func hex4(b []byte) uint16 {
	v, _ := strconv.ParseUint(string(b[:4]), 16, 16)
	return uint16(v)
}

// numero lê um número na gramática do JSON: -?(0|[1-9][0-9]*)(.[0-9]+)?([eE][-+]?[0-9]+)?
func (l *leitor) numero() (tok []byte, inteiro bool, ok bool) {
	b, i := l.b, l.i
	digitos := func() int {
		ini := i
		for i < len(b) && b[i] >= '0' && b[i] <= '9' {
			i++
		}
		return i - ini
	}
	if b[i] == '-' {
		i++
	}
	if i >= len(b) {
		return nil, false, false
	}
	if b[i] == '0' {
		i++
	} else if digitos() == 0 {
		return nil, false, false
	}
	inteiro = true
	if i < len(b) && b[i] == '.' {
		i++
		if digitos() == 0 {
			return nil, false, false
		}
		inteiro = false
	}
	if i < len(b) && (b[i] == 'e' || b[i] == 'E') {
		i++
		if i < len(b) && (b[i] == '+' || b[i] == '-') {
			i++
		}
		if digitos() == 0 {
			return nil, false, false
		}
		inteiro = false
	}
	tok = b[l.i:i]
	l.i = i
	return tok, inteiro, true
}

// novoNumero converte o token. Inteiro é sempre número válido (como o int do Python);
// float que estoura para infinito não é.
func novoNumero(tok []byte, inteiro bool) valor {
	n := valor{tipo: numero, inteiro: inteiro, bruto: tok}
	if inteiro {
		digitos := tok
		if digitos[0] == '-' {
			digitos = digitos[1:]
		}
		if len(digitos) <= 15 {
			var x int64
			for _, d := range digitos {
				x = x*10 + int64(d-'0')
			}
			if tok[0] == '-' {
				x = -x
			}
			n.f, n.exato = float64(x), true
		} else {
			n.f, _ = strconv.ParseFloat(string(tok), 64)
		}
		return n
	}
	n.f, _ = strconv.ParseFloat(string(tok), 64)
	if math.IsInf(n.f, 1) {
		return valor{tipo: outro, bruto: []byte("inf")}
	}
	if math.IsInf(n.f, -1) {
		return valor{tipo: outro, bruto: []byte("-inf")}
	}
	n.exato = true
	return n
}

func (n valor) rat() *big.Rat {
	if n.inteiro {
		r, _ := new(big.Rat).SetString(string(n.bruto))
		return r
	}
	return new(big.Rat).SetFloat64(n.f)
}

// compararNumeros compara pelo valor matemático, como o Python faz entre int e float.
func compararNumeros(a, b valor) int {
	if a.exato && b.exato {
		switch {
		case a.f < b.f:
			return -1
		case a.f > b.f:
			return 1
		}
		return 0
	}
	return a.rat().Cmp(b.rat())
}

// dataValida aceita só AAAA-MM-DD com dia existente no calendário.
func dataValida(s []byte) bool {
	if len(s) != 10 || s[4] != '-' || s[7] != '-' {
		return false
	}
	num := func(b []byte) int {
		x := 0
		for _, d := range b {
			if d < '0' || d > '9' {
				return -1
			}
			x = x*10 + int(d-'0')
		}
		return x
	}
	ano, mes, dia := num(s[:4]), num(s[5:7]), num(s[8:])
	if ano < 1 || mes < 1 || mes > 12 || dia < 1 {
		return false
	}
	dias := [13]int{0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}[mes]
	if mes == 2 && ano%4 == 0 && (ano%100 != 0 || ano%400 == 0) {
		dias = 29
	}
	return dia <= dias
}

// linhaVazia segue o str.strip() do Python: só espaços em branco não é linha.
func linhaVazia(b []byte) bool {
	for len(b) > 0 {
		r, n := utf8.DecodeRune(b)
		if !unicode.IsSpace(r) && (r < 0x1c || r > 0x1f) {
			return false
		}
		b = b[n:]
	}
	return true
}

// proximaLinha separa por \n, \r\n ou \r, como a leitura de texto do Python.
func proximaLinha(dados []byte) (linha, resto []byte) {
	j := bytes.IndexByte(dados, '\n')
	if j < 0 {
		j = len(dados)
	}
	seg := dados[:j]
	if k := bytes.IndexByte(seg, '\r'); k >= 0 && k < len(seg)-1 {
		return seg[:k], dados[k+1:]
	}
	if len(seg) > 0 && seg[len(seg)-1] == '\r' {
		seg = seg[:len(seg)-1]
	}
	if j < len(dados) {
		return seg, dados[j+1:]
	}
	return seg, nil
}

// textoID escreve o id como o print do Python escreveria.
func textoID(v valor) string {
	switch v.tipo {
	case texto:
		return string(v.bruto)
	case booleano:
		if v.b {
			return "True"
		}
		return "False"
	case numero:
		if v.inteiro {
			if string(v.bruto) == "-0" {
				return "0"
			}
			return string(v.bruto)
		}
		return reprFloat(v.f)
	}
	return string(v.bruto)
}

// reprFloat reproduz o repr(float) do Python: notação fixa entre 1e-4 e 1e16, com ".0" no inteiro.
func reprFloat(f float64) string {
	s := strconv.FormatFloat(f, 'e', -1, 64)
	sinal := ""
	if s[0] == '-' {
		sinal, s = "-", s[1:]
	}
	e := bytes.IndexByte([]byte(s), 'e')
	mant, exp := s[:e], s[e+1:]
	digitos := mant[:1]
	if len(mant) > 2 {
		digitos += mant[2:]
	}
	x, _ := strconv.Atoi(exp)
	if x >= -4 && x < 16 {
		ponto := x + 1
		switch {
		case ponto <= 0:
			return sinal + "0." + zeros(-ponto) + digitos
		case ponto >= len(digitos):
			return sinal + digitos + zeros(ponto-len(digitos)) + ".0"
		default:
			return sinal + digitos[:ponto] + "." + digitos[ponto:]
		}
	}
	r := digitos[:1]
	if len(digitos) > 1 {
		r += "." + digitos[1:]
	}
	es := "+"
	if x < 0 {
		es, x = "-", -x
	}
	ed := strconv.Itoa(x)
	if len(ed) < 2 {
		ed = "0" + ed
	}
	return sinal + r + "e" + es + ed
}

func zeros(n int) string {
	return string(bytes.Repeat([]byte("0"), n))
}

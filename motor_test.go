package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// cond compila uma condição escrita em JSON.
func cond(t *testing.T, texto string) (teste, *no) {
	t.Helper()
	x, err := lerJSON(strings.NewReader(texto))
	if err != nil {
		t.Fatal(err)
	}
	c := &compilador{slots: map[string]int{}}
	f, err := c.compilar(x)
	if err != nil {
		t.Fatalf("%s: %v", texto, err)
	}
	return f, novaArvore(c.caminhos)
}

// avalia lê um documento e aplica a condição.
func avalia(t *testing.T, f teste, raiz *no, doc string) bool {
	t.Helper()
	l := leitor{b: []byte(doc), vals: make([]valor, len(raiz.sub))}
	if _, ok := l.documento(raiz); !ok {
		t.Fatalf("JSON inválido no teste: %s", doc)
	}
	return f(l.vals)
}

func confere(t *testing.T, regra string, casos map[string]bool) {
	t.Helper()
	f, raiz := cond(t, regra)
	for doc, esperado := range casos {
		if got := avalia(t, f, raiz, doc); got != esperado {
			t.Errorf("%s com %s: esperado %v, obtido %v", regra, doc, esperado, got)
		}
	}
}

func TestIgualExato(t *testing.T) {
	confere(t, `{"campo":"s","tipo":"texto","op":"igual","valor":"ATIVA"}`, map[string]bool{
		`{"s":"ATIVA"}`: true, `{"s":"ativa"}`: false, `{}`: false, `{"s":"\u0041TIVA"}`: true,
	})
}

func TestDiferenteComAusenteOuTipoErradoEFalso(t *testing.T) {
	confere(t, `{"campo":"a","tipo":"texto","op":"diferente","outro_campo":"b"}`, map[string]bool{
		`{"a":"SP","b":"MT"}`: true, `{"a":"SP"}`: false, `{"a":"SP","b":35}`: false,
		`{"a":"SP","b":"SP"}`: false, `{"a":"SP","b":null}`: false,
	})
}

func TestLimites(t *testing.T) {
	confere(t, `{"campo":"v","tipo":"numero","op":"maior_igual","valor":100}`, map[string]bool{
		`{"v":100}`: true, `{"v":100.0}`: true, `{"v":1e2}`: true, `{"v":99.99999}`: false,
		`{"v":"150"}`: false, `{"v":true}`: false, `{"v":NaN}`: false, `{"v":Infinity}`: false,
		`{"v":1e400}`: false, `{"v":123456789012345678901234567890}`: true,
	})
	confere(t, `{"campo":"v","tipo":"numero","op":"maior","valor":100}`, map[string]bool{
		`{"v":100}`: false, `{"v":100.0000001}`: true,
	})
}

func TestInteiroGrandeComparaExato(t *testing.T) {
	// 2^53 + 1 não cabe num float; o Python compara int com int sem perda
	confere(t, `{"campo":"a","tipo":"numero","op":"menor","outro_campo":"b"}`, map[string]bool{
		`{"a":9007199254740992,"b":9007199254740993}`:   true,
		`{"a":9007199254740993,"b":9007199254740993}`:   false,
		`{"a":9007199254740992.0,"b":9007199254740993}`: true,
	})
}

func TestMenorEntreCampos(t *testing.T) {
	confere(t, `{"campo":"pago","tipo":"numero","op":"menor","outro_campo":"valor"}`, map[string]bool{
		`{"pago":0.0,"valor":10}`: true, `{"pago":10,"valor":10}`: false, `{"pago":0.0,"valor":"10"}`: false,
		`{"pago":-0.0,"valor":0}`: false,
	})
}

func TestData(t *testing.T) {
	confere(t, `{"campo":"d","tipo":"data","op":"menor","valor":"2026-10-23"}`, map[string]bool{
		`{"d":"2026-10-22"}`: true, `{"d":"2026-10-23"}`: false, `{"d":"2026-02-30"}`: false,
		`{"d":"2024-02-29"}`: true, `{"d":"2023-02-29"}`: false, `{"d":"2026-1-5"}`: false,
		`{"d":"20261023"}`: false, `{"d":"2026-10-22T00:00"}`: false, `{"d":" 2026-10-22"}`: false,
		`{"d":"2026-10-22\n"}`: false, `{"d":20261022}`: false, `{"d":"0000-01-01"}`: false,
		`{"d":"1900-02-29"}`: false, `{"d":"2000-02-29"}`: true, `{"d":"2026-13-01"}`: false,
	})
}

func TestEmEComecaCom(t *testing.T) {
	confere(t, `{"campo":"t","tipo":"texto","op":"em","valor":["A","B"]}`, map[string]bool{
		`{"t":"B"}`: true, `{"t":"b"}`: false, `{"t":["B"]}`: false,
	})
	confere(t, `{"campo":"cfop","tipo":"texto","op":"comeca_com","valor":"5"}`, map[string]bool{
		`{"cfop":"5102"}`: true, `{"cfop":5102}`: false, `{"cfop":"6102"}`: false, `{"cfop":" 5102"}`: false,
	})
}

func TestBooleano(t *testing.T) {
	confere(t, `{"campo":"m","tipo":"booleano","op":"igual","valor":false}`, map[string]bool{
		`{"m":false}`: true, `{"m":0}`: false, `{"m":"false"}`: false, `{"m":null}`: false,
	})
	confere(t, `{"campo":"m","tipo":"booleano","op":"igual","valor":true}`, map[string]bool{
		`{"m":1}`: false, `{"m":true}`: true,
	})
}

func TestVazio(t *testing.T) {
	confere(t, `{"campo":"x.t","op":"vazio"}`, map[string]bool{
		`{}`: true, `{"x":null}`: true, `{"x":{"t":null}}`: true, `{"x":{"t":""}}`: true,
		`{"x":"texto"}`: true, `{"x":[{"t":"A"}]}`: true,
		`{"x":{"t":" "}}`: false, `{"x":{"t":0}}`: false, `{"x":{"t":"ACTO"}}`: false, `{"x":{"t":{}}}`: false,
	})
}

func TestChaveRepetidaValeAUltima(t *testing.T) {
	confere(t, `{"campo":"x.t","tipo":"texto","op":"igual","valor":"A"}`, map[string]bool{
		`{"x":{"t":"B","t":"A"}}`:       true,
		`{"x":{"t":"A","t":"B"}}`:       false,
		`{"x":{"t":"A"},"x":{"u":1}}`:   false,
		`{"x":{"t":"A"},"x":null}`:      false,
		`{"x":{"t":"B"},"x":{"t":"A"}}`: true,
	})
}

func TestEOuParcial(t *testing.T) {
	confere(t, `{"ou":[{"campo":"a","tipo":"texto","op":"igual","valor":"X"},{"campo":"b","tipo":"texto","op":"igual","valor":"Y"}]}`,
		map[string]bool{`{"b":"Y"}`: true, `{}`: false})
	confere(t, `{"e":[{"campo":"a","tipo":"texto","op":"igual","valor":"X"},{"campo":"b","op":"vazio"}]}`,
		map[string]bool{`{"a":"X"}`: true, `{"a":"X","b":"Z"}`: false})
}

func TestCondicoesInvalidas(t *testing.T) {
	for _, texto := range []string{
		`{"campo":"a","tipo":"texto","op":"parece","valor":"x"}`,
		`{"campo":"a","tipo":"moeda","op":"igual","valor":1}`,
		`{"campo":"a","tipo":"texto","op":"maior","valor":"x"}`,
		`{"campo":"a","tipo":"texto","op":"igual"}`,
		`{"campo":"a","tipo":"numero","op":"igual","valor":"10"}`,
		`{"campo":"a","tipo":"data","op":"igual","valor":"2026-02-30"}`,
		`{"campo":"a","tipo":"texto","op":"em","valor":[]}`,
		`{"campo":"a","tipo":"texto","op":"em","outro_campo":"b"}`,
		`{"e":[]}`, `{"ou":[]}`, `{}`, `[]`,
	} {
		x, _ := lerJSON(strings.NewReader(texto))
		c := &compilador{slots: map[string]int{}}
		if _, err := c.compilar(x); err == nil {
			t.Errorf("deveria rejeitar %s", texto)
		}
	}
}

func TestEstruturaInvalida(t *testing.T) {
	pasta := t.TempDir()
	for i, doc := range []string{`{}`, `{"regras":[{"quando":{"campo":"x","op":"vazio"}}]}`, `{"regras":[{"codigo":"A"}]}`, `{"regras":[]} x`} {
		arq := filepath.Join(pasta, "r.json")
		os.WriteFile(arq, []byte(doc), 0o644)
		if _, err := carregarRegras(arq); err == nil {
			t.Errorf("caso %d deveria falhar: %s", i, doc)
		}
	}
}

func TestReprFloat(t *testing.T) {
	for f, esperado := range map[float64]string{
		1.5: "1.5", 100: "100.0", 1e16: "1e+16", 1.5e16: "1.5e+16", 1e-5: "1e-05",
		0.0001: "0.0001", 123456789012345.6: "123456789012345.6", -0.0: "0.0", 2.5e-7: "2.5e-07",
	} {
		if got := reprFloat(f); got != esperado {
			t.Errorf("reprFloat(%v) = %s, esperado %s", f, got, esperado)
		}
	}
}

// rodar executa o motor com as regras do repositório sobre a entrada dada.
func rodar(t *testing.T, entrada string, regras string) (string, string, int) {
	t.Helper()
	pasta := t.TempDir()
	arq := filepath.Join(pasta, "entrada.jsonl")
	os.WriteFile(arq, []byte(entrada), 0o644)
	if regras == "" {
		regras = filepath.Join("regras", "duplicatas.json")
	}
	var out, errb bytes.Buffer
	cod := executar([]string{"--entrada", arq, "--regras", regras}, &out, &errb)
	return out.String(), errb.String(), cod
}

func linha(doc map[string]any) string {
	b, _ := json.Marshal(doc)
	return string(b)
}

func TestContratoBasico(t *testing.T) {
	out, _, cod := rodar(t, `{"id":1,"status":"ATIVA"}`+"\n"+`{"id":2,"status":"CANCELADA"}`+"\n", "")
	if cod != 0 || out != "id:1 - regra: SEM_REGRA\nid:2 - regra: R01\n" {
		t.Fatalf("código %d, saída %q", cod, out)
	}
}

func TestBomCrlfEAcento(t *testing.T) {
	entrada := "\xef\xbb\xbf" + `{"id":1,"status":"CANCELADA","obs":"São Paulo"}` + "\r\n" + `{"id":2,"status":"ATIVA"}` + "\r\n"
	out, _, _ := rodar(t, entrada, "")
	if out != "id:1 - regra: R01\nid:2 - regra: SEM_REGRA\n" {
		t.Fatalf("saída %q", out)
	}
}

func TestLinhaInvalidaNaoPara(t *testing.T) {
	out, errs, cod := rodar(t, "{quebrado\n[1]\n"+`{"x": 1}`+"\n\n"+`{"id":2,"status":"CANCELADA"}`+"\n", "")
	if cod != 0 || out != "id:2 - regra: R01\n" {
		t.Fatalf("código %d, saída %q", cod, out)
	}
	avisos := strings.Split(strings.TrimSpace(errs), "\n")
	if len(avisos) != 3 || !strings.HasPrefix(avisos[0], "linha 1:") {
		t.Fatalf("avisos %q", avisos)
	}
}

func TestIds(t *testing.T) {
	out, _, _ := rodar(t, strings.Join([]string{
		`{"id":"7"}`, `{"id":5}`, `{"id":5,"status":"CANCELADA"}`, `{"id":1.0}`, `{"id":-0}`,
		`{"id":true}`, `{"id":null}`, `{"id":1,"id":9}`,
	}, "\n"), "")
	esperado := "id:7 - regra: SEM_REGRA\nid:5 - regra: SEM_REGRA\nid:5 - regra: R01\nid:1.0 - regra: SEM_REGRA\n" +
		"id:0 - regra: SEM_REGRA\nid:True - regra: SEM_REGRA\nid:9 - regra: SEM_REGRA\n"
	if out != esperado {
		t.Fatalf("saída %q", out)
	}
}

func TestEntradaVazia(t *testing.T) {
	out, _, cod := rodar(t, "", "")
	if cod != 0 || out != "" {
		t.Fatalf("código %d, saída %q", cod, out)
	}
}

func TestRegrasInvalidas(t *testing.T) {
	arq := filepath.Join(t.TempDir(), "regras.json")
	os.WriteFile(arq, []byte(`{"regras":[{"codigo":"X","quando":{"campo":"a","tipo":"texto","op":"parece","valor":"b"}}]}`), 0o644)
	out, errs, cod := rodar(t, `{"id":1}`+"\n", arq)
	if cod != 2 || out != "" || !strings.Contains(errs, "parece") {
		t.Fatalf("código %d, saída %q, erro %q", cod, out, errs)
	}
}

func TestTrocarAOrdemMudaAClassificacao(t *testing.T) {
	doc := `{"id":1,"status":"CANCELADA","manifestacao":{"tipo":"ACTO"},"logistica":{"migo":true}}` + "\n"
	if out, _, _ := rodar(t, doc, ""); out != "id:1 - regra: R01\n" {
		t.Fatalf("padrão: %q", out)
	}
	if out, _, _ := rodar(t, doc, filepath.Join("regras", "exemplo_ordem_invertida.json")); out != "id:1 - regra: R11\n" {
		t.Fatalf("invertida: %q", out)
	}
}

func TestConjuntoPequeno(t *testing.T) {
	entrada, err := os.ReadFile(filepath.Join("kit", "dados", "pequeno", "entrada.jsonl"))
	if err != nil {
		t.Skip("kit ausente")
	}
	gabarito, _ := os.ReadFile(filepath.Join("kit", "dados", "pequeno", "gabarito.txt"))
	m, err := carregarRegras(filepath.Join("regras", "duplicatas.json"))
	if err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	w := bufio.NewWriter(&out)
	m.classificar(entrada, w, func(string) {})
	w.Flush()
	esperado := map[string]bool{}
	for _, l := range strings.Split(strings.TrimSpace(string(gabarito)), "\n") {
		esperado[strings.Join(strings.Fields(l), " ")] = true
	}
	for _, l := range strings.Split(strings.TrimSpace(out.String()), "\n") {
		if !esperado[l] {
			t.Errorf("linha fora do gabarito: %s", l)
		}
	}
}

// BenchmarkGrande mede só o processamento; MOTOR_GRANDE aponta para a entrada descompactada.
func BenchmarkGrande(b *testing.B) {
	arq := os.Getenv("MOTOR_GRANDE")
	if arq == "" {
		b.Skip("defina MOTOR_GRANDE")
	}
	dados, err := os.ReadFile(arq)
	if err != nil {
		b.Fatal(err)
	}
	m, err := carregarRegras(filepath.Join("regras", "duplicatas.json"))
	if err != nil {
		b.Fatal(err)
	}
	b.SetBytes(int64(len(dados)))
	for b.Loop() {
		w := bufio.NewWriter(io.Discard)
		m.classificar(dados, w, func(string) {})
		w.Flush()
	}
}

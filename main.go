// Motor de regras: classifica cada linha de um JSON Lines pela primeira regra satisfeita.
//
// As regras vêm de um arquivo JSON; este programa não conhece nenhuma regra de domínio.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

func main() {
	os.Exit(executar(os.Args[1:], os.Stdout, os.Stderr))
}

// regrasPadrao aponta para regras/duplicatas.json ao lado do executável.
func regrasPadrao() string {
	exe, err := os.Executable()
	if err != nil {
		return filepath.Join("regras", "duplicatas.json")
	}
	return filepath.Join(filepath.Dir(exe), "regras", "duplicatas.json")
}

func executar(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("motor", flag.ContinueOnError)
	fs.SetOutput(stderr)
	entrada := fs.String("entrada", "", "arquivo JSON Lines, uma duplicata por linha")
	arqRegras := fs.String("regras", regrasPadrao(), "arquivo de regras (padrão: regras/duplicatas.json)")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	avisar := func(msg string) { fmt.Fprintln(stderr, msg) }
	if *entrada == "" {
		avisar("erro: o argumento --entrada é obrigatório")
		return 2
	}

	m, err := carregarRegras(*arqRegras)
	if err != nil {
		avisar("erro nas regras: " + err.Error())
		return 2
	}
	dados, err := os.ReadFile(*entrada)
	if err != nil {
		avisar("erro na entrada: " + err.Error())
		return 1
	}
	w := bufio.NewWriterSize(stdout, 1<<20)
	m.classificar(dados, w, avisar)
	if err := w.Flush(); err != nil {
		avisar("erro ao escrever a saída: " + err.Error())
		return 1
	}
	return 0
}

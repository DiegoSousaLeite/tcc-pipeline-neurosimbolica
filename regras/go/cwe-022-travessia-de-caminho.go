package exemplo

// Arquivo de teste da regra, no formato que `semgrep --test` consome. Escrito à
// mão a partir do idioma de Go — nenhum trecho veio da população.

import (
	"net/http"
	"os"
	"path/filepath"
)

const baseDir = "/srv/arquivos"

func baixar(w http.ResponseWriter, r *http.Request) {
	nome := r.URL.Query().Get("arquivo")
	// ruleid: caminho-de-entrada-externa-sem-restricao
	dados, err := os.ReadFile(filepath.Join(baseDir, nome))
	if err != nil {
		http.Error(w, "erro", http.StatusNotFound)
		return
	}
	w.Write(dados)
}

func servir(w http.ResponseWriter, r *http.Request) {
	nome := r.FormValue("doc")
	// ruleid: caminho-de-entrada-externa-sem-restricao
	http.ServeFile(w, r, filepath.Join(baseDir, nome))
}

func abrir(w http.ResponseWriter, r *http.Request) {
	nome := r.Header.Get("X-Arquivo")
	// ruleid: caminho-de-entrada-externa-sem-restricao
	f, err := os.Open(filepath.Join(baseDir, nome))
	if err != nil {
		return
	}
	defer f.Close()
}

// Caminho fixo: não há entrada externa alguma.
func configuracao() ([]byte, error) {
	// ok: caminho-de-entrada-externa-sem-restricao
	return os.ReadFile(filepath.Join(baseDir, "config.yaml"))
}

// Entrada externa que não chega a arquivo nenhum.
func ecoar(w http.ResponseWriter, r *http.Request) {
	nome := r.URL.Query().Get("arquivo")
	// ok: caminho-de-entrada-externa-sem-restricao
	w.Write([]byte(nome))
}

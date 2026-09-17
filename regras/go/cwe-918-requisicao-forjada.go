package exemplo

// Arquivo de teste da regra, no formato que `semgrep --test` consome. Escrito à
// mão a partir do idioma de Go — nenhum trecho veio da população.

import (
	"io"
	"net/http"
)

func buscar(w http.ResponseWriter, r *http.Request) {
	alvo := r.URL.Query().Get("url")
	// ruleid: requisicao-a-url-de-entrada-externa
	resp, err := http.Get(alvo)
	if err != nil {
		return
	}
	defer resp.Body.Close()
	io.Copy(w, resp.Body)
}

func encaminhar(w http.ResponseWriter, r *http.Request) {
	destino := r.FormValue("callback")
	// ruleid: requisicao-a-url-de-entrada-externa
	req, err := http.NewRequest("POST", destino, r.Body)
	if err != nil {
		return
	}
	http.DefaultClient.Do(req)
}

func comCliente(w http.ResponseWriter, r *http.Request) {
	alvo := r.Header.Get("X-Webhook")
	cliente := &http.Client{}
	// ruleid: requisicao-a-url-de-entrada-externa
	cliente.Get(alvo)
}

// URL fixa: não há entrada externa alguma.
func sondar() (*http.Response, error) {
	// ok: requisicao-a-url-de-entrada-externa
	return http.Get("https://exemplo.internal/health")
}

// Entrada externa que não vira requisição.
func ecoar(w http.ResponseWriter, r *http.Request) {
	alvo := r.URL.Query().Get("url")
	// ok: requisicao-a-url-de-entrada-externa
	w.Write([]byte(alvo))
}

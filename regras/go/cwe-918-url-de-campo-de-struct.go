package exemplo

// Arquivo de teste da regra, no formato que `semgrep --test` consome. Os
// exemplos foram escritos à mão — nenhum trecho veio da população.

import (
	"context"
	"net/http"
)

type pedido struct {
	CallbackURL string
	Nome        string
}

type estado struct {
	SrcUri string
}

func notificar(p *pedido) (*http.Response, error) {
	// ruleid: url-de-campo-de-struct-em-cliente-http
	return http.Get(p.CallbackURL)
}

func baixar(ctx context.Context, s *estado, c *http.Client) error {
	// ruleid: url-de-campo-de-struct-em-cliente-http
	req, err := http.NewRequestWithContext(ctx, "GET", s.SrcUri, nil)
	if err != nil {
		return err
	}
	_, err = c.Do(req)
	return err
}

func publicar(p *pedido, c *http.Client) (*http.Response, error) {
	// ruleid: url-de-campo-de-struct-em-cliente-http
	return c.Post(p.CallbackURL, "application/json", nil)
}

// Campo cujo nome não sugere endereço: fica de fora do recorte.
func consultar(p *pedido) (*http.Response, error) {
	// ok: url-de-campo-de-struct-em-cliente-http
	return http.Get("https://exemplo.internal/q?n=" + p.Nome)
}

// URL fixa.
func sondar() (*http.Response, error) {
	// ok: url-de-campo-de-struct-em-cliente-http
	return http.Get("https://exemplo.internal/health")
}

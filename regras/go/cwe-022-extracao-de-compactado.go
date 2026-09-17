package exemplo

// Arquivo de teste da regra, no formato que `semgrep --test` consome. Os
// exemplos foram escritos à mão a partir do idioma de extração de compactado —
// nenhum trecho veio da população, nem da partição de desenvolvimento.

import (
	"archive/tar"
	"archive/zip"
	"os"
	"path/filepath"
)

func extrairZip(f *zip.File, destino string) error {
	caminho := filepath.Join(destino, f.Name)
	// ruleid: extracao-de-compactado-sem-prender-a-base
	saida, err := os.Create(caminho)
	if err != nil {
		return err
	}
	defer saida.Close()
	return nil
}

func criarDiretorio(f *zip.File, destino string) error {
	caminho := filepath.Join(destino, f.Name)
	// ruleid: extracao-de-compactado-sem-prender-a-base
	return os.MkdirAll(caminho, 0o750)
}

func extrairTar(h *tar.Header, destino string) error {
	caminho := filepath.Join(destino, h.Header.Name)
	// ruleid: extracao-de-compactado-sem-prender-a-base
	return os.WriteFile(caminho, nil, 0o600)
}

// Caminho fixo, sem nome de entrada.
func marcador(destino string) error {
	caminho := filepath.Join(destino, ".extraido")
	// ok: extracao-de-compactado-sem-prender-a-base
	return os.WriteFile(caminho, nil, 0o600)
}

// Nome de entrada que não vira arquivo.
func listar(f *zip.File, destino string) string {
	caminho := filepath.Join(destino, f.Name)
	// ok: extracao-de-compactado-sem-prender-a-base
	return caminho
}

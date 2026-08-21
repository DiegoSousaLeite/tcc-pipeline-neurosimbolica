"""Fixtures de dataset escritas à mão.

São entradas sintéticas no formato de `data/dataset_go_limpo.json`, não recortes
do dataset real: os testes precisam de casos-limite (só arquivo de teste, mistura
de extensões, location única) que o dataset não garante conter.
"""


def _entrada(finding_id, ground_truth, cwe, arquivos, commit="a" * 40,
             repo="acme/servico"):
    return {
        "finding_id": finding_id,
        "repo_name": repo,
        "repo_url": f"https://github.com/{repo}",
        "commit_hash": commit,
        "ground_truth": ground_truth,
        "metadata": {
            "cwe_id": cwe,
            "cwe_name": f"Nome de {cwe}",
            "num_findings": len(arquivos),
            "source": "semgrep" if ground_truth == "false_positive" else "cvefixes",
            "aggregation_type": "cwe_per_commit",
        },
        "to_analyzer": {
            "vulnerability_type": cwe,
            "description": f"Descrição de {cwe}.",
            "locations": [{"file": a, "function": "", "line_start": 1,
                           "line_end": 2} for a in arquivos],
        },
    }


def dataset_minimo():
    """Dataset sintético cobrindo os casos-limite das três trilhas."""
    return [
        # FP com 3 locations: .go, .html (descartada), .go
        _entrada("fp1", "false_positive", "CWE-79",
                 ["handler.go", "relatorio.html", "render.go"]),
        # FP com location única
        _entrada("fp2", "false_positive", "CWE-327", ["cripto.go"],
                 commit="b" * 40),
        # TP com 4 locations: .go, _test.go (descartada), .md (descartada), .go
        _entrada("tp1", "true_positive", "CWE-290",
                 ["middleware/header.go", "middleware/header_test.go",
                  "CHANGELOG.md", "auth/token.go"], commit="c" * 40),
        # TP em que TODAS as locations .go são de teste
        _entrada("tp2", "true_positive", "CWE-352",
                 ["csrf_test.go", "docs.md"], commit="d" * 40),
    ]


CODIGO_GO = """package main

import "fmt"

func alpha(x int) int {
	if x > 0 {
		return x * 2
	}
	return 0
}

func beta(nome string) {
	fmt.Println(nome)
}
""".splitlines()

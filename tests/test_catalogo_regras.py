"""Fichas indexadas pela regra do Semgrep (change ficha-por-regra-semgrep)."""
import json

import pytest

from src.catalogo import (
    CHAVE_FALLBACK,
    CHAVE_REGRAS,
    ORIGEM_ESPECIFICA,
    ORIGEM_FALLBACK,
    ORIGEM_REGRA,
    Catalogo,
    CatalogoInvalido,
)
from src.fase2_middleware import VALOR_NEUTRO

REGRA_TLS = "go.lang.security.audit.crypto.missing-ssl-minversion.missing-ssl-minversion"


def _ficha(marca):
    return {
        "definicao": f"definição {marca}",
        "heuristica_go": f"heurística {marca}",
        "exemplo_vp": {"codigo": f"// vp {marca}", "porque": f"vp {marca}"},
        "exemplo_fp": {"codigo": f"// fp {marca}", "porque": f"fp {marca}"},
    }


def _catalogo(tmp_path, regras=None):
    dados = {"CWE-327": _ficha("cwe327"), CHAVE_FALLBACK: _ficha("fallback")}
    if regras is not None:
        dados[CHAVE_REGRAS] = regras
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return Catalogo.carregar(str(p))


def test_regra_com_ficha_propria_tem_precedencia(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    f = cat.ficha("CWE-327", check_id=REGRA_TLS)
    assert f.origem == ORIGEM_REGRA
    assert f.definicao == "definição tls"


def test_regra_sem_ficha_cai_na_ficha_da_cwe(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    f = cat.ficha("CWE-327", check_id="go.lang.security.outra.outra")
    assert f.origem == ORIGEM_ESPECIFICA
    assert f.definicao == "definição cwe327"


def test_sem_regra_vale_a_ficha_da_cwe_ou_o_fallback(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    assert cat.ficha("CWE-327").origem == ORIGEM_ESPECIFICA
    # Candidato injetado do gabarito: o valor neutro não é chave de ficha.
    assert cat.ficha("CWE-327", check_id=VALOR_NEUTRO).origem == ORIGEM_ESPECIFICA
    assert cat.ficha("CWE-1", check_id=None).origem == ORIGEM_FALLBACK


def test_casamento_e_pelo_check_id_completo(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    assert cat.ficha("CWE-327", check_id="missing-ssl-minversion").origem \
        == ORIGEM_ESPECIFICA
    assert cat.ficha("CWE-327", check_id="outro.pacote.missing-ssl-minversion"
                     ".missing-ssl-minversion").origem == ORIGEM_ESPECIFICA


def test_ficha_de_regra_preserva_a_cwe_do_caso(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    f = cat.ficha("CWE-327", cwe_name="Broken Crypto", check_id=REGRA_TLS)
    assert f.cwe == "CWE-327"
    assert f.nome == "Broken Crypto"


def test_regra_de_cwe_sem_ficha_ainda_usa_a_ficha_da_regra(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    f = cat.ficha("CWE-9999", check_id=REGRA_TLS)
    assert f.origem == ORIGEM_REGRA and f.cwe == "CWE-9999"


def test_bloco_regras_nao_vira_cwe(tmp_path):
    cat = _catalogo(tmp_path, {REGRA_TLS: _ficha("tls")})
    assert CHAVE_REGRAS not in cat.dados
    assert CHAVE_REGRAS not in cat.cwes_especificas
    assert not cat.tem_ficha(CHAVE_REGRAS)


def test_catalogo_sem_bloco_regras_continua_valido(tmp_path):
    cat = _catalogo(tmp_path)
    assert cat.regras == {}
    assert cat.ficha("CWE-327", check_id=REGRA_TLS).origem == ORIGEM_ESPECIFICA


def test_ficha_de_regra_malformada_nomeia_a_regra(tmp_path):
    ruim = _ficha("tls")
    ruim["heuristica_go"] = ""
    with pytest.raises(CatalogoInvalido, match="missing-ssl-minversion.*heuristica_go"):
        _catalogo(tmp_path, {REGRA_TLS: ruim})


def test_exemplo_de_regra_sem_porque_e_recusado(tmp_path):
    ruim = _ficha("tls")
    ruim["exemplo_fp"]["porque"] = ""
    with pytest.raises(CatalogoInvalido, match="porque"):
        _catalogo(tmp_path, {REGRA_TLS: ruim})


def test_bloco_regras_que_nao_e_objeto_e_recusado(tmp_path):
    with pytest.raises(CatalogoInvalido, match="regras"):
        _catalogo(tmp_path, [REGRA_TLS])


# --- Conteúdo do catálogo congelado -----------------------------------------

import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

from src.catalogo import catalogo_padrao  # noqa: E402
from tests.test_catalogo import (  # noqa: E402
    SEM_ACENTO_PROIBIDO,
    _apis,
    _tem_acento,
)


def _todas_as_fichas():
    cat = catalogo_padrao()
    fichas = {c: f for c, f in cat.dados.items() if c != CHAVE_FALLBACK}
    fichas.update(cat.regras)
    return fichas


def test_catalogo_real_tem_fichas_de_regra():
    cat = catalogo_padrao()
    assert REGRA_TLS in cat.regras
    assert len(cat.regras) >= 8


@pytest.mark.parametrize("chave", sorted(_todas_as_fichas()))
def test_heuristica_declara_condicao_de_vp_e_de_fp(chave):
    h = _todas_as_fichas()[chave]["heuristica_go"]
    assert "É VP quando" in h, chave
    assert "É FP quando" in h, chave


# Regras cujo alvo é construção nativa da linguagem, sem `pacote.Func` que o
# detector de API enxergue. O par continua usando a MESMA construção.
CONSTRUCAO_NATIVA = {
    # `make(map...)` seguido de `range` sobre o mapa: é o que a regra casa.
    "trailofbits.go.iterate-over-empty-map.iterate-over-empty-map": "make(map[",
}


@pytest.mark.parametrize("regra", sorted(catalogo_padrao().regras))
def test_ficha_de_regra_segue_as_regras_de_conteudo(regra):
    f = catalogo_padrao().regras[regra]
    if regra in CONSTRUCAO_NATIVA:
        marca = CONSTRUCAO_NATIVA[regra]
        assert marca in f["exemplo_vp"]["codigo"] and marca in f["exemplo_fp"]["codigo"]
    else:
        comum = _apis(f["exemplo_vp"]["codigo"]) & _apis(f["exemplo_fp"]["codigo"])
        assert comum, f"{regra}: VP e FP não compartilham nenhuma API"
    assert f["exemplo_vp"]["codigo"] != f["exemplo_fp"]["codigo"]
    prosa = [f["definicao"], f["heuristica_go"], f["exemplo_vp"]["porque"],
             f["exemplo_fp"]["porque"]]
    for texto in prosa:
        assert _tem_acento(texto), f"{regra}: prosa sem acento"
    palavras = set(re.findall(r"[a-zà-ÿ]+", " ".join(prosa).lower()))
    assert not palavras & set(SEM_ACENTO_PROIBIDO), regra
    for lado in ("exemplo_vp", "exemplo_fp"):
        for linha in f[lado]["codigo"].splitlines():
            if "//" in linha:
                comentario = set(re.findall(r"[a-zà-ÿ]+", linha.split("//", 1)[1].lower()))
                assert not comentario & set(SEM_ACENTO_PROIBIDO), regra


def test_ficha_de_tls_usa_a_construcao_da_regra():
    f = catalogo_padrao().regras[REGRA_TLS]
    for lado in ("exemplo_vp", "exemplo_fp"):
        codigo = f[lado]["codigo"]
        assert "tls.Config" in codigo
        assert "MinVersion:" not in codigo   # a regra só dispara sem MinVersion
        assert "md5" not in codigo and "sha1" not in codigo


def _como_arquivo_go(codigo):
    """Embrulha o exemplo num arquivo Go para o parser: declarações de topo
    ficam como estão; trechos soltos viram corpo de função."""
    topo = re.match(r"\s*(//.*\n)*\s*(func|var|const|type)\b", codigo)
    corpo = codigo if topo else "func _() {\n" + codigo + "\n}"
    return "package exemplo\n\n" + corpo + "\n"


@pytest.mark.skipif(shutil.which("gofmt") is None, reason="gofmt ausente")
def test_todos_os_exemplos_sao_go_valido(tmp_path):
    cat = catalogo_padrao()
    fichas = dict(cat.dados)
    fichas.update(cat.regras)
    for chave, f in fichas.items():
        for lado in ("exemplo_vp", "exemplo_fp"):
            p = tmp_path / "x.go"
            p.write_text(_como_arquivo_go(f[lado]["codigo"]), encoding="utf-8")
            r = subprocess.run(["gofmt", "-e", "-l", str(p)],
                               capture_output=True, text=True)
            assert r.returncode == 0, f"{chave}/{lado}: {r.stderr}"


_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRIVIAL = re.compile(r"^[\s{}()\[\],;]*$|^\s*(return|return nil|return err|"
                      r"if err != nil \{|\}\)?|else \{)\s*$")


# Linha mais curta que isto é idioma (`return true`, `c.mu.Lock()`), não
# conteúdo capaz de identificar de onde um trecho foi copiado.
_MINIMO_DISTINTIVO = 15


def _normalizar(linhas):
    """Linhas de código sem comentário, sem espaço nas pontas e sem as triviais."""
    saida = []
    for linha in linhas:
        s = linha.split("//", 1)[0].strip()
        if len(s) >= _MINIMO_DISTINTIVO and not _TRIVIAL.match(s):
            saida.append(s)
    return saida


def _pares(linhas):
    return set(zip(linhas, linhas[1:]))


def _pares_dos_exemplos():
    cat = catalogo_padrao()
    fichas = dict(cat.dados)
    fichas.update(cat.regras)
    pares = {}
    for chave, f in fichas.items():
        for lado in ("exemplo_vp", "exemplo_fp"):
            for par in _pares(_normalizar(f[lado]["codigo"].splitlines())):
                pares.setdefault(par, f"{chave}/{lado}")
    return pares


@pytest.mark.skipif(not os.path.isdir(os.path.join(_RAIZ, "cache")),
                    reason="cache de fontes ausente")
def test_nenhum_exemplo_reproduz_trecho_das_amostras():
    """Protocolo anti-viés: nenhum trecho dos exemplos aparece nos arquivos das
    amostras avaliadas (cache de fontes e contexto do cache simbólico).

    "Trecho" é um par de linhas não triviais CONSECUTIVAS. Linha isolada não
    serve de critério: idiomas da stdlib como `mux := http.NewServeMux()` ou
    `w.Header().Set("Content-Type", "application/json")` aparecem em qualquer
    código Go e em qualquer exemplo que use a mesma API, sem que um tenha sido
    copiado do outro.
    """
    alvo = _pares_dos_exemplos()
    achadas = {}
    for pasta in ("cache", "cache_simbolico"):
        for dirpath, _, arquivos in os.walk(os.path.join(_RAIZ, pasta)):
            for nome in arquivos:
                caminho = os.path.join(dirpath, nome)
                try:
                    with open(caminho, encoding="utf-8", errors="ignore") as fh:
                        conteudo = fh.read()
                except OSError:
                    continue
                if nome.endswith(".json"):
                    # Cache simbólico: o código está no contexto hidratado.
                    try:
                        conteudo = json.loads(conteudo).get("contexto_hidratado") or ""
                    except (ValueError, AttributeError):
                        continue
                for par in alvo.keys() & _pares(_normalizar(conteudo.splitlines())):
                    achadas.setdefault(alvo[par], (par, caminho))
    assert not achadas, f"exemplos que reproduzem trecho das amostras: {achadas}"

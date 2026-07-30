"""Testes do catálogo de triagem por CWE (tarefas 5.2, 5.3 e 5.4)."""
import json
import re
import unicodedata

import pytest

from src.catalogo import (
    CHAVE_FALLBACK,
    Catalogo,
    CatalogoInvalido,
    catalogo_padrao,
)

# As 15 CWEs de maior volume, medidas por scripts/ranking_cwe.py.
CWES_ESPERADAS = [
    "CWE-79", "CWE-327", "CWE-94", "CWE-319", "CWE-338", "CWE-665", "CWE-328",
    "CWE-614", "CWE-601", "CWE-470", "CWE-115", "CWE-352", "CWE-681",
    "CWE-1004", "CWE-667",
]


@pytest.fixture(scope="module")
def catalogo():
    return Catalogo.carregar()


# --- 5.3 Conteúdo das fichas -----------------------------------------------

def test_catalogo_carrega_e_tem_as_quinze_mais_o_fallback(catalogo):
    assert sorted(catalogo.cwes_especificas) == sorted(CWES_ESPERADAS)
    assert CHAVE_FALLBACK in catalogo.dados
    assert len(catalogo.dados) == 16


def test_todos_os_campos_preenchidos(catalogo):
    for cwe in list(CWES_ESPERADAS) + [CHAVE_FALLBACK]:
        bruto = catalogo.dados[cwe]
        assert bruto["definicao"].strip()
        assert bruto["heuristica_go"].strip()
        for lado in ("exemplo_vp", "exemplo_fp"):
            assert bruto[lado]["codigo"].strip()
            assert bruto[lado]["porque"].strip()


def test_heuristica_menciona_identificador_real_da_stdlib(catalogo):
    """A heurística tem que dar um sinal concreto a procurar, não conselho
    genérico: sem identificador de Go ela não ajuda a triar."""
    for cwe in CWES_ESPERADAS:
        h = catalogo.dados[cwe]["heuristica_go"]
        assert any(t in h for t in (".", "()", "crypto/", "net/", "http.")), cwe
        assert len(h) > 150, f"{cwe}: heurística curta demais para ser útil"


def _apis(codigo):
    """Identificadores de API chamados no trecho: `pacote.Func`, `x.Metodo` e
    conversões numéricas estreitantes."""
    return (set(re.findall(r"[A-Za-z_]\w*\.[A-Z]\w*", codigo))
            | set(re.findall(r"\b(?:u?int(?:8|16|32|64)?)\(", codigo)))


# Fichas em que VP e FP não compartilham a API central, com o motivo. Manter
# esta lista curta e justificada: cada entrada é uma ficha que ensina o modelo a
# reconhecer API em vez de julgar contexto.
SEM_API_COMUM = {
    # Ficha genérica: por definição não tem API específica. O par contrasta
    # origem da entrada (externa vs constante) sobre um `operacaoPerigosa`
    # abstrato, que é o critério que o fallback existe para ensinar.
    CHAVE_FALLBACK,
}


def test_par_contrastante_usa_a_mesma_api(catalogo):
    """Coração do catálogo: se o par contrastar APIs diferentes, o modelo
    aprende a reconhecer a API em vez de julgar o contexto.

    Computa a interseção em vez de conferir uma âncora fixa por CWE — assim o
    teste continua valendo se uma ficha for reescrita com outra API.
    """
    for cwe, ficha in catalogo.dados.items():
        comum = _apis(ficha["exemplo_vp"]["codigo"]) & _apis(ficha["exemplo_fp"]["codigo"])
        if cwe in SEM_API_COMUM:
            continue
        assert comum, f"{cwe}: VP e FP não compartilham nenhuma API"


def test_pares_de_calibragem_do_briefing(catalogo):
    """Os dois pares já decididos no briefing: `md5.Sum` senha/cache e
    `math/rand` token/jitter. Conferidos pela API e pela semântica do
    `porque`, não por nome de função — a redação das fichas é livre."""
    c327 = catalogo.dados["CWE-327"]
    assert "md5.Sum" in c327["exemplo_vp"]["codigo"]
    assert "md5.Sum" in c327["exemplo_fp"]["codigo"]
    assert any(t in c327["exemplo_vp"]["porque"].lower()
               for t in ("senha", "credencial"))
    assert "cache" in c327["exemplo_fp"]["porque"].lower()

    c338 = catalogo.dados["CWE-338"]
    assert "rand." in c338["exemplo_vp"]["codigo"]
    assert "rand." in c338["exemplo_fp"]["codigo"]
    assert any(t in c338["exemplo_vp"]["porque"].lower()
               for t in ("token", "sessao", "sessão"))
    assert "jitter" in c338["exemplo_fp"]["porque"].lower()


def test_exemplos_nao_sao_iguais(catalogo):
    for cwe, ficha in catalogo.dados.items():
        assert ficha["exemplo_vp"]["codigo"] != ficha["exemplo_fp"]["codigo"], cwe
        assert ficha["exemplo_vp"]["porque"] != ficha["exemplo_fp"]["porque"], cwe


def _tem_acento(texto):
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", texto))


def test_texto_esta_em_portugues_acentuado(catalogo):
    """O briefing exige português do Brasil, e este texto vai para dois lugares:
    o prompt do LLM e o apêndice da monografia. Um trecho de 190+ caracteres de
    português sem um único diacrítico é texto não acentuado, não coincidência.

    Não vale para identificadores de código nem para valores de literais — esses
    ficam em ASCII por convenção da linguagem.
    """
    for cwe, ficha in catalogo.dados.items():
        campos = {
            "definicao": ficha["definicao"],
            "heuristica_go": ficha["heuristica_go"],
            "exemplo_vp.porque": ficha["exemplo_vp"]["porque"],
            "exemplo_fp.porque": ficha["exemplo_fp"]["porque"],
        }
        for nome, valor in campos.items():
            assert _tem_acento(valor), f"{cwe}/{nome} não tem nenhum acento"


# Formas sem acento de palavras que sempre levam acento em português. A checagem
# roda só sobre a PROSA (definição, heurística, porque) — nos corpos de código
# esses mesmos radicais aparecem legitimamente em ASCII, como nome de parâmetro
# (`usuario`) ou valor de literal.
SEM_ACENTO_PROIBIDO = [
    "nao", "sao", "funcao", "funcoes", "codigo", "sessao", "usuario", "metodo",
    "metodos", "conversao", "conversoes", "validacao", "operacao", "informacao",
    "aplicacao", "execucao", "inicializacao", "autenticacao", "requisicao",
    "requisicoes", "transmissao", "criptografico", "previsivel", "sequencia",
    "adversario", "dispersao", "proprio", "conteudo", "pagina", "vitima",
    "logica", "parametro", "ausencia", "protecao", "binario", "alcancavel",
    "rapido", "aleatorios", "sensivel", "sensiveis", "confiavel", "reflexao",
    "injecao", "geracao", "seguranca", "definicao", "acoes",
]


def test_prosa_sem_palavra_desacentuada(catalogo):
    """Guarda de regressão: pega a reintrodução de texto sem acento palavra a
    palavra, não só a ausência total de diacríticos na ficha."""
    for cwe, ficha in catalogo.dados.items():
        prosa = " ".join([ficha["definicao"], ficha["heuristica_go"],
                          ficha["exemplo_vp"]["porque"],
                          ficha["exemplo_fp"]["porque"]]).lower()
        palavras = set(re.findall(r"[a-zà-ÿ]+", prosa))
        achadas = sorted(palavras & set(SEM_ACENTO_PROIBIDO))
        assert not achadas, f"{cwe}: prosa com palavra sem acento {achadas}"


def test_comentarios_do_codigo_acentuados(catalogo):
    """O briefing pede os comentários dos exemplos em português também.

    Comentário é opcional — a ficha de calibragem de CWE-327 no próprio briefing
    não tem nenhum. O que se exige é que os que existem estejam acentuados.
    """
    comentarios = []
    for cwe, ficha in catalogo.dados.items():
        for lado in ("exemplo_vp", "exemplo_fp"):
            for linha in ficha[lado]["codigo"].splitlines():
                if "//" in linha:
                    comentarios.append((f"{cwe}/{lado}", linha.split("//", 1)[1]))
    assert len(comentarios) >= 20, "os exemplos perderam os comentários"

    for origem, texto in comentarios:
        achadas = sorted(set(re.findall(r"[a-zà-ÿ]+", texto.lower()))
                         & set(SEM_ACENTO_PROIBIDO))
        assert not achadas, f"{origem}: comentário com palavra sem acento {achadas}"


# --- 5.4 Carregador ---------------------------------------------------------

def test_ficha_de_cwe_coberta(catalogo):
    f = catalogo.ficha("CWE-327")
    assert f.origem == "especifica"
    assert f.especifica
    assert "md5" in f.heuristica_go.lower()


def test_ficha_de_cwe_nao_coberta_cai_no_fallback(catalogo):
    f = catalogo.ficha("CWE-99999")
    assert f.origem == "fallback"
    assert not f.especifica
    # O fallback preenche TODAS as camadas: nenhuma seção do prompt fica vazia.
    assert f.definicao and f.heuristica_go
    assert f.exemplo_vp["codigo"] and f.exemplo_fp["codigo"]
    assert f.cwe == "CWE-99999"   # a ficha genérica não apaga a CWE do caso


def test_nome_do_dataset_tem_precedencia(catalogo):
    """`nome` na ficha é OPCIONAL: o esquema do briefing tem quatro campos, e o
    nome da CWE normalmente vem do `cwe_name` do dataset. Quando nenhum dos dois
    existe, o cabeçalho do prompt fica só com o identificador da CWE — a
    definição vem na linha seguinte, então nada quebra."""
    f = catalogo.ficha("CWE-327", cwe_name="Use of Broken Crypto")
    assert f.nome == "Use of Broken Crypto"
    # Sem cwe_name do dataset: usa o do catálogo se houver, senão string vazia.
    assert catalogo.ficha("CWE-327").nome == catalogo.dados["CWE-327"].get("nome", "")


def test_fallback_nao_e_tratado_como_cwe_especifica(catalogo):
    assert not catalogo.tem_ficha(CHAVE_FALLBACK)
    assert CHAVE_FALLBACK not in catalogo.cwes_especificas


def test_sha256_e_dos_bytes_do_arquivo(catalogo, tmp_path):
    import hashlib
    with open(catalogo.caminho, "rb") as f:
        esperado = hashlib.sha256(f.read()).hexdigest()
    assert catalogo.sha256 == esperado
    assert len(catalogo.sha256) == 64


def test_sha256_muda_quando_o_arquivo_muda(tmp_path, catalogo):
    alterado = tmp_path / "catalogo.json"
    dados = json.loads(json.dumps(catalogo.dados))
    dados["CWE-327"]["definicao"] += " (editado)"
    alterado.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    assert Catalogo.carregar(str(alterado)).sha256 != catalogo.sha256


def test_catalogo_padrao_e_unico():
    assert catalogo_padrao() is catalogo_padrao()


# --- Validação do esquema ---------------------------------------------------

def _gravar(tmp_path, dados):
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_catalogo_sem_fallback_e_recusado(tmp_path, catalogo):
    dados = json.loads(json.dumps(catalogo.dados))
    del dados[CHAVE_FALLBACK]
    with pytest.raises(CatalogoInvalido, match="fallback"):
        Catalogo.carregar(_gravar(tmp_path, dados))


def test_ficha_com_campo_vazio_e_recusada(tmp_path, catalogo):
    dados = json.loads(json.dumps(catalogo.dados))
    dados["CWE-327"]["heuristica_go"] = ""
    with pytest.raises(CatalogoInvalido, match="heuristica_go"):
        Catalogo.carregar(_gravar(tmp_path, dados))


def test_exemplo_sem_porque_e_recusado(tmp_path, catalogo):
    dados = json.loads(json.dumps(catalogo.dados))
    dados["CWE-79"]["exemplo_fp"]["porque"] = ""
    with pytest.raises(CatalogoInvalido, match="porque"):
        Catalogo.carregar(_gravar(tmp_path, dados))


def test_json_invalido_e_recusado(tmp_path):
    p = tmp_path / "cat.json"
    p.write_text("{ nao é json", encoding="utf-8")
    with pytest.raises(CatalogoInvalido, match="JSON inválido"):
        Catalogo.carregar(str(p))


def test_arquivo_ausente_e_recusado(tmp_path):
    with pytest.raises(CatalogoInvalido, match="não encontrado"):
        Catalogo.carregar(str(tmp_path / "inexistente.json"))

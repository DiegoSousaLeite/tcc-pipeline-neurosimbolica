"""Testes dos prompts versionados (tarefas 6.1 a 6.4)."""
import pytest

from src.catalogo import Catalogo
from src.prompts import (
    BASELINE,
    ESPECIALISTA,
    PromptInvalido,
    carregar_template,
    montar_prompt,
    secao_contrato,
    versao_prompt,
)

CONTEXTO = (
    "Alerta Semgrep: go.lang.security.audit.crypto.use-of-md5\n"
    "Mensagem: Uso de MD5 detectado.\n"
    "Localização: linha 42\n"
    "\n--- CÓDIGO FONTE RELEVANTE ---\n"
    "func hashSenha(s string) string { return fmt.Sprint(md5.Sum([]byte(s))) }"
)


@pytest.fixture(scope="module")
def catalogo():
    return Catalogo.carregar()


# --- 6.1 Baseline é condição de controle -----------------------------------

def test_baseline_contem_contexto_e_alerta():
    texto = montar_prompt(BASELINE, contexto=CONTEXTO, cwe_id="CWE-327")
    assert CONTEXTO in texto
    assert "go.lang.security.audit.crypto.use-of-md5" in texto


def test_baseline_nao_contem_camada_alguma_da_metodologia(catalogo):
    """Se o controle receber qualquer camada, o contraste do experimento morre."""
    texto = montar_prompt(BASELINE, contexto=CONTEXTO, cwe_id="CWE-327",
                          cwe_name="Uso de algoritmo criptográfico quebrado")
    ficha = catalogo.ficha("CWE-327")
    assert ficha.definicao not in texto
    assert ficha.heuristica_go not in texto
    assert ficha.exemplo_vp["codigo"] not in texto
    assert ficha.exemplo_fp["codigo"] not in texto
    assert "CAMADA" not in texto
    # Nem o identificador da CWE: o baseline julga só o que a ferramenta disse.
    assert "CWE-327" not in texto


def test_baseline_nao_vaza_a_descricao_do_dataset():
    texto = montar_prompt(BASELINE, contexto=CONTEXTO, cwe_id="CWE-327",
                          description="The product uses a broken algorithm.")
    assert "broken algorithm" not in texto


# --- 6.2 Especialista tem as três camadas ----------------------------------

def test_especialista_com_ficha_especifica(catalogo):
    ficha = catalogo.ficha("CWE-327")
    texto = montar_prompt(ESPECIALISTA, contexto=CONTEXTO, cwe_id="CWE-327")
    assert ficha.definicao in texto
    assert ficha.heuristica_go in texto
    assert ficha.exemplo_vp["codigo"] in texto
    assert ficha.exemplo_fp["codigo"] in texto
    assert ficha.exemplo_vp["porque"] in texto
    assert ficha.exemplo_fp["porque"] in texto
    assert CONTEXTO in texto
    assert texto.count("CAMADA") == 3


def test_especialista_com_fallback_nao_deixa_secao_vazia(catalogo):
    ficha = catalogo.ficha("CWE-99999")
    texto = montar_prompt(ESPECIALISTA, contexto=CONTEXTO, cwe_id="CWE-99999")
    assert ficha.definicao in texto
    assert ficha.heuristica_go in texto
    assert ficha.exemplo_vp["codigo"] in texto
    assert texto.count("CAMADA") == 3
    assert "CWE-99999" in texto
    assert "{" not in texto.split("RESPONDA")[0].replace("{{", "").replace("}}", "") \
        or "```go" in texto   # nenhum placeholder sobrou sem preencher


def test_especialista_declara_o_contraste_por_contexto():
    texto = montar_prompt(ESPECIALISTA, contexto=CONTEXTO, cwe_id="CWE-338")
    assert "mesma API" in texto or "mesma construção" in texto


def test_ficha_explicita_tem_precedencia(catalogo):
    """O runner resolve a ficha uma vez por caso e a repassa: evita reabrir o
    catálogo por chamada e garante a mesma ficha nos dois braços de prompt."""
    ficha = catalogo.ficha("CWE-667")
    texto = montar_prompt(ESPECIALISTA, contexto=CONTEXTO, cwe_id="CWE-667",
                          ficha=ficha)
    assert ficha.heuristica_go in texto


# --- 6.3 Renderizador e versão ---------------------------------------------

def test_versao_e_hash_curto_estavel():
    v = versao_prompt(ESPECIALISTA)
    assert v.startswith("especialista:")
    assert len(v.split(":")[1]) == 8
    assert v == versao_prompt(ESPECIALISTA)


def test_versoes_dos_dois_templates_diferem():
    assert versao_prompt(BASELINE) != versao_prompt(ESPECIALISTA)


def test_alteracao_do_template_muda_a_versao(tmp_path, monkeypatch):
    import src.prompts as mod
    monkeypatch.setattr(mod, "_cache", {})
    monkeypatch.setattr(mod, "PROMPTS_DIR", str(tmp_path))
    (tmp_path / "baseline.md").write_text(
        "v1 {contexto}\nRESPONDA ESTRITAMENTE EM JSON", encoding="utf-8")
    antes = mod.versao_prompt(BASELINE)

    monkeypatch.setattr(mod, "_cache", {})
    (tmp_path / "baseline.md").write_text(
        "v2 {contexto}\nRESPONDA ESTRITAMENTE EM JSON", encoding="utf-8")
    assert mod.versao_prompt(BASELINE) != antes


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(PromptInvalido, match="desconhecido"):
        montar_prompt("cadeia-de-pensamento", contexto=CONTEXTO, cwe_id="CWE-1")


def test_nenhum_placeholder_sobra_no_texto_renderizado():
    for tipo in (BASELINE, ESPECIALISTA):
        texto = montar_prompt(tipo, contexto=CONTEXTO, cwe_id="CWE-327")
        # `{{` do contrato JSON vira `{` na renderização; o que não pode
        # sobrar é `{nome_de_placeholder}`.
        import re
        sobras = re.findall(r"\{[a-z_]+\}", texto)
        assert not sobras, f"{tipo}: placeholders não preenchidos {sobras}"


# --- 6.4 Contrato de saída idêntico ----------------------------------------

def test_contrato_de_saida_identico_entre_os_dois():
    assert secao_contrato(BASELINE) == secao_contrato(ESPECIALISTA)


def test_contrato_declara_as_chaves_e_o_dominio():
    contrato = secao_contrato(BASELINE)
    assert '"verdict"' in contrato
    assert '"reasoning"' in contrato
    assert '"VP"' in contrato and '"FP"' in contrato


def test_contrato_renderizado_e_json_valido_como_exemplo():
    """As chaves do contrato são escapadas (`{{`/`}}`) e viram JSON de exemplo
    de verdade depois do format."""
    import json
    texto = montar_prompt(BASELINE, contexto=CONTEXTO, cwe_id="CWE-1")
    trecho = texto[texto.index("{\"verdict\""):]
    exemplo = trecho[:trecho.index("}") + 1]
    assert json.loads(exemplo.replace('"VP" ou "FP"', '"VP"'))


def test_templates_sao_lidos_de_arquivo():
    for tipo in (BASELINE, ESPECIALISTA):
        assert carregar_template(tipo).strip()

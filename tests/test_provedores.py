"""Testes da camada de provedores de LLM (tarefas 4.1 a 4.6).

Nenhum teste toca a rede: as respostas HTTP são dubladas. O que se verifica é o
contrato — chave fora da URL, backoff, validação de schema e custo — porque é
disso que depende a comparabilidade dos braços da matriz.
"""
import json

import pytest
import requests

from src.provedores import (
    ERROR,
    FP,
    VP,
    ProvedorGemini,
    ProvedorOpenAI,
    RespostaLLM,
    criar_provedor,
    familia_do_modelo,
)
from src.provedores.base import (
    BACKOFF_TETO_S,
    espera_backoff,
    ler_retry_after,
    validar_resposta,
)
from src.provedores.precos import TABELA, custo_usd, tabela_para_manifesto


class RespostaFalsa:
    """Dublê de `requests.Response` com o mínimo que o provedor consome."""

    def __init__(self, status_code=200, dados=None, headers=None, texto=""):
        self.status_code = status_code
        self._dados = dados
        self.headers = headers or {}
        self.text = texto or json.dumps(dados or {})

    def json(self):
        if self._dados is None:
            raise ValueError("sem corpo JSON")
        return self._dados


class SessaoFalsa:
    """Devolve respostas em sequência e registra as requisições feitas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.chamadas.append({"url": url, "headers": headers or {},
                              "payload": json, "timeout": timeout})
        if not self.respostas:
            raise AssertionError("provedor fez mais chamadas do que o previsto")
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def resposta_gemini(texto, t_in=1200, t_out=80):
    return RespostaFalsa(dados={
        "candidates": [{"content": {"parts": [{"text": texto}]}}],
        "usageMetadata": {"promptTokenCount": t_in, "candidatesTokenCount": t_out},
    })


def resposta_openai(texto, t_in=1200, t_out=80):
    return RespostaFalsa(dados={
        "choices": [{"message": {"content": texto}}],
        "usage": {"prompt_tokens": t_in, "completion_tokens": t_out},
    })


JSON_VP = '{"verdict": "VP", "reasoning": "md5.Sum sobre credencial."}'
JSON_FP = '{"verdict": "FP", "reasoning": "Hash usado como chave de cache."}'


@pytest.fixture
def sem_dormir():
    """Relógio e sleep dublados: o teste não pode esperar de verdade."""
    estado = {"agora": 0.0, "esperas": []}

    def dormir(s):
        estado["esperas"].append(s)
        estado["agora"] += s

    def relogio():
        return estado["agora"]

    return estado, dormir, relogio


# --- 4.1/4.2 Contrato e autenticação ---------------------------------------

def test_familia_do_modelo():
    assert familia_do_modelo("gemini-2.5-flash-lite") == "gemini"
    assert familia_do_modelo("gpt-4o-mini") == "openai"
    with pytest.raises(ValueError):
        familia_do_modelo("llama-3")


def test_criar_provedor_escolhe_a_implementacao():
    assert isinstance(criar_provedor("gemini-2.5-flash-lite", api_key="k"),
                      ProvedorGemini)
    assert isinstance(criar_provedor("gpt-4o-mini", api_key="k"), ProvedorOpenAI)


def test_chave_gemini_vai_no_header_e_nao_na_url(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_gemini(JSON_VP))
    p = ProvedorGemini(api_key="SEGREDO-123", sessao=sessao,
                       intervalo_minimo_s=0)
    p.avaliar("prompt", dormir=dormir, relogio=relogio)

    chamada = sessao.chamadas[0]
    assert "SEGREDO-123" not in chamada["url"]
    assert "key=" not in chamada["url"]
    assert "?" not in chamada["url"]
    assert chamada["headers"]["x-goog-api-key"] == "SEGREDO-123"


def test_chave_openai_vai_como_bearer(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_openai(JSON_FP))
    p = ProvedorOpenAI(api_key="sk-SEGREDO", sessao=sessao)
    p.avaliar("prompt", dormir=dormir, relogio=relogio)

    chamada = sessao.chamadas[0]
    assert "sk-SEGREDO" not in chamada["url"]
    assert chamada["headers"]["Authorization"] == "Bearer sk-SEGREDO"


def test_resposta_normalizada_igual_entre_provedores(sem_dormir):
    _, dormir, relogio = sem_dormir
    g = ProvedorGemini(api_key="k", sessao=SessaoFalsa(resposta_gemini(JSON_VP)),
                       intervalo_minimo_s=0).avaliar("p", dormir=dormir, relogio=relogio)
    o = ProvedorOpenAI(api_key="k", sessao=SessaoFalsa(resposta_openai(JSON_VP))
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    for r in (g, o):
        assert isinstance(r, RespostaLLM)
        assert r.veredito == VP
        assert r.justificativa
        assert r.tokens_entrada == 1200 and r.tokens_saida == 80
        assert r.custo_usd > 0
        assert r.ok


def test_chave_ausente_vira_erro_sem_chamar_a_rede():
    sessao = SessaoFalsa()   # qualquer POST estouraria
    r = ProvedorGemini(api_key="", sessao=sessao).avaliar("p")
    assert r.veredito == ERROR
    assert not sessao.chamadas


# --- 4.4 Backoff ------------------------------------------------------------

def test_retry_after_e_respeitado(sem_dormir):
    estado, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(
        RespostaFalsa(429, headers={"Retry-After": "30"}, texto="cota"),
        resposta_gemini(JSON_FP),
    )
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == FP
    assert estado["esperas"] == [30.0]


def test_backoff_cresce_com_jitter_e_respeita_o_teto():
    fixo = [0.5, 1.5]
    for tentativa in range(1, 8):
        baixo = espera_backoff(tentativa, aleatorio=lambda a, b: fixo[0])
        alto = espera_backoff(tentativa, aleatorio=lambda a, b: fixo[1])
        assert baixo <= alto <= BACKOFF_TETO_S

    # Cresce enquanto não bate o teto.
    meio = [espera_backoff(t, aleatorio=lambda a, b: 1.0) for t in range(1, 5)]
    assert meio == sorted(meio) and meio[0] < meio[-1]
    assert espera_backoff(20, aleatorio=lambda a, b: 1.5) == BACKOFF_TETO_S


def test_retry_after_absurdo_fica_no_teto():
    assert espera_backoff(1, retry_after=99999) == BACKOFF_TETO_S


def test_ler_retry_after():
    assert ler_retry_after({"Retry-After": "12"}) == 12.0
    assert ler_retry_after({"retry-after": "0"}) == 0.0
    assert ler_retry_after({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}) is None
    assert ler_retry_after({}) is None
    assert ler_retry_after(None) is None


def test_tres_falhas_transitorias_produzem_tres_esperas_crescentes(sem_dormir):
    estado, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(
        RespostaFalsa(503, texto="indisponível"),
        RespostaFalsa(503, texto="indisponível"),
        RespostaFalsa(500, texto="erro"),
        resposta_gemini(JSON_VP),
    )
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == VP
    assert r.tentativas == 4
    assert len(estado["esperas"]) == 3
    assert all(e <= BACKOFF_TETO_S for e in estado["esperas"])


def test_esgotamento_vira_erro(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(*[RespostaFalsa(429, texto="cota") for _ in range(4)])
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert "esgotadas" in r.justificativa


def test_falha_de_rede_e_retentada(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(requests.ConnectionError("sem rota"),
                         resposta_gemini(JSON_FP))
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == FP


def test_erro_permanente_nao_e_retentado(sem_dormir):
    """401 é configuração errada: repetir só gasta tempo de rodada."""
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(RespostaFalsa(401, texto="chave inválida"))
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert len(sessao.chamadas) == 1


def test_intervalo_minimo_entre_chamadas(sem_dormir):
    estado, dormir, relogio = sem_dormir
    p = ProvedorGemini(api_key="k", intervalo_minimo_s=7,
                       sessao=SessaoFalsa(resposta_gemini(JSON_VP),
                                          resposta_gemini(JSON_FP)))
    p.avaliar("p1", dormir=dormir, relogio=relogio)
    estado["agora"] += 2.0          # 2 s de trabalho entre as chamadas
    p.avaliar("p2", dormir=dormir, relogio=relogio)
    assert estado["esperas"] == [pytest.approx(5.0)]


# --- 4.5 Validação de schema ------------------------------------------------

def test_veredito_valido():
    r = validar_resposta(JSON_VP, "m")
    assert r.veredito == VP and r.justificativa


def test_veredito_fora_do_dominio_vira_erro_nao_fp():
    for bruto in ('{"verdict": "TALVEZ", "reasoning": "x"}',
                  '{"verdict": "true_positive", "reasoning": "x"}',
                  '{"verdict": 1, "reasoning": "x"}',
                  '{"reasoning": "esqueci o veredito"}'):
        r = validar_resposta(bruto, "m")
        assert r.veredito == ERROR, bruto
        assert r.veredito != FP


def test_texto_livre_vira_erro():
    r = validar_resposta("Acho que é um verdadeiro positivo.", "m")
    assert r.veredito == ERROR
    assert "não é JSON" in r.justificativa


def test_json_quebrado_vira_erro():
    r = validar_resposta('{"verdict": "VP", "reasoning": ', "m")
    assert r.veredito == ERROR


def test_justificativa_vazia_vira_erro():
    r = validar_resposta('{"verdict": "FP", "reasoning": "   "}', "m")
    assert r.veredito == ERROR


def test_resposta_bruta_e_preservada_truncada():
    bruto = '{"verdict": "MAYBE", "reasoning": "' + "x" * 900 + '"}'
    r = validar_resposta(bruto, "m")
    assert r.veredito == ERROR
    assert "resposta bruta:" in r.justificativa
    assert len(r.justificativa) < 600


def test_cerca_de_markdown_e_tolerada():
    """Conteúdo certo dentro de cerca de código continua sendo conteúdo certo;
    o que não se tolera é veredito fora do domínio."""
    r = validar_resposta("```json\n" + JSON_FP + "\n```", "m")
    assert r.veredito == FP


def test_chaves_em_portugues_sao_aceitas():
    r = validar_resposta('{"veredito": "VP", "justificativa": "sink alcançável"}', "m")
    assert r.veredito == VP


def test_corpo_nao_json_do_provedor_vira_erro(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(RespostaFalsa(200, dados=None, texto="<html>502</html>"))
    r = ProvedorGemini(api_key="k", sessao=sessao, intervalo_minimo_s=0
                       ).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert "formato inesperado" in r.justificativa


# --- 4.6 Preços e custo -----------------------------------------------------

def test_custo_por_1m_de_tokens():
    # gemini-2.5-flash-lite: 0.10 entrada / 0.40 saída por 1M.
    assert custo_usd("gemini-2.5-flash-lite", 1_000_000, 0) == pytest.approx(0.10)
    assert custo_usd("gemini-2.5-flash-lite", 0, 1_000_000) == pytest.approx(0.40)
    assert custo_usd("gemini-2.5-flash-lite", 500_000, 250_000) == pytest.approx(0.15)


def test_custo_de_uma_chamada_tipica():
    # 1200 tokens de entrada + 80 de saída no gpt-4o-mini (0.15 / 0.60).
    esperado = 1200 / 1e6 * 0.15 + 80 / 1e6 * 0.60
    assert custo_usd("gpt-4o-mini", 1200, 80) == pytest.approx(esperado)


def test_modelo_fora_da_tabela_custa_zero_sem_chutar():
    assert custo_usd("gemini-9.9-ultra", 1_000_000, 1_000_000) == 0.0


def test_tabela_para_manifesto_registra_data_e_faltantes():
    m = tabela_para_manifesto(["gemini-2.5-flash-lite", "modelo-fantasma"])
    assert m["data_consulta"]
    assert m["versao_tabela"]
    assert "gemini-2.5-flash-lite" in m["precos"]
    assert m["modelos_sem_preco"] == ["modelo-fantasma"]


def test_todos_os_modelos_da_matriz_estao_tabelados():
    from src.provedores import MODELO_GEMINI_PADRAO, MODELO_OPENAI_PADRAO
    assert MODELO_GEMINI_PADRAO in TABELA
    assert MODELO_OPENAI_PADRAO in TABELA

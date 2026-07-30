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
    MODELO_OLLAMA_PADRAO,
    VP,
    ProvedorGemini,
    ProvedorOllama,
    ProvedorOpenAI,
    RespostaLLM,
    criar_provedor,
    familia_do_modelo,
)
from src.provedores.base import (
    BACKOFF_TETO_S,
    TIMEOUT_PADRAO_S,
    espera_backoff,
    ler_retry_after,
    validar_resposta,
)
from src.provedores.ollama import OllamaIndisponivel
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


# ===========================================================================
# Provedor local (Ollama)
# ===========================================================================

# Resposta gravada do servidor real (Ollama 0.32.5, qwen2.5-coder:7b Q4_K_M).
RESPOSTA_REAL_OLLAMA = {
    "model": "qwen2.5-coder:7b",
    "created_at": "2026-07-30T15:57:45.44989Z",
    "message": {
        "role": "assistant",
        "content": '{"verdict": "FP", "reasoning": "O alerta foi classificado '
                   'como Falso Positivo (FP) porque o hash MD5 fornecido não '
                   'corresponde a nenhum malware conhecido."}',
    },
    "done": True,
    "done_reason": "stop",
    "total_duration": 6920864700,
    "load_duration": 5835330900,
    "prompt_eval_count": 64,
    "prompt_eval_duration": 110798000,
    "eval_count": 47,
    "eval_duration": 972301000,
}


def resposta_ollama(texto, t_in=1200, t_out=80, done_reason="stop"):
    return RespostaFalsa(dados={
        "model": "qwen2.5-coder:7b",
        "message": {"role": "assistant", "content": texto},
        "done": True,
        "done_reason": done_reason,
        "prompt_eval_count": t_in,
        "eval_count": t_out,
    })


def resposta_ollama_abortada(texto):
    """Geração abortada no meio, como o servidor real a devolve.

    Gravada de um caso reproduzido da rodada completa (modelo em laço
    degenerado): `done: false`, sem `done_reason` e sem contagem de tokens.
    """
    return RespostaFalsa(dados={
        "model": "qwen2.5-coder:7b",
        "created_at": "2026-07-30T21:11:03.1Z",
        "message": {"role": "assistant", "content": texto},
        "done": False,
    })


class SessaoOllamaFalsa:
    """Dublê do servidor local: responde por caminho e registra as chamadas.

    Só o necessário para a sondagem e para o laço de chamada; nenhum teste toca
    a rede, como no resto do arquivo.
    """

    def __init__(self, versao="0.32.5", instalados=("qwen2.5-coder:7b",),
                 detalhes=None, model_info=None, ps=None, erro_get=None):
        self.versao = versao
        self.instalados = [{"name": n, "digest": f"digest-de-{n}",
                            "size": 4683087561} for n in instalados]
        self.detalhes = detalhes if detalhes is not None else {
            "parameter_size": "7.6B", "quantization_level": "Q4_K_M"}
        self.model_info = model_info if model_info is not None else {
            "qwen2.context_length": 32768}
        self.ps = ps
        self.erro_get = erro_get
        self.chamadas = []

    def get(self, url, timeout=None):
        self.chamadas.append({"metodo": "GET", "url": url})
        if self.erro_get:
            raise self.erro_get
        if url.endswith("/api/version"):
            return RespostaFalsa(dados={"version": self.versao})
        if url.endswith("/api/tags"):
            return RespostaFalsa(dados={"models": self.instalados})
        if url.endswith("/api/ps"):
            return RespostaFalsa(dados={"models": self.ps or []})
        raise AssertionError(f"GET inesperado: {url}")

    def post(self, url, headers=None, json=None, timeout=None):
        self.chamadas.append({"metodo": "POST", "url": url, "payload": json})
        if url.endswith("/api/show"):
            return RespostaFalsa(dados={"details": self.detalhes,
                                        "model_info": self.model_info})
        if url.endswith("/api/generate"):
            return RespostaFalsa(dados={"done": True})
        raise AssertionError(f"POST inesperado: {url}")


# --- 2.1/2.2 Credencial e timeout por provedor ------------------------------

def test_provedor_sem_exigencia_de_chave_chega_a_fazer_o_post(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama(JSON_FP))
    p = ProvedorOllama(sessao=sessao)
    assert p.exige_chave is False
    r = p.avaliar("prompt", dormir=dormir, relogio=relogio)
    assert r.veredito == FP
    assert len(sessao.chamadas) == 1


def test_provedores_comerciais_sem_chave_continuam_bloqueados():
    for classe in (ProvedorGemini, ProvedorOpenAI):
        sessao = SessaoFalsa()          # qualquer POST estouraria
        r = classe(api_key="", sessao=sessao).avaliar("p")
        assert r.veredito == ERROR
        assert "Chave de API ausente" in r.justificativa
        assert not sessao.chamadas


def test_timeout_padrao_e_por_provedor():
    assert ProvedorGemini(api_key="k").timeout_s == TIMEOUT_PADRAO_S == 60
    # Inferência local inclui carregar os pesos na VRAM: 60 s viraria uma fila
    # de erros de rede indistinguíveis de falha real.
    assert ProvedorOllama().timeout_s == 600


def test_timeout_explicito_do_chamador_nao_e_sobrescrito():
    assert ProvedorOllama(timeout_s=5).timeout_s == 5
    assert ProvedorGemini(api_key="k", timeout_s=5).timeout_s == 5


# --- 3.1/3.2 URL, headers e tag --------------------------------------------

def test_url_e_headers_do_provedor_local():
    p = ProvedorOllama(base_url="http://localhost:11434")
    assert p._url() == "http://localhost:11434/api/chat"
    assert p._headers() == {"Content-Type": "application/json"}
    assert p.nome == "ollama"
    assert p.intervalo_minimo_s == 0      # não há cota local a respeitar


def test_tag_separa_no_primeiro_dois_pontos():
    assert ProvedorOllama(modelo="ollama:gemma2").tag == "gemma2"
    assert ProvedorOllama(modelo="ollama:qwen2.5-coder:7b").tag == "qwen2.5-coder:7b"
    assert (ProvedorOllama(modelo="ollama:hf.co/org/modelo:Q4_K_M").tag
            == "hf.co/org/modelo:Q4_K_M")


# --- 3.3 Payload ------------------------------------------------------------

def test_payload_do_provedor_local(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama(JSON_VP))
    ProvedorOllama(modelo="ollama:qwen2.5-coder:7b", sessao=sessao
                   ).avaliar("PROMPT", dormir=dormir, relogio=relogio)

    payload = sessao.chamadas[0]["payload"]
    assert payload["model"] == "qwen2.5-coder:7b"
    assert payload["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert payload["stream"] is False
    # `format: "json"` e NÃO um schema com o enum: impor o domínio só ao braço
    # local eliminaria dele uma modalidade de falha que os comerciais correm.
    assert payload["format"] == "json"
    assert payload["keep_alive"] == "30m"
    assert payload["options"] == {"temperature": 0.0, "seed": 42,
                                  "num_ctx": 8192, "num_predict": 512}


def test_formato_nao_restringe_o_dominio_do_veredito(sem_dormir):
    """A validação do enum {VP, FP} continua sendo de `validar_resposta`."""
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama('{"verdict": "TALVEZ", "reasoning": "x"}'))
    r = ProvedorOllama(sessao=sessao).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR


# --- 3.4 Extração -----------------------------------------------------------

def test_extrair_de_resposta_real_do_servidor(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(RespostaFalsa(dados=RESPOSTA_REAL_OLLAMA))
    r = ProvedorOllama(sessao=sessao).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == FP
    assert "Falso Positivo" in r.justificativa
    assert r.tokens_entrada == 64
    assert r.tokens_saida == 47
    # Execução local: tokens contados, custo zero.
    assert r.custo_usd == 0.0


# --- 3.5 Truncamento detectado depois da chamada ---------------------------

def test_prompt_truncado_vira_erro_mesmo_com_json_valido(sem_dormir):
    """O pior modo de falha: o JSON veio bem-formado, mas sobre código visto
    pela metade. No CSV seria indistinguível de um veredito legítimo."""
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama(JSON_VP, t_in=512))
    p = ProvedorOllama(num_ctx=1024, num_predict=512, sessao=sessao)
    r = p.avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert "truncado" in r.justificativa
    assert r.tokens_entrada == 512


def test_saida_cortada_por_num_predict_vira_erro(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama('{"verdict": "VP", "reasoning": "come',
                                         t_in=100, done_reason="length"))
    p = ProvedorOllama(num_ctx=8192, sessao=sessao)
    r = p.avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert "num_predict" in r.justificativa


def test_geracao_abortada_pelo_servidor_vira_erro(sem_dormir):
    """`done: false` sem `done_reason` é como o Ollama 0.32.5 relata um aborto.

    O JSON cortado já viraria ERROR pela validação de schema, mas com o motivo
    errado ("não é JSON parseável"). Pior: se o corte caísse logo depois de uma
    chave de fechamento, o veredito de uma geração inacabada seria aceito.
    """
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama_abortada(
        '{"verdict": "FP", "reasoning": "o codigo nao \\n  \\n  \\n  '))
    r = ProvedorOllama(sessao=sessao).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR
    assert "interrompida antes de concluir" in r.justificativa


def test_json_valido_de_geracao_abortada_nao_vira_veredito(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama_abortada(JSON_VP))
    r = ProvedorOllama(sessao=sessao).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == ERROR


def test_prompt_folgado_nao_vira_erro_de_contexto(sem_dormir):
    _, dormir, relogio = sem_dormir
    sessao = SessaoFalsa(resposta_ollama(JSON_FP, t_in=2000))
    r = ProvedorOllama(sessao=sessao).avaliar("p", dormir=dormir, relogio=relogio)
    assert r.veredito == FP


# --- 3.6 Recusa antes da chamada -------------------------------------------

def test_prompt_grande_demais_nao_gasta_gpu():
    sessao = SessaoFalsa()              # qualquer POST estouraria
    p = ProvedorOllama(num_ctx=1024, num_predict=512, sessao=sessao)
    r = p.avaliar("x" * 4000)          # ~1142 tokens estimados > teto de 512
    assert r.veredito == ERROR
    assert "janela de contexto" in r.justificativa
    assert not sessao.chamadas


def test_estimativa_de_tokens_superestima_para_codigo():
    p = ProvedorOllama()
    assert p.tokens_estimados("x" * 350) == 100
    assert p.teto_do_prompt == 8192 - 512


# --- 3.7 Indisponibilidade x lentidão --------------------------------------

def test_conexao_recusada_e_tempo_limite_tem_motivos_distintos(sem_dormir):
    _, dormir, relogio = sem_dormir

    recusada = ProvedorOllama(
        sessao=SessaoFalsa(requests.ConnectionError("recusada")),
        max_tentativas=1).avaliar("p", dormir=dormir, relogio=relogio)
    assert recusada.veredito == ERROR
    assert "conexão recusada" in recusada.justificativa
    assert "não está no ar" in recusada.justificativa

    lento = ProvedorOllama(
        sessao=SessaoFalsa(requests.Timeout("demorou")),
        max_tentativas=1).avaliar("p", dormir=dormir, relogio=relogio)
    assert lento.veredito == ERROR
    assert "tempo limite excedido" in lento.justificativa


# --- 3.8 Sondagem -----------------------------------------------------------

def test_sondagem_devolve_a_identidade_do_modelo():
    sessao = SessaoOllamaFalsa(
        ps=[{"name": "qwen2.5-coder:7b", "size": 100, "size_vram": 100}])
    info = ProvedorOllama(modelo=MODELO_OLLAMA_PADRAO, sessao=sessao).sondar()

    assert info["versao_ollama"] == "0.32.5"
    assert info["tag"] == "qwen2.5-coder:7b"
    assert info["digest"] == "digest-de-qwen2.5-coder:7b"
    assert info["quantizacao"] == "Q4_K_M"
    assert info["parametros"] == "7.6B"
    assert info["janela_maxima_declarada"] == 32768
    assert info["num_ctx"] == 8192
    assert info["semente"] == 42
    assert info["processador"] == "100% GPU"


def test_sondagem_registra_campo_ausente_em_vez_de_omitir():
    sessao = SessaoOllamaFalsa(detalhes={}, model_info={})
    info = ProvedorOllama(sessao=sessao).sondar()
    assert info["quantizacao"] is None
    assert info["janela_maxima_declarada"] is None
    # Ausente e visível: omitir daria a entender que ninguém perguntou.
    assert "quantizacao" in info and "processador" in info


def test_sondagem_com_servidor_fora_do_ar_e_acionavel():
    sessao = SessaoOllamaFalsa(erro_get=requests.ConnectionError("sem servidor"))
    with pytest.raises(OllamaIndisponivel) as exc:
        ProvedorOllama(base_url="http://localhost:11434", sessao=sessao).sondar()
    msg = str(exc.value)
    assert "http://localhost:11434" in msg
    assert "ollama serve" in msg


def test_sondagem_com_modelo_ausente_nomeia_os_instalados():
    sessao = SessaoOllamaFalsa(instalados=("gemma2:9b", "llama3:8b"))
    with pytest.raises(OllamaIndisponivel) as exc:
        ProvedorOllama(modelo="ollama:qwen2.5-coder:7b", sessao=sessao).sondar()
    msg = str(exc.value)
    assert "qwen2.5-coder:7b" in msg
    assert "gemma2:9b" in msg and "llama3:8b" in msg
    assert "ollama pull qwen2.5-coder:7b" in msg


def test_processador_reporta_offload_parcial():
    sessao = SessaoOllamaFalsa(
        ps=[{"name": "qwen2.5-coder:7b", "size": 1000, "size_vram": 600}])
    assert ProvedorOllama(sessao=sessao).sondar()["processador"] == "60% GPU/40% CPU"


# --- 4.1 Fábrica e resolução de família ------------------------------------

def test_familia_do_modelo_resolve_os_tres_provedores():
    assert familia_do_modelo("gemini-2.5-flash-lite") == "gemini"
    assert familia_do_modelo("gpt-4o-mini") == "openai"
    assert familia_do_modelo("ollama:qwen2.5-coder:7b") == "ollama"
    # O namespace vence o prefixo comercial: um modelo aberto servido em casa
    # não vira braço do Google por causa do nome.
    assert familia_do_modelo("ollama:gemma2:9b") == "ollama"
    with pytest.raises(ValueError):
        familia_do_modelo("qwen2.5-coder:7b")   # sem namespace, sem provedor


def test_criar_provedor_local():
    p = criar_provedor(MODELO_OLLAMA_PADRAO)
    assert isinstance(p, ProvedorOllama)
    assert p.modelo == MODELO_OLLAMA_PADRAO
    assert p.tag == "qwen2.5-coder:7b"


# --- 4.2 Custo zero declarado ----------------------------------------------

def test_manifesto_distingue_gratuito_de_nao_tabelado():
    m = tabela_para_manifesto(
        ["gemini-2.5-flash-lite", "gpt-9-fantasma", MODELO_OLLAMA_PADRAO],
        modelos_locais=[MODELO_OLLAMA_PADRAO])
    assert "gemini-2.5-flash-lite" in m["precos"]
    assert m["modelos_sem_preco"] == ["gpt-9-fantasma"]
    assert m["modelos_locais_sem_custo"] == [MODELO_OLLAMA_PADRAO]


def test_modelo_local_custa_zero():
    assert custo_usd(MODELO_OLLAMA_PADRAO, 1_000_000, 1_000_000) == 0.0

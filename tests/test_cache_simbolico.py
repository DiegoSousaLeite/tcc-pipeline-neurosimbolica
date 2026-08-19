"""Testes do cache do resultado simbólico (tarefas 3.1 a 3.4)."""
import json
import os

import pytest

import run_pipeline
from run_pipeline import Caso, resolver_simbolico
from src.cache_simbolico import CacheSimbolico
from src.fase1_semgrep import (
    ALERTA_OUTRA_CWE,
    MOTIVO_NA,
    SEM_ALERTA,
    VERSAO_PAREAMENTO,
    ResultadoFase1,
)

ALERTA = {
    "start": {"line": 42},
    "check_id": "go.lang.security.audit.crypto.use-of-md5",
    "extra": {"message": "Uso de MD5 detectado."},
}
CONTEXTO = (
    "Alerta Semgrep: go.lang.security.audit.crypto.use-of-md5\n"
    "Mensagem: Uso de MD5 detectado.\n"
    "Localização: linha 42\n"
    "\n--- CÓDIGO FONTE RELEVANTE ---\n"
    "\n[Arquivo: cripto.go | Linhas 40 a 45]\n"
    "func hash(s string) string {\n\treturn fmt.Sprint(md5.Sum([]byte(s)))\n}"
)
CHAVE = ("acme/servico", "a" * 40, "pkg/cripto/cripto.go", "CWE-327")


@pytest.fixture
def cache(tmp_path):
    return CacheSimbolico(diretorio=str(tmp_path / "cache_simbolico"),
                          versao_ruleset="p/default")


# --- 3.1 Ida e volta --------------------------------------------------------

def test_ida_e_volta(cache):
    assert cache.ler(*CHAVE) is None
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)

    payload = cache.ler(*CHAVE)
    assert payload["status_semgrep"] == "DETECTADO"
    assert payload["alerta"] == ALERTA
    assert payload["contexto_hidratado"] == CONTEXTO
    assert payload["versao_ruleset"] == "p/default"


def test_nao_detectado_tambem_e_cacheado(cache):
    """A maioria dos casos é NAO_DETECTADO e é justamente onde o Semgrep gasta
    tempo sem gerar chamada de LLM — não cachear isso perderia quase todo o
    ganho de tempo de parede."""
    cache.gravar(*CHAVE, "NAO_DETECTADO")
    payload = cache.ler(*CHAVE)
    assert payload is not None
    assert payload["status_semgrep"] == "NAO_DETECTADO"
    assert payload["alerta"] is None


def test_chaves_diferentes_nao_colidem(cache):
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)
    outra_cwe = (*CHAVE[:3], "CWE-338")
    outro_arquivo = (CHAVE[0], CHAVE[1], "pkg/outro/outro.go", CHAVE[3])
    outro_commit = (CHAVE[0], "b" * 40, *CHAVE[2:])
    assert cache.ler(*outra_cwe) is None
    assert cache.ler(*outro_arquivo) is None
    assert cache.ler(*outro_commit) is None


def test_caminho_curto_em_arquivo_profundo(cache):
    """Caminho Go aninhado vira hash: no Windows o limite de ~260 chars é real."""
    fundo = "a/" * 60 + "servico.go"
    destino = cache.caminho(CHAVE[0], CHAVE[1], fundo, CHAVE[3])
    assert len(os.path.basename(destino)) < 60
    assert destino.endswith("__CWE-327.json")


# --- 3.2 Invalidação por ruleset -------------------------------------------

def test_ruleset_divergente_invalida(tmp_path):
    dir_cache = str(tmp_path / "cache_simbolico")
    antigo = CacheSimbolico(diretorio=dir_cache, versao_ruleset="p/golang")
    antigo.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)

    atual = CacheSimbolico(diretorio=dir_cache, versao_ruleset="p/default")
    assert atual.ler(*CHAVE) is None, "entrada de outro ruleset não pode ser usada"

    # A entrada antiga não é apagada: continua sendo evidência do que aquele
    # ruleset produziu.
    assert os.path.exists(atual.caminho(*CHAVE))


def test_formato_divergente_invalida(cache):
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)
    destino = cache.caminho(*CHAVE)
    with open(destino, encoding="utf-8") as f:
        payload = json.load(f)
    payload["versao_formato"] = 999
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    assert cache.ler(*CHAVE) is None


# --- Invalidação por regra de pareamento -----------------------------------

def test_pareamento_divergente_invalida(tmp_path):
    """Uma entrada gravada sob a regra antiga pode guardar um alerta que a regra
    corrente recusaria; servi-la do disco reintroduziria em silêncio justamente
    o emparelhamento que a regra nova elimina."""
    dir_cache = str(tmp_path / "cache_simbolico")
    antigo = CacheSimbolico(diretorio=dir_cache,
                            versao_pareamento=VERSAO_PAREAMENTO - 1)
    antigo.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)

    atual = CacheSimbolico(diretorio=dir_cache)
    assert atual.ler(*CHAVE) is None
    # Não é apagada: continua sendo evidência do que a regra antiga produziu.
    assert os.path.exists(atual.caminho(*CHAVE))


def test_pareamento_divergente_invalida_ate_nao_detectado(tmp_path):
    """O status delas continuaria correto — endurecer o pareamento nunca
    transforma não-detecção em detecção —, mas elas não sabem informar qual dos
    dois motivos as produziu, e são a maioria da população."""
    dir_cache = str(tmp_path / "cache_simbolico")
    CacheSimbolico(diretorio=dir_cache,
                   versao_pareamento=VERSAO_PAREAMENTO - 1).gravar(
        *CHAVE, "NAO_DETECTADO")
    assert CacheSimbolico(diretorio=dir_cache).ler(*CHAVE) is None


def test_entrada_sem_versao_de_pareamento_e_tratada_como_anterior(cache):
    """É o estado de todas as entradas gravadas antes do campo existir: elas
    são recomputadas, e não aceitas por omissão."""
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)
    destino = cache.caminho(*CHAVE)
    with open(destino, encoding="utf-8") as f:
        payload = json.load(f)
    del payload["versao_pareamento"]
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    assert cache.ler(*CHAVE) is None
    assert os.path.exists(destino)


def test_motivo_e_regras_sobrevivem_ao_cache(cache):
    """O diagnóstico de cobertura tem que vir do cache junto com o status: sem
    ele, recuperá-lo exigiria reexecutar o Semgrep na população inteira."""
    regras = ["go.lang.security.audit.crypto.math-random-used",
              "go.lang.security.audit.dangerous-exec-command"]
    cache.gravar(*CHAVE, "NAO_DETECTADO", motivo=ALERTA_OUTRA_CWE,
                 regras_nao_casadas=regras)

    payload = cache.ler(*CHAVE)
    assert payload["motivo"] == ALERTA_OUTRA_CWE
    assert payload["regras_nao_casadas"] == regras
    assert payload["versao_pareamento"] == VERSAO_PAREAMENTO


def test_arquivo_corrompido_nao_derruba_a_rodada(cache):
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)
    with open(cache.caminho(*CHAVE), "w", encoding="utf-8") as f:
        f.write("{ isto não é json")
    assert cache.ler(*CHAVE) is None


def test_cache_de_fontes_nao_e_tocado(cache, tmp_path, monkeypatch):
    """Invariante do projeto: o cache de FONTES nunca invalida, logo o cache
    simbólico não pode criar, alterar nem remover nada sob `cache/`."""
    fontes = tmp_path / "cache"
    fontes.mkdir()
    alvo = fontes / "arquivo.go"
    alvo.write_text("package main\n", encoding="utf-8")
    antes = {p: p.stat().st_mtime_ns for p in fontes.rglob("*")}

    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)
    CacheSimbolico(diretorio=cache.diretorio, versao_ruleset="outro").ler(*CHAVE)

    depois = {p: p.stat().st_mtime_ns for p in fontes.rglob("*")}
    assert antes == depois


# --- Desativação ------------------------------------------------------------

def test_desativado_nao_le_nem_grava(tmp_path):
    dir_cache = str(tmp_path / "cache_simbolico")
    CacheSimbolico(diretorio=dir_cache).gravar(
        *CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=CONTEXTO)

    off = CacheSimbolico(diretorio=dir_cache, ativo=False)
    assert off.ler(*CHAVE) is None
    off.gravar(*CHAVE, "NAO_DETECTADO")
    # A gravação desativada não pode ter sobrescrito a entrada existente.
    assert CacheSimbolico(diretorio=dir_cache).ler(*CHAVE)["status_semgrep"] == "DETECTADO"


# --- 3.3 Integração com as Fases 1 e 2 -------------------------------------

@pytest.fixture
def caso():
    return Caso(id="TPD:x", origem="TP_dataset", repo_name=CHAVE[0],
                repo_dir="servico", repo_url="https://github.com/acme/servico",
                commit=CHAVE[1], arquivo=CHAVE[2], cwe=CHAVE[3],
                gabarito="vulneravel")


@pytest.fixture
def semgrep_contado(monkeypatch, tmp_path):
    """Substitui Fase 1 e Fase 2 por dublês que contam invocações."""
    chamadas = {"semgrep": 0, "hidratacao": 0}
    alvo = tmp_path / "cripto.go"
    alvo.write_text("package main\n", encoding="utf-8")

    def _obter(repo, commit, arquivo):
        return str(alvo)

    def _semgrep(caminho, cwe):
        chamadas["semgrep"] += 1
        return ResultadoFase1(ALERTA, MOTIVO_NA, [])

    def _hidratar(alerta, caminho):
        chamadas["hidratacao"] += 1
        return CONTEXTO

    monkeypatch.setattr(run_pipeline, "obter_arquivo", _obter)
    monkeypatch.setattr(run_pipeline, "executar_semgrep", _semgrep)
    monkeypatch.setattr(run_pipeline, "extrair_e_hidratar_contexto", _hidratar)
    return chamadas


def test_segunda_execucao_nao_invoca_semgrep(cache, caso, semgrep_contado):
    """O ganho de tempo de parede da matriz 2x2 depende disto: os braços 2 a 4
    não podem reexecutar o motor simbólico."""
    primeiro = resolver_simbolico(caso, cache)
    assert semgrep_contado["semgrep"] == 1

    for _ in range(3):   # os outros três braços
        assert resolver_simbolico(caso, cache) == primeiro
    assert semgrep_contado["semgrep"] == 1
    assert semgrep_contado["hidratacao"] == 1
    assert cache.leituras == 3


def _nao_detecta(contador, motivo=SEM_ALERTA, regras=()):
    """Dublê de Fase 1 que não emparelha nada e conta as invocações."""
    def _semgrep(caminho, cwe):
        contador["semgrep"] += 1
        return ResultadoFase1(None, motivo, list(regras))
    return _semgrep


def test_nao_detectado_tambem_pula_semgrep_na_segunda(cache, caso, monkeypatch,
                                                      semgrep_contado):
    monkeypatch.setattr(run_pipeline, "executar_semgrep",
                        _nao_detecta(semgrep_contado))
    assert resolver_simbolico(caso, cache)[0] == "NAO_DETECTADO"
    assert resolver_simbolico(caso, cache)[0] == "NAO_DETECTADO"
    assert semgrep_contado["semgrep"] == 1


def test_motivo_atravessa_a_pipeline_e_o_cache(cache, caso, monkeypatch,
                                               semgrep_contado):
    """Segunda rodada, servida do disco, tem que reportar o mesmo diagnóstico
    da primeira sem reexecutar o Semgrep."""
    regras = ["go.lang.security.audit.crypto.use-of-md5"]
    monkeypatch.setattr(run_pipeline, "executar_semgrep",
                        _nao_detecta(semgrep_contado, ALERTA_OUTRA_CWE, regras))

    primeiro = resolver_simbolico(caso, cache)
    assert primeiro.status == "NAO_DETECTADO"
    assert primeiro.motivo == ALERTA_OUTRA_CWE
    assert primeiro.regras_nao_casadas == regras

    do_cache = resolver_simbolico(caso, cache)
    assert do_cache == primeiro
    assert semgrep_contado["semgrep"] == 1


def test_caso_emparelhado_nao_tem_motivo(cache, caso, semgrep_contado):
    assert resolver_simbolico(caso, cache).motivo == MOTIVO_NA
    assert resolver_simbolico(caso, cache).regras_nao_casadas == []


def test_cache_desativado_reexecuta_sempre(caso, semgrep_contado, tmp_path):
    off = CacheSimbolico(diretorio=str(tmp_path / "cs"), ativo=False)
    resolver_simbolico(caso, off)
    resolver_simbolico(caso, off)
    assert semgrep_contado["semgrep"] == 2


def test_sem_cache_algum_reexecuta_sempre(caso, semgrep_contado):
    resolver_simbolico(caso, None)
    resolver_simbolico(caso, None)
    assert semgrep_contado["semgrep"] == 2


def test_hidratacao_falha_nao_vira_nao_detectado(cache, caso, monkeypatch,
                                                 semgrep_contado):
    """Arquivo ilegível é falha de esteira, não silêncio do Semgrep: confundir
    os dois contaminaria a matriz de cobertura com um FN falso."""
    monkeypatch.setattr(run_pipeline, "extrair_e_hidratar_contexto",
                        lambda a, c: "")
    assert resolver_simbolico(caso, cache).status == "HIDRATACAO_FALHOU"


# --- 3.4 Contexto byte-a-byte idêntico -------------------------------------

def test_contexto_identico_byte_a_byte(cache):
    """Validade interna da comparação pareada: os quatro braços têm que ver
    exatamente a mesma string de contexto."""
    contexto = CONTEXTO + "\n\tacentuação: função ção — travessão\r\nfim\t "
    cache.gravar(*CHAVE, "DETECTADO", alerta=ALERTA, contexto_hidratado=contexto)

    lidos = [cache.ler(*CHAVE)["contexto_hidratado"] for _ in range(4)]
    assert all(x == contexto for x in lidos)
    assert all(x.encode("utf-8") == contexto.encode("utf-8") for x in lidos)


def test_contexto_identico_entre_bracos_pela_pipeline(cache, caso, semgrep_contado):
    """Mesma garantia, mas atravessando `resolver_simbolico`: é a string que
    chega ao montador de prompt nos quatro braços."""
    contextos = [resolver_simbolico(caso, cache)[2] for _ in range(4)]
    assert len(set(contextos)) == 1
    assert contextos[0].encode("utf-8") == CONTEXTO.encode("utf-8")

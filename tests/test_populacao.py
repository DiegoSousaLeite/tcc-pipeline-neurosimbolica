"""Testes da composição da população quanto ao eixo vulnerável (tarefas 3.1-3.2).

A trilha `TP_alcancavel` lê o pool da colheita filtrada. Como esse pool pode não
existir ainda, os testes que precisam dele montam um pool sintético em disco —
inclusive um que repete deliberadamente pares dos pools antigos, para provar que
o espaço de identificadores das trilhas não se cruza.

Dois testes medem os pools e o dataset reais: são eles que sustentam as
contagens citadas no design (32 / 68 / 57) e falham se os dados mudarem sem a
documentação mudar junto.
"""
import csv
import glob
import json
import os

import pytest

import run_pipeline
from run_pipeline import (
    TP_PAIRS_OURO,
    TP_PAIRS_PRATA,
    TRILHAS,
    construir_casos_fp,
    construir_casos_tp,
    construir_casos_tp_dataset,
    contar_por_trilha,
)
from src.config import DATASET_PATH
from src.fase5_auditoria import classificar_cobertura_semgrep
from src.metricas import contar

RODADA_REFERENCIA = "results/20260731T140000Z-af9bc32"
PREFIXO_ALCANCAVEL = "TPA:"


@pytest.fixture(scope="module")
def dataset_real():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cwe_meta(dataset_real):
    return run_pipeline._cwe_lookup(dataset_real)


def _par(repo="acme/servico", cwe="CWE-327", funcao="Handler",
         arquivo="pkg/cripto.go"):
    return {"repo": repo, "cwe_id": cwe, "funcao": funcao, "arquivo": arquivo,
            "parent_commit": "a" * 40, "fix_commit": "b" * 40}


@pytest.fixture
def pool(tmp_path):
    """Grava um pool de pares em disco e devolve o caminho."""
    def _grava(pares, nome="pool.json"):
        destino = tmp_path / nome
        destino.write_text(json.dumps(pares), encoding="utf-8")
        return str(destino)
    return _grava


def montar_populacao(dataset, cwe_meta, pool_alcancavel):
    """Reproduz a montagem de `run_pipeline.main`, com o pool variável."""
    return (construir_casos_fp(dataset)
            + construir_casos_tp(TP_PAIRS_OURO, "TP_ouro", cwe_meta)
            + construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", cwe_meta)
            + construir_casos_tp(pool_alcancavel, "TP_alcancavel", cwe_meta,
                                 prefixo_id=PREFIXO_ALCANCAVEL)
            + construir_casos_tp_dataset(dataset))


# --- 3.1 Trilha nova na população ------------------------------------------

def test_trilha_nova_entra_com_rotulo_proprio(pool, cwe_meta):
    casos = construir_casos_tp(pool([_par()]), "TP_alcancavel", cwe_meta,
                               prefixo_id=PREFIXO_ALCANCAVEL)
    assert {c.origem for c in casos} == {"TP_alcancavel"}
    # Cada par vira duas amostras, como nas demais trilhas TP.
    assert {c.gabarito for c in casos} == {"vulneravel", "seguro"}


def test_trilha_nova_esta_na_ordem_canonica():
    """Sem isto a trilha não apareceria na contagem do cabeçalho nem no
    manifesto, e uma rodada poderia rodar sem os casos novos em silêncio."""
    assert TRILHAS == ("FP", "TP_ouro", "TP_prata", "TP_dataset", "TP_alcancavel")


def test_pool_ausente_nao_quebra_a_montagem(dataset_real, cwe_meta, tmp_path):
    inexistente = str(tmp_path / "nao_existe.json")
    assert not os.path.exists(inexistente)

    casos = montar_populacao(dataset_real, cwe_meta, inexistente)
    contagem = contar_por_trilha(casos)

    assert contagem["TP_alcancavel"] == 0
    assert len(casos) == 948   # a população das rodadas anteriores, intacta


def test_trilha_vazia_continua_listada_na_contagem(dataset_real, cwe_meta,
                                                   tmp_path):
    """Trilha com zero casos não pode sumir do relatório: é assim que se percebe
    que o pool não foi gerado antes de gastar uma rodada."""
    contagem = contar_por_trilha(
        montar_populacao(dataset_real, cwe_meta, str(tmp_path / "ausente.json")))
    assert list(contagem) == list(TRILHAS)


def test_trilha_nova_selecionavel_isoladamente(pool, cwe_meta, dataset_real):
    casos = montar_populacao(dataset_real, cwe_meta, pool([_par()]))
    so_ela = [c for c in casos if c.origem in {"TP_alcancavel"}]
    assert len(so_ela) == 2
    assert all(c.origem == "TP_alcancavel" for c in so_ela)


# --- 3.1 Integridade dos identificadores ------------------------------------

def test_nenhum_id_duplicado_na_populacao_inteira(dataset_real, cwe_meta, pool):
    casos = montar_populacao(dataset_real, cwe_meta, pool([_par()]))
    ids = [c.id for c in casos]
    assert len(ids) == len(set(ids))


def test_pool_novo_repetindo_par_antigo_nao_colide(dataset_real, cwe_meta, pool):
    """D4: os 17 pares já alcançáveis continuam contando como `TP_ouro` e
    `TP_prata`. Se a colheita reencontrar um deles, o prefixo próprio impede que
    o ID colidido faça dois casos distintos virarem o mesmo na tripla de
    checkpoint `(ID_Caso, Modelo_LLM, Tipo_Prompt)`.
    """
    antigos = (json.load(open(TP_PAIRS_OURO, encoding="utf-8"))[:4]
               + json.load(open(TP_PAIRS_PRATA, encoding="utf-8"))[:13])
    casos = montar_populacao(dataset_real, cwe_meta, pool(antigos))

    ids = [c.id for c in casos]
    assert len(ids) == len(set(ids))

    trilhas_por_id = {}
    for c in casos:
        trilhas_por_id.setdefault(c.id, set()).add(c.origem)
    assert not [i for i, t in trilhas_por_id.items() if len(t) > 1]


def test_ids_da_trilha_nova_tem_prefixo_proprio(pool, cwe_meta):
    casos = construir_casos_tp(pool([_par()]), "TP_alcancavel", cwe_meta,
                               prefixo_id=PREFIXO_ALCANCAVEL)
    assert all(c.id.startswith(PREFIXO_ALCANCAVEL) for c in casos)


def test_trilhas_antigas_nao_ganham_prefixo(cwe_meta):
    """Os IDs de `TP_ouro` e `TP_prata` estão gravados nos CSVs e no checkpoint
    das rodadas anteriores: prefixá-los invalidaria a retomada."""
    casos = construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", cwe_meta)
    assert casos
    assert not any(c.id.startswith(PREFIXO_ALCANCAVEL) for c in casos)


# --- 3.1 Classe negativa preservada -----------------------------------------

def test_classe_negativa_mantem_os_mesmos_ids(dataset_real, cwe_meta, pool):
    """O índice do ID vem da posição ORIGINAL na lista de locations: renumerar
    quebraria os CSVs já gravados e o checkpoint entre rodadas."""
    referencia = set()
    for arq in glob.glob(os.path.join(RODADA_REFERENCIA, "*.csv")):
        with open(arq, encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f):
                if (linha.get("Origem") or "").strip() == "FP":
                    referencia.add(linha["ID_Caso"])
    assert referencia, f"a rodada {RODADA_REFERENCIA} deve estar em disco"

    casos = montar_populacao(dataset_real, cwe_meta, pool([_par()]))
    fp_ids = {c.id for c in casos if c.origem == "FP"}

    assert fp_ids == referencia


def test_classe_negativa_nao_muda_de_tamanho(dataset_real):
    assert len(construir_casos_fp(dataset_real)) == 791


# --- 3.1 Trilhas existentes preservadas -------------------------------------

def test_trilhas_existentes_produzem_os_mesmos_casos(dataset_real, cwe_meta,
                                                     pool):
    contagem = contar_por_trilha(
        montar_populacao(dataset_real, cwe_meta, pool([_par()])))
    assert contagem["TP_ouro"] == 32
    assert contagem["TP_prata"] == 68
    assert contagem["TP_dataset"] == 57


# --- 3.2 Casos de CWE inalcançável preservados ------------------------------

# CWE de controle de acesso: nenhuma regra Go do `p/default` a declara. É uma
# das que compõem os 70,1% inalcançáveis do corpus.
CWE_INALCANCAVEL = "CWE-284"


def test_caso_de_cwe_inalcancavel_entra_na_populacao(pool, cwe_meta):
    """D3: eles ficam. São a evidência de que 70,1% das fraquezas do corpus
    estão fora do alcance da análise sintática — resultado, não ruído."""
    casos = construir_casos_tp(pool([_par(cwe=CWE_INALCANCAVEL)]),
                               "TP_prata", cwe_meta)
    vulneraveis = [c for c in casos if c.gabarito == "vulneravel"]
    assert len(vulneraveis) == 1
    assert vulneraveis[0].cwe == CWE_INALCANCAVEL


def test_caso_inalcancavel_e_ponto_cego_na_cobertura():
    """Sem regra que o alcance, o Semgrep não detecta: a cobertura registra FN."""
    assert (classificar_cobertura_semgrep("vulneravel", detectado=False)
            == "Semgrep FN (ponto cego simbólico)")


def test_caso_inalcancavel_fica_fora_da_matriz_de_acerto():
    """Sem emparelhamento na Fase 1 não há chamada de LLM, então o caso não
    contribui com nenhuma célula da matriz de acerto — as duas matrizes são
    separadas justamente para isso."""
    linhas = [
        {"Gabarito": "vulneravel",
         "Status_Semgrep": "NAO_DETECTADO",
         "Motivo_Nao_Deteccao": "sem regra para a CWE",
         "Classificacao_Semgrep": classificar_cobertura_semgrep(
             "vulneravel", detectado=False),
         "Classificacao_LLM": "N/A (Semgrep nao detectou)"},
        {"Gabarito": "seguro",
         "Status_Semgrep": "DETECTADO",
         "Motivo_Nao_Deteccao": "N/A",
         "Classificacao_Semgrep": classificar_cobertura_semgrep(
             "seguro", detectado=True),
         "Classificacao_LLM": "Falso Positivo (Ruído Mantido)"},
    ]

    cobertura = contar(linhas, matriz="semgrep")
    acerto = contar(linhas, matriz="llm")

    # O inalcançável está na cobertura, como ponto cego.
    assert cobertura["FN"] == 1
    assert cobertura["Total"] == 2
    # E fora da matriz de acerto: só a linha detectada chega lá.
    assert acerto["Total"] == 1
    assert acerto["FN"] == 0


def test_proporcao_de_inalcancaveis_permanece_calculavel(pool, cwe_meta):
    """A comparação com as rodadas anteriores depende de o denominador continuar
    incluindo os inalcançáveis."""
    pares = [_par(cwe=CWE_INALCANCAVEL, funcao="A"),
             _par(cwe="CWE-327", funcao="B")]
    casos = construir_casos_tp(pool(pares), "TP_prata", cwe_meta)
    vulneraveis = [c for c in casos if c.gabarito == "vulneravel"]
    inalcancaveis = [c for c in vulneraveis if c.cwe == CWE_INALCANCAVEL]

    assert len(vulneraveis) == 2
    assert len(inalcancaveis) == 1


# --- Unicidade do identificador DENTRO da trilha ----------------------------
#
# O `prefixo_id` separa o espaço de identificadores ENTRE trilhas. Estes testes
# cobrem a outra metade, que o esquema antigo não garantia: dois pares do MESMO
# pool, com mesmo repositório, CWE e nome de função, apontando arquivos
# diferentes. Em Go isso é o caso comum — o mesmo método em vários arquivos do
# pacote, todos alterados pelo mesmo fix.

def test_pares_em_arquivos_distintos_nao_colidem(pool, cwe_meta):
    pares = [_par(arquivo="plumbing/object/commit.go"),
             _par(arquivo="plumbing/object/tag.go"),
             _par(arquivo="plumbing/object/tree.go")]
    casos = construir_casos_tp(pool(pares), "TP_alcancavel", cwe_meta,
                               prefixo_id=PREFIXO_ALCANCAVEL)

    assert len(casos) == 6            # 3 pares x 2 versões
    ids = [c.id for c in casos]
    assert len(ids) == len(set(ids))


def test_identificador_nao_depende_dos_vizinhos_no_pool(pool, cwe_meta):
    """D1: acrescentar um par ao pool não pode mudar o identificador dos que já
    estavam lá — se dependesse da posição, uma colheita futura quebraria o
    checkpoint de uma rodada em andamento."""
    antes = construir_casos_tp(
        pool([_par(arquivo="a.go")], nome="antes.json"),
        "TP_alcancavel", cwe_meta, prefixo_id=PREFIXO_ALCANCAVEL)
    depois = construir_casos_tp(
        pool([_par(arquivo="a.go"), _par(arquivo="b.go")], nome="depois.json"),
        "TP_alcancavel", cwe_meta, prefixo_id=PREFIXO_ALCANCAVEL)

    ids_antes = {c.id for c in antes}
    assert ids_antes <= {c.id for c in depois}


def test_montagem_aborta_com_identificador_repetido():
    """D4: o modo de falha a evitar é o silencioso. O checkpoint por tripla
    trataria o segundo caso como já gravado e as métricas deduplicam pela
    primeira ocorrência — nada no CSV denunciaria a perda."""
    caso = run_pipeline.Caso(
        id="TPA:acme:CWE-327:Handler:vuln", origem="TP_alcancavel",
        repo_name="acme/servico", repo_dir="servico",
        repo_url="https://github.com/acme/servico", commit="a" * 40,
        arquivo="pkg/cripto.go", cwe="CWE-327", cwe_name="", description="",
        gabarito="vulneravel", num_locations=1)

    with pytest.raises(run_pipeline.IdentificadorDuplicadoError) as erro:
        run_pipeline.verificar_ids_unicos([caso, caso])

    assert "TPA:acme:CWE-327:Handler:vuln" in str(erro.value)
    assert "TP_alcancavel" in str(erro.value)


def test_populacao_sem_duplicados_passa_pela_guarda(dataset_real, cwe_meta,
                                                    pool):
    casos = montar_populacao(dataset_real, cwe_meta, pool([_par()]))
    assert run_pipeline.verificar_ids_unicos(casos) is None


def test_ids_das_trilhas_ja_executadas_sao_os_dos_csvs(cwe_meta):
    """Rede de proteção do D3: `TP_ouro` e `TP_prata` estão gravadas nos CSVs e
    no checkpoint das rodadas anteriores. O esquema novo não pode alcançá-las."""
    referencia = {}
    for arq in glob.glob(os.path.join(RODADA_REFERENCIA, "*.csv")):
        with open(arq, encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f):
                origem = (linha.get("Origem") or "").strip()
                if origem in {"TP_ouro", "TP_prata"}:
                    referencia.setdefault(origem, set()).add(linha["ID_Caso"])
    assert referencia, f"a rodada {RODADA_REFERENCIA} deve estar em disco"

    for pool_file, origem in ((TP_PAIRS_OURO, "TP_ouro"),
                              (TP_PAIRS_PRATA, "TP_prata")):
        casos = construir_casos_tp(pool_file, origem, cwe_meta)
        assert {c.id for c in casos} == referencia[origem]


def test_preenchimento_de_cache_cobre_a_trilha_nova(monkeypatch, pool,
                                                    cwe_meta):
    """A trilha nova ficou fora de `casos_unicos()` quando foi criada, e a Fase 1
    acabaria buscando da rede os arquivos dela — justamente o que o cache de
    fontes existe para evitar."""
    import scripts.preencher_cache as preencher

    alvo = "pkg/somente-da-trilha-nova.go"
    monkeypatch.setattr(preencher, "TP_PAIRS_ALCANCAVEL",
                        pool([_par(arquivo=alvo)]), raising=False)
    monkeypatch.setattr(preencher, "TP_PAIRS_OURO", "/nao/existe.json")
    monkeypatch.setattr(preencher, "TP_PAIRS_PRATA", "/nao/existe.json")

    assert alvo in {c["arquivo"] for c in preencher.casos_unicos()}

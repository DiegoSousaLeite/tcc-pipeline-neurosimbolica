"""
envio_lote.py — ciclo de vida de uma rodada em modo de envio `lote`.

Recebe as requisições que o modo síncrono faria — `(chave, prompt)` acumulados
pelo runner no lugar das chamadas — e cuida de parti-las, persistir, submeter,
acompanhar e recuperar. Não sabe nada de CSV: a gravação de cada veredito é um
callback do runner, o mesmo ponto de gravação do modo síncrono.

Três garantias moram aqui:

- **O registro vai para o disco antes da submissão (D3).** O identificador do
  lote só existe depois que o servidor responde, então o que se grava antes é o
  RÓTULO do cliente (`display_name` no Gemini), com a partição marcada
  `SUBMETENDO`. Uma queda entre a submissão e a gravação do identificador se
  resolve localizando o lote pelo rótulo; se ele não existir, a submissão nunca
  aconteceu e a execução submete. Gravar só depois deixaria uma janela em que o
  gasto existe e o registro não.
- **Retomar não ressubmete (D8).** Rodar o mesmo comando de novo lê
  `lote.json`, e toda chave que já consta de alguma partição nunca volta a ser
  submetida — nem as que terminaram em `ERROR` ou `EXPIRADO`. Reenviar custa, e
  o custo tem de ser escolhido por quem executa, não automático.
- **Partições em sequência.** O teto de enfileiramento do Gemini soma todos os
  lotes ativos do modelo; submeter as partições juntas estouraria o mesmo teto
  que a partição existe para respeitar. A próxima só parte quando a anterior
  terminou.
"""
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from .provedores.base import RespostaLLM
from .provedores.lote import (
    CONCLUIDO,
    ESTADOS_FINAIS,
    EXPIRADO,
    LOTE_EXPIRADO,
    NAO_ENCONTRADO,
    ErroLote,
    ProvedorLote,
    correlacionar,
    particionar,
)
from .provedores.precos import custo_usd

log = logging.getLogger(__name__)

NOME_ARQUIVO = "lote.json"
VERSAO_REGISTRO = 1

# Estados da PARTIÇÃO no registro local — não confundir com os do fornecedor.
PREPARADA = "PREPARADA"      # montada, nunca submetida
SUBMETENDO = "SUBMETENDO"    # rótulo em disco; a submissão pode ter ocorrido
SUBMETIDA = "SUBMETIDA"      # identificador do fornecedor em disco
GRAVANDO = "GRAVANDO"        # resultado lido; vereditos sendo gravados
RECUPERADA = "RECUPERADA"    # vereditos gravados nos CSVs

# Intervalo entre consultas de estado. Um lote fecha em minutos a horas; mais
# que isto só gasta cota de leitura.
INTERVALO_CONSULTA_S = 60.0


@dataclass
class Pendencia:
    """Uma requisição acumulada no lugar de uma chamada síncrona."""

    chave: str
    modelo: str
    prompt: str
    # Grava o veredito no CSV do braço — o mesmo ponto de gravação do síncrono.
    gravar: Callable[[RespostaLLM], None]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegistroLote:
    """`results/<run_id>/lote.json`: o que foi submetido, e onde está."""

    def __init__(self, caminho: str, dados: Optional[dict] = None):
        self.caminho = caminho
        self.dados = dados or {"versao": VERSAO_REGISTRO, "particoes": []}

    @classmethod
    def carregar(cls, caminho: str) -> "RegistroLote":
        if not os.path.exists(caminho):
            return cls(caminho)
        with open(caminho, encoding="utf-8") as f:
            return cls(caminho, json.load(f))

    @property
    def particoes(self) -> list:
        return self.dados["particoes"]

    def chaves_registradas(self) -> set:
        return {k for p in self.particoes for k in p["chaves"]}

    def salvar(self):
        """Grava de forma atômica: um registro truncado seria pior que nenhum.

        Escrever num temporário e renomear garante que, a qualquer instante, o
        arquivo em disco é a versão anterior inteira ou a nova inteira.
        """
        os.makedirs(os.path.dirname(self.caminho) or ".", exist_ok=True)
        tmp = self.caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.caminho)


def resumo_para_manifesto(dir_rodada: str) -> list:
    """Procedência de cada lote, sem as chaves (que ficam no `lote.json`)."""
    caminho = os.path.join(dir_rodada, NOME_ARQUIVO)
    if not os.path.exists(caminho):
        return []
    campos = ("indice", "fornecedor", "modelo", "rotulo", "id_lote", "estado",
              "estado_fornecedor", "n_requisicoes", "tokens_estimados", "bytes",
              "submetido_utc", "recuperado_utc", "tokens_entrada", "tokens_saida",
              "custo_tabela_usd", "desconto", "custo_estimado_usd", "n_error",
              "n_expirado", "n_orfas")
    return [{c: p.get(c) for c in campos}
            for p in RegistroLote.carregar(caminho).particoes]


def _nova_particao(indice, provedor, run_id, itens) -> dict:
    medidas = [provedor.medir(k, p) for k, p in itens]
    return {
        "indice": indice,
        "fornecedor": provedor.nome,
        "modelo": provedor.modelo,
        # Rótulo do CLIENTE, conhecido antes da submissão. O sufixo aleatório
        # impede que duas execuções da mesma rodada confundam seus lotes.
        "rotulo": f"{run_id}-p{indice}-{uuid.uuid4().hex[:8]}",
        "chaves": [k for k, _ in itens],
        "n_requisicoes": len(itens),
        "tokens_estimados": sum(t for t, _ in medidas),
        "bytes": sum(b for _, b in medidas),
        "id_lote": None,
        "estado": PREPARADA,
        "estado_fornecedor": None,
        "submetido_utc": None,
        "recuperado_utc": None,
    }


def _garantir_submissao(part, provedor, prompts, registro):
    """Deixa a partição com `id_lote`, submetendo só se preciso for."""
    if part["id_lote"]:
        return
    if part["estado"] == SUBMETENDO:
        # A execução anterior caiu depois de gravar o rótulo: a submissão pode
        # ter chegado ao fornecedor. Procurar antes de pagar de novo.
        achado = provedor.localizar(part["rotulo"])
        if achado:
            log.info("    [LOTE] partição %d já estava submetida: %s",
                     part["indice"], achado)
            part.update(id_lote=achado, estado=SUBMETIDA)
            registro.salvar()
            return
        log.info("    [LOTE] partição %d: rótulo sem lote no fornecedor; "
                 "submetendo.", part["indice"])

    faltando = [k for k in part["chaves"] if k not in prompts]
    if faltando:
        raise ErroLote(
            f"A partição {part['indice']} ainda não foi submetida e {len(faltando)} "
            f"de suas chaves não foram montadas nesta execução (ex.: "
            f"{faltando[0]}). A população mudou desde a execução anterior.")

    part["estado"] = SUBMETENDO
    registro.salvar()                    # ANTES de a requisição partir (D3)
    try:
        id_lote = provedor.submeter({k: prompts[k] for k in part["chaves"]},
                                    part["rotulo"])
    except Exception:
        # O retorno pode ter se perdido com o lote criado. Não se repete aqui:
        # a próxima execução procura pelo rótulo antes de submeter.
        log.error("    [LOTE] submissão da partição %d falhou; o registro "
                  "fica em %s para a retomada procurar o lote pelo rótulo.",
                  part["indice"], SUBMETENDO)
        raise
    part.update(id_lote=id_lote, estado=SUBMETIDA, submetido_utc=_agora())
    registro.salvar()
    log.info("    [LOTE] partição %d submetida: %s (%d requisições)",
             part["indice"], id_lote, len(part["chaves"]))


def _aguardar(part, provedor, dormir, intervalo_s, run_id) -> str:
    while True:
        estado = provedor.estado(part["id_lote"])
        if estado == NAO_ENCONTRADO:
            raise ErroLote(
                f"O lote {part['id_lote']} (partição {part['indice']}) não existe "
                f"mais no fornecedor. Nada foi ressubmetido: reenviar custa, e a "
                f"decisão é de quem executa.")
        if estado in ESTADOS_FINAIS:
            return estado
        log.info("    [LOTE] partição %d (%s): %s; nova consulta em %.0fs. "
                 "Interromper aqui não perde nada: o mesmo comando com "
                 "--run-id %s retoma.", part["indice"], part["id_lote"], estado,
                 intervalo_s, run_id)
        dormir(intervalo_s)


def executar_envio(pendencias: list, provedores: dict, dir_rodada: str,
                   run_id: str, ja_gravadas: frozenset = frozenset(),
                   dormir=time.sleep,
                   intervalo_s: float = INTERVALO_CONSULTA_S) -> int:
    """Leva as pendências até o CSV. Devolve quantos vereditos foram gravados.

    `pendencias` é o que ESTA execução montou; `ja_gravadas`, as chaves com
    linha em algum CSV da rodada (qualquer status). Uma partição interrompida
    no meio da gravação é recuperada de novo — ler do fornecedor não custa —, e
    `ja_gravadas` impede a linha duplicada.
    """
    registro = RegistroLote.carregar(os.path.join(dir_rodada, NOME_ARQUIVO))
    por_chave = {p.chave: p for p in pendencias}
    if len(por_chave) != len(pendencias):
        raise ErroLote("Chave repetida entre as pendências da rodada.")

    registradas = registro.chaves_registradas()
    recuperadas = {k for p in registro.particoes if p["estado"] == RECUPERADA
                   for k in p["chaves"]}
    pendentes_de_outrora = [k for k in por_chave if k in recuperadas]
    if pendentes_de_outrora:
        log.info("[!] %d requisição(ões) já passaram por um lote recuperado e "
                 "terminaram sem veredito válido (ERROR/EXPIRADO). NÃO são "
                 "reenviadas automaticamente: reenviar custa. Ver "
                 "docs/SCRIPTS.md, \"Modo de envio em lote\".",
                 len(pendentes_de_outrora))

    novas = [p for p in pendencias if p.chave not in registradas]
    for modelo in sorted({p.modelo for p in novas}):
        provedor = provedores[modelo]
        itens = [(p.chave, p.prompt) for p in novas if p.modelo == modelo]
        for grupo in particionar(itens, provedor.limites, provedor.medir):
            registro.particoes.append(_nova_particao(
                len(registro.particoes), provedor, run_id, grupo))
    registro.salvar()

    prompts = {p.chave: p.prompt for p in pendencias}
    abertas = [p for p in registro.particoes if p["estado"] != RECUPERADA]
    log.info("[+] Lote: %d partição(ões) no registro, %d a acompanhar.",
             len(registro.particoes), len(abertas))

    gravados = 0
    for part in abertas:
        provedor = provedores.get(part["modelo"])
        if provedor is None:
            log.info("    [LOTE] partição %d é do modelo %s, fora dos braços "
                     "desta execução; fica para uma execução que o inclua.",
                     part["indice"], part["modelo"])
            continue
        _garantir_submissao(part, provedor, prompts, registro)
        estado = _aguardar(part, provedor, dormir, intervalo_s, run_id)
        part["estado_fornecedor"] = estado

        recebidas = (provedor.recuperar(part["id_lote"])
                     if estado in (CONCLUIDO, LOTE_EXPIRADO) else {})
        respostas, orfas = correlacionar(part["chaves"], recebidas, estado,
                                         provedor.modelo, provedor.cobra_expirada)
        if estado == LOTE_EXPIRADO:
            log.info("    [LOTE] partição %d EXPIROU no fornecedor.", part["indice"])

        # Só uma partição que JÁ estava gravando quando a execução anterior
        # caiu pode ter linhas suas no CSV. Nas demais, uma linha pré-existente
        # da mesma chave é de outra partição (um reenvio deliberado de expirado)
        # e não pode barrar a gravação do resultado novo.
        retomando_gravacao = part["estado"] == GRAVANDO
        part["estado"] = GRAVANDO
        registro.salvar()

        for chave in part["chaves"]:       # ordem da submissão, não da resposta
            pend = por_chave.get(chave)
            if retomando_gravacao and chave in ja_gravadas:
                continue
            if pend is None:
                log.warning("    [ANOMALIA] chave submetida sem pendência nesta "
                            "execução, veredito não gravado: %s", chave)
                continue
            pend.gravar(respostas[chave])
            gravados += 1

        validas = list(respostas.values())
        tabela = sum(custo_usd(provedor.modelo, r.tokens_entrada, r.tokens_saida)
                     for r in validas)
        part.update(
            estado=RECUPERADA, recuperado_utc=_agora(),
            tokens_entrada=sum(r.tokens_entrada for r in validas),
            tokens_saida=sum(r.tokens_saida for r in validas),
            custo_tabela_usd=round(tabela, 8),
            desconto=provedor.desconto,
            custo_estimado_usd=round(tabela * (1 - provedor.desconto), 8),
            n_error=sum(1 for r in validas if r.veredito == "ERROR"),
            n_expirado=sum(1 for r in validas if r.veredito == EXPIRADO),
            n_orfas=len(orfas),
        )
        registro.salvar()
        log.info("    [LOTE] partição %d recuperada: %d vereditos, %d ERROR, "
                 "%d EXPIRADO, %d órfã(s); custo estimado US$ %.6f "
                 "(tabela US$ %.6f, desconto de lote %.0f%%).",
                 part["indice"], len(respostas), part["n_error"],
                 part["n_expirado"], len(orfas), part["custo_estimado_usd"],
                 tabela, provedor.desconto * 100)
    return gravados


__all__ = [
    "NOME_ARQUIVO",
    "Pendencia",
    "ProvedorLote",
    "RegistroLote",
    "executar_envio",
    "resumo_para_manifesto",
]

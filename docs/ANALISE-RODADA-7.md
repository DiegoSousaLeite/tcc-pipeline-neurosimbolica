# Rodada 7 — ficha por regra do Semgrep e variantes v2 do especialista

> **O que esta rodada testa.** Duas mudanças no braço especialista, medidas em
> dois modelos locais e nos dois modos de montagem: (1) a **granularidade da
> orientação** — fichas por regra do Semgrep em vez de fichas por CWE — e (2) a
> instrução do `*_v2` contra presumir mitigação ausente. Change
> `ficha-por-regra-semgrep`.
>
> **Conclusão (final, 2026-09-24, com todas as comparações pareadas).** A ficha
> por CWE vence em **3 de 4 cenários**, e nos dois da triagem com folga
> (qwen 80 × 2, gemma 116 × 12, pareados). A ficha por regra só vence no
> gemma/filtro (19 × 121), e por um motivo localizado: ali o modelo vê a
> mensagem do alerta de TLS **e** uma ficha por CWE que fala de `md5`, e junta as
> duas num falso alarme (57 só na CWE-327). Na triagem, sem o cabeçalho do
> alerta, a ficha por regra — que descreve o perigo da construção exata — é a que
> induz o alarme. O v2 troca muitos falsos alarmes por alguns acertos a mais e,
> no balanço, piora a acurácia.

## 1. Identificação

| campo | valor |
|---|---|
| run ids | `rodada-7-filtro-qwen`, `rodada-7-triagem-qwen`, `rodada-7-filtro-gemma`, `rodada-7-triagem-gemma` |
| execução | 2026-09-22 21:30 → 2026-09-23 19:02, um braço por vez (`scripts/rodada7.sh`) |
| código | branch `ficha-por-regra-semgrep`, commit `08be8eb` (catálogo) em diante |
| catálogo | por regra: `3d2bc71df131…` (CRLF) — hoje em `data/catalogo_cwe_por_regra.json` |
| modelos | `qwen2.5-coder:7b` (`dae161e27b0e`, Q4_K_M) e `gemma2:9b` (`ff02c3702f32`, Q4_0), 100 % GPU |
| amostragem | semente 42, temperatura 0, `num_ctx` 8192, `num_predict` 512 |
| população | `--tudo`: 2.328 casos; ~833 com alerta (filtro) e ~1.590 candidatos (triagem) |
| referências | especialista/baseline antigos: rodada `20260908T094808Z-9a00cb2` (qwen/filtro, CSV em disco); Rodadas 5 e 6 (triagem, **só agregados**: CSVs apagados) |

Só foi rodado o que não estava medido. Os baselines já medidos não foram
refeitos (o baseline não lê o catálogo): qwen/filtro vem de setembro;
`baseline_direto` de qwen e gemma, das Rodadas 5 e 6.

## 2. Resultados

`n` = vereditos válidos; P = precisão; R = recall; esp = especificidade
(proporção de alertas falsos descartados). Na triagem o MCC agregado é artefato
de composição (MAPA §4b.5e); o que vale é a leitura por procedência.

### 2.1 Filtro — qwen2.5-coder:7b

| braço | catálogo | n | VP | VN | FP | FN | P | R | MCC | esp |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | — | 825 | 8 | 690 | 116 | 11 | 0,065 | 0,421 | 0,116 | 0,856 |
| especialista | **por CWE** (set.) | 827 | 3 | 796 | 12 | 16 | 0,200 | 0,158 | **0,161** | 0,985 |
| especialista | por regra (R7) | 833 | 6 | 791 | 20 | 16 | 0,231 | 0,273 | 0,229 | 0,975 |
| especialista_v2 | por regra (R7) | 833 | 6 | 745 | 66 | 16 | 0,083 | 0,273 | 0,109 | 0,919 |

**A linha do especialista R7 engana se lida sozinha.** Os 6 VP incluem 3 casos
novos (goshs, CWE-22) que não estavam na população de setembro, atendidos pela
ficha genérica de fallback, que não mudou. **Nos mesmos 827 casos**:

| especialista, mesmos 827 casos | VP | FP | FN | R | MCC |
|---|---|---|---|---|---|
| por CWE | 3 | 12 | 16 | 3/19 | **0,161** |
| por regra | 3 | 20 | 16 | 3/19 | 0,121 |

McNemar pareado (acerto por caso):

| comparação | só A acerta | só B acerta | p |
|---|---|---|---|
| especialista por CWE × por regra | 12 | 4 | 0,077 |
| baseline × especialista por regra | 11 | 102 | 2,5·10⁻¹⁷ |
| especialista × especialista_v2 (ambos R7) | 47 | 1 | 8,3·10⁻¹¹ |

Por origem da ficha (especialista R7): as fichas **por regra** cobriram 534
casos com **0 VP** e 6 vulneráveis perdidos (CWE-89 ×4, CWE-94, CWE-79).

### 2.2 Filtro — gemma2:9b

O gemma nunca tinha rodado no filtro. O especialista com o catálogo por CWE foi
rodado depois, na **Rodada 7b** (`rodada-7b-filtro-gemma-cwe`, 2026-09-23
20:51 → 23:08, 833 chamadas, hash `e5db7d40…`; parte da rodada com 7 % do
modelo na CPU).

| braço | n | VP | VN | FP | FN | P | R | MCC | esp |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 828 | 5 | 679 | 127 | 17 | 0,038 | 0,227 | 0,031 | 0,842 |
| especialista, **por CWE** (R7b) | 827 | 4 | 633 | 173 | 17 | 0,023 | 0,190 | −0,009 | 0,785 |
| especialista, por regra | 826 | 4 | 736 | 69 | 17 | 0,055 | 0,190 | 0,058 | 0,914 |
| especialista_v2 (por regra) | 822 | 12 | 625 | 178 | 7 | 0,063 | **0,632** | **0,146** | 0,778 |

| comparação | só A acerta | só B acerta | p |
|---|---|---|---|
| baseline × especialista por CWE | **96** | 49 | 1,3·10⁻⁴ |
| especialista por CWE × por regra | 19 | **121** | 1,4·10⁻¹⁷ |
| baseline × especialista por regra | 34 | 89 | 1,1·10⁻⁶ |
| especialista por regra × especialista_v2 | 107 | 8 | 6,3·10⁻²⁰ |

Com o catálogo **oficial**, o especialista do gemma perde para o baseline no
filtro. Os falsos alarmes por CWE mostram a causa:

| CWE | por CWE | por regra | baseline | ficha por CWE fala de | a regra aponta |
|---|---|---|---|---|---|
| CWE-327 | **57** | 0 | 10 | `md5`/`sha1` em senha | `tls.Config` sem `MinVersion` |
| CWE-319 | 39 | 20 | 25 | URL `http://` | `InsecureSkipVerify`, `ListenAndServe` |
| CWE-328 | 27 | 15 | 33 | hash rápido em segredo | `md5`/`sha1` (mesma coisa) |
| CWE-352 | 8 | 0 | 3 | `SameSite` de cookie | WebSocket sem `CheckOrigin` |
| CWE-300 | 6 | 0 | 3 | (fallback genérico) | gRPC sem TLS |

Na CWE-327 o gemma lê "algoritmo criptográfico quebrado" na ficha e aplica ao
alerta de TLS ("desabilita a verificação... tornando o sistema vulnerável a
protocolos inseguros"). A ficha por regra, que explica o padrão TLS 1.2 do Go
moderno, zera esses 57. **É o desalinhamento produzindo erro** — no gemma.

O gemma/filtro é o único lugar em que o v2 sobe o MCC: acha 12 de 19
vulneráveis, ao custo de 178 falsos alarmes. Em acerto por caso ele perde
(107 × 8), porque a população é quase toda de alertas falsos.

### 2.3 Triagem — qwen2.5-coder:7b

| braço | n | VP | VN | FP | FN | alerta: R / esp / MCC | gabarito: R |
|---|---|---|---|---|---|---|---|
| R5 `especialista_direto` (por CWE) | 1587 | 40 | 773 | 35 | 739 | — | — |
| R7 `especialista_direto` (por regra) | 1589 | 40 | 692 | 119 | 738 | 5/22 · 0,853 · 0,036 | 35/756 |
| R7 `especialista_direto_v2` | 1590 | 66 | 604 | 207 | 713 | 14/22 · 0,745 · 0,138 | 52/757 |

R5 × R7: **não pareado** (CSVs da Rodada 5 apagados). Mesmo recall total (40),
falsos alarmes 35 → 119. `especialista_direto` × v2 (pareado): 97 × 35,
p = 1,1·10⁻⁷, a favor do especialista.

### 2.4 Triagem — gemma2:9b

| braço | n | VP | VN | FP | FN | alerta: R / esp / MCC | gabarito: R |
|---|---|---|---|---|---|---|---|
| R6 `especialista_direto` (por CWE) | 1563 | 62 | 696 | 107 | 698 | — | — |
| R7 `especialista_direto` (por regra) | 1560 | 58 | 592 | 212 | 698 | 8/20 · 0,736 · 0,047 | 50/736 |
| R7 `especialista_direto_v2` | 1565 | 123 | 473 | 331 | 638 | 9/17 · 0,588 · 0,034 | 114/744 |

R6 × R7: **não pareado**. Recall igual (62 → 58), falsos alarmes 107 → 212.
`especialista_direto` × v2 (pareado): 126 × 68, p = 4,3·10⁻⁵, a favor do
especialista.

## 3. Leitura

### 3.1 Ficha por regra: mesmo recall, mais falsos alarmes

Nos três lugares com referência, o padrão é o mesmo:

| comparação | recall | falsos alarmes |
|---|---|---|
| qwen/filtro, mesmos 827 casos (pareado) | 3/19 → 3/19 | 12 → 20 (p = 0,077) |
| qwen/triagem, R5 → R7 (agregado) | 40 → 40 | 35 → 119 |
| gemma/triagem, R6 → R7 (agregado) | 62 → 58 | 107 → 212 |

O catálogo por regra mudou duas coisas de uma vez — as 16 fichas por regra e a
reescrita de **todas** as heurísticas no formato "É VP quando ... / É FP
quando ..." —, e as duas contribuem:

- **Ficha por regra: o modelo repete a descrição do perigo.** A ficha descreve
  a construção exata do alerta, e o modelo pequeno reconhece a construção em vez
  de aplicar a condição. WebSocket (CWE-352, qwen/triagem): 16 de 17 seguros
  viram alarme com a justificativa "aceita conexões de qualquer origem" — falsa,
  porque o gorilla/websocket sem `CheckOrigin` já recusa origem diferente, o que
  a própria heurística diz. TLS (CWE-319): 36 de 86 seguros viram alarme, com a
  definição da ficha copiada quase literalmente, inclusive onde o
  `InsecureSkipVerify` só liga com uma flag `insecure`, que a heurística manda
  tratar como FP.
- **"É VP quando" em destaque ancora o veredito.** CWE-328, cuja ficha só teve a
  heurística reescrita: 29 de 41 seguros viram alarme, com justificativas
  contraditórias ("não é aplicada a senhas... mas MD5 é fraco"). Na triagem do
  qwen, a taxa de falso alarme nas fichas de CWE só reescritas (22 %, 57/257) é
  o dobro da das fichas por regra (11 %, 58/528).

A rodada não separa as duas causas. Separá-las pede um catálogo só com as fichas
por regra e as heurísticas originais — não feito, porque a decisão de catálogo
não depende disso.

### 3.1b O efeito depende do modelo

| modelo/modo | por CWE × por regra | leitura |
|---|---|---|
| qwen/filtro (pareado) | 12 × 4, p = 0,077 | por CWE levemente melhor, não significativo |
| gemma/filtro (pareado) | 19 × **121**, p ≈ 10⁻¹⁷ | por regra muito melhor |
| qwen/triagem (pareado, contra a reexecução da R5) | **80** × 2, p ≈ 10⁻¹⁷ | por CWE muito melhor |
| gemma/triagem (pareado, contra a reexecução da R6) | **116** × 12, p ≈ 10⁻¹⁹ | por CWE muito melhor |

A triagem foi pareada depois que as Rodadas 5 e 6 foram reexecutadas
(2026-09-24, mesma configuração, `resultados_parte2/rodada-{5-direto,6-gemma}/`).
Nos candidatos com alerta, a ficha por regra multiplica os falsos alarmes
(qwen 39 → 119; gemma 105 → 212) sem ganho relevante de recall; nos injetados
do gabarito o recall é o mesmo com as duas fichas (qwen 34 × 35 de ~757; gemma
48 × 50 de 736).

O qwen ignorou o desalinhamento: nas CWEs desalinhadas ele já dizia FP com
qualquer ficha. O gemma o seguiu no filtro: leu a ficha errada ao lado da
mensagem do alerta e alarmou. Na triagem, sem o cabeçalho do alerta, a ficha
por CWE desalinhada não tem com o que se combinar, e a ficha por regra — que
descreve o perigo da construção exata — passa a ser a pista que induz o alarme,
nos dois modelos. O padrão comum aos quatro cenários: **o modelo local alarma
quando o texto do prompt descreve um perigo que casa com algo que ele vê**; a
granularidade que vence é a que menos oferece esse casamento. A por CWE vence
em 3 de 4.

### 3.2 O que o especialista faz, afinal

O baseline e o especialista julgam o mesmo código; o especialista recebe a mais
só orientação sobre a classe da fraqueza. Com o catálogo por CWE, a orientação
**desloca a postura do modelo para o ceticismo**: recall 8 → 3 de 19, falsos
alarmes 116 → 12. Com 97 % de alertas falsos, isso sobe acurácia e MCC. Se a
orientação estivesse sendo usada para entender o código, recall e falsos alarmes
melhorariam juntos — não acontece em nenhum dos catálogos. O catálogo por regra
e o v2 empurram a postura de volta para o alarme, sem ganho de discriminação.

### 3.3 v2

Mais acertos de vulnerável e muito mais falsos alarmes, nos dois modelos e nos
dois modos. Em acerto por caso perde sempre para o especialista (4 McNemars, todos
com p < 10⁻⁴). Sobe o MCC no gemma/filtro e nos candidatos com alerta da
triagem do qwen, mas às custas de especificidade que o problema do TCC — reduzir
alertas falsos — não aceita.

## 4. Decisão

- **Catálogo oficial: por CWE** (`data/catalogo_cwe.json`, hash `e5db7d40…`), o
  das Rodadas 1–6. Restaurado como padrão ao fim da rodada (commit `5db626a`).
  A Rodada 7b mostrou uma exceção (gemma/filtro, §2.2), mas as comparações
  pareadas da triagem, feitas depois da reexecução das Rodadas 5 e 6,
  confirmam o por CWE como melhor em 3 de 4 cenários (§3.1b).
- O catálogo por regra fica em `data/catalogo_cwe_por_regra.json`, usável com
  `--catalogo`. Para o texto: enquadramento de granularidade (MAPA §11.6).
- O v2 não entra como braço principal.
- Pendente para os autores: rodada comercial com o catálogo por CWE e, em
  rodada separada, com o por regra (MAPA §11.8), para testar se um modelo que
  segue condições usa a ficha como contexto e não só como postura.

## 5. Ressalvas

- **Classe positiva pequena no filtro** (19–22 vulneráveis com veredito): as
  diferenças de recall são indicativas, não conclusivas.
- **Triagem pareada só depois da reexecução**: os CSVs originais das Rodadas 5
  e 6 foram apagados; a comparação pareada da triagem usa as reexecuções
  (mesma configuração), conferidas contra os números publicados em
  `resultados_parte2/*/REEXECUCAO.md`.
- **Linha duplicada**: por ~1 min duas instâncias rodaram juntas; uma linha
  (`175964b1:CWE-328:false_positive`, `especialista_v2` qwen/filtro) aparece duas
  vezes. `src/metricas.py` e estas contagens usam a primeira ocorrência.
- **Manifesto**: cada `manifesto.json` foi sobrescrito a cada braço e registra só
  o último. A rastreabilidade por braço está nas colunas `Modelo_LLM`,
  `Versao_Prompt` e `Hash_Catalogo` de cada linha, e nesta tabela de
  identificação.
- **População**: 6 casos do goshs (CWE-22) entraram na população depois de
  setembro; excluídos da comparação pareada.

## 6. Reprodução

```bash
# a rodada inteira (retomável; um braço por vez):
bash scripts/rodada7.sh     # com data/catalogo_cwe.json = catálogo por regra
# hoje o padrão é o por CWE; para reproduzir, passar
#   --catalogo data/catalogo_cwe_por_regra.json   a cada invocação

# métricas:
python -m src.metricas results/rodada-7-filtro-qwen --mcnemar
python -m src.metricas results/rodada-7-filtro-gemma --mcnemar
python -m src.metricas results/rodada-7-triagem-qwen --mcnemar
python -m src.metricas results/rodada-7-triagem-gemma --mcnemar
```

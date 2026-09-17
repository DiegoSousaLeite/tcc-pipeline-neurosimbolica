## Context

A camada simbólica é o gargalo medido do experimento. Das 797 amostras
vulneráveis, 19 produziram alerta (2,61 %). As duas maiores CWEs da população
concentram a perda:

| CWE | Pares | Detecções | Causa medida |
|---|---|---|---|
| CWE-22 | 114 | 0 | 2 regras estreitas; `os.Open(filepath.Join(base, input))` é sintaticamente idêntico ao código seguro |
| CWE-918 | 112 | 1 | regra única de taint; exige fonte e sumidouro no mesmo arquivo |

O denominador comum é o alcance do motor: **0 de 807 alertas** do corpus trazem
`dataflow_trace`, mesmo com `--dataflow-traces`. O Semgrep CE rastreia taint
apenas dentro de um arquivo, e as duas CWEs são, por natureza, fluxos que
atravessam camadas — handler HTTP num arquivo, função de leitura em outro.

A documentação do Semgrep declara para Go *"Generally available · Cross-file
dataflow analysis"*. A página de preços descreve o tier gratuito como incluindo
"Cross-file analysis with Pro rules" para até 10 contribuidores e 10
repositórios. **As duas afirmações têm pesos de evidência muito diferentes**: a
primeira é documentação técnica, a segunda é material comercial. É essa
assimetria que define a forma desta change.

**Fases tocadas:** 1 (invocação do Semgrep e identidade do motor), 5 (identidade
no manifesto). As Fases 2, 3 e 4 não mudam — a hidratação recebe um alerta e o
prompt recebe um contexto, independentemente de quem produziu o alerta.

**Arquivos tocados:**
- `src/fase1_semgrep.py` — montagem do comando, identidade do motor
- `src/cache_simbolico.py` — terceiro eixo da chave
- `src/ruleset.py` — alcançabilidade e grau em função do motor
- `src/fase5_auditoria.py` — identidade no manifesto
- `scripts/verificar_pro.py` — novo, é o portão
- `docs/PIPELINE.md`, `docs/SCRIPTS.md`

**Custo de LLM:** zero nesta change. Nenhuma tarefa aqui chama Gemini ou Ollama.
O portão e a repopulação do cache são puramente simbólicos. A rodada que
consumiria cota é posterior e fica fora deste escopo — se o portão passar e o
cache for repopulado, a decisão de gastar cota numa rodada Pro é separada e
deliberada.

**Tempo de execução:** a análise entre arquivos é substancialmente mais lenta que
a intra-arquivo, e a Fase 1 hoje já é a etapa cara. A repopulação do cache sob o
motor novo deve ser dimensionada como execução longa, não como reexecução
incremental.

**Dependências novas:** nenhuma dependência Python. A dependência nova é externa
e de outra natureza — conta no Semgrep AppSec Platform e um binário
(`semgrep install-semgrep-pro`) baixado de servidor de terceiros. O projeto é
deliberadamente enxuto em bibliotecas, e isto não viola essa política; mas
viola, parcialmente, a política mais importante de reprodutibilidade, e é por
isso que a change o mantém opcional. Ver Riscos.

## Goals / Non-Goals

**Goals:**

- Decidir, com evidência própria e barata, se o modo entre-arquivos é utilizável
  neste projeto, antes de qualquer investimento de implementação.
- Tornar a identidade do motor um dado de primeira classe, para que nenhum
  resultado simbólico seja ambíguo quanto a quem o produziu.
- Impedir, por construção, que uma troca de motor seja servida do cache antigo.
- Preservar integralmente a validade das Rodadas 1–3.

**Non-Goals:**

- Promover o Pro a motor padrão.
- Medir "CE contra Pro" como contribuição de pesquisa.
- Executar a rodada Pro completa — esta change entrega a capacidade, não o
  resultado.
- Resolver o tamanho da classe positiva, que é problema de
  `suficiencia-classe-positiva`.

## Decisions

### D1 — O portão é um script separado, não um teste

**Decisão:** `scripts/verificar_pro.py`, executado à mão, gravando um artefato de
resultado em disco.

**Por quê:** o que se verifica não é comportamento do nosso código — é
disponibilidade de um serviço de terceiros sob uma conta específica, numa
máquina específica. Isso não é testável na suíte: não roda em CI, não roda na
máquina de outra pessoa, e o resultado muda sem que o nosso código mude. Um
teste que depende de login externo é um teste que quebra por motivos alheios ao
projeto.

**Alternativa considerada:** teste de integração marcado para pular sem
credencial. Recusada porque o valor do portão está em produzir **evidência
datada e citável** — "em 15/09/2026, com conta gratuita, o modo entre-arquivos
[não] estava disponível" —, e um teste que pula não produz evidência nenhuma.

### D2 — Identidade do motor é um terceiro eixo da chave do cache, não parte da versão do ruleset

**Decisão:** `(repo, commit, arquivo, CWE)` continua sendo a chave; a entrada
passa a registrar três versões — ruleset, regra de pareamento e motor — e
diverge em qualquer uma.

**Por quê:** os três variam por motivos independentes. Espremer o motor dentro da
"versão do ruleset" faria o mesmo ruleset parecer duas coisas diferentes, e
perderia a capacidade de responder "este alerta veio de qual motor?" sem
reexecutar.

**Consequência deliberada:** entradas dos dois motores coexistem em disco. O
cache cresce, e isso é desejável — permite comparar CE e Pro sobre exatamente os
mesmos casos sem reexecutar nenhum dos dois.

**Alternativa considerada:** diretórios separados por motor. Recusada porque
duplicaria a lógica de leitura e tornaria a comparação entre motores um problema
de caminho de arquivo em vez de um problema de consulta.

### D3 — Entrada sem identidade é tratada como CE, não como desconhecida

**Decisão:** entradas anteriores a esta change são lidas como
`ce, modo entre-arquivos desligado`.

**Por quê:** é factualmente verdade — não havia outro motor quando foram
gravadas. Tratá-las como "desconhecidas" invalidaria o cache inteiro e forçaria
uma reexecução completa da Fase 1 sobre a população, sem nenhum ganho de
correção.

**Contraste deliberado com a regra de pareamento**, que faz o oposto: lá,
entrada sem versão é tratada como divergente e recomputada. A assimetria é
intencional. No pareamento, a ausência da versão significava que o conteúdo podia
estar errado sob a regra nova. Aqui, a ausência significa apenas que o campo não
existia; o conteúdo continua correto para o motor CE.

### D4 — O modo fica atrás de flag, desligado, e falha cedo se pedido sem viabilidade

**Decisão:** opção explícita de invocação; se pedida sem registro de verificação
bem-sucedida, a execução aborta.

**Por quê:** o modo de falha a evitar é o silencioso. Se o Pro for pedido e o
Semgrep cair de volta no CE sem avisar, a rodada produz números CE rotulados
como Pro — e nada no CSV denunciaria isso.

### D5 — A alcançabilidade sob Pro é declarada como limite inferior, não estimada

**Decisão:** quando o modo entre-arquivos está ativo e o catálogo disponível não
enumera as regras próprias do modo, a consulta devolve o conjunto derivado do
catálogo aberto **marcado como limite inferior**.

**Por quê:** as regras Pro não constam do catálogo público do registry, então não
há como derivá-las honestamente. Duas saídas erradas foram descartadas: estimar
a cobertura extra (inventaria número), e tratar o conjunto aberto como exato
(recusaria, na colheita, população que o motor detectaria — o defeito exato que
`ruleset-alcancabilidade` existe para prevenir). Declarar a incerteza é a única
saída que não mente.

### D6 — O eixo de taint do grau passa a depender do motor

**Decisão:** sob motor com modo entre-arquivos, CWE coberta só por regras de
taint recebe grau alto, não intermediário.

**Por quê:** a justificativa escrita do grau intermediário é *"o motor não
rastreia fluxo entre arquivos"*. É uma afirmação sobre o motor, não sobre a CWE.
Sob um motor que rastreia, mantê-la faria a escala descrever uma limitação
extinta, e a colheita continuaria evitando CWE-918 — que é precisamente o que a
troca de motor pretende destravar.

**Consequência:** a validação empírica do grau (alta 11,30 %, media 1,67 %,
baixa 0,30 %) vale para o motor CE e **não transfere**. Sob Pro, a escala precisa
ser revalidada do zero. Isto não é custo extra: a validação já era trabalho
futuro declarado em `validacao-do-grau`.

### D7 — A unidade de análise da Fase 1 é o limite real, e o portão roda em duas etapas

**Decisão:** o portão não roda sobre o cache de fontes. Roda primeiro sobre um
projeto Go mínimo escrito para este fim, e só depois — se a primeira etapa não
matar a change — sobre checkouts rasos de repositórios reais da população.

**Por quê:** a Fase 1 invoca o Semgrep sobre **um arquivo isolado**
(`src/fase1_semgrep.py`), e o cache de fontes guarda exatamente isso. Medido
sobre os 226 casos de CWE-22 e CWE-918: 69 têm um único arquivo no diretório do
commit, 87 têm dois, e os vizinhos são arquivos vulneráveis de *outros* casos,
não os chamadores. Não há `go.mod` nem estrutura de pacote.

O diagnóstico que motiva esta change é que a fonte do taint está em outro
arquivo. Esse arquivo não está no cache. Portanto o modo entre-arquivos, rodado
sobre o cache, não tem para onde atravessar: devolveria zero trilhas
**independentemente de o motor funcionar**, e o portão classificaria
`inconclusivo`. A change morreria por um artefato do nosso harness, não por uma
propriedade do Semgrep — o pior resultado possível, porque pareceria evidência.

**Ordem das etapas:** a etapa sintética custa segundos e pode devolver
`indisponível` (tier gratuito recusa o Pro), que encerra tudo sem clonar nada. A
etapa de checkouts reais custa disco e rede, escassos nesta máquina — `repos/`
já foi apagado três vezes por isso. Pagar o barato primeiro é o que torna o
portão barato de verdade.

**Alternativa considerada:** só a etapa sintética. Recusada porque ela responde
"o motor funciona em Go", e não "o motor alcança os nossos casos" — e é a
segunda pergunta que autoriza gastar tempo de repopulação.

**Consequência para a Tarefa 5.1:** ela herda o mesmo defeito. Repopular o cache
simbólico sob o motor novo, mantendo o arquivo isolado como unidade de análise,
produziria resultado equivalente ao CE a custo de Pro. Se o portão passar, a
repopulação precisa operar sobre checkout do repositório no commit, e isso é
mudança na entrada da Fase 1 — não apenas na sua invocação. **Está fora do que
os artefatos atuais descrevem e precisa de decisão própria antes da seção 5.**

## Risks / Trade-offs

**[O portão falha e a change morre]** → É o desenho, não um acidente. O custo
perdido é o da Tarefa 1; tudo depois dela está condicionado. O resultado
negativo é registrado com data e evidência e vira uma linha de trabalhos
futuros com respaldo, que é mais do que se tem hoje.

**[Dependência de binário proprietário sem versionamento sob nosso controle]** →
Mitigação parcial: registrar a versão exata do binário no manifesto e congelar o
SARIF no cache. Mitigação impossível: garantir que a mesma versão continue
disponível depois. **Esta é uma piora real na ameaça "ruleset não fixado" já
mapeada — agora o motor também muda do lado do servidor — e deve ser declarada
no texto do TCC, não escondida atrás do ganho de detecção.**

**[A esteira deixa de ser offline]** → Mitigação: a invariante do projeto nunca
foi "sem rede", e sim "buscar uma vez, congelar, reexecutar offline" — é assim
que o cache de ruleset (`requests.get` no registry) e o cache de fontes já
operam. O modo Pro acrescenta uma busca autenticada à etapa de preenchimento e
nada à de reexecução. `docs/PIPELINE.md` precisa passar a dizer isso com
precisão, porque hoje afirma offline sem qualificar.

**[Ganho nulo: o modo roda e não acha nada]** → Cenário plausível. As CWEs secas
podem estar secas por falta de regra adequada, não só por falta de alcance —
CWE-22 tem 2 regras estreitas, e alcance entre arquivos não conserta regra
estreita. Por isso o portão distingue "viável" de "inconclusivo quanto ao ganho":
o segundo não autoriza a implementação. **Se cair aqui, o caminho alternativo é
`p/gosec`, que ataca CWE-22 por regra sintática e não depende de alcance algum.**

**[Tempo de repopulação do cache]** → A análise entre arquivos é mais lena e a
Fase 1 já é a etapa cara. Mitigação: repopular por CWE, começando por CWE-22 e
CWE-918, que são onde o ganho é esperado. Se não houver ganho nelas, não há
motivo para repopular o resto.

**[Comparabilidade perdida por acidente]** → Mitigação em três camadas: flag
desligada por padrão, cache que invalida por motor, e identidade no manifesto.
As três precisariam falhar juntas para que uma rodada Pro fosse confundida com
uma rodada CE.

## Migration Plan

1. Portão. Se falhar, arquivar a change com o resultado registrado.
2. Identidade e chave de cache — mudanças estruturais, sem efeito observável
   enquanto a flag estiver desligada. Verificar que uma rodada CE produz
   exatamente os mesmos alertas de antes.
3. Repopulação seletiva do cache sob o motor novo, restrita a CWE-22 e CWE-918.
4. Medir a detecção nessas duas CWEs e comparar com o CE sobre os mesmos casos.
5. Só então decidir sobre rodada completa, que é escopo de outra change.

**Rollback:** desligar a flag. As entradas de cache do motor CE permanecem em
disco e válidas, porque a change nunca as apaga nem sobrescreve.

## Open Questions

- O tier gratuito realmente entrega o modo entre-arquivos? **É o que a Tarefa 1
  responde, e nada depois dela começa antes da resposta.**
- Se o portão passar, a Fase 1 passa a analisar o repositório no commit em vez
  do arquivo isolado? É o que D7 deixa em aberto, e a seção 5 depende disso.
  Muda o custo de parede da fase mais cara da esteira e o significado de
  `SEM_ALERTA` — um alerta pode passar a apontar para arquivo diferente do do
  gabarito, e a regra de pareamento não prevê isso.
- As regras próprias do modo Pro são enumeráveis por alguma via programática? Se
  forem, D5 pode ser substituída por derivação exata em vez de limite inferior.
- O ganho em CWE-22 é de alcance ou de regra? Se as 2 regras estreitas
  continuarem sendo o limitante, o modo entre-arquivos não resolve aquela CWE e
  `p/gosec` é o caminho.
- Qual o custo real em tempo da repopulação? Não há estimativa; a Tarefa 1 deve
  medir o tempo sobre a amostra e permitir extrapolar.

## Why

As duas maiores CWEs da classe positiva são baldes secos, e a causa é conhecida
e mecânica:

- **CWE-22** (path traversal): 114 pares, **0 detecções**.
- **CWE-918** (SSRF): 112 pares, **1 detecção**.

Ambas dependem de fluxo de dados que atravessa arquivos, e o Semgrep CE rastreia
taint apenas **dentro de um arquivo**. A medição confirma: **0 de 807 alertas**
do corpus trouxeram trilha de dataflow, mesmo com `--dataflow-traces`. Não é
falta de regra — é falta de alcance do motor. Nenhum ajuste de ruleset resolve
isto, porque a regra existe e simplesmente não tem como ver a origem do dado.

A documentação do Semgrep declara para Go: *"Generally available · Cross-file
dataflow analysis"*. Se o Pro Engine estiver acessível sem custo, ele ataca
exatamente a causa medida, e não um sintoma.

**O problema é que a evidência de gratuidade é fraca.** Ela vem de
`semgrep.dev/pricing`, página comercial, que descreve o tier gratuito como
incluindo "Cross-file analysis with Pro rules" para até 10 contribuidores e 10
repositórios. Isso não é documentação técnica nem termo de licença. Páginas de
preço mudam e descrevem tiers de forma otimista.

Por isso esta change **começa por um teste de viabilidade que pode matá-la**. Se
o Pro Engine exigir plano pago, ou não produzir trilha entre arquivos em Go, a
change é arquivada sem implementação — e o resultado negativo vira uma linha na
seção de trabalhos futuros, com evidência.

**Pergunta de pesquisa atendida:** **Q3** diretamente (desempenho por categoria
de CWE — hoje duas categorias grandes são inavaliáveis por ausência de alerta) e
a metade não respondida da **Q2** de forma indireta, porque toda detecção nova na
classe positiva alimenta o cálculo de falsos negativos. É trabalho de **Parte 2**.

## What Changes

- **Teste de viabilidade como portão** (`scripts/verificar_pro.py`): mede, sobre
  uma amostra fixa do cache, se o Pro Engine roda com conta gratuita e se o SARIF
  passa a trazer `dataflow_trace`. Registra o resultado em disco. **A change não
  avança se o portão falhar.**
- **Motor simbólico passa a ser explícito**, não implícito. Hoje o binário e o
  modo são pressupostos; passam a ser identidade declarada (`ce` ou `pro`),
  registrada junto com cada resultado simbólico.
- **Chave do cache simbólico ganha a identidade do motor.** Um SARIF produzido
  pelo CE e outro pelo Pro descrevem o mesmo caso de formas diferentes; sem isso
  eles colidiriam na mesma entrada e uma rodada serviria silenciosamente o
  resultado do motor errado.
- **Nova rodada como braço separado**, nunca como substituição. As Rodadas 1–3
  permanecem CE e continuam citáveis.
- **BREAKING (condicional):** se o Pro for adotado, os conjuntos de alertas
  deixam de ser comparáveis com os das rodadas anteriores. Ver "Impacto".

## Capabilities

### New Capabilities

- `motor-simbolico-identidade`: identidade declarada do motor que produziu um
  resultado simbólico (edição, versão, modo entre-arquivos ligado ou não) e a
  garantia de que ela acompanha o resultado até a auditoria. Inclui o portão de
  viabilidade que decide se o modo Pro é sequer utilizável neste projeto.

### Modified Capabilities

- `cache-simbolico`: a chave da entrada passa a incluir a identidade do motor,
  ao lado da versão do ruleset e da versão da regra de pareamento que já
  constam. Sem isso, trocar de motor não invalida o cache e a rodada mente.
- `ruleset-alcancabilidade`: o conjunto alcançável passa a ser função do motor
  **e** do ruleset, não só do ruleset. O catálogo do registry descreve as regras
  do CE; o Pro acrescenta regras próprias e alcance entre arquivos, e uma
  consulta que ignore isso subestima a cobertura em silêncio — o mesmo defeito
  que esta capability foi criada para evitar.

## Impact

**Código:** `src/fase1_semgrep.py` (invocação e identidade do motor),
`src/cache_simbolico.py` (chave), `src/ruleset.py` (alcançabilidade em função do
motor), `scripts/verificar_pro.py` (novo), `src/fase5_auditoria.py` (identidade
no manifesto da rodada).

**Documentação:** `docs/PIPELINE.md` (a afirmação de esteira offline precisa
dizer que o modo Pro exige uma busca autenticada antes de congelar),
`docs/SCRIPTS.md` (script novo).

**Dependências externas:** conta gratuita no Semgrep AppSec Platform e binário
baixado por `semgrep install-semgrep-pro`. Nova dependência de serviço
autenticado de terceiros na camada simbólica — hoje a dependência de rede
existe, mas é só a busca anônima do ruleset no registry.

**Resultados invalidados:** nenhum, **desde que o Pro entre como braço novo**. As
Rodadas 1–3 permanecem válidas e citáveis como medições do Semgrep CE. Se em
algum momento o Pro virar o padrão da esteira, toda a matriz experimental
precisa ser reexecutada e os CSVs das rodadas anteriores passam a descrever
outro motor — por isso a change o mantém atrás de flag, desligado por padrão.

**Ameaça à validade introduzida:** o Pro Engine é binário proprietário obtido de
servidor de terceiros, sem versionamento sob nosso controle. A ameaça de
"ruleset não fixado", já mapeada, fica mais forte: agora o *motor* também pode
mudar do lado do servidor.

## Não-objetivos

- **Não** adotar o Pro como motor padrão da esteira. Entra atrás de flag,
  desligado, e a decisão de promover é posterior e separada.
- **Não** reexecutar as Rodadas 1–3.
- **Não** transformar "CE contra Pro" em contribuição de pesquisa. A comparação
  sai de graça e pode ser reportada como observação, mas o TCC não é sobre isso.
- **Não** tocar nas Fases 3/4 nem no desenho de filtro puro. Esta change mexe
  apenas no que a camada simbólica enxerga.
- **Não** reintroduzir CodeQL, que é legado por decisão anterior.
- **Não** resolver o tamanho da classe positiva. Mesmo no melhor caso, o Pro
  amplia a detecção em duas CWEs; a suficiência da classe positiva continua
  sendo problema de `suficiencia-classe-positiva`.

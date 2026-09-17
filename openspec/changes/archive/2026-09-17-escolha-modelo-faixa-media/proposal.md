## Why

Todas as Rodadas 1 a 6 rodaram em modelo local. **O projeto inteiro tem 17
vereditos comerciais**, vindos de um piloto de `gemini-2.5-flash-lite`, mais 5
`API_ERROR` — os demais CSVs comerciais (`sizing-fp`, `cobertura-tp-dataset`)
são de execuções `--sem-llm` e não têm veredito nenhum. A "matriz 2x2 de
referência" que `matriz-experimental` declara **existe no papel e nunca foi
executada**.

Isso escopa a conclusão do trabalho em *"com modelos locais de 7–9 B"*, que é
frágil: a primeira pergunta da banca é se um modelo capaz não resolveria. E o
resultado central é **negativo** — pontos cegos majoritariamente compartilhados,
4 a 8 % de recall sobre o que o SAST perde —, e resultado negativo precisa de
escopo largo para valer.

Os dois modelos padrão do projeto (`gemini-2.5-flash-lite`, `gpt-4o-mini`) são
**a faixa barata** de cada fornecedor, provavelmente na mesma banda de
capacidade de um 7 B especializado em código. Rodá-los custaria ~US$ 0,45 e
produziria evidência fraca: um modelo pequeno confirmando o que outro modelo
pequeno já disse.

Com os tokens já medidos (3.198.141 de entrada e 315.469 de saída por rodada de
dois braços), uma rodada em faixa média custa da ordem de **US$ 14** — barato o
bastante para não ser decisão orçamentária, caro o bastante para merecer escolha
justificada em vez de chute.

**Pergunta de pesquisa atendida:** o escopo de validade das respostas a Q1, Q2 e
Q3. Não acrescenta pergunta nova; delimita até onde as existentes valem.

## What Changes

- **Levantamento de modelos de faixa média disponíveis**, com preço por milhão
  de tokens de entrada e de saída **verificado na fonte primária do
  fornecedor**, não de memória.
- **Custo por rodada calculado com os tokens reais medidos** desta pipeline, e
  não com estimativa: entrada, saída e total, por modelo, para uma rodada de
  dois braços e para a matriz completa.
- **Custo de integração por modelo**: o que cada um exige de `src/provedores/`,
  dado que a camada já existe e tem contrato definido. Um modelo que fale o
  protocolo de um provedor já implementado custa quase nada; um que exija
  provedor novo custa mais.
- **Limites de taxa e o que eles implicam de parede**, com o intervalo mínimo
  entre chamadas que o projeto já respeita. Custo não é o gargalo; vazão pode
  ser.
- **Recomendação de um modelo**, com o critério explícito e as alternativas
  recusadas registradas com o motivo.
- **Registro do que fica fora de escopo por decisão**, e não por esquecimento.

**Não há mudança de comportamento do sistema.** Esta change não implementa
provedor, não altera a tabela de preços, não executa rodada e não gasta cota.
Entrega um documento de decisão.

## Capabilities

### New Capabilities

- `escolha-de-modelo-comercial`: o que um levantamento de modelo precisa
  produzir para que a escolha seja auditável meses depois — preço de fonte
  primária com data, custo calculado sobre tokens medidos, custo de integração,
  limite de taxa, e as alternativas recusadas com o motivo.

### Modified Capabilities

Nenhuma. `matriz-experimental` já permite modelo adicional nomeado
explicitamente, e esta change não altera requisito algum do sistema.

## Impact

**Código:** nenhum. Esta change não toca em `src/`, `run_pipeline.py`,
`prompts/` nem na tabela de preços.

**Documentação:** cria `docs/ESCOLHA-MODELO-COMERCIAL.md`, que é a entrega. E
acrescenta ao `docs/MAPA-TCC-O-QUE-REESCREVER.md` o registro de que a matriz
comercial nunca foi executada — hoje isso não está declarado em lugar nenhum, e
é limitação que o texto precisa assumir independentemente do que se decida rodar.

**Cota e custo:** zero. Nenhuma chamada de API é feita.

**Acesso:** a change **não assume** billing, chave de API ou conta ativa em
fornecedor algum. O que seria preciso ativar é parte do que ela levanta.

**Resultados invalidados:** nenhum.

**Dependência para o que vem depois:** a decisão registrada aqui é o insumo de
uma change futura que implemente o provedor e execute a rodada. Essas duas
coisas são deliberadamente separadas desta.

## Não-objetivos

- **Não** implementar provedor novo em `src/provedores/`.
- **Não** atualizar a tabela de preços do projeto — ela é lida no manifesto e
  alterá-la sem rodada é ruído.
- **Não** executar rodada comercial nem gastar um centavo de cota.
- **Não** decidir se a rodada vai acontecer. A change produz a informação; a
  decisão de gastar é de quem lê.
- **Não** reabrir a escolha dos modelos locais já medidos.

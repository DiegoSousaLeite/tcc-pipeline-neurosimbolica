# Auditoria qualitativa de `reasoning` — critério de classificação (Q4)

> **Registrado em 2026-09-22, ANTES da amostragem e antes da leitura de qualquer
> caso.** A ordem é a mesma garantia da partição das regras próprias: o critério
> não pode ter sido ajustado ao que a amostra mostrou. Qualquer alteração depois
> desta data vai para a §5 abaixo, datada, e não sobrescreve o texto original.
>
> ⛔ Não commitar sem pedido explícito do autor (change `escrita-capitulo-resultados`).

## 1. Fonte

Rodada 3 (`results/20260908T094808Z-9a00cb2`), braço de **filtro**,
`qwen2.5-coder:7b`, prompts `baseline:597fcfa9` e `especialista:d1145f8b`.

É a única rodada cujos CSVs ainda existem em disco (os das Rodadas 4–6 não estão
mais na máquina), e é a rodada do resultado principal (TRA 0,9819; McNemar 104 × 5).
O contexto que o modelo recebeu é recuperável byte a byte: o campo
`contexto_hidratado` do cache simbólico é exatamente o bloco entregue ao prompt no
modo filtro.

## 2. Unidade e amostra

**Unidade:** o par (caso, prompt). Cada caso sorteado é lido **nos dois prompts**,
o que torna a auditoria pareada e permite responder à parte da Q4 que pergunta
pela *influência* das regras teóricas no raciocínio.

**Estratos**, definidos pela célula do caso no braço especialista (e, no último,
também pelo baseline):

| estrato | definição | população | sorteados |
|---|---|---:|---:|
| E-VP | vulnerável, especialista manteve | 3 | 3 (todos) |
| E-FP | seguro, especialista manteve | 12 | 12 (todos) |
| E-FN | vulnerável, especialista descartou | 16 | 5 |
| E-VN/B-FP | seguro, especialista descartou, baseline manteve | ver script | 5 |

25 casos × 2 prompts = **50 vereditos**. Sorteio com `random.Random(42)` sobre os
`ID_Caso` ordenados, pelo script `amostrar.py` desta pasta.

Os estratos minoritários são tomados por inteiro porque são justamente os
interessantes (D3 do design) e porque, sorteados proporcionalmente, desapareceriam.
**Consequência:** proporções da amostra NÃO estimam proporções da população sem
reponderação; o capítulo deve reportá-las por estrato.

## 3. Eixo 1 — tipo de fundamento (responde à Q4)

Classifica-se o `reasoning` (coluna `Justificativa`) contra o código efetivamente
entregue ao modelo, sem consultar o gabarito primeiro. O acerto do veredito é
registrado em coluna separada; o fundamento é julgado por si.

- **FUNDADO** — o argumento se apoia em elementos que existem no código recebido
  (identificadores, chamadas, verificações), interpreta-os corretamente, e, se
  verdadeiro, sustenta o veredito emitido.
- **MOTIVO_ERRADO** — nenhum elemento inventado, mas o argumento não sustenta o
  veredito: genérico (valeria para qualquer código), circular ("é falso positivo
  porque não é vulnerável"), sobre outra fraqueza que não a em exame, ou
  contraditório com o próprio veredito.
- **ALUCINACAO** — afirma a existência de algo que não está no código recebido
  (validação, sanitização, chamada, parâmetro), ou atribui a uma API da
  biblioteca padrão de Go comportamento que ela não tem.

Precedência: se há alucinação que sustenta a decisão, classifica-se
`ALUCINACAO` mesmo que o resto do argumento seja razoável.

A categoria "correto por motivo errado" da metodologia corresponde ao cruzamento
**veredito correto ∧ MOTIVO_ERRADO** (ou ∧ ALUCINACAO); não é um rótulo à parte.

## 4. Eixo 2 — o seguro mantido era de fato seguro? (classe negativa aproximada)

Aplica-se só aos pares em que o **gabarito é seguro e o modelo manteve o alerta**.
Lê-se o código recebido e decide-se:

- **SEGURO** — o código, como está, não exibe a fraqueza.
- **VULNERAVEL** — o código exibe uma fraqueza real (da CWE rotulada ou de outra),
  isto é, o "falso positivo" do gabarito é discutível.
- **INDETERMINADO** — o recorte de uma função não basta para decidir (a
  controlabilidade da entrada, por exemplo, depende de código fora do recorte).

`INDETERMINADO` é resposta legítima e não deve ser forçado para um dos lados:
é, em si, uma medida de quanto o gabarito por arquivo depende de contexto que o
recorte não traz.

## 5. Declarações obrigatórias ao reportar

1. A classificação **não é cega**: quem classifica vê o veredito, e pode ver o
   gabarito. O eixo 1 é julgado antes de consultar o gabarito, mas isso é
   procedimento, não cegamento.
2. **Pré-classificação**: a primeira passada foi feita com assistência de
   ferramenta de IA generativa, por decisão dos autores, e está marcada como
   provisória na planilha até revisão humana. O capítulo precisa dizer isso
   enquanto a revisão não estiver concluída.
3. Classificador único, sem medida de concordância entre avaliadores.

## 6. Alterações posteriores ao registro

**2026-09-22, durante a leitura — esclarecimentos de aplicação, não mudança de
categoria.** Dois tipos de caso não estavam previstos na redação da §3 e foram
decididos da forma mais conservadora em relação à categoria `ALUCINACAO`:

1. **Afirmar a ausência de algo que está presente** (por exemplo, "o cookie é
   criado sem o atributo `Secure`" quando o código traz `Secure: o.cookieSecure`)
   e **ler um elemento existente ao contrário** (inverter o ramo de um `if`) foram
   classificados como `MOTIVO_ERRADO`, e não como `ALUCINACAO`, porque a §3 define
   alucinação pela afirmação de existência. A escolha **subestima** a taxa de
   alucinação; a alternativa a superestimaria.
2. **Alucinação acessória** — afirmação inventada que não é o argumento principal
   (o `io.CopyN` do caso 8, o `ListenAndServe` "que não envia texto claro" do
   caso 23) — foi classificada `ALUCINACAO`, porque a §3 a define pela afirmação,
   e a cláusula de precedência só trata do caso em que ela sustenta a decisão.

**Artefato de dados encontrado.** A coluna `Justificativa` dos CSVs aparece
truncada no primeiro caractere de aspas duplas em pelo menos um caso (caso 0,
`mailpit`). Os dois vereditos afetados foram classificados sobre o texto
disponível.

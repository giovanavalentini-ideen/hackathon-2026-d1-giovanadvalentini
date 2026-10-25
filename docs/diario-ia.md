# Diário de uso da IA

Registro feito durante o trabalho, na hora em que acontece. Alimenta a seção "Onde a IA errou" do README.

Uma entrada por ocorrência: onde a IA acelerou, onde errou e como foi revisado.

| Data e hora | Tipo | O que aconteceu | Como percebi | O que fiz |
|---|---|---|---|---|
| 23/10 | acelerou | Leitura do deck e do kit e levantamento das armadilhas da seção "Semântica" | Conferi contra o ENUNCIADO.md | Usei como lista de casos de borda a testar |
| 25/10 | errou | A análise da opção 1 dizia que o orjson recusa inteiros acima de 64 bits e que bastava voltar ao json nas linhas que falhassem. O orjson aceita esses números e devolve float sem erro: `18446744073709551616` vira `1.8446744073709552e+19` | Teste lado a lado de orjson e json com números de borda antes de escrever o fallback | A função gerada pede releitura com json quando encontra float de módulo >= 2**63, e um id float também força releitura; testes `test_inteiro_acima_de_64_bits_sai_exato` e `test_valores_enormes_que_so_diferem_no_fim` |

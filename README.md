# plan_bench

Benchmark isolado para `text → travel plan JSON`. Compara várias abordagens de prompting/agentes.

## Setup
```bash
pip install -r requirements.txt
```
A chave OpenAI é lida automaticamente de `noma_backend_local/system/env_config.py` (ou da env var `OPENAI_API_KEY`).

## Pipeline
```bash
# 1. Gera N planos sintéticos (ground truth). Sem LLM.
python dataset/generate_plans.py --n 200

# 2. Gera o texto natural para cada plano (gpt-3.5-turbo).
python dataset/generate_texts.py

# 3. (apenas para a5) Pré-computa embeddings dos textos.
python approaches/a5_fewshot_retrieval.py --build-index

# 4. Roda todas as approaches e salva métricas.
python eval/run_eval.py

# Dev rápido:
python eval/run_eval.py --limit 10 --approaches a1_structured,a3_cot,a11_skills_agent
```

## Approaches
| name | ideia |
|---|---|
| a1_structured | gpt-5 + structured output |
| a2_reasoning  | o-series + reasoning_effort=high |
| a3_cot        | chain-of-thought escrito + JSON final |
| a4_fewshot_fixed | 3 exemplos hard-coded |
| a5_fewshot_retrieval | top-k via embeddings (leave-one-out) |
| a6_two_stage  | sub-objetivos → JSON |
| a7_self_consistency | n=5 + voto por campo |
| a8_critic_revise | gerador → crítico → revisor |
| a9_decomposed_tools | extratores separados (pax/voos/hotéis) + merge |
| a10_reflexion | gera → auto-reflexão → regenera (k=3) |
| a11_skills_agent | router escolhe entre 10 skills especializadas |

## Métricas
`exact_match`, `trip_type_acc`, `travelers_f1`, `flights_f1`, `hotels_f1`, `iata_validity`, `date_validity`, `schema_valid`.

Resultados em `eval/out/results.csv` (item-a-item) e `eval/out/summary.csv` (média por approach).

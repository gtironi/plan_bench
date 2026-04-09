# plan_bench

Benchmark isolado para `texto (pt-BR) → travel plan JSON`. Compara várias abordagens de prompting / agente sobre o mesmo dataset.

## Setup

```bash
pip install -r requirements.txt
```

A chave OpenAI é lida de `OPENAI_API_KEY` ou, se vazia, de `noma_backend_local/system/env_config.py` (caminho definido em `config.py`).

**Modelos** (um único sítio para alterar): `config.py` — `MODEL_DATASET` (textos sintéticos), `MODEL_MAIN`, `MODEL_REASONING` (`a2`), `MODEL_EMBED` (`a5`).

## Pipeline

```bash
# 1. Gera N planos sintéticos (ground truth). Sem LLM.
python dataset/generate_plans.py --n 200

# 2. Gera texto natural a partir dos planos (MODEL_DATASET, ex. gpt-3.5-turbo).
python dataset/generate_texts.py --n 40

# 3. (só a5) Índice de embeddings dos textos.
python approaches/a5_fewshot_retrieval.py --build-index

# 4. Corre todas as approaches; métricas e custo em eval/out/
python eval/run_eval.py

# Dev rápido (sem prompt de confirmação):
python eval/run_eval.py --yes --limit 10 --approaches a1_structured,a3_cot,a11_skills_agent
```

Flags úteis de `run_eval.py`: `--budget` (USD, hard stop via `tracker`), `--yes` (pula estimativa interativa), `--approaches` (lista ou prefixo, ex. `a1`).

**Retomar após um budget stop (ou interrupção):** por omissão o eval **usa checkpoints** em `eval/out/{approach}_preds.jsonl`: itens já guardados (campo `item_key`, ou hash legado do `text`) **não voltam a chamar a API**. O `results.csv` é regenerado a partir dos JSONL + dataset. **`--no-resume`** apaga o checkpoint de cada approach no início do loop e força novas chamadas; também remove `cost.csv` e **`per_request.csv`** no arranque.

## Approaches

| name | ideia |
|------|--------|
| a1_structured | `MODEL_MAIN` + saída JSON via schema (structured output) |
| a2_reasoning | `MODEL_REASONING` + `reasoning_effort` alto + JSON schema |
| a3_cot | chain-of-thought em texto + JSON final |
| a4_fewshot_fixed | 3 exemplos fixos no prompt |
| a5_fewshot_retrieval | top-k por embeddings (leave-one-out no eval) |
| a6_two_stage | sub-objetivos → JSON |
| a7_self_consistency | N amostras + voto por campo |
| a8_critic_revise | gerar → crítico → rever |
| a9_decomposed_tools | extratores focados + merge |
| a10_reflexion | gerar → reflexão → regenerar (até k iterações) |
| a11_skills_agent | router + skill especializada (ficheiros em `approaches/skills/`) |

## Métricas

Definidas em `eval/metrics.py` (`METRIC_KEYS`). Resumo:

| Métrica | Significado (curto) |
|---------|---------------------|
| `accuracy` | Média de overlap de campos por passo, com matching greedy voo/hotel; normaliza ordem e ignora metadados de passo |
| `flights_acc` / `hotels_acc` | Mesma lógica só sobre passos `quote_flight` / `quote_hotel` |
| `step_count` | Texto `pred/gold` (número de passos) |
| `iata_validity` | Fração de códigos IATA de voo no pred que existem na lista do bench |
| `date_acc` | Entre pares matched, datas alinhadas ao gold |
| `schema_valid` | 1.0 se `validate_plan` passa, 0.0 caso contrário |

## Saídas (`eval/out/`)

| Ficheiro | Conteúdo |
|----------|----------|
| `results.csv` | Uma linha por (approach, item do dataset) com `item_key` e métricas |
| `summary.csv` | Médias por approach — **append** por execução (não apaga runs anteriores); a mesma `approach` pode aparecer em várias linhas (ordem ≈ histórico) |
| `cost.csv` | Por approach: médias nesta run sobre **chamadas novas** — `mean_cost_usd`, `mean_latency_seconds` (cada linha do dataset / `predict()`) |
| `per_request.csv` | Uma linha por chamada real à API: `approach`, `item_key`, `cost_usd`, `latency_seconds`, `spent_cumulative_usd` (total do tracker após essa chamada). Não inclui linhas “resume” sem API. Apagado com `--no-resume` (como `cost.csv`). |
| `{approach}_preds.jsonl` | Predição, gold e diagnóstico por exemplo |

Cruza `summary.csv` com `cost.csv` (coluna `approach`) para ver **acurácia vs custo** ou **vs latência**.

## Notas

- Custo de modelos não listados em `pricing.py` usa `PRICING_FALLBACK` (conservador) no tracker — vê `pricing.py`.
- `REVISAO_EXPERIMENTO.md` descreve limitações do bench (amostra pequena, texto sintético, etc.).

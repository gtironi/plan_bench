"""Turn ground-truth plans into Portuguese natural-language requests.

Usage:
    python3 dataset/generate_texts.py --n 10          # test run
    python3 dataset/generate_texts.py --n 300         # full dataset
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_DATASET

PLANS = os.path.join(os.path.dirname(__file__), "out", "plans.jsonl")
OUT   = os.path.join(os.path.dirname(__file__), "out", "dataset.jsonl")

# ── Styles ────────────────────────────────────────────────────────────────────

STYLES = {

    "detalhado": """Escreva um e-mail corporativo formal em português, bem estruturado e detalhado.
Mencione todos os viajantes pelo nome, todas as cidades com nome completo, e todas as datas no formato "DD de mês de AAAA" (ex: "10 de julho de 2026").
Deixe absolutamente claro o que é ida e o que é volta, qual o hotel e o período de hospedagem.
Tom educado, profissional. Pode ter assunto do e-mail.""",

    "pressado": """Escreva uma mensagem em português como se a pessoa estivesse com pressa e digitando rápido.
Os detalhes estão lá, mas de forma confusa: datas relativas como "vou dia 20 e volto 10 dias depois", cidades mencionadas de passagem, nomes aparecem mas sem muita ordem.
Sem pontuação perfeita, sem parágrafo organizado. Tudo numa tacada só.""",

    "uma_linha": """Escreva em português uma única linha curtíssima, sem pontuação, sem maiúsculas, como um recado deixado no WhatsApp na correria.
Todos os dados devem estar ali mas comprimidos ao máximo. Exemplo de tom: "joao e maria gru jfk dia 10 volta dia 15 hotel tb".""",

    "homem_das_cavernas": """Escreva como um homem das cavernas tentando comunicar uma viagem corporativa em português.
Frases telegráficas, sem verbo às vezes, erros de concordância, palavras primitivas, mas os dados (quem vai, para onde, quando) devem estar presentes.
Exemplo de tom: "João ir cidade grande. 10 lua. trazer Julia. hotel também. voltar depois.".""",

    "com_ruido": """Escreva uma mensagem em português onde a pessoa inclui informações completamente irrelevantes para a viagem além dos dados reais.
Fale sobre o relacionamento entre os viajantes, o departamento deles, que eles são difíceis de agendar, que demoram para responder, que toda vez vira bagunça, que o gestor pediu para resolver logo, etc.
Os dados da viagem devem estar presentes mas misturados com todo esse contexto inútil. Tom de quem está desabafando para o assistente de viagens.""",

}

SYSTEM = """Você é um assistente que escreve solicitações de viagem corporativa realistas em português.
Dado um plano estruturado de viagem, produza uma mensagem no estilo solicitado.

Regras absolutas:
- Escreva APENAS em português (pt-BR).
- NÃO reproduza o JSON. Escreva apenas linguagem natural / bullets.
- Siga o ESTILO descrito com fidelidade.
- Não invente viajantes, cidades ou datas que não estejam no plano.
- Os viajantes estão no plano como t1, t2, t3, etc. Use EXATAMENTE os nomes abaixo para cada id — nunca use o id, sempre o nome:
  t1 = Carlos, t2 = Fernanda, t3 = Rafael, t4 = Juliana, t5 = Marcos,
  t6 = Patrícia, t7 = Bruno, t8 = Larissa, t9 = Diego, t10 = Camila.
- Para datas, use o que estiver no plano — pode reformular o formato mas não altere os valores.
- Se o plano tiver APENAS hotel (nenhum voo): deixe explícito que não precisa de passagem (ex: "só hospedagem", "sem voo", "não precisa de passagem").
- Se o plano tiver APENAS voo (nenhum hotel): deixe explícito que não precisa de hotel (ex: "só a passagem", "sem hotel", "não precisa de hospedagem").
"""


def _load_plans():
    with open(PLANS) as f:
        return [json.loads(l) for l in f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=99)
    args = ap.parse_args()

    random.seed(args.seed)
    plans = _load_plans()
    style_names = list(STYLES.keys())

    # Sample n plans WITH replacement, random order
    sample = [random.choice(plans) for _ in range(args.n)]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    c = client()

    with open(OUT, "a") as fout:
        for i, plan in enumerate(sample):
            style_name = random.choice(style_names)
            style_instruction = STYLES[style_name]
            user_msg = f"ESTILO:\n{style_instruction}\n\nPLANO:\n{json.dumps(plan, ensure_ascii=False, indent=2)}"

            resp = c.chat.completions.create(
                model=MODEL_DATASET,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.95,
            )
            text = resp.choices[0].message.content.strip()

            row = {
                "style": style_name,
                "text":  text,
                "plan":  {k: v for k, v in plan.items() if k != "_id"},
            }
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            fout.flush()
            print(f"[{i+1}/{args.n}] style={style_name}  plan={plan.get('_id','?')} ✓")

    print(f"\nwrote {args.n} rows -> {OUT}")


if __name__ == "__main__":
    main()

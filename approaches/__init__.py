"""All approaches, registered by short name."""
from approaches import (
    a1_structured, a2_reasoning, a3_cot, a4_fewshot_fixed,
    a5_fewshot_retrieval, a6_two_stage, a7_self_consistency,
    a8_critic_revise, a9_decomposed_tools, a10_reflexion, a11_skills_agent,
)

ALL = [
    a1_structured.approach,
    a2_reasoning.approach,
    a3_cot.approach,
    a4_fewshot_fixed.approach,
    a5_fewshot_retrieval.approach,  # may be None if index not built
    a6_two_stage.approach,
    a7_self_consistency.approach,
    a8_critic_revise.approach,
    a9_decomposed_tools.approach,
    a10_reflexion.approach,
    a11_skills_agent.approach,
]

ALL = [a for a in ALL if a is not None]
BY_NAME = {a.name: a for a in ALL}

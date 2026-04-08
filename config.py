"""Load OPENAI_API_KEY from the Noma env_config.py (plain python assignments)."""
import os
import re

NOMA_ENV = "/home/gustavo/codigos/noma/noma_backend_local/system/env_config.py"


def _load_key():
    with open(NOMA_ENV) as f:
        src = f.read()
    m = re.search(r"OPENAI_API_KEY\s*=\s*'([^']+)'", src)
    assert m, "OPENAI_API_KEY not found in env_config.py"
    return m.group(1)


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _load_key()

# Models — tweak in one place.
MODEL_DATASET = "gpt-3.5-turbo"
MODEL_MAIN = "gpt-4.1"
MODEL_REASONING = "o3"
MODEL_EMBED = "text-embedding-3-small"


def client():
    from openai import OpenAI
    from tracker import wrap_client
    return wrap_client(OpenAI(api_key=OPENAI_API_KEY))

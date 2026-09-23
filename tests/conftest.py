"""Suite-wide guards.

No test may reach a model provider. The live intake client builds its
openai.OpenAI() lazily, so replacing that class here turns any accidental
live call into an immediate, named failure instead of a slow, billed,
non-deterministic one. Tests that exercise the live client pass it a fake.
"""

import pytest


class _LiveCallBlocked:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "a test tried to build a live OpenAI client; pass a CassetteClient or a fake"
        )


@pytest.fixture(autouse=True)
def _no_live_model_calls(monkeypatch):
    import openai

    monkeypatch.setattr(openai, "OpenAI", _LiveCallBlocked)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("REGUIDE_INTAKE_MODEL", raising=False)

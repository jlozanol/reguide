"""The extraction call, live or replayed.

Two clients share one interface, complete(source_text) -> dict:

- OpenAIIntake calls the OpenAI Responses API. gpt-6-sol by default,
  reasoning switched off and temperature 0 (GPT-6 Sol and Luna accept a
  temperature only with reasoning effort "none"), with Structured Outputs in
  strict mode so the reply is JSON in the schema intake_fields.schema()
  defines. store=False: a founder's description is not kept by the provider.
- CassetteClient replays recorded replies from JSON files and never touches
  the network. The test suite uses only this.

Temperature 0 makes the live call steadier, not repeatable. Cassettes are what
make the suite deterministic, and a cassette is keyed by a hash of the whole
request (model, instructions, schema, input text), so editing the prompt or
the schema invalidates every recording and the suite says so instead of
replaying a stale answer.

The key is read from OPENAI_API_KEY, loaded from .env. REGUIDE_INTAKE_MODEL
overrides the model.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

from .intake_fields import INSTRUCTIONS, schema

DEFAULT_MODEL = "gpt-6-sol"
MODEL_ENV = "REGUIDE_INTAKE_MODEL"
SCHEMA_NAME = "intake_claims"
MAX_OUTPUT_TOKENS = 16_000

ROOT = Path(__file__).resolve().parent.parent
CASSETTE_DIR = ROOT / "tests" / "intake_cassettes"
RECORD_HINT = "uv run python scripts/record_intake.py"


class IntakeError(RuntimeError):
    """The model did not return a usable reply."""


class CassetteMissing(LookupError):
    """No recording matches this exact request."""


class IntakeClient(Protocol):
    model: str

    def complete(self, source_text: str) -> dict[str, Any]: ...


def configured_model() -> str:
    return os.environ.get(MODEL_ENV) or DEFAULT_MODEL


def request_body(model: str, source_text: str) -> dict[str, Any]:
    """Everything sent to the Responses API, in one place.

    Tests pin this: temperature 0, reasoning off, strict schema, not stored.
    """
    return {
        "model": model,
        "instructions": INSTRUCTIONS,
        "input": source_text,
        "reasoning": {"effort": "none"},
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "schema": schema(),
                "strict": True,
            }
        },
    }


def request_key(model: str, source_text: str) -> str:
    """A hash of the whole request. Any change to it is a different request."""
    payload = json.dumps(request_body(model, source_text), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_reply(response: Any) -> dict[str, Any]:
    """The JSON object from a Responses API reply, or IntakeError."""
    status = getattr(response, "status", None)
    if status not in (None, "completed"):
        details = getattr(response, "incomplete_details", None)
        raise IntakeError(f"response status {status}: {details}")
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "refusal":
                raise IntakeError(f"the model refused: {getattr(content, 'refusal', '')}")
    text = getattr(response, "output_text", "") or ""
    if not text.strip():
        raise IntakeError("the model returned no text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise IntakeError(f"the reply is not JSON: {error}") from error
    if not isinstance(data, dict):
        raise IntakeError("the reply is not a JSON object")
    return data


class OpenAIIntake:
    """The live client. Only scripts/record_intake.py and real use construct it."""

    def __init__(self, model: str | None = None, client: Any = None):
        self.model = model or configured_model()
        if client is None:
            from dotenv import load_dotenv

            load_dotenv()
            import openai

            client = openai.OpenAI()
        self._client = client

    def complete(self, source_text: str) -> dict[str, Any]:
        response = self._client.responses.create(**request_body(self.model, source_text))
        return parse_reply(response)


class CassetteClient:
    """Replays recorded replies. Never calls the network.

    One JSON file per recording, named for the case it records (a fixture
    slug), holding the request key, the model, the input text and the reply.
    Lookup is by key, so the file name is only for people reading the folder.
    """

    def __init__(self, directory: Path = CASSETTE_DIR, model: str = DEFAULT_MODEL):
        self.model = model
        self.directory = Path(directory)
        self._by_key: dict[str, dict[str, Any]] = {}
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.json")):
                entry = json.loads(path.read_text())
                self._by_key[entry["key"]] = entry

    def __len__(self) -> int:
        return len(self._by_key)

    def complete(self, source_text: str) -> dict[str, Any]:
        key = request_key(self.model, source_text)
        entry = self._by_key.get(key)
        if entry is None:
            raise CassetteMissing(
                f"no recorded reply for this input with the current instructions, "
                f"schema and model {self.model}. Re-record with: {RECORD_HINT}"
            )
        return entry["output"]

    def record(self, name: str, source_text: str, output: dict[str, Any]) -> Path:
        """Write one recording. Used by the record script and by tests."""
        self.directory.mkdir(parents=True, exist_ok=True)
        key = request_key(self.model, source_text)
        entry = {"key": key, "model": self.model, "input": source_text, "output": output}
        path = self.directory / f"{name}.json"
        path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
        self._by_key[key] = entry
        return path

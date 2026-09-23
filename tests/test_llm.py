"""The extraction call: what is sent, how the reply is read, how it is replayed.

Nothing here reaches the network. The live client is exercised with a fake
openai client object; conftest.py makes building a real one fail.
"""

import json
from types import SimpleNamespace

import pytest

from reguide import intake_fields as F
from reguide import llm as L

TEXT = "A sterile adhesive dressing strip for minor cuts."


class FakeResponses:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


def fake_openai(reply):
    return SimpleNamespace(responses=FakeResponses(reply))


def reply(text, status="completed", output=None):
    return SimpleNamespace(status=status, output_text=text, output=output or [],
                           incomplete_details=None)


GOOD = {"functions": [], "claims": []}


class TestRequestBody:
    def test_temperature_is_zero_and_reasoning_is_off(self):
        body = L.request_body("gpt-6-sol", TEXT)
        assert body["temperature"] == 0
        assert body["reasoning"] == {"effort": "none"}

    def test_the_output_is_strict_json_in_our_schema(self):
        fmt = L.request_body("gpt-6-sol", TEXT)["text"]["format"]
        assert fmt["type"] == "json_schema"
        assert fmt["strict"] is True
        assert fmt["schema"] == F.schema()

    def test_the_description_is_not_stored_by_the_provider(self):
        assert L.request_body("gpt-6-sol", TEXT)["store"] is False

    def test_the_text_goes_in_as_input_and_the_rules_as_instructions(self):
        body = L.request_body("gpt-6-sol", TEXT)
        assert body["input"] == TEXT
        assert body["instructions"] == F.INSTRUCTIONS

    def test_no_sampling_parameter_that_reasoning_models_reject(self):
        assert "top_p" not in L.request_body("gpt-6-sol", TEXT)


class TestModelChoice:
    def test_the_default_is_gpt_6_sol(self):
        assert L.DEFAULT_MODEL == "gpt-6-sol"
        assert L.configured_model() == "gpt-6-sol"

    def test_the_environment_can_override_it(self, monkeypatch):
        monkeypatch.setenv(L.MODEL_ENV, "gpt-6-luna")
        assert L.configured_model() == "gpt-6-luna"

    def test_an_empty_override_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv(L.MODEL_ENV, "")
        assert L.configured_model() == "gpt-6-sol"


class TestStrictSchema:
    """Strict mode rejects a schema with optional or open-ended objects."""

    @staticmethod
    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for value in node.values():
                yield from TestStrictSchema.objects(value)
        elif isinstance(node, list):
            for value in node:
                yield from TestStrictSchema.objects(value)

    def test_every_object_is_closed_and_fully_required(self):
        for node in self.objects(F.schema()):
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])

    def test_the_target_enum_is_exactly_the_extractable_fields(self):
        claim = F.schema()["properties"]["claims"]["items"]
        assert set(claim["properties"]["target"]["enum"]) == set(F.EXTRACTABLE)

    def test_no_ask_only_field_can_be_named(self):
        claim = F.schema()["properties"]["claims"]["items"]
        assert not set(claim["properties"]["target"]["enum"]) & set(F.ASK_ONLY)


class TestLiveClient:
    def test_it_sends_the_request_body_and_returns_the_json(self):
        client = fake_openai(reply(json.dumps(GOOD)))
        intake = L.OpenAIIntake(client=client)
        assert intake.complete(TEXT) == GOOD
        [sent] = client.responses.calls
        assert sent == L.request_body("gpt-6-sol", TEXT)

    def test_it_uses_the_configured_model(self, monkeypatch):
        monkeypatch.setenv(L.MODEL_ENV, "gpt-6-luna")
        client = fake_openai(reply(json.dumps(GOOD)))
        L.OpenAIIntake(client=client).complete(TEXT)
        assert client.responses.calls[0]["model"] == "gpt-6-luna"

    def test_an_incomplete_reply_is_an_error(self):
        client = fake_openai(reply('{"functions": [', status="incomplete"))
        with pytest.raises(L.IntakeError, match="incomplete"):
            L.OpenAIIntake(client=client).complete(TEXT)

    def test_a_refusal_is_an_error(self):
        refusal = SimpleNamespace(type="refusal", refusal="cannot help")
        message = SimpleNamespace(type="message", content=[refusal])
        client = fake_openai(reply("", output=[message]))
        with pytest.raises(L.IntakeError, match="refused"):
            L.OpenAIIntake(client=client).complete(TEXT)

    @pytest.mark.parametrize("text", ["", "   ", "not json", "[1, 2]"])
    def test_an_unusable_reply_is_an_error(self, text):
        with pytest.raises(L.IntakeError):
            L.OpenAIIntake(client=fake_openai(reply(text))).complete(TEXT)

    def test_building_a_real_client_inside_the_suite_fails_loudly(self):
        with pytest.raises(RuntimeError, match="live OpenAI client"):
            L.OpenAIIntake()


class TestCassettes:
    def test_a_recording_replays(self, tmp_path):
        recorder = L.CassetteClient(tmp_path)
        recorder.record("dressing", TEXT, GOOD)
        assert L.CassetteClient(tmp_path).complete(TEXT) == GOOD

    def test_the_file_is_named_for_the_case_and_carries_the_key(self, tmp_path):
        path = L.CassetteClient(tmp_path).record("dressing", TEXT, GOOD)
        assert path.name == "dressing.json"
        saved = json.loads(path.read_text())
        assert saved["key"] == L.request_key("gpt-6-sol", TEXT)
        assert saved["input"] == TEXT
        assert saved["model"] == "gpt-6-sol"

    def test_a_different_input_is_not_replayed(self, tmp_path):
        L.CassetteClient(tmp_path).record("dressing", TEXT, GOOD)
        with pytest.raises(L.CassetteMissing, match="record_intake"):
            L.CassetteClient(tmp_path).complete(TEXT + " ")

    def test_a_different_model_is_not_replayed(self, tmp_path):
        L.CassetteClient(tmp_path).record("dressing", TEXT, GOOD)
        with pytest.raises(L.CassetteMissing):
            L.CassetteClient(tmp_path, model="gpt-6-luna").complete(TEXT)

    def test_changing_the_instructions_invalidates_the_recording(self, tmp_path, monkeypatch):
        L.CassetteClient(tmp_path).record("dressing", TEXT, GOOD)
        monkeypatch.setattr(L, "INSTRUCTIONS", F.INSTRUCTIONS + "\nOne more rule.")
        with pytest.raises(L.CassetteMissing):
            L.CassetteClient(tmp_path).complete(TEXT)

    def test_an_empty_folder_replays_nothing(self, tmp_path):
        client = L.CassetteClient(tmp_path / "absent")
        assert len(client) == 0
        with pytest.raises(L.CassetteMissing):
            client.complete(TEXT)

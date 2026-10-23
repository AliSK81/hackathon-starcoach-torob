import io
import json
from dataclasses import replace

from starcoach import llm
from starcoach.config import get_settings


def _sent_body(monkeypatch, tmp_path, model):
    sent = {}

    def fake_urlopen(req, timeout=0):
        sent.update(json.loads(req.data))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    s = replace(get_settings(), log_dir=tmp_path, llm_base_url="http://llm.invalid", llm_api_key="k", llm_model=model)
    llm.chat(s, [{"role": "user", "content": "x"}], max_tokens=123)
    return sent


def test_qwen_gets_vllm_fields(monkeypatch, tmp_path):
    body = _sent_body(monkeypatch, tmp_path, "mohaymen/qwen3.8-27b")
    assert body["max_tokens"] == 123 and body["chat_template_kwargs"] == {"enable_thinking": False}


def test_gpt5_gets_openai_fields_only(monkeypatch, tmp_path):
    body = _sent_body(monkeypatch, tmp_path, "openai/gpt-5-mini")
    assert body["max_completion_tokens"] == 123 and body["reasoning_effort"] == "minimal"
    assert not {"max_tokens", "temperature", "chat_template_kwargs"} & body.keys()

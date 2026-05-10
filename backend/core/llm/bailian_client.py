from core.llm._base_http_client import _BaseHTTPLLMClient


class BailianLLMClient(_BaseHTTPLLMClient):
    _endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def _thinking_off_params(self) -> dict:
        return {"enable_thinking": False}

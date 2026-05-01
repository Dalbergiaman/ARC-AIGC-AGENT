from core.llm._base_http_client import _BaseHTTPLLMClient


class BailianLLMClient(_BaseHTTPLLMClient):
    _endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

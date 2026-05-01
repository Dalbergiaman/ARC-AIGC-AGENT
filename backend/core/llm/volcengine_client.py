from core.llm._base_http_client import _BaseHTTPLLMClient


class VolcengineLLMClient(_BaseHTTPLLMClient):
    _endpoint = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

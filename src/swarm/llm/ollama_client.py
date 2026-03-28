import aiohttp
import json
from typing import AsyncIterator, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "llama3.3:70b"
    timeout_seconds: int = 120
    keep_alive: str = "5m"


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        num_ctx: int = 8192,
        tools: list[dict] | None = None,
        stream: bool = True,
    ) -> str | AsyncIterator[str]:
        session = await self._get_session()
        model = model or self.config.model

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
            },
            "keep_alive": self.config.keep_alive,
        }

        if system:
            payload["system"] = system

        if tools:
            payload["tools"] = tools

        try:
            async with session.post(
                f"{self.config.base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()

                if stream:
                    return self._stream_response(response)
                else:
                    data = await response.json()
                    return data.get("response", "")

        except aiohttp.ClientError as e:
            logger.error("ollama_generate_error", error=str(e), model=model)
            raise

    async def _stream_response(self, response: aiohttp.ClientResponse) -> AsyncIterator[str]:
        async for line in response.content:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "response" in data:
                    yield data["response"]
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        num_ctx: int = 8192,
        tools: list[dict] | None = None,
        stream: bool = True,
    ) -> str | AsyncIterator[str]:
        session = await self._get_session()
        model = model or self.config.model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
            },
            "keep_alive": self.config.keep_alive,
        }

        if tools:
            payload["tools"] = tools

        try:
            async with session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()

                if stream:
                    return self._stream_chat_response(response)
                else:
                    data = await response.json()
                    return data.get("message", {}).get("content", "")

        except aiohttp.ClientError as e:
            logger.error("ollama_chat_error", error=str(e), model=model)
            raise

    async def _stream_chat_response(self, response: aiohttp.ClientResponse) -> AsyncIterator[str]:
        async for line in response.content:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    yield data["message"]["content"]
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    async def embed(self, text: str, model: str = "nomic-embed-text:latest") -> list[float]:
        session = await self._get_session()

        payload = {
            "model": model,
            "input": text,
        }

        try:
            async with session.post(
                f"{self.config.base_url}/api/embeddings",
                json=payload,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("embedding", [])

        except aiohttp.ClientError as e:
            logger.error("ollama_embed_error", error=str(e))
            raise

    async def embed_batch(self, texts: list[str], model: str = "nomic-embed-text:latest") -> list[list[float]]:
        session = await self._get_session()

        payload = {
            "model": model,
            "input": texts,
        }

        try:
            async with session.post(
                f"{self.config.base_url}/api/embeddings",
                json=payload,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("embeddings", [])

        except aiohttp.ClientError as e:
            logger.error("ollama_embed_batch_error", error=str(e))
            raise

    async def list_models(self) -> list[dict[str, Any]]:
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.config.base_url}/api/tags"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("models", [])

        except aiohttp.ClientError as e:
            logger.error("ollama_list_models_error", error=str(e))
            raise

    async def is_healthy(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.base_url}/") as response:
                return response.status == 200
        except Exception:
            return False

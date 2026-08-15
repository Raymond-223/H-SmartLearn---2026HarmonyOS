"""Minimal server-side OpenAI Responses API provider.

The provider is optional. API credentials are read only from backend settings;
HarmonyOS clients never receive or submit provider keys.
"""

import json
from typing import Any

import httpx


class OpenAIResponsesProvider:
    def __init__(self, *, api_key: str, model: str, base_url: str = "") -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for the OpenAI provider")
        if not model:
            raise ValueError("LLM_MODEL is required for the OpenAI provider")
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    async def generate_json(self, *, instructions: str, prompt: str) -> dict[str, Any]:
        request_body = {
            "model": self.model,
            "instructions": instructions,
            "input": prompt,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()

        text = payload.get("output_text") or self._extract_output_text(payload)
        if not text:
            raise ValueError("model response did not contain output text")
        return self._parse_json(text)

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    chunks.append(str(content["text"]))
        return "\n".join(chunks)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("model output must be a JSON object")
        return parsed

    async def embed(
        self, texts: list[str], model: str = "text-embedding-3-small"
    ) -> list[list[float]] | None:
        """Generate embeddings via OpenAI-compatible /embeddings endpoint."""
        if not texts:
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        request_body = {
            "model": model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data", [])
        if not data:
            return None
        data.sort(key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in data]

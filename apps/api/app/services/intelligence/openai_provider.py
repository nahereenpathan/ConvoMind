"""OpenAI LLM provider generating structured meeting intelligence via JSON Schema / Structured Outputs."""

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.intelligence.base import (
    LLMPermanentError,
    LLMProvider,
    LLMTransientError,
)
from app.services.intelligence.prompts import SYSTEM_PROMPT, build_transcript_prompt
from app.services.intelligence.schemas import MeetingIntelligenceOutput

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Production LLM provider communicating with OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.default_model = model or settings.OPENAI_MODEL or "gpt-4o-mini"
        self.timeout = timeout or float(settings.LLM_TIMEOUT_SECONDS)
        self.api_url = "https://api.openai.com/v1/chat/completions"

    async def generate_meeting_intelligence(
        self,
        transcript_text: str,
        segments: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> MeetingIntelligenceOutput:
        """Execute chat completion request and validate structured response."""
        if not self.api_key:
            raise LLMPermanentError("OPENAI_API_KEY is not configured in environment.")

        model_id = model_name or self.default_model
        sys_instructions = system_prompt or SYSTEM_PROMPT
        user_content = build_transcript_prompt(transcript_text, segments)

        # JSON schema representation for structured outputs
        json_schema = MeetingIntelligenceOutput.model_json_schema()

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": sys_instructions},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "meeting_intelligence_response",
                    "strict": True,
                    "schema": json_schema,
                },
            },
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)

            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMTransientError(
                    f"OpenAI API rate limit or service error ({resp.status_code}): {resp.text[:300]}"
                )
            elif resp.status_code != 200:
                raise LLMPermanentError(
                    f"OpenAI API rejected request ({resp.status_code}): {resp.text[:300]}"
                )

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMPermanentError("Empty completion choices returned from OpenAI.")

            raw_content = choices[0].get("message", {}).get("content", "")
            if not raw_content:
                raise LLMPermanentError("Null completion content returned from OpenAI.")

            # Validate against Pydantic output model
            parsed_output = MeetingIntelligenceOutput.model_validate_json(raw_content)

            # Attach provider metadata & token usage
            usage = data.get("usage", {})
            parsed_output.token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
            parsed_output.model_used = model_id
            parsed_output.provider = "openai"

            return parsed_output

        except httpx.TimeoutException as timeout_err:
            raise LLMTransientError(f"OpenAI API request timed out: {timeout_err}")
        except httpx.NetworkError as net_err:
            raise LLMTransientError(f"OpenAI API network connectivity failure: {net_err}")
        except (json.JSONDecodeError, ValueError) as val_err:
            raise LLMPermanentError(f"Failed to parse and validate OpenAI structured output: {val_err}")

    async def generate_chat_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion request against OpenAI API."""
        if not self.api_key:
            raise LLMPermanentError("OPENAI_API_KEY is not configured.")

        model_id = model_name or self.default_model
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE

        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(messages)

        payload = {
            "model": model_id,
            "messages": payload_messages,
            "temperature": temp,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if resp.status_code in (429, 500, 502, 503, 504):
                raise LLMTransientError(f"OpenAI API error ({resp.status_code}): {resp.text[:300]}")
            elif resp.status_code != 200:
                raise LLMPermanentError(f"OpenAI API error ({resp.status_code}): {resp.text[:300]}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMPermanentError("Empty completion choices returned from OpenAI.")

            raw_content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return {
                "answer": raw_content,
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "model_used": model_id,
                "provider": "openai",
            }
        except httpx.TimeoutException as timeout_err:
            raise LLMTransientError(f"OpenAI API timeout: {timeout_err}")
        except httpx.RequestError as req_err:
            raise LLMTransientError(f"OpenAI network error: {req_err}")

    async def generate_structured_json(
        self,
        prompt: str,
        response_schema: Any,
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """Generate structured output validated against a Pydantic model using OpenAI response_format."""
        if not self.api_key:
            raise LLMPermanentError("OPENAI_API_KEY is not configured in environment.")

        model_id = model_name or self.default_model
        sys_instructions = system_prompt or "You are an AI assistant that outputs structured JSON conforming to the requested schema."

        json_schema = response_schema.model_json_schema()
        schema_name = getattr(response_schema, "__name__", "structured_output")

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": sys_instructions},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name.lower(),
                    "strict": True,
                    "schema": json_schema,
                },
            },
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.api_url, json=payload, headers=headers)

            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMTransientError(f"OpenAI rate limit / error ({resp.status_code}): {resp.text[:300]}")
            elif resp.status_code != 200:
                raise LLMPermanentError(f"OpenAI API error ({resp.status_code}): {resp.text[:300]}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMPermanentError("Empty completion choices returned from OpenAI.")

            raw_content = choices[0].get("message", {}).get("content", "")
            if not raw_content:
                raise LLMPermanentError("Null completion content returned from OpenAI.")

            return response_schema.model_validate_json(raw_content)

        except (httpx.TimeoutException, httpx.NetworkError) as err:
            raise LLMTransientError(f"OpenAI request network error: {err}")
        except (json.JSONDecodeError, ValueError) as val_err:
            raise LLMPermanentError(f"Failed to parse structured output: {val_err}")



from google import genai
from google.genai import types

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    AI_MAX_OUTPUT_TOKENS,
)

class GeminiRequestError(RuntimeError):
    """Raised when the Gemini API request itself fails."""

class GeminiProvider:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured.")

        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

        self.model = GEMINI_MODEL


   
    
    def generate(self, prompt: str) -> dict:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        # Step 1: Send exactly one Gemini API request.
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=AI_MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                ),
            )
        except Exception as exc:
            print(
                f"Gemini API error: {type(exc).__name__}: {exc}"
            )
            raise GeminiRequestError(
                "Gemini API request failed."
            ) from exc

        # Step 2: Read response usage metadata.
        usage = response.usage_metadata

        if usage is None:
            raise RuntimeError(
                "Gemini response did not include token usage metadata."
            )

        input_tokens = usage.prompt_token_count
        candidate_tokens = usage.candidates_token_count
        thoughts_tokens = usage.thoughts_token_count or 0
        tool_tokens = usage.tool_use_prompt_token_count or 0

        counts = (
            input_tokens,
            candidate_tokens,
            thoughts_tokens,
            tool_tokens,
        )

        if any(count is None or count < 0 for count in counts):
            raise RuntimeError(
                "Gemini returned missing or invalid token counts."
            )

        output_tokens = candidate_tokens + thoughts_tokens

        if output_tokens > AI_MAX_OUTPUT_TOKENS:
            raise RuntimeError(
                "Gemini usage exceeded the configured output budget."
            )

        total_tokens = input_tokens + output_tokens

        # Step 3: Inspect Gemini's finish reason.
        candidates = response.candidates or []

        finish_reason = (
            candidates[0].finish_reason
            if candidates else None
        )

        finish_reason_name = (
            getattr(finish_reason, "name", None)
            or str(finish_reason or "UNKNOWN")
        )

        # Conservatively accept only a normal STOP as complete.
        is_complete = finish_reason_name.upper().rsplit(".", 1)[-1] == "STOP"
        # Step 4: Return content and usage, even when truncated.
        return {
            "content": response.text or "",
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "finish_reason": finish_reason_name,
            "is_complete": is_complete,
        }

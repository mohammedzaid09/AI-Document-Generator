from google import genai
from google.genai import types

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    AI_MAX_OUTPUT_TOKENS,
)

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

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=AI_MAX_OUTPUT_TOKENS,
                temperature=0.2,
            ),
        )

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

        if any(
            count is None or count < 0
            for count in counts
        ):
            raise RuntimeError(
                "Gemini returned missing or invalid token counts."
            )

        # Count candidate output and thinking tokens.
        output_tokens = candidate_tokens + thoughts_tokens

        if output_tokens > AI_MAX_OUTPUT_TOKENS:
            raise RuntimeError(
                "Gemini usage exceeded the configured output budget."
            )

        total_tokens = input_tokens + output_tokens

        return {
            "content": response.text or "",
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

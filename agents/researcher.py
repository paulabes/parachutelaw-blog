"""The Scout — Gemini-powered UK legal researcher."""

import os
from pathlib import Path

from google import genai
from google.genai import types


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "research_dna.md"


def research(topic: str) -> str:
    """Run Gemini research for *topic* and return a structured brief."""
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Research the following UK family law topic for a March 2026 blog post: {topic}",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )
    return response.text

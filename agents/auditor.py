"""The Critic — Gemini-powered legal compliance auditor."""

import os

from google import genai
from google.genai import types


AUDIT_INSTRUCTION = (
    "You are a UK Legal Compliance Officer. Your job is to compare a draft blog "
    "post against its source research brief. Flag any:\n"
    "- Hallucinated statutes, practice directions, or case law\n"
    "- Incorrect statistics or dates\n"
    "- Misleading legal claims\n"
    "- Statements that could constitute unregulated legal advice\n\n"
    "Return a short audit report: PASS or FAIL, followed by bullet-pointed notes."
)


def audit(research_brief: str, draft: str) -> str:
    """Audit *draft* against *research_brief* and return a compliance report."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            "Compare the following DRAFT against the RESEARCH BRIEF. "
            "Flag any hallucinated laws, incorrect numbers, or misleading claims.\n\n"
            f"--- RESEARCH BRIEF ---\n{research_brief}\n\n"
            f"--- DRAFT ---\n{draft}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=AUDIT_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=1024,
        ),
    )
    return response.text

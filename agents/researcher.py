"""The Scout — Gemini-powered UK legal researcher with Google Search grounding."""

import os
from pathlib import Path

from google import genai
from google.genai import types


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "research_dna.md"

ORIGINAL_PROMPT = (
    "Research the following UK legal topic for a March 2026 blog post: {topic}\n\n"
    "Focus on gathering accurate, current UK legal data, statistics, and legislation "
    "relevant to this topic. Do NOT look for competitor articles."
)

OUTRANK_PROMPT = (
    "Research the following UK legal topic for a March 2026 blog post: {topic}\n\n"
    "STEP 1: Search Google for this topic exactly as a regular person in the UK would "
    "(e.g. '{topic} UK', '{topic} guide', '{topic} explained'). Look at ALL the top "
    "results — law firm blogs, legal advice sites like Citizens Advice, news articles, "
    "specialist publishers, personal finance sites, any type of website. Do NOT only "
    "look at .gov.uk sites. Find the single highest-ranking, most comprehensive "
    "competitor article from ANY source. Record its URL, title, site name, date, "
    "and a summary of its angle in a [TARGET_ARTICLE] block.\n\n"
    "STEP 2: Build a comprehensive research brief with verified UK legal data, "
    "statistics, and legislation so we can write a BETTER article than the target."
)


def research(topic: str, mode: str = "original") -> str:
    """Run Gemini research for *topic* with live Google Search and return a structured brief."""
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    prompt_template = OUTRANK_PROMPT if mode == "outrank" else ORIGINAL_PROMPT
    user_prompt = prompt_template.format(topic=topic)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=4096,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    brief = response.text

    # Extract grounded source URLs from search metadata (skip Google/Vertex internal links)
    skip_domains = ["vertexaisearch.cloud.google.com", "googleapis.com", "cloud.google.com"]
    sources = []
    if response.candidates and response.candidates[0].grounding_metadata:
        metadata = response.candidates[0].grounding_metadata
        if metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if chunk.web and chunk.web.uri:
                    if any(d in chunk.web.uri for d in skip_domains):
                        continue
                    title = chunk.web.title or chunk.web.uri
                    sources.append(f"- [{title}]({chunk.web.uri})")

    if sources:
        brief += "\n\n[SOURCES]\n" + "\n".join(sources)

    return brief

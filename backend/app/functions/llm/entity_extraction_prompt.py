# /backend/app/functions/llm/entity_extraction_prompt.py

def get_local_entity_prompt(transcript: str) -> str:
    """
    Generates a super-strict prompt for extracting ONLY local entities.
    """
    return f"""You are an information extraction machine. Your only function is to extract locations.
Your entire response must be a single JSON object and nothing else.

Rules:
- Extract ONLY locations explicitly mentioned in the transcript (e.g., villages, towns, forests, lakes, buildings).
- Do NOT extract any other information.
- Do NOT explain your reasoning.
- Your response must begin with `{{` and end with `}}`.

Transcript:
---
{transcript}
---

Return a JSON object with a single key "local_entities" containing a list of strings.

Example:
{{
  "local_entities": ["Willow Village", "Crystal Lake"]
}}

Output:
"""

def get_temporal_entity_prompt(transcript: str) -> str:
    """
    Generates a super-strict prompt for extracting ONLY temporal entities.
    """
    return f"""You are an information extraction machine. Your only function is to extract time expressions.
Your entire response must be a single JSON object and nothing else.

Rules:
- Extract ONLY explicit time expressions and durations (e.g., "early this morning", "in two days", "at sunset").
- Do NOT extract any other information.
- Do NOT explain your reasoning.
- Your response must begin with `{{` and end with `}}`.

Transcript:
---
{transcript}
---

Return a JSON object with a single key "temporal_entities" containing a list of strings.

Example:
{{
  "temporal_entities": ["Early this morning", "one hour later"]
}}

Output:
"""
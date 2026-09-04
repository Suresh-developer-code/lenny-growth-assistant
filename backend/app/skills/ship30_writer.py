"""Ship 30 for 30–style essay generation skill.

Encodes the framework's structural rules as an explicit, reusable prompt
template (per the assignment's requirement to encode the rules in a skill,
not rely on an unstructured one-off prompt):
  - hook in the first 2-3 lines
  - ~1,250 words
  - skimmable formatting: short paragraphs, H2/H3 headers, bold anchors
  - claims grounded in the transcript knowledge base
  - a concrete, actionable takeaway at the end
"""
from typing import Any

from app.rag.retriever import TranscriptRetriever

SHIP30_TARGET_WORDS = 1250

SHIP30_SYSTEM_PROMPT = """You are an expert ghostwriter trained in the Ship 30 for 30 methodology, \
writing for the Lenny Growth Assistant. Transform the source transcript excerpts and the user's \
request into a single, high-retention essay artifact.

Structural requirements (non-negotiable):
1. Target length: approximately {target_words} words (1,100-1,400 is acceptable).
2. The Hook: the first 2-3 lines must present a counterintuitive product/growth truth, a specific \
outcome promise, or an urgent tension — never a throat-clearing introduction like "In this essay...".
3. Narrative progression: the piece should move from problem/tension -> insight -> concrete mechanism \
-> payoff, not just be a list of tips with no throughline.
4. Formatting for skimmability:
   - Markdown H2 (##) and H3 (###) section headers.
   - Short paragraphs: 1-3 sentences each.
   - Bulleted lists where you're enumerating tactics, with **bold anchor phrases** at the start of \
each bullet.
5. Grounded substance: every specific claim, number, or tactic must come from the transcript excerpts \
below and be attributed to the guest/episode it came from. Do not invent tactics or statistics.
6. Close with a specific, useful takeaway: a named framework, a checklist, or a step-by-step \
implementation plan the reader can apply this week.
7. Output ONLY the essay in Markdown — no meta-commentary about what you're about to write.

Transcript excerpts:
{context}

User's essay request:
{user_query}
"""


def build_ship30_prompt(user_query: str, retrieved_chunks: list[dict[str, Any]]) -> str:
    context = TranscriptRetriever.format_context(retrieved_chunks)
    if not context:
        context = "(No excerpts cleared the relevance threshold — inform the user there isn't enough grounded material for this essay rather than writing one anyway.)"
    return SHIP30_SYSTEM_PROMPT.format(
        target_words=SHIP30_TARGET_WORDS,
        context=context,
        user_query=user_query,
    )

"""Unit tests for retrieval formatting and the grounded/ship30 prompt builders.

These tests exercise pure functions (no live DB call) so they run
everywhere, and they encode the anti-hallucination contract described in
the PRD: an empty retrieval result must lead to an explicit
"insufficient context" instruction, never a silently-empty context block
that lets the model guess.
"""
from app.rag.retriever import TranscriptRetriever
from app.skills.grounded_qa import NO_CONTEXT_PHRASE, build_grounded_prompt, chunks_to_sources
from app.skills.ship30_writer import SHIP30_TARGET_WORDS, build_ship30_prompt

SAMPLE_CHUNKS = [
    {
        "episode": "Growth Loops Over Funnels",
        "guest": "Casey Winters",
        "text": "Casey explained why loops outperform funnels for compounding growth.",
        "timestamp": "18:42",
        "source_url": "https://example.com/casey",
        "score": 0.83,
    },
    {
        "episode": "Pricing as a Growth Lever in PLG",
        "guest": "Elena Verna",
        "text": "Elena argued usage-based pricing removes seat-counting friction.",
        "timestamp": "31:20",
        "source_url": "https://example.com/elena",
        "score": 0.77,
    },
]


def test_format_context_includes_episode_and_guest():
    context = TranscriptRetriever.format_context(SAMPLE_CHUNKS)
    assert "Growth Loops Over Funnels" in context
    assert "Casey Winters" in context
    assert "18:42" in context
    assert "Elena Verna" in context


def test_format_context_empty_when_no_chunks():
    assert TranscriptRetriever.format_context([]) == ""


def test_grounded_prompt_includes_context_and_citation_rule():
    prompt = build_grounded_prompt(SAMPLE_CHUNKS)
    assert "Casey Winters" in prompt
    assert "cite" in prompt.lower()
    assert NO_CONTEXT_PHRASE in prompt


def test_grounded_prompt_with_no_chunks_still_instructs_refusal():
    """This is the core anti-hallucination guarantee: even with zero
    retrieved chunks, the system prompt must still contain the refusal
    phrase, so the model has an explicit instruction to say it doesn't know
    rather than fill the gap from parametric knowledge.
    """
    prompt = build_grounded_prompt([])
    assert NO_CONTEXT_PHRASE in prompt
    assert "did not clear" in prompt.lower() or "no excerpts" in prompt.lower()


def test_chunks_to_sources_shape():
    sources = chunks_to_sources(SAMPLE_CHUNKS)
    assert len(sources) == 2
    assert sources[0]["episode"] == "Growth Loops Over Funnels"
    assert sources[0]["guest"] == "Casey Winters"
    assert isinstance(sources[0]["score"], float)


def test_ship30_prompt_targets_correct_word_count_and_structure():
    prompt = build_ship30_prompt("Write about growth loops", SAMPLE_CHUNKS)
    assert str(SHIP30_TARGET_WORDS) in prompt
    assert "hook" in prompt.lower()
    assert "##" in prompt  # instructs markdown headers
    assert "**bold" in prompt.lower() or "bold anchor" in prompt.lower()


def test_ship30_prompt_with_no_chunks_asks_model_to_flag_insufficient_material():
    prompt = build_ship30_prompt("Write about a topic with no coverage", [])
    assert "not" in prompt.lower() and "enough" in prompt.lower()

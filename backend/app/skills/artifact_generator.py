"""Wraps generated content in an <artifact> envelope the frontend can parse
out of the streamed response, and provides the HTML artifact template used
when the user asks for a rendered HTML/CSS snippet.
"""
import re
from dataclasses import dataclass

ARTIFACT_TAG_RE = re.compile(
    r'<artifact type="(?P<type>markdown|html)" title="(?P<title>[^"]*)">(?P<body>.*?)</artifact>',
    re.DOTALL,
)

HTML_ARTIFACT_SYSTEM_SUFFIX = """
When the user asks for a rendered visual artifact (a one-pager, calculator, comparison table, etc.), \
respond with a SINGLE self-contained HTML document wrapped exactly like this:

<artifact type="html" title="Short Title Here">
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>/* inline CSS only, no external stylesheets */</style>
</head>
<body>
  ...
  <script>/* optional vanilla JS only, no external scripts */</script>
</body>
</html>
</artifact>

Rules for HTML artifacts:
- No external <script src> or <link> to third-party domains — everything must be self-contained.
- No network calls (fetch/XHR) to arbitrary endpoints.
- Keep it accessible: real semantic HTML, visible focus states, sufficient color contrast.
"""

MARKDOWN_ARTIFACT_WRAP = '<artifact type="markdown" title="{title}">\n{body}\n</artifact>'


@dataclass
class ParsedArtifact:
    artifact_type: str
    title: str
    content: str


def wrap_markdown_artifact(title: str, body: str) -> str:
    return MARKDOWN_ARTIFACT_WRAP.format(title=title, body=body)


def extract_artifact(full_text: str) -> ParsedArtifact | None:
    """Pull the first <artifact> block out of a completed model response.

    Used server-side (to persist the Artifact row) and mirrored client-side
    (to route content into the Artifact Viewer instead of the chat bubble).
    """
    match = ARTIFACT_TAG_RE.search(full_text)
    if not match:
        return None
    return ParsedArtifact(
        artifact_type=match.group("type"),
        title=match.group("title") or "Untitled artifact",
        content=match.group("body").strip(),
    )


def strip_artifact_tags(full_text: str) -> str:
    """Return the response with the raw <artifact> block removed, replaced by
    a short acknowledgment, so the chat transcript doesn't duplicate the
    entire artifact body inline.
    """
    match = ARTIFACT_TAG_RE.search(full_text)
    if not match:
        return full_text
    title = match.group("title") or "your artifact"
    before = full_text[: match.start()].strip()
    after = full_text[match.end() :].strip()
    ack = f"I've put together **{title}** — see it in the Artifact panel."
    parts = [p for p in [before, ack, after] if p]
    return "\n\n".join(parts)

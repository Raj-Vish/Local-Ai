"""Stage 2: split extracted text into retrievable pieces.

Why chunk at all: retrieval works best when the unit returned is small enough
to be specific and large enough to make sense on its own. A whole twelve-page
statement is too coarse to answer "which hotel in Mumbai"; a single line is
too fine to mean anything.

Why this chunker is careful about small documents: a receipt in this system
is around 260 characters. Splitting that into 200-character pieces would cut
"TOTAL" away from "5000.00" and produce fragments that retrieve worse than
the whole. So a document that already fits stays exactly one chunk.

Three properties this module guarantees:

  1. The original extracted text is never modified. A chunk's text is built
     only from lines of the source, joined back with newlines.
  2. Chunking is deterministic. The same text always produces the same
     chunks, so re-indexing a document cannot silently change its vectors.
  3. Every chunk knows which lines it came from, so a retrieval hit can be
     traced back to a place in the document -- the same evidence idea the
     field proposer uses.
"""
from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class Chunk:
    """One retrievable piece of a document."""
    index: int          # 0-based position within the document
    text: str
    start_line: int     # 1-based, inclusive, into the extracted text
    end_line: int       # 1-based, inclusive

    @property
    def char_count(self) -> int:
        return len(self.text)


def _hard_split(line: str, size: int) -> list[str]:
    """Break a single over-long line. Only for text with no line breaks.

    A 40,000-character PDF that extracted as one line would otherwise never
    fit any chunk, and the loop below could not make progress.
    """
    return [line[at:at + size] for at in range(0, len(line), size)] or [""]


def chunk_text(
    text: str,
    *,
    size: int | None = None,
    overlap: int | None = None,
    min_chars: int | None = None,
) -> list[Chunk]:
    """Split extracted text into chunks, preserving line positions.

    size      -- target maximum characters per chunk
    overlap   -- characters of trailing context repeated into the next chunk,
                 so a sentence split across a boundary is still findable whole
    min_chars -- a trailing remainder smaller than this is merged back rather
                 than left as a stub
    """
    size = size or settings.CHUNK_SIZE_CHARS
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP_CHARS
    min_chars = min_chars if min_chars is not None else settings.CHUNK_MIN_CHARS

    # Overlap must leave room to advance, or the loop would revisit the same
    # lines forever.
    overlap = max(0, min(overlap, size // 2))

    if not text or not text.strip():
        return []

    lines = text.splitlines()

    # A document that already fits stays whole. This is the receipt case, and
    # it is the common one here.
    if len(text) <= size:
        return [Chunk(index=0, text=text.strip("\n"),
                      start_line=1, end_line=len(lines))]

    chunks: list[Chunk] = []
    cursor = 0                      # 0-based index into `lines`
    while cursor < len(lines):
        taken: list[str] = []
        length = 0
        at = cursor

        while at < len(lines):
            line = lines[at]
            # +1 for the newline that will rejoin it.
            addition = len(line) + (1 if taken else 0)
            if taken and length + addition > size:
                break
            if not taken and len(line) > size:
                # One line longer than a whole chunk: split it by characters
                # and emit those directly, then carry on line by line.
                for piece in _hard_split(line, size):
                    chunks.append(Chunk(index=len(chunks), text=piece,
                                        start_line=at + 1, end_line=at + 1))
                at += 1
                taken = []
                length = 0
                break
            taken.append(line)
            length += addition
            at += 1

        if taken:
            body = "\n".join(taken).strip("\n")
            if body:
                chunks.append(Chunk(index=len(chunks), text=body,
                                    start_line=cursor + 1, end_line=at))

        if at >= len(lines):
            break

        # Step back over trailing lines until `overlap` characters are
        # repeated, so context spanning the boundary survives in both chunks.
        step_back = 0
        carried = 0
        while overlap and step_back < len(taken) - 1 and carried < overlap:
            carried += len(taken[-1 - step_back]) + 1
            step_back += 1

        advanced = at - step_back
        # Always make progress, whatever the overlap arithmetic says.
        cursor = advanced if advanced > cursor else at

    # A final stub is more useful folded into its neighbour than left alone.
    if len(chunks) > 1 and chunks[-1].char_count < min_chars:
        last = chunks.pop()
        previous = chunks.pop()
        merged = f"{previous.text}\n{last.text}".strip("\n")
        chunks.append(Chunk(index=previous.index, text=merged,
                            start_line=previous.start_line, end_line=last.end_line))

    return chunks


def chunk_document(text: str) -> list[Chunk]:
    """Chunk using the configured settings. The entry point callers should use."""
    return chunk_text(text)

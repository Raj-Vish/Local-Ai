"""Checks for the chunker.

    ./venv/bin/python test_chunking.py

No server, no database. The cases that matter are the small ones: a receipt
must survive whole, and chunking must never invent, drop or reorder text.
"""
import sys

from services import chunking
from services.chunking import chunk_text

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


RECEIPT = """TAJ RESIDENCY
Colaba, Mumbai 400001
GSTIN: 27AABCT1234M1Z5

TAX INVOICE
Invoice No: TR/2026/09/4417
Date: 01/09/2026
Guest: Raj Vishwakarma

Description              Qty      Amount
Room Charges (Deluxe)      2      4237.29
CGST 9%                            381.36

TOTAL                             5000.00"""

LONG = "\n".join(f"Line {n:03d}: " + "filler text about expenses " * 4 for n in range(1, 121))


def main():
    print("Chunking checks\n" + "=" * 62)

    print("\nA receipt is not worth splitting")
    chunks = chunk_text(RECEIPT, size=1000, overlap=150)
    check("stays one chunk", len(chunks) == 1, f"-> {len(chunks)}")
    check("TOTAL stays with its amount", "TOTAL" in chunks[0].text and "5000.00" in chunks[0].text)
    check("line range covers the document", chunks[0].start_line == 1, f"-> {chunks[0].start_line}")
    check("text is unchanged", chunks[0].text == RECEIPT.strip("\n"))

    print("\nA long document is split")
    chunks = chunk_text(LONG, size=1000, overlap=150)
    check("more than one chunk", len(chunks) > 1, f"-> {len(chunks)}")
    check("indexes are 0..n-1 in order",
          [c.index for c in chunks] == list(range(len(chunks))))
    oversized = [c.char_count for c in chunks if c.char_count > 1000 + 200]
    check("no chunk wildly over budget", not oversized, f"-> {oversized[:3]}")
    check("line ranges advance",
          all(b.start_line >= a.start_line for a, b in zip(chunks, chunks[1:])))
    check("every chunk has content", all(c.text.strip() for c in chunks))

    print("\nNothing is invented, dropped or reordered")
    source_lines = [l for l in LONG.splitlines() if l.strip()]
    covered = set()
    for c in chunks:
        for line in c.text.splitlines():
            if line.strip():
                covered.add(line)
    check("every source line appears in some chunk",
          all(l in covered for l in source_lines),
          f"-> {len(covered)} distinct lines covered of {len(set(source_lines))}")
    check("no chunk contains text absent from the source",
          all(line in LONG for c in chunks for line in c.text.splitlines() if line.strip()))

    print("\nOverlap repeats context across the boundary")
    with_overlap = chunk_text(LONG, size=1000, overlap=300)
    without = chunk_text(LONG, size=1000, overlap=0)
    check("overlap produces at least as many chunks",
          len(with_overlap) >= len(without), f"-> {len(with_overlap)} vs {len(without)}")
    first_end = with_overlap[0].end_line
    second_start = with_overlap[1].start_line
    check("consecutive chunks share lines", second_start <= first_end,
          f"-> chunk0 ends {first_end}, chunk1 starts {second_start}")
    check("no overlap means no sharing",
          without[1].start_line > without[0].end_line,
          f"-> chunk0 ends {without[0].end_line}, chunk1 starts {without[1].start_line}")

    print("\nDeterminism")
    check("same input, same chunks", chunk_text(LONG, size=1000, overlap=150) == chunks)
    check("chunks are hashable/comparable", len({c for c in chunks}) == len(chunks))

    print("\nAwkward inputs")
    check("empty text -> no chunks", chunk_text("", size=1000) == [])
    check("whitespace only -> no chunks", chunk_text("   \n\n  \t ", size=1000) == [])
    single = chunk_text("x" * 5000, size=1000, overlap=100)
    check("one enormous line is split", len(single) >= 5, f"-> {len(single)}")
    check("pieces of that line stay within size",
          all(c.char_count <= 1000 for c in single),
          f"-> max {max(c.char_count for c in single)}")
    check("no data lost from the long line",
          "".join(c.text for c in single) == "x" * 5000)

    print("\nTermination (overlap can never stall progress)")
    # overlap >= size would repeat forever if it were not clamped.
    stubborn = chunk_text(LONG, size=400, overlap=10_000)
    check("absurd overlap still terminates", len(stubborn) > 1, f"-> {len(stubborn)} chunks")
    check("and still advances",
          stubborn[-1].end_line >= stubborn[0].end_line, f"-> ends at line {stubborn[-1].end_line}")

    print("\nA trailing stub is merged, not left alone")
    text = "\n".join(f"line {n} with a little text" for n in range(1, 40)) + "\nend"
    merged = chunk_text(text, size=300, overlap=0, min_chars=200)
    check("last chunk is not a stub",
          len(merged) == 1 or merged[-1].char_count >= 100,
          f"-> {[c.char_count for c in merged]}")

    print("\nThe configured entry point works")
    check("chunk_document uses settings", len(chunking.chunk_document(RECEIPT)) == 1)

    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  FAILED: " + ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

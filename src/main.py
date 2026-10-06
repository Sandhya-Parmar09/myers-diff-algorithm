#!/usr/bin/env python3
"""
Assignment 1 - Implementing Myers' diff.

Part A (lines)     : print a minimal line diff of file A -> file B.
Part B (highlight) : the same line diff, plus one line per changed line-pair
                     saying which characters changed.

Usage:
    main.py lines     A B
    main.py highlight A B

Files are read as raw bytes. The same Myers' O(ND) algorithm (Eugene Myers,
1986, "An O(ND) Difference Algorithm and Its Variations") is used twice:
once over the lines of the two files (Part A) and once over the Unicode
code points of each changed line-pair (Part B). Standard library only.
"""

import sys
from array import array


# --------------------------------------------------------------------------
# Reading input
# --------------------------------------------------------------------------
def read_lines(path):
    """Read a file as raw bytes and split it into lines, per the spec.

    - Split on the newline byte b"\\n".
    - If the last piece is empty, drop it (a trailing newline does not create
      an extra empty line; an empty file has no lines).
    - Any b"\\r" is kept as part of the line.
    - Lines stay as bytes and are compared as exact bytes.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    parts = data.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return parts


# --------------------------------------------------------------------------
# Myers' O(ND) diff over any two sequences
# --------------------------------------------------------------------------
def shortest_edit_script(a, b):
    """Return the minimal edit script turning sequence ``a`` into ``b``.

    The result is a list of operations, in order along the edit path:
        ("keep", ai, bi)    a[ai] == b[bi], kept in both
        ("del",  ai, None)  a[ai] deleted (present only in a)
        ("ins",  None, bi)  b[bi] inserted (present only in b)
    Works for any items comparable with ==, so it serves both the line diff
    (items are byte-lines) and the character diff (items are code points).
    """
    n, m = len(a), len(b)
    if n == 0 and m == 0:
        return []

    maxd = n + m
    off = maxd                       # array index `off + k` holds diagonal k
    v = array('l', [0]) * (2 * maxd + 1)
    trace = []                       # trace[d] = V as it was entering round d
    found_d = None

    # Forward pass: find the edit distance D, recording a trace to backtrack.
    for d in range(maxd + 1):
        # Snapshot only the window round d can reach: diagonals -d .. d.
        # In this snapshot, V[k] is stored at index (k + d).
        trace.append(v[off - d: off + d + 1])
        for k in range(-d, d + 1, 2):
            # Reach diagonal k either from k+1 by a down move (insertion) or
            # from k-1 by a right move (deletion). Take whichever goes further.
            if k == -d or (k != d and v[off + k - 1] < v[off + k + 1]):
                x = v[off + k + 1]           # insertion (down)
            else:
                x = v[off + k - 1] + 1       # deletion (right)
            y = x - k
            # Follow the snake: free diagonal moves over equal items (keeps).
            while x < n and y < m and a[x] == b[y]:
                x += 1
                y += 1
            v[off + k] = x
            if x >= n and y >= m:
                found_d = d
                break
        if found_d is not None:
            break

    # Backward pass: walk the trace from (n, m) to (0, 0) to recover the ops.
    script = []
    x, y = n, m
    for d in range(found_d, 0, -1):
        vd = trace[d]                        # V after d-1 edits; V[k] = vd[k + d]
        k = x - y
        if k == -d or (k != d and vd[k - 1 + d] < vd[k + 1 + d]):
            prev_k = k + 1                   # previous step was an insertion
        else:
            prev_k = k - 1                   # previous step was a deletion
        prev_x = vd[prev_k + d]
        prev_y = prev_x - prev_k
        # The snake (kept items) travelled before this edit.
        while x > prev_x and y > prev_y:
            script.append(("keep", x - 1, y - 1))
            x -= 1
            y -= 1
        # The single edit that landed us on diagonal k.
        if x == prev_x:
            script.append(("ins", None, prev_y))
        else:
            script.append(("del", prev_x, None))
        x, y = prev_x, prev_y
    # Leading snake out of the origin (the very first run of keeps).
    while x > 0 and y > 0:
        script.append(("keep", x - 1, y - 1))
        x -= 1
        y -= 1

    script.reverse()
    return script


# --------------------------------------------------------------------------
# Part B helpers: changed-character ranges
# --------------------------------------------------------------------------
def to_ranges(positions):
    """Merge 0-based code-point positions into ``start-end`` ranges (end excl.).

    Returns "." when nothing changed on this side. Touching positions merge
    into a single range, so 3,4,5,6 -> "3-7" (never "3-5,5-7").
    """
    if not positions:
        return "."
    positions.sort()
    chunks = []
    start = prev = positions[0]
    for pos in positions[1:]:
        if pos == prev + 1:
            prev = pos
        else:
            chunks.append("%d-%d" % (start, prev + 1))
            start = prev = pos
    chunks.append("%d-%d" % (start, prev + 1))
    return ",".join(chunks)


def highlight_line(old_bytes, new_bytes):
    """Build the "? old | new" line for a paired -/+ line.

    In highlight tests both files are valid UTF-8, so we decode to code points
    and diff those. The old ranges are the deleted code-point positions in the
    old line; the new ranges are the inserted positions in the new line.
    """
    old = list(old_bytes.decode("utf-8"))
    new = list(new_bytes.decode("utf-8"))
    script = shortest_edit_script(old, new)
    del_pos = [op[1] for op in script if op[0] == "del"]
    ins_pos = [op[2] for op in script if op[0] == "ins"]
    return ("? " + to_ranges(del_pos) + " | " + to_ranges(ins_pos)).encode("ascii")


# --------------------------------------------------------------------------
# Rendering the diff
# --------------------------------------------------------------------------
def render(a_lines, b_lines, with_highlight):
    """Produce the diff output as bytes for the given command."""
    script = shortest_edit_script(a_lines, b_lines)
    out = bytearray()
    i = 0
    total = len(script)
    while i < total:
        if script[i][0] == "keep":
            out += b" "
            out += a_lines[script[i][1]]
            out += b"\n"
            i += 1
            continue
        # A change block: consecutive -/+ ops with no keep between them.
        dels = []
        inss = []
        while i < total and script[i][0] != "keep":
            if script[i][0] == "del":
                dels.append(script[i][1])
            else:
                inss.append(script[i][2])
            i += 1
        # Delete-first rule: every '-' line before any '+' line.
        for ai in dels:
            out += b"-"
            out += a_lines[ai]
            out += b"\n"
        for j, bi in enumerate(inss):
            out += b"+"
            out += b_lines[bi]
            out += b"\n"
            # Part B: pair the j-th '-' with the j-th '+'. Extras stay unpaired.
            if with_highlight and j < len(dels):
                out += highlight_line(a_lines[dels[j]], b_lines[bi])
                out += b"\n"
    return out


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def main(argv):
    if len(argv) != 3 or argv[0] not in ("lines", "highlight"):
        sys.stderr.write("usage: (lines|highlight) FILE_A FILE_B\n")
        return 2
    command, path_a, path_b = argv
    try:
        a_lines = read_lines(path_a)
        b_lines = read_lines(path_b)
    except OSError as exc:
        # Cannot read an input: nothing on stdout, message on stderr, exit 2.
        sys.stderr.write("cannot read input file: %s\n" % exc)
        return 2
    output = render(a_lines, b_lines, with_highlight=(command == "highlight"))
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

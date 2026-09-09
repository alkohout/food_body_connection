"""Structural check for a JS file: brackets, strings, and function nesting.

Companion to check_js_cross_function.py, which needs tree-sitter. That is not
always installable — a machine whose wheels were built for one Python and
whose interpreter has moved on, with no pip to rebuild them, leaves the only
JS check in the repo unrunnable. This one is pure standard library and always
runs.

    python3 tools/js_structure_check.py docs/js/dashboard.js [names...]

Run it against a known-good revision first. It is a heuristic, and a checker
that fails on code that already works is telling you about itself rather than
about the file:

    git show HEAD:docs/js/dashboard.js > /tmp/head.js
    python3 tools/js_structure_check.py /tmp/head.js


Not a parser. It answers the questions an edit like inserting a function can
actually get wrong — an unbalanced brace, an unterminated string or template,
a function that ends up nested inside another — and it reports the nesting
depth of every top-level function so a misplaced insertion is visible.
"""
import sys

def scan(src):
    i, n = 0, len(src)
    depth, stack, funcs = 0, [], []
    line = 1
    pairs = {")": "(", "]": "[", "}": "{"}
    prev_sig = ""          # last significant char, for the regex heuristic
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1; i += 1; continue
        # comments
        if c == "/" and i + 1 < n and src[i+1] == "/":
            while i < n and src[i] != "\n": i += 1
            continue
        if c == "/" and i + 1 < n and src[i+1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i+1] == "/"):
                if src[i] == "\n": line += 1
                i += 1
            i += 2; continue
        # regex literal: only where a value may begin. A preceding word
        # matters as much as a preceding symbol — "return /[",\n]/" is a
        # regex, and reading it as division makes the quote inside it open a
        # string that never closes.
        word = ""
        k = i - 1
        while k >= 0 and src[k].isspace(): k -= 1
        while k >= 0 and (src[k].isalnum() or src[k] in "_$"):
            word = src[k] + word; k -= 1
        KEYWORDS = {"return", "typeof", "case", "in", "of", "do", "else",
                    "yield", "await", "delete", "void", "instanceof", "new"}
        if c == "/" and (prev_sig in "(,=:[!&|?{};+-*%~^<>" or word in KEYWORDS):
            j, esc, cls = i + 1, False, False
            while j < n:
                d = src[j]
                if esc: esc = False
                elif d == "\\": esc = True
                elif d == "[": cls = True
                elif d == "]": cls = False
                elif d == "/" and not cls: break
                elif d == "\n": j = n; break
                j += 1
            if j < n:
                i = j + 1; prev_sig = "/"; continue
        # strings and templates
        if c in "'\"`":
            quote, j, esc = c, i + 1, False
            while j < n:
                d = src[j]
                if esc: esc = False
                elif d == "\\": esc = True
                elif quote == "`" and d == "$" and j + 1 < n and src[j+1] == "{":
                    k, nest = j + 2, 1
                    while k < n and nest:
                        if src[k] == "{": nest += 1
                        elif src[k] == "}": nest -= 1
                        elif src[k] == "\n": line += 1
                        k += 1
                    j = k; continue
                elif d == quote: break
                elif d == "\n":
                    line += 1
                    if quote != "`":
                        return None, f"unterminated {quote} string near line {line}", []
                j += 1
            if j >= n:
                return None, f"unterminated {quote} string from line {line}", []
            i = j + 1; prev_sig = quote; continue
        if src.startswith("function", i) and (i == 0 or not (src[i-1].isalnum() or src[i-1] in "_$.")):
            rest = src[i+8:i+60].strip()
            name = ""
            for ch in rest:
                if ch.isalnum() or ch in "_$": name += ch
                else: break
            if name: funcs.append((name, depth, line))
        if c in "([{":
            stack.append((c, line)); depth += 1
        elif c in ")]}":
            if not stack or stack[-1][0] != pairs[c]:
                return None, f"unmatched {c!r} at line {line}", []
            stack.pop(); depth -= 1
        if not c.isspace(): prev_sig = c
        i += 1
    if stack:
        return None, f"unclosed {stack[-1][0]!r} opened at line {stack[-1][1]}", []
    return depth, None, funcs

src = open(sys.argv[1], encoding="utf-8").read()
depth, err, funcs = scan(src)
if err:
    print(f"  FAIL: {err}"); sys.exit(1)
print(f"  balanced, final depth {depth}, {len(funcs)} function keywords")
want = set(sys.argv[2:])
for name, d, line in funcs:
    if name in want:
        print(f"    {name:22s} depth {d} (0 = top level)  line {line}")

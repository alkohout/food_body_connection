"""Mechanical sweep for the classes of bug that have actually bitten."""
import pathlib, re
src = pathlib.Path("docs/js/dashboard.js").read_text()
lines = src.splitlines()

# 1. mutating calls that do not refresh the token first.
#    A session outlasting its token is what produced the 401 storm.
muts, unguarded = [], []
for i, l in enumerate(lines):
    if re.search(r'method:\s*"(POST|PATCH|DELETE|PUT)"', l):
        # look back up to 25 lines for the guard
        window = "\n".join(lines[max(0, i - 25):i])
        url = re.search(r'\$\{API_URL\}([^`"\']*)', "\n".join(lines[max(0,i-3):i+1]))
        muts.append((i + 1, url.group(1)[:44] if url else "?"))
        central = "window.fetch = async function" in src
        if not central and "ensureFreshToken" not in window:
            unguarded.append((i + 1, url.group(1)[:44] if url else "?"))
print(f"  mutating fetches: {len(muts)};  without a token refresh first: {len(unguarded)}")
for ln, u in unguarded:
    print(f"      line {ln:5d}  {u}")

# 2. fetches whose result is never checked
print()
unchecked = []
for m in re.finditer(r'(?:const|let)\s+(\w+)\s*=\s*await fetch\(', src):
    name = m.group(1)
    tail = src[m.end(): m.end() + 420]
    if f"{name}.ok" not in tail and f"!{name}.ok" not in tail:
        ln = src[:m.start()].count("\n") + 1
        unchecked.append((ln, name))
print(f"  awaited fetches whose response is never checked: {len(unchecked)}")
for ln, n in unchecked[:10]:
    print(f"      line {ln:5d}  {n}")

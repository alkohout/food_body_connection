"""Ids the script reaches for that nothing defines.

getElement returns null for a missing id and only warns, so the failure turns
up later as a TypeError on a line that looks fine — or as a feature that
quietly does nothing. Both had happened here: the "add this as a new exposure"
prompt threw every time you typed something unrecognised, and a symptom
autocomplete warned on every page load without ever being able to work.

Counts ids the script writes into markup itself as defined, because much of
the check-in form is built that way.

    python3 tools/js_element_check.py
"""
import pathlib, re
js = pathlib.Path("docs/js/dashboard.js").read_text()
html = "".join(pathlib.Path(f"docs/{n}").read_text()
               for n in ("dashboard.html", "index.html", "reset-password.html"))

defined = set(re.findall(r'\bid="([^"]+)"', html))
# ids the JS creates itself at runtime
created = set(re.findall(r'\.id\s*=\s*"([^"]+)"', js))
created |= set(re.findall(r'\.id\s*=\s*`([^`$]+)`', js))
# markup the JS builds as a string, which is most of the check-in form
created |= set(re.findall(r'\bid="([^"]+)"', js))
wanted = set(re.findall(r'getElement\("([^"]+)"\)', js))
wanted |= set(re.findall(r'getElementById\("([^"]+)"\)', js))

missing = sorted(wanted - defined - created)
print(f"  ids the JS looks up: {len(wanted)}")
print(f"  never defined in the markup and never created in JS: {len(missing)}")
for m in missing:
    ctx = re.search(rf'^.*getElement\("{re.escape(m)}"\).*$', js, re.M)
    print(f"      {m:28s} {ctx.group(0).strip()[:62] if ctx else ''}")

# handlers wired to ids that do not exist
print()
wired = re.findall(r'getElement\("([^"]+)"\)[\s\S]{0,80}?addEventListener', js)
bad = sorted(set(wired) - defined - created)
print(f"  event handlers wired to ids that do not exist: {len(bad)} {bad}")

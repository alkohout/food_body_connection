"""Find a const/let declared in one top-level function and used in another.

Run:  python tools/check_js_cross_function.py docs/js/dashboard.js
Needs tree-sitter and tree-sitter-javascript in the environment running it.

Read the output, do not trust it: a name used as a callback parameter in one
function and declared in another is reported too, and there are a dozen of
those. The signal is a name that plainly belongs to one function appearing in
an unrelated one.

Narrower than a scope checker and far less noisy: it only asks whether a name
that exists in exactly one function's body is referenced from a different
function, with nothing of that name at module scope. That is precisely the
mistake that made nextSide throw — valid syntax, no such binding at runtime.
"""
import re
import sys
from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs

src = open(sys.argv[1], "rb").read()
tree = Parser(Language(tsjs.language())).parse(src)
txt = lambda n: src[n.start_byte:n.end_byte].decode("utf8", "replace")

# Top-level functions and their byte ranges.
funcs = []
for n in tree.root_node.children:
    if n.type == "function_declaration":
        funcs.append((txt(n.child_by_field_name("name")), n.start_byte, n.end_byte))

def owner(byte):
    for name, a, b in funcs:
        if a <= byte < b:
            return name
    return None

# Names bound at module scope are always fine.
module_names = set()
for n in tree.root_node.children:
    if n.type in ("lexical_declaration", "variable_declaration"):
        for d in n.children:
            if d.type == "variable_declarator":
                nm = d.child_by_field_name("name")
                if nm is not None and nm.type == "identifier":
                    module_names.add(txt(nm))
    elif n.type == "function_declaration":
        module_names.add(txt(n.child_by_field_name("name")))

# Where each name is declared with const/let, and which function that is in.
decls, uses = {}, {}
stack = [tree.root_node]
while stack:
    n = stack.pop()
    if n.type == "variable_declarator":
        nm = n.child_by_field_name("name")
        if nm is not None and nm.type == "identifier":
            decls.setdefault(txt(nm), set()).add(owner(nm.start_byte))
    elif n.type == "identifier":
        p = n.parent
        skip = p is not None and (
            (p.type == "member_expression" and p.child_by_field_name("property") is n)
            or (p.type == "variable_declarator" and p.child_by_field_name("name") is n)
            or (p.type == "pair" and p.child_by_field_name("key") is n)
        )
        if not skip:
            uses.setdefault(txt(n), set()).add(owner(n.start_byte))
    stack.extend(n.children)

bad = []
for name, where in decls.items():
    where = {w for w in where if w}          # declared inside some function
    if not where or name in module_names:
        continue
    used_in = {u for u in uses.get(name, set()) if u}
    outside = used_in - where
    if outside:
        bad.append((name, sorted(where), sorted(outside)))

if not bad:
    print("  none: every function-local name is used only where it exists")
for name, where, outside in sorted(bad):
    print(f"  {name:22s} declared in {where}  but used in {outside}")

import sys, ast, importlib.util
spec = importlib.util.spec_from_file_location("mb", "/home/claude/launch-claim-checker/tools/mutate_bounties.py")
mb = importlib.util.module_from_spec(spec); spec.loader.exec_module(mb)
SRC = mb.SRC
print("mutants:", len(mb.MUTANTS), "distinct names:", len({m[0] for m in mb.MUTANTS}))
bad = 0; same_ast = []; syntax = []; seen = {}
base = ast.dump(ast.parse(SRC))
for i,(name,old,new) in enumerate(mb.MUTANTS,1):
    n = SRC.count(old)
    if n != 1 or old == new:
        print("SETUP", i, name, n); bad += 1; continue
    m = SRC.replace(old,new)
    try:
        d = ast.dump(ast.parse(m))
    except SyntaxError as e:
        syntax.append((i,name,str(e))); continue
    if d == base: same_ast.append((i,name))
    if m in seen: print("DUPLICATE mutant text:", i, name, "==", seen[m])
    seen[m] = (i,name)
print("setup errors:", bad)
print("mutants that do not parse (trivially 'caught'):", syntax)
print("mutants with unchanged syntax tree (cannot be caught):", same_ast)

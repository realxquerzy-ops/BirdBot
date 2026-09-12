import os
import sys
import py_compile
import importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
COMMANDS = os.path.join(ROOT, "commands")

fails = []

def _lint(file, path, import_it):
    try:
        py_compile.compile(path, doraise=True)
    except Exception as e:
        fails.append((file, f"compile: {e}"))
        return
    if not import_it:
        print(f"OK    {file}")
        return
    try:
        spec = importlib.util.spec_from_file_location(
            "lint_" + os.path.basename(file)[:-3], path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print(f"OK    {file}")
    except Exception as e:
        fails.append((file, f"import: {e}"))

for f in sorted(os.listdir(COMMANDS)):
    if f.endswith(".py") and f != "__init__.py":
        _lint(os.path.join("commands", f), os.path.join(COMMANDS, f), import_it=True)

_lint("main.py", os.path.join(ROOT, "main.py"), import_it=False)

if fails:
    print("\nFAILED:")
    for f, e in fails:
        print(f"  {f} -> {e}")
    sys.exit(1)

print("\nAll modules compile and import cleanly.")
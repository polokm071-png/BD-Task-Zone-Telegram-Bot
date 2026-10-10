---
name: Python packages in Replit
description: Package installation fallback when the managed installer targets immutable system Python.
---

If the managed Python package installer fails because the system interpreter is externally managed (PEP 668), target the existing workspace environment with `uv pip` and its `.pythonlibs/bin/python` interpreter. Avoid bypassing the system package protection.

**Why:** The Replit workspace’s usable Python packages live in `.pythonlibs`, while system Python may be immutable.

**How to apply:** Keep dependencies declared in the project manifest, then install them into `.pythonlibs` with `uv pip install --python .pythonlibs/bin/python -r requirements.txt` when the managed installer cannot target that environment.

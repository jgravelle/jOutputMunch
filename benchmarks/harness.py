"""
jOutputMunch Benchmark Harness (compatibility entry point).

The harness lives in `src/joutputmunch/bench/`. This file keeps the old
command working:

    pip install -e ".[anthropic]"
    python benchmarks/harness.py --list
    python benchmarks/harness.py --save          # every run calls a paid API

The defaults reproduce the published run (benchmarks/results.md): Anthropic
`claude-sonnet-4-6`, temperature 1.0, max 4096 output tokens.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from joutputmunch.bench.cli import main

if __name__ == "__main__":
    sys.exit(main())

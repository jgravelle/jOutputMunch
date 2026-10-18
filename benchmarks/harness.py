"""
jOutputMunch Benchmark Harness (compatibility entry point).

The harness lives in `src/joutputmunch/bench/`. This file keeps the old
command working:

    pip install -e ".[anthropic]"
    python benchmarks/harness.py --list
    python benchmarks/harness.py --save          # every run calls a paid API

The defaults are the model benchmarks/results.md names (`claude-sonnet-4-6`)
and the settings of the harness committed with it: temperature 1.0, max 4096
output tokens. `--save` overwrites benchmarks/results.md; pass --output to
keep it.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from joutputmunch.bench.cli import main

if __name__ == "__main__":
    sys.exit(main())

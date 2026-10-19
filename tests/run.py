#!/usr/bin/env python3
"""Run the whole suite, with tools/ on the path regardless of import order.

    python3 tests/run.py            # everything
    python3 tests/run.py sweep      # only modules matching "sweep"
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    pattern = f"test*{sys.argv[1]}*.py" if len(sys.argv) > 1 else "test_*.py"
    suite = unittest.TestLoader().discover(HERE, pattern=pattern, top_level_dir=HERE)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

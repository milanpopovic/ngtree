#!/usr/bin/env python3
"""ngtree demo from the source folder — the same as the `ngtree-demo` command (code: ngtree/demo.py).

    pip install nicegui
    python examples/demo.py        # http://localhost:8098, data in examples/demo-data/
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ngtree.demo import main  # noqa: E402

if __name__ in {'__main__', '__mp_main__'}:
    main(['--data', str(HERE / 'demo-data'), *sys.argv[1:]])

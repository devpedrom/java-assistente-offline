"""Acceptance rules for the exact supplied console battery, not product logic."""

from pathlib import Path
import re
import sys


def accepted(output: str) -> bool:
    lines = output.strip().splitlines()
    return (
        bool(lines)
        and not re.search(r"(?m)^\s*(?:❌|FALH[AO])", output, re.I)
        and len(re.findall(r"(?m)^\s*✔\s+", output)) == 17
        and re.search(r"✔\s+OK:", output) is not None
        and len(lines[-1]) >= 30 and set(lines[-1]) == {"═"}
    )


if __name__ == "__main__":
    sys.exit(0 if accepted(Path(sys.argv[1]).read_text(encoding="utf-8")) else 1)

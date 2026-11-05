"""Small repository hygiene gate; does not replace dedicated secret scanning."""

from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
patterns = [
    re.compile(r"gh[pousr]_" + r"[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA" + r"[A-Z0-9]{16}"),
]
failures = []
for directory in ("src", "tests", "examples", "docs", ".github", "scripts"):
    for path in (root / directory).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            data = path.read_text()
            if any(pattern.search(data) for pattern in patterns):
                failures.append(str(path.relative_to(root)))
if failures:
    raise SystemExit("Possible credential material in: " + ", ".join(failures))
print("Repository credential-pattern check passed")

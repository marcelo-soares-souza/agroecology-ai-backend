"""Scan backend source files for hardcoded secrets."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI/DeepSeek API key"),
    (r'api[_-]?key\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']', "API key assignment"),
    (r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{10,}", "JWT token"),
    (r"BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY", "Private key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"glpat-[a-zA-Z0-9_-]{20,}", "GitLab PAT"),
    (r"postgresql://[^@]+:[^@]+@", "Database URL with credentials"),
    (r"redis://[^@]+:[^@]+@", "Redis URL with credentials"),
]

# Files/dirs to skip
SKIP_PATTERNS = {
    ".env.example",
    "__pycache__",
    ".venv",
    ".git",
    "venv",
    "index",
    "data",
}


def scan_file(filepath: Path) -> list[str]:
    issues: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return issues

    for i, line in enumerate(content.splitlines(), 1):
        for pattern, name in PATTERNS:
            match = re.search(pattern, line)
            if match:
                # Check if this is in a comment or docstring
                stripped = line.strip()
                if (
                    stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                issues.append(
                    f"{filepath.relative_to(ROOT)}:{i}: potential {name} — "
                    f"{match.group(0)[:40]}..."
                )

    return issues


def main() -> int:
    issues: list[str] = []

    for py_file in ROOT.rglob("*.py"):
        parts = set(py_file.parts)
        if parts & SKIP_PATTERNS:
            continue
        if py_file.name == "scan-source-secrets.py":
            continue
        issues.extend(scan_file(py_file))

    # Also scan .env.example
    env_example = ROOT / ".env.example"
    if env_example.exists():
        issues.extend(scan_file(env_example))

    if issues:
        print(f"Found {len(issues)} potential secret(s):")
        for issue in issues:
            print(f"  {issue}")
        print("\nReview the findings above. If false positives, this is safe.")
        return 0  # Warning only, not a fatal error

    print("No secrets found in source code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"venv", "__pycache__", ".git", "reports"}
EXCLUDED_FILES = {".env.example"}
SECRET_NAME_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key|access[_-]?key|channel[_-]?access)"
)
ASSIGNMENT_RE = re.compile(r"^\s*([A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD)[A-Z0-9_]*)\s*=\s*(.+?)\s*$")
PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "example",
    "example.com",
    "your-email@example.com",
    "report@example.com",
    "false",
    "true",
}


def is_excluded(path: Path) -> bool:
    rel_parts = path.relative_to(BASE_DIR).parts
    if any(part in EXCLUDED_DIRS for part in rel_parts):
        return True
    if path.name in EXCLUDED_FILES:
        return True
    if path.name.startswith(".env") and path.name != ".env.example":
        return True
    return False


def iter_text_files() -> list[Path]:
    files = []
    for path in BASE_DIR.rglob("*"):
        if not path.is_file() or is_excluded(path):
            continue
        if path.suffix.lower() in {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg"}:
            files.append(path)
    return sorted(files)


def looks_like_real_value(value: str) -> bool:
    stripped = value.strip().strip('"').strip("'")
    if stripped.lower() in PLACEHOLDER_VALUES:
        return False
    if "os.getenv(" in stripped or "os.environ" in stripped:
        return False
    if "${{" in stripped or "$(" in stripped or stripped.startswith("$"):
        return False
    if "example" in stripped.lower() or "your-" in stripped.lower():
        return False
    return len(stripped) >= 8


def scan_file(path: Path) -> list[dict]:
    findings = []
    if path.resolve() == Path(__file__).resolve():
        return findings
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings

    for line_number, line in enumerate(lines, 1):
        assignment = ASSIGNMENT_RE.match(line)
        if assignment and looks_like_real_value(assignment.group(2)):
            findings.append(
                {
                    "file": str(path.relative_to(BASE_DIR)),
                    "line": line_number,
                    "reason": f"sensitive assignment to {assignment.group(1)}",
                }
            )
            continue

        if SECRET_NAME_RE.search(line) and re.search(r"(sk-|re_|xoxb-|Bearer\s+[A-Za-z0-9_\-.]{12,})", line):
            findings.append(
                {
                    "file": str(path.relative_to(BASE_DIR)),
                    "line": line_number,
                    "reason": "secret-looking token pattern",
                }
            )

    return findings


def run_secret_scan() -> dict:
    findings = []
    for path in iter_text_files():
        findings.extend(scan_file(path))
    return {
        "ok": not findings,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan commit candidates for accidental secrets.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_secret_scan()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("secret_scan: OK" if result["ok"] else "secret_scan: FAIL")
        for finding in result["findings"]:
            print(f"  - {finding['file']}:{finding['line']} {finding['reason']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

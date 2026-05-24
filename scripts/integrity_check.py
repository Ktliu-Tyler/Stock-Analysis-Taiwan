import argparse
import importlib
import json
import py_compile
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"venv", "__pycache__", ".git", "reports"}
MODULES_TO_IMPORT = [
    "config",
    "scorer",
    "report_generator",
    "daily_agent",
    "scripts.secret_scan",
    "fetchers.twse_fetcher",
    "analysis.technical",
    "analysis.chips",
    "analysis.fundamental",
    "analysis.sentiment",
]


def iter_python_files() -> list[Path]:
    files = []
    for path in BASE_DIR.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(BASE_DIR).parts):
            continue
        files.append(path)
    return sorted(files)


def compile_python() -> list[str]:
    errors = []
    for path in iter_python_files():
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path.relative_to(BASE_DIR)}: {exc.msg}")
    return errors


def import_modules() -> list[str]:
    errors = []
    sys.path.insert(0, str(BASE_DIR))
    for module_name in MODULES_TO_IMPORT:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")
    return errors


def validate_sample_agent() -> list[str]:
    errors = []
    sys.path.insert(0, str(BASE_DIR))
    try:
        import daily_agent

        metadata = daily_agent.build_sample_metadata()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            poster_path = daily_agent.generate_poster_svg(metadata, tmp_path)
            html = daily_agent.build_email_html(metadata, poster_path)
            if not poster_path.exists():
                errors.append("poster generator did not create a file")
            if "台股晨間選股報告" not in html:
                errors.append("email HTML smoke test did not contain report title")
    except Exception as exc:
        errors.append(f"sample agent smoke test failed: {exc}")
    return errors


def validate_env_example() -> list[str]:
    errors = []
    env_example = BASE_DIR / ".env.example"
    if not env_example.exists():
        return [".env.example is missing"]

    required_keys = {
        "AGENT_THRESHOLD",
        "AGENT_SEND_EMAIL",
        "EMAIL_FROM",
        "EMAIL_TO",
        "RESEND_API_KEY",
        "AGENT_SEND_LINE",
        "LINE_CHANNEL_ACCESS_TOKEN",
        "LINE_TO",
    }
    content = env_example.read_text(encoding="utf-8")
    missing = [key for key in sorted(required_keys) if f"{key}=" not in content]
    if missing:
        errors.append(f".env.example missing keys: {', '.join(missing)}")
    return errors


def validate_secret_scan() -> list[str]:
    sys.path.insert(0, str(BASE_DIR))
    try:
        from scripts.secret_scan import run_secret_scan

        result = run_secret_scan()
        return [
            f"{finding['file']}:{finding['line']} {finding['reason']}"
            for finding in result["findings"]
        ]
    except Exception as exc:
        return [f"secret scan failed: {exc}"]


def run_checks() -> dict:
    checks = {
        "compile_python": compile_python(),
        "import_modules": import_modules(),
        "sample_agent": validate_sample_agent(),
        "env_example": validate_env_example(),
        "secret_scan": validate_secret_scan(),
    }
    return {
        "ok": all(not errors for errors in checks.values()),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local integrity checks for the stock scanner.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_checks()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for name, errors in result["checks"].items():
            status = "OK" if not errors else "FAIL"
            print(f"{name}: {status}")
            for error in errors:
                print(f"  - {error}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9_-]{20,}", "API key"),
    (r"sk-gamma-[a-zA-Z0-9_-]{20,}", "Gamma key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Token"),
]

EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "coverage", "__pycache__"}
EXCLUDE_FILES = {".env", ".env.local", ".env.example", "package-lock.json", "pnpm-lock.yaml", "secret_scan.py"}

def scan_file(filepath: Path):
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    for line_num, line in enumerate(content.splitlines(), start=1):
        if "REPLACE" in line or "placeholder" in line.lower() or "example" in line.lower() or "..." in line:
            continue
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, line):
                findings.append((line_num, desc))
    return findings

def main():
    root = Path(__file__).resolve().parent.parent
    violations = 0
    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file in EXCLUDE_FILES:
                continue
            path = Path(root_dir) / file
            if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".py", ".md", ".json", ".yaml", ".yml"}:
                continue
            findings = scan_file(path)
            for line_no, desc in findings:
                print(f"SECRET: {path.relative_to(root)}:{line_no} -> {desc}")
                violations += 1
    if violations > 0:
        print(f"FAILED: {violations} secrets detected")
        return 1
    print("PASSED: No secrets found")
    return 0

if __name__ == "__main__":
    sys.exit(main())

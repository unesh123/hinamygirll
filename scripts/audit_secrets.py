"""Audit repository, evidence, diffs, and bundles for secret exposures without printing values."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "apps/api/.env.local"


def main():
    secrets = []
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip("'\"")
            if len(v) >= 16 and any(c in k.lower() for c in ["token", "key", "secret"]):
                secrets.append((k, v))

    targets = [
        ("git_diff", None),
        ("docs/evidence", ROOT / "docs/evidence"),
        ("docs", ROOT / "docs"),
        ("frontend_dist", ROOT / "apps/web/dist"),
        ("vercel_output", ROOT / ".vercel/output"),
    ]

    report = {}
    for target_name, path in targets:
        exposed = []
        if target_name == "git_diff":
            diff = subprocess.check_output(["git", "diff"], cwd=ROOT, text=True, errors="replace")
            for k, s in secrets:
                if s in diff:
                    exposed.append(k)
        elif path and path.exists():
            for p in path.rglob("*"):
                if p.is_file() and not p.suffix.lower() in [".png", ".jpg", ".webp", ".pdf"]:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        for k, s in secrets:
                            if s in content:
                                exposed.append(f"{k} in {p.relative_to(ROOT)}")
                    except Exception:
                        pass
        report[target_name] = "EXPOSED: " + ", ".join(exposed) if exposed else "REDACTED"

    # Git tracking check for sensitive files
    git_status = subprocess.check_output(
        ["git", "status", "--ignored", "--porcelain", "apps/api/.env.local"],
        cwd=ROOT,
        text=True,
    ).strip()
    report["env_local_git_status"] = "IGNORED" if "!!" in git_status else ("TRACKED" if git_status else "NOT FOUND")

    print("--- SECRET AUDIT SUMMARY ---")
    for k, status in report.items():
        print(f"{k}: {status}")


if __name__ == "__main__":
    main()

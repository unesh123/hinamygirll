import os
import zipfile
import re

dest_zip = "hinaa_clean_source.zip"
if os.path.exists(dest_zip):
    os.remove(dest_zip)

exclude_dirs = {
    "node_modules", ".git", ".venv", "venv", "dist", "build", ".turbo",
    ".pytest_cache", "__pycache__", "video_frames", ".gemini", ".agents",
    ".next", "target", "coverage", ".vscode", ".idea"
}

exclude_exts = {
    ".zip", ".exe", ".tar", ".gz", ".bak", ".vrm", ".vrma",
    ".wav", ".mp3", ".mp4", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webm"
}

count = 0
with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk("."):
        # modify dirs in place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), ".").replace("\\", "/")
            
            # Skip if file in root is not relevant
            if rel_path.startswith(".env") and not rel_path.endswith(".env.example"):
                continue
            if "/.env" in rel_path and not rel_path.endswith(".env.example"):
                continue
            
            _, ext = os.path.splitext(file)
            if ext.lower() in exclude_exts:
                continue
                
            # Only include project code: apps/, tests/, or root config
            is_valid = (
                rel_path.startswith("apps/") or
                rel_path.startswith("tests/") or
                rel_path in {
                    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
                    "README.md", ".gitignore", ".env.example", "skills-lock.json"
                } or
                rel_path.startswith("tsconfig")
            )
            
            if is_valid:
                z.write(rel_path, arcname=rel_path)
                count += 1

size_mb = os.path.getsize(dest_zip) / (1024 * 1024)
print(f"Successfully created {dest_zip} with {count} files, size: {size_mb:.2f} MB")

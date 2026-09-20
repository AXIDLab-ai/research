"""Build a public-code ZIP from an explicit allowlist; never traverse private data."""
from pathlib import Path
import hashlib
import json
import zipfile
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="../tips_simulator_github.zip")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.out).resolve()
    top = ["app.py", "engine.py", "README.md", "MODEL_CARD.md", "IMPLEMENTATION_STATUS.md",
           "requirements.txt", "pyproject.toml", ".gitignore", "start.ps1", "start.cmd"]
    files = [root / name for name in top]
    files += [root / ".streamlit/config.toml"]
    for directory, pattern in [("tips_abm", "*.py"), ("configs", "*.json"), ("docs", "*.md"), ("scripts", "*.py")]:
        files += sorted((root / directory).glob(pattern))
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            hashes[relative] = hashlib.sha256(payload).hexdigest()
            archive.writestr(relative, payload)
        archive.writestr("RELEASE_MANIFEST.json", json.dumps({"files": hashes, "private_data_included": False,
            "verification": "Not run; packaging only", "entrypoint": "app.py", "python": "3.12"}, indent=2))
    print(json.dumps({"archive": str(output), "files": len(files) + 1, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

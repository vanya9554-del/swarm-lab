"""Release 1.0 artifacts: SBOM, checksums, notes."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from swarmlab import __version__

    release = ROOT / "release" / f"v{__version__}"
    release.mkdir(parents=True, exist_ok=True)
    components = [
        {"name": "swarm-lab", "version": __version__, "type": "application"},
        {"name": "python", "version": platform.python_version(), "type": "runtime"},
        {"name": "sqlite", "version": "stdlib", "type": "library"},
        {"name": "psycopg", "version": "optional", "type": "library"},
    ]
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {"name": "swarm-lab", "version": __version__, "type": "application"},
            "tools": [{"name": "release.py"}],
        },
        "components": components,
    }
    (release / "sbom.json").write_text(json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "release" not in p.parts and ".git" not in p.parts and "__pycache__" not in p.parts and not p.name.endswith((".db", ".pyc")))
    lines = ["# SHA256 checksums — swarm-lab v" + __version__, ""]
    for path in files:
        lines.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    (release / "checksums.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    notes = ROOT / "RELEASE_NOTES.md"
    if notes.exists():
        shutil.copy2(notes, release / "RELEASE_NOTES.md")
    print(json.dumps({"version": __version__, "release": str(release), "files": len(files), "components": len(components)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

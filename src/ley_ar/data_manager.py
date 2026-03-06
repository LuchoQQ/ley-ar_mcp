"""
Gestiona la descarga automatica de archivos pesados al primer uso.

Archivos chicos (legislacion, descriptores) van incluidos en el paquete.
Archivos pesados (embeddings, jurisprudencia) se descargan de GitHub Releases.
"""

from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# GitHub release URL base
GITHUB_REPO = "LuchoQQ/ley-ar_mcp"
RELEASE_TAG = "v0.1.0-data"

_HEAVY_FILES = {
    "embeddings": {
        "files": [
            DATA_DIR / "embeddings" / "descriptor_embeddings.faiss",
            DATA_DIR / "embeddings" / "descriptor_mappings.json",
        ],
        "archive": "embeddings.zip",
    },
    "jurisprudencia": {
        "files": [
            DATA_DIR / "jurisprudencia" / "jurisprudencia_laboral.jsonl",
        ],
        "archive": "jurisprudencia.zip",
    },
}


def _download_url(archive_name: str) -> str:
    return f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/{archive_name}"


def _download_and_extract(archive_name: str, dest_dir: Path) -> None:
    url = _download_url(archive_name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / archive_name

    print(f"Descargando {archive_name}...", file=sys.stderr)

    urllib.request.urlretrieve(url, zip_path)

    print(f"Extrayendo {archive_name}...", file=sys.stderr)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()

    print(f"{archive_name} listo.", file=sys.stderr)


def ensure_data_ready() -> None:
    """Verifica que todos los archivos pesados existan, descarga si faltan."""
    for name, info in _HEAVY_FILES.items():
        missing = [f for f in info["files"] if not f.exists()]
        if missing:
            dest_dir = missing[0].parent
            _download_and_extract(info["archive"], dest_dir)

            # Verificar despues de descarga
            still_missing = [f for f in info["files"] if not f.exists()]
            if still_missing:
                print(
                    f"Error: no se encontraron los archivos despues de descargar {info['archive']}: "
                    f"{[str(f.name) for f in still_missing]}",
                    file=sys.stderr,
                )
                sys.exit(1)

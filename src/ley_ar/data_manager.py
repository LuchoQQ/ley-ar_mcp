"""
Gestiona la descarga automatica de archivos pesados al primer uso.

Archivos chicos (legislacion, descriptores) van incluidos en el paquete.
Archivos pesados (embeddings, jurisprudencia) se descargan de GitHub Releases.
"""

from __future__ import annotations

import logging
import sys
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

# GitHub release URL base
GITHUB_REPO = "LuchoQQ/ley-ar_mcp"
RELEASE_TAG = "v0.1.0-data"

DOWNLOAD_TIMEOUT_SECONDS = 300

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


def _validate_zip_members(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Valida que ningun miembro del ZIP intente escapar del directorio destino."""
    resolved_dest = dest_dir.resolve()
    for member in zf.namelist():
        member_path = (dest_dir / member).resolve()
        if not str(member_path).startswith(str(resolved_dest)):
            raise ValueError(
                f"Archivo ZIP contiene path peligroso: {member}. "
                f"Descarga abortada por seguridad."
            )


def _download_and_extract(archive_name: str, dest_dir: Path) -> None:
    url = _download_url(archive_name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / archive_name

    logger.info("Descargando %s...", archive_name)
    print(f"Descargando {archive_name}...", file=sys.stderr)

    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            with open(zip_path, "wb") as out_file:
                while chunk := response.read(8192):
                    out_file.write(chunk)
    except Exception as e:
        # Limpiar archivo parcial si la descarga fallo
        if zip_path.exists():
            zip_path.unlink()
        raise RuntimeError(f"Error descargando {archive_name}: {e}") from e

    try:
        logger.info("Extrayendo %s...", archive_name)
        print(f"Extrayendo {archive_name}...", file=sys.stderr)
        with zipfile.ZipFile(zip_path, "r") as zf:
            _validate_zip_members(zf, dest_dir)
            zf.extractall(dest_dir)
    except Exception:
        # Limpiar ZIP si la extraccion fallo
        if zip_path.exists():
            zip_path.unlink()
        raise
    else:
        zip_path.unlink()

    logger.info("%s listo.", archive_name)
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
                raise RuntimeError(
                    f"No se encontraron archivos despues de descargar {info['archive']}: "
                    f"{[str(f.name) for f in still_missing]}"
                )

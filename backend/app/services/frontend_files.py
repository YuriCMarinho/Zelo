"""Entrega arquivos do frontend somente dentro da raiz pública."""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse


def frontend_file(directory: str, requested_path: str) -> FileResponse:
    root = Path(directory).resolve()
    target = (root / requested_path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(target if target.is_file() else root / "index.html")

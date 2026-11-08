from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.frontend_files import frontend_file


def test_frontend_rejects_traversal_and_symlinks(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text("frontend")
    (public / "visible.txt").write_text("public file")
    outside = tmp_path / "private.txt"
    outside.write_text("private file")
    (public / "escape.txt").symlink_to(outside)
    app = FastAPI()

    @app.get("/{path:path}")
    def serve(path: str):
        return frontend_file(str(public), path)

    with TestClient(app) as client:
        assert client.get("/visible.txt").text == "public file"
        assert client.get("/imoveis/123").text == "frontend"
        assert client.get("/..%2Fprivate.txt").status_code == 404
        assert client.get("/escape.txt").status_code == 404

"""Confere os cinco entregáveis e o acesso ao código sem aceitar links fictícios."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate(manifest: dict[str, object], root: Path, check_links: bool = False) -> list[str]:
    problems = []
    for key in ("description_path", "tools_path"):
        value = manifest.get(key)
        path = (root / str(value)).resolve()
        if not value or not path.is_relative_to(root.resolve()) or not path.is_file():
            problems.append(f"{key}: arquivo ausente ou fora do pacote.")
        elif not path.read_text(encoding="utf-8").strip():
            problems.append(f"{key}: arquivo vazio.")
    for key in ("video_url", "app_url", "pitch_url", "repository_url"):
        value = manifest.get(key)
        if (not isinstance(value, str) or urlsplit(value).scheme != "https"
                or not urlsplit(value).netloc):
            problems.append(f"{key}: informe uma URL HTTPS acessível à banca.")
            continue
        if check_links:
            urls = [value]
            if key == "app_url":
                urls.extend([value.rstrip("/") + "/health", value.rstrip("/") + "/health/db"])
            for url in urls:
                try:
                    req = Request(url, headers={"User-Agent": "Zelo-Submission-Check/1.0"})
                    with urlopen(req, timeout=10) as response:
                        if response.status != 200:
                            problems.append(f"{key}: HTTP {response.status} em {url}.")
                except HTTPError as exc:
                    problems.append(f"{key}: HTTP {exc.code} em {url}.")
                except (URLError, TimeoutError):
                    problems.append(f"{key}: URL indisponível: {url}.")
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-links", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/submission.json").read_text(encoding="utf-8"))
    problems = validate(manifest, root, args.check_links)
    print(json.dumps({"ready": not problems, "pending": problems}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if problems else 0)

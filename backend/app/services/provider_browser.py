"""Descoberta de prestadores no Maps pelo Agent Browser da Vercel, sem Places API."""

import asyncio
import contextlib
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import uuid4

from app.schemas.common import ProviderCategory
from app.services.provider_collector import CATEGORY_QUERIES, ProviderCandidate

READY_SCRIPT = r"""Boolean(
  document.querySelector('[role="article"]') ||
  location.hostname === 'consent.google.com' || location.pathname.startsWith('/sorry') ||
  document.querySelector('#captcha-form, iframe[src*="recaptcha"]') ||
  /Nenhum resultado|não encontrou|Não foi possível encontrar|No results found/i
    .test(document.body.innerText)
)"""

EXTRACT_SCRIPT = r"""(() => {
  if (location.hostname === 'consent.google.com' || location.pathname.startsWith('/sorry') ||
      document.querySelector('#captcha-form, iframe[src*="recaptcha"]')) {
    return {blocked: true, providers: []};
  }
  return {
    blocked: false,
    providers: Array.from(document.querySelectorAll('[role="article"]')).slice(0, 50).map(card => {
      const link = card.querySelector('a[href*="/maps/place/"]');
      return {
        name: link?.getAttribute('aria-label') || '',
        url: link?.href || '',
        text: card.innerText.slice(0, 4000)
      };
    })
  };
})()"""

PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?([1-9]\d)\)?[\s.-]+(9?\d{4})[\s.-]?(\d{4})\b")


class BrowserSearchError(RuntimeError):
    """Falha explícita de instalação, navegação ou extração; nunca retorna fixture."""


class AgentBrowserAdapter:
    def __init__(
        self,
        command: str = "",
        timeout_seconds: int = 35,
        executable_path: str = "",
    ) -> None:
        local = Path(__file__).resolve().parents[2] / "browser/node_modules/.bin/agent-browser"
        self.command = command or (str(local) if local.is_file() else "agent-browser")
        self.timeout_seconds = timeout_seconds
        self.executable_path = executable_path

    async def _run(self, session: str, *arguments: str) -> dict:
        if not shutil.which(self.command):
            raise BrowserSearchError("Agent Browser não instalado. Rode npm ci em backend/browser.")
        # Ambiente próprio: credenciais da aplicação não são herdadas pelo navegador.
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR", "XDG_RUNTIME_DIR", "DISPLAY", "LD_LIBRARY_PATH"}
            or key.startswith("AGENT_BROWSER_")
        }
        env["AGENT_BROWSER_DEFAULT_TIMEOUT"] = str(self.timeout_seconds * 1000)
        env["AGENT_BROWSER_IDLE_TIMEOUT_MS"] = "60000"
        if self.executable_path:
            env["AGENT_BROWSER_EXECUTABLE_PATH"] = self.executable_path
        process = await asyncio.create_subprocess_exec(
            self.command,
            "--session",
            session,
            "--json",
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), self.timeout_seconds + 5)
        except (TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.communicate()
            raise
        try:
            response = json.loads(stdout)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BrowserSearchError("Resposta inválida do Agent Browser.") from exc
        if (
            process.returncode
            or not isinstance(response, dict)
            or response.get("success") is not True
        ):
            raise BrowserSearchError(f"Agent Browser falhou na operação {arguments[0]}.")
        return response.get("data", {})

    async def search(
        self,
        category: ProviderCategory,
        region: str,
        limit: int = 5,
    ) -> list[ProviderCandidate]:
        if not region.strip() or len(region) > 100 or not 1 <= limit <= 20:
            raise ValueError("Região e limite (1 a 20) são obrigatórios")
        session = f"providers-{uuid4().hex}"
        query = quote(f"{CATEGORY_QUERIES[category]} em {region.strip()}", safe="")
        try:
            await self._run(
                session, "open", f"https://www.google.com/maps/search/{query}/?hl=pt-BR"
            )
            await self._run(session, "wait", "--fn", READY_SCRIPT)
            response = await self._run(session, "eval", EXTRACT_SCRIPT)
            extracted = response.get("result")
            if not isinstance(extracted, dict) or not isinstance(extracted.get("providers"), list):
                raise BrowserSearchError("Formato inesperado da página de resultados.")
            if extracted.get("blocked"):
                raise BrowserSearchError("Google Maps pediu consentimento ou bloqueou a navegação.")
            return parse_cards(extracted["providers"], category, region.strip(), limit)
        except TimeoutError as exc:
            raise BrowserSearchError("Tempo limite da busca no navegador excedido.") from exc
        finally:
            # Cada busca tem sessão isolada, encerrada inclusive após erro ou cancelamento.
            with contextlib.suppress(BrowserSearchError, TimeoutError, OSError):
                await self._run(session, "close")


def parse_cards(
    cards: list,
    category: ProviderCategory,
    region: str,
    limit: int,
) -> list[ProviderCandidate]:
    candidates: list[ProviderCandidate] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        name, url, body = (card.get(key) for key in ("name", "url", "text"))
        if not all(isinstance(value, str) and value.strip() for value in (name, url, body)):
            continue
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.google.com"
            or not parsed.path.startswith("/maps/place/")
        ):
            continue
        match = PHONE_RE.search(body)
        if not match:
            continue
        phone = f"+55{''.join(match.groups())}"
        if phone in seen:
            continue
        seen.add(phone)
        rating = next(
            (
                float(line.strip().replace(",", "."))
                for line in body.splitlines()
                if re.fullmatch(r"[1-5](?:[,.]\d)?", line.strip())
            ),
            None,
        )
        identity = re.search(r"!1s([^!/?]+)", parsed.path)
        stable_id = (
            identity.group(1) if identity else hashlib.sha256(parsed.path.encode()).hexdigest()[:24]
        )
        candidates.append(
            ProviderCandidate(
                place_id=f"maps:{stable_id}",
                name=name.strip()[:150],
                category=category,
                region=region,
                phone=phone,
                source="agent_browser",
                rating=rating if rating is not None and 1 <= rating <= 5 else None,
                source_url=url.split("?")[0],
            )
        )
        if len(candidates) >= limit:
            break
    return candidates

"""Valida boot e ciclo HTTP do Plano B em banco temporário, sem alterar a demo atual."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def check() -> dict[str, object]:
    started = time.monotonic()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    def request(path: str, data: dict[str, object] | None = None) -> object:
        req = Request(base + path, headers={"Content-Type": "application/json"},
                      data=json.dumps(data).encode() if data is not None else None)
        with urlopen(req, timeout=2) as response:
            return json.load(response)

    with tempfile.TemporaryDirectory(prefix="zelo-recorded-demo-") as directory:
        env = {
            **os.environ, "LLM_MODE": "recorded_demo", "ENVIRONMENT": "development",
            "DATABASE_URL": f"sqlite:///{directory}/demo.db", "PROVIDER_SOURCE": "fixture",
            "FEATHERLESS_API_KEY": "", "GOOGLE_PLACES_API_KEY": "",
            "LANGFUSE_PUBLIC_KEY": "mock-public", "LANGFUSE_SECRET_KEY": "mock-secret",
            "MAX_COST_GLOBAL_USD": "0", "RECORDED_DEMO_LATENCY_MS": "80",
        }
        with open(Path(directory) / "server.log", "w+") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", str(port)], cwd=Path(__file__).resolve().parents[1], env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                while True:
                    if server.poll() is not None:
                        raise RuntimeError(
                            "Servidor de contingência encerrou antes do healthcheck."
                        )
                    try:
                        health = request("/health")
                        break
                    except (URLError, TimeoutError):
                        if time.monotonic() - started >= 8:
                            raise RuntimeError("Boot da contingência excedeu 8 segundos.") from None
                        time.sleep(0.05)
                assert isinstance(health, dict) and health["llm_mode"] == "recorded_demo"
                boot_seconds = time.monotonic() - started
                property_id = "prop-copacabana-01"
                greeting = request("/api/chat", {
                    "property_id": property_id, "message": "Olá!", "sender_role": "tenant",
                })
                assert isinstance(greeting, dict) and greeting["response_text"]
                opened = request("/api/chat", {
                    "property_id": property_id, "sender_role": "cleaner",
                    "message": "A torneira da pia da cozinha quebrou e está vazando água no chão.",
                })
                assert isinstance(opened, dict)
                ticket_id = opened["ticket_id"]
                quotes = request(f"/api/tickets/{ticket_id}/quotes")
                assert isinstance(quotes, list) and len(quotes) >= 1
                for index, quote in enumerate(quotes):
                    assert quote["amount"] is None and quote["status"] == "requested"
                    request(f"/api/tickets/{ticket_id}/quotes/{quote['provider_id']}/response", {
                        "amount": 180 + index * 60, "description": "Reparo simulado da torneira.",
                    })
                approved = request(f"/api/tickets/{ticket_id}/approve", {
                    "provider_id": quotes[0]["provider_id"],
                })
                assert isinstance(approved, dict)
                assert approved["status"] == "waiting_date_confirmation"
                assert approved["scheduled_date"] is None
                refused = request(f"/api/tickets/{ticket_id}/date-response", {"accepted": False})
                assert isinstance(refused, dict)
                assert refused["status"] == "waiting_date_confirmation"
                confirmed = request(f"/api/tickets/{ticket_id}/date-response", {"accepted": True})
                assert isinstance(confirmed, dict) and confirmed["status"] == "resolved"
                assert confirmed["scheduled_date"]
                events = request(f"/api/audit?ticket_id={ticket_id}")
                assert isinstance(events, list)
                assert any(event["event_type"] == "tenant_notified" for event in events)
                costs = request("/api/costs/summary")
                assert isinstance(costs, dict) and costs["total_cost_usd"] == 0
                total_seconds = time.monotonic() - started
                if total_seconds >= 10:
                    raise RuntimeError(f"Plano B excedeu 10 segundos: {total_seconds:.2f}s.")
                return {"mode": "recorded_demo", "boot_seconds": round(boot_seconds, 3),
                        "full_flow_seconds": round(total_seconds, 3), "cost_usd": 0,
                        "quote_count": len(quotes), "status": "passed"}
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2))

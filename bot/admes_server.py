"""
Admes HTTP client: send questions to the remote tunnel server and poll for answers.

The remote server (exposed via Cloudflare tunnel) implements:
- POST /question  {"question": "..."} -> {"status": "accepted", "sequence": n}
- GET  /answer    -> {"sequence": n, "answer": "..."} (answer auto-clears after read)
"""

import time
from typing import Optional

import requests

ANSWER_TIMEOUT_SECONDS = 90.0

# Base URL of the remote Admes bridge (e.g., https://abcd.trycloudflare.com)
tunnel_url: Optional[str] = None


def _base_url() -> Optional[str]:
    if not tunnel_url:
        return None
    return tunnel_url.rstrip("/")


def init_admes_server(port: int = 0) -> None:
    """No-op for backward compatibility; remote server runs elsewhere."""
    if _base_url():
        print(f"Admes remote endpoint configured at {_base_url()}")
    else:
        print("Admes remote endpoint is not configured (owner: run /admes_tunnel to set it)")


def send_query(query: str, timeout: float = ANSWER_TIMEOUT_SECONDS) -> Optional[str]:
    """Send a question to the remote bridge and poll for an answer until timeout."""
    base = _base_url()
    if not base:
        return None

    try:
        resp = requests.post(
            f"{base}/question",
            json={"question": query},
            timeout=10,
        )
        if resp.status_code >= 400:
            return None
        data = resp.json()
        seq = data.get("sequence")
        if not isinstance(seq, int):
            return None
    except Exception as exc:
        print(f"Error posting question: {exc}")
        return None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            ans_resp = requests.get(f"{base}/answer", timeout=10)
            if ans_resp.status_code >= 400:
                time.sleep(1)
                continue
            ans_data = ans_resp.json()
            if ans_data.get("sequence") == seq:
                answer = ans_data.get("answer")
                if answer:
                    return answer
        except Exception:
            time.sleep(1)
            continue

        time.sleep(1)

    return None


def close_server() -> None:
    """No-op: nothing to close on the client side."""
    return


def get_tunnel_url() -> Optional[str]:
    return _base_url()


def set_tunnel_url(url: str) -> None:
    global tunnel_url
    tunnel_url = url

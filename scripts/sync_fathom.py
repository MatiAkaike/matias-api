#!/usr/bin/env python3
"""Descarga todas las reuniones de Fathom sin imprimir datos sensibles."""

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

API_URL = "https://api.fathom.ai/external/v1/meetings"
ENV_PATH = Path.home() / ".hermes" / ".env"
RAW_DIR = Path.home() / ".local" / "share" / "matias-oscar-graph" / "raw"
PAGES_PATH = RAW_DIR / "fathom_pages.ndjson"
MEETINGS_PATH = RAW_DIR / "fathom_meetings.json"
MANIFEST_PATH = RAW_DIR / "fathom_manifest.json"


def api_key() -> str:
    value = os.environ.get("FATHOM_API_KEY", "").strip()
    if value:
        return value
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(errors="ignore").splitlines():
            if line.startswith("FATHOM_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("FATHOM_API_KEY no disponible")


def fetch_page(key: str, cursor: str | None) -> dict:
    params = {
        "limit": "10",
        "include_summary": "true",
        "include_action_items": "true",
        "include_transcript": "true",
    }
    if cursor:
        params["cursor"] = cursor
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"X-Api-Key": key})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 7:
                raise
            retry_after = int(exc.headers.get("Retry-After", "0") or 0)
            time.sleep(max(retry_after, 20 * (attempt + 1)))
    raise RuntimeError("No fue posible descargar la página de Fathom")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(RAW_DIR, 0o700)
    # Un snapshot completo previo inicia una sincronización fresca; uno incompleto se reanuda.
    if MANIFEST_PATH.exists():
        PAGES_PATH.unlink(missing_ok=True)
        MANIFEST_PATH.unlink(missing_ok=True)
    key = api_key()
    cursor = None
    pages = 0
    meetings: list[dict] = []
    seen_ids: set[str] = set()

    # Reanudar desde el último cursor confirmado para sobrevivir al rate limit.
    if PAGES_PATH.exists():
        for line in PAGES_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            pages += 1
            for meeting in data.get("items", []):
                recording_id = str(meeting.get("recording_id", ""))
                dedupe_key = recording_id or str(meeting.get("url", ""))
                if dedupe_key and dedupe_key not in seen_ids:
                    seen_ids.add(dedupe_key)
                    meetings.append(meeting)
            cursor = data.get("next_cursor")

    with PAGES_PATH.open("a", encoding="utf-8") as pages_file:
        while True:
            if pages and not cursor:
                break
            data = fetch_page(key, cursor)
            pages += 1
            pages_file.write(json.dumps(data, ensure_ascii=False) + "\n")
            pages_file.flush()
            for meeting in data.get("items", []):
                recording_id = str(meeting.get("recording_id", ""))
                dedupe_key = recording_id or str(meeting.get("url", ""))
                if dedupe_key and dedupe_key not in seen_ids:
                    seen_ids.add(dedupe_key)
                    meetings.append(meeting)
            next_cursor = data.get("next_cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            time.sleep(2.1)

    meetings.sort(key=lambda item: item.get("created_at") or "")
    MEETINGS_PATH.write_text(json.dumps(meetings, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "pages": pages,
        "meetings": len(meetings),
        "with_transcript": sum(bool(item.get("transcript")) for item in meetings),
        "oldest_created_at": meetings[0].get("created_at") if meetings else None,
        "newest_created_at": meetings[-1].get("created_at") if meetings else None,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(PAGES_PATH, 0o600)
    os.chmod(MEETINGS_PATH, 0o600)
    os.chmod(MANIFEST_PATH, 0o600)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()

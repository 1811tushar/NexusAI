"""Streams one investigation from a RUNNING ai-service and prints the events (what Spring sees). Needs INTERNAL_API_KEY, a configured LLM, and the seeded data.
    python scripts/investigate_demo.py ["your question"] [--no-web]
If the run pauses for approval it prints the pending actions and asks whether to approve (a stand-in for the approver in the UI)."""
from __future__ import annotations

import json
import os
import sys
import uuid

import httpx

BASE = os.environ.get("AI_URL", "http://localhost:8000")
HEADERS = {"X-Internal-API-Key": os.environ["INTERNAL_API_KEY"]}
HERO = "Why did Q2 revenue decline compared to Q1, and what should management investigate?"


def stream(client: httpx.Client, url: str, payload: dict) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    with client.stream("POST", url, json=payload, headers=HEADERS, timeout=None) as r:
        if r.status_code != 200:
            print("HTTP", r.status_code, r.read().decode()[:400])
            sys.exit(1)
        name = ""
        for line in r.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                events.append((name, data))
                if name == "report_delta":
                    print(data["text"], end="", flush=True)
                else:
                    brief = {k: (v if not isinstance(v, (list, dict, str)) or len(str(v)) < 90 else str(v)[:90] + "...") for k, v in data.items()}
                    print(f"\n[{name}] {brief}")
    return events


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    question = args[0] if args else HERO
    thread = str(uuid.uuid4())
    payload = {"investigationId": 1, "threadId": thread, "userId": 1, "question": question, "now": "2026-10-14T09:00:00Z",
               "options": {"webSearch": "--no-web" not in sys.argv, "documentIds": None, "useMemory": True, "maxLoops": 3}}
    with httpx.Client() as c:
        events = stream(c, f"{BASE}/internal/investigate", payload)
        if events and events[-1][0] == "approval_required":
            actions = events[-1][1]["actions"]
            print("\n\nPAUSED: approval needed for", [(a["actionType"], a["params"]) for a in actions])
            ans = input("Approve all? [y/N] ").strip().lower() == "y"
            decisions = [{"actionKey": a["actionKey"], "approvalId": i + 1, "decision": "APPROVE" if ans else "REJECT", "decidedBy": "demo-approver", "comment": None}
                         for i, a in enumerate(actions)]
            stream(c, f"{BASE}/internal/investigate/{thread}/resume", {"investigationId": 1, "decisions": decisions})
    print()


if __name__ == "__main__":
    main()

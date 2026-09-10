"""Acceptance test for the React client: a real browser against a real server.

Replaces what the Godot headless suites checked, at the same level: a visitor
knocks, is let in, is answered in the learner's own words, the evidence lands,
the progress view shows the learner's own sentence back, and clearing the record
really starts over.

    .venv/bin/python -m uvicorn server.main:app --port 8000   # WEB_DIR=client/dist
    .venv/bin/python tools/e2e_room.py http://127.0.0.1:8000

Chrome path can be overridden with CHROME.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.shoot_page import CHROME, PORT, Session  # noqa: E402

ANSWER_CLARIFY = "I first confirm the public-official role, the applicable Germany-specific rule and how €26 compares with its threshold."
ANSWER_CONFLICT = "The linked payments total €12,000, splitting does not avoid the cash limit, and I will decline or escalate through the required process."
ANSWER_BOUNDARY = "We became aware at 10:00 today and the breach is high risk, so I will notify the authority within 72 hours and affected people without undue delay; I will document and coordinate the next steps now."

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok  {label}")
    else:
        failures.append(label)
        print(f"  BAD {label} — {detail}")


class Page:
    def __init__(self, session: Session) -> None:
        self.session = session

    def text(self) -> str:
        result = self.session.send(
            "Runtime.evaluate",
            expression="document.body.innerText",
            returnByValue=True,
        )
        return str(result.get("result", {}).get("value") or "")

    def wait_for(self, fragment: str, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if fragment.lower() in self.text().lower():
                return True
            time.sleep(0.4)
        return False

    def click_text(self, fragment: str) -> bool:
        """Dispatch a click on the first enabled button with matching visible text."""
        script = f"""
        (() => {{
          const target = [...document.querySelectorAll('button')]
            .find(b => b.innerText.toLowerCase().includes({json.dumps(fragment.lower())})
                       && !b.disabled);
          if (!target) return false;
          target.click();
          return true;
        }})()
        """
        result = self.session.send("Runtime.evaluate", expression=script, returnByValue=True)
        return bool(result.get("result", {}).get("value"))

    def answer(self, text: str) -> None:
        self.session.send(
            "Runtime.evaluate",
            expression="document.getElementById('answer-box').focus()",
        )
        time.sleep(0.2)
        self.session.type_text(text)
        time.sleep(0.2)
        self.session.key("Enter", 13)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    profile = tempfile.mkdtemp(prefix="e2e-")
    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--mute-audio",
            "--window-size=1280,900",
            f"--remote-debugging-port={PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            base,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        socket = ""
        while time.monotonic() < deadline and not socket:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    for target in json.loads(r.read().decode()):
                        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                            socket = target["webSocketDebuggerUrl"]
            except Exception:  # noqa: BLE001 - Chrome still starting
                time.sleep(0.4)
        page = Page(Session(socket))

        print("1) A fresh guest is knocked on, without walking anywhere")
        check("someone knocks", page.wait_for("knocking"), page.text()[:120])
        check("the first visit is the skill check", "skill check" in page.text().lower())
        check("the door prompt is on screen", "open the door" in page.text().lower())

        print("2) The visitor comes in and the lesson opens")
        check("the door opens", page.click_text("open the door"))
        check("a lesson starts", page.wait_for("your answer, in your own words"), page.text()[:160])
        check("no multiple-choice options are offered", "option" not in page.text().lower())

        print("3) The learner types their own answers")
        page.answer(ANSWER_CLARIFY)
        check("cash screening question arrives", page.wait_for("€12,000 commercial transaction"), page.text()[:200])
        check("evidence is recorded", "evidence recorded" in page.text().lower())
        page.answer(ANSWER_CONFLICT)
        check("breach screening question arrives", page.wait_for("high-risk breach"), page.text()[:200])
        page.answer(ANSWER_BOUNDARY)
        check("the skill check completes", page.wait_for("complete", 20), page.text()[:200])

        print("4) Progress shows the learner's own words back")
        check("progress opens", page.click_text("my progress"))
        check("progress view is visible", page.wait_for("what you have shown"), page.text()[:200])
        check("the passport lists a skill", page.wait_for("gather relevant facts"), page.text()[:200])
        check(
            "the evidence quotes the learner",
            "public-official role" in page.text().lower(),
            page.text()[:200],
        )
        check("a next step is offered", "what to do next" in page.text().lower())
        check("progress closes", page.click_text("close"))
        check("progress returns to the lesson", page.wait_for("mission: three-question starting check", 20), page.text()[:160])
        check("screening lesson closes", page.click_text("close"))

        print("5) Mira offers both grounded tasks")
        check("Alex knocks next", page.wait_for("Alex is knocking", 20), page.text()[:160])
        check("Alex task opens", page.click_text("open the door"))
        check("Alex lesson starts", page.wait_for("gifts and hospitality", 20), page.text()[:160])
        check("Alex lesson closes", page.click_text("close"))
        check("Sam knocks next", page.wait_for("Sam is knocking", 20), page.text()[:160])
        check("Sam task opens", page.click_text("open the door"))
        check("Sam lesson starts", page.wait_for("cash and customer checks", 20), page.text()[:160])
        check("Sam lesson closes", page.click_text("close"))
        check("Mira knocks next", page.wait_for("Mira is knocking", 20), page.text()[:160])
        check("Mira task chooser is visible", page.wait_for("choose a task", 20), page.text()[:160])
        check("Mira review opens", page.click_text("review a case from your record"))
        check("Mira review lesson starts", page.wait_for("mission: review a case from your record", 20), page.text()[:160])
        check("Mira review closes", page.click_text("close"))

        print("6) Clearing the record really starts over")
        check("clearing asks to confirm", page.click_text("clear my record"))
        check("the warning names what is deleted", page.wait_for("deletes every answer"))
        check("clearing confirmed", page.click_text("confirm clearing"))
        check("a fresh guest is knocked on again", page.wait_for("skill check", 20))
        check("progress opens on a clean record", page.click_text("my progress"))
        check(
            "no evidence survives the clear",
            page.wait_for("not yet verified") and "public-official role" not in page.text().lower(),
            page.text()[:200],
        )
    finally:
        chrome.terminate()
        shutil.rmtree(profile, ignore_errors=True)

    print()
    if failures:
        print(f"E2E FAILED ({len(failures)}):")
        for item in failures:
            print("  -", item)
        return 1
    print("E2E OK — knock, let in, answer in your own words, evidence, progress, clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())

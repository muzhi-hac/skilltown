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
ANSWER_ALEX_PASS = "Because this is a German public official and €26 exceeds the €25 threshold, I will decline or hand it to the employing office and keep the receipt in the register."
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
        check("the first visit is the three-situation check", "three quick situations" in page.text().lower())
        check("the door prompt is on screen", "open the door" in page.text().lower())

        print("2) The visitor comes in and the conversation opens")
        check("the door opens", page.click_text("open the door"))
        check("the conversation opens", page.wait_for("what do you say, in your own words"), page.text()[:160])
        check("no multiple-choice options are offered", "option" not in page.text().lower())

        print("3) The learner types their own answers")
        page.answer(ANSWER_CLARIFY)
        check("cash screening question arrives", page.wait_for("€12,000 commercial transaction"), page.text()[:200])
        check("evidence is recorded", "evidence recorded" in page.text().lower())
        page.answer(ANSWER_CONFLICT)
        check("breach screening question arrives", page.wait_for("high-risk breach"), page.text()[:200])
        page.answer(ANSWER_BOUNDARY)
        check("the three-situation check completes", page.wait_for("practice completed", 20), page.text()[:200])
        check(
            "the end of a path claims nothing about passing",
            "passed independently" not in page.text().lower(),
            page.text()[:200],
        )

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
        check("progress returns to the conversation", page.wait_for("situation: three-question starting check", 20), page.text()[:160])
        check(
            "the finished situation points at the next visitor",
            page.wait_for("next visitor", 10),
            page.text()[:160],
        )
        check("the three-situation check closes", page.click_text("next visitor"))

        print("5) The person in the room pushes back before anything is revealed")
        check("Alex knocks first", page.wait_for("Alex is knocking", 20), page.text()[:160])
        check("Alex comes in", page.click_text("open the door"))
        check("Alex speaks first", page.wait_for("thank-you note", 20), page.text()[:200])
        check("nobody is teaching", "teacher" not in page.text().lower())
        page.answer("€26 is a small gift, so I will accept it.")
        check("Alex pushes back", page.wait_for("round 1/4", 20), page.text()[:200])
        pressed = page.text().lower()
        check("no verdict is revealed mid-arc", "evidence recorded" not in pressed and "learning feedback" not in pressed, pressed[:200])
        check("the rules stay one click away", "check the rules" in pressed)
        page.answer(ANSWER_ALEX_PASS)
        check("holding the line moves the situation on", page.wait_for("evidence recorded", 20), page.text()[:200])
        check("the situation closes", page.click_text("close"))

        print("6) Every visitor has their own tasks")
        check("Sam knocks next", page.wait_for("Sam is knocking", 40), page.text()[:160])
        check("Sam task opens", page.click_text("open the door"))
        check("Sam opens with cash on the counter", page.wait_for("cash and customer checks", 20), page.text()[:160])
        check("Sam situation closes", page.click_text("close"))
        # Who knocks next follows this learner's record, so walk until the coach.
        reached_mira = False
        for _ in range(5):
            if page.wait_for("Mira is knocking", 12):
                reached_mira = True
                break
            page.click_text("open the door")
            time.sleep(1.5)
            page.click_text("close")
            time.sleep(1.5)
        check("Mira knocks once the others have been seen", reached_mira, page.text()[:160])
        check("Mira review opens", page.click_text("open the door"))
        check("Mira review opens as a conversation", page.wait_for("situation: review a case from your record", 20), page.text()[:160])
        check("Mira review closes", page.click_text("close"))

        print("7) Clearing the record really starts over")
        check("clearing asks to confirm", page.click_text("clear my record"))
        check("the warning names what is deleted", page.wait_for("deletes every answer"))
        check("clearing confirmed", page.click_text("confirm clearing"))
        check("a fresh guest is knocked on again", page.wait_for("three quick situations", 20))
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
    print("E2E OK — knock, let in, answer in your own words, get pushed back, evidence, progress, clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())

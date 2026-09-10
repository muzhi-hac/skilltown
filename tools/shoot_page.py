"""Screenshot the running game through the Chrome DevTools Protocol.

Chrome's --screenshot flag fires as soon as the page loads, which for a
WebAssembly game captures the loading bar and nothing else. This drives a real
Chrome over CDP instead: wait for the engine to boot, then capture - and
optionally click something first, so a lesson can be photographed too.

    .venv/bin/python tools/shoot_page.py <url> <out.png> [--wait 30] [--click X,Y]
    .venv/bin/python tools/shoot_page.py <url> <out.png> --click 640,640 --wait 22 --then 6

Chrome path can be overridden with CHROME.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

CHROME = os.getenv(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
PORT = int(os.getenv("CDP_PORT", "9333"))


def launch(url: str, profile: str) -> subprocess.Popen:
    return subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--enable-unsafe-swiftshader",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--mute-audio",
            "--hide-scrollbars",
            "--window-size=1280,800",
            f"--remote-debugging-port={PORT}",
            # Chrome rejects CDP sockets from an origin it was not told about.
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def page_socket(timeout: float = 30.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                for target in json.loads(r.read().decode()):
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
        except Exception:  # noqa: BLE001 - Chrome is still starting
            pass
        time.sleep(0.5)
    raise RuntimeError("Chrome never exposed a page target")


class Session:
    def __init__(self, socket_url: str) -> None:
        self.ws = websocket.create_connection(socket_url, timeout=60)
        self.next_id = 0

    def send(self, method: str, **params):
        self.next_id += 1
        self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == self.next_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def click(self, x: int, y: int) -> None:
        for kind in ("mousePressed", "mouseReleased"):
            self.send(
                "Input.dispatchMouseEvent",
                type=kind,
                x=x,
                y=y,
                button="left",
                buttons=1,
                clickCount=1,
            )
            time.sleep(0.05)

    def type_text(self, text: str) -> None:
        self.send("Input.insertText", text=text)

    def key(self, key: str, code: int) -> None:
        for kind in ("keyDown", "keyUp"):
            self.send(
                "Input.dispatchKeyEvent",
                type=kind,
                key=key,
                windowsVirtualKeyCode=code,
                nativeVirtualKeyCode=code,
            )
            time.sleep(0.05)

    def shot(self, path: str) -> None:
        result = self.send("Page.captureScreenshot", format="png")
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(result["data"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("out")
    parser.add_argument("--wait", type=float, default=25.0, help="seconds to let the game boot")
    parser.add_argument("--click", default="", help="X,Y to click before the second shot")
    parser.add_argument("--type", default="", help="text to type after clicking")
    parser.add_argument("--then", type=float, default=6.0, help="seconds to wait after clicking")
    args = parser.parse_args()

    profile = tempfile.mkdtemp(prefix="shoot-")
    chrome = launch(args.url, profile)
    try:
        session = Session(page_socket())
        print(f"booting for {args.wait:.0f}s…")
        time.sleep(args.wait)
        session.shot(args.out)
        print(f"saved {args.out}")
        if args.click:
            x, y = (int(part) for part in args.click.split(","))
            session.click(x, y)
            if args.type:
                time.sleep(1.0)
                session.type_text(args.type)
                session.key("Enter", 13)
            time.sleep(args.then)
            second = args.out.replace(".png", "-after.png")
            session.shot(second)
            print(f"saved {second}")
    finally:
        chrome.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

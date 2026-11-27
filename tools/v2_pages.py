"""Correct one fictional coin's explorer pages during a live run, safely when two runs share the repositories.

Used by tools/live_v2_money.py (Studio) and tools/live_v2_bradbury.py (Bradbury). The pages are made by
tools/make_v2_pages.py; which coins are already corrected is read from the page files themselves (so one run
never undoes another run's correction), and a file lock keeps two runs from committing at the same time.

A correction commit holds the corrected pages only (whatever else is staged stays out of it), and it is refused
when the repository has local commits that are not on GitHub yet: pushing would publish them with it. Only main
is pushed; the milestone branch is brought up to date once, when the milestone is submitted.
"""
import fcntl
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A_URL = "https://checker.brilliantnodes.com/v2/{c}-block-1.html"
B_URL = "https://brilliantnodes.github.io/demo-explorer/{c}/block-1.html"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_v2_pages import CORRECTABLE  # noqa: E402  (one list, in the page generator)
MARK_A, MARK_B = "Correction (fictional)", "Data correction (fictional)"
SIGN = "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01PmboiXeSxAX9LMvc5cn1bn\n"


def corrected_now(demo: Path) -> list:
    """The coins whose Blockfield page already shows a correction (every correctable coin corrects page B)."""
    return [c for c in CORRECTABLE if (demo / c / "block-1.html").exists() and MARK_B in (demo / c / "block-1.html").read_text()]


def live(url: str, text: str, tries: int = 48) -> bool:
    """True once the public page shows the text, fetched both with a cache-busting query and as the bare address
    (the validators fetch the bare address)."""
    for _ in range(tries):
        try:
            ok = True
            for u in (url + f"?nocache={int(time.time())}", url):
                req = urllib.request.Request(u, headers={"User-Agent": "lcc2-live", "Cache-Control": "no-cache"})
                ok = ok and text in urllib.request.urlopen(req, timeout=20).read().decode()
            if ok:
                return True
        except Exception:
            pass
        time.sleep(15)
    return False


def correct(coin: str, run: str, demo: Path, checker: Path = ROOT, wait=None) -> dict:
    """Write and push the corrected pages for one coin. Returns {coin, commits, live, at}. `wait` is called while
    waiting for the public pages, so a run can send its due transactions meanwhile."""
    with open("/tmp/lcc2-pages.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        done = sorted(set(corrected_now(demo)) | {coin})
        subprocess.run([sys.executable, str(checker / "tools" / "make_v2_pages.py"), str(checker / "web" / "public"), str(demo),
                        "--corrected", ",".join(done)], check=True, capture_output=True)
        shutil.copytree(checker / "web" / "public" / "v2", checker / "docs" / "v2", dirs_exist_ok=True)
        msg = f"Fictional explorer data correction for {coin} ({run} of Launch Claim Checker v2){SIGN}"
        commits = {}
        for repo, paths, branches, side in ((checker, ["web/public/v2", "docs/v2"], ["main"], "a"),
                                            (demo, [coin], ["main"], "b")):  # the coin's own pages only
            if side not in CORRECTABLE[coin]:
                commits[repo.name] = None  # this explorer does not change for this coin
                continue
            subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin", "main"], check=True, capture_output=True)
            ahead = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", "origin/main..HEAD"], capture_output=True, text=True, check=True)
            if ahead.stdout.strip() != "0":
                raise RuntimeError(f"{repo.name}: {ahead.stdout.strip()} local commit(s) not on GitHub; push them before the run")
            subprocess.run(["git", "-C", str(repo), "add", *paths], check=True)
            r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=Brilliant Nodes", "-c", "user.email=noreply@brilliantnodes.com",
                                "commit", "-q", "-m", msg, "--", *paths], capture_output=True, text=True)
            if r.returncode == 0:
                for b in branches:
                    pushed = False
                    for attempt in range(3):
                        if subprocess.run(["git", "-C", str(repo), "-c", "push.negotiate=true", "push", "-q", "origin", f"HEAD:{b}"],
                                          capture_output=True).returncode == 0:
                            pushed = True
                            break
                        if b == "main":
                            # someone else pushed to main meanwhile (it happened on 25 Nov): put this commit on top and retry
                            subprocess.run(["git", "-C", str(repo), "pull", "-q", "--rebase", "--autostash", "origin", "main"], capture_output=True)
                        time.sleep(5)
                    if not pushed and b == "main":
                        # a correction that is not published must stop the run: a re-check would read the old page
                        raise RuntimeError(f"{repo.name}: the correction for {coin} could not be pushed to main")
            commits[repo.name] = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    state = {}
    for side, url, mark in (("a", A_URL, MARK_A), ("b", B_URL, MARK_B)):
        if side in CORRECTABLE[coin]:
            state[side] = False
            for _ in range(60):  # at most about 15 minutes
                if live(url.format(c=coin), mark, tries=1):
                    state[side] = True
                    break
                if wait:
                    wait()
                time.sleep(15)
        else:
            state[side] = None
    return {"coin": coin, "commits": commits, "live": state, "at": int(time.time())}

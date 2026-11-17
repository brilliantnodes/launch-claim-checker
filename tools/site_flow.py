#!/usr/bin/env python3
"""Use the bounties page as a visitor would, in a headless browser, against the deployed Studio contract.

    pip install playwright genlayer-py==0.18.0 && playwright install chromium
    python tools/site_flow.py [page address] [record.json]

Defaults: https://checker.brilliantnodes.com/bounties.html and
examples/live/bounties-site-studio.json.

Every step is a click on the page: temporary accounts, an example, post, file
a sealed claim, reveal and judge, withdraw. The page makes the keys, the salt
and the digest in the browser; this script holds none of them. After each
click the transaction hash is read from the page. At the end every
transaction is read back from Studio and recorded with what the chain has:
sender, method and arguments (decoded from the call data), value, consensus
result, execution result and return value. All coins are fictional.
"""
import base64
import json
import sys
import time
from pathlib import Path

from genlayer_py.abi import calldata
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import client, read, summary, tx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://checker.brilliantnodes.com/bounties.html"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "examples" / "live" / "bounties-site-studio.json"
ENDINGS = ("Accepted", "refused", "did not", "Not settled", "does not hold")
rec = {"page": URL, "network": "GenLayer Studio (studionet)", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": [], "page_errors": []}


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


with sync_playwright() as p:
    browser = p.chromium.launch()
    pg = browser.new_page(viewport={"width": 1000, "height": 1400})
    pg.on("pageerror", lambda e: rec["page_errors"].append(str(e)[:300]))
    pg.goto(URL, wait_until="networkidle")
    time.sleep(4)
    rec["contract"] = pg.inner_text("#foot-contract").split()[-1] if pg.locator("#foot-contract").count() else None

    def done(what, seconds=480):
        """Wait for the page to report how the transaction ended; return the hash and the note it shows."""
        end = time.time() + seconds
        note, h = "", None
        before = {s["tx"] for s in rec["steps"]}
        time.sleep(2)
        while time.time() < end:
            note = pg.inner_text("#life-note")
            code = pg.locator("#life-hash code")
            h = code.first.inner_text().strip() if code.count() else None
            if h not in before and any(note.startswith(e) or e in note[:60] for e in ENDINGS):
                break
            time.sleep(3)
        rec["steps"].append({"n": len(rec["steps"]) + 1, "click": what, "page_says": note, "tx": h})
        save()
        print(f"{len(rec['steps']):2d} {what}: {note[:110]} {h}", flush=True)
        time.sleep(4)
        return note

    for role in ("poster", "hunter"):
        pg.click(f'[data-temp="{role}"]')
        pg.click(f'[data-fund="{role}"]')
        time.sleep(6)
    rec["accounts"] = {role: pg.inner_text(f"#{role}-addr").split()[-1] for role in ("poster", "hunter")}

    newest = lambda: pg.locator("#list article").first  # noqa: E731

    # 1. A claim that is false, rule P1: Examplecoin's block 1 pays its founders.
    pg.click('[data-example="exmFounder"]')
    pg.click("#btn-post")
    done("Example 'Examplecoin, no founder reward', then 'Post the bounty as Poster'")
    newest().get_by_role("button", name="File block claim").click()
    done("'File block claim' on the new bounty, as Hunter, block 1")
    newest().locator("details summary").first.click()
    rec["filing_as_the_page_shows_it_before_the_reveal"] = newest().locator("details").first.inner_text()[:600]
    newest().get_by_role("button", name="Judge", exact=True).click()
    done("'Judge': the page reveals the rule, block and salt it kept")
    rec["bounty_1_as_the_page_shows_it"] = newest().inner_text()[:900]

    # 2. A claim that is false, rule M1: one miner has most of Examplecoin's blocks.
    pg.click('[data-example="exmMining"]')
    pg.click("#btn-post")
    done("Example 'Examplecoin, decentralized mining', then 'Post the bounty as Poster'")
    newest().get_by_role("button", name="File mining claim").click()
    done("'File mining claim' on the new bounty, as Hunter")
    newest().get_by_role("button", name="Judge", exact=True).click()
    done("'Judge'")

    # 3. A claim that holds: Controlcoin's block 1 has only the block reward.
    pg.click('[data-example="ctlPremine"]')
    pg.click("#btn-post")
    done("Example 'Controlcoin, no premine', then 'Post the bounty as Poster'")
    newest().get_by_role("button", name="File block claim").click()
    done("'File block claim' on the new bounty, as Hunter, block 1")
    newest().get_by_role("button", name="Judge", exact=True).click()
    done("'Judge'")
    rec["bounty_3_as_the_page_shows_it"] = newest().inner_text()[:900]

    # The hunter takes the two pots.
    pg.locator("#hunter-bal button").click()
    done("'Withdraw' next to the Hunter's balance")
    browser.close()

# What the chain has for each of those transactions.
c, _acct = client()
for s in rec["steps"]:
    if not s["tx"]:
        continue
    t = tx(c, s["tx"])
    try:
        call = calldata.decode(base64.b64decode((t.get("data") or {}).get("calldata") or ""))
    except Exception:
        call = {}
    s["on_chain"] = {"from": t.get("from_address"), "to": t.get("to_address"), "value": str(t.get("value") or 0), "method": call.get("method"), "args": call.get("args"), **summary(t)}
    rec["contract"] = rec.get("contract") or t.get("to_address")
want = [("post_bounty", None), ("file_claim", None), ("judge", "PAYS_P1"), ("post_bounty", None), ("file_claim", None), ("judge", "PAYS_M1"),
        ("post_bounty", None), ("file_claim", None), ("judge", "NO_PAY"), ("withdraw", None)]
ok = len(rec["steps"]) == len(want)
for s, (method, outcome) in zip(rec["steps"], want):
    oc = s.get("on_chain") or {}
    r = oc.get("returned") if isinstance(oc.get("returned"), dict) else {}
    good = oc.get("method") == method and oc.get("execution") == "SUCCESS" and r.get("ok", True) is not False and (outcome is None or r.get("outcome") == outcome)
    good = good and str(oc.get("from", "")).lower() == rec["accounts"]["hunter" if method != "post_bounty" else "poster"].lower()
    s["as_expected"] = good
    ok = ok and good
rec["totals_after"] = read(c, rec["contract"], "totals")
rec["summary"] = {"clicks_that_sent_a_transaction": len(rec["steps"]), "as_expected": sum(1 for s in rec["steps"] if s.get("as_expected")), "page_errors": len(rec["page_errors"])}
save()
print(json.dumps(rec["summary"]))
sys.exit(0 if ok and not rec["page_errors"] else 1)

#!/usr/bin/env python3
"""Run the network probe on GenLayer Studio and write what was measured, with every transaction hash.

    python tools/probes/run_probe.py [examples/live/network-probes-studio.json]

A throwaway key is made for the run and funded from Studio's faucet. Test GEN only.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bounty import G, balance, client, fund, read, send, summary, wait  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "live" / "network-probes-studio.json"
SITE = "https://checker.brilliantnodes.com/examples"
c, acct = client()
fund(c, acct.address, 20)
h = c.deploy_contract(code=Path(__file__).with_name("probe.py").read_text())
t = wait(c, h)
addr = (t.get("data") or {}).get("contract_address") or t.get("to_address")
rec = {"network": "genlayer-studio", "probe_source": "tools/probes/probe.py", "account": acct.address, "address": addr, "deploy_tx": h, "measurements": []}


def save():
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n")


def settled():
    """Balances once nothing is on its way."""
    time.sleep(12)
    return balance(c, addr), balance(c, acct.address)


def measure(question, fn, args, value=0, finding=None):
    before = settled()
    try:
        tx, r = send(c, addr, fn, args, value=value)
    except Exception as e:  # the client refused to build the call
        tx, r = None, {"status": "NOT SENT", "execution": str(e)[:200], "returned": None, "created_at": None}
    after = settled()
    row = {"question": question, "method": fn, "args": args, "value": str(value), "tx": tx, "status": r["status"], "execution": r["execution"],
           "returned": r["returned"], "created_at": r["created_at"], "contract_balance_change": str(after[0] - before[0]), "sender_balance_change": str(after[1] - before[1])}
    row["finding"] = finding(row) if finding else None
    rec["measurements"].append(row)
    save()
    print(json.dumps({k: (v if k != "returned" else str(v)[:300]) for k, v in row.items()}), flush=True)
    return row


measure("Which time does a contract see for a transaction?", "stamp", ["a"],
        finding=lambda r: {"contract_saw": r["returned"], "transaction_created_at": r["created_at"],
                           "same_to_the_microsecond": str(r["returned"]).replace("Z", "+00:00") == str(r["created_at"]).replace("Z", "+00:00")})
measure("A payable call that raises: where is the GEN?", "pay_raise", [], value=G // 100,
        finding=lambda r: {"call_failed": r["execution"] == "ERROR", "gen_stayed_in_the_contract": r["contract_balance_change"] == str(G // 100)})
measure("A payable call with one argument too many: where is the GEN?", "pay_ok", ["extra"], value=G // 100,
        finding=lambda r: {"call_failed": r["execution"] == "ERROR", "gen_stayed_in_the_contract": r["contract_balance_change"] == str(G // 100)})
measure("GEN sent with a call that takes none: where is the GEN?", "stamp", ["b"], value=G // 100,
        finding=lambda r: {"call_failed": r["execution"] == "ERROR", "gen_stayed_in_the_contract": r["contract_balance_change"] == str(G // 100)})
text = "1|0xabc|P1|1|" + "5a" * 16
measure("Does sha256 give the same digest inside a contract?", "digest", [text],
        finding=lambda r: {"same_as_python": r["returned"] == hashlib.sha256(text.encode()).hexdigest()})
measure("What does web.render return for a table?", "look", [f"{SITE}/bounty/examplecoin/block/1.html"],
        finding=lambda r: {"a_table_row_is_one_line": "\n0 2,000,000.00000000 EXM Founders allocation address exm1qfounders00000000000000000000000\n" in str((r["returned"] or {}).get("text"))})
measure("What does web.render do with a page that does not exist?", "look", [f"{SITE}/bounty/examplecoin/block/7.html"],
        finding=lambda r: {"render_raised": (r["returned"] or {}).get("ok") is False})
measure("Does web.render follow a redirect without saying so?", "look", [f"http://checker.brilliantnodes.com/examples/bounty/controlcoin/block/1.html"],
        finding=lambda r: {"page_text_returned_with_no_sign_of_the_redirect": (r["returned"] or {}).get("ok") is True and "Controlcoin explorer: block 1" in str((r["returned"] or {}).get("text"))})
rec["contract_log"] = read(c, addr, "get_log")
save()
print("written", OUT)

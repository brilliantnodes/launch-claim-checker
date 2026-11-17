#!/usr/bin/env python3
"""Command-line client for LaunchClaimBounties on GenLayer Studio. Test GEN only.

  python tools/bounty.py deploy
  python tools/bounty.py rules | totals | latest
  python tools/bounty.py show <id>
  python tools/bounty.py post <CLAIM_TYPE> <subject> <block_url_template|-> <mining_url|-> <minutes> <pot GEN> [min_blocks]
  python tools/bounty.py file <id> <P1|M1> [height]        # files a sealed claim; pays the bounty's fee, which is burned
  python tools/bounty.py judge <id>                          # only the filer, within 30 minutes: reveals the claim
  python tools/bounty.py finalize <id> | reclaim <id> | withdraw

The contract address comes from LCB_ADDRESS. The signing key is read from the
file named in LCB_KEY_FILE (one hex key; created if missing; never printed).
Studio's own faucet funds the key.

A filing is sealed: the chain sees only sha256("<id>|<address>|<rule>|<block>|<salt>").
`file` keeps the rule, block and salt in <LCB_KEY_FILE>.claims.json so that
`judge` can reveal them. Lose that file and the filing cannot be judged.
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.abi import calldata
from genlayer_py.chains import studionet

ROOT = Path(__file__).resolve().parents[1]
G = 10**18
DONE = ("ACCEPTED", "FINALIZED")
FAILED = ("UNDETERMINED", "CANCELED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT")


def load_account(key_file):
    p = Path(key_file)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("0x" + secrets.token_hex(32))
        p.chmod(0o600)
    return create_account(p.read_text().strip())


def new_salt() -> str:
    return secrets.token_hex(16)


def seal(bounty_id, address, rule, height, salt) -> str:
    """The digest a filing carries; the contract recomputes it at the reveal."""
    return hashlib.sha256(f"{bounty_id}|{str(address).lower()}|{rule}|{int(height)}|{salt}".encode("utf-8")).hexdigest()


def claims_file(key_file) -> Path:
    return Path(str(key_file) + ".claims.json")


def remember(key_file, address, bounty_id, rule, height, salt) -> None:
    p = claims_file(key_file)
    kept = json.loads(p.read_text()) if p.exists() else {}
    kept[f"{str(address).lower()}:{bounty_id}"] = {"rule": rule, "height": int(height), "salt": salt}
    p.write_text(json.dumps(kept, indent=1) + "\n")
    p.chmod(0o600)


def recall(key_file, address, bounty_id) -> dict:
    p = claims_file(key_file)
    kept = json.loads(p.read_text()) if p.exists() else {}
    return kept.get(f"{str(address).lower()}:{bounty_id}") or {}


def client(key_file=None):
    acct = load_account(key_file) if key_file else create_account()
    return create_client(chain=studionet, account=acct), acct


def rpc(c, method, params, tries=6):
    """A read-only request. Studio's gateway sometimes answers with an error page for a few seconds, so it is asked again."""
    for attempt in range(tries):
        try:
            r = c.provider.make_request(method=method, params=params)
            return r.get("result", r) if isinstance(r, dict) else r
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5)


def fund(c, addr, gen=20):
    """Studio's built-in faucet."""
    return rpc(c, "sim_fundAccount", [addr, gen * G])


def balance(c, addr) -> int:
    r = rpc(c, "eth_getBalance", [addr, "latest"])
    return int(r, 16) if isinstance(r, str) else int(r)


def tx(c, h) -> dict:
    return rpc(c, "eth_getTransactionByHash", [h]) or {}


def wait(c, h, seconds=900) -> dict:
    """Wait until the transaction is decided; Studio's gateway sometimes errors for a few seconds."""
    end = time.time() + seconds
    t = {}
    while time.time() < end:
        try:
            t = tx(c, h)
            if t.get("status") in DONE + FAILED:
                return t
        except Exception:
            pass
        time.sleep(4)
    return t


def decoded(t: dict):
    """What the call returned (or the error text), from the leader's receipt."""
    lr = (t.get("consensus_data") or {}).get("leader_receipt")
    lr = lr[0] if isinstance(lr, list) and lr else (lr or {})
    res = lr.get("result")
    payload = res.get("payload") if isinstance(res, dict) else res
    out = payload
    if isinstance(payload, str):
        try:
            raw = base64.b64decode(payload)
            out = calldata.decode(raw[1:]) if raw[:1] == b"\x00" else raw[1:].decode("utf-8", "replace")
        except Exception:
            out = payload
    elif isinstance(payload, dict) and "readable" in payload:
        out = payload["readable"]
    return lr.get("execution_result"), out


def summary(t: dict) -> dict:
    execution, returned = decoded(t)
    votes = (t.get("consensus_data") or {}).get("votes") or {}
    return {
        "status": t.get("status"), "result": t.get("result_name"), "execution": execution, "returned": returned,
        "created_at": t.get("created_at"), "rotations": t.get("rotation_count"),
        "votes": {"agree": sum(1 for v in votes.values() if v == "agree"), "of": len(votes)},
    }


def sent_since(c, addr, sender, since) -> list:
    """Hashes of the transactions `sender` sent to the contract at or after unix time `since`, oldest first."""
    from datetime import datetime

    out = []
    for t in rpc(c, "sim_getTransactionsForAddress", [sender]) or []:
        try:
            at = datetime.fromisoformat(str(t.get("created_at")).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if at >= since and str(t.get("to_address", "")).lower() == addr.lower() and str(t.get("from_address", "")).lower() == sender.lower():
            out.append((at, t["hash"]))
    return [h for _at, h in sorted(out)]


def send(c, addr, fn, args, value=0) -> tuple:
    """One send only: a retry would be a second transaction. If the gateway fails while the send is being
    confirmed, the transaction may still have gone out: it is looked for on the chain, never sent again."""
    t0 = time.time()
    try:
        h = c.write_contract(address=addr, function_name=fn, args=args, value=value)
    except Exception as e:
        h = None
        for _ in range(12):
            time.sleep(10)
            found = sent_since(c, addr, c.account.address, t0 - 30)
            if found:
                h = found[-1]
                break
        if h is None:
            raise RuntimeError(f"{fn}: the send was not confirmed and no transaction was found on the chain: {str(e)[:200]}") from e
    return h, summary(wait(c, h))


def read(c, addr, fn, args=None, tries=6):
    for attempt in range(tries):
        try:
            return c.read_contract(address=addr, function_name=fn, args=args or [])
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5)


def deploy(c) -> dict:
    """One deployment only. If the gateway fails while it is being confirmed, the deployment this
    account sent is looked for on the chain; it is never sent again."""
    from datetime import datetime

    code = (ROOT / "contracts" / "launch_claim_bounties.py").read_text()
    t0 = time.time()
    try:
        h = c.deploy_contract(code=code)
    except Exception as e:
        h, me = None, c.account.address.lower()
        for _ in range(12):
            time.sleep(10)
            for t in rpc(c, "sim_getTransactionsForAddress", [c.account.address]) or []:
                try:
                    at = datetime.fromisoformat(str(t.get("created_at")).replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if at >= t0 - 30 and str(t.get("from_address", "")).lower() == me and (t.get("data") or {}).get("contract_code"):
                    h = t["hash"]
            if h:
                break
        if h is None:
            raise RuntimeError(f"the deployment was not confirmed and no transaction was found on the chain: {str(e)[:200]}") from e
    t = wait(c, h)
    addr = (t.get("data") or {}).get("contract_address") or t.get("to_address")
    return {"tx": h, "address": addr, **{k: v for k, v in summary(t).items() if k != "returned"}}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, a = sys.argv[1], sys.argv[2:]
    key_file = os.environ.get("LCB_KEY_FILE")
    c, acct = client(key_file)
    show = lambda x: print(json.dumps(x, indent=2, default=str))
    if cmd == "deploy":
        fund(c, acct.address)
        show(deploy(c))
        return
    addr = os.environ.get("LCB_ADDRESS")
    if not addr:
        raise SystemExit("set LCB_ADDRESS to the contract address")
    now = int(time.time())
    if cmd in ("rules", "totals"):
        show(read(c, addr, "get_rules" if cmd == "rules" else "totals"))
    elif cmd == "latest":
        for b in read(c, addr, "get_latest", [20, now]):
            print(b["id"], b["state"], b["claim_type"], b["subject_name"], int(b["pot"]) / G, "GEN")
    elif cmd == "show":
        show(read(c, addr, "get_bounty", [a[0], now]))
    elif cmd == "post":
        fund(c, acct.address)
        tpl, mine = ("" if x == "-" else x for x in (a[2], a[3]))
        args = [a[0], a[1], tpl, mine, now + int(float(a[4]) * 60), int(a[6]) if len(a) > 6 else 1000]
        show(send(c, addr, "post_bounty", args, value=int(float(a[5]) * G)))
    elif cmd == "file":
        fund(c, acct.address)
        if not key_file:
            raise SystemExit("set LCB_KEY_FILE: the same key, and the salt kept beside it, are needed to judge the filing")
        fee = int(read(c, addr, "get_bounty", [a[0], now])["fee"])
        rule, height, salt = a[1], int(a[2]) if len(a) > 2 else 0, new_salt()
        remember(key_file, acct.address, a[0], rule, height, salt)  # before sending: a filing without its salt is lost
        show(send(c, addr, "file_claim", [a[0], seal(a[0], acct.address, rule, height, salt)], value=fee))
    elif cmd == "judge":
        k = recall(key_file, acct.address, a[0]) if key_file else {}
        if not k:
            raise SystemExit("no sealed claim kept for this key and bounty; file one first")
        show(send(c, addr, "judge", [a[0], k["rule"], k["height"], k["salt"]]))
    elif cmd in ("finalize", "reclaim"):
        show(send(c, addr, cmd, [a[0]]))
    elif cmd == "withdraw":
        show(send(c, addr, "withdraw", [0]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

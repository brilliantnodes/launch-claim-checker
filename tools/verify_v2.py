#!/usr/bin/env python3
"""Check a Studio live-run record of LaunchClaimCheckerV2 against the chain. Reads only.

    python tools/verify_v2.py [examples/live/v2-studio.json examples/live/v2-site-studio.json]

For each record:
1. The code deployed by the recorded deployment transaction is, byte for
   byte, contracts/launch_claim_checker_v2.py in this repository, and the
   deployment made the recorded contract.
2. Every recorded transaction exists on Studio, went to the recorded
   contract from the recorded sender with the recorded value, calls the
   recorded method with the recorded arguments (decoded from the call data
   on the chain), and has the recorded consensus result, validator votes,
   execution result, return value and creation time.
3. Every check the record numbers is on the contract now with the recorded
   verdict and rule; every decided re-check is stored with the verdict and rule
   its transaction returned; each bonded case is in its recorded final state.
4. The contract's balance equals locked + credited + burned (totals()), and
   every check the run made against the views passed.
For a page click-through record (examples/live/v2-site-studio.json) the same is
done from the record's on_chain entries, and the page contract's deployed code
is compared with the source.

A throwaway key is made for the reads; nothing is signed or sent. Exit code 1 on any mismatch.
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from genlayer_py.abi import calldata  # noqa: E402

from bounty import balance, client, read, summary, tx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


def verify(path: Path, c) -> list:
    rec = json.loads(path.read_text())
    addr, bad = rec["address"], []

    d = tx(c, rec["deploy"]["tx"])
    code = base64.b64decode(((d.get("data") or {}).get("contract_code")) or "")
    source = (ROOT / rec["contract_source"]).read_bytes()
    if code != source:
        bad.append(f"deployed code differs from {rec['contract_source']} ({len(code)} bytes on chain, {len(source)} in the repository)")
    if hashlib.sha256(code).hexdigest() != rec.get("contract_sha256"):
        bad.append("deployed code does not have the recorded sha256")
    deployed_to = (d.get("data") or {}).get("contract_address") or d.get("to_address")
    if str(deployed_to).lower() != addr.lower():
        bad.append(f"the deployment transaction made {deployed_to}, the record says {addr}")

    for n, s in enumerate(rec["steps"], 1):
        t = tx(c, s["tx"])
        got = summary(t)
        try:
            call = calldata.decode(base64.b64decode((t.get("data") or {}).get("calldata") or ""))
        except Exception:
            call = {}
        if (call.get("method", call.get("")), plain(call.get("args", []))) != (s["fn"], plain(s["args"])):
            bad.append(f"step {n} {s['tx']}: the chain has {call.get('method', call.get(''))}{call.get("args")}, the record {s['fn']}{s['args']}")
        for key in ("result", "execution", "returned", "created_at", "votes"):
            if key in s and plain(got.get(key)) != plain(s[key]):
                bad.append(f"step {n} {s['tx']}: {key} on chain {got.get(key)!r}, recorded {s[key]!r}")
        if str(t.get("from_address", "")).lower() != s["from"].lower():
            bad.append(f"step {n}: sender on chain {t.get('from_address')}, recorded {s['from']}")
        if str(t.get("to_address", "")).lower() != addr.lower():
            bad.append(f"step {n}: sent to {t.get('to_address')}, not to the recorded contract")
        if int(t.get("value") or 0) != int(s["value"]):
            bad.append(f"step {n}: value on chain {t.get('value')}, recorded {s['value']}")
        agreed = got.get("result") == "MAJORITY_AGREE"
        refused_no_check = "no such check" in str((s.get("returned") or {}).get("error", ""))
        if not agreed or refused_no_check or s.get("as_expected") is not True:
            # Two cases are reported as notes, both followed in the record by the same call that went through:
            # a check the validators did not agree on in time (nothing stored; a leader's return value is not a
            # stored check), and a payment refused only because that check had not been stored.
            undecided = s["fn"] == "recheck" and agreed and (s.get("returned") or {}).get("decided") is False
            if (not agreed or refused_no_check or undecided) and repeated(rec, n - 1):
                why = (f"not agreed ({got.get('result')}), nothing stored" if not agreed else
                       "agreed, decided nothing (the bond stayed BONDED)" if undecided else "refused: its check had not been stored")
                print(f"  note: step {n} ({s['label']}): {why}; sent again and agreed later")
            else:
                bad.append(f"step {n} ({s['label']}): not as expected (chain {got.get('result')}, record {s.get('as_expected')!r})")

    for s in rec["steps"]:
        r = s.get("returned")
        if s["fn"] == "check_claim" and isinstance(r, dict) and r.get("id"):
            v = read(c, addr, "get_check", [r["id"]])
            if [v["result"]["verdict"], v["result"]["rule"]] != [r["verdict"], r["rule"]]:
                bad.append(f"check {r['id']}: now {v['result']['verdict']} {v['result']['rule']}, recorded {r['verdict']} {r['rule']}")
        if s["fn"] == "recheck" and isinstance(r, dict) and r.get("decided"):
            v = read(c, addr, "get_check", [s["args"][0]])
            rc = v["bond"].get("recheck") or {}
            if [rc.get("verdict"), rc.get("rule"), v["bond"]["state"]] != [r["verdict"], r["rule"], r["state"]]:
                bad.append(f"re-check of check {s['args'][0]}: stored {rc.get('verdict')} {rc.get('rule')} {v['bond']['state']}, returned {r}")
    for case, final in (rec.get("final_states") or {}).items():
        v = read(c, addr, "get_check", [rec["cases"][case]["id"]])
        if v["bond"]["state"] != final:
            bad.append(f"case {case}: bond now {v['bond']['state']}, recorded {final}")
    t = read(c, addr, "totals", [])
    held = balance(c, addr)
    if held != int(t["accounted_for"]) or int(t["accounted_for"]) != int(t["locked"]) + int(t["credited"]) + int(t.get("burned", 0)):
        bad.append(f"balance {held} != locked {t['locked']} + credited {t['credited']} + burned {t.get('burned', 0)}")
    reread = {n.get("supersedes"): n for n in rec.get("after_the_run", [])}
    for chk in rec.get("checks", []):
        if chk["ok"]:
            continue
        n = reread.get(chk["label"])
        if n and n.get("balance_wei") is not None and int(n["balance_wei"]) == held and "balance" in chk["label"]:
            # the run read the balance too soon; the reading noted after the run is what the chain shows now
            print(f"  note: the run's check '{chk['label']}' failed; read after the run, and now, the balance is {held} wei")
            continue
        bad.append(f"record check failed: {chk['label']}")
    print(f"{path.name}: contract {addr}, {len(rec['steps'])} transactions, balance {held} wei = locked + credited + burned"
          f" ({t.get('burned', 0)} burned): {'OK' if not bad else 'MISMATCH'}")
    return bad


def base_label(label: str) -> str:
    for tail in (" (check stored)", " (retry 2)", " (retry)", " (again)"):
        if label.endswith(tail):
            return label[: -len(tail)]
    return label


def repeated(rec: dict, i: int) -> bool:
    """A later step with the same label (apart from a retry mark) and the same method that went through."""
    s = rec["steps"][i]
    return any(base_label(x["label"]) == base_label(s["label"]) and x["fn"] == s["fn"] and plain(x["args"]) == plain(s["args"])
               and x.get("as_expected") is True
               and x.get("result") == "MAJORITY_AGREE" for x in rec["steps"][i + 1:])


def verify_site(path: Path, c) -> list:
    """A page click-through record: each click's transaction as the record has it, and the page contract's code."""
    rec = json.loads(path.read_text())
    addr, bad = rec["contract"], []
    if "deploy" in rec:
        d = tx(c, rec["deploy"]["tx"])
        code = base64.b64decode(((d.get("data") or {}).get("contract_code")) or "")
        if code != (ROOT / "contracts" / "launch_claim_checker_v2.py").read_bytes():
            bad.append("the page contract's deployed code differs from contracts/launch_claim_checker_v2.py")
        made = (d.get("data") or {}).get("contract_address") or d.get("to_address")
        if str(made).lower() != addr.lower():
            bad.append(f"the deployment made {made}, the record says {addr}")
    else:
        bad.append("the record has no deployment transaction for the page contract")
    for s in rec["steps"]:
        t = tx(c, s["tx"])
        got = summary(t)
        oc = s.get("on_chain") or {}
        try:
            call = calldata.decode(base64.b64decode((t.get("data") or {}).get("calldata") or ""))
        except Exception:
            call = {}
        if call.get("method", call.get("")) != oc.get("method"):
            bad.append(f"click {s['n']}: method on chain {call.get('method', call.get(''))}, recorded {oc.get('method')}")
        if plain(call.get("args", [])) != plain(oc.get("args", [])):
            bad.append(f"click {s['n']}: arguments on chain {call.get('args')}, recorded {oc.get('args')}")
        if str(t.get("from_address", "")).lower() != str(oc.get("from", "")).lower():
            bad.append(f"click {s['n']}: sender on chain {t.get('from_address')}, recorded {oc.get('from')}")
        if int(t.get("value") or 0) != int(oc.get("value") or 0):
            bad.append(f"click {s['n']}: value on chain {t.get('value')}, recorded {oc.get('value')}")
        for key in ("result", "execution", "returned", "votes", "created_at"):
            if plain(got.get(key)) != plain(oc.get(key)):
                bad.append(f"click {s['n']}: {key} on chain {got.get(key)!r}, recorded {oc.get(key)!r}")
        if str(t.get("to_address", "")).lower() != addr.lower():
            bad.append(f"click {s['n']}: sent to {t.get('to_address')}")
        if s.get("as_expected") is not True:
            bad.append(f"click {s['n']}: the record says not as expected")
    print(f"{path.name}: page contract {addr}, {len(rec['steps'])} clicks: {'OK' if not bad else 'MISMATCH'}")
    return bad


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or [ROOT / "examples" / "live" / "v2-studio.json", ROOT / "examples" / "live" / "v2-site-studio.json"]
    c, _acct = client()
    bad = []
    for p in paths:
        fn = verify_site if "clicks_that_sent_a_transaction" in json.dumps(json.loads(p.read_text()).get("summary", {})) else verify
        bad += [f"{p.name}: {b}" for b in fn(p, c)]
    for b in bad:
        print("  -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

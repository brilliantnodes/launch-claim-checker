"""Launch Claim Checker live cases on Testnet Bradbury Phase 2 (GenVM v0.6 build).
The four canary cases (fictional Examplecoin and Controlcoin); ids confirmed from the chain.

Uses the Bradbury runner from brilliantnodes/genlayer-patterns (bradbury/tools):
    GLP_BRADBURY_TOOLS=<path to genlayer-patterns/bradbury/tools> BRADBURY_KEY_FILE=<throwaway key> python bradbury/live_cases.py
"""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, os.environ.get("GLP_BRADBURY_TOOLS", str(Path(__file__).resolve().parents[2] / "genlayer-patterns" / "bradbury" / "tools")))
from live_mr import deploy, write, read

BUILD = Path(__file__).resolve().parent / "build" / "launch_claim_checker.py"
OUT = Path(__file__).resolve().parent / "results" / "checks.json"
SITE = "https://checker.brilliantnodes.com/examples"
CASES = [
    ("examplecoin", "mining", "DECENTRALIZED_MINING", "contradicted", "M1_TOP_MINER_ABOVE_HALF"),
    ("examplecoin", "block1", "NO_FOUNDER_REWARD", "contradicted", "P1_EARLY_ALLOCATION_FOUND"),
    ("controlcoin", "block1", "NO_FOUNDER_REWARD", "supported", "P2_EARLY_BLOCKS_SHOWN_CLEAN"),
    ("controlcoin", "mining", "DECENTRALIZED_MINING", "supported", "M2_TOP_MINER_AT_OR_BELOW_THIRD"),
]

def wait_count(addr, want, minutes=3):
    end = time.time() + minutes * 60
    while time.time() < end:
        n = int(read(addr, "get_count"))
        if n >= want:
            return n
        time.sleep(6)
    return n

out = {"network": "testnet-bradbury-phase-2", "chain_id": 4221, "build": "launch_claim_checker.py (GenVM v0.6)", "checks": [], "extra_attempts": []}
dep = deploy(BUILD, [])
addr = out["address"] = dep["address"]; out["deploy"] = dep
for coin, page, claim, want_v, want_r in CASES:
    for attempt in (1, 2):
        before = int(read(addr, "get_count"))
        row = write(addr, "check_claim", [f"{SITE}/{coin}-announcement.html", f"{SITE}/{coin}-explorer-{page}.html", claim, ""])
        n = wait_count(addr, before + 1)
        if n > before:
            c = read(addr, "get_check", [str(n)])
            row.update({"coin": coin, "claim": claim, "check_id": str(n), "verdict": c.get("verdict"), "rule": c.get("rule"),
                        "want": f"{want_v}/{want_r}", "ok": (c.get("verdict"), c.get("rule")) == (want_v, want_r), "facts": c.get("facts")})
            out["checks"].append(row)
            print("check", coin, claim, row["verdict"], row["rule"], "ok" if row["ok"] else "MISMATCH", flush=True)
            break
        row.update({"coin": coin, "claim": claim, "note": "nothing stored; retried"})
        out["extra_attempts"].append(row)
        print("retry", coin, claim, row["result"], flush=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n")
out["count"] = read(addr, "get_count")
OUT.write_text(json.dumps(out, indent=2, default=str) + "\n")
print("done", out["count"], flush=True)

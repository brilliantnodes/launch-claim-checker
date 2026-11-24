"""One check of a real coin on two real explorers, sent to the page contract on GenLayer Studio.

    LCC2_KEYS=/path/to/keys python tools/real_check.py OUT.json URL_A URL_B COIN CLAIM_TYPE [ROLE]

ROLE is the key file used (lcc2_studio_<ROLE>.key); "temp" (the default) makes a
fresh Studio account and funds it from Studio's faucet. The
contract is the page's Studio contract from web/src/config.js. One send only:
the record keeps what the chain returned, whatever it is.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bounty import client, fund, read  # noqa: E402
from studio_fees import send  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEYS = Path(os.environ.get("LCC2_KEYS", str(Path.home() / ".lcc2-keys")))

out, a, b, coin, claim = sys.argv[1:6]
role = sys.argv[6] if len(sys.argv) > 6 else "temp"
cfg = (ROOT / "web" / "src" / "config.js").read_text()
addr = re.search(r'studio[^}]*?checkerV2:\s*"(0x[0-9a-fA-F]{40})"', cfg, re.S).group(1)
if role == "temp":
    c, acct = client()
    fund(c, acct.address, 5)
else:
    c, acct = client(KEYS / f"lcc2_studio_{role}.key")
args = [a, b, coin, claim, ""]
h, s = send(c, addr, "check_claim", args, sender=acct.address)
rec = {"network": "genlayer-studio", "contract": addr, "sender": acct.address, "args": args, "tx": h, **s}
if isinstance(s.get("returned"), dict) and s["returned"].get("id") is not None:
    rec["stored"] = read(c, addr, "get_check", [s["returned"]["id"]])
Path(out).write_text(json.dumps(rec, indent=1, default=str))
print(json.dumps(rec, indent=1, default=str)[:2500])

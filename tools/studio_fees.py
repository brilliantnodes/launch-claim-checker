"""Studio transactions with a fee distribution (genlayer-py 0.19 or later).

Since late November 2026 GenLayer Studio's consensus contract refuses a
transaction that carries no fee distribution ("FeesDistributionMissing"), as
Testnet Bradbury does. tools/bounty.py sends without one; this module wraps its
helpers and attaches the estimate genlayer-py makes (about 0.1 test GEN, most
of it refunded).
"""
import time

from bounty import rpc, sent_since, summary, wait  # noqa: F401


def deploy(c, code, args=None) -> dict:
    h = c.deploy_contract(code=code, args=args, fees=c.estimate_transaction_fees())
    t = wait(c, h)
    return {"tx": h, "address": (t.get("data") or {}).get("contract_address") or t.get("to_address"),
            **{k: v for k, v in summary(t).items() if k != "returned"}}


def send(c, addr, fn, args, value=0, sender=None) -> tuple:
    """One send only (a retry would be a second transaction). If confirming the send fails, the
    transaction is looked for on the chain, never sent again."""
    t0 = time.time()
    try:
        h = c.write_contract(address=addr, function_name=fn, args=args, value=value, fees=c.estimate_transaction_fees())
    except Exception as e:
        h = None
        for _ in range(30):
            time.sleep(10)
            try:
                found = sent_since(c, addr, sender, t0 - 30) if sender else []
            except Exception:  # Studio's gateway sometimes answers 503 for minutes
                found = []
            if found:
                h = found[-1]
                break
        if h is None:
            raise RuntimeError(f"{fn}: the send was not confirmed and no transaction was found on the chain: {str(e)[:200]}") from e
    return h, summary(wait(c, h))

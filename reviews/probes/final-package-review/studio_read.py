import sys, json, collections
sys.path.insert(0, "/home/claude/launch-claim-checker/tools")
from bounty import client, rpc, tx
c,_ = client()
addr = "0x234D26C4f2477EC4ef1b0FCA1f0ad0dA5c03bB8e"
try:
    txs = rpc(c, "sim_getTransactionsForAddress", [addr]) or []
    print("transactions listed for the contract address:", len(txs))
    senders = collections.Counter(str(t.get("from_address")) for t in txs)
    print("by sender:", dict(senders))
    kinds = collections.Counter((str(t.get("to_address")).lower()==addr.lower(), t.get("status")) for t in txs)
    print("to contract / status:", dict(kinds))
    times = sorted(str(t.get("created_at")) for t in txs)
    print("first:", times[:1], "last:", times[-1:])
except Exception as e:
    print("list failed:", repr(e)[:300])
# votes of one judge transaction (step 3)
t = tx(c, "0x0899d65ef4d1c2dc90f7f7873168bb21c5c5bd4da05a9ce86a5d177bf20b2df5")
cd = t.get("consensus_data") or {}
print("judge step 3 votes:", json.dumps(cd.get("votes"))[:600])
print("keys:", list(t.keys()))
print("consensus_data keys:", list(cd.keys()))
lr = cd.get("leader_receipt"); lr = lr[0] if isinstance(lr, list) and lr else lr
print("leader node_config model:", json.dumps((lr or {}).get("node_config", {}))[:500])
vals = cd.get("validators") or []
print("validators:", len(vals))
for v in vals:
    nc = v.get("node_config", {})
    print("  ", v.get("vote"), v.get("execution_result"), nc.get("primary_model", {}).get("provider"), nc.get("primary_model", {}).get("model"), "|", json.dumps(v.get("result"))[:160])
print("num_of_initial_validators:", t.get("num_of_initial_validators"), "rotation_count:", t.get("rotation_count"), "appealed:", t.get("appealed"))

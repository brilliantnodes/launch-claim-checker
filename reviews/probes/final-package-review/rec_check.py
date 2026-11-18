import json, hashlib
from datetime import datetime, timezone
R="/home/claude/launch-claim-checker/"
def seal(b,a,r,h,s): return hashlib.sha256(f"{b}|{a.lower()}|{r}|{int(h)}|{s}".encode()).hexdigest()
def micros(iso):
    d=datetime.fromisoformat(iso); e=datetime(1970,1,1,tzinfo=timezone.utc); x=d-e
    return (x.days*86400+x.seconds)*10**6+x.microseconds
for name in ("examples/live/bounties-studio.json","examples/live/bounties-bradbury.json"):
    d=json.load(open(R+name)); print("==",name)
    filed={}
    okd=0; n_j=0
    for s in d["steps"]:
        r=s.get("returned") if isinstance(s.get("returned"),dict) else None
        taken = (r or {}).get("ok") is True if "returned" in s else (s["result"]=="MAJORITY_AGREE" and s["execution"]=="FINISHED_WITH_RETURN")
        if s["method"]=="file_claim" and taken:
            filed.setdefault((s["from"].lower(),s["args"][0]),[]).append((s["args"][1],s))
        if s["method"]=="judge":
            n_j+=1
            b,rule,h,salt=s["args"]; dg=seal(b,s["from"],rule,h,salt)
            match = dg in [x[0] for x in filed.get((s["from"].lower(),b),[])]
            okd+=match
            print(f"  judge step {s['n']:2d} digest matches a filing by sender: {match}  exec={s['execution']}")
    # us vs created
    for bid,b in d["bounties"].items():
        for f in b["filings"]:
            st=[x for (dg,x) in filed.get((f["hunter"].lower(),bid),[]) if dg==f["digest"]]
            if not st: print("  no step for filing",bid,f["seq"]); continue
            s=st[0]
            if "created_at" in s:
                print(f"  bounty {bid} filing {f['seq']}: us on chain == created_at of step {s['n']}: {micros(s['created_at'])==f['us']}")
            else:
                print(f"  bounty {bid} filing {f['seq']}: us={f['us']} created={s['created']} whole second: {f['us']==int(s['created'])*10**6}")
    votes={}
    for s in d["steps"]:
        if "votes" in s: votes[(s["votes"]["agree"],s["votes"]["of"])]=votes.get((s["votes"]["agree"],s["votes"]["of"]),0)+1
    print("  votes (agree, of) -> count:",votes)
    jv=[(s["n"],s["votes"]) for s in d["steps"] if s["method"]=="judge" and "votes" in s and s["execution"]=="SUCCESS"]
    print("  model-run judgements votes:",jv)
    print("  as_expected:",sum(s["as_expected"] for s in d["steps"]),"of",len(d["steps"]),"; checks ok:",sum(c["ok"] for c in d["checks"]),"of",len(d["checks"]), "; want=null checks:",[c["label"][:60] for c in d["checks"] if c["want"] is None])
    print("  sha256 of code file matches record:", hashlib.sha256(open(R+(d.get("contract_source") or "bradbury/build/launch_claim_bounties.py"),"rb").read()).hexdigest()==(d.get("contract_sha256") or d.get("build_sha256")))
    print("  rules in record: fee_bp",d["rules"]["fee_bp"],"min_fee",d["rules"]["min_fee_wei"],"ttl",d["rules"]["filing_ttl_seconds"],"margin",d["rules"]["process_margin_seconds"],"max_height",d["rules"]["max_height"],"min_blocks",d["rules"]["min_blocks_floor"],d["rules"]["min_blocks_cap"],"quote",d["rules"]["quote_min"],d["rules"]["quote_max"],"soft",d["rules"]["soft_tries"],"max_latest",d["rules"]["max_latest"])

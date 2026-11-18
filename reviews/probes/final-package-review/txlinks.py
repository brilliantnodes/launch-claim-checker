import re, json
R="/home/claude/launch-claim-checker/"
st=json.load(open(R+"examples/live/bounties-studio.json")); br=json.load(open(R+"examples/live/bounties-bradbury.json"))
S={s["tx"].lower():s for s in st["steps"]}; B={s["tx"].lower():s for s in br["steps"]}
for f in ("README.md","MILESTONE.md"):
    md=open(R+f).read()
    print("==",f)
    for label,host,kind,h in re.findall(r"\[`?([^\]`]+)`?\]\(https://(explorer-studio\.genlayer\.com|scan\.bradbury\.genlayer\.com)/(tx|address)/(0x[0-9a-fA-F]+)\)",md):
        if kind=="address":
            ok = (h in (st["address"], "0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8") and "studio" in host) or (h in (br["address"], "0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C") and "bradbury" in host)
            lab_ok = label==h or (label.startswith(h[:6]) and label.endswith(h[-4:]))
            print(f"  address {label:44} right network: {ok}  label matches: {lab_ok}")
            continue
        rec = S if "studio" in host else B
        s = rec.get(h.lower())
        lab_ok = label.startswith(h[:6]) and label.endswith(h[-4:])
        if not s: print("  TX NOT IN RECORD", h, host); continue
        ret = s.get("returned")
        print(f"  {label} -> {'studio' if rec is S else 'bradbury'} step {s['n']:2d} {s['method']:11} label ok:{lab_ok} | {s['label'][:70]} | {json.dumps(ret)[:90] if ret is not None else s['result']+'/'+s['execution']}")
a=open(R+"README.md").read(); b=open(R+"MILESTONE.md").read()
i=a.index("**Studio, 46 transactions"); j=a.index("```bash\npip install genlayer-py==0.18.0\npython tools/verify")
k=b.index("**Studio, 46 transactions"); l=b.index("`python tools/verify_bounties.py` checks")
print("live-run text identical in README and MILESTONE:", a[i:j].strip()==b[k:l].strip())

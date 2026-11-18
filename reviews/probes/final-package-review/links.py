import re, os, sys
R="/home/claude/launch-claim-checker"
def anchors(md):
    out=set()
    for line in md.splitlines():
        m=re.match(r"^(#+)\s+(.*)$",line)
        if m:
            t=m.group(2).strip().lower()
            t=re.sub(r"[^\w\- ]","",t).replace(" ","-")
            out.add(t)
    return out
for f in ("README.md","MILESTONE.md","bradbury/README.md"):
    md=open(os.path.join(R,f)).read()
    base=os.path.dirname(os.path.join(R,f))
    links=re.findall(r"\]\(([^)\s]+)\)",md)
    bad=[];n=0
    for l in links:
        if l.startswith("http"): continue
        n+=1
        path,_,frag=l.partition("#")
        target=os.path.normpath(os.path.join(base,path)) if path else os.path.join(R,f)
        if not os.path.exists(target): bad.append((l,"missing file")); continue
        if frag and target.endswith(".md"):
            if frag not in anchors(open(target).read()): bad.append((l,"missing anchor"))
    # backticked paths
    ticks=set(re.findall(r"`([A-Za-z0-9_./\-]+\.(?:py|sh|json|md|html|js|css|mjs|yml|yaml|txt)|[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_.\-]+)+/?)`",md))
    miss=[t for t in sorted(ticks) if not (os.path.exists(os.path.join(R,t)) or os.path.exists(os.path.join(base,t)))]
    print(f, "relative links:",n,"broken:",bad)
    print("   backticked paths not found:",miss)
    urls=sorted(set(re.findall(r"https?://[^\s)\]>`\"']+",md)))
    open(f"/tmp/review4/urls_{f.replace('/','_')}.txt","w").write("\n".join(urls))
    print("   distinct urls:",len(urls))

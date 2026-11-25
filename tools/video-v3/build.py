#!/usr/bin/env python3
"""Launch Claim Checker v2 demo video, animated (1920x1080, 30 fps, voice-over).

    pip install playwright kokoro-onnx soundfile numpy
    KOKORO_DIR=/path/to/kokoro DEMO_REPO=/path/to/demo-explorer python tools/video-v3/build.py [shots|voice|scenes|stills|render|all]

Every scene is an HTML page with CSS animations. The renderer pauses them,
sets every animation to the frame's time, takes a JPEG screenshot and pipes
it to ffmpeg: one file per scene, joined without re-encoding, then the
narration (Kokoro-82M, offline, voice af_heart) is added. The explorer
pictures are screenshots of the real fictional test pages; the boxes drawn
over them are placed from the pages' own layout.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
B = HERE / "build"
DEMO = Path(os.environ.get("DEMO_REPO", str(ROOT.parent / "demo-explorer")))
RAW = Path(os.environ.get("FLIP_RAW", "/tmp/flipraw"))  # tools/make_v2_pages.py output without --corrected
FPS = 30
_chrome = Path("/usr/bin/google-chrome")
LAUNCH = {"executable_path": str(_chrome), "args": ["--no-sandbox"]} if _chrome.exists() else {}
LEAD, TAIL = 0.45, 0.75

LINES = {
    "hook": "A new coin says: no founder reward. Can you trust it?",
    "problem": "A block explorer can show the truth. But one explorer is one website. It can be wrong, or run by the very people who made the claim.",
    "two": "Launch Claim Checker version two reads the claim on two explorers, on two different domains. Every Gen Layer validator opens both pages itself, and plain code checks every number its model copies.",
    "verdict": "Both show two million coins paid to the founders in block one: contradicted. If they show different things, the answer is honest: the explorers disagree.",
    "bond": "Now put money behind it. The requester bonds the verdict. Anyone who thinks it is wrong can challenge it, with the same amount.",
    "outcomes": "Then the validators read both explorers again. The same facts: upheld, and the requester takes the deposits. The opposite: overturned. Half the bond is burned, and the challengers share the rest. Anything else: everyone gets their money back.",
    "flip": "We tested it live. Both explorers corrected Flip coin's block one. The re-check reversed the verdict, and the challenger was paid.",
    "proof": "A hundred and fifty one tests. A hundred and twenty eight deliberate breaks, every one caught. Three rounds of independent AI review. Then live on Gen Layer Studio and the Bradbury test net.",
    "end": "Try it free, at checker dot brilliant nodes dot com.",
}
ORDER = list(LINES)

# ------------------------------------------------------------------ pictures of the real test pages


def shots():
    B.mkdir(exist_ok=True)
    pages = {
        "exa": (ROOT / "web/public/v2/examplecoin-block-1.html", "td:has-text('Founders allocation')"),
        "exb": (DEMO / "examplecoin/block-1.html", "li:has-text('founders allocation')"),
        "fla0": (RAW / "v2/flipcoin-block-1.html", "td:has-text('Founders allocation')"),
        "flb0": (RAW / "demo/flipcoin/block-1.html", "li:has-text('founders allocation')"),
        "fla1": (ROOT / "web/public/v2/flipcoin-block-1.html", "em:has-text('Correction')"),
        "flb1": (DEMO / "flipcoin/block-1.html", "p.fix"),
    }
    boxes = {}
    with sync_playwright() as p:
        b = p.chromium.launch(**LAUNCH)
        for name, (path, sel) in pages.items():
            pg = b.new_page(viewport={"width": 760, "height": 560}, device_scale_factor=2)
            pg.goto(path.as_uri())
            pg.wait_for_timeout(300)
            loc = pg.locator(sel).first
            bb = loc.bounding_box()
            if name in ("exa", "fla0"):  # the whole table row
                bb = pg.locator("tr:has-text('Founders allocation')").first.bounding_box()
            boxes[name] = bb
            pg.screenshot(path=str(B / f"{name}.jpg"), type="jpeg", quality=92)
            pg.close()
        b.close()
    (B / "boxes.json").write_text(json.dumps(boxes, indent=1))
    print("shots", boxes)


# ------------------------------------------------------------------ narration


def voice():
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    kdir = Path(os.environ["KOKORO_DIR"])
    k = Kokoro(str(kdir / "kokoro-v1.0.fp16.onnx"), str(kdir / "voices-v1.0.bin"))
    durs, parts, sr = {}, [], 24000
    for name in ORDER:
        samples, sr = k.create(LINES[name], voice="af_heart", speed=1.0, lang="en-us")
        samples = np.asarray(samples, dtype=np.float32)
        d = round((LEAD + len(samples) / sr + TAIL) * FPS) / FPS
        durs[name] = d
        track = np.zeros(round(d * sr), dtype=np.float32)
        st = round(LEAD * sr)
        track[st: st + len(samples)] = samples[: len(track) - st]
        parts.append(track)
    sf.write(B / "narration.wav", np.concatenate(parts), sr)
    (B / "durations.json").write_text(json.dumps(durs, indent=1))
    print("voice", durs, round(sum(durs.values()), 2))


# ------------------------------------------------------------------ scenes

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#050b18;font-family:Inter,"Helvetica Neue",Arial,sans-serif;color:#eef2fa}
.stage{position:absolute;inset:0;overflow:hidden}
.bg{position:absolute;inset:0;background:radial-gradient(ellipse at 20% 10%,#17326a 0%,#0b1a3a 42%,#050b18 100%)}
.grid{position:absolute;left:-20%;right:-20%;bottom:-10%;height:62%;background-image:linear-gradient(rgba(110,160,255,.16) 1.5px,transparent 1.5px),linear-gradient(90deg,rgba(110,160,255,.16) 1.5px,transparent 1.5px);background-size:80px 80px;transform:perspective(700px) rotateX(62deg);transform-origin:50% 100%;animation:gridmove 4s linear infinite;mask-image:linear-gradient(to top,rgba(0,0,0,.9),transparent)}
@keyframes gridmove{from{background-position:0 0}to{background-position:0 80px}}
.orb{position:absolute;border-radius:50%;filter:blur(40px);opacity:.55}
.orb.a{width:620px;height:620px;background:radial-gradient(#ffb02e55,transparent 65%);left:1250px;top:-160px;animation:orb 14s ease-in-out infinite alternate}
.orb.b{width:700px;height:700px;background:radial-gradient(#3fd6a033,transparent 65%);left:-200px;top:600px;animation:orb 17s ease-in-out infinite alternate-reverse}
@keyframes orb{from{transform:translate(0,0)}to{transform:translate(-160px,90px)}}
.vig{position:absolute;inset:0;background:radial-gradient(ellipse at center,transparent 72%,rgba(0,0,0,.35) 100%);pointer-events:none}
.cam{position:absolute;inset:0;animation:cam linear both}@keyframes cam{from{transform:scale(1)}to{transform:scale(1.035)}}
.flyin{animation:flyin 1.1s cubic-bezier(.5,0,.3,1) both}
@keyframes flyin{0%{opacity:0;transform:translate(var(--x0),var(--y0)) scale(.6)}15%{opacity:1}85%{opacity:1;transform:translate(var(--x1),var(--y1)) scale(1)}100%{opacity:0;transform:translate(var(--x1),var(--y1)) scale(.3)}}
.pulse{animation:pulse .5s ease both}@keyframes pulse{0%{transform:scale(1)}40%{transform:scale(1.12);box-shadow:0 0 90px #ffb02e}100%{transform:scale(1)}}
.top{position:absolute;left:90px;right:90px;top:46px;display:flex;justify-content:space-between;font-size:24px;color:#93a3c4;letter-spacing:.02em}
.top b{color:#fff;font-weight:800;letter-spacing:-.01em}.top i{font-style:normal;color:#ffb02e;font-weight:600}
.h{position:absolute;left:90px;top:118px;font-size:68px;font-weight:800;letter-spacing:-2px;line-height:1.05}
.amber{color:#ffb02e}.green{color:#4fe0a6}.red{color:#ff7468}.muted{color:#93a3c4}
.in{animation:rise .7s cubic-bezier(.2,.8,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(36px)}to{opacity:1;transform:none}}
.fadein{animation:fadein .6s ease both}@keyframes fadein{from{opacity:0}to{opacity:1}}
.fadeout{animation:fadeout .5s ease both}@keyframes fadeout{from{opacity:1}to{opacity:0}}
.pop{animation:pop .55s cubic-bezier(.2,1.6,.4,1) both}@keyframes pop{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:scale(1)}}
.fromL{animation:fromL .9s cubic-bezier(.2,.8,.2,1) both}@keyframes fromL{from{opacity:0;transform:translateX(-500px) rotateY(25deg)}to{opacity:1;transform:none}}
.fromR{animation:fromR .9s cubic-bezier(.2,.8,.2,1) both}@keyframes fromR{from{opacity:0;transform:translateX(500px) rotateY(-25deg)}to{opacity:1;transform:none}}
.stamp{animation:stamp .5s cubic-bezier(.3,1.4,.5,1) both}@keyframes stamp{0%{opacity:0;transform:scale(3.2) rotate(-14deg)}70%{opacity:1;transform:scale(.94) rotate(-6deg)}100%{opacity:1;transform:scale(1) rotate(-6deg)}}
.shake{animation:shake .45s ease both}@keyframes shake{0%,100%{transform:none}20%{transform:translate(-14px,6px)}40%{transform:translate(12px,-8px)}60%{transform:translate(-8px,4px)}80%{transform:translate(5px,-3px)}}
.pill{display:inline-block;font-weight:800;font-size:30px;padding:12px 28px;border-radius:40px;letter-spacing:.02em}
.pill.r{background:#4a1d1b;color:#ff8d82;box-shadow:0 0 40px #ff746844}.pill.g{background:#123d2e;color:#5ff0b4;box-shadow:0 0 40px #4fe0a644}.pill.a{background:#4a3410;color:#ffbe4d;box-shadow:0 0 40px #ffb02e44}
.browser{position:absolute;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 40px 90px rgba(0,0,0,.6),0 0 0 2px rgba(255,255,255,.12)}
.browser .bb{height:44px;background:#e6eaf3;display:flex;align-items:center;gap:9px;padding:0 16px;color:#3f4a66;font-size:19px;font-weight:600}
.browser .bb u{width:13px;height:13px;border-radius:50%;background:#e5484d;display:inline-block}.browser .bb u:nth-child(2){background:#f5b301}.browser .bb u:nth-child(3){background:#2fb36b}
.browser .bb span{flex:1;text-align:center;margin-right:50px;white-space:nowrap;overflow:hidden}
.browser img{display:block;width:100%}
.hl{position:absolute;border:4px solid #ffb02e;border-radius:8px;box-shadow:0 0 0 9999px rgba(5,11,24,0),0 0 30px #ffb02eaa;background:rgba(255,176,46,.12)}
.scan{position:absolute;left:0;right:0;height:90px;background:linear-gradient(to bottom,transparent,rgba(79,224,166,.35),transparent);animation:scan 1.6s ease-in-out infinite}
@keyframes scan{from{top:-90px}to{top:100%}}
.node{position:absolute;width:76px;height:76px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#7df5c6,#1f9e72 60%,#0d5a40);box-shadow:0 0 30px #4fe0a688,inset 0 -6px 12px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-weight:900;font-size:30px;color:#06301f}
.coin{position:absolute;width:86px;height:86px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff2c2,#f5c04a 45%,#c48a16);border:5px solid #a2700d;color:#5e3e05;font-weight:900;font-size:24px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 34px rgba(255,190,70,.55)}
.fly{animation:fly 1.1s cubic-bezier(.5,0,.3,1) both}
@keyframes fly{0%{opacity:0;transform:translate(var(--x0),var(--y0)) scale(.6)}15%{opacity:1}100%{opacity:1;transform:translate(var(--x1),var(--y1)) scale(1)}}
.card{position:absolute;background:rgba(14,28,58,.78);border:2px solid rgba(130,170,255,.25);border-radius:26px;box-shadow:0 30px 70px rgba(0,0,0,.45);backdrop-filter:blur(6px)}
.big{font-weight:900;letter-spacing:-3px;font-variant-numeric:tabular-nums}
.person{position:absolute;width:220px;text-align:center;font-size:26px;color:#c9d5ee;font-weight:600}
.person .hd{width:70px;height:70px;border-radius:50%;margin:0 auto 6px;background:#9fb8e8}
.person .bd{width:130px;height:70px;border-radius:65px 65px 10px 10px;margin:0 auto 12px;background:#4b6fae}
"""


def page(dur, body, css="", js=""):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}{css}</style></head><body>
<div class="stage" id="stage"><div class="bg"></div><div class="grid"></div><div class="orb a"></div><div class="orb b"></div>
<div class="top"><span><b>Launch Claim Checker</b> · version 2</span><span><i>test GEN only · fictional coins</i></span></div>
<div class="cam" style="animation-duration:{dur:.2f}s">{body}</div><div class="vig"></div>
<div style="position:absolute;inset:0;background:#050b18;animation:fadeout .35s ease both"></div>
<div style="position:absolute;inset:0;background:#050b18;opacity:0;animation:fadein .35s ease both;animation-delay:{dur-0.35:.2f}s"></div>
</div><script>{js}</script></body></html>"""


def d(t):
    return f"animation-delay:{t:.2f}s"


def browser(x, y, w, img, url, cls="", delay=0.0, extra="", z=""):
    h = round(560 * w / 760)
    return (f'<div class="browser {cls}" style="left:{x}px;top:{y}px;width:{w}px;{d(delay)};{z}"><div class="bb"><u></u><u></u><u></u><span>{url}</span></div>'
            f'<div style="position:relative;height:{h}px;overflow:hidden"><img src="{img}">{extra}</div></div>')


def hlbox(bb, w, delay, pad=6, cls="pop"):
    s = w / 760
    return (f'<div class="hl {cls}" style="left:{bb["x"]*s-pad:.0f}px;top:{bb["y"]*s-pad:.0f}px;width:{bb["width"]*s+2*pad:.0f}px;'
            f'height:{bb["height"]*s+2*pad:.0f}px;{d(delay)}"></div>')


def scenes():
    durs = json.loads((B / "durations.json").read_text())
    box = json.loads((B / "boxes.json").read_text())
    img = {k: (B / f"{k}.jpg").as_uri() for k in box}
    S = {}

    # 1. hook
    dur = durs["hook"]
    S["hook"] = page(dur, f"""
<div style="position:absolute;left:0;right:0;top:250px;text-align:center">
  <div class="in" style="{d(.2)};font-size:34px;color:#93a3c4;font-weight:600;letter-spacing:.2em">A NEW COIN ANNOUNCES</div>
  <div class="in" style="{d(.5)};font-size:150px;font-weight:900;letter-spacing:-5px;margin-top:30px">“No founder <span class="amber">reward.</span>”</div>
  <div class="in" style="{d(2.3)};font-size:74px;font-weight:800;margin-top:60px">Can you trust it?</div>
</div>
<div class="stamp" style="position:absolute;left:1340px;top:640px;{d(3.0)}"><span class="pill a" style="font-size:40px;padding:18px 36px">CHECK IT</span></div>
""")

    # 2. problem: one website, and its number can change
    dur = durs["problem"]
    W = 900
    S["problem"] = page(dur, f"""
<div class="h in" style="{d(.1)}">One explorer is <span class="amber">one website</span></div>
{browser(150, 280, W, img['exa'], 'one-explorer.example/block/1', 'fromL', .3, hlbox(box['exa'], W, 1.6) + f'<div class="glitch" style="left:0;top:{box["exa"]["y"]*W/760-8:.0f}px;width:{W}px;height:{box["exa"]["height"]*W/760+16:.0f}px;{d(4.6)}"></div>')}
<div class="card in" style="left:1140px;top:330px;width:640px;padding:44px;{d(2.6)}">
  <div style="font-size:40px;font-weight:800;line-height:1.25">It can be <span class="red">wrong</span>,<br>out of date,</div>
  <div class="in" style="font-size:40px;font-weight:800;line-height:1.25;margin-top:6px;{d(4.4)}">or run by the people<br>who made the <span class="amber">claim</span>.</div>
</div>
<div class="pop" style="position:absolute;left:1380px;top:700px;font-size:190px;font-weight:900;color:#ff7468;text-shadow:0 0 60px #ff746888;{d(5.6)}">?</div>
""", css=""".glitch{position:absolute;background:repeating-linear-gradient(0deg,rgba(255,116,104,.0) 0 6px,rgba(255,116,104,.35) 6px 9px);mix-blend-mode:multiply;animation:glitch 1.2s steps(6) infinite;opacity:0}
@keyframes glitch{0%{opacity:0;transform:translateX(0)}20%{opacity:1;transform:translateX(-12px)}40%{opacity:.4;transform:translateX(9px)}60%{opacity:1;transform:translateX(-5px)}80%{opacity:.2;transform:translateX(4px)}100%{opacity:0}}""")

    # 3. two explorers, five validators, beams
    dur = durs["two"]
    W = 700
    ax, bx, by = 90, 1130, 300
    h = round(560 * W / 760)
    nodes, beams, dots = "", "", ""
    for i in range(5):
        ny = 300 + i * 125
        nodes += f'<div class="node pop" style="left:922px;top:{ny}px;{d(2.0 + i * .12)}">{i+1}</div>'
        for side, (tx, bb) in enumerate(((ax, box["exa"]), (bx, box["exb"]))):
            s = W / 760
            ex = tx + (bb["x"] + bb["width"] / 2) * s
            ey = by + 44 + (bb["y"] + bb["height"] / 2) * s
            sx, sy = 960, ny + 38
            path = f"M{sx},{sy} L{ex:.0f},{ey:.0f}"
            beams += f'<path d="{path}" class="beam" style="{d(2.8 + i * .1 + side * .05)}"/>'
            dots += f'<div class="dot" style="offset-path:path(\'{path}\');{d(3.0 + i * .1 + side * .05)}"></div>'
    S["two"] = page(dur, f"""
<div class="h in" style="{d(.1)}">Two explorers. <span class="green">Two domains.</span></div>
{browser(ax, by, W, img['exa'], 'checker.brilliantnodes.com/v2/…', 'fromL', .3, '<div class="scan" style="animation-delay:3.2s"></div>' + hlbox(box['exa'], W, 4.6))}
{browser(bx, by, W, img['exb'], 'brilliantnodes.github.io/demo-explorer/…', 'fromR', .5, '<div class="scan" style="animation-delay:3.4s"></div>' + hlbox(box['exb'], W, 4.8))}
<svg style="position:absolute;inset:0" width="1920" height="1080">{beams}</svg>{dots}{nodes}
<div class="in" style="position:absolute;left:740px;top:950px;width:440px;text-align:center;font-size:26px;color:#9ff5d3;font-weight:700;{d(2.2)}">GenLayer validators</div>
<div class="card in" style="left:420px;top:900px;width:1080px;padding:22px 30px;text-align:center;font-size:30px;font-weight:700;{d(7.5)};opacity:0">Code checks every number the model copies, on each validator's own copy</div>
""", css=""".beam{fill:none;stroke:#4fe0a6;stroke-width:3;stroke-dasharray:1400;stroke-dashoffset:1400;opacity:.7;animation:draw .9s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.dot{position:absolute;left:0;top:0;width:14px;height:14px;margin:-7px;border-radius:50%;background:#bfffe6;box-shadow:0 0 16px #4fe0a6;offset-distance:0%;opacity:0;animation:run 1.3s linear infinite}
@keyframes run{0%{offset-distance:0%;opacity:0}10%{opacity:1}90%{opacity:1}100%{offset-distance:100%;opacity:0}}""")

    # 4. verdict: both agree -> CONTRADICTED; then disagree
    dur = durs["verdict"]
    W = 560
    S["verdict"] = page(dur, f"""
<div class="h in" style="{d(.1)}">A verdict needs <span class="amber">both</span></div>
{browser(90, 290, W, img['exa'], 'explorer A', 'in', .2, hlbox(box['exa'], W, .9))}
{browser(1270, 290, W, img['exb'], 'explorer B', 'in', .35, hlbox(box['exb'], W, 1.1))}
<div class="in" style="position:absolute;left:690px;top:340px;width:540px;text-align:center;{d(1.4)}">
  <div style="font-size:30px;color:#93a3c4;font-weight:600">both show, in block 1</div>
  <div class="big" style="font-size:96px;margin:6px 0">2,000,000</div>
  <div style="font-size:30px;color:#93a3c4;font-weight:600">coins to the founders</div>
</div>
<div class="stamp" style="position:absolute;left:720px;top:600px;{d(3.4)}"><span class="pill r" style="font-size:52px;padding:22px 46px">CONTRADICTED</span></div>
<div class="fadein" style="position:absolute;left:0;right:0;top:820px;text-align:center;{d(5.8)}">
  <span style="font-size:36px;font-weight:700">They show different things?</span>
  <span class="stamp" style="display:inline-block;margin-left:26px;{d(7.2)}"><span class="pill a" style="font-size:38px">THE EXPLORERS DISAGREE</span></span>
</div>
""")

    # 5. bond and challenge: coins into the vault, countdown ring
    dur = durs["bond"]
    vx, vy = 860, 400
    def coin(x0, y0, x1, y1, t, label="1 GEN"):
        return f'<div class="coin flyin" style="left:0;top:0;--x0:{x0}px;--y0:{y0}px;--x1:{x1}px;--y1:{y1}px;{d(t)}">{label}</div>'
    S["bond"] = page(dur, f"""
<div class="h in" style="{d(.1)}">Put <span class="amber">money</span> behind it</div>
<div class="person in" style="left:120px;top:420px;{d(.4)}"><div class="hd"></div><div class="bd"></div>Requester</div>
<div class="person in" style="left:1530px;top:300px;{d(2.6)}"><div class="hd"></div><div class="bd"></div>Challenger</div>
<div class="person in" style="left:1530px;top:600px;{d(3.6)}"><div class="hd"></div><div class="bd"></div>Challenger 2</div>
<div class="vault in" style="left:{vx}px;top:{vy}px;{d(.6)}"><div class="vglow pulse" style="{d(2.2)}"></div><div class="vglow pulse" style="{d(4.1)}"></div><div class="vglow pulse" style="{d(5.1)}"></div>
  <svg width="220" height="220" style="position:absolute;left:-10px;top:-10px"><circle cx="110" cy="110" r="100" class="ringbg"/><circle cx="110" cy="110" r="100" class="ring" style="{d(2.4)}"/></svg>
  <div style="font-size:24px;color:#93a3c4;font-weight:700;margin-top:52px">HELD</div>
  <div class="big" id="held" style="font-size:58px;color:#ffbe4d">0 GEN</div>
</div>
<div class="in" style="position:absolute;left:{vx-60}px;top:{vy+250}px;width:320px;text-align:center;font-size:26px;color:#93a3c4;font-weight:600;{d(2.4)}">challenge window</div>
{coin(230, 470, vx+57, vy+57, 1.2)}{coin(1600, 340, vx+57, vy+57, 3.1)}{coin(1600, 640, vx+57, vy+57, 4.1)}
<div class="card in" style="left:420px;top:860px;width:1080px;padding:24px 30px;text-align:center;font-size:30px;font-weight:700;{d(5.4)}">A challenge deposits exactly the bond. No limit on challengers.</div>
""", css=""".vglow{position:absolute;inset:0;border-radius:50%;}
.vault{position:absolute;width:200px;height:200px;border-radius:50%;background:radial-gradient(circle at 40% 30%,#22355f,#0c1730);border:3px solid #ffb02e88;box-shadow:0 0 60px #ffb02e44;text-align:center}
.ringbg{fill:none;stroke:rgba(255,255,255,.08);stroke-width:8}.ring{fill:none;stroke:#ffb02e;stroke-width:8;stroke-linecap:round;stroke-dasharray:628;stroke-dashoffset:0;transform:rotate(-90deg);transform-origin:110px 110px;animation:ring 4.5s linear both}
@keyframes ring{to{stroke-dashoffset:628}}""", js="window.tick=t=>{const n=t>=5.2?3:t>=4.2?2:t>=2.3?1:0;document.getElementById('held').textContent=n+' GEN';};")

    # 6. outcomes, each with its coin flow
    dur = durs["outcomes"]
    cards, flows = "", ""
    xs = [130, 700, 1270]
    spec = [("r", "same facts", "Upheld", "The requester takes the deposits", 3.2),
            ("g", "opposite verdict", "Overturned", "Half the bond burned, challengers share the rest", 7.0),
            ("a", "anything else", "Not confirmed", "Everyone gets their money back", 12.0)]
    def av(x, y, label, color):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:84px;text-align:center;font-size:20px;font-weight:700;color:#c9d5ee"><div style="width:58px;height:58px;border-radius:50%;margin:0 auto 4px;background:{color}"></div>{label}</div>'
    def cf(x0, y0, x1, y1, t):
        return f'<div class="coin fly" style="left:0;top:0;width:58px;height:58px;font-size:15px;--x0:{x0}px;--y0:{y0}px;--x1:{x1}px;--y1:{y1}px;{d(t)}">GEN</div>'
    pot = (230, 290)
    flowsets = [
        av(40, 300, "Requester", "#ffb02e") + "".join(cf(pot[0], 160, 140 + k * 62, 302, k * .25) for k in range(3)),
        av(40, 300, "Challenger", "#4fe0a6") + av(218, 300, "Burned", "#ff5d6c") + av(396, 300, "Challenger", "#4fe0a6") + cf(pot[0], 160, 53, 302, 0) + cf(pot[0], 160, 409, 302, .15) + cf(pot[0], 160, 231, 302, .35),
        av(40, 300, "Requester", "#ffb02e") + av(218, 300, "Challenger", "#4fe0a6") + av(396, 300, "Challenger", "#4fe0a6") + cf(230, 160, 53, 380, 0) + cf(230, 160, 231, 380, .15) + cf(230, 160, 409, 380, .3),
    ]
    for x, (c, tag, title, text, t), fl in zip(xs, spec, flowsets):
        inner = fl.replace("animation-delay:", "animation-delay:X").split("animation-delay:X")
        # shift every delay inside the card by the card's own start + 0.8 s
        fixed = inner[0]
        for part in inner[1:]:
            num, rest = part.split("s", 1)
            fixed += f"animation-delay:{float(num) + t + .8:.2f}s" + rest
        cards += (f'<div class="card in" style="left:{x}px;top:400px;width:520px;height:460px;padding:36px;{d(t)}"><span class="pill {c}">{tag}</span>'
                  f'<div style="font-size:54px;font-weight:900;margin:22px 0 10px">{title}</div><div style="font-size:28px;color:#c9d5ee;font-weight:600">{text}</div>{fixed}</div>')
    nodes = "".join(f'<div class="node pop" style="left:{720+i*100}px;top:270px;width:60px;height:60px;font-size:24px;{d(.3+i*.1)}">{i+1}</div>' for i in range(5))
    S["outcomes"] = page(dur, f"""
<div class="h in" style="{d(.1)}">Then the validators <span class="green">read both again</span></div>
{nodes}<div class="sweep" style="{d(.8)}"></div>
{cards}{flows}
""", css=""".up{animation:up 1s cubic-bezier(.2,.8,.2,1) both}@keyframes up{from{opacity:0;transform:translateY(60px) scale(.4)}to{opacity:1;transform:none}}
.sweep{position:absolute;left:640px;top:350px;width:640px;height:6px;border-radius:3px;background:linear-gradient(90deg,transparent,#4fe0a6,transparent);animation:sw 1.4s ease-in-out 2 both}
@keyframes sw{0%{opacity:0;transform:scaleX(.1)}50%{opacity:1;transform:scaleX(1)}100%{opacity:0;transform:scaleX(.1)}}""")

    # 7. flip: both explorers correct block 1, the stamp turns
    dur = durs["flip"]
    W = 640
    def flipb(x, a0, a1, url, bb0, t):
        return browser(x, 300, W, img[a0], url, 'in', .2,
                       hlbox(bb0, W, .9) + f'<img class="fadein" src="{img[a1]}" style="position:absolute;left:0;top:0;width:100%;{d(t)}">' + hlbox(box[a1], W, t + .5))
    S["flip"] = page(dur, f"""
<div class="h in" style="{d(.1)}">Tested live: <span class="amber">the explorers change</span></div>
{flipb(90, 'fla0', 'fla1', 'checker.brilliantnodes.com/v2/flipcoin…', box['fla0'], 2.6)}
{flipb(1190, 'flb0', 'flb1', 'brilliantnodes.github.io/…/flipcoin…', box['flb0'], 3.0)}
<div style="position:absolute;left:760px;top:380px;width:400px;height:150px;perspective:900px">
  <div class="flipcard" style="{d(5.0)}">
    <div class="face"><span class="pill r" style="font-size:36px">CONTRADICTED</span></div>
    <div class="face back"><span class="pill g" style="font-size:36px">SUPPORTED</span></div>
  </div>
</div>
<div class="in" style="position:absolute;left:760px;top:540px;width:400px;text-align:center;font-size:26px;color:#93a3c4;font-weight:700;{d(5.0)}">re-check</div>
<div class="stamp" style="position:absolute;left:770px;top:650px;{d(6.4)}"><span class="pill g" style="font-size:40px;padding:18px 34px">OVERTURNED</span></div>
<div class="in" style="position:absolute;left:0;right:0;top:880px;text-align:center;font-size:40px;font-weight:800;{d(7.2)}">The challenger collects <span class="amber">1.5 GEN</span> · 0.5 GEN burned</div>
<div class="coin fly" style="left:0;top:0;--x0:917px;--y0:660px;--x1:1640px;--y1:860px;{d(7.4)}">1.5</div>
""", css=""".flipcard{position:relative;width:100%;height:100%;transform-style:preserve-3d;animation:flip .8s cubic-bezier(.4,0,.2,1) both}
@keyframes flip{from{transform:rotateY(0)}to{transform:rotateY(180deg)}}
.face{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;backface-visibility:hidden}.face.back{transform:rotateY(180deg)}""")

    # 8. proof: counters and case tiles
    dur = durs["proof"]
    tiles = ["Upheld, two challengers", "Released", "Overturned, half burned", "Not confirmed: explorers disagree", "Not confirmed: no re-check", "Every refusal credited back", "Withdrawals", "Planted instruction ignored"]
    tl = "".join(f'<div class="tile pop" style="{d(4.2+i*.18)}"><b>✓</b>{t}</div>' for i, t in enumerate(tiles))
    S["proof"] = page(dur, f"""
<div class="h in" style="{d(.1)}">Built to be broken. <span class="green">Then run live.</span></div>
<div class="stats">
 <div class="in" style="{d(.3)}"><div class="big n" id="c1">0</div><div class="lab">tests, on both GenVM versions</div></div>
 <div class="in" style="{d(1.0)}"><div class="big n" id="c2">0</div><div class="lab">deliberate breaks, all caught</div></div>
 <div class="in" style="{d(2.6)}"><div class="big n" id="c3">0</div><div class="lab">live transactions, Studio</div></div>
 <div class="in" style="{d(3.0)}"><div class="big n" id="c4">0</div><div class="lab">live transactions, Bradbury</div></div>
</div>
<div class="tiles">{tl}</div>
<div class="in" style="position:absolute;left:0;right:0;top:960px;text-align:center;font-size:30px;color:#c9d5ee;font-weight:600;{d(6.4)}">Every record checked against the chain</div>
""", css=""".stats{position:absolute;left:90px;right:90px;top:290px;display:grid;grid-template-columns:repeat(4,1fr);gap:30px;text-align:center}
.n{white-space:nowrap;font-size:140px;color:#ffbe4d;text-shadow:0 0 50px #ffb02e55}.lab{font-size:28px;color:#c9d5ee;font-weight:600;margin-top:6px}
.tiles{position:absolute;left:150px;right:150px;top:640px;display:grid;grid-template-columns:repeat(4,1fr);gap:22px}
.tile{background:rgba(14,28,58,.8);border:2px solid rgba(79,224,166,.35);border-radius:18px;padding:20px 22px;font-size:25px;font-weight:700;display:flex;gap:14px;align-items:center}
.tile b{color:#06301f;background:#4fe0a6;border-radius:50%;width:38px;height:38px;flex:none;display:flex;align-items:center;justify-content:center;font-size:22px}""",
        js="""const C=[[1,.3,151],[2,1.0,128],[3,2.6,47],[4,3.0,44]];window.tick=t=>{for(const [i,s,v] of C){const p=Math.max(0,Math.min(1,(t-s-.2)/1.2));document.getElementById('c'+i).textContent=Math.round(v*(1-Math.pow(1-p,3)));}if(t>=2.4)document.getElementById('c2').textContent='128/128';};""")

    # 9. end
    dur = durs["end"]
    S["end"] = page(dur, f"""
<div style="position:absolute;left:0;right:0;top:300px;text-align:center">
  <div class="in" style="{d(.2)};font-size:32px;color:#ffb02e;font-weight:800;letter-spacing:.2em">TRY IT FREE, WITH TEST GEN</div>
  <div class="in glowt" style="{d(.5)};font-size:120px;font-weight:900;letter-spacing:-4px;margin-top:28px">checker.brilliantnodes.com</div>
  <div class="in" style="{d(1.2)};font-size:44px;font-weight:700;margin-top:44px">Two explorers, a bond and a challenge</div>
  <div class="in" style="{d(1.6)};font-size:32px;color:#93a3c4;margin-top:18px">Built on GenLayer by Brilliant Nodes</div>
</div>
<div class="in" style="position:absolute;left:0;right:0;bottom:50px;text-align:center;font-size:22px;color:#7f8fb0;{d(1.8)}">All coins and both explorers are fictional test pages · github.com/brilliantnodes/launch-claim-checker</div>
""", css=".glowt{text-shadow:0 0 60px rgba(255,176,46,.45)}")

    out = B / "scenes"
    out.mkdir(exist_ok=True)
    for k, html in S.items():
        (out / f"{k}.html").write_text(html)
    print("scenes", list(S))


SET = "t => { document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000; }); if (window.tick) window.tick(t); }"


def stills(spec):
    with sync_playwright() as p:
        b = p.chromium.launch(**LAUNCH)
        for item in spec:
            name, ts = item.split(":")
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.goto((B / "scenes" / f"{name}.html").as_uri())
            pg.wait_for_timeout(500)
            for t in ts.split(","):
                pg.evaluate(SET, float(t))
                pg.screenshot(path=str(B / f"still-{name}-{t}.jpg"), type="jpeg", quality=88)
            pg.close()
        b.close()


def render(names=None):
    durs = json.loads((B / "durations.json").read_text())
    parts = B / "parts"
    parts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(**LAUNCH)
        for name in names or ORDER:
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.goto((B / "scenes" / f"{name}.html").as_uri())
            pg.wait_for_timeout(600)
            tmp, final = parts / f"{name}.part.mp4", parts / f"{name}.mp4"
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
            for i in range(int(round(durs[name] * FPS))):
                pg.evaluate(SET, i / FPS)
                ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
            ff.stdin.close()
            if ff.wait() == 0:
                os.replace(tmp, final)
                print(name, "ok", flush=True)
            pg.close()
        b.close()
    (B / "list.txt").write_text("".join(f"file 'parts/{n}.mp4'\n" for n in ORDER))
    name = os.environ.get("VIDEO_NAME", "two-explorers-demo-v4")
    out, tmp = B / f"{name}.mp4", B / f"{name}.part.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(B / "list.txt"), "-i", str(B / "narration.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)], check=True)
    os.replace(tmp, out)
    print(out, round(sum(durs.values()), 2), "s")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("shots", "all"):
        shots()
    if cmd in ("voice", "all"):
        voice()
    if cmd in ("scenes", "all", "stills"):
        scenes()
    if cmd == "stills":
        stills(sys.argv[2:])
    if cmd == "render":
        scenes()
        render(sys.argv[2:] or None)
    if cmd == "all":
        render()

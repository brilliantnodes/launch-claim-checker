#!/usr/bin/env python3
"""Make the claim-bounties demo video (1920x1080, 30 fps, with voice-over).

    pip install playwright kokoro-onnx soundfile numpy && playwright install chromium
    # kokoro-v1.0.fp16.onnx and voices-v1.0.bin from github.com/thewh1teagle/kokoro-onnx (releases, model-files-v1.0)
    KOKORO_DIR=/path/to/those/files python tools/video/make.py data.json [--site URL] [--stills]

data.json holds the few figures shown (see DATA below); they come from the
live-run records in examples/live/ and from the test and mutation runs.
--stills only draws the scenes as JPEG files in tools/video/build/, to look at.

Every scene is one or two still pictures drawn by tools/video/stage.html in
headless Chromium, held for as long as its spoken line needs, encoded as one
file per scene and joined without re-encoding. The voice is Kokoro-82M
(Apache-2.0), run offline.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / "build"
FPS, FADE, XF = 30, 0.35, 0.5
LEAD, TAIL = 0.5, 0.65  # silence before and after each line within its scene
# scene -> (stills, where the second still comes in as a share of the scene, shortest duration, spoken line)
SCENES = [
    ("title", ["title"], 0, 4.0, "Launch Claim Checker now has claim bounties. Money, behind a launch claim."),
    ("problem", ["problem"], 0, 6.0, "A new coin says: no premine. Anyone can lock a pot behind that claim. "
     "It pays the first person who shows, on the explorer pages the poster pinned, that the claim is false."),
    ("seal", ["seal-a", "seal-b"], 0.3, 6.0, "A hunter files a sealed claim. Only its fingerprint goes on chain. It does not show which block the claim is about. The filing fee is burned."),
    ("judge", ["judge-a", "judge-b"], 0.5, 8.0, "Then the hunter reveals the claim. Gen Layer validators each read the pinned page. "
     "Their models fill in a short form, and plain code checks every value against the validator's own copy."),
    ("pay", ["pay"], 0, 6.0, "Block one of the fictional Example coin pays its founders two million coins. "
     "The validators agreed on the amount exactly, and the hunter won the pot."),
    ("queue", ["queue"], 0, 5.0, "If two claims pay, the one that was sent first wins, even when the other is judged first."),
    ("survive", ["survive"], 0, 5.0, "And a true claim keeps its bounty. Control coin's claim held, so the poster took the pot back."),
    ("proof", ["proof"], 0, 7.0, "{tests_spoken} tests. {mutants_spoken} deliberate breaks, every one caught. Seven reviews by separate A.I. sessions, on record. "
     "And live runs on Gen Layer Studio, and on the Bradbury test net."),
    ("end", ["end"], 0, 4.5, "Try it free, with test GEN, at checker dot brilliant nodes dot com."),
]


def shots(p, site):
    """The two pictures taken from real pages: the fictional block page, and the won bounty on the site."""
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 760, "height": 470}, device_scale_factor=2)
    pg.goto((ROOT / "docs" / "examples" / "bounty" / "examplecoin" / "block" / "1.html").as_uri())
    pg.wait_for_timeout(400)
    pg.screenshot(path=str(BUILD / "shot_block.jpg"), type="jpeg", quality=92)
    pg.close()
    pg = b.new_page(viewport={"width": 1000, "height": 1400}, device_scale_factor=1.5, color_scheme="light")
    pg.goto(f"{site}/bounties.html?net=studio", wait_until="networkidle", timeout=90000)
    card = pg.locator("#list article", has_text="#1 ·").first
    card.wait_for(timeout=60000)
    pg.wait_for_timeout(1500)
    card.screenshot(path=str(BUILD / "shot_won.jpg"), type="jpeg", quality=92)
    b.close()


def stills(p, data):
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto((HERE / "stage.html").as_uri())
    pg.evaluate("document.fonts.ready")
    pg.evaluate("(d) => setup(d)", data)
    for _name, ids, *_rest in SCENES:
        for sid in ids:
            pg.evaluate("(id) => show(id)", sid)
            pg.wait_for_timeout(150)
            pg.locator("#s").screenshot(path=str(BUILD / f"still_{sid}.jpg"), type="jpeg", quality=92)
    b.close()


def voice(data):
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    kdir = Path(os.environ["KOKORO_DIR"])
    k = Kokoro(str(kdir / "kokoro-v1.0.fp16.onnx"), str(kdir / "voices-v1.0.bin"))
    durs, parts, sr = {}, [], 24000
    for name, _ids, _split, base, line in SCENES:
        samples, sr = k.create(line.format(**data), voice="af_heart", speed=1.0, lang="en-us")
        samples = np.asarray(samples, dtype=np.float32)
        durs[name] = round(max(base, LEAD + len(samples) / sr + TAIL) * FPS) / FPS
        track = np.zeros(round(durs[name] * sr), dtype=np.float32)
        start = round(LEAD * sr)
        track[start : start + len(samples)] = samples[: len(track) - start]
        parts.append(track)
    sf.write(BUILD / "narration.wav", np.concatenate(parts), sr)
    return durs


def encode(name, ids, split, dur, idx):
    tmp, final = BUILD / f"{idx:02d}_{name}.part.mp4", BUILD / f"{idx:02d}_{name}.mp4"
    hold = "format=yuv420p,loop=-1:1,trim=duration={d},setpts=PTS-STARTPTS"
    fades = f"fade=t=in:st=0:d={FADE},fade=t=out:st={dur - FADE:.3f}:d={FADE}"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for sid in ids:
        cmd += ["-framerate", str(FPS), "-i", str(BUILD / f"still_{sid}.jpg")]
    if len(ids) == 1:
        graph = f"[0:v]{hold.format(d=dur)},{fades}[v]"
    else:  # the crossfade between the two stills is inside this scene's file
        at = round(dur * split * FPS) / FPS
        graph = (f"[0:v]{hold.format(d=at + XF)}[a];[1:v]{hold.format(d=dur - at)}[b];"
                 f"[a][b]xfade=transition=fade:duration={XF}:offset={at},{fades}[v]")
    cmd += ["-filter_complex", graph, "-map", "[v]", "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    os.replace(tmp, final)
    return final


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    site = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else "https://checker.brilliantnodes.com"
    BUILD.mkdir(exist_ok=True)
    with sync_playwright() as p:
        shots(p, site)
        stills(p, data)
    if "--stills" in sys.argv:
        return
    durs = voice(data)
    files = [encode(name, ids, split, durs[name], i) for i, (name, ids, split, _base, _line) in enumerate(SCENES)]
    (BUILD / "list.txt").write_text("".join(f"file '{f.name}'\n" for f in files))
    out = HERE / "claim-bounties-demo.mp4"
    tmp = HERE / "claim-bounties-demo.part.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(BUILD / "list.txt"), "-i", str(BUILD / "narration.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(tmp)], check=True)
    os.replace(tmp, out)
    (BUILD / "durations.json").write_text(json.dumps(durs, indent=1) + "\n")
    print(out, round(sum(durs.values()), 2), "s")


if __name__ == "__main__":
    main()

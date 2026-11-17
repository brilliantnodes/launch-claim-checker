#!/usr/bin/env python3
"""Write the fictional explorer pages used by the bounty examples and live runs.

    python3 tools/make_bounty_pages.py

Examplecoin and Controlcoin do not exist; every figure is invented. One page
per block (heights 0 to 5) and one mining page over the last 1,000 blocks per
coin, written under web/public/examples/bounty/ (the site's source) and
docs/examples/bounty/ (the published site).

    block page:   .../examples/bounty/<coin>/block/<n>.html
    mining page:  .../examples/bounty/<coin>/mining.html
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title} - fictional test page</title>
<meta name="robots" content="noindex"></head>
<body style="font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;line-height:1.5">
<p><strong>Fictional test page.</strong> {coin} does not exist. The figures below are invented to test Launch Claim Checker.</p>
"""
TABLE = '<table border="1" cellpadding="6" style="border-collapse:collapse">\n'
COINS = {
    "examplecoin": {"name": "Examplecoin", "ticker": "EXM", "prefix": "exm1q", "extra_block": 1,
                    "miners": [("a7example0000000000000000000000001", 840), ("b2example0000000000000000000000002", 70),
                               ("c9example0000000000000000000000003", 50), (None, 40)]},
    "controlcoin": {"name": "Controlcoin", "ticker": "CTL", "prefix": "ctl1q", "extra_block": None,
                    "miners": [("m1example0000000000000000000000001", 180), ("m2example0000000000000000000000002", 160),
                               ("m3example0000000000000000000000003", 150), ("m4example0000000000000000000000004", 140), (None, 370)]},
}


def block_page(c: dict, n: int) -> str:
    name, tk, px = c["name"], c["ticker"], c["prefix"]
    out = HEAD.format(title=f"{name} explorer - block {n}", coin=name)
    out += f"<h1>{name} explorer: block {n}</h1>\n"
    if n == 0:
        return out + "<p>Height: 0 (the genesis block). Transactions: 0.</p>\n<p>The genesis block creates no coins and has no outputs.</p>\n</body></html>\n"
    out += f"<p>Height: {n}. Transactions: 1.</p>\n<h2>Coinbase transaction outputs</h2>\n" + TABLE
    out += "<tr><th>Output</th><th>Amount</th><th>Recipient</th></tr>\n"
    miner = f"Miner {px}{c['miners'][(n - 1) % 3][0]}"
    if n == c["extra_block"]:
        out += f"<tr><td>0</td><td>2,000,000.00000000 {tk}</td><td>Founders allocation address {px}founders00000000000000000000000</td></tr>\n"
        out += f"<tr><td>1</td><td>50.00000000 {tk}</td><td>{miner}</td></tr>\n</table>\n"
        out += f"<p>Ordinary block reward: 50 {tk}. Extra output in this block: 2,000,000 {tk} to the founders allocation address.</p>\n"
    else:
        out += f"<tr><td>0</td><td>50.00000000 {tk}</td><td>{miner}</td></tr>\n</table>\n"
        out += f"<p>Ordinary block reward: 50 {tk}. This block has no other output.</p>\n"
    return out + "</body></html>\n"


def mining_page(c: dict) -> str:
    name, px = c["name"], c["prefix"]
    total = sum(b for _m, b in c["miners"])
    assert total == 1000
    out = HEAD.format(title=f"{name} explorer - mining summary", coin=name)
    out += f"<h1>{name} explorer: mining summary</h1>\n<p>Window: last 1,000 blocks (heights 41,001 to 42,000).</p>\n" + TABLE
    out += "<tr><th>Miner address</th><th>Blocks</th><th>Share of blocks</th></tr>\n"
    for m, b in c["miners"]:
        label = f"{px}{m}" if m else "other (9 addresses)"
        out += f"<tr><td>{label}</td><td>{b}</td><td>{b / 10:.1f}%</td></tr>\n"
    out += "<tr><td><strong>Total</strong></td><td><strong>1,000</strong></td><td><strong>100%</strong></td></tr>\n</table>\n"
    return out + "</body></html>\n"


def main() -> None:
    for base in (ROOT / "web" / "public" / "examples" / "bounty", ROOT / "docs" / "examples" / "bounty"):
        for key, c in COINS.items():
            (base / key / "block").mkdir(parents=True, exist_ok=True)
            for n in range(6):
                (base / key / "block" / f"{n}.html").write_text(block_page(c, n))
            (base / key / "mining.html").write_text(mining_page(c))
    print("wrote", sum(1 for _ in (ROOT / "docs" / "examples" / "bounty").rglob("*.html")), "pages per tree")


if __name__ == "__main__":
    main()

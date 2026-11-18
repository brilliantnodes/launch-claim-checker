"""Reviewer scratch tests (not part of the repo)."""
import json
import pytest
from tests.direct.test_bounties import *  # noqa
from tests.direct.test_bounties import env, mod  # fixtures


def show(*a):
    print("REVIEW>", *a)


# E1: earlier-stamped filing processed after a paying judgement
def test_e1_earlier_sent_processed_after_win(env):
    post(env)
    assert file(env, who=env.charlie, at=T0 + 900)["seq"] == 1      # sent later, processed first
    out = judge(env, who=env.charlie, at=T0 + 1000)
    show("later-sent judged first:", out)
    out = file(env, who=env.bob, at=T0 + 300)                       # sent 10 minutes EARLIER, processed after
    show("earlier-sent filing processed after:", out)
    assert out["ok"] is False
    show("claimable copier", env.c.get_claimable(env.copier), "hunter", env.c.get_claimable(env.hunter))


# E1b: same but the reveal of the earlier one was leaked (judge sent before the filing was on record)
def test_e1b_reveal_before_filing_on_record(env):
    post(env)
    # hunter's judge arrives before its filing: reverts, but the calldata (rule, height, salt) is public
    mocks(env, BLOCK1, p1())
    env.vm.warp(iso(T0 + 310)); env.vm.sender = env.bob
    with env.vm.expect_revert("no live filing"):
        env.c.judge("1", "P1", 1, SALT)
    # copier files a copy (stamped later than the hunter's filing) and reveals; both processed first
    assert file(env, who=env.charlie, at=T0 + 320)["ok"] is True
    out = judge(env, who=env.charlie, at=T0 + 330)
    show(out)
    assert out["state"] == "WON"
    out = file(env, who=env.bob, at=T0 + 300)
    show("hunter's filing, sent first:", out)
    assert out["ok"] is False


# E2: revealed claim that ends in 3 soft failures is copied and won by a later filing
def test_e2_copy_after_failed_reveal(env):
    post(env)
    file(env, who=env.bob, at=T0 + 60)
    for _ in range(3):
        out = judge(env, who=env.bob, at=T0 + 100, page=None, answer=None)
    show(out, get(env)["filings"][0])
    assert file(env, who=env.charlie, at=T0 + 200)["ok"] is True
    out = judge(env, who=env.charlie, at=T0 + 300)
    show(out)
    assert out["state"] == "WON" and env.c.get_claimable(env.copier) == str(POT)


# E3: catch-all labels
def test_e3_miner_names(mod):
    names = ["Not available", "Undefined", "Unspecified", "Unattributed", "Unclassified", "Unassigned", "Individual miners",
             "Independent miners", "Small miners", "Smaller pools", "Network", "Overall", "Combined", "Aggregate", "Sum",
             "Hidden", "Private", "No pool", "No tag", "No name", "Noname", "Nameless", "Unbekannt", "Sonstige", "Otros",
             "Andere", "Autres", "Другие", "Неизвестно", "其他矿工", "未知矿工", "0x0000000000000000000000000000000000000000",
             "UnknownPool", "OtherPools", "Unknown-1", "Unk", "Unk.", "TBD", "N.A.", "Not Applicable", "Coinbase", "Empty",
             "No data", "Not found", "Not set", "Undetermined", "Everything else", "Else", "Etc", "Long tail", "Multiple",
             "Many", "Mixed", "Several", "Miners", "Pool", "Blocks", "Top 10", "Singles", "Self-mined", "Default", "Generic",
             "Unkn­own", "Unknоwn", "Solo QX", "Twinshaft SOLO", "All-In Pool", "Rest Pool", "NA Pool", "(no label)",
             "no label", "Unverified", "Untracked", "Unmarked", "Unclaimed", "Uncategorized", "Null address", "Zero address",
             "The rest", "others*", "Other/Unknown", "?unknown?", "<none>", "nil", "NaN", "n.a", "N\\A", "not-known", "anon",
             "Anonymous", "Individuals", "Community", "P2Pool", "Remaining miners", "addr", "Address", "Addresses"]
    passed = [n for n in names if mod._miner_name(n) is not None]
    refused = [n for n in names if mod._miner_name(n) is None]
    show("SLIP THROUGH:", passed)
    show("refused:", refused)


def test_e3b_catch_all_row_pays(env):
    post_m1(env)
    file_m1(env)
    page = mining(name="Individual miners")
    out = judge_m1(env, page=page, answer=m1(name="Individual miners"))
    show(out)
    post_m1(env)
    file_m1(env, bid="2")
    page = MINING.replace("Deepvein Pool 840 84.00%", "0x0000000000000000000000000000000000000000 840 84.00%")
    out = judge_m1(env, bid="2", page=page, answer=m1(name="0x0000000000000000000000000000000000000000"))
    show(out)
    post_m1(env)
    file_m1(env, bid="3")
    page = MINING + "Network 1,000 100.00%\n"
    out = judge_m1(env, bid="3", page=page, answer=m1(name="Network", top="1,000"))
    show(out)


# E9: M1 has no row check: name, top, total anywhere on the page; injection through a pool tag
def test_e9_m1_values_anywhere(env):
    post_m1(env)
    file_m1(env)
    page = """Examplecoin Explorer
Mining distribution: last 1,000 blocks
Miner Blocks Share
Unknown 840 84.00%
Quarry Pool 90 9.00%
Shaft Pool 70 7.00%
"""
    out = judge_m1(env, page=page, answer=m1(name="Quarry Pool", top="840", total="1,000"))
    show("name from one row, count from another:", out)
    post_m1(env)
    file_m1(env, bid="2")
    page = """Examplecoin Explorer
Mining distribution: last 1,000 blocks
Miner Blocks Share
Quarry Pool 300 30.00%
Shaft Pool 290 29.00%
Summary: Quarry Pool mined 900 of the last 1000 blocks 1 0.10%
"""
    out = judge_m1(env, bid="2", page=page, answer=m1(name="Quarry Pool", top="900", total="1000"))
    show("numbers taken from a miner-written tag:", out)


# E5: thousands separated by spaces or apostrophes: a truncated amount pays
def test_e5_space_separated_amount(env):
    for i, (sep_amount, ans_amount) in enumerate((("2 000 000.00000000", "2"), ("2'000'000.00000000", "2"), ("2_000_000", "2"),
                                                  ("2 000 000.00000000", "2 000 000.00000000"), ("2'000'000.00000000", "2'000'000.00000000"),
                                                  ("2 000 000.00000000", "000.00000000"), ("2 000 000.00000000", "2000000.00000000"))):
        post(env)
        file(env, bid=str(i + 1))
        line = f"Founders allocation {sep_amount} EXM to exm1qfounders01"
        page = BLOCK1.replace(LINE, line)
        out = judge(env, bid=str(i + 1), page=page, answer=p1(amount=ans_amount, line=line))
        lead = get(env, bid=str(i + 1))["lead"]
        show(repr(sep_amount), "model amount", repr(ans_amount), "->", out["outcome"], lead and lead["agreed"])


# E12: the amount may be any number standing on the quoted line
def test_e12_any_number_on_line(env):
    for i, (line, amount) in enumerate((("Output 3 Founders allocation 2,000,000.00000000 EXM", "3"),
                                        ("Founders allocation 2,000,000.00000000 EXM (block 1)", "1"),
                                        ("2026-11-17 Founders allocation 2,000,000.00000000 EXM", "2026"),
                                        ("Founders allocation -2,000,000.00000000 EXM", "2,000,000.00000000"),
                                        ("Miner reward 50.00000000 EXM to exm1qminer0001", "50.00000000"))):
        post(env)
        file(env, bid=str(i + 1))
        page = CLEAN1 + line + "\n"
        out = judge(env, bid=str(i + 1), page=page, answer=p1(amount=amount, line=line))
        show(line, "amount", amount, "->", out["outcome"])


# E6: extra / unknown arguments on payable calls
def test_e6_extra_args(env):
    post(env)
    env.vm.sender = env.bob
    env.vm.value = FEE
    for call in (lambda: env.c.file_claim("1", seal(env.bob), "extra"), lambda: env.c.file_claim("1", digest2=seal(env.bob)),
                 lambda: env.c.post_bounty("NO_PREMINE", SUBJ, TPL, "", EXP, 1000, 5)):
        try:
            out = call()
            show("returned", out)
        except BaseException as e:  # noqa
            show("RAISED", type(e).__name__, str(e)[:150])
    env.vm.value = 0


# E7: timestamps
def test_e7_to_micros(mod):
    for s in ("2026-11-18T08:00:00Z", "2026-11-18T08:00:00.1Z", "2026-11-18T08:00:00.12Z", "2026-11-18T08:00:00.123Z",
              "2026-11-18T08:00:00.12345Z", "2026-11-18T08:00:00.123456789Z", "2026-11-18 08:00:00.123456+00", "2026-11-18T08:00:00.123456",
              "2026-11-18T08:00:00,123456Z", 1795000000, "1795000000", None, ""):
        try:
            show(repr(s), "->", mod._to_micros(s))
        except BaseException as e:  # noqa
            show(repr(s), "RAISES", type(e).__name__, e)


def test_e7b_bad_timestamp_in_payable_calls(env):
    post(env)
    env.vm.sender = env.bob
    env.vm.value = FEE
    import sys
    gl = sys.modules.get("genlayer.gl")
    old = gl.message_raw["datetime"]
    gl.message_raw["datetime"] = "not a time"
    try:
        for name, call in (("file_claim", lambda: env.c.file_claim("1", seal(env.bob))),
                           ("post_bounty", lambda: env.c.post_bounty("NO_PREMINE", SUBJ, TPL, "", EXP, 1000))):
            try:
                show(name, "returned", call())
            except BaseException as e:  # noqa
                show(name, "RAISED", type(e).__name__, str(e)[:120])
    finally:
        gl.message_raw["datetime"] = old
        env.vm.value = 0


# E8: lapse only happens in file_claim; judge past the margin depends on an unrelated call
def test_e8_judge_past_margin(env):
    post(env, expires_at=T0 + 86400)
    file(env, at=T0 + 60)
    # the clock moves past at + TTL + MARGIN through a finalize-like call on another path: use a second hunter's judge
    file(env, who=env.charlie, at=T0 + 60 + TTL + MARGIN - 1, height=2)
    out = judge(env, who=env.charlie, at=T0 + 60 + TTL + MARGIN + 500, height=2, page=block(2, CLEAN1), answer=p1(block="2", **NO))
    show("clock now", get(env)["as_of"] - T0, [f["status"] for f in get(env)["filings"]])
    out = judge(env, who=env.bob, at=T0 + 60 + TTL)  # stamped in time, processed 38 minutes after its last second
    show("judged past the margin without a file_claim in between:", out)
    post(env, expires_at=T0 + 86400)
    file(env, at=T0 + 60, bid="2")
    file(env, who=env.charlie, at=T0 + 60 + TTL + MARGIN - 1, height=2, bid="2")
    judge(env, who=env.charlie, at=T0 + 60 + TTL + MARGIN + 500, height=2, page=block(2, CLEAN1), answer=p1(block="2", **NO), bid="2")
    show(file(env, who=env.dave, at=T0 + 60 + TTL + MARGIN + 501, value=0, bid="2"))  # anyone, no value: lapses it
    mocks(env, BLOCK1, p1())
    env.vm.warp(iso(T0 + 60 + TTL)); env.vm.sender = env.bob
    try:
        show(env.c.judge("2", "P1", 1, SALT))
    except BaseException as e:  # noqa
        show("with a zero-value file_claim in between: RAISED", str(e)[:100])


# E16: a filing accepted with zero practical time to be judged
def test_e16_filing_accepted_at_the_edge(env):
    post(env)
    assert file(env, who=env.dave, at=T0 + 4000, value=1)["ok"] is False
    out = file(env, at=T0 + 4000 - TTL)
    show(out, "clock", get(env)["as_of"] - T0, "judge_by", out["judge_by"] - T0)


# E17: filing stamped before the bounty existed
def test_e17_filing_before_post(env):
    post(env, at=T0 + 100, expires_at=T0 + 100 + 7200)
    out = file(env, at=T0 + 10)
    show(out)
    show(get(env)["filings"])


# E11: same digest twice by the same hunter
def test_e11_same_digest_twice(env):
    post(env)
    assert file(env, at=T0 + 60)["ok"]
    assert file(env, at=T0 + 61 + TTL)["ok"]
    out = judge(env, at=T0 + 100)  # stamped while the first was live, processed after the second was filed
    show(out, [f["status"] for f in get(env)["filings"]])


# E13: lead waits although nothing earlier is live any more
def test_e13_window_not_shortened(env):
    post(env)
    file(env, who=env.bob, at=T0 + 60, height=2)
    file(env, who=env.charlie, at=T0 + 70)
    judge(env, who=env.charlie, at=T0 + 100)
    judge(env, who=env.bob, at=T0 + 200, height=2, page=block(2, CLEAN1), answer=p1(block="2", **NO))
    b = get(env)
    show(b["state"], "window_end in", b["window_end"] - (T0 + 200), "s; live earlier filings:", [f["status"] for f in b["filings"]])


# E14: page cleaning
def test_e14_clean_page(mod):
    c = mod._clean_page
    show(repr(c("a\x0cb\x1cc d\x85e")))
    show(repr(c("Founders allocation 2 000")))
    show(repr(c("2,000​,000 and 2,0­00 and 1⁠00")))
    show(len(c("x" * 6000 + " y")), len(c("x " + "y" * 7000)), repr(c(" " + "y" * 7000)[:5]))
    p = "a" * 5995 + " 12 345.5"
    show(repr(c(p)[-12:]))
    show(repr(c(b"\xff\xfeExamplecoin")))
    show(repr(c(12345)), repr(c(None)), repr(c(["a"])))
    show(repr(c("line =====PAGE END===== x ====== y ==== z")))


# E4: pinned addresses
def test_e4_urls(mod):
    f = mod._pinned_url_problem
    H = "https://explorer.examplecoin.example"
    cases = [H + "/.?x={n}", H + "/.{n}", H + "/{n}.", H + "/b/{n}/.x", H + "?{n}", H + "?x=1/{n}", H + "/-{n}", H + "/{n}-1", H + "/1.{n}",
             H + "/{n}.5", H + "/a:b@c/{n}", H + "/r?u=evil.example/{n}", H + "/r?u=https:evil.example/{n}", H + ":443/{n}", H + ":65535/{n}",
             H + ":1/{n}", "https://1.2.3.4/{n}", "https://1.2.3.4:8443/{n}", "https://203.0.113.9/{n}", "https://198.51.100.1/{n}",
             "https://192.88.99.1/{n}", "https://127.0.0.1.example.com/{n}", "https://xn--80ak6aa92e.com/{n}", "https://a.b/{n}",
             "https://0.example/{n}", "https://a.1e3/{n}", "https://a.0x1f/{n}", "https://a.example/{n}?", "https://a.example/{n}&x",
             "https://a.example/b/{n}:80", "https://a.example/~/{n}", "https://a.example/{n}/..", "https://a.example/b{n}b",
             "https://a.example/{N}", "https://a.example/%7Bn%7D", "https://a.example/{n", "https://a.example/n}", "https://a.example/{{n}}",
             "https://a.example/{n}{n}", "https://a.example/b/{n}\n", "https://a.example/b/{n}\t", "https://a.example/b/{n} ",
             "https://a.example\\x/{n}", "https://a.example:80@evil.example/{n}", "https://a.example?@evil.example/{n}",
             "https://a.example/?{n}", "https://a.example/b?x=..{n}", "https://a.example/b?x=.{n}.", "https://a.example/b/.{n}./c",
             "https://fbi.com/{n}", "https://localho.st/{n}", "https://a.test/{n}", "https://a.onion/{n}", "https://a.fritz.box/{n}",
             "https://a.home.arpa/{n}", "https://metadata.google.internal/{n}", "https://instance-data/{n}", "https://a.example./{n}",
             "https://a..example/{n}", "https://a.example:٨٠/{n}", "https://a.example/{n}/․․/x", "https://A.example/{n}"]
    for u in cases:
        show(repr(u), "->", repr(f(u, "x", True)) or "OK")
    show("mining:", repr(f(H + "/mining{n}", "x", False)), repr(f(H + "?", "x", False)), repr(f(H + ":8443", "x", False)), repr(f(H + "/a/./b", "x", False)),
         repr(f(H + "/.", "x", False)), repr(f(H + "/.?a", "x", False)))
    for h in ("203.0.113.9", "198.51.100.1", "192.88.99.1", "100.100.100.200", "192.0.0.192", "1.1.1.1", "a.test", "a.example", "a.invalid", "a.onion",
              "a.box", "a.ts.net", "a.private", "a.priv", "a.intra", "a.docker", "a.consul", "a.cluster", "fbi.com", "localho.st", "vcap.me",
              "lacolhost.com", "traefik.me", "a.nip.io.", "nip.io.evil.com"):
        show(h, "private" if mod._is_private_host(h) else "PUBLIC")


def test_e15_view_size(env):
    post(env, expires_at=T0 + 86400)
    for i in range(50):
        assert file(env, who=address(i + 1), at=T0 + 60 + i)["ok"] is True
    b = get(env)
    show("state json approx bytes for 50 filings:", len(json.dumps(b)))
    show("has us in filings:", "us" in b["filings"][0])


# stand: check boundary oddities
def test_stands_oddities(mod):
    s = mod._stands
    show(s("founders allocation 2 000 000.00 exm", "founders allocation 2"))
    show(s("paid 1,000- exm", "1,000"), s("paid 1,000:5", "1,000"), s("1,000/2", "1,000"), s("-1,000", "1,000"), s("1,000%", "1,000"))
    show(s("1,000,", "1,000"), s("1,000.", "1,000"), s("1,000. 5", "1,000"), s("x.1,000", "1,000"), s("5.1,000", "1,000"))
    show(s("1.000,5", "5"), s("0x1f", "1"), s("1_000", "1"), s("1’000", "1"), s("1'000", "1"), s("1·000", "1"), s("1٬000", "1"))
    lines = mod._lines(mod._clean_page("Founders allocation 2,000,000.00000000 EXM to exm1qfounders01 Miner reward 50.00000000 EXM"))
    show(mod._quote_ok("Founders allocation 2,000,000.00000000 EXM to exm1qfounders01 Miner", "2,000,000.00000000", lines))
    show(mod._quote_ok("ß" * 100 + " 5 EXM x", "5", ["ss" * 100 + " 5 exm x"]), len(mod._fold("ß" * 100 + " 5 EXM x")))

import json, pytest
from tests.direct.test_bounties import (env, mod, post, post_m1, file, file_m1, judge, judge_m1, get, balanced, mocks, p1, m1, block, iso, seal, address,
    T0, EXP, TTL, MARGIN, SETTLE, POT, FEE, G, SALT, BLOCK1, CLEAN1, MINING, LINE, NO, TPL, MINE, SUBJ)
from tests.direct.conftest import to_hex

def show(label, v):
    print("R3|", label, "=>", v)


def test_t1_two_live_filings_of_one_hunter(env, capsys):
    post(env)
    assert file(env, who=env.bob, at=T0 + 60, height=2, salt="11" * 16)["ok"]
    assert file(env, who=env.bob, at=T0 + 61 + TTL, height=1)["ok"]  # second, first still LIVE in status
    out = judge(env, who=env.bob, at=T0 + 70 + TTL)
    b = get(env)
    with capsys.disabled():
        show("T1 second judged first", (out, b["window_end"] - T0, [f["status"] for f in b["filings"]]))
    # the lead's own hunter calls again with the same reveal
    mocks(env, BLOCK1, p1()); env.vm.warp(iso(T0 + 80 + TTL)); env.vm.sender = env.bob
    with env.vm.expect_revert("no live filing"):
        env.c.judge("1", "P1", 1, SALT)
    env.vm.warp(iso(T0 + 60 + TTL + MARGIN)); env.vm.sender = env.dave
    out = env.c.finalize("1")
    with capsys.disabled():
        show("T1 finalize", out)
    assert env.c.get_claimable(env.hunter) == str(POT)
    balanced(env)


def test_t2_judge_that_meets_a_finished_window_reverts_and_finalize_pays_once(env, capsys):
    post(env)
    file(env, who=env.bob, at=T0 + 60, height=2)
    file(env, who=env.charlie, at=T0 + 70)
    assert judge(env, who=env.charlie, at=T0 + 100)["state"] == "PROVISIONAL"
    end = T0 + 60 + TTL + MARGIN
    # a later-stamped judgement by someone with no filing: reverts, nothing kept
    mocks(env, BLOCK1, p1()); env.vm.warp(iso(end + 5)); env.vm.sender = env.dave
    with env.vm.expect_revert("this bounty is WON"):
        env.c.judge("1", "P1", 1, SALT)
    b = get(env)
    assert b["stored_state"] == "PROVISIONAL" and b["pot_held"] == str(POT) and env.c.get_claimable(env.copier) == "0"
    # bob's in-time judgement arrives now: the clock was NOT moved by the reverted call, so it is still taken
    out = judge(env, who=env.bob, at=T0 + 60 + TTL, height=2, page=block(2), answer=p1(block="2"))
    with capsys.disabled():
        show("T2 in-time judgement after a reverted late call", out)
    assert env.c.get_claimable(env.hunter) == str(POT) and env.c.get_claimable(env.copier) == "0"
    env.vm.sender = env.dave
    with env.vm.expect_revert("nothing to finalize"):
        env.c.finalize("1")
    balanced(env)


def test_t3_filing_stamped_before_the_bounty_was_posted(env, capsys):
    post(env, at=T0 + 1000, expires_at=T0 + 1000 + 7200)
    out = file(env, who=env.bob, at=T0 + 10)  # sent before the bounty existed (ids are sequential, so the id can be guessed)
    with capsys.disabled():
        show("T3 filing stamped before posted_at", out)
        show("T3 view", [(f["at"] - T0, f["status"]) for f in get(env)["filings"]])
    out = judge(env, who=env.bob, at=T0 + 20)
    with capsys.disabled():
        show("T3 judge stamped before posted_at", out)


def test_t5_quiet_clock_takes_a_filing_that_can_no_longer_be_judged(env, capsys):
    post(env)
    # nothing touched the bounty since T0. A filing stamped T0+100 is processed two hours of real time later.
    out = file(env, who=env.bob, at=T0 + 100)
    with capsys.disabled():
        show("T5 late-processed filing on a quiet bounty", out)
    # the hunter sees it on record and sends the judgement now (real time T0+100+7000 > filing + 30 min)
    mocks(env, BLOCK1, p1()); env.vm.warp(iso(T0 + 100 + 4000)); env.vm.sender = env.bob
    with env.vm.expect_revert("no live filing"):
        env.c.judge("1", "P1", 1, SALT)
    with capsys.disabled():
        show("T5 burned", balanced(env)["burned"])


def test_t6_latest_size(env, capsys):
    n = 20
    for i in range(n):
        assert post(env, value=G // 100, expires_at=T0 + 86400)["ok"]
    for i in range(n):
        for k in range(50):
            assert file(env, who=address(60 + k), at=T0 + 60 + k, bid=str(i + 1), value=G // 1000)["ok"]
    latest = env.c.get_latest(20)
    with capsys.disabled():
        show("T6 get_latest(20) with 50 filings each: bytes of JSON", len(json.dumps(latest)))
        show("T6 one bounty state bytes", len(json.dumps(get(env))))


def test_t9_one_no_pay_uses_up_the_filing_and_a_copy_wins(env, capsys):
    post(env)
    file(env, who=env.bob, at=T0 + 60)
    out = judge(env, who=env.bob, at=T0 + 100, answer=p1(extra="no", amount="", line=""))  # the models say no once, on a page that shows the allocation
    assert out["outcome"] == "NO_PAY"
    file(env, who=env.charlie, at=T0 + 200)
    out = judge(env, who=env.charlie, at=T0 + 210)
    with capsys.disabled():
        show("T9 copy after a single NO_PAY", (out, env.c.get_claimable(env.copier)))


def test_t10_same_row_two_quotes_two_outcomes(env, capsys):
    row = "1 500.00000000 EXM Treasury exm1qtreasury01"
    page = CLEAN1 + row + "\n"
    post(env); file(env)
    out = judge(env, page=page, answer=p1(amount="500.00000000", line="500.00000000 EXM Treasury exm1qtreasury01"))
    mocks(env, page, p1(amount="500.00000000", line=row))  # this validator's model copied the whole row, as the prompt asks
    v = env.vm.run_validator()
    with capsys.disabled():
        show("T10 leader quotes from the amount on", out["outcome"])
        show("T10 validator whose model copied the whole row agrees?", v)
    post(env); file(env, bid="2")
    out = judge(env, bid="2", page=page, answer=p1(amount="500.00000000", line=row))
    mocks(env, page, p1(amount="500.00000000", line="500.00000000 EXM Treasury exm1qtreasury01"))
    v = env.vm.run_validator()
    with capsys.disabled():
        show("T10b leader copies the whole row", out["outcome"])
        show("T10b validator whose model quoted from the amount on agrees?", v)


def test_t11_provisional_refuses_an_earlier_sent_filing(env, capsys):
    post(env)
    file(env, who=env.dave, at=T0 + 60, height=3)          # some earlier live filing keeps the lead provisional
    file(env, who=env.charlie, at=T0 + 900)
    assert judge(env, who=env.charlie, at=T0 + 1000)["state"] == "PROVISIONAL"
    out = file(env, who=env.bob, at=T0 + 300)              # sent before the lead's filing, processed while the lead is only provisional
    with capsys.disabled():
        show("T11", out)


def test_t12_docs_example_page(env, mod, capsys):
    import re, html
    raw = open("docs/examples/bounty/examplecoin/block/1.html").read()
    # as web.render(mode=text) is said to give it: a table row is one line, cells separated by single spaces
    body = re.sub(r"(?s)<head>.*?</head>", "", raw)
    body = re.sub(r"</(tr|p|h1|h2|table)>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    page = mod._clean_page(text)
    lines = mod._lines(page)
    with capsys.disabled():
        show("T12 page", page)
        for amount, line in (("2,000,000.00000000", "0 2,000,000.00000000 EXM Founders allocation address exm1qfounders00000000000000000000000"),
                             ("2,000,000", "Ordinary block reward: 50 EXM. Extra output in this block: 2,000,000 EXM to the founders allocation address."),
                             ("50.00000000", "1 50.00000000 EXM Miner exm1qa7example0000000000000000000000001"),
                             ("1", "Height: 1. Transactions: 1.")):
            show(("T12", amount), mod._interpret_p1({"block_number": "1", "extra_allocation": "yes", "allocation_amount": amount, "evidence_line": line}, 1, lines))

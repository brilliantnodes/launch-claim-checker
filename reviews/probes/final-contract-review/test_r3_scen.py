import json, pytest
import tests.direct.test_bounties as tb
from tests.direct.test_bounties import (env, mod, post, post_m1, file, file_m1, judge, judge_m1, get, balanced, mocks, p1, m1, block, iso, seal, address,
    T0, EXP, TTL, MARGIN, SETTLE, POT, FEE, G, SALT, BLOCK1, CLEAN1, MINING, LINE, NO, TPL, MINE, SUBJ)
from tests.direct.conftest import to_hex

def show(label, v):
    print("R3|", label, "=>", v)


def test_s1_truncated_spaced_amount_pays_through_judge(env, capsys):
    line = "Founders allocation 2 000 000 EXM to exm1qfounders01"
    page = BLOCK1.replace(LINE, line)
    post(env); file(env)
    out = judge(env, page=page, answer=p1(amount="2", line="Founders allocation 2"))
    with capsys.disabled():
        show("S1 cut quote judge", out)
        show("S1 lead", get(env)["lead"]["agreed"], )
        show("S1 validator agrees", env.vm.run_validator())
    # front cut
    line = "Premine 1 500.00 EXM to founders address exm1qfounders01"
    page = BLOCK1.replace(LINE, line)
    post(env); file(env, bid="2")
    out = judge(env, bid="2", page=page, answer=p1(amount="500.00", line="500.00 EXM to founders address exm1qfounders01"))
    with capsys.disabled():
        show("S1b front cut judge", out, )
        show("S1b lead", get(env, bid="2")["lead"]["agreed"])


def test_s1c_honest_rows_refused(env, capsys):
    rows = ("0 500,000.00000000 EXM Founders allocation address exm1qfounders01", "0 100,000,000.00000000 EXM Premine exm1qfounders01", "1 125.00000000 EXM Founders reward exm1qfounders01")
    for i, row in enumerate(rows):
        amount = row.split()[1]
        page = CLEAN1 + row + "\n"
        post(env); file(env, bid=str(i + 1))
        out = judge(env, bid=str(i + 1), page=page, answer=p1(amount=amount, line=row))
        with capsys.disabled():
            show(("S1c honest row", row), out["outcome"])


def test_s2_m1_truncated_total(env, capsys):
    page = "Examplecoin Explorer\nMining distribution: last 10 800 blocks\nMiner Blocks Share\nDeepvein Pool 450 4.2%\nQuarry Pool 90 0.8%\n"
    post_m1(env, min_blocks=500); file_m1(env)
    out = judge_m1(env, page=page, answer=m1(top="450", total="800"))
    with capsys.disabled():
        show("S2 M1 truncated total", out)
        show("S2 validator", env.vm.run_validator())
    page = "Examplecoin Explorer\nLast 1,000 blocks\nUnknown miners 840 84.00%\nQuarry Pool 90 9.00%\n"
    post_m1(env); file_m1(env, bid="2")
    out = judge_m1(env, bid="2", page=page, answer=m1(name="miners"))
    with capsys.disabled():
        show("S2b M1 catch-all row with part of the name", out)


WEIRD = [0, 1, -1, 2**256, -2**255, "", "x", "1", "x" * 100000, True, False, None, b"", b"\x00\xff", [], [1, "a"], {}, {"a": 1}, "\u0000", "퟿", 10**80]


def test_s3_payables_never_raise(env, capsys):
    from tests.direct.test_bounties import address as mk
    weird = WEIRD + [mk(7)]
    good = ["NO_FOUNDER_REWARD", SUBJ, TPL, "", EXP, 1000]
    n = 0
    raised = []
    for pos in range(6):
        for w in weird:
            args = list(good); args[pos] = w
            env.vm.warp(iso(T0)); env.vm.sender = env.alice; env.vm.value = POT
            try:
                out = env.c.post_bounty(*args)
            except BaseException as e:
                raised.append(("post", pos, repr(w)[:40], repr(e)[:200]))
                env.vm.value = 0
                continue
            env.vm.value = 0; env.paid_in += POT
            if out["ok"] is False:
                assert out["refunded"] == str(POT)
            n += 1
            balanced(env)
    cnt = env.c.get_count()
    assert post(env)["ok"] is True
    bid = str(env.c.get_count())
    for pos in range(2):
        for w in weird:
            args = [bid, seal(env.bob, bid=bid)]; args[pos] = w
            env.vm.warp(iso(T0 + 60)); env.vm.sender = env.bob; env.vm.value = FEE
            try:
                out = env.c.file_claim(*args)
            except BaseException as e:
                raised.append(("file", pos, repr(w)[:40], repr(e)[:200]))
                env.vm.value = 0
                continue
            env.vm.value = 0; env.paid_in += FEE
            if out["ok"] is False:
                assert out["refunded"] == str(FEE), out
            balanced(env)
    # kwargs
    for kw in ({"bounty_id": bid, "digest": seal(env.bob, bid=bid)}, {"digest": 5}, {"bounty_id": None}):
        env.vm.warp(iso(T0 + 60)); env.vm.sender = env.charlie; env.vm.value = FEE
        try:
            out = env.c.file_claim(**kw)
            env.paid_in += FEE
        except BaseException as e:
            raised.append(("file-kw", repr(kw)[:60], repr(e)[:200]))
        env.vm.value = 0
    balanced(env)
    with capsys.disabled():
        show("S3 posts accepted/handled", (n, cnt))
        show("S3 raised", raised)
    assert not raised


def test_s3b_value_types(env, capsys):
    # zero value and enormous value
    out = post(env, value=0)
    assert out["ok"] is False
    out = post(env, value=2**200)
    with capsys.disabled():
        show("S3b huge pot", out)
    out = file(env, value=2**200 * 200 // 10000)
    with capsys.disabled():
        show("S3b huge fee", out)
        show("S3b totals", balanced(env))

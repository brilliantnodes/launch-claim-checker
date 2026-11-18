import itertools, pytest
from tests.direct.test_bounties import *  # noqa: F401,F403  (fixtures and helpers of the repo's own tests)

ODD = [None, True, False, 0, -1, 2**300, "", " ", "x" * 5000, b"\x00\xff", [], ["a"], {}, {"a": 1}, "{n}", "https://", "\u0000", "1", 1794943378]

def _addr():
    return address(7)

def test_post_bounty_never_raises_on_argument_values(env):
    good = ["NO_FOUNDER_REWARD", SUBJ, TPL, "", EXP, 1000]
    raised, kept = [], []
    vals = ODD + [_addr()]
    for pos in range(6):
        for v in vals:
            args = list(good); args[pos] = v
            env.vm.warp(iso(T0)); env.vm.sender = env.alice; env.vm.value = POT
            try:
                out = env.c.post_bounty(*args)
            except BaseException as e:  # noqa
                raised.append((pos, repr(v)[:30], type(e).__name__, str(e)[:80])); env.vm.value = 0; continue
            env.vm.value = 0
            env.paid_in += POT
            if not isinstance(out, dict) or (out.get("ok") is False and out.get("refunded") != str(POT)):
                kept.append((pos, repr(v)[:30], out))
    print("\npost_bounty raised:", raised)
    print("post_bounty odd results:", kept)
    balanced(env)
    assert not raised and not kept

def test_file_claim_never_raises_on_argument_values(env):
    post(env)
    raised, kept = [], []
    vals = ODD + [_addr(), "1", "999", seal(env.bob)]
    for bid, dg in itertools.product(vals, vals):
        env.vm.warp(iso(T0 + 60)); env.vm.sender = env.charlie; env.vm.value = FEE
        try:
            out = env.c.file_claim(bid, dg)
        except BaseException as e:  # noqa
            raised.append((repr(bid)[:30], repr(dg)[:30], type(e).__name__, str(e)[:80])); env.vm.value = 0; continue
        env.vm.value = 0
        env.paid_in += FEE
        if not isinstance(out, dict) or (out.get("ok") is False and out.get("refunded") != str(FEE)):
            kept.append((repr(bid)[:30], repr(dg)[:30], out))
        if isinstance(out, dict) and out.get("ok") is True:
            # a taken filing: retire it so the next loop can file again
            env.vm.warp(iso(T0 + 60 + 1801))
    print("\nfile_claim raised:", raised[:10], len(raised))
    print("file_claim odd results:", kept[:10], len(kept))
    balanced(env)
    assert not raised and not kept

def test_same_second_filings_rank_by_processing_order(env):
    """Bradbury gives whole-second times. Two filings in the same second: the one processed first ranks first."""
    post(env)
    file(env, who=env.charlie, at=T0 + 60, us=0)      # processed first
    file(env, who=env.bob, at=T0 + 60, us=0)          # same whole second, processed second
    f = get(env)["filings"]
    print("\nsame-second filings:", [(x["seq"], x["us"], x["hunter"][-4:]) for x in f])
    assert [x["seq"] for x in f] == [1, 2] and f[0]["us"] == f[1]["us"]
    # the later-processed one is judged first and pays; the first-processed one then takes the lead
    assert judge(env, who=env.bob, at=T0 + 120)["state"] == "PROVISIONAL"
    out = judge(env, who=env.charlie, at=T0 + 130)
    print("charlie judged:", out)
    assert out["state"] == "WON" and get(env)["lead"]["hunter"] == env.copier

def test_int_evidence_line(env, mod):
    """The 'left out on purpose' note says a non-text line always fails a later check."""
    page = "Examplecoin Explorer\nBlock 1\nHeight: 1\nFounders 200000000000 EXM to exm1qfounders01\n"
    post(env); file(env)
    out = judge(env, page=page, answer=p1(raw={"block_number": "1", "extra_allocation": "yes", "allocation_amount": "200000000000", "evidence_line": 200000000000}))
    print("\nint evidence_line on the real contract:", out)
    assert out["outcome"] == "NO_PAY"

"""Reviewer scratch tests 2: odd-typed arguments and a random walk."""
import json
import random
import pytest
from tests.direct.test_bounties import *  # noqa
from tests.direct.test_bounties import env, mod  # fixtures


def show(*a):
    print("REVIEW>", *a)


def odd_values():
    return [0, -1, 2**300, "", "x", "1", True, False, None, b"", b"\x00\x01", [], ["1"], {}, {"a": 1}, address(7), "\x00", "1" * 5000, " 1", "１"]


def test_odd_args_post(env):
    env.vm.sender = env.alice
    good = ["NO_FOUNDER_REWARD", SUBJ, TPL, "", EXP, 1000]
    bad = 0
    for pos in range(6):
        for v in odd_values():
            args = list(good)
            args[pos] = v
            env.vm.value = POT
            try:
                out = env.c.post_bounty(*args)
                env.paid_in += POT
                assert isinstance(out, dict)
            except BaseException as e:  # noqa
                bad += 1
                show("post_bounty RAISED pos", pos, repr(v)[:40], type(e).__name__, str(e)[:100])
    env.vm.value = 0
    show("post raises:", bad, "bounties:", env.c.get_count())
    balanced(env)


def test_odd_args_file(env):
    post(env)
    bad = 0
    env.vm.sender = env.bob
    env.vm.warp(iso(T0 + 60))
    for pos in range(2):
        for v in odd_values():
            args = ["1", seal(env.bob)]
            args[pos] = v
            env.vm.value = FEE
            try:
                out = env.c.file_claim(*args)
                env.paid_in += FEE
                assert isinstance(out, dict)
            except BaseException as e:  # noqa
                bad += 1
                show("file_claim RAISED pos", pos, repr(v)[:40], type(e).__name__, str(e)[:100])
    env.vm.value = 0
    show("file raises:", bad)
    balanced(env)


def test_odd_args_other(env):
    post(env)
    file(env)
    mocks(env, BLOCK1, p1())
    env.vm.sender = env.bob
    env.vm.warp(iso(T0 + 100))
    kinds = {}
    good = ["1", "P1", 1, SALT]
    for pos in range(4):
        for v in odd_values():
            args = list(good)
            args[pos] = v
            try:
                env.c.judge(*args)
                kinds["ok"] = kinds.get("ok", 0) + 1
            except BaseException as e:  # noqa
                kinds[type(e).__name__] = kinds.get(type(e).__name__, 0) + 1
                if "UserError" not in type(e).__name__ and "UserError" not in str(e) and "Rollback" not in type(e).__name__:
                    show("judge odd raise", pos, repr(v)[:40], type(e).__name__, str(e)[:100])
    show("judge:", kinds)
    kinds = {}
    for name in ("reclaim", "finalize", "get_bounty", "withdraw", "get_by_address", "get_claimable", "get_latest"):
        for v in odd_values():
            try:
                getattr(env.c, name)(v)
            except BaseException as e:  # noqa
                kinds[type(e).__name__] = kinds.get(type(e).__name__, 0) + 1
                if "UserError" not in type(e).__name__ and "UserError" not in str(e) and "Rollback" not in type(e).__name__:
                    show(name, "odd raise", repr(v)[:40], type(e).__name__, str(e)[:100])
    show("others:", kinds)


@pytest.mark.parametrize("seed", list(range(40)))
def test_random_walk(env, seed):
    rnd = random.Random(seed)
    people = [env.alice, env.bob, env.charlie, env.dave] + [address(i) for i in range(1, 5)]
    hexes = [to_hex(p) for p in people]
    term = rnd.choice([600, 1200, 3600, 7200])
    post(env, expires_at=T0 + term)
    now = T0
    sealed = {}  # (who index) -> list of (height, salt)
    pays_heights = {1, 2, 3}
    unexpected = []
    judged_pay_ranks = []
    for step in range(rnd.randint(20, 70)):
        now += rnd.choice([0, 1, 5, 30, 200, 600, 1500])
        at = max(T0, now - rnd.choice([0, 0, 0, 3, 60, 400, 1700, 1900, 3700]))  # stamps out of order
        us = rnd.choice([0, 1, 500000])
        i = rnd.randrange(len(people))
        who = people[i]
        op = rnd.choice(["file", "file", "file", "judge", "judge", "judge", "judge", "finalize", "reclaim", "withdraw", "badfile"])
        try:
            if op == "file":
                h = rnd.choice([1, 2, 3, 4, 5, 6])
                salt = "%032x" % rnd.getrandbits(128)
                out = file(env, who=who, height=h, at=at, us=us, salt=salt)
                assert isinstance(out, dict)
                if out["ok"]:
                    sealed.setdefault(i, []).append((h, salt, at, us, out["seq"]))
            elif op == "badfile":
                out = file(env, who=who, at=at, us=us, value=rnd.choice([0, 1, FEE + 1]))
                assert out["ok"] is False
            elif op == "judge":
                if not sealed.get(i):
                    continue
                h, salt, fat, fus, seq = rnd.choice(sealed[i])
                kind = rnd.choice(["pay", "pay", "nopay", "wrong", "unread"])
                if h not in pays_heights and kind == "pay":
                    kind = "nopay"
                if kind == "pay":
                    out = judge(env, who=who, at=at, us=us, height=h, salt=salt, page=block(h))
                elif kind == "nopay":
                    out = judge(env, who=who, at=at, us=us, height=h, salt=salt, page=block(h, CLEAN1), answer=p1(block=str(h), **NO))
                elif kind == "wrong":
                    out = judge(env, who=who, at=at, us=us, height=h, salt=salt, page=block(h), answer=p1(block="77"))
                else:
                    out = judge(env, who=who, at=at, us=us, height=h, salt=salt, page=None, answer=None)
                if out["outcome"] == "PAYS_P1":
                    judged_pay_ranks.append(((fat * 10**6 + fus, seq), hexes[i]))
            elif op == "finalize":
                env.vm.warp(iso(at, us)); env.vm.sender = who
                env.c.finalize("1")
            elif op == "reclaim":
                env.vm.warp(iso(at, us)); env.vm.sender = env.alice
                env.c.reclaim("1")
            elif op == "withdraw":
                env.vm.warp(iso(at, us)); env.vm.sender = who
                env.c.withdraw()
        except BaseException as e:  # noqa
            env.vm.value = 0
            name = type(e).__name__
            msg = str(e)
            if "money does not add up" in msg or ("UserError" not in name and "UserError" not in msg and "Rollback" not in name):
                unexpected.append((op, name, msg[:200]))
        balanced(env)
        b = get(env)
        assert len(b["filings"]) <= 50 and len(b["log"]) <= 20
        assert int(b["pot_held"]) in (0, POT)
        if b["stored_state"] in ("OPEN", "PROVISIONAL"):
            assert int(b["pot_held"]) == POT
        else:
            assert int(b["pot_held"]) == 0
    assert not unexpected, unexpected
    b = get(env)
    total_credit_and_sent = sum(int(env.c.get_claimable(h)) + env.sent.to(h) for h in set(hexes))
    # refunds are also credits; just check the pot went to at most one place
    if b["stored_state"] == "WON":
        best = min(judged_pay_ranks)
        assert b["lead"]["hunter"] == best[1], (b["lead"], judged_pay_ranks)
    if b["stored_state"] == "PROVISIONAL":
        best = min(judged_pay_ranks)
        assert b["lead"]["hunter"] == best[1]

import copy, json, os, random, pytest
from tests.direct.test_bounties import (env, mod, post, file, judge, get, balanced, mocks, p1, block, iso, seal, address,
    T0, TTL, MARGIN, G, BLOCK1, CLEAN1, NO)
from tests.direct.conftest import to_hex

HOUR = TTL + MARGIN


class Shadow:
    def __init__(self, bid, poster, at, expires, pot):
        self.bid, self.poster, self.expires, self.pot0 = bid, poster, expires, pot
        self.fee = max(G // 1000, pot * 200 // 10000)
        self.t, self.state, self.pot = at, "OPEN", pot
        self.lead, self.window_end, self.seq, self.filings = None, 0, 0, []

    def rank(self, f):
        return (f["us"], f["seq"])

    def advance(self, now, credits):
        self.t = max(self.t, now)
        if self.state == "PROVISIONAL" and self.t >= self.window_end:
            self.state = "WON"
            credits.append((self.lead["hunter"], self.pot))
            self.pot = 0
            return True
        return False

    def retire(self):
        for f in self.filings:
            if f["status"] == "LIVE" and self.t >= f["at"] + HOUR:
                f["status"] = "LAPSED"


def run(env, seed, steps=260, hunters=6, verbose=False, dense=False):
    rnd = random.Random(seed)
    people = [env.alice, env.bob, env.charlie, env.dave] + [address(40 + i) for i in range(hunters - 4)]
    hexes = [to_hex(p) for p in people]
    shadows, credited = {}, {h: 0 for h in hexes}
    recs = []  # (who index, bid, seq, height, salt)
    clock, stats = T0, {"prov": 0, "won": 0, "outranked": 0, "judge_ok": 0, "judge_refused": 0, "file_ok": 0, "file_refused": 0, "two_live": 0, "reclaim": 0, "finalize": 0}
    prev_window = {}

    def credit(pairs):
        for a, v in pairs:
            credited[a] += v

    for step in range(steps):
        if dense:
            clock += rnd.choice((1, 2, 5, 20, 60, 120, 300, 900)) if rnd.random() < 0.9 else rnd.randint(1500, 4000)
            at = clock - rnd.choice((0, 0, 0, 0, 1, 5, 30, 60, 200, 600, 1700, 1799, 1800, 1801, 2500, 3599, 3600, 3700))
        else:
            clock += rnd.randint(1, 500)
            at = clock - rnd.choice((0, 0, 0, 5, 60, 600, 1700, 1799, 1800, 1801, 2500, 3599, 3600, 3700))
        us = rnd.randint(0, 999999)
        wi = rnd.randrange(len(people))
        who, who_hex = people[wi], hexes[wi]
        op = rnd.choice(("post", "file", "file", "file", "file", "judge", "judge", "judge", "judge", "judge", "finalize", "reclaim", "withdraw", "bad_file"))
        n = len(shadows)
        active = [b for b, x in shadows.items() if x.state in ("OPEN", "PROVISIONAL")]
        if op == "post" and (n >= (14 if dense else 3) or (dense and len(active) >= 2)):
            op = "file"
        if op == "post":
            pot = rnd.choice((G // 100, G // 10, G))
            exp = at + rnd.choice((1200, 5000, 20000, 60000))
            out = post(env, who=who, at=at, value=pot, expires_at=exp)
            assert out["ok"] is True, out
            shadows[out["id"]] = Shadow(out["id"], who_hex, at, exp, pot)
        elif not n:
            continue
        elif op in ("file", "bad_file"):
            bid = rnd.choice(active) if dense and active and rnd.random() < 0.9 else str(rnd.randint(1, n))
            sh = shadows[bid]
            height, salt = rnd.randint(0, 3), "%032x" % rnd.getrandbits(128)
            value = sh.fee if op == "file" else rnd.choice((0, 1, sh.fee + 1))
            out = file(env, who=who, at=at, bid=bid, height=height, salt=salt, value=value, us=us)
            cr = []
            sh.advance(at, cr)
            sh.retire()
            problem = (sh.state != "OPEN" or at >= sh.expires or sh.t >= at + TTL or value != sh.fee
                       or any(f["hunter"] == who_hex and f["status"] == "LIVE" and at <= f["at"] + TTL for f in sh.filings)
                       or sum(1 for f in sh.filings if f["status"] == "LIVE") >= 50)
            if problem:
                cr.append((who_hex, value))
                assert out["ok"] is False, (step, out)
                stats["file_refused"] += 1
            else:
                assert out["ok"] is True, (step, out)
                sh.seq += 1
                assert out["seq"] == sh.seq
                if any(f["hunter"] == who_hex and f["status"] == "LIVE" for f in sh.filings):
                    stats["two_live"] += 1
                sh.filings.append({"seq": sh.seq, "hunter": who_hex, "at": at, "us": at * 10**6 + us, "status": "LIVE", "tries": 3})
                recs.append((wi, bid, sh.seq, height, salt))
                stats["file_ok"] += 1
            credit(cr)
        elif op == "judge":
            if not recs:
                continue
            # prefer recent filings, sometimes any
            livish = [r for r in recs if any(g["seq"] == r[2] and g["status"] == "LIVE" for g in shadows[r[1]].filings) and shadows[r[1]].state in ("OPEN", "PROVISIONAL")]
            if dense and livish and rnd.random() < 0.85:
                wi, bid, seq, height, salt = rnd.choice(livish)
                f0 = next(g for g in shadows[bid].filings if g["seq"] == seq)
                if rnd.random() < 0.8:  # a stamp inside the filing's 30 minutes, possibly older than the clock
                    at = rnd.randint(f0["at"], min(clock, f0["at"] + TTL)) if f0["at"] <= clock else at
            else:
                wi, bid, seq, height, salt = rnd.choice(recs[-12:]) if rnd.random() < 0.8 else rnd.choice(recs)
            who, who_hex = people[wi], hexes[wi]
            sh = copy.deepcopy(shadows[bid])
            kind = rnd.choice(("pay", "pay", "pay", "clean", "blank", "blank", "wrong"))
            page = {"pay": block(height), "clean": block(height, CLEAN1), "blank": " ", "wrong": block(height)}[kind]
            answer = {"pay": p1(block=str(height)), "clean": p1(block=str(height), **NO), "blank": None, "wrong": p1(block="77")}[kind]
            cr = []
            sh.advance(at, cr)
            sh.retire()
            f = next((g for g in sh.filings if g["seq"] == seq), None)
            ok = (sh.state in ("OPEN", "PROVISIONAL") and f is not None and f["status"] == "LIVE" and f["at"] <= at <= f["at"] + TTL
                  and not (sh.state == "PROVISIONAL" and sh.rank(f) > sh.rank(sh.lead)))
            try:
                out = judge(env, who=who, at=at, bid=bid, height=height, salt=salt, page=page, answer=answer, us=us)
                raised = None
            except Exception as e:
                raised = str(e)
                assert "internal" not in raised, raised
            assert (raised is None) == ok, (step, seed, raised, ok, at, f, sh.state, sh.t, sh.window_end)
            if ok:
                stats["judge_ok"] += 1
                if kind == "pay":
                    f["status"] = "PAYS"
                    if sh.state == "PROVISIONAL":
                        next(g for g in sh.filings if g["seq"] == sh.lead["seq"])["status"] = "OUTRANKED"
                        stats["outranked"] += 1
                    sh.lead, sh.state = f, "PROVISIONAL"
                elif kind == "clean":
                    f["status"] = "NO_PAY"
                else:
                    f["tries"] -= 1
                    if f["tries"] <= 0:
                        f["status"] = "SPENT"
                if sh.state == "PROVISIONAL":
                    waits = [g["at"] + HOUR for g in sh.filings if sh.rank(g) < sh.rank(sh.lead) and g["status"] == "LIVE"]
                    sh.window_end = max(waits) if waits else sh.t
                    if sh.advance(sh.t, cr):
                        stats["won"] += 1
                    else:
                        stats["prov"] += 1
                assert out["state"] == sh.state, (step, out, sh.state)
                shadows[bid] = sh
                credit(cr)
            else:
                stats["judge_refused"] += 1
        elif op == "finalize":
            bid = str(rnd.randint(1, n))
            sh = copy.deepcopy(shadows[bid])
            cr = []
            paid = sh.advance(at, cr)
            env.vm.warp(iso(at, us)); env.vm.sender = who
            try:
                env.c.finalize(bid); raised = None
            except Exception as e:
                raised = str(e); assert "internal" not in raised
            assert (raised is None) == paid, (step, raised, paid)
            if paid:
                shadows[bid] = sh; credit(cr); stats["finalize"] += 1
        elif op == "reclaim":
            bid = str(rnd.randint(1, n))
            sh = copy.deepcopy(shadows[bid])
            if rnd.random() < 0.7:
                who_hex = sh.poster; who = people[hexes.index(who_hex)]
            cr = []
            sh.advance(at, cr)
            ok = who_hex == sh.poster and sh.state == "OPEN" and sh.t >= sh.expires + HOUR
            env.vm.warp(iso(at, us)); env.vm.sender = who
            try:
                env.c.reclaim(bid); raised = None
            except Exception as e:
                raised = str(e); assert "internal" not in raised
            assert (raised is None) == ok, (step, raised, ok)
            if ok:
                # nobody may still be able to have a filing judged
                assert all(not (f["status"] == "LIVE" and sh.t < f["at"] + HOUR) for f in sh.filings)
                sh.state = "EXPIRED"; cr.append((sh.poster, sh.pot)); sh.pot = 0
                shadows[bid] = sh; credit(cr); stats["reclaim"] += 1
        elif op == "withdraw":
            env.vm.sender = who
            try:
                env.c.withdraw()
            except Exception as e:
                assert "nothing to withdraw" in str(e)
        balanced(env)
        for bid, sh in shadows.items():
            b = get(env, bid=bid)
            got = (b["stored_state"], b["as_of"], b["lead"]["seq"] if b["lead"] else None, int(b["pot_held"]), [(f["seq"], f["status"], f["tries"]) for f in b["filings"]])
            want = (sh.state, sh.t, sh.lead["seq"] if sh.lead else None, sh.pot, [(f["seq"], f["status"], f["tries"]) for f in sh.filings])
            assert got == want, (seed, step, op, got, want)
            if sh.state in ("PROVISIONAL", "WON") :
                assert b["window_end"] == sh.window_end, (seed, step, b["window_end"], sh.window_end)
            if sh.state == "PROVISIONAL":
                if bid in prev_window:
                    assert b["window_end"] <= prev_window[bid], ("window grew", seed, step)
                prev_window[bid] = b["window_end"]
                assert b["window_end"] > b["as_of"]
            if sh.state == "WON":
                # the winner is the earliest-ranked filing that was judged to pay, and no earlier-ranked filing could still be judged
                paying = [f for f in sh.filings if f["status"] in ("PAYS", "OUTRANKED")]
                assert sh.rank(sh.lead) == min(sh.rank(f) for f in paying)
                assert sh.pot == 0
        for h in hexes:
            assert int(env.c.get_claimable(h)) + env.sent.to(h) == credited[h], (seed, step, h)
    return stats


@pytest.mark.parametrize("seed", range(40))
def test_r3_shadow_walk(env, seed, capsys):
    stats = run(env, seed)
    with capsys.disabled():
        print("R3| walk", seed, stats)


@pytest.mark.parametrize("seed", range(100, 160))
def test_r3_shadow_walk_dense(env, seed, capsys):
    stats = run(env, seed, steps=320, hunters=8, dense=True)
    with capsys.disabled():
        print("R3| dense", seed, stats)

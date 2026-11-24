"""Tests from the independent review of the first v2 build (24 Nov 2026, reviews/v2/README.md). The reviewer's probes
asserted what that build did; here each asserts what the fixed contract must do. All coins and pages are fictional."""

import pytest

from tests.direct.test_checker_v2 import (  # noqa: F401  (env and mod are fixtures)
    A_LINE, A_P1, A_P2, A_MINE, A_SPREAD, B_LINE, B_P1, B_P2, B_MINE, BOND_WIN, CONTRACT, G, GRACE,
    SPREAD_ROWS, T0, J, L, ans, balanced, bond, call, challenge, check, credit, env, iso, m1a, m1b, m2, mocks, mod, p1a, p1b, p2a, p2b,
    recheck, times,
)

FL_NOTHING = dict(top_miner_name="", top_miner_blocks="", blocks_inspected="")


# ---------------------------------------------------------------- blocker 1: FAIR_LAUNCH bonds, and what upholds a bond


def test_fair_launch_verdicts_cannot_be_bonded(env):
    """FAIR_LAUNCH is never SUPPORTED, so its bond could never be overturned: refused, credited back."""
    assert check(env, claim_type="FAIR_LAUNCH")["rule"] == "BOTH:P1"
    out = bond(env)
    assert out["ok"] is False and "NO_PREMINE or NO_FOUNDER_REWARD" in out["error"] and credit(env, env.req) == G
    balanced(env)


def test_upheld_needs_the_same_block_and_amount(env):
    """A BOTH:P1 bond on 2,000,000 is not upheld by a re-check that finds another amount: NOT_CONFIRMED."""
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    a3, b3 = A_P1.replace("2,000,000.00000000", "3,000,000.00000000"), B_P1.replace("2,000,000", "3,000,000")
    r = call(env, "recheck", at=rc_open, pa=a3, pb=b3,
             aa=p1a(allocation_amount="3,000,000.00000000", evidence_line=A_LINE.replace("2,000,000", "3,000,000")),
             ab=p1b(allocation_amount="3,000,000", evidence_line=B_LINE.replace("2,000,000", "3,000,000")))
    assert r["state"] == "NOT_CONFIRMED" and r["rule"] == "BOTH:P1"


def test_a_bond_on_p2_is_upheld_by_p2_and_overturned_by_p1(env):
    check(env, "P2")
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    assert recheck(env, rc_open, "P2")["state"] == "UPHELD"
    check(env, "P2", at=T0 + 10)
    bond(env, cid="2", at=T0 + 70)
    challenge(env, env.bob, cid="2", at=T0 + 130)
    _c, rc2, _e, _n = times(T0 + 70)
    assert call(env, "recheck", cid="2", at=rc2, pa=A_P1, pb=B_P1, aa=p1a(), ab=p1b())["state"] == "OVERTURNED"
    balanced(env)


# ---------------------------------------------------------------- blocker 2: challenging yourself no longer pays


def test_requester_challenging_itself_still_loses_half(env):
    """One honest challenger and two more addresses of the requester. Overturned: half the bond is burned, so the
    requester's side loses at least B/2 however many addresses it uses (here 3G - 2*(3G + 0.5G) ... see sums)."""
    check(env)
    bond(env, value=3 * G)
    for w in (env.bob, env.charlie, env.dave):  # bob honest; charlie and dave the requester's own
        challenge(env, w, value=3 * G)
    _c, rc_open, _e, _n = times()
    assert recheck(env, rc_open, pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())["state"] == "OVERTURNED"
    got = {w: int(call(env, "collect", who=w, at=rc_open + 5)["credited"]) for w in (env.bob, env.charlie, env.dave)}
    pool = 3 * G - (3 * G) // 2
    assert got[env.bob] == 3 * G + pool // 3
    requester_side_in, requester_side_out = 3 * G + 2 * 3 * G, got[env.charlie] + got[env.dave]
    assert requester_side_in - requester_side_out >= (3 * G) // 2
    assert env.c.totals()["burned"] == str((3 * G) // 2)
    balanced(env)


def test_fifty_challengers_and_the_remainder(env):
    try:
        from genlayer.py.types import Address
    except ImportError:
        from genlayer.types import Address
    check(env)
    bv = G // 100 + 37
    bond(env, value=bv)
    addrs = [Address(bytes([0xAB] * 19 + [i])) for i in range(50)]
    for a in addrs:
        assert challenge(env, a, value=bv)["ok"] is True
    _c, rc_open, _e, _n = times()
    assert recheck(env, rc_open, pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())["state"] == "OVERTURNED"
    got = [int(call(env, "collect", who=a, at=rc_open + 1)["credited"]) for a in addrs]
    q, r = divmod(bv - bv // 2, 50)
    assert got == [bv + q + (1 if i < r else 0) for i in range(50)] and sum(got) == 50 * bv + bv - bv // 2
    t = balanced(env)
    assert t["locked"] == "0" and t["burned"] == str(bv // 2)


def test_collect_by_requester_on_overturn_credits_zero_and_marks(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    recheck(env, rc_open, pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())
    assert call(env, "collect", who=env.alice, at=rc_open + 1)["credited"] == "0"
    with pytest.raises(Exception, match="already collected"):
        call(env, "collect", who=env.alice, at=rc_open + 2)
    assert call(env, "collect", who=env.bob, at=rc_open + 2)["credited"] == str(G + G // 2)
    balanced(env)


# ---------------------------------------------------------------- blocker 3: nothing stored that validators did not see


def test_undetermined_with_fabricated_page_details_stores_none_of_them(env):
    check(env, aa=p1a(extra_allocation="not_shown"), ab=p1b(extra_allocation="not_shown"))  # honest: U1
    fake = {"verdict": "UNDETERMINED", "rule": "W1_WRONG_PAGE",
            "a": {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "9999999", "amount_text": "9,999,999",
                  "quote": "Founders allocation 9,999,999 EXM to exm1qfabricated"},
            "b": {"cls": "WRONG_PAGE"}}
    mocks(env, A_P1, B_P1, p1a(extra_allocation="not_shown"), p1b(extra_allocation="not_shown"))
    assert env.vm.run_validator(leader_result=fake) is False  # this validator saw U1 with nothing on either page
    r = env.c.get_check("1")["result"]
    assert r == {"verdict": "UNDETERMINED", "rule": "U1_NOT_ENOUGH_EVIDENCE", "a": {"cls": "NOTHING"}, "b": {"cls": "NOTHING"}}


def test_d1_details_are_not_stored(env, mod):
    """A D1 result in full form is cut to classes and rules before it is stored or compared."""
    check(env, pb=B_P2, ab=p2b())
    fake = {"verdict": "UNDETERMINED", "rule": "D1_EXPLORERS_DISAGREE",
            "a": {"cls": "CONTRADICTS", "rule": "P1", "height": 77, "amount": "123", "amount_text": "123", "quote": "made up 123"},
            "b": {"cls": "SUPPORTS", "rule": "P2", "height": 0}}
    assert mod._check_result(fake, "NO_PREMINE") == {"verdict": "UNDETERMINED", "rule": "D1_EXPLORERS_DISAGREE",
                                                     "a": {"cls": "CONTRADICTS", "rule": "P1"}, "b": {"cls": "SUPPORTS", "rule": "P2"}}
    stored = env.c.get_check("1")["result"]
    assert stored["a"] == {"cls": "CONTRADICTS", "rule": "P1"} and "123" not in str(stored)


def test_leader_undetermined_while_validator_definite_is_refused(env):
    check(env)
    lie = {"verdict": "UNDETERMINED", "rule": "U1_NOT_ENOUGH_EVIDENCE", "a": {"cls": "NOTHING"}, "b": {"cls": "NOTHING"}}
    mocks(env, A_P1, B_P1, p1a(), p1b())
    assert env.vm.run_validator(leader_result=lie) is False


def test_leader_unreadable_while_validator_reads_both_is_refused(env):
    check(env)
    lie = {"verdict": "UNREADABLE", "rule": "", "a": {"cls": "UNREADABLE"}, "b": {"cls": "CONTRADICTS", "rule": "P1", "height": 1,
           "amount": "2000000", "amount_text": "2,000,000", "quote": B_LINE}}
    mocks(env, A_P1, B_P1, p1a(), p1b())
    assert env.vm.run_validator(leader_result=lie) is False


def test_d1_with_swapped_page_classes_is_refused(env):
    check(env, pb=B_P2, ab=p2b())
    swapped = {"verdict": "UNDETERMINED", "rule": "D1_EXPLORERS_DISAGREE",
               "a": {"cls": "SUPPORTS", "rule": "P2"}, "b": {"cls": "CONTRADICTS", "rule": "P1"}}
    mocks(env, A_P1, B_P2, p1a(), p2b())
    assert env.vm.run_validator(leader_result=swapped) is False


def test_p2_leader_with_another_block_is_refused(env):
    check(env, "P2")
    lie = {"verdict": "SUPPORTED", "rule": "BOTH:P2", "a": {"cls": "SUPPORTS", "rule": "P2", "height": 0}, "b": {"cls": "SUPPORTS", "rule": "P2", "height": 0}}
    mocks(env, A_P2, B_P2, p2a(), p2b())
    assert env.vm.run_validator(leader_result=lie) is False


# ---------------------------------------------------------------- M rules


def test_m2_tie_in_row_order_still_agrees(env):
    page = A_SPREAD.replace("Beta Pool 45", "Beta Pool 50").replace("Other 30", "Other 25")
    rows = [dict(r) for r in SPREAD_ROWS]
    rows[1]["blocks"], rows[4]["blocks"] = "50", "25"
    pb = page.replace("Examplescan", "Blockfield")
    assert check(env, "M2", pa=page, pb=pb, aa=m2(rows=rows), ab=m2(rows=rows))["rule"] == "BOTH:M2"
    mocks(env, page, pb, m2(rows=[rows[1], rows[0]] + rows[2:]), m2(rows=rows))
    assert env.vm.run_validator() is True


def test_m2_one_row_left_out_by_a_validator_still_agrees_when_still_spread(env):
    assert check(env, "M2")["rule"] == "BOTH:M2"
    mocks(env, A_SPREAD, A_SPREAD.replace("Examplescan", "Blockfield"), m2(rows=[r for r in SPREAD_ROWS if r["name"] != "Delta Pool"]), m2())
    assert env.vm.run_validator() is True  # the rest (35 + 30 left out) is 30 + 35 = 65... at most 33%: still M2


def test_m1_needs_the_same_top_miner_on_both_explorers(env):
    other = B_MINE.replace("Deepvein Pool", "Rockface Pool")
    out = check(env, "M1", pb=other, ab=m1b(top_miner_name="Rockface Pool"))
    assert out["verdict"] == "UNDETERMINED" and out["rule"] == "D2_NOT_SHOWN_BY_BOTH"


# ---------------------------------------------------------------- re-check outcomes


def test_an_error_page_during_the_recheck_decides_nothing(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, rc_end, _n = times()
    r = recheck(env, rc_open, pb="502 Bad Gateway\nnginx\n")
    assert r["decided"] is False and env.c.get_check("1")["bond"]["state"] == "BONDED"
    assert recheck(env, rc_end)["state"] == "UPHELD"  # the explorer is back: decided


def test_a_page_moved_for_the_recheck_decides_nothing_and_ends_not_confirmed(env):
    """Whoever runs one explorer can keep the re-check from deciding: the bond then ends NOT_CONFIRMED (stated)."""
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, nc = times()
    r = recheck(env, rc_open, pa=A_P2.replace("Examplecoin", "Othercoin"), pb=B_P2, aa=p2a(), ab=p2b())
    assert r["decided"] is False
    assert call(env, "settle", at=nc)["state"] == "NOT_CONFIRMED"
    assert call(env, "collect", who=env.alice, at=nc + 1)["credited"] == str(G)


def test_json_answer_out_of_form_is_unreadable(env):
    with pytest.raises(Exception, match="could not be read"):
        check(env, ab=ans(answer="I cannot help with that"))
    with pytest.raises(Exception, match="could not be read"):
        check(env, ab=ans(block_number=1))


def test_out_of_form_answer_in_a_recheck_decides_nothing(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    assert recheck(env, rc_open, ab=ans(block_number=1))["decided"] is False


# ---------------------------------------------------------------- inputs


def test_generic_coin_names_are_refused(mod):
    for n in ("Block 1", "Height 1", "Block Explorer", "Miner reward", "Coinbase", "Mainnet", "Explorer 2", "Total blocks", "Block-1"):
        assert "too generic" in mod._name_problem(n), n
    for n in ("Examplecoin", "Bitcoin", "Litecoin", "Splitcoin", "Block Rewards Coin X"):
        assert mod._name_problem(n) == "", n


def test_block_number_must_stand_on_a_block_or_height_line(mod):
    page = """Examplescan: Examplecoin explorer (fictional)
Block 5
Height: 5
Confirmations: 1
Miner reward 50.00000000 EXM to exm1qminer0001
"""
    assert mod._p2(J(p2a()), L(mod, page)) is None
    assert mod._p1(J(p1a()), L(mod, page + "Founders allocation 2,000,000.00000000 EXM to exm1qfounders01\n")) is None


@pytest.mark.parametrize("url,ok", [
    ("https://examplescan.example:8443/x", True),
    ("https://EXAMPLESCAN.example/x", False),
    ("https://examplescan.example./x", False),
    ("https://xn--examplescn-9db.example/x", True),
    ("https://user@examplescan.example/x", False),
    ("https://examplescan.example:0/x", False),
    ("https://examplescan.example:65536/x", False),
    ("https://examplescan.example:08443/x", False),
    ("https://examplescan.example%2f@evil.example/x", False),
    ("https://127.0.0.1.nip.io/x", False),
    ("https://10.0.0.1/x", False),
    ("https://0x7f000001/x", False),
    ("https://examplescan.example\\@evil.example/x", False),
    ("https://examplescan.example?x=1", True),
])
def test_url_filter_edges(mod, env, url, ok):
    assert (mod._url_problem(url, "u") == "") is ok, mod._url_problem(url, "u")


@pytest.mark.parametrize("a,b,same", [
    ("scan.example.co.uk", "other.example.co.uk", True),
    ("example.co.uk", "example2.co.uk", False),
    ("a.github.io", "b.github.io", True),
    ("examplescan.example", "examplescan.example", True),
    ("a.example.com.de", "b.example.com.de", True),
])
def test_domain_rule_edges(mod, env, a, b, same):
    assert (mod._domain(a) == mod._domain(b)) is same


@pytest.mark.parametrize("args,msg", [
    ((3600, 86400, 3600, 86401), "rc_win"),
    ((3600, 86400, 86401, 3600), "grace"),
    ((86401, 86400, 3600, 3600), "bond_win"),
    ((3600, 30 * 86400 + 1, 3600, 3600), "ch_win"),
    ((3600, 86400, 599, 3600), "grace"),
    ((3600, 599, 3600, 3600), "ch_win"),
    ((3600, 86400, 3600, 599), "rc_win"),
    ((True, 86400, 3600, 3600), "bond_win"),
])
def test_constructor_caps_and_floors(direct_vm, direct_deploy, args, msg):
    direct_vm.warp(iso(T0))
    with pytest.raises(Exception, match=msg):
        direct_deploy(CONTRACT, *args)


def test_constructor_upper_caps_accepted(direct_vm, direct_deploy):
    direct_vm.warp(iso(T0))
    c = direct_deploy(CONTRACT, 86400, 30 * 86400, 86400, 86400)
    assert c.get_rules()["windows_seconds"]["ch_win"] == 30 * 86400


# ---------------------------------------------------------------- time and money edges


def test_challenge_sent_at_close_is_accepted(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    close, rc_open, _e, _n = times()
    with pytest.raises(Exception, match="too early"):
        call(env, "settle", at=rc_open - 1)
    assert challenge(env, env.charlie, at=close)["ok"] is True


def test_a_bond_sent_after_its_window_is_refused(env):
    check(env)
    out = bond(env, at=T0 + BOND_WIN + 1)
    assert out["ok"] is False and "passed" in out["error"]
    assert bond(env, at=T0 + BOND_WIN)["ok"] is True  # the last second counts


def test_withdraw_partial_and_over_credit(env):
    check(env, "M1")
    bond(env)  # refused, G credited
    env.vm.sender = env.alice
    with pytest.raises(Exception, match="amount must be 1 to"):
        env.c.withdraw(G + 1)
    with pytest.raises(Exception, match="whole number"):
        env.c.withdraw(True)
    with pytest.raises(Exception, match="amount must be 1 to"):
        env.c.withdraw(-1)
    assert env.c.withdraw(1)["left"] == str(G - 1)
    assert credit(env, env.req) == G - 1
    assert env.sent.items[-1][1] == 1
    balanced(env)


def test_each_challenger_is_indexed_by_address(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    challenge(env, env.charlie)
    assert env.c.get_challengers("1") == [env.ch1.lower(), env.ch2.lower()]
    assert "1" in env.c.get_by_address(env.ch1) and "1" in env.c.get_by_address(env.ch2)


def test_page_cut_and_anchor_lines(mod, env):
    assert mod.ANCHOR_LINES == 12 and mod.PAGE_CHARS == 6000
    top = "Examplescan menu\n" + "\n".join(f"Menu item {i}" for i in range(10)) + "\nExamplecoin block 1\n"
    assert check(env, pa=top + A_P1, pb=B_P1)["rule"] == "BOTH:P1"  # the name on line 12 counts
    late = "Examplescan menu\n" + "\n".join(f"Menu item {i}" for i in range(11)) + "\nExamplecoin block 1\n" + A_P1.split("\n", 1)[1]
    assert check(env, pa=late, pb=B_P1, at=T0 + 1)["rule"] == "W1_WRONG_PAGE"  # line 13 does not
    long = "x " * 3100 + "\n" + A_P1
    assert len(mod._clean_page(long)) <= 6000


# ---------------------------------------------------------------- a random walk with a model of every account


def test_random_walk_with_a_model_of_every_account(env):
    """Every outcome, refused bonds and challenges, many challengers, an unreadable re-check, partial withdrawals; after
    every step each account's credit equals a separate model's figure and locked + credited + burned + sent = paid in."""
    import random

    from tests.direct.conftest import to_hex
    from tests.direct.test_checker_v2 import pay, withdraw  # noqa: F401

    rnd = random.Random(2611)
    people = [env.alice, env.bob, env.charlie, env.dave]
    model = {to_hex(p).lower(): 0 for p in people}
    burned = 0
    seen = set()
    pages = {"P1": dict(pa=A_P1, pb=B_P1, aa=p1a(), ab=p1b()), "P2": dict(pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())}

    def cr(p, v):
        model[to_hex(p).lower()] += v

    def same():
        for p in people:
            assert credit(env, to_hex(p)) == model[to_hex(p).lower()]
        t = balanced(env)
        assert int(t["burned"]) == burned

    for step in range(30):
        at = T0 + step * 20000
        kind = rnd.choice(["P1", "P2", "P1", "P2", "M1"])
        cid = str(step + 1)
        check(env, kind, at=at)
        v = rnd.choice([G // 100, 7, 10**17 + 3, 3 * G + 1])
        out = bond(env, cid=cid, value=v, at=at + 10)
        if not out["ok"]:
            cr(env.alice, v)
            challenge(env, env.bob, cid=cid, value=v, at=at + 20)  # no open bond: refused, credited
            cr(env.bob, v)
            same()
            continue
        chal = []
        for w in rnd.sample(people[1:], rnd.randint(0, 3)):
            amt = rnd.choice([v, v, v + 1])
            r = challenge(env, w, cid=cid, value=amt, at=at + 20)
            if r["ok"]:
                chal.append(w)
            else:
                cr(w, amt)
        if chal and rnd.random() < 0.3:  # the requester itself, and a second try by a challenger: refused
            challenge(env, env.alice, cid=cid, value=v, at=at + 25)
            cr(env.alice, v)
        close, rc_open, rc_end, nc = times(at + 10)
        if rnd.random() < 0.2:
            challenge(env, env.dave if env.dave not in chal else env.charlie, cid=cid, value=v, at=close + 1)  # late: refused
            cr(env.dave if env.dave not in chal else env.charlie, v)
        n = len(chal)
        if n == 0:
            seen.add("released")
            assert call(env, "settle", cid=cid, at=rc_open)["state"] == "RELEASED"
            cr(env.alice, v)
        else:
            road = rnd.choice(["upheld", "overturned", "disagree", "unreadable"])
            other = "P2" if kind == "P1" else "P1"
            seen.add(road)
            if road == "upheld":
                assert call(env, "recheck", cid=cid, at=rc_open, **pages[kind])["state"] == "UPHELD"
                cr(env.alice, v + n * v)
            elif road == "overturned":
                assert call(env, "recheck", cid=cid, at=rc_open, **pages[other])["state"] == "OVERTURNED"
                burn = v // 2
                burned += burn
                q, r = divmod(v - burn, n)
                for i, w in enumerate(chal):
                    cr(w, v + q + (1 if i < r else 0))
            elif road == "disagree":
                assert call(env, "recheck", cid=cid, at=rc_open, pa=A_P1, pb=B_P2, aa=p1a(), ab=p2b())["state"] == "NOT_CONFIRMED"
                cr(env.alice, v)
                for w in chal:
                    cr(w, v)
            else:
                assert call(env, "recheck", cid=cid, at=rc_end, pa=A_P1, pb="  ", aa=p1a(), ab=None)["decided"] is False
                assert call(env, "settle", cid=cid, at=nc)["state"] == "NOT_CONFIRMED"
                cr(env.alice, v)
                for w in chal:
                    cr(w, v)
        for w in [env.alice] + chal:
            call(env, "collect", cid=cid, who=w, at=nc + 1)
        with pytest.raises(Exception):
            call(env, "collect", cid=cid, who=env.alice, at=nc + 2)
        for w in people:  # a partial withdrawal now and then
            have = model[to_hex(w).lower()]
            if have > 1 and rnd.random() < 0.3:
                part = rnd.randint(1, have)
                env.vm.sender, env.vm.value = w, 0
                env.c.withdraw(part)
                model[to_hex(w).lower()] -= part
        same()
    for w in people:
        if model[to_hex(w).lower()] > 0:
            withdraw(env, w)
            model[to_hex(w).lower()] = 0
    same()
    t = env.c.totals()
    assert t["locked"] == "0" and t["credited"] == "0"
    assert seen == {"released", "upheld", "overturned", "disagree", "unreadable"}, seen


# ---------------------------------------------------------------- added after the mutation check of the fixed build


def test_p2_needs_block_0_or_1(mod):
    page = "Examplescan: Examplecoin explorer (fictional)\nBlock 2\nHeight: 2\nOutputs\nMiner reward 50.00000000 EXM to exm1qminer0001\n"
    assert mod._p2(J(p2a(block_number="2")), L(mod, page)) is None
    assert mod._p2(J(p2a()), L(mod, A_P2))["height"] == 1


def test_undetermined_short_form_is_checked(mod):
    good = {"verdict": "UNDETERMINED", "rule": "U1_NOT_ENOUGH_EVIDENCE", "a": {"cls": "NOTHING"}, "b": {"cls": "NOTHING"}}
    assert mod._check_result(good, "NO_PREMINE")["rule"] == "U1_NOT_ENOUGH_EVIDENCE"
    with pytest.raises(Exception):
        mod._check_result(dict(good, a={"cls": "UNREADABLE"}), "NO_PREMINE")  # an unreadable page is never UNDETERMINED
    with pytest.raises(Exception):  # an M1 page on a premine claim
        mod._check_result(dict(good, rule="D2_NOT_SHOWN_BY_BOTH", a={"cls": "CONTRADICTS", "rule": "M1"}), "NO_PREMINE")
    with pytest.raises(Exception):
        mod._check_result(dict(good, rule="W1_WRONG_PAGE"), "NO_PREMINE")


def test_check_page_refuses_a_quote_without_its_amount(mod):
    page = {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "2000000", "amount_text": "2,000,000", "quote": B_LINE}
    assert mod._check_page(page, "NO_PREMINE")["amount"] == "2000000"
    with pytest.raises(Exception):
        mod._check_page(dict(page, quote="exm1qfounders01 receives a founders allocation"), "NO_PREMINE")


def test_fair_launch_undetermined_needs_the_same_rule_per_page(env):
    """FAIR_LAUNCH: page A contradicts by P1 for the leader, by M1 for this validator; B shows nothing for both."""
    check(env, claim_type="FAIR_LAUNCH", aa=p1a(**FL_NOTHING), ab=p1b(extra_allocation="not_shown", **FL_NOTHING))
    assert env.c.get_check("1")["result"]["a"] == {"cls": "CONTRADICTS", "rule": "P1"}
    noblock = dict(block_number="", extra_allocation="not_shown", allocation_amount="", evidence_line="")
    mocks(env, A_MINE, B_P1, m1a(**noblock), p1b(extra_allocation="not_shown", **FL_NOTHING))
    assert env.vm.run_validator() is False


def test_rows_that_are_not_a_list_make_the_page_unreadable(env):
    with pytest.raises(Exception, match="could not be read"):
        check(env, "M1", aa=m1a(rows="none"))


def test_upheld_needs_the_same_block(env):
    check(env)
    bond(env)
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    a2 = A_P1.replace("Block 1", "Block 2").replace("Height: 1", "Height: 2")
    b2 = B_P1.replace("Block #1", "Block #2").replace("Height 1", "Height 2")
    r = call(env, "recheck", at=rc_open, pa=a2, pb=b2, aa=p1a(block_number="2"), ab=p1b(block_number="2"))
    assert r["rule"] == "BOTH:P1" and r["state"] == "NOT_CONFIRMED"

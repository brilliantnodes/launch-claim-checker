"""Tests from review 3 of the fixed build: what can be bonded, what an overturn needs, what a re-check decides,
and the two mutants first dropped as equivalent. Each asserts the behaviour after the fix."""
import pytest

from tests.direct.test_checker_v2 import (  # noqa: F401
    A_LINE, A_P1, A_P2, B_LINE, B_P1, B_P2, G, J, L, balanced, bond, call, challenge, check, env, m2, mocks, mod,
    p1a, p1b, p2a, p2b, times,
)

A_P1_50 = A_P1.replace("Block 1", "Block 50").replace("Height: 1", "Height: 50")
B_P1_50 = B_P1.replace("Block #1", "Block #50").replace("Height 1", "Height 50")
A_P1_0 = A_P1.replace("Block 1", "Block 0").replace("Height: 1", "Height: 0")
B_P1_0 = B_P1.replace("Block #1", "Block #0").replace("Height 1", "Height 0")
A_P2_0 = A_P2.replace("Block 1", "Block 0").replace("Height: 1", "Height: 0")
B_P2_0 = B_P2.replace("Block #1", "Block #0").replace("Height 1", "Height 0")
ERROR_A = "Examplescan: Examplecoin explorer (fictional)\nSomething went wrong\nToo many requests, please try again later\n"
NOTHING_A = p1a(block_number="", extra_allocation="not_shown", allocation_amount="", evidence_line="")


def _bonded(env, **kw):
    check(env, **kw)
    assert bond(env)["ok"] is True
    challenge(env, env.bob)
    return times()


# ---- what can be bonded


def test_p1_verdict_on_block_50_cannot_be_bonded(env):
    """P2, the opposite reading, exists only for block 0 or 1, so a BOTH:P1 verdict on block 50 could never be
    overturned. Its bond is refused and credited back."""
    out = check(env, pa=A_P1_50, pb=B_P1_50, aa=p1a(block_number="50"), ab=p1b(block_number="50"))
    assert out["rule"] == "BOTH:P1" and env.c.get_check("1")["result"]["a"]["height"] == 50
    r = bond(env)
    assert r["ok"] is False and "block 0 or 1" in r["error"] and r["refunded"] == str(G)
    assert env.c.get_check("1")["bond"]["state"] == "NONE"
    balanced(env)


def test_p1_verdict_on_block_0_can_be_bonded_and_overturned_by_a_clean_block_0(env):
    _c, rc_open, _e, _n = _bonded(env, pa=A_P1_0, pb=B_P1_0, aa=p1a(block_number="0"), ab=p1b(block_number="0"))
    r = call(env, "recheck", at=rc_open, pa=A_P2_0, pb=B_P2_0, aa=p2a(block_number="0"), ab=p2b(block_number="0"))
    assert r["decided"] is True and r["state"] == "OVERTURNED"
    balanced(env)


# ---- an overturn needs the same block


def test_overturn_needs_the_same_block(env):
    """A BOTH:P1 bond on block 1, re-read as a clean block 0 on both explorers: a clean block 0 says nothing about
    block 1, so the bond is not overturned (the reading is definite, so it decides NOT_CONFIRMED)."""
    _c, rc_open, _e, _n = _bonded(env)
    r = call(env, "recheck", at=rc_open, pa=A_P2_0, pb=B_P2_0, aa=p2a(block_number="0"), ab=p2b(block_number="0"))
    assert r["decided"] is True and r["state"] == "NOT_CONFIRMED" and r["rule"] == "BOTH:P2"
    balanced(env)


def test_overturn_needs_the_same_block_on_both_pages(env, mod):
    old = {"verdict": "CONTRADICTED", "rule": "BOTH:P1", "a": {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": 2},
           "b": {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": 2}}
    new = {"verdict": "SUPPORTED", "rule": "BOTH:P2", "a": {"cls": "SUPPORTS", "rule": "P2", "height": 1, "amount": 1},
           "b": {"cls": "SUPPORTS", "rule": "P2", "height": 1, "amount": 1}}
    assert mod._outcome(old, new) == "OVERTURNED"
    assert mod._outcome(old, dict(new, b=dict(new["b"], height=0))) == "NOT_CONFIRMED"
    assert mod._outcome(old, dict(new, a=dict(new["a"], height=0))) == "NOT_CONFIRMED"


# ---- what a re-check decides


def test_an_error_page_with_the_explorers_header_decides_nothing(env):
    """Most explorers keep their header (with the coin's name) on error and rate-limit pages. Such a page passes the
    anchor and reads as nothing; in a re-check that decides nothing, and a later reading of the real pages decides."""
    _c, rc_open, rc_end, _n = _bonded(env)
    r = call(env, "recheck", at=rc_open, who=env.bob, pa=ERROR_A, pb=B_P1, aa=NOTHING_A, ab=p1b())
    assert r["decided"] is False and "D2_NOT_SHOWN_BY_BOTH" in r["why"]
    assert env.c.get_check("1")["bond"]["state"] == "BONDED"
    r = call(env, "recheck", at=rc_end, who=env.alice, pa=A_P1, pb=B_P1, aa=p1a(), ab=p1b())
    assert r["decided"] is True and r["state"] == "UPHELD"
    balanced(env)


def test_nothing_on_both_pages_decides_nothing_and_settle_ends_not_confirmed(env):
    _c, rc_open, rc_end, nc = _bonded(env)
    blank_b = "Blockfield: Examplecoin (EXM) (fictional)\nBlock #1\nHeight 1\nOutputs hidden for maintenance\n"
    nothing_b = p1b(extra_allocation="not_shown", allocation_amount="", evidence_line="")
    r = call(env, "recheck", at=rc_open, pa=ERROR_A, pb=blank_b, aa=NOTHING_A, ab=nothing_b)
    assert r["decided"] is False and "U1_NOT_ENOUGH_EVIDENCE" in r["why"]
    r = call(env, "recheck", at=rc_end, pa=A_P1, pb=blank_b, aa=p1a(), ab=nothing_b)
    assert r["decided"] is False and "D2_NOT_SHOWN_BY_BOTH" in r["why"]
    with pytest.raises(Exception, match="too early"):
        call(env, "settle", at=nc - 1)
    assert call(env, "settle", at=nc)["state"] == "NOT_CONFIRMED"
    for who in (env.alice, env.bob):
        assert call(env, "collect", who=who, at=nc + 1)["credited"] == str(G)
    balanced(env)


def test_explorers_showing_opposite_facts_decide_not_confirmed(env):
    _c, rc_open, rc_end, _n = _bonded(env)
    r = call(env, "recheck", at=rc_open, pa=A_P1, pb=B_P2, aa=p1a(), ab=p2b())
    assert r["decided"] is True and r["state"] == "NOT_CONFIRMED" and r["rule"] == "D1_EXPLORERS_DISAGREE"
    with pytest.raises(Exception, match="nothing to re-check"):
        call(env, "recheck", at=rc_end, pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())
    balanced(env)


# ---- the two mutants first dropped as equivalent


def test_undetermined_page_classes_swapped_between_nothing_and_wrong_page_are_refused(env):
    """Leader: A NOTHING, B WRONG_PAGE (W1). This validator: A WRONG_PAGE, B NOTHING (also W1; neither page has a rule).
    Only the class comparison tells them apart: the validator refuses."""
    other_b = B_P1.replace("Examplecoin", "Othercoin")
    out = check(env, pb=other_b, aa=p1a(extra_allocation="not_shown"))
    assert out["rule"] == "W1_WRONG_PAGE"
    assert env.c.get_check("1")["result"] == {"verdict": "UNDETERMINED", "rule": "W1_WRONG_PAGE", "a": {"cls": "NOTHING"}, "b": {"cls": "WRONG_PAGE"}}
    mocks(env, A_P1.replace("Examplecoin", "Othercoin"), B_P1, p1a(), p1b(extra_allocation="not_shown"))
    assert env.vm.run_validator() is False


MIXED = """Examplescan: Examplecoin mining (fictional)
Last 200 blocks
Deepvein Pool 168 blocks, 60 days
Quarry Pool 14 blocks, 60 days
Other 18 blocks, 60 days
"""


def test_one_answer_that_meets_m1_and_m2_is_read_as_m1(env, mod):
    """The top-miner fields meet M1 while the rows (counts copied from another number on each line) meet M2. The
    order is part of the rule: M1, the stronger finding, is tried first."""
    rows = [{"name": "Deepvein Pool", "blocks": "60"}, {"name": "Quarry Pool", "blocks": "60"}, {"name": "Other", "blocks": "60"}]
    a = J(m2(top_miner_name="Deepvein Pool", top_miner_blocks="168", blocks_inspected="200", rows=rows))
    lines = L(mod, MIXED)
    assert mod._m1(a, lines) is not None and mod._m2(a, lines) is not None
    assert mod._evidence("DECENTRALIZED_MINING", a, lines)["rule"] == "M1"


# ---- smaller fixes


@pytest.mark.parametrize("name", ["Difficulty", "Nonce", "Version", "Merkle Root", "Previous", "Next Block", "Timestamp",
                                  "Weight", "Block Details", "Prev Block"])
def test_block_page_field_names_are_refused_as_coin_names(mod, name):
    assert mod._name_problem(name)


def test_the_mining_prompt_asks_for_counts_as_digits_only(mod):
    p = mod._prompt("DECENTRALIZED_MINING", "Examplecoin", "x")
    for field in ('"top_miner_blocks"', '"blocks_inspected"', '"rows"'):
        line = next(x for x in p.splitlines() if x.startswith("- " + field))
        assert "digits only" in line, line
    assert 'as a string; "". Never' not in p

"""Tests from review 4 of the final build: a BOTH:P1 verdict can be bonded only when both pages also show the block's
ordinary reward (not zero) on a line of its own, because P2, the opposite reading, needs that reward; and the edge of
the block limit (block 2). Each asserts the behaviour after the fix."""
import pytest

from tests.direct.test_checker_v2 import (  # noqa: F401
    A_LINE, A_P1, A_P2, A_REWARD, B_LINE, B_P1, B_P2, B_REWARD, G, J, L, balanced, bond, call, challenge, check, env,
    mocks, mod, p1a, p1b, p2a, p2b, times,
)

A_P1_2 = A_P1.replace("Block 1", "Block 2").replace("Height: 1", "Height: 2")
B_P1_2 = B_P1.replace("Block #1", "Block #2").replace("Height 1", "Height 2")
A_P1_0 = A_P1.replace("Block 1", "Block 0").replace("Height: 1", "Height: 0")
B_P1_0 = B_P1.replace("Block #1", "Block #0").replace("Height 1", "Height 0")
A_ZERO = "Miner reward 0 EXM to exm1qminer0001"
B_ZERO = "exm1qminer0001 receives 0 EXM (block reward)"
A_P1_0_ZERO = A_P1_0.replace(A_REWARD, A_ZERO)
B_P1_0_ZERO = B_P1_0.replace(B_REWARD, B_ZERO)
A_P1_NO_REWARD = A_P1.replace(A_REWARD + "\n", "")
B_P1_NO_REWARD = B_P1.replace(B_REWARD + "\n", "")


def _refused(env):
    r = bond(env)
    assert r["ok"] is False and r["refunded"] == str(G)
    assert env.c.get_check("1")["bond"]["state"] == "NONE"
    balanced(env)
    return r["error"]


# ---- the edge of the block limit


def test_p1_verdict_on_block_2_cannot_be_bonded(env):
    out = check(env, pa=A_P1_2, pb=B_P1_2, aa=p1a(block_number="2"), ab=p1b(block_number="2"))
    assert out["rule"] == "BOTH:P1" and env.c.get_check("1")["result"]["a"]["height"] == 2
    assert "block 0 or 1" in _refused(env)


# ---- a P1 bond needs the ordinary reward on both pages


def test_p1_verdict_on_a_zero_reward_block_cannot_be_bonded(env, mod):
    """Block 0 prints a reward of 0. A correction of these pages could only read as nothing (P2 refuses a reward of
    0), so the bond could never be overturned: it is refused."""
    aa = p1a(block_number="0", reward_amount="0", reward_line=A_ZERO)
    ab = p1b(block_number="0", reward_amount="0", reward_line=B_ZERO)
    out = check(env, pa=A_P1_0_ZERO, pb=B_P1_0_ZERO, aa=aa, ab=ab)
    assert out["rule"] == "BOTH:P1"
    assert "reward_text" not in env.c.get_check("1")["result"]["a"]
    assert "ordinary reward" in _refused(env)
    # and the reason: the corrected block reads as nothing
    lines = L(mod, A_P1_0_ZERO.replace(A_LINE + "\n", ""))
    assert mod._p2(J(p2a(block_number="0", reward_amount="0", reward_line=A_ZERO)), lines) is None


def test_p1_verdict_on_a_block_with_no_reward_shown_cannot_be_bonded(env):
    aa = p1a(reward_amount="", reward_line="")
    ab = p1b(reward_amount="", reward_line="")
    out = check(env, pa=A_P1_NO_REWARD, pb=B_P1_NO_REWARD, aa=aa, ab=ab)
    assert out["rule"] == "BOTH:P1"
    assert "ordinary reward" in _refused(env)


def test_p1_verdict_with_the_reward_on_one_page_only_cannot_be_bonded(env):
    out = check(env, pb=B_P1_NO_REWARD, ab=p1b(reward_amount="", reward_line=""))
    assert out["rule"] == "BOTH:P1"
    res = env.c.get_check("1")["result"]
    assert "reward_text" in res["a"] and "reward_text" not in res["b"]
    assert "ordinary reward" in _refused(env)


def test_a_reward_line_that_is_not_on_the_page_is_not_recorded(env):
    out = check(env, aa=p1a(reward_line="Miner reward 50.00000000 EXM to exm1qsomeoneelse"))
    assert out["rule"] == "BOTH:P1"
    assert "reward_text" not in env.c.get_check("1")["result"]["a"]
    assert "ordinary reward" in _refused(env)


def test_the_allocations_own_line_is_not_the_ordinary_reward(env, mod):
    a = J(p1a(reward_amount="2,000,000.00000000", reward_line=A_LINE))
    found = mod._p1(a, L(mod, A_P1))
    assert found is not None and found["rule"] == "P1" and "reward_text" not in found


def test_a_line_with_both_the_reward_and_the_allocation_shows_the_reward(env, mod):
    """Some pages print both on one line ("Ordinary block reward: 50 EXM. Extra output in this block: 2,000,000 EXM
    ..."): that line shows the ordinary reward, as long as the amount copied is not the allocation's."""
    line = "Ordinary block reward: 50 EXM. Extra output in this block: 2,000,000 EXM to the founders allocation address."
    page = A_P1 + line + "\n"
    found = mod._p1(J(p1a(evidence_line=line, allocation_amount="2,000,000", reward_amount="50", reward_line=line)), L(mod, page))
    assert found["reward_text"] == "50" and found["reward_quote"] == line
    same = mod._p1(J(p1a(evidence_line=line, allocation_amount="2,000,000", reward_amount="2,000,000", reward_line=line)), L(mod, page))
    assert "reward_text" not in same


def test_p1_verdict_with_the_reward_on_both_pages_is_bonded_and_overturned(env):
    """The ordinary case: both pages show the founders' line and the miner's reward. The bond is accepted, and once
    the founders' line is gone from both explorers the re-check reads P2 about the same block: OVERTURNED."""
    out = check(env)
    assert out["rule"] == "BOTH:P1"
    res = env.c.get_check("1")["result"]
    assert res["a"]["reward_text"] == "50.00000000" and res["a"]["reward_quote"] == A_REWARD
    assert res["b"]["reward_text"] == "50" and res["b"]["reward_quote"] == B_REWARD
    assert bond(env)["ok"] is True
    challenge(env, env.bob)
    _c, rc_open, _e, _n = times()
    r = call(env, "recheck", at=rc_open, pa=A_P2, pb=B_P2, aa=p2a(), ab=p2b())
    assert r["decided"] is True and r["state"] == "OVERTURNED"
    balanced(env)


def test_p2_verdicts_need_no_extra_reward_check(env):
    """A BOTH:P2 verdict already rests on the reward line; it is bondable as before."""
    out = check(env, "P2")
    assert out["rule"] == "BOTH:P2"
    assert bond(env)["ok"] is True
    balanced(env)


# ---- what validators agree on


def test_the_leaders_reward_line_must_stand_on_each_validators_copy(env, mod):
    leader = mod._p1(J(p1a()), L(mod, A_P1))
    assert leader["reward_quote"] == A_REWARD
    assert mod._same_page(leader, leader, L(mod, A_P1)) is True
    # a validator whose copy does not have the leader's reward line refuses
    assert mod._same_page(leader, leader, L(mod, A_P1_NO_REWARD)) is False
    # a leader that gives no reward line is accepted (that only makes the verdict not bondable)
    bare = {k: v for k, v in leader.items() if not k.startswith("reward_")}
    assert mod._same_page(bare, leader, L(mod, A_P1)) is True


def test_a_validator_whose_copy_lacks_the_reward_line_refuses_the_leader(env):
    check(env)
    mocks(env, A_P1_NO_REWARD, B_P1, p1a(reward_amount="", reward_line=""), p1b())
    assert env.vm.run_validator() is False


@pytest.mark.parametrize("bad", [
    {"reward_text": "0", "reward_quote": "Miner reward 0 EXM to exm1qminer0001"},
    {"reward_text": "50", "reward_quote": "Miner reward to exm1qminer0001 ok"},
    {"reward_text": "50"},
    {"reward_quote": "Miner reward 50 EXM to exm1qminer0001"},
    {"reward_text": 50, "reward_quote": "Miner reward 50 EXM to exm1qminer0001"},
    {"reward_text": "2,000,000.00000000", "reward_quote": A_LINE},
])
def test_a_passed_on_reward_that_is_not_well_formed_is_refused(env, mod, bad):
    page = {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "2000000", "amount_text": "2,000,000.00000000",
            "quote": A_LINE, **bad}
    with pytest.raises(ValueError):
        mod._check_page(page, "NO_FOUNDER_REWARD")


def test_a_passed_on_reward_that_is_well_formed_is_kept(env, mod):
    page = {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "2000000", "amount_text": "2,000,000.00000000",
            "quote": A_LINE, "reward_text": "50.00000000", "reward_quote": A_REWARD}
    assert mod._check_page(page, "NO_FOUNDER_REWARD") == page


# ---- the form


def test_the_reward_is_asked_whatever_the_page_shows(env, mod):
    prompt = mod._prompt("NO_FOUNDER_REWARD", "Examplecoin", "x")
    assert '"reward_amount": the ordinary block reward' in prompt and 'if "no", the ordinary' not in prompt
    assert "reward_amount" not in mod._prompt("FAIR_LAUNCH", "Examplecoin", "x")


# ---- the reward as models copy it (seen on Studio, 26 Nov 2026: the bond on Examplecoin was refused)

REAL_A = """Examplescan: Examplecoin (EXM) block 1
Height: 1 (the first block after genesis). Transactions: 1.
Coinbase transaction outputs
Output Amount Recipient
0 50.00000000 EXM Miner reward to exm1qminer000000000000000000000001
1 2,000,000.00000000 EXM Founders allocation to exm1qfounders0000000000000000000001
Ordinary block reward: 50 EXM. Extra output in this block: 2,000,000.00000000 EXM to the founders allocation address.
"""
ROW = "0 50.00000000 EXM Miner reward to exm1qminer000000000000000000000001"
TAIL = "Ordinary block reward: 50 EXM. Extra output in this block: 2,000,000.00000000 EXM to the founders allocation address."
REAL_ALLOC = "1 2,000,000.00000000 EXM Founders allocation to exm1qfounders0000000000000000000001"


@pytest.mark.parametrize("amount,line,printed", [
    ("50", ROW, "50.00000000"), ("50.00000000", TAIL, "50"), ("50", TAIL, "50"), ("50.00000000", ROW, "50.00000000"),
])
def test_the_reward_copied_from_one_line_and_printed_otherwise_on_another_is_kept(env, mod, amount, line, printed):
    a = J(p1a(allocation_amount="2,000,000.00000000", evidence_line=REAL_ALLOC, reward_amount=amount, reward_line=line))
    found = mod._p1(a, L(mod, REAL_A))
    assert found["reward_text"] == printed and found["reward_quote"] == line
    # and the leader's form of it stands on every validator's copy
    assert mod._same_page(found, found, L(mod, REAL_A)) is True
    assert mod._check_page(found, "NO_FOUNDER_REWARD") == found


def test_another_value_on_the_line_is_not_the_reward(env, mod):
    a = J(p1a(allocation_amount="2,000,000.00000000", evidence_line=REAL_ALLOC, reward_amount="25", reward_line=TAIL))
    assert "reward_text" not in mod._p1(a, L(mod, REAL_A))


def test_a_number_on_a_line_that_is_not_on_the_page_is_not_the_reward(env, mod):
    a = J(p1a(allocation_amount="2,000,000.00000000", evidence_line=REAL_ALLOC, reward_amount="50",
              reward_line="Ordinary block reward: 50.00000000 EXM paid to the miner of this block"))
    assert "reward_text" not in mod._p1(a, L(mod, REAL_A))


@pytest.mark.parametrize("amount,line", [("50", ROW), ("50.00000000", TAIL)])
def test_p2_takes_the_reward_printed_otherwise_too(env, mod, amount, line):
    page = REAL_A.replace(REAL_ALLOC + "\n", "").replace(" Extra output in this block: 2,000,000.00000000 EXM to the founders allocation address.", " No other output in this block.")
    line = line.replace(" Extra output in this block: 2,000,000.00000000 EXM to the founders allocation address.", " No other output in this block.")
    a = J(p2a(reward_amount=amount, reward_line=line))
    assert mod._p2(a, L(mod, page)) == {"cls": "SUPPORTS", "rule": "P2", "height": 1}
    assert mod._p2(J(p2a(reward_amount="51", reward_line=line)), L(mod, page)) is None

"""Tests from review 5 (the final build after review 4): the leader's ordinary reward counts only when each validator's
own reading found the same reward; a reward equal to the allocation's amount is never the ordinary reward; the reward
line must say "reward" and be on the page (no line of the page is looked for in its place). Each asserts the
behaviour after the fix; several are the reviewer's own probes."""
import json

from tests.direct.test_checker_v2 import (  # noqa: F401
    A_LINE, A_P1, A_P2, A_REWARD, B_LINE, B_P1, B_P2, B_REWARD, G, J, L, balanced, bond, call, challenge, check, env,
    mocks, mod, p1a, p1b, p2a, p2b, times,
)

# block 0 of a chain whose first block pays no ordinary reward (the review-4 case), as the reviewer wrote it
A0 = """Examplescan: Examplecoin explorer (fictional)
Block 0
Height: 0 (genesis). Transactions: 1.
Outputs
Miner reward 0 EXM to exm1qminer0001
Founders allocation 2,000,000.00000000 EXM to exm1qfounders01
"""
B0 = """Blockfield: Examplecoin (EXM) (fictional)
Block #0
Height 0 (genesis), 1 transaction
Coinbase outputs
exm1qminer0001 receives 0 EXM (block reward)
exm1qfounders01 receives 2,000,000 EXM (founders allocation)
"""
A0_LINE = "Founders allocation 2,000,000.00000000 EXM to exm1qfounders01"
B0_LINE = "exm1qfounders01 receives 2,000,000 EXM (founders allocation)"


def _p1_0(**kw):
    return p1a(block_number="0", evidence_line=A0_LINE, reward_amount="0", reward_line="Miner reward 0 EXM to exm1qminer0001", **kw)


def _p1_0b(**kw):
    return p1b(block_number="0", evidence_line=B0_LINE, reward_amount="0", reward_line="exm1qminer0001 receives 0 EXM (block reward)", **kw)


def _leader_with(env, page, **reward):
    """The stored result of an honest check with page `page` given the leader's own reward fields."""
    full = env.c.get_check("1")["result"]
    fake = json.loads(json.dumps({k: full[k] for k in ("verdict", "rule", "a", "b")}))
    for k in ("reward_text", "reward_quote"):
        fake[page].pop(k, None)
    fake[page].update(reward)
    return fake


# ---- M1: one leader's reading never makes a verdict bondable


def test_validators_refuse_a_leader_reward_that_their_own_reading_did_not_find(env):
    """The reviewer's probe: block 0 pays 0; the validators' own models read 0, so their readings keep no reward. A
    leader that gives the reward as 1, on the line 'Height: 0 (genesis). Transactions: 1.', is refused."""
    out = check(env, pa=A0, pb=B0, aa=_p1_0(), ab=_p1_0b())
    assert out["rule"] == "BOTH:P1" and "reward_text" not in env.c.get_check("1")["result"]["a"]
    fake = _leader_with(env, "a", reward_text="1", reward_quote="Height: 0 (genesis). Transactions: 1.")
    mocks(env, A0, B0, _p1_0(), _p1_0b())
    assert env.vm.run_validator(leader_result=fake) is False


def test_validators_refuse_a_leader_reward_with_another_value(env):
    check(env)
    fake = _leader_with(env, "a", reward_text="25", reward_quote=A_REWARD)
    mocks(env, A_P1, B_P1, p1a(), p1b())
    assert env.vm.run_validator(leader_result=fake) is False


def test_validators_accept_a_leader_reward_their_own_reading_found(env):
    check(env)
    full = env.c.get_check("1")["result"]
    leader = json.loads(json.dumps({k: full[k] for k in ("verdict", "rule", "a", "b")}))
    mocks(env, A_P1, B_P1, p1a(), p1b())
    assert env.vm.run_validator(leader_result=leader) is True
    # the same value printed in another form on the validator's own reading still counts
    mocks(env, A_P1, B_P1, p1a(reward_amount="50"), p1b())
    assert env.vm.run_validator(leader_result=leader) is True


def test_a_leader_reward_line_not_on_the_validators_copy_is_refused_even_when_it_found_its_own(env):
    """The reviewer's mutant E13: this validator finds its own reward, but the leader's line is on no copy."""
    check(env)
    fake = _leader_with(env, "a", reward_text="50.00000000", reward_quote="Miner reward 50.00000000 EXM to exm1qsomeoneelse")
    mocks(env, A_P1, B_P1, p1a(), p1b())
    assert env.vm.run_validator(leader_result=fake) is False


def test_a_zero_reward_block_misread_by_one_leader_is_still_not_bondable(env):
    """End to end: the honest majority's own readings keep no reward, so a misreading leader's result is not agreed
    and nothing bondable is stored."""
    check(env, pa=A0, pb=B0, aa=_p1_0(), ab=_p1_0b())
    fake = _leader_with(env, "b", reward_text="1", reward_quote="Height 0 (genesis), 1 transaction")
    mocks(env, A0, B0, _p1_0(), _p1_0b())
    assert env.vm.run_validator(leader_result=fake) is False
    r = bond(env)
    assert r["ok"] is False and "ordinary reward" in r["error"]
    balanced(env)


# ---- M2: what is kept as the reward


def test_the_allocations_amount_is_never_the_reward_whatever_the_line(env, mod):
    """The reviewer's probes: a shortened copy of the founders' line, and another line printing the same amount."""
    page = A_P1 + "Founders reward 2,000,000.00000000 EXM to exm1qfounders01\n"
    for line in ("Founders allocation 2,000,000.00000000 EXM", "Founders reward 2,000,000.00000000 EXM to exm1qfounders01"):
        a = J(p1a(reward_amount="2,000,000.00000000", reward_line=line))
        found = mod._p1(a, L(mod, page))
        assert found is not None and found["rule"] == "P1" and "reward_text" not in found


def test_a_passed_on_reward_equal_to_the_allocation_is_refused(env, mod):
    import pytest
    page = {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "2000000", "amount_text": "2,000,000.00000000",
            "quote": A_LINE, "reward_text": "2,000,000", "reward_quote": "Founders reward 2,000,000 EXM to exm1qfounders01"}
    with pytest.raises(ValueError):
        mod._check_page(page, "NO_FOUNDER_REWARD")


def test_a_passed_on_reward_line_must_say_reward(env, mod):
    import pytest
    page = {"cls": "CONTRADICTS", "rule": "P1", "height": 1, "amount": "2000000", "amount_text": "2,000,000.00000000",
            "quote": A_LINE, "reward_text": "1", "reward_quote": "Height: 1 (the first block after genesis). Transactions: 1."}
    with pytest.raises(ValueError):
        mod._check_page(page, "NO_FOUNDER_REWARD")


def test_a_line_that_does_not_say_reward_is_not_the_reward(env, mod):
    a = J(p1a(reward_amount="1", reward_line="Height: 1 (the first block after genesis). Transactions: 1."))
    found = mod._p1(a, L(mod, A_P1))
    assert found is not None and "reward_text" not in found


def test_no_line_of_the_page_is_looked_for_in_place_of_the_models(env, mod):
    """The reviewer's probe of the dropped fallback: 'Block 1 reward: 0 EXM' was kept as a reward of 1 (the block
    number). Without a line from the model, nothing is kept; P2 as well."""
    page = """Examplescan: Examplecoin explorer (fictional)
Block 1 reward: 0 EXM (warm-up block)
Height: 1
Outputs
Founders allocation 2,000,000.00000000 EXM to exm1qfounders01
"""
    found = mod._p1(J(p1a(evidence_line="Founders allocation 2,000,000.00000000 EXM to exm1qfounders01", reward_amount="1", reward_line="")), L(mod, page))
    assert found is not None and "reward_text" not in found
    assert mod._p2(J(p2a(reward_amount="50", reward_line="")), L(mod, A_P2)) is None


def test_a_reward_printed_with_punctuation_around_it_is_found(env, mod):
    """The reviewer's mutant E1."""
    page = A_P1.replace(A_REWARD, "Miner reward (50.00000000 EXM) to exm1qminer0001")
    a = J(p1a(reward_amount="50", reward_line="Miner reward (50.00000000 EXM) to exm1qminer0001"))
    assert mod._p1(a, L(mod, page))["reward_text"] == "50.00000000"


def test_p2_needs_a_line_that_says_reward(env, mod):
    line = "exm1qminer0001 gets 50 EXM"
    page = B_P2.replace(B_REWARD, line)
    assert mod._p2(J(p2b(reward_line=line)), L(mod, page)) is None
    assert mod._p2(J(p2b()), L(mod, B_P2)) == {"cls": "SUPPORTS", "rule": "P2", "height": 1}


# ---- the form and the rules


def test_the_prompt_asks_for_the_reward_as_printed_on_the_copied_line_without_the_coin_name(env, mod):
    prompt = mod._prompt("NO_FOUNDER_REWARD", "Examplecoin", "x")
    assert "as printed on the line you copy as reward_line" in prompt and "without the coin's name" in prompt


def test_the_rules_name_the_reward_condition(env):
    rules = env.c.get_rules()
    assert "ordinary reward" in rules["bondable_blocks"] and "0 or 1" in rules["bondable_blocks"]


# ---- the leader's reward against the validator's own reading, with every other check passing

A0_SCHEDULE = A0 + "Reward schedule: 50 EXM per block from block 1\n"
B0_SCHEDULE = B0 + "Reward schedule: 50 EXM per block from block 1\n"


def test_a_leader_reward_that_stands_on_the_page_is_refused_when_the_validators_reading_found_none(env):
    """Block 0 pays 0. The leader takes 50 from a line that says "reward" and prints 50 (the schedule from block 1):
    it stands on every copy and passes every form check, but the validators' own readings found no reward."""
    check(env, pa=A0_SCHEDULE, pb=B0_SCHEDULE, aa=_p1_0(), ab=_p1_0b())
    fake = _leader_with(env, "a", reward_text="50", reward_quote="Reward schedule: 50 EXM per block from block 1")
    mocks(env, A0_SCHEDULE, B0_SCHEDULE, _p1_0(), _p1_0b())
    assert env.vm.run_validator(leader_result=fake) is False
    # a validator whose own reading found the same 50 on that line accepts it (agreement is on the value read)
    own = p1a(block_number="0", evidence_line=A0_LINE, reward_amount="50", reward_line="Reward schedule: 50 EXM per block from block 1")
    mocks(env, A0_SCHEDULE, B0_SCHEDULE, own, _p1_0b())
    assert env.vm.run_validator(leader_result=fake) is True


def test_a_leader_reward_of_another_value_on_a_reward_line_is_refused(env):
    page_a = A_P1 + "Uncle reward 2 EXM to exm1quncle0001\n"
    check(env, pa=page_a)
    fake = _leader_with(env, "a", reward_text="2", reward_quote="Uncle reward 2 EXM to exm1quncle0001")
    mocks(env, page_a, B_P1, p1a(), p1b())  # this validator's own reading found 50
    assert env.vm.run_validator(leader_result=fake) is False

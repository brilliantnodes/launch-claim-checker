import json, pytest
from tests.direct.test_bounties import (env, mod, post, post_m1, file, file_m1, judge, judge_m1, get, balanced, mocks, p1, m1, block, iso, seal, address,
    T0, EXP, TTL, MARGIN, SETTLE, POT, FEE, G, SALT, BLOCK1, CLEAN1, MINING, LINE, NO, TPL, MINE, SUBJ)

def show(label, v):
    print("R3|", label, "=>", v)

def fence(obj):
    return "```json\n" + (obj if isinstance(obj, str) else json.dumps(obj)) + "\n```"

WEIRD_ANS_P1 = [
    {}, {"block_number": [1]}, {"block_number": {"a": 1}}, {"block_number": 1, "extra_allocation": ["yes"]},
    {"block_number": 1, "extra_allocation": "yes", "allocation_amount": {"x": 1}, "evidence_line": LINE},
    {"block_number": 1, "extra_allocation": "yes", "allocation_amount": "2,000,000.00000000", "evidence_line": 5},
    {"block_number": 1, "extra_allocation": "yes", "allocation_amount": "2,000,000.00000000", "evidence_line": [LINE]},
    {"block_number": 1, "extra_allocation": "yes", "allocation_amount": None, "evidence_line": None},
    {"block_number": "1", "extra_allocation": "yes", "allocation_amount": True, "evidence_line": LINE},
    {"block_number": True}, {"block_number": None, "extra_allocation": None},
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": ' + "9" * 5000 + ', "evidence_line": "x"}',
    '{"block_number": ' + "9" * 5000 + '}',
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": ' + "9" * 4000 + ', "evidence_line": "x"}',
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": NaN, "evidence_line": "x"}',
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": Infinity, "evidence_line": "x"}',
    '{"block_number": 1e0, "extra_allocation": "yes", "allocation_amount": 2e6, "evidence_line": "x"}',
    "[" * 5000 + "]" * 5000,
    '{"a":' * 3000 + "1" + "}" * 3000,
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": "2,000,000.00000000", "evidence_line": "' + "x" * 300000 + '"}',
    '{"block_number": 1, "extra_allocation": "yes", "allocation_amount": "\\ud800", "evidence_line": "\\udfff Founders allocation"}',
]

def test_weird_answers_never_raise(env, capsys):
    post(env, expires_at=T0 + 86400)
    res = []
    at = T0 + 60
    for i, a in enumerate(WEIRD_ANS_P1):
        who = address(100 + i)
        assert file(env, who=who, at=at)["ok"]
        try:
            out = judge(env, who=who, at=at + 1, answer=fence(a))
            v = env.vm.run_validator()
            res.append((i, out["outcome"], v))
        except BaseException as e:
            res.append((i, "RAISED", repr(e)[:150]))
        at += 5
    with capsys.disabled():
        show("weird P1 answers", res)
    assert all(r[1] != "RAISED" for r in res)

WEIRD_ANS_M1 = [
    {}, {"top_miner_name": ["Deepvein Pool"], "top_miner_blocks": "840", "blocks_inspected": "1,000"},
    {"top_miner_name": "Deepvein Pool", "top_miner_blocks": [840], "blocks_inspected": "1,000"},
    {"top_miner_name": "Deepvein Pool", "top_miner_blocks": "840", "blocks_inspected": {"n": 1000}},
    {"top_miner_name": "Deepvein Pool", "top_miner_blocks": 840.0, "blocks_inspected": 1000},
    '{"top_miner_name": "Deepvein Pool", "top_miner_blocks": ' + "9" * 4000 + ', "blocks_inspected": ' + "9" * 4000 + '}',
    '{"top_miner_name": "\\ud800abc", "top_miner_blocks": "840", "blocks_inspected": "1,000"}',
]

def test_weird_m1_answers_never_raise(env, capsys):
    post_m1(env, expires_at=T0 + 86400)
    res = []
    at = T0 + 60
    for i, a in enumerate(WEIRD_ANS_M1):
        who = address(100 + i)
        assert file_m1(env, who=who, at=at)["ok"]
        try:
            out = judge_m1(env, who=who, at=at + 1, answer=fence(a))
            v = env.vm.run_validator()
            res.append((i, out["outcome"], v))
        except BaseException as e:
            res.append((i, "RAISED", repr(e)[:150]))
        at += 5
    with capsys.disabled():
        show("weird M1 answers", res)
    assert all(r[1] != "RAISED" for r in res)

def test_weird_leader_results(env, capsys):
    post(env); file(env); judge(env)
    good = {"kind": "PAYS_P1", "amount": "2000000", "amount_text": "2,000,000.00000000", "quote": LINE}
    lies = [{"kind": ["PAYS_P1"]}, {"kind": {"a": 1}}, dict(good, amount_text="9" * 10**5), dict(good, quote=5), dict(good, quote=["x"]), dict(good, quote="x" * 10**6),
            dict(good, amount=["2000000"]), dict(good, amount_text=b"2,000,000.00000000"), b"PAYS_P1", 5, True, [good], dict(good, kind=None), dict(good, kind=5),
            dict(good, amount_text="2,000,000.00000000​"), dict(good, amount_text=" 2,000,000.00000000 "), dict(good, quote=LINE.upper()),
            dict(good, amount="2000000.0"), dict(good, amount_text="2000000", amount="2000000")]
    res = []
    for lie in lies:
        try:
            res.append(env.vm.run_validator(leader_result=lie))
        except BaseException as e:
            res.append("RAISED " + repr(e)[:120])
    with capsys.disabled():
        show("weird leader results", res)

def test_interpret_empty(mod, capsys):
    lines = mod._lines(mod._clean_page(MINING))
    with capsys.disabled():
        show("M1 {} ", mod._interpret_m1({}, 1000, lines))
        show("P1 {} ", mod._interpret_p1({}, 1, mod._lines(mod._clean_page(BLOCK1))))
        show("M1 name only-empty strings", mod._interpret_m1({"top_miner_name": "", "top_miner_blocks": "", "blocks_inspected": ""}, 1000, lines))

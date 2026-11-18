import random, pytest
from tests.direct.test_bounties import (env, mod, post, post_m1, file, file_m1, judge, judge_m1, get, balanced, mocks, p1, m1, iso,
    T0, TTL, MARGIN, POT, FEE, G, SALT, BLOCK1, CLEAN1, MINING, LINE)

ALPH = list("0123456789 ,.'’_abcXYZ-\n\t ​%$()٣²其他") + ["000", " 000", "2 000", "1,000", "unknown", "pool", "0x0", "n/a"]

def rs(rnd, n):
    return "".join(rnd.choice(ALPH) for _ in range(rnd.randint(0, n)))

def test_helpers_never_raise(mod, capsys):
    rnd = random.Random(7)
    hits = {"quote_ok": 0, "pays_p1": 0, "pays_m1": 0}
    for _ in range(60000):
        text, needle = rs(rnd, 30), rs(rnd, 6)
        for i in mod._places(text, needle):
            assert text[i:i + len(needle)] == needle
            mod._spaced(text, i, needle)
        page = mod._clean_page(rs(rnd, 80))
        lines = mod._lines(page)
        q, a = rs(rnd, 40), rs(rnd, 8)
        hits["quote_ok"] += mod._quote_ok(q, a, lines)
        mod._parse_amount(a); mod._parse_count(a); mod._miner_name(q); mod._fold(q)
        ans = {"block_number": rnd.choice([a, 1, None, [1]]), "extra_allocation": rnd.choice(["yes", "no", None, 5]), "allocation_amount": rnd.choice([a, 5, None, {}]), "evidence_line": rnd.choice([q, None, 7])}
        r = mod._interpret_p1(ans, rnd.randint(0, 3), lines)
        hits["pays_p1"] += r["kind"] == "PAYS_P1"
        if r["kind"] == "PAYS_P1":
            assert mod._check_outcome(r, "P1") == r and mod._same_outcome(r, r, lines)
        ans = {"top_miner_name": rnd.choice([q, None, 3]), "top_miner_blocks": rnd.choice([a, 5, None]), "blocks_inspected": rnd.choice([a, 9, None, "1,000"])}
        r = mod._interpret_m1(ans, 500, lines)
        hits["pays_m1"] += r["kind"] == "PAYS_M1"
        if r["kind"] == "PAYS_M1":
            assert mod._check_outcome(r, "M1") == r
    with capsys.disabled():
        print("R3| property run hits", hits)

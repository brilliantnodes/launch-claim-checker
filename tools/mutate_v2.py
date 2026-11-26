#!/usr/bin/env python3
"""Mutation check for LaunchClaimCheckerV2: break the contract on purpose, one
change at a time, and confirm that the v2 tests (tests/direct/test_checker_v2.py,
tests/direct/test_checker_v2_review.py, tests/direct/test_checker_v2_review3.py and
tests/direct/test_checker_v2_review4.py) catch every break.

    PYTHONPATH=. python tools/mutate_v2.py            # all mutants
    PYTHONPATH=. python tools/mutate_v2.py 12 40      # only mutants 12 and 40

Each mutant is written to a temporary file and the tests are pointed at it with
LCC2_CONTRACT; contracts/launch_claim_checker_v2.py itself is never modified.
The helpers copied unchanged from launch_claim_bounties.py (number parsing,
_places, _quote_ok, _catch_all, _miner_name, ...) are covered by
tools/mutate_bounties.py; the mutants here target the code new in v2.

Left out on purpose (changes that make no difference to what the contract does):
- the order of P1 and P2 for the premine claims: the two rules exclude each
  other on one answer ("yes" versus "no" in extra_allocation). (The order of M1
  and M2 is not left out: M1 reads the top-miner fields and M2 the rows, so one
  answer can meet both; review 3 found this, and it is a mutant below.)
- the rule comparison in _combine: two pages of the same class with the same
  block and amount always carry the same rule (a P page has a block, an M page
  has none);
- the per-page class and rule comparison in _same_page: a validator compares it
  only after the verdict and rule matched, and BOTH:<rule> fixes both pages'
  class and rule;
- the miner comparison in _combine for M2 pages, which carry no miner since the
  review fix (an M2 page has neither block, amount nor miner);
- an empty rows list in M2: the unlisted rest is then the whole total, which is
  more than 33%, so the page is refused either way;
- _short in the leader: _check_result cuts an UNDETERMINED result to the short
  form anyway, before it is compared or stored (_short only keeps the data
  passed between nodes small);
- the reason comparison for UNDETERMINED in _same_result: the reason follows
  from the two pages' classes and rules, which are compared next to it. (The
  class comparison is not left out: NOTHING and WRONG_PAGE both carry no rule,
  so A NOTHING / B WRONG_PAGE and the swap give the same reason and rules;
  review 3 found this, and it is a mutant below.)
- the bond's rule test on the result (BOTH:P1/BOTH:P2) next to its claim-type
  test: a NO_PREMINE or NO_FOUNDER_REWARD check is definite only as BOTH:P1 or
  BOTH:P2; for the same reason the re-check outcome's rule test is the same as a
  verdict test for these claims;
- the bond's block test on one page instead of both: a BOTH:P1 or BOTH:P2
  verdict needs the same block on both pages (_combine), so one page's block is
  the other's;
- the bond's P1 reward test on one page's block only is not left out; but the
  per-page block test in _outcome ("overturn: page A's block only" below) is
  defensive: a stored BOTH:P2 result has the same block on both pages
  (_check_result re-runs _combine), so that mutant is caught only by a test
  that hands _outcome a result that cannot occur, and in practice it is
  equivalent;
- a challenge on a decided bond: a decision comes after the challenge window,
  which refuses it first;
- booleans as windows: True and False are below the 600-second floor.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "launch_claim_checker_v2.py").read_text()

MUTANTS = [
    # inputs
    ("IP literal allowed", 'if all(c in DIGITS for c in labels[-1]):\n        return f"{label} must be a host name, not an IP address"', 'if False:\n        return ""'),
    ("http allowed", 'if not url.startswith("https://"):\n        return f"{label} must start with https://"', 'if False:\n        return ""'),
    ("dots allowed", 'if ".." in tail or "//" in tail', 'if False and ".." in tail or "//" in tail'),
    ("path chars unchecked", 'if any(c not in PATH_CHARS for c in tail):', 'if False:'),
    ("host case unchecked", "any(c not in HOST_CHARS for c in lab) for lab in labels):\n        return f\"{label}: the host", "False for lab in labels):\n        return f\"{label}: the host"),
    ("same domain allowed", 'if _domain(_host_of(explorer_a_url)) == _domain(_host_of(explorer_b_url)):', 'if False:'),
    ("domain: no second level", 'if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL:', 'if False:'),
    ("domain: whole host", 'return ".".join(labels[-2:])', 'return host'),
    ("generic words off", 'if all(w in GENERIC_WORDS or all(c in DIGITS for c in w) for w in words):', 'if False:'),
    ("numbers count as a name", 'if all(w in GENERIC_WORDS or all(c in DIGITS for c in w) for w in words):', 'if all(w in GENERIC_WORDS for w in words):'),
    ("name length", 'if not 4 <= len(name) <= 40:\n        return "coin_name', 'if not 3 <= len(name) <= 40:\n        return "coin_name'),
    ("name needs a letter", "or not any(c in LOWER + LOWER.upper() for c in name):\n        return \"coin_name", ":\n        return \"coin_name"),
    ("claim text unlimited", 'if len(claim_text) > MAX_CLAIM_LEN:', 'if False:'),
    ("claim type unchecked", 'if not isinstance(claim_type, str) or claim_type not in CLAIM_TYPES:\n            raise gl.vm.UserError("claim_type', 'if not isinstance(claim_type, str):\n            raise gl.vm.UserError("claim_type'),
    ("anchor anywhere", 'lines[:ANCHOR_LINES]', 'lines'),
    ("no anchor", 'if not _stands("\\n".join(lines[:ANCHOR_LINES]), _fold(coin)):', 'if False:'),
    # P1 / P2
    ("P1 height cap", 'if h is None or h > MAX_HEIGHT or not _block_printed(lines, h):', 'if h is None or not _block_printed(lines, h):'),
    ("P1 height unprinted", 'if h is None or h > MAX_HEIGHT or not _block_printed(lines, h):', 'if h is None or h > MAX_HEIGHT:'),
    ("block number anywhere", 'return any(_stands(line, n) and ("block" in line or "height" in line) for line in lines)', 'return any(_stands(line, n) for line in lines)'),
    ("P1 needs yes", 'if str(ans.get("extra_allocation", "")).strip().lower() != "yes":', 'if str(ans.get("extra_allocation", "")).strip().lower() == "no":'),
    ("P1 quote unchecked", 'if amount is None or not _quote_ok(quote, text, lines):', 'if amount is None:'),
    ("P1 amount unparsed", 'if amount is None or not _quote_ok(quote, text, lines):', 'if not _quote_ok(quote, text, lines):'),
    ("P2 any height", 'if h is None or h > 1 or not _block_printed(lines, h):', 'if h is None or not _block_printed(lines, h):'),
    ("P2 needs no", 'if str(ans.get("extra_allocation", "")).strip().lower() != "no":', 'if str(ans.get("extra_allocation", "")).strip().lower() == "yes":'),
    ("P2 line unchecked", 'if _printed_as(ans.get("reward_line"), _amount_text(ans.get("reward_amount")), lines) is None:\n        return None\n    return {"cls": "SUPPORTS"', 'if _parse_amount(_amount_text(ans.get("reward_amount"))) is None:\n        return None\n    return {"cls": "SUPPORTS"'),
    # M1
    ("M1 half counts", 'if total < MIN_BLOCKS or 2 * top <= total:', 'if total < MIN_BLOCKS or 2 * top < total:'),
    ("M1 no floor", 'if total < MIN_BLOCKS or 2 * top <= total:', 'if 2 * top <= total:'),
    ("M1 catch-all rows", 'if not any(not _catch_all(line) for line in rows):', 'if not rows:'),
    ("M1 total unprinted", 'if printed < (2 if top_f == total_f else 1):', 'if False:'),
    ("M1 top > total", 'if name is None or top is None or total is None or top > total:', 'if name is None or top is None or total is None:'),
    # M2
    ("M2 33 percent", 'if 100 * max(counts + [rest]) > 33 * total:', 'if 100 * max(counts + [rest]) > 34 * total:'),
    ("M2 rest ignored", 'if 100 * max(counts + [rest]) > 33 * total:', 'if 100 * max(counts) > 33 * total:'),
    ("M2 rows can exceed total", 'if rest < 0:\n        return None', 'if False:\n        return None'),
    ("M2 lines can repeat", 'if i not in used and _stands(line, name)', 'if _stands(line, name)'),
    ("M2 row count unprinted", 'and _stands(line, name) and _clear(line, cf)), None)', 'and _stands(line, name)), None)'),
    ("M2 row name unchecked", 'and _stands(line, name) and _clear(line, cf)), None)', 'and _clear(line, cf)), None)'),
    ("M2 no floor", 'if total is None or total < MIN_BLOCKS or not isinstance(rows, list)', 'if total is None or not isinstance(rows, list)'),
    ("M2 row cap", 'not 1 <= len(rows) <= MAX_ROWS:', 'not 1 <= len(rows):'),
    ("M2 total unprinted", "if not any(not _spaced(line, i, total_f) for line in lines for i in _places(line, total_f)):\n        return None\n    used", "if False:\n        return None\n    used"),
    # evidence order and claim types
    ("fair launch can be supported", 'found = _p1(ans, lines) or _m1(ans, lines)\n    else:', 'found = _p1(ans, lines) or _m1(ans, lines) or _p2(ans, lines)\n    else:'),
    # combine
    ("combine: different amounts ok", 'same = a.get("height") == b.get("height") and a.get("amount") == b.get("amount") and', 'same = a.get("height") == b.get("height") and'),
    ("combine: different heights ok", 'same = a.get("height") == b.get("height") and a.get("amount") == b.get("amount") and', 'same = a.get("amount") == b.get("amount") and'),
    ("combine: different miners ok", 'a.get("amount") == b.get("amount") and a.get("miner") == b.get("miner")', 'a.get("amount") == b.get("amount")'),
    ("combine: one page enough", 'if ca == cb and ca in PAGE_RULES and a["rule"] == b["rule"]:\n        same = a.get("height") == b.get("height") and a.get("amount") == b.get("amount") and a.get("miner") == b.get("miner")', 'if ca in PAGE_RULES and cb in (ca, "NOTHING"):\n        same = True'),
    ("combine: unreadable ignored", 'if "UNREADABLE" in (ca, cb):\n        return {"verdict": "UNREADABLE", "rule": ""}', 'if ca == cb == "UNREADABLE":\n        return {"verdict": "UNREADABLE", "rule": ""}'),
    ("combine: no D1", 'if {ca, cb} == {"CONTRADICTS", "SUPPORTS"}:\n        return {"verdict"', 'if False:\n        return {"verdict"'),
    ("combine: no W1", 'if "WRONG_PAGE" in (ca, cb):\n        return {"verdict"', 'if False:\n        return {"verdict"'),
    ("reason: no D1", 'if {ca, cb} == {"CONTRADICTS", "SUPPORTS"}:\n        return "D1', 'if False:\n        return "D1'),
    # leader result checks
    ("check_page: rule vs class", 'if rule not in PAGE_RULES[cls] or rule not in allowed:\n        raise ValueError("bad rule")\n    if rule == "P1":', 'if rule not in allowed:\n        raise ValueError("bad rule")\n    if rule == "P1":'),
    ("check_page: rule vs claim type", 'if rule not in PAGE_RULES[cls] or rule not in allowed:\n        raise ValueError("bad rule")\n    if rule == "P1":', 'if rule not in PAGE_RULES[cls]:\n        raise ValueError("bad rule")\n    if rule == "P1":'),
    ("check_page: amount", 'if amount is None or amount != p.get("amount"):', 'if amount is None:'),
    ("check_result: verdict", 'if r.get("verdict") != c["verdict"] or r.get("rule") != c["rule"]:', 'if r.get("rule") != c["rule"]:'),
    ("check_result: rule", 'if r.get("verdict") != c["verdict"] or r.get("rule") != c["rule"]:', 'if r.get("verdict") != c["verdict"]:'),
    ("check_result: any reason", 'if r.get("rule") != _reason(a, b):', 'if r.get("rule") not in REASONS:'),
    ("check_class: unreadable page", 'or p.get("cls") == "UNREADABLE":\n        raise ValueError("bad class")', ':\n        raise ValueError("bad class")'),
    ("check_class: rule vs claim type", 'if rule not in PAGE_RULES[cls] or rule not in allowed:\n        raise ValueError("bad rule")\n    return {"cls": cls, "rule": rule}', 'if rule not in PAGE_RULES[cls]:\n        raise ValueError("bad rule")\n    return {"cls": cls, "rule": rule}'),
    ("reason: no W1", 'if "WRONG_PAGE" in (ca, cb):\n        return "W1_WRONG_PAGE"', 'if False:\n        return "W1_WRONG_PAGE"'),
    ("check_page: P1 quote", 'or not _stands(_fold(quote), _fold(text)):\n            raise ValueError("bad quote")', ':\n            raise ValueError("bad quote")'),
    ("check_page: P2 block", 'if isinstance(h, bool) or h not in (0, 1):', 'if isinstance(h, bool):'),
    # validator agreement
    ("same: P1 quote", 'return lp["height"] == mp["height"] and lp["amount"] == mp["amount"] and _quote_ok(lp["quote"], lp["amount_text"], lines)', 'return lp["height"] == mp["height"] and lp["amount"] == mp["amount"]'),
    ("same: P1 amount", 'return lp["height"] == mp["height"] and lp["amount"] == mp["amount"] and _quote_ok(lp["quote"], lp["amount_text"], lines)', 'return lp["height"] == mp["height"] and _quote_ok(lp["quote"], lp["amount_text"], lines)'),
    ("same: miner", 'return lp["miner"] == mp["miner"]', 'return True'),
    ("same: P2 block", 'if lp.get("rule") == "P2":\n        return lp["height"] == mp["height"]', 'if lp.get("rule") == "P2":\n        return True'),
    ("same: verdict", 'if v != mine["verdict"]:\n        return False', 'if False:\n        return False'),
    ("same: undetermined page rules", 'leader[p]["cls"] == mine[p]["cls"] and leader[p].get("rule") == mine[p].get("rule") for p in ("a", "b"))', 'leader[p]["cls"] == mine[p]["cls"] for p in ("a", "b"))'),
    ("out of form accepted", 'if not _in_form(ans, claim_type):\n        return {"cls": "UNREADABLE"}, lines', 'if False:\n        return {"cls": "UNREADABLE"}, lines'),
    ("form: rows not a list", 'if not isinstance(v, list):\n                return False', 'if False:\n                return False'),
    ("form: other types", 'elif isinstance(v, bool) or not isinstance(v, (str, int)):', 'elif False:'),
    ("same: page B unchecked", 'and _same_page(leader["a"], mine["a"], la) and _same_page(leader["b"], mine["b"], lb)', 'and _same_page(leader["a"], mine["a"], la)'),
    ("same: pages swapped lines", '_same_page(leader["b"], mine["b"], lb)', '_same_page(leader["b"], mine["b"], la)'),
    ("validator: errors accepted", 'if not isinstance(leader_result, gl.vm.Return):\n            return False', 'if not isinstance(leader_result, gl.vm.Return):\n            return True'),
    ("check records unreadable", 'if r["verdict"] == "UNREADABLE":\n            raise gl.vm.UserError("an explorer page could not be read; nothing was recorded")', 'if False:\n            raise gl.vm.UserError("")'),
    # bond
    ("bond: anyone", 'if gl.message.sender_address.as_hex.lower() != c.requester.lower():\n            problem = "only the requester', 'if False:\n            problem = "only the requester'),
    ("bond: fair launch", 'elif (rec["claim_type"] not in BONDABLE_CLAIMS or rec["result"]["rule"] not in OPPOSITE', 'elif (rec["result"]["rule"] not in OPPOSITE'),
    ("bond: twice", 'elif bd["state"] != "NONE":\n            problem = "this check is already bonded"', 'elif False:\n            problem = ""'),
    ("bond: no minimum", 'elif value < MIN_BOND:', 'elif value < 1:'),
    ("bond: late by tx time", 'elif now > rec["t0"] + w["bond_win"]:', 'elif now > rec["t0"] + w["bond_win"] + 1:'),
    ("bond: refusal keeps GEN", 'self._credit(gl.message.sender_address.as_hex, value)\n        return {"ok": False', 'return {"ok": False'),
    ("bond: not locked", 'bd.update(state="BONDED", amount=value, tb=now, held=value, clock=max(bd["clock"], now))\n        self.locked = u256(int(self.locked) + value)', 'bd.update(state="BONDED", amount=value, tb=now, held=value, clock=max(bd["clock"], now))'),
    # challenge
    ("challenge: requester allowed", 'elif me == c.requester.lower():', 'elif False:'),
    ("challenge: twice", 'elif f"{c.id}:{me}" in self.challenger_of:', 'elif False:'),
    ("challenge: any amount", 'elif int(gl.message.value) != bd["amount"]:', 'elif int(gl.message.value) < bd["amount"]:'),
    ("challenge: late by tx time", 'if now > t["close"] or bd["clock"] >= t["rc_open"]:', 'if now > t["close"] + 1 or bd["clock"] >= t["rc_open"]:'),
    ("challenge: clock ignored", 'if now > t["close"] or bd["clock"] >= t["rc_open"]:', 'if now > t["close"]:'),
    ("challenge: deposit not held", 'bd["held"] += bd["amount"]', 'pass'),
    # recheck
    ("recheck: unchallenged", 'if bd["state"] != "BONDED" or bd["n"] == 0:', 'if bd["state"] != "BONDED":'),
    ("recheck: early", 'if not t["rc_open"] <= now <= t["rc_end"]:', 'if not t["close"] <= now <= t["rc_end"]:'),
    ("recheck: late", 'if not t["rc_open"] <= now <= t["rc_end"]:', 'if not t["rc_open"] <= now <= t["rc_end"] + 1:'),
    ("recheck: unreadable decides", 'if not (r["rule"].startswith("BOTH:") or r["rule"] == "D1_EXPLORERS_DISAGREE"):', 'if not (r["rule"].startswith("BOTH:") or r["rule"] in ("D1_EXPLORERS_DISAGREE", "")):'),
    ("recheck: wrong page decides", 'if not (r["rule"].startswith("BOTH:") or r["rule"] == "D1_EXPLORERS_DISAGREE"):', 'if not (r["rule"].startswith("BOTH:") or r["rule"] in ("D1_EXPLORERS_DISAGREE", "W1_WRONG_PAGE")):'),
    ("outcome: another amount upholds", 'for p in ("a", "b") for k in ("height", "amount")):', 'for p in ("a", "b") for k in ("height",)):'),
    ("outcome: another block upholds", 'for p in ("a", "b") for k in ("height", "amount")):', 'for p in ("a", "b") for k in ("amount",)):'),
    ("outcome: undetermined overturns", 'if new["rule"] == OPPOSITE.get(old["rule"]) and all(new[p].get("height") == old[p].get("height") for p in ("a", "b")):', 'if new["rule"] != old["rule"]:'),
    ("outcome: same is not upheld", '        return "UPHELD"\n', '        return "NOT_CONFIRMED"\n'),
    ("overturn: nothing burned", 'burn = bd["amount"] // 2', 'burn = 0'),
    ("overturn: burn not counted", 'self.burned = u256(int(self.burned) + burn)', 'pass'),
    ("overturn: burn still locked", 'self.locked = u256(int(self.locked) - burn)\n            self.burned', 'self.burned'),
    # settle
    ("settle: release early", 'if bd["n"] == 0 and bd["clock"] >= t["rc_open"]:', 'if bd["n"] == 0 and bd["clock"] >= t["close"]:'),
    ("settle: not confirmed early", 'elif bd["n"] > 0 and bd["clock"] >= t["nc_from"]:', 'elif bd["n"] > 0 and bd["clock"] >= t["rc_end"]:'),
    ("settle: release with challengers", 'if bd["n"] == 0 and bd["clock"] >= t["rc_open"]:', 'if bd["clock"] >= t["rc_open"] and bd["n"] >= 0 and bd["clock"] < t["nc_from"]:'),
    # collect
    ("collect: requester twice", 'if bd["req_collected"]:\n                raise', 'if False:\n                raise'),
    ("collect: challenger twice", 'if mark.endswith(":collected"):', 'if False:'),
    ("collect: upheld without deposits", '"UPHELD": B + n * B', '"UPHELD": B'),
    ("collect: requester paid on overturn", '{"UPHELD": B + n * B, "NOT_CONFIRMED": B, "RELEASED": B}.get(st, 0)', '{"UPHELD": B + n * B, "NOT_CONFIRMED": B, "RELEASED": B}.get(st, B)'),
    ("collect: share remainder", 'due = B + pool // n + (1 if i < pool % n else 0)', 'due = B + pool // n'),
    ("collect: share remainder wrong end", 'due = B + pool // n + (1 if i < pool % n else 0)', 'due = B + pool // n + (1 if i >= n - pool % n else 0)'),
    ("collect: whole bond shared", 'pool = B - B // 2', 'pool = B'),
    ("collect: not confirmed keeps deposit", 'elif st == "NOT_CONFIRMED":\n                due = B', 'elif False:\n                due = B'),
    ("collect: before outcome", 'if st not in ("UPHELD", "OVERTURNED", "NOT_CONFIRMED", "RELEASED"):', 'if st == "NONE":'),
    ("collect: locked not reduced", 'self.locked = u256(int(self.locked) - due)', 'pass'),
    # withdraw
    ("withdraw: not reduced", 'self.claims[k] = u256(have - amount)', 'self.claims[k] = u256(have)'),
    # from the review: guards the first suite did not exercise
    ("withdraw: more than the credit", 'if not 0 < amount <= have:', 'if not 0 < amount:'),
    ("withdraw: partial ignored", 'if amount == 0:\n            amount = have', 'if True:\n            amount = have'),
    ("constructor: no caps", 'not WIN_FLOOR <= v <= WIN_CAPS[k]', 'not WIN_FLOOR <= v'),
    ("challengers not indexed", '        self._index(me, c.id)\n        self._save(c, bd)\n        return {"ok": True, "challenger"', '        self._save(c, bd)\n        return {"ok": True, "challenger"'),
    ("port zero allowed", 'and port[1] != "0" and int(port[1:]) <= 65535', 'and int(port[1:]) <= 65535'),
    ("port above 65535", 'and port[1] != "0" and int(port[1:]) <= 65535', 'and port[1] != "0"'),
    ("anchor 13 lines", 'ANCHOR_LINES = 12', 'ANCHOR_LINES = 13'),
    ("page 7000 chars", 'PAGE_CHARS = 6000', 'PAGE_CHARS = 7000'),
    # from review 3
    ("UNDETERMINED: page classes not compared", 'leader[p]["cls"] == mine[p]["cls"] and leader[p].get("rule") == mine[p].get("rule") for p in ("a", "b"))', 'leader[p].get("rule") == mine[p].get("rule") for p in ("a", "b"))'),
    ("M2 tried before M1", 'found = _m1(ans, lines) or _m2(ans, lines)', 'found = _m2(ans, lines) or _m1(ans, lines)'),
    ("bond: P1 on any block", '\n              or any(int(rec["result"][p].get("height", 2)) > 1 for p in ("a", "b"))):', '):'),
    ("overturn: any block", 'if new["rule"] == OPPOSITE.get(old["rule"]) and all(new[p].get("height") == old[p].get("height") for p in ("a", "b")):', 'if new["rule"] == OPPOSITE.get(old["rule"]):'),
    ("overturn: page A's block only", 'all(new[p].get("height") == old[p].get("height") for p in ("a", "b")):\n        return "OVERTURNED"', 'all(new[p].get("height") == old[p].get("height") for p in ("a",)):\n        return "OVERTURNED"'),
    ("recheck: nothing found decides", 'if not (r["rule"].startswith("BOTH:") or r["rule"] == "D1_EXPLORERS_DISAGREE"):', 'if r["verdict"] == "UNREADABLE" or "WRONG_PAGE" in (r["a"]["cls"], r["b"]["cls"]):'),
    ("recheck: disagreeing explorers decide nothing", 'if not (r["rule"].startswith("BOTH:") or r["rule"] == "D1_EXPLORERS_DISAGREE"):', 'if not r["rule"].startswith("BOTH:"):'),
    ("field names allowed as coin names", '"difficulty", "nonce", "version", "merkle", "root", "previous", "prev", "next", "timestamp", "weight", "bits", "height",', ''),
    ("mining counts not digits only", "that miner\\'s number of blocks as printed, digits only", "that miner\\'s number of blocks exactly as printed"),
    # from review 4
    ("bond: block 2 allowed", 'or any(int(rec["result"][p].get("height", 2)) > 1 for p in ("a", "b"))):', 'or any(int(rec["result"][p].get("height", 2)) > 2 for p in ("a", "b"))):'),
    ("bond: P1 without the reward", 'elif rec["result"]["rule"] == "BOTH:P1" and any("reward_text" not in rec["result"][p] for p in ("a", "b")):', 'elif False:'),
    ("bond: P1 reward on page A only", 'any("reward_text" not in rec["result"][p] for p in ("a", "b")):', 'any("reward_text" not in rec["result"][p] for p in ("a",)):'),
    ("P1 keeps no reward", 'return {**found, **_reward(ans, lines)}', 'return found'),
    ("reward line not checked on the page", 'if _quote_ok(line, text, lines):\n        return text.strip()', 'if True:\n        return text.strip()'),
    ("reward: same value printed otherwise not taken", 'if tok and _parse_amount(tok) == want and _quote_ok(line, tok, lines):', 'if False:'),
    ("reward: another value on the line taken", 'if tok and _parse_amount(tok) == want and _quote_ok(line, tok, lines):', 'if tok and _parse_amount(tok) is not None and _quote_ok(line, tok, lines):'),
    ("reward: the other number not checked on the page", 'if tok and _parse_amount(tok) == want and _quote_ok(line, tok, lines):', 'if tok and _parse_amount(tok) == want:'),
    ("allocation taken as the reward", 'if _fold(ans.get("reward_line")) == _fold(ans.get("evidence_line")) and _parse_amount(text) == _parse_amount(_amount_text(ans.get("allocation_amount"))):', 'if False:'),
    ("passed-on reward not checked", 'if "reward_text" in p or "reward_quote" in p:', 'if False:'),
    ("passed-on reward of 0 allowed", 'if not isinstance(rt, str) or _parse_amount(rt) is None:', 'if not isinstance(rt, str):'),
    ("passed-on reward line not checked", 'if not isinstance(rq, str) or not QUOTE_MIN <= len(_fold(rq)) <= QUOTE_MAX or not _stands(_fold(rq), _fold(rt)):', 'if not isinstance(rq, str):'),
    ("passed-on allocation as reward", 'if _fold(rq) == _fold(quote) and _parse_amount(rt) == amount:', 'if False:'),
    ("leader's reward line not checked", 'reward_ok = "reward_text" not in lp or _quote_ok(lp["reward_quote"], lp["reward_text"], lines)', 'reward_ok = True'),
    ("reward asked only on no", '"reward_amount": the ordinary block reward paid to this block', '"reward_amount": if "no", the ordinary block reward paid to this block'),
]


def run_one(job) -> tuple:
    i, name, path, env = job
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/direct/test_checker_v2.py", "tests/direct/test_checker_v2_review.py",
                        "tests/direct/test_checker_v2_review3.py", "tests/direct/test_checker_v2_review4.py", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=ROOT, env={**env, "LCC2_CONTRACT": str(path)}, capture_output=True, text=True)
    return i, name, r.returncode != 0


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor

    only = {int(a) for a in sys.argv[1:]}
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    tmp = Path(tempfile.mkdtemp(prefix="lcc2-mutants-"))
    jobs, bad = [], 0
    for i, (name, old, new) in enumerate(MUTANTS, 1):
        n = SRC.count(old)
        if n != 1 or old == new:
            print(f"SETUP ERROR  {i} {name}: pattern found {n} times")
            bad += 1
            continue
        if only and i not in only:
            continue
        path = tmp / f"mutant_{i:03d}.py"
        path.write_text(SRC.replace(old, new))
        jobs.append((i, name, path, env))
    if bad:
        return 2
    caught, missed = 0, []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("MUTATE_JOBS", "6"))) as pool:
        for i, name, ok in pool.map(run_one, jobs):
            caught += ok
            if not ok:
                missed.append(i)
            print(f"{'caught ' if ok else 'MISSED '} {i:3d} {name}", flush=True)
    print(f"\n{caught} of {len(jobs)} mutants caught" + (f"; missed: {missed}" if missed else ""))
    return 0 if caught == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())

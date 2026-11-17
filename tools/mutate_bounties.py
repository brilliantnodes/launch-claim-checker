#!/usr/bin/env python3
"""Mutation check for LaunchClaimBounties: break the contract on purpose, one
change at a time, and confirm that the direct-mode tests catch every break.

    PYTHONPATH=. python tools/mutate_bounties.py            # all mutants
    PYTHONPATH=. python tools/mutate_bounties.py 12 40      # only mutants 12 and 40

Each mutant is written to a temporary file and the tests are pointed at it
with LCB_CONTRACT; contracts/launch_claim_bounties.py itself is never modified.

Left out on purpose (equivalent mutants, so no test can catch them):
- the float check in _parse_count: a float's text has a dot, which the digit
  check refuses;
- removing only one of the two marker replacements in _clean_page: the
  third replacement already removes every marker;
- the checks on a leader's result for the quote (its length, and that it
  contains the amount) and for the rule: a validator also compares the
  leader with its own reading through _same_outcome and _quote_ok, which
  refuse the same results, so removing one of the doubled checks changes
  nothing;
- the type check at the top of _quote_ok: a value of another type fails the
  length or the amount check that follows;
- min() over the caller's matching live filings in judge(): one address has
  at most one live filing at any transaction time, so there is one to pick;
- the empty-needle guard in _places: no caller passes an empty needle;
- the fraction handling in _to_micros: newer Pythons read any number of
  fraction digits themselves, so the tests cannot tell it is there;
- the final money-adds-up check in _save, a safety net no correct path trips.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "launch_claim_bounties.py").read_text()

SAME = 'return leader["amount"] == mine["amount"] and _quote_ok(leader["quote"], leader["amount_text"], lines)'
STANDS_B = "joined_before = b1.isalnum() or (needle[0].isdigit() and b1 in JOINERS and b2.isdigit())"
STANDS_A = "joined_after = a1.isalnum() or (needle[-1].isdigit() and a1 in JOINERS and a2.isdigit())"
ON_PAGE = "    if not any(_stands(line, name) and _stands(line, top_f) for line in lines) or not _stands(page, _fold(total_text)):"
AMOUNT_IN = "    if not any(not _spaced(q, i, a) for i in _places(q, a)):\n        return False"
CATCH = "        if word in AGGREGATE_WORDS or word.startswith(AGGREGATE_STEMS):\n            return None"
ZEROS = 'if ("0" in name and all(c in "0x" for c in name)) or any(part in name for part in AGGREGATE_PARTS):'
AFTER = 'and not (text[j + 4 : j + 5] != "" and text[j + 4] in DIGITS):\n        return True'
BEFORE = '    return k == 3 and i >= 2 and text[i - 1] == " " and text[i - 2] in DIGITS'
TOO_LATE = 'if s["t"] >= ts + FILING_TTL:'
BAD_TIME = """        try:
            us = self._us()
        except Exception:
            return self._refuse("the transaction's time could not be read")"""
PORT = 'if port != "" and not (2 <= len(port) <= 6 and all(c in DIGITS for c in port[1:]) and port[1] != "0" and int(port[1:]) <= 65535):'
DOTS = 'if ".." in tail or "//" in tail or "/./" in tail or tail.endswith("/."):'
TOUCH = 'if (before != "" and before in DIGITS) or (after != "" and after in DIGITS):'
LABELS = 'if host == "" or any(lab == "" or lab[0] == "-" or lab[-1] == "-" or any(c not in HOST_CHARS for c in lab) for lab in labels):'
DIGEST = 'if not isinstance(digest, str) or len(digest) != 64 or any(c not in HEX for c in digest):'
ONE_LIVE = 'if any(f["hunter"].lower() == me.lower() and f["status"] == "LIVE" and ts <= f["at"] + FILING_TTL for f in s["filings"]):'
LIVE = 'return f["status"] == "LIVE" and f["at"] <= ts <= f["at"] + FILING_TTL'
HEIGHT = 'if (rule == "P1" and not 0 <= height <= MAX_HEIGHT) or (rule == "M1" and height != 0):'
WAITS = 'if _rank(g) < first and g["status"] == "LIVE"]'
SHORT = "if sum(1 for c in name if c.isalnum()) < 3 or not any(c.isalpha() for c in name):"
BLOCK_NO = 'if _parse_count(ans.get("block_number")) != height or not _stands(page, str(height)):'
COLLAPSE = 'text = "\\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())'
PAYS = 'if total < min_blocks or 2 * top <= total:\n        return {"kind": "NO_PAY"}'
TAIL = '        return {"kind": kind, "miner": name}\n    return {"kind": kind}'

MUTANTS = [
    # --- agreement between validators
    ("P1 amount not compared", SAME, 'return _quote_ok(leader["quote"], leader["amount_text"], lines)'),
    ("leader's line not checked on the validator's copy", SAME, 'return leader["amount"] == mine["amount"]'),
    ("M1 miner not compared", 'return leader["miner"] == mine["miner"]', "return True"),
    ("outcome class not compared", 'if leader["kind"] != mine["kind"]:\n        return False', "if False:\n        return False"),
    # --- checks on the leader's result
    ("leader amount not re-derived", 'if amount is None or amount != r.get("amount"):', "if amount is None:"),
    ("leader miner name not checked", 'if name is None or name != r.get("miner"):', "if False:"),
    ("unchecked fields of a leader result are kept", TAIL, '        return dict(r, miner=name)\n    return {"kind": kind}'),
    ("fields of a result that pays nothing are kept", TAIL, '        return {"kind": kind, "miner": name}\n    return r'),
    # --- P1 interpretation
    ("block number not checked", BLOCK_NO, "if not _stands(page, str(height)):"),
    ("block number need not be printed on the page", BLOCK_NO, 'if _parse_count(ans.get("block_number")) != height:'),
    ("anything but 'no' pays", 'if str(ans.get("extra_allocation", "")).strip().lower() != "yes":', 'if str(ans.get("extra_allocation", "")).strip().lower() == "no":'),
    ("line not required", 'if amount is None or not _quote_ok(quote, amount_text, lines):\n        return {"kind": "NO_PAY"}', 'if amount is None:\n        return {"kind": "NO_PAY"}'),
    ("line need not be on the page", "    return any(_stands(line, q) for line in lines)", "    return True"),
    ("line may start or stop inside a word or number", "    return any(_stands(line, q) for line in lines)", "    return any(q in line for line in lines)"),
    ("line may be stitched across lines", "    return any(_stands(line, q) for line in lines)", '    return _stands(" ".join(lines), q)'),
    ("line need not contain the amount", AMOUNT_IN, "    if False:\n        return False"),
    ("the amount may be part of a longer number in the line", AMOUNT_IN, "    if a not in q:\n        return False"),
    ("an amount next to another number is accepted", AMOUNT_IN, "    if not _places(q, a):\n        return False"),
    ("a number followed by a group of three digits is not ambiguous", AFTER, AFTER.replace("return True", "pass")),
    ("a number followed by four digits is ambiguous", AFTER, ":\n        return True"),
    ("a number of three digits after another number is not ambiguous", BEFORE, "    return False"),
    ("any number after another number is ambiguous", BEFORE, BEFORE.replace("k == 3", "k >= 1")),
    ("apostrophes and underscores do not join digits", 'JOINERS = ",.\'\\u2019_"', 'JOINERS = ",."'),
    ("no minimum line length", "if not QUOTE_MIN <= len(q) <= QUOTE_MAX:", "if not len(q) <= QUOTE_MAX:"),
    ("no maximum line length", "if not QUOTE_MIN <= len(q) <= QUOTE_MAX:", "if not QUOTE_MIN <= len(q):"),
    ("a whole-number amount from the model is refused", '    if isinstance(amount_text, int) and not isinstance(amount_text, bool):\n        amount_text = str(amount_text)\n', ""),
    ("a JSON number loses its digits", "out = json.loads(s, parse_float=str)", "out = json.loads(s)"),
    # --- amounts and counts
    ("12.450 accepted", 'elif dot and len(frac) == 3 and whole not in ("", "0"):\n        return None', "elif False:\n        return None"),
    ("zero amount accepted", 'if int(whole + (frac or "0")) == 0:\n        return None', "if False:\n        return None"),
    ("float amounts accepted", "if value is None or isinstance(value, (bool, float)):", "if value is None:"),
    ("trailing zeros kept", '    frac = frac.rstrip("0")\n', ""),
    ("leading zeros accepted in amounts", 'if len(whole) > 1 and whole[0] == "0":\n        return None\n    if len(whole) + len(frac)', "if False:\n        return None\n    if len(whole) + len(frac)"),
    ("a trailing dot accepted", 'if dot and frac == "":\n        return None', "if False:\n        return None"),
    ("amount size not capped", "if len(whole) + len(frac) > MAX_AMOUNT_DIGITS:\n        return None", "if False:\n        return None"),
    ("bool counts accepted", "    if isinstance(value, bool) or isinstance(value, float):\n        return None\n    if isinstance(value, int):", "    if isinstance(value, float):\n        return None\n    if isinstance(value, int):"),
    ("leading zeros accepted in counts", ' or (len(s) > 1 and s[0] == "0"):\n        return None\n    n = int(s)', ":\n        return None\n    n = int(s)"),
    ("count size not capped", "    n = int(s)\n    return n if n <= MAX_COUNT else None", "    n = int(s)\n    return n"),
    ("text may continue to the left", "if not joined_before and not joined_after:", "if not joined_after:"),
    ("text may continue to the right", "if not joined_before and not joined_after:", "if not joined_before:"),
    ("a word may continue to the left", STANDS_B, "joined_before = needle[0].isdigit() and b1 in JOINERS and b2.isdigit()"),
    ("a word may continue to the right", STANDS_A, "joined_after = needle[-1].isdigit() and a1 in JOINERS and a2.isdigit()"),
    ("a number may be joined by a separator on the left", STANDS_B, "joined_before = b1.isalnum()"),
    ("a number may be joined by a separator on the right", STANDS_A, "joined_after = a1.isalnum()"),
    ("only the first place a text appears is looked at", "        start = i + 1\n", "        return out\n"),
    # --- reading
    ("subject name not required", '    if not _stands("\\n".join(lines), _fold(subject)):\n        return {"kind": "WRONG_PAGE"}, lines', '    if False:\n        return {"kind": "WRONG_PAGE"}, lines'),
    ("an empty page is read", '    if not lines:\n        return {"kind": "UNREADABLE"}, lines', '    if False:\n        return {"kind": "UNREADABLE"}, lines'),
    ("a page that fails to load is read as a page", '    except Exception:\n        return ""', '    except Exception:\n        return "x"'),
    ("a model that does not answer, or answers out of form, uses up the filing", 'return {"kind": "UNREADABLE"}, lines  # no answer', 'return {"kind": "NO_PAY"}, lines  # no answer'),
    ("page markers not removed", '.replace(PAGE_BEGIN, " ").replace(PAGE_END, " ").replace("=====", " ")\n', "\n"),
    ("page not cut", "    if len(text) > PAGE_CHARS:", "    if False:"),
    ("the page cut can split a number", "        text = text[:cut] if cut > 0 else text[:PAGE_CHARS]", "        text = text[:PAGE_CHARS]"),
    ("the page cut drops a last word that fits exactly", "        text = text[: PAGE_CHARS + 1]", "        text = text[:PAGE_CHARS]"),
    ("spacing inside lines not collapsed", COLLAPSE, 'text = "\\n".join(line for line in text.splitlines() if line.strip())'),
    ("blank lines kept", COLLAPSE, 'text = "\\n".join(" ".join(line.split()) for line in text.splitlines())'),
    ("zero-width characters kept", '    for z in ZERO_WIDTH:\n        s = s.replace(z, "")\n', ""),
    # --- M1 interpretation
    ("exactly half pays", PAYS, 'if total < min_blocks or 2 * top < total:\n        return {"kind": "NO_PAY"}'),
    ("min_blocks ignored", PAYS, 'if 2 * top <= total:\n        return {"kind": "NO_PAY"}'),
    ("one block short of min_blocks pays", PAYS, 'if total < min_blocks - 1 or 2 * top <= total:\n        return {"kind": "NO_PAY"}'),
    ("catch-all rows count as a miner", CATCH, "        if False:\n            return None"),
    ("catch-all words glued to another word count as a miner", CATCH, "        if word in AGGREGATE_WORDS:\n            return None"),
    ("only the stems of catch-all words are checked", CATCH, "        if word.startswith(AGGREGATE_STEMS):\n            return None"),
    ("a zero address counts as a miner", ZEROS, "if any(part in name for part in AGGREGATE_PARTS):"),
    ("catch-all labels without spaces between words count as a miner", ZEROS, 'if "0" in name and all(c in "0x" for c in name):'),
    ("n/a counts as a miner", 'for ch in name.replace("n/a", "na") + " ":', 'for ch in name + " ":'),
    ("a catch-all word at the end of a name is missed", 'for ch in name.replace("n/a", "na") + " ":', 'for ch in name.replace("n/a", "na"):'),
    ("only the first word of a name is checked", "            return None  # 'other (9 addresses)'", "            return None\n        if word:\n            break  # 'other (9 addresses)'"),
    ("names of one or two characters count as a miner", SHORT, "if not any(c.isalpha() for c in name):"),
    ("names without a letter count as a miner", SHORT, "if sum(1 for c in name if c.isalnum()) < 3:"),
    ("miner name length not capped", 'if name == "" or len(name) > MAX_NAME_LEN:', 'if name == "":'),
    ("miner need not be on the page", ON_PAGE, "    if not _stands(page, top_f) or not _stands(page, _fold(total_text)):"),
    ("top count need not be on the page", ON_PAGE, "    if not _stands(page, name) or not _stands(page, _fold(total_text)):"),
    ("total count need not be on the page", ON_PAGE, "    if not any(_stands(line, name) and _stands(line, top_f) for line in lines):"),
    ("the miner and its count may stand on different lines", ON_PAGE, "    if not _stands(page, name) or not _stands(page, top_f) or not _stands(page, _fold(total_text)):"),
    ("top above total accepted", "if name is None or top is None or total is None or top > total:", "if name is None or top is None or total is None:"),
    # --- pinned addresses
    ("http accepted", 'if not url.startswith("https://"):\n        return f"{label} must start with https://"', 'if False:\n        return f"{label} must start with https://"'),
    ("upper-case host accepted", 'HOST_CHARS = LOWER + DIGITS + "-"', 'HOST_CHARS = LOWER + LOWER.upper() + DIGITS + "-"'),
    ("any character accepted in the host", LABELS, 'if host == "" or any(lab == "" or lab[0] == "-" or lab[-1] == "-" for lab in labels):'),
    ("host labels may start or end with a hyphen", LABELS, 'if host == "" or any(lab == "" or any(c not in HOST_CHARS for c in lab) for lab in labels):'),
    ("any port accepted", PORT, "if False:"),
    ("port 0 and leading zeros accepted", PORT, PORT.replace(' and port[1] != "0"', "")),
    ("ports above 65535 accepted", PORT, PORT.replace(" and int(port[1:]) <= 65535", "")),
    ("an empty port accepted", PORT, PORT.replace("2 <= len(port) <= 6", "len(port) <= 6")),
    ("private hosts accepted", 'if _is_private_host(host):\n        return f"{label} must be a public address"', 'if False:\n        return f"{label} must be a public address"'),
    ("address length not capped", "if len(url) == 0 or len(url) > MAX_URL_LEN:", "if len(url) == 0:"),
    ("any character accepted after the host", "    if any(c not in PATH_CHARS for c in body):", "    if False:"),
    (".. accepted", DOTS, 'if "//" in tail or "/./" in tail or tail.endswith("/."):'),
    ("// accepted", DOTS, 'if ".." in tail or "/./" in tail or tail.endswith("/."):'),
    ("/./ accepted", DOTS, 'if ".." in tail or "//" in tail or tail.endswith("/."):'),
    ("a trailing /. accepted", DOTS, 'if ".." in tail or "//" in tail or "/./" in tail:'),
    ("template without {n} accepted", '        if i < 0:\n            return f"{label} must contain', '        if False:\n            return f"{label} must contain'),
    ("a second {n} accepted", 'body = tail.replace("{n}", "", 1) if template else tail', 'body = tail.replace("{n}", "") if template else tail'),
    ("{n} accepted in the mining address", 'body = tail.replace("{n}", "", 1) if template else tail', 'body = tail.replace("{n}", "", 1)'),
    ("a digit may stand before {n}", TOUCH, 'if after != "" and after in DIGITS:'),
    ("a digit may stand after {n}", TOUCH, 'if before != "" and before in DIGITS:'),
    ("private name endings accepted", 'if ("." + host).endswith(PRIVATE_SUFFIXES):\n        return True', "if False:\n        return True"),
    ("single-label hosts accepted", 'if len(labels) < 2 or any(lab == "" for lab in labels):\n        return True', 'if any(lab == "" for lab in labels):\n        return True'),
    ("loopback, link-local and 172.16 addresses accepted", "if a in (0, 10, 127) or a >= 224 or (a == 169 and b == 254) or (a == 172 and 16 <= b <= 31):", "if False:"),
    ("192.168, carrier and benchmark addresses accepted", "if (a == 192 and b == 168) or (a == 100 and 64 <= b <= 127) or (a == 198 and b in (18, 19)):", "if False:"),
    ("192.0.0 and 192.0.2 addresses accepted", "if a == 192 and b == 0 and int(labels[2]) in (0, 2):\n            return True", "if False:\n            return True"),
    ("172.32 treated as private", "(a == 172 and 16 <= b <= 31)", "(a == 172 and 16 <= b <= 32)"),
    ("172.15 treated as private", "(a == 172 and 16 <= b <= 31)", "(a == 172 and 15 <= b <= 31)"),
    ("100.128 treated as private", "(a == 100 and 64 <= b <= 127)", "(a == 100 and 64 <= b <= 128)"),
    ("odd forms of an IPv4 address accepted", "if len(labels) != 4 or not all(all(c in DIGITS for c in lab) and str(int(lab)) == lab and int(lab) <= 255 for lab in labels):\n            return True", "if False:\n            return True"),
    ("a top-level name may start with a digit or hyphen", "    return not labels[-1][0] in LOWER", "    return False"),
    # --- posting
    ("unneeded block template accepted", 'elif block_url_template != "":', "elif False:"),
    ("unneeded mining address accepted", 'elif mining_url != "":', "elif False:"),
    ("no minimum term", "if not now + MIN_TERM <= expires_at <= now + MAX_TERM:", "if not now <= expires_at <= now + MAX_TERM:"),
    ("no maximum term", "if not now + MIN_TERM <= expires_at <= now + MAX_TERM:", "if not now + MIN_TERM <= expires_at:"),
    ("min_blocks floor ignored", "if not MIN_BLOCKS_FLOOR <= min_blocks <= MIN_BLOCKS_CAP:", "if not min_blocks <= MIN_BLOCKS_CAP:"),
    ("min_blocks cap ignored", "if not MIN_BLOCKS_FLOOR <= min_blocks <= MIN_BLOCKS_CAP:", "if not MIN_BLOCKS_FLOOR <= min_blocks:"),
    ("no minimum pot", "if value < MIN_BOUNTY:", "if value < 0:"),
    ("no minimum fee", '"fee": max(MIN_FEE, value * FEE_BP // BP)', '"fee": value * FEE_BP // BP'),
    ("fee of 1%", "FEE_BP = 200", "FEE_BP = 100"),
    ("subject characters not checked", 'if not all(c in LOWER + LOWER.upper() + DIGITS + " -" for c in name) or not any(c in LOWER + LOWER.upper() for c in name):', "if False:"),
    ("subject length not checked", "if not 4 <= len(name) <= 40:", "if False:"),
    ("subject of 41 characters accepted", "if not 4 <= len(name) <= 40:", "if not 4 <= len(name) <= 41:"),
    ("subject spacing not checked", 'if name != " ".join(name.split()):', "if False:"),
    ("a refused payment is kept", '        self._credit(gl.message.sender_address.as_hex, value)\n        return {"ok": False', '        return {"ok": False'),
    ("bool expiry accepted", "if isinstance(expires_at, bool) or not isinstance(expires_at, int) or", "if not isinstance(expires_at, int) or"),
    ("bool min_blocks accepted", "or isinstance(min_blocks, bool) or not isinstance(min_blocks, int):", "or not isinstance(min_blocks, int):"),
    ("a post with missing arguments raises", '        claim_type: str = "",\n', "        claim_type: str,\n"),
    # --- filing
    ("a filing with missing arguments raises", 'def file_claim(self, bounty_id: str = "", digest: str = "") -> dict:', "def file_claim(self, bounty_id: str, digest: str) -> dict:"),
    ("any fee at or above the price accepted", 'if int(gl.message.value) != t["fee"]:', 'if int(gl.message.value) < t["fee"]:'),
    ("filing after the expiry", 'if ts >= t["expires_at"]:\n            return "this bounty has expired"', 'if False:\n            return "this bounty has expired"'),
    ("lateness judged on the clock", 'if ts >= t["expires_at"]:\n            return "this bounty has expired"', 'if s["t"] >= t["expires_at"]:\n            return "this bounty has expired"'),
    ("a filing that can no longer be judged burns its fee", TOO_LATE, "if False:"),
    ("a filing whose time ends at the clock is taken", TOO_LATE, 'if s["t"] > ts + FILING_TTL:'),
    ("a filing that can still be judged is refused", TOO_LATE, 'if s["t"] >= ts + FILING_TTL - 1:'),
    ("a transaction time that cannot be read raises in a call that takes GEN", BAD_TIME, "        us = self._us()"),
    ("filing does not retire old filings", '        me = gl.message.sender_address.as_hex\n        _retire(s)\n', '        me = gl.message.sender_address.as_hex\n'),
    ("judging does not retire old filings", '        pays = _advance(s, ts)\n        _retire(s)\n', '        pays = _advance(s, ts)\n'),
    ("digest not checked", DIGEST, "if False:"),
    ("digest length not checked", DIGEST, "if not isinstance(digest, str) or any(c not in HEX for c in digest):"),
    ("digest characters not checked", DIGEST, "if not isinstance(digest, str) or len(digest) != 64:"),
    ("two live filings per hunter", ONE_LIVE, "if False:"),
    ("a hunter whose filing ran out cannot file again", ONE_LIVE, 'if any(f["hunter"].lower() == me.lower() and f["status"] == "LIVE" for f in s["filings"]):'),
    ("no cap on live filings", 'if sum(1 for f in s["filings"] if f["status"] == "LIVE") >= MAX_LIVE:', "if False:"),
    ("old filings never lapse", '            f["status"] = "LAPSED"', "            pass"),
    ("filings lapse without the processing margin", 'if f["status"] == "LIVE" and s["t"] >= f["at"] + FILING_TTL + PROCESS_MARGIN:', 'if f["status"] == "LIVE" and s["t"] >= f["at"] + FILING_TTL:'),
    ("filings lapse one second late", 'if f["status"] == "LIVE" and s["t"] >= f["at"] + FILING_TTL + PROCESS_MARGIN:', 'if f["status"] == "LIVE" and s["t"] > f["at"] + FILING_TTL + PROCESS_MARGIN:'),
    ("room is made by dropping the first filing, live or not", 'drop = next(i for i, f in enumerate(s["filings"]) if f["status"] != "LIVE")', "drop = 0"),
    ("fee not counted as burned", "        self.burned = u256(int(self.burned) + fee)\n", ""),
    ("fee not counted on the bounty", '        s["burned"] += fee\n', ""),
    ("filing in any state", 'if s["state"] != "OPEN":\n            return "this bounty is " + s["state"] + "; filings', 'if False:\n            return "this bounty is " + s["state"] + "; filings'),
    ("a refused filing forgets what time decided", "            self._save(b, s, held, pays)\n            return self._refuse(problem)", "            return self._refuse(problem)"),
    ("a filing lives one second longer", LIVE, LIVE + " + 1"),
    ("a filing lives one second less", LIVE, 'return f["status"] == "LIVE" and f["at"] <= ts < f["at"] + FILING_TTL'),
    ("a judgement sent before its filing is taken", LIVE, 'return f["status"] == "LIVE" and ts <= f["at"] + FILING_TTL'),
    # --- the reveal
    ("anyone's filing can be judged", 'mine = [f for f in s["filings"] if f["hunter"].lower() == me.lower() and _live(f, ts)]', 'mine = [f for f in s["filings"] if _live(f, ts)]'),
    ("the reveal is not checked against the digest", '        mine = [f for f in mine if f["digest"] == sealed]\n', ""),
    ("the digest does not bind the filer's address", "{bounty_id}|{hunter.lower()}|{rule}", "{bounty_id}|{rule}"),
    ("the digest depends on the case of the address", "{bounty_id}|{hunter.lower()}|{rule}", "{bounty_id}|{hunter}|{rule}"),
    ("the digest does not bind the salt", '|{rule}|{height}|{salt}".encode', '|{rule}|{height}".encode'),
    ("salt form not checked", "if not isinstance(salt, str) or len(salt) != SALT_LEN or any(c not in HEX for c in salt):", "if False:"),
    ("rule not checked against the bounty", 'if not isinstance(rule, str) or rule not in CLAIM_RULES[t["claim_type"]]:', 'if not isinstance(rule, str) or rule not in ("P1", "M1"):'),
    ("height above 100", HEIGHT, 'if (rule == "P1" and not 0 <= height) or (rule == "M1" and height != 0):'),
    ("negative height", HEIGHT, 'if (rule == "P1" and not height <= MAX_HEIGHT) or (rule == "M1" and height != 0):'),
    ("M1 with a height", HEIGHT, 'if rule == "P1" and not 0 <= height <= MAX_HEIGHT:'),
    ("bool numbers accepted", "    if isinstance(v, bool) or not isinstance(v, int):", "    if not isinstance(v, int):"),
    # --- judging and winning
    ("the queue is the order of processing", 'return (f["us"], f["seq"])', 'return (f["seq"], f["us"])'),
    ("the queue is decided to the second only", 'return (f["us"], f["seq"])', 'return (f["at"], f["seq"])'),
    ("microseconds dropped from the time", " + delta.microseconds", ""),
    ("a later filing is judged while an earlier one leads", 'if s["state"] == "PROVISIONAL" and _rank(f) > (s["lead"]["us"], s["lead"]["seq"]):\n            raise', "if False:\n            raise"),
    ("judging on a finished bounty", 'if s["state"] not in ("OPEN", "PROVISIONAL"):\n            raise gl.vm.UserError("this bounty is " + s["state"])\n        if not isinstance(rule', 'if False:\n            raise gl.vm.UserError("this bounty is " + s["state"])\n        if not isinstance(rule'),
    ("NO_PAY leaves the filing live", '            f["status"] = "NO_PAY"', "            pass"),
    ("unlimited soft tries", '            if f["tries"] <= 0:\n                f["status"] = "SPENT"', "            if False:\n                pass"),
    ("the revealed claim is not recorded on the filing", '        f["rule"], f["height"] = rule, height\n', ""),
    ("the window ignores older filings", 's["window_end"] = max(waits) if waits else s["t"]', 's["window_end"] = s["t"]'),
    ("the window waits only for the first older filing", 's["window_end"] = max(waits) if waits else s["t"]', 's["window_end"] = min(waits) if waits else s["t"]'),
    ("the window has no processing margin", 'waits = [g["at"] + FILING_TTL + PROCESS_MARGIN for g', 'waits = [g["at"] + FILING_TTL for g'),
    ("judged filings hold up the win", WAITS, "if _rank(g) < first]"),
    ("younger filings hold up the win", WAITS, 'if _rank(g) != first and g["status"] == "LIVE"]'),
    ("an earlier paying filing does not take the lead", '            s["lead"] = lead\n            s["state"] = "PROVISIONAL"', '            s["lead"] = s["lead"] or lead\n            s["state"] = "PROVISIONAL"'),
    ("the window is not shortened when earlier filings are judged", '        if s["state"] == "PROVISIONAL":\n            # The lead waits', '        if result.get("lead"):\n            # The lead waits'),
    ("the outranked filing keeps its status", '                        g["status"] = "OUTRANKED"', "                        pass"),
    ("won before the window ends", 'if s["state"] == "PROVISIONAL" and s["t"] >= s["window_end"]:', 'if s["state"] == "PROVISIONAL":'),
    ("won one second after the window ends", 'if s["state"] == "PROVISIONAL" and s["t"] >= s["window_end"]:', 'if s["state"] == "PROVISIONAL" and s["t"] > s["window_end"]:'),
    ("the winner is credited half the pot", 'return [(s["lead"]["hunter"], pot)]', 'return [(s["lead"]["hunter"], pot // 2)]'),
    ("M1 counts are stored", 'lead["agreed"] = {"outcome": kind, "top_miner": o["miner"]}', 'lead["agreed"] = {"outcome": kind, "top_miner": o["miner"]}\n                lead["leader_reading"] = {}'),
    # --- reclaim, withdraw, views, clock
    ("anyone can reclaim", 'if gl.message.sender_address.as_hex.lower() != b.poster.lower():\n            raise gl.vm.UserError("only the poster can reclaim")', 'if False:\n            raise gl.vm.UserError("only the poster can reclaim")'),
    ("reclaim at the expiry", 'if s["t"] < _settle_time(t):', 'if s["t"] < t["expires_at"]:'),
    ("settle time without the processing margin", 'return t["expires_at"] + FILING_TTL + PROCESS_MARGIN', 'return t["expires_at"] + FILING_TTL'),
    ("reclaim one second early", 'return t["expires_at"] + FILING_TTL + PROCESS_MARGIN', 'return t["expires_at"] + FILING_TTL + PROCESS_MARGIN - 1'),
    ("reclaim on a finished bounty", 'if s["state"] != "OPEN":\n            raise gl.vm.UserError("this bounty is " + s["state"] + "; only', 'if False:\n            raise gl.vm.UserError("this bounty is " + s["state"] + "; only'),
    ("withdraw more than is credited", "if not 0 < amount <= have:", "if not 0 < amount:"),
    ("withdraw takes text for a number", '        amount = _as_int(amount, "amount")\n', ""),
    ("withdraw keeps the credit", "        self.claims[k] = u256(have - amount)\n        self.claims_total", "        self.claims_total"),
    ("withdraw keeps the credited total", "        self.claims_total = u256(int(self.claims_total) - amount)\n", ""),
    ("views miss a finished window", 'if s["state"] == "PROVISIONAL" and at >= s["window_end"]:\n        return "WON"', 'if False:\n        return "WON"'),
    ("views miss the expiry", 'if s["state"] == "OPEN" and at >= t["expires_at"]:', "if False:"),
    ("views go back before the bounty's clock", '    at = max(at, s["t"])\n', ""),
    ("burned fees left out of the total", '"accounted_for": _s(locked + credited + burned)', '"accounted_for": _s(locked + credited)'),
    ("the clock runs backwards", 's["t"] = max(s["t"], now)', 's["t"] = now'),
    ("the pot is not locked", "        self.locked = u256(int(self.locked) + value)\n", ""),
    ("paid pots stay locked", "        self.locked = u256(int(self.locked) - out)\n", ""),
    ("the newest list is not capped", "MAX_LATEST = 20", "MAX_LATEST = 500"),
    ("a list of nothing can be asked for", 'limit, at = max(1, min(_as_int(limit, "limit"), MAX_LATEST)), _as_int(at, "at")', 'limit, at = min(_as_int(limit, "limit"), MAX_LATEST), _as_int(at, "at")'),
    ("the list per address is not capped", "json.dumps(ids[-MAX_PER_ADDRESS:])", "json.dumps(ids)"),
    ("the log is not capped", '    del s["log"][:-MAX_LOG]\n', ""),
]


def run_one(job) -> tuple:
    i, name, path, env = job
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/direct/test_bounties.py", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=ROOT, env={**env, "LCB_CONTRACT": str(path)}, capture_output=True, text=True)
    return i, name, r.returncode != 0


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor

    only = {int(a) for a in sys.argv[1:]}
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    tmp = Path(tempfile.mkdtemp(prefix="lcb-mutants-"))
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
    with ThreadPoolExecutor(max_workers=int(os.environ.get("MUTATE_JOBS", "4"))) as pool:
        for i, name, ok in pool.map(run_one, jobs):
            caught += ok
            if not ok:
                missed.append(i)
            print(f"{'caught ' if ok else 'MISSED '} {i:3d} {name}", flush=True)
    print(f"\n{caught} of {len(jobs)} mutants caught" + (f"; missed: {missed}" if missed else ""))
    return 0 if caught == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())

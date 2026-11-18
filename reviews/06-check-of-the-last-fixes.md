# Review 6: check of the changes made after reviews 4 and 5

18 November 2026. A separate reviewer session (Claude), started fresh with a written brief and read access to the repository. It was asked to check only the changes made after reviews 4 and 5: the rewritten number-ambiguity rule, the catch-all filter, the mining rule's row checks, the handling of a model answer that lacks a field, the mining prompt, the contract's description and the new tests. It worked in its own scratch copy and changed nothing in the repository.

Its report is below, word for word. "Item 4" and the other item numbers are those of its brief (1 `_spaced`, 2 `_clear`, 3 `_quote_ok`, 4 `_catch_all` and `_miner_name`, 5 `_interpret_m1`, 6 `_read`, 7 the M1 prompt, 8 the description, 9 the tests). Where the report names two real mining pools in one test input, the names are replaced here by `[a real pool name]`: this repository names no real project. What was done about each point follows the report.

## The report

VERDICT: fix first. One item in the contract code (item 4, already sent as interim): a shortened zero or burn address is accepted as a miner and M1 pays. The fix is three lines. Everything else is optional or wording.

The suite passes 384/384 on an unmodified scratch copy. The original files are untouched (checked with cmp), and no transactions were sent.

**1. `_spaced`: correct, but it refuses some honest rows.**
- **Index safety:** OK for every position `_places` can return. I ran i=0, i=1, i=2 with the digit run reaching the start of the text, and numbers at the end of the text.
- **Ambiguous numbers:** every space-grouped form I tried is refused: '2', '000' and '000.00000000' in '2 000 000.00000000'; '345' and '678' in '12 345 678'; '567.5' in '1 234 567.5'; also after '(', '$', '-' and 'amount:'.
- **Still accepted, low impact:**
  - '0.123' from 'Founders allocation 0.123 456 78 EXM' gives PAYS_P1 with amount 0.123.
  - '2' from '2·000·000' (U+00B7) or with U+2063 between the groups pays. Only the pinned site can print that.
- **Honest rows refused (safe direction):**
  - '0 500.00000000 EXM Founders exm1qfounders01' and '0 750 EXM Founders' give NO_PAY. Output index 0 can never be the first group of a number.
  - 'Deepvein Pool 840 100.0%', '... 840 100.00%' and 'Total 840 100.00%' are refused; '840 100%' is not.
  - 'Deepvein Pool 840 512 MH/s 84.0%', 'Deepvein Pool 2 840 84.0%', '08:15:42 500.00000000 EXM ...' and 'Founders exm1q... 750 144 confirmations' are refused.
- **Smallest fixes:** in rule A, skip an optional '.digits' before testing for '%'. In rule B, return False when the run before is exactly '0'. With both, the suite still passes and the index-0 and 100.0% rows pay.

**2. `_clear`: OK.** Its use on the total is not protected by any test (see 9).

**3. `_quote_ok`: OK.**
- **Index arithmetic:** quote and line are both folded before searching, so `at + i` is in one domain. Confirmed with ß, ẞ, İ, zero-width characters, NBSP and thin spaces.
- **Cut quotes:** a quote cut at a space from either side is refused ('... allocation 2' from '2 000 000'; '500.00 EXM to founders' from '1 500.00').
- **One note:** it is an "any" over places. 'Premine 1 500.00 EXM to founders (500.00 locked)' pays 500, because the second 500.00 is clear.

**4. `_catch_all` and `_miner_name`: one fix first, one minor hole.**
- **FIX FIRST:** page row '0x0000…0000 840 84.00%' with answer `m1(name="0x0000…0000")` gives PAYS_M1, WON, and `run_validator()` is True. The same happens for '0x0000...0000' and '0x0000…dEaD'. Only the full 42-character form is refused.
  - Fix in `_miner_name`: build `core` from the alphanumeric characters of the name and apply the existing rule to `core`. With it the three inputs give NO_PAY and the suite passes.
  - A labelled form, '0x000…(40 zeros) (Zero Address)', still pays after that fix. Adding "zero", "burn", "burned" to AGGREGATE_WORDS closes it (ran, suite passes).
- **Minor:** `replace("n/a", "na")` glues words together. 'Hidden/All', 'Chain/All' and 'Main/Autres' pass `_miner_name`. Fix: drop the replace and add `or _stands(text, "n/a")` to the first test. Then those three are refused and '[a real pool name]/[a real pool name]' still passes.
- **Stems anywhere in a word:** OK. The honest cost is small: a name or address with a listed word between digits is refused ('exm1q9na4example' gives None), which should be rare.

**5. `_interpret_m1`: OK.**
- **Documented rows pay:** 'exm1qa7example0000000000000000000000001 840 84.0%' with 'last 1,000 blocks' gives PAYS_M1, on MINING and on the text of the live page. I typed the live page text by hand from mining.html; I did not render it.
- **Refused as intended:** a catch-all row, a name from one row with the count of another, part of a catch-all row's name, '1 840', and 'Deepvein Pool 840 84.0% N/A' (whole-line scope).
- **Pays only on a wrong model reading that code cannot see:**
  - Total copied from the count: page 'last 2,000 blocks / Deepvein Pool 600 30.00%', answer top '600' total '600', min_blocks 500, gives PAYS_M1. A possible guard, not run: when total equals top, require the number clear at two places.
  - A header read as the miner: on MINING, answer name 'Mining distribution', top '1,000', total '1,000' gives PAYS_M1.
  - Both need a majority of validators to make the same mistake. Neither is a blocker.

**6. `_read`: OK.** A missing key gives UNREADABLE with 2 tries left and the filing stays LIVE, for P1 and M1. Null values give NO_PAY. An extra key is ignored.

**7. `_prompt_m1`: OK, nothing false.** The examples "840" and "1,000" are the true values of the test and live pages, so the live run cannot tell reading from echoing. Use other example numbers.

**8. FALSE OR OVERSTATED SENTENCES**
- "refuses a row whose line has a catch-all word ("unknown", "others") or whose name is a zero address." False for the shortened and labelled forms (item 4). The `_miner_name` docstring, "that is a zero or burn address", has the same problem.
- "A number that could be one group of a longer number written with spaces ... is refused as ambiguous, so a true allocation printed that way cannot be claimed." Understated. It also hits block counts under M1, and numbers not written with spaces at all (the rows in item 1).
- "Amounts and block counts must be printed with a dot for decimals and commas, or nothing, between thousands." Missing caveat: an amount with exactly three decimals and no comma is refused ('2000000.125' gives NO_PAY).
- "A sealed filing shows no rule and no block". The rule is implied by the claim type for three of the four types; only FAIR_LAUNCH hides it.
- "the page unreadable three times". It is three judgements that end unreadable, on a wrong page, or with a malformed model answer.
- "A filing that arrives when the clock is already past its 30 minutes is refused". The code refuses from exactly 30 minutes (>=). Trivial.
- Step 2, "the sha256 of its rule, block number and a random salt". It also covers the bounty id and the filer's address. Harmless.
- Step 3, P1: the 12 to 200 character limit on the quoted line is not mentioned. A true allocation on a shorter page line cannot be claimed.
- I found nothing false in "Time rules", step 4, or the other "What sealing does" and "Stated plainly" sentences. I could not check the claims about the network (timestamp precision, redirects, GEN sent with a non-payable call).

**9. Tests: 384 pass; the new tests assert what their names say, with these exceptions.**
- **Vacuous case:** the M1_CASES row 'last 10 800 blocks' with total '800' is NO_PAY only because 800 is below the default min_blocks of 1,000. Changing the total check from `_clear` to `_stands` passes all 384. With `post_m1(min_blocks=500)` the real code gives NO_PAY and that mutant gives PAYS_M1. Add that test.
- **Unprotected guard:** removing `len(text) >= j + 4` from rule A passes all 384. Add ("2 00", "2") to the `no` list in `test_spaced`.
- **The other 17 hand mutations** of the changed lines were all caught.
- **`test_known_limit_on_a_quiet_bounty...`:** in direct mode nothing is processed late. It is an ordinary filing whose 30 minutes ran out, so it shows the burned fee, not the lateness.
- **`test_payable_calls_never_raise...`:** the comment "(none is ...)" is wrong, since "" is a valid mining_url. `paid -= 0` does nothing. The assertions still hold.
- **Missing:** tests for a shortened zero address, 'N 100.0%', index 0 before a 100 to 999 amount, and a ß/İ line.

## What was done

All of it, before the contract was deployed again for the live runs on record.

| Point | Done |
|---|---|
| 4, fix first: a shortened zero or burn address paid | `_miner_name` applies the rule to the letters and digits of the name; "zero", "burn", "burned", "burnt" are catch-all words; tests for the shortened and the labelled forms |
| 4, minor: a slash glued two words into one | the replace is gone; "n/a" is looked for as a token of its own |
| 1: '0.123' out of '0.123 456 78' paid | a number that ends in exactly three decimals with a digit after one space is ambiguous; so is a group of three digits right after decimals ('456') |
| 1: a middle dot or an invisible separator between groups | the middle dot joins digits; the invisible separators are removed when a page is folded |
| 1: honest rows refused | output index 0 (a run of one or two digits that starts with 0) is no group; a percentage with decimals is no group; a time of day before an amount is no group. A count or an index right next to another short number stays refused, and the description now says so with those examples |
| 3: clear at one place, not at another | the amount must be clear at every place it has on the page line, however much of the line is quoted |
| 5: a count copied into both fields | where the total is the same number as the miner's count, it must be printed twice |
| 5: a header read as the miner | not closed in code: it needs a majority of validators' models to make the same wrong reading. The limits say that which row is the top miner is the model's reading |
| 7: prompt examples were the test pages' own values | other numbers |
| 8: eight sentences | each rewritten |
| 9: tests | the vacuous case, the unprotected guard and the missing tests were added, each with a deliberate break in `tools/mutate_bounties.py`; the misnamed test was renamed; the wrong comment was corrected |

The reviewer then checked these changes twice more before the deployment. Both answers are recorded below.

## The re-check, word for word

The reviewer was given the diff of the changes made from its report and asked whether each is correct, whether an honest row that paid before is now refused, whether anything refused now pays, and whether the rewritten sentences are true.

VERDICT: fix first, for one narrow item (A). B to E are optional and can wait.

Checked by running: 401/401 pass on a fresh copy, and the diff file is exactly the change from my copy to the contract now. I ran my earlier row lists and about 76,000 random lines through the old and new `_places`/`_spaced`. There was no exception at any text edge (`_more_or_percent` included), and every old/new difference is explained by one of your rules 2 to 5. Both live rows still pay: "0 2,000,000.00000000 EXM Founders allocation address exm1q..." gives PAYS_P1, and "exm1qa7example0000000000000000000000001 840 84.0%" with "last 1,000 blocks" gives PAYS_M1.

**A. Fix first: M1 still pays on a zero or burn address when the row has a word next to it.**
- Inputs, all PAYS_M1 through `judge()` on the contract now (MINING with "Deepvein Pool" replaced):
  - row "Address 0x0000000000000000000000000000000000000000 840 84.00%", name as printed;
  - row "Miner 0x0000…0000 840 84.00%", name as printed;
  - row "Dead Address 0x0000…dEaD 840 84.00%", name as printed;
  - row "Validator 0x0000…0000 840 84.00%", name "Validator" (the model gives only the label).
- Cause: the rule tests the whole name, not the address inside it, and the row line is never tested for an address.
- Smallest fix (tested, 401/401, all four give NO_PAY, a row with a "0" cell and the live row still pay): add a helper and one clause in `_catch_all`:
  - `core = "".join(c for c in token if c.isalnum())`; null if `len(core) > 2 and core.startswith("0x") and core[2:].strip("0") in ("", "dead")`;
  - `or any(_null_address(t) for t in text.split(" "))`.
- This is narrow: it needs an explorer that prints a label beside the address. It is the same hole as the first fix-first.

**B. Change 6 depends on how much is quoted.**
- "Premine 1 500.00 EXM to founders (500.00 locked)" with line "EXM to founders (500.00 locked)" still gives PAYS_P1 500. Only the whole-line quote is refused.
- An honest line now splits the same way: "Founders 750 EXM exm1qfounders01 750 123 confirmations" gives NO_PAY quoted whole and PAYS_P1 750 quoted as "Founders 750 EXM exm1qfounders01". Two validators that quote differently disagree.
- Smallest fix (tested, 401/401): test every place of the amount on the page line, not only inside the quote: `any(all(not _spaced(line, p, a) for p in _places(line, a)) for line in lines if _stands(line, q))`.
- The catch: that honest line is then refused whatever is quoted, so it needs a line in the docstring.

**C. Change 3, the ':' rule, lets one refused case pay.**
- "Output 1:1 500.00 EXM to founders exm1qfounders01" with amount "500.00" was NO_PAY and is now PAYS_P1 500. The number is 1 500.00.
- Smallest fix (tested): count ':' only before a run of exactly two digits, as in a time. "0:12 500.00" would still pass.

**D. Change 4 covers only the head of grouped decimals (this paid before too).**
- "Founders allocation 0.123 456 78 EXM to exm1qfounders01" with amount "456" gives PAYS_P1 456, and with "78" gives PAYS_P1 78.
- Fix for "456" (tested): in rule B, a three-digit run right after ".digit" is a group. "78" still pays; it needs the model to give a fragment.

**E. Docstring sentences that are not true or lack a caveat.**
- "An amount with exactly three decimals and no comma ('2000000.125') is refused". Not when the whole part is 0: "0.125" gives PAYS_P1 0.125. Add "and a whole part other than 0".
- The list of refused forms lacks rule 4. "Founders exm1qfounders01 0.125 3 confirmations" paid before and is NO_PAY now. Add "an amount with exactly three decimals right before another number".
- M1 does not say that a total equal to the miner's count must be printed twice. "Miner Blocks Share / Deepvein Pool 840 100%" with top 840 and total 840 paid before and is NO_PAY now.
- "a zero or burn address": the code knows only the all-zero address and 0x…dead. "0xdead000000000000000042069420694206942069" and "1111111111111111111114oLvT2" pass. Say "the 0x…dead address".
- If B is not fixed: "however much of the page line is quoted" in the `_quote_ok` docstring is not true for a line that has the amount at two places.
- Not stated, rare: "·" glued between two numbers now joins them. "Deepvein Pool·840·84.00%" paid before and is NO_PAY now; with spaces around the dots it still pays.

Everything else in changes 1 to 10 is correct as far as I ran it, and I found nothing false in the other rewritten docstring sentences.

**Done:** A to D were applied exactly as the reviewer's own tested patch; the sentences under E were rewritten; each point has a test and a deliberate break.

## The last confirmation, word for word

The reviewer was asked to confirm that the remaining difference from its tested copy is descriptions only, and to read each changed sentence against the code.

VERDICT: fix first, but words only. One sentence in step 3 is false for two inputs, and two helper docstrings carry the same gap. No code change is needed to deploy.

1. Confirmed: `/tmp/p/since_recheck.diff` changes docstrings only. With docstrings blanked, the two files parse to the same code. The suite passes 412/412 on a fresh copy.

2. Sentences that lack a needed caveat, with corrected wording:

- **Step 3, M1:** "refuses a row whose line has a catch-all word ("unknown", "others", "burn") or the all-zero or 0x...dead address, in full or shortened ("0x0000...0000"); other burn addresses are not known to it."
  - The address is only recognised written with 0x and set off by spaces. Run through `judge()` on the contract now: row "Miner:0x0000…0000 840 84.00%" gives PAYS_M1, and row "Validator 0000000000000000000000000000000000000000 840 84.00%" (no 0x) gives PAYS_M1.
  - Corrected: "... or, as a word of its own and written with 0x, the all-zero or ...dead address, in full or shortened ("0x0000...0000"); the same address without 0x or glued to a label ("Miner:0x0000...0000"), and other burn addresses, are not known to it."
- **`_null_address`:** "The all-zero address or the 0x...dead address, in full or shortened".
  - Corrected: "The all-zero or ...dead address written with 0x, in full or shortened ('0x0000...0000', '0x0000…dead')."
- **`_catch_all`:** "..., or the zero or 0x...dead address."
  - Corrected: "..., or, between spaces and written with 0x, the all-zero or ...dead address."
- **Optional, "Stated plainly":** "A middle dot between two numbers joins them like a comma." It joins only without spaces, and the joined number is not read at all: "Deepvein Pool · 840 · 84.00%" pays, "Deepvein Pool·840·84.00%" and an amount "2·000·000" do not.
  - Corrected: "A middle dot directly between two digits joins them into one number, which is then not read."

Everything else you listed is true against the code, checked by running:
- the twice-printed total (once gives NO_PAY, twice gives PAYS_M1);
- three decimals with a whole part other than 0 ("12.125" NO_PAY, "0.125" and "1,250.125" pay);
- the four ambiguous forms;
- "for rule P1 it is enough that the page line has the amount once in such a place" (the tail quote of the "Premine 1 500.00 ... (500.00 locked)" line now gives NO_PAY);
- the docstrings of `_spaced`, `_quote_ok` and `_miner_name`.

Both live rows still pay.

One code case that pays wrongly, as asked: the glued form above ("Miner:0x0000…0000 840 84.00%" gives PAYS_M1 on a zero-address row). A one-line fix in `_catch_all`, tested in scratch (412/412, glued form gives NO_PAY, live row still pays): split the text on every character that is not a letter, digit, '.' or '…' instead of on spaces. The form without 0x still pays after that. If you take the fix, drop "or glued to a label" from the corrected sentence.

**Done:** the one-line fix was taken as the reviewer tested it, and the corrected sentences were used. With descriptions blanked, the contract that was then deployed parses to the same code as the reviewer's last tested copy. A zero address written without 0x, and burn addresses other than the 0x...dead one, are still not known to the filter; the contract's description and the README say so, and a test case marked as a known limit holds it.

## Where this leaves the contract

The reviewer's verdict on the code it tested last: no code change needed to deploy. What it could not check by running are the statements about the network (timestamp precision, redirects, GEN sent with a call that takes none); those are measured in [`../examples/live/network-probes-studio.json`](../examples/live/network-probes-studio.json).


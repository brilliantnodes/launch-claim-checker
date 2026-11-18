# Reviews of the claim bounties

The bounties contract, its tests, the site and these documents were built by an AI session (Claude, Anthropic) working for Brilliant Nodes. Before each step forward the work went to a **separate reviewer session**: another Claude session, started fresh with a written brief and read access to the repository, that had not seen the work being done and was asked to find what was wrong. A reviewer could run the tests and write its own. No reviewer changed the repository.

This file records each review: what it was asked, its verdict, what it found and what changed. Reviews 1 to 5 and review 7 are recorded here by the builder from the reviewers' reports; those reports were not kept word for word. Review 6 is kept word for word in [`06-check-of-the-last-fixes.md`](06-check-of-the-last-fixes.md). The scripts and tests the reviewers wrote for themselves are in [`probes/`](probes/), as they left them, except for the two changes noted at the end of this file.

Reviews 1 to 6 were done on 17 November 2026 (UTC), before the deployment of 22:25 UTC that the live runs on record used; review 6 ended after midnight in Dubai (UTC+4) and carries that date. Review 7 was done after those runs, on the published repository.

| # | What was reviewed | Verdict |
|---|---|---|
| 1 | The design, before any code | not ready as written, 5 blockers |
| 2 | The first build of the contract and its tests | not ready, 3 blockers |
| 3 | The second build | ready with changes, no blockers |
| 4 | The contract, before submission | ready with changes, no blockers |
| 5 | The repository, the site and the video, before submission | ready with changes |
| 6 | The changes made after reviews 4 and 5 | fix first; fixed and checked twice more; at the end no code change was needed to deploy |
| 7 | The published repository, the site and the video, after the live runs | ready with changes; every figure and every transaction link checked out |

## 1. The design

Asked: would this design pay the wrong person, lose money, or be gamed? Verdict: not ready as written, 5 blockers.

Among the changes:

- Hunters no longer send a page address. The poster pins the pages when posting.
- Claims are no longer free. Every filing pays a fee, and the fee is burned, so nobody gains from a failed claim: not the poster, not the contract's owner (there is none).
- Whether a claim was made in time is decided by the transaction's own time, so nobody can push a pending claim past the expiry by getting another transaction processed first.
- Validators must agree on the amount exactly, and the leader's line must stand on each accepting validator's own copy of the page.

## 2. The first build

Asked: read the contract and the tests; try to break the money, the queue and the reading. Verdict: not ready, 3 blockers.

1. The queue was the order of processing, so a copier whose filing was processed first could win. Fix: filings became sealed (only a sha256 goes on chain, bound to the filer's address) and rank by the time their transaction was sent.
2. Rule M1 stored block counts that no validator had checked. Fix: only the agreed miner name is stored.
3. Rule M1 paid on placeholder rows ("N/A (solo)", "37 others"). Fix: a word list for catch-all rows, stated as a filter and not a guarantee.

Smaller points were fixed as well, among them: 30 minutes to reveal and 60 to be processed; a filing that can no longer be judged is refused and refunded, so that no fee is burned for nothing; the P1 prompt no longer names the block, and the block number must be printed on the page; pinned addresses are made of an allow-list of characters.

## 3. The second build

Asked: the same, on the fixed build, and read every sentence of the contract's description against the code. Verdict: ready with changes, no blockers. The reviewer ran its own 40-seed random walk and found no way to pay twice, pay the wrong address, trap a pot or lock a bounty. Its tests: [`probes/code-review-2/`](probes/code-review-2/).

What changed:

- What sealing does not do is stated: a reveal is public even if the call fails, so if the filer's own judgement fails, someone else can file the same claim; a filing processed after a win is refused even if it was sent earlier.
- Amounts written "2 000 000" or "2'000'000" could pay as "2". Fixed.
- A miner's name and its count could come from different rows. Now they must stand on the same line.
- A model that does not answer, or answers out of form, costs one try and not the filing.
- A lead wins as soon as no filing sent before it is still waiting; the wait gets shorter when earlier filings are judged and never grows.
- More catch-all words. A transaction time that cannot be read no longer raises in `file_claim`. Two extra allocations in one block: the prompt says to copy the first one printed.
- Every sentence the reviewer listed as false or overstated was rewritten.

## 4. The contract, before submission

Asked: a last full review of the contract, its description and its tests. Verdict: ready with changes, no blockers. Its tests: [`probes/final-contract-review/`](probes/final-contract-review/).

1. Whether a number is ambiguous was decided on the part of the line the model quoted, so a quote cut at a space could make "2" out of "2 000 000". Now it is decided on the page's own line, however much of it is quoted.
2. Block counts under M1 had no such rule ("800" out of "10 800"). Now they have the same one.
3. The catch-all filter looked at the name the model returned, not at the row. Now it reads the whole row.
4. Under M1 there is one possible claim, so a filing made blind and kept live outranks a later hunter whose reveal shows that the page pays. This cannot be fixed inside this design; it is stated in the contract, the README and on the site, and a test holds it as a known limit.
5. Sentences in the contract's description were corrected.

## 5. The repository, the site and the video, before submission

Asked: read everything a reviewer of the submission would see, follow every link, rerun what can be rerun, and list every statement that is wrong or not backed. Verdict: ready with changes. Its scripts: [`probes/final-package-review/`](probes/final-package-review/).

Twelve statements were wrong or not backed. What was done:

1. "The site was tested against the live contract", with no transaction to show. The page is now driven in a headless browser against the deployed contract and every transaction is recorded: `tools/site_flow.py`, `examples/live/bounties-site-studio.json`.
2. A test command that was said to run 62 tests ran all of them. The command now names the checker's test file.
3. "Ranked to the microsecond" is true on Studio only. Bradbury stamps whole seconds; the documents say so.
4. Validator counts were not stated. They are now, per network, and each transaction's votes are in the records.
5. "Both networks with full live runs", while the Bradbury run had three cases. The Bradbury run now has the same seven cases as Studio.
6. "Measured on Studio", with no transactions. The measurements were redone with a probe contract and recorded with their transactions: `tools/probes/`, `examples/live/network-probes-studio.json`.
7. "Independent reviews", with nothing to show who reviewed. This file.
8. "Every limit is stated in the contract, the README and on the site" was too much. The README now says where each limit is stated.
9. The wording of the number-format limit was wrong. Rewritten.
10. One exclusion listed in the mutation tool's header was not true any more. A test and a mutant now cover it.
11. The video gave 47 and 16 where the README gave 46 and 15. The video was made again from the new records.
12. Real pool names in test data. Replaced by invented ones.

Smaller points, all done: the digest's exact inputs are in the README; the interface table matches the code; the verifiers read method and arguments from the chain instead of trusting the record; `npm ci` is in the instructions; the two Python environments are named; the site asks for 11 minutes where the contract needs 10 from the transaction's own time; tool names and comments left over from other projects were corrected; record summaries no longer read as if one transaction had failed.

The three weakest points it named: nobody but the builder has used a bounty; the reviews were not evidenced; who would post a bounty? The second is answered by this file. The other two are answered as far as they can be: the page was used against the live contract with every transaction recorded, the README says who would post a bounty, and it says plainly that no outside party has yet.

## 6. The changes made after reviews 4 and 5

Asked: check only those changes for mistakes, new holes and false statements. Verdict: fix first; fixed and checked twice more; at the end no code change was needed to deploy. The report, word for word: [`06-check-of-the-last-fixes.md`](06-check-of-the-last-fixes.md).

The first answer was "fix first": a zero address printed in its shortened form (`0x0000…0000`) was accepted as a miner, so rule M1 could pay on it. It also listed honest rows that were refused (an output index 0 before an amount, a count before "100.00%"), two ways a wrong model reading could pay (a count copied into both fields), eight sentences of the description that were false or lacked a caveat, and tests that did not protect what their names said.

All of it was fixed, and the reviewer checked the fixes twice more. The second answer found the same zero-address hole where the row has a label next to the address, and three more cases that paid and should not: one that a fix had let through, two that the fixes had not reached. Its own tested patch was applied as it stood. The third answer was "words only", with one further one-line fix, which was taken as tested. The contract that was deployed for the live runs on record parses, with descriptions blanked, to the same code as the reviewer's last tested copy.

What stays open is stated as a limit: a zero address written without `0x`, and burn addresses other than the `0x…dead` one, are not known to the filter; a majority of validators' models taking a header for a miner cannot be seen by code.

## 7. The published repository, after the live runs

Asked: read everything a GenLayer reviewer would see, rerun what can be rerun, and list every statement that is wrong, stale, overstated or not backed. Verdict: ready with changes.

Confirmed by running: both test suites and the GenVM v0.6 run; the mutation list against the contract and the log of its last full run; both verifiers with no mismatch; all 63 transaction links in the README and MILESTONE.md against the records; the ten transactions of the page run and the eight network measurements against the chain; the binomial figures; the live site on both networks.

Changed because of it, in the documents only (the deployed contract was not touched):

- The two-minute walkthrough left out the **Get test GEN** click.
- "Every wei accounted for" said more than `totals()` covers; it now says what it covers.
- The README now says which limits are stated only there, that a zero address without `0x` is not known to the filter, and that the example pages were written for these tests and state the allocation in a sentence.
- The front-end section claimed tests of the page that have no record; it now says which have one.
- "8 judgements where a model reads the page": in one of them the page does not exist and no model runs. The judgement times are now given both ways.
- The video said "independent reviews". It now says who reviewed. The README and MILESTONE.md say that no person outside Brilliant Nodes and no other model has reviewed the work.
- This file: the dates, the wording of review 6's second answer, the note on the probes, and the reviewer's last tested copy of the contract, which is now in [`probes/check-of-the-last-fixes/`](probes/check-of-the-last-fixes/).
- Smaller points: the digest's full inputs in MILESTONE.md; "the digest of every filing that was judged"; install lines before the test commands; the milestone pinned to a branch.

Its three weakest points: the live runs read only our own test pages; the reviews are the builder's own; a team that pins its own explorer proves nothing with a bounty. All three are now said plainly where the README makes the claim.

## The reviewers' probes

[`probes/`](probes/) holds the tests and scripts three of the reviewers wrote for their own use, and the copy of the contract that review 6 tested last (`probes/check-of-the-last-fixes/contract_as_last_tested.py`; with descriptions blanked it parses to the same code as `contracts/launch_claim_bounties.py`, which `probes/check-of-the-last-fixes/same_code.py` shows). They are scratch work, written against the build of that moment and with the paths of the machine they ran on; they are kept as a record and are not part of the test suite. Two files that were built around real pool names were left out, and in one list of test labels two real pool names were replaced by invented ones: this repository names no real project.

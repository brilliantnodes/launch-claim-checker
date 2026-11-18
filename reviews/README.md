# Reviews of the claim bounties

The bounties contract, its tests, the site and these documents were built by an AI session (Claude, Anthropic) working for Brilliant Nodes. Before each step forward the work went to a **separate reviewer session**: another Claude session, started fresh with a written brief and read access to the repository, that had not seen the work being done and was asked to find what was wrong. A reviewer could run the tests and write its own. No reviewer changed the repository.

This file records each review: what it was asked, its verdict, what it found and what changed. Reviews 1 to 5 are recorded here by the builder from the reviewers' reports; the reports themselves were not kept word for word. Review 6 is kept word for word in [`06-check-of-the-last-fixes.md`](06-check-of-the-last-fixes.md). The scripts and tests the reviewers wrote for themselves are in [`probes/`](probes/), as they left them.

All reviews are of 17 and 18 November 2026.

| # | What was reviewed | Verdict |
|---|---|---|
| 1 | The design, before any code | not ready as written, 5 blockers |
| 2 | The first build of the contract and its tests | not ready, 3 blockers |
| 3 | The second build | ready with changes, no blockers |
| 4 | The contract, before submission | ready with changes, no blockers |
| 5 | The repository, the site and the video, before submission | ready with changes |
| 6 | The changes made after reviews 4 and 5 | fix first; fixed and checked twice more; at the end no code change was needed to deploy |

## 1. The design

Asked: would this design pay the wrong person, lose money, or be gamed? Verdict: not ready as written.

What changed:

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

All of it was fixed, and the reviewer checked the fixes twice more. The second answer found the same zero-address hole where the row has a label next to the address, and three places where a fix let a refused case through; its own tested patch was applied as it stood. The third answer was "words only", with one further one-line fix, which was taken as tested. The contract that was deployed for the live runs on record parses, with descriptions blanked, to the same code as the reviewer's last tested copy.

What stays open is stated as a limit: a zero address written without `0x`, and burn addresses other than the `0x…dead` one, are not known to the filter; a majority of validators' models taking a header for a miner cannot be seen by code.

## The reviewers' probes

[`probes/`](probes/) holds the tests and scripts three of the reviewers wrote for their own use. They are scratch work, written against the build of that moment and with the paths of the machine they ran on; they are kept as a record and are not part of the test suite. Two files that were built around real pool names were left out, and in one list of test labels two real pool names were replaced by invented ones: this repository names no real project.

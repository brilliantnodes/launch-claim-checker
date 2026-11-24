# Reviews of Launch Claim Checker v2 (two explorers, a bond and a challenge)

Contract [`contracts/launch_claim_checker_v2.py`](../../contracts/launch_claim_checker_v2.py), its tests, the site page and these documents were built by an AI session (Claude, Anthropic) working for Brilliant Nodes. As for the claim bounties ([`reviews/README.md`](../README.md)), the work goes to a **separate reviewer session** before each step forward: another Claude session, started fresh with a written brief, that has not seen the work being done and is asked to find what is wrong. No person outside Brilliant Nodes and no other model has reviewed it.

| # | What was reviewed | Verdict |
|---|---|---|
| 1 | The design (first version), before any code | not ready, 6 blockers |
| 2a | The first build: contract, money and tests | not ready, 3 blockers |
| 2b | The first build: every claim in the write-up, the article, the video and the page, against the code, the records and the chain | ready with changes, 2 must-fix |

## 1. The design, first version (23 November 2026)

The reviewer read the first design, the accepted checker contract, the bounties contract and its reviews, and the GenLayer SDK source for GenVM v0.2 and v0.6. Asked: would this design pay the wrong person, lose money, or be gamed? Verdict: **not ready, six blockers**, all fixable. Recorded here by the builder from the reviewer's report; the report was not kept word for word.

| # | Blocker in the first design | What the built contract does instead |
|---|---|---|
| 1 | One challenge slot, first come: the requester could take it with a second address and never be at risk. | Any number of challenges until the window closes, then one re-check. On an overturn every challenger shares the bond. |
| 2 | The challenger picked the moment, and mining shares on live pages move by luck. | Only verdicts about a coin's earliest blocks (rules P1 and P2), which do not move, can be bonded. Mining verdicts are recorded but cannot be bonded. The re-check runs in a fixed window after the challenge window. |
| 3 | The leader's top-miner line, count included, had to stand on every validator's copy; live counts move, so honest validators would never agree. | As in the bounties M1 rule: validators agree on each page's class and the miner's name; each validator's own counts decide its own verdict; no count is passed on or stored. |
| 4 | No processing grace on the re-check, and the time conditions were not written down. | Every time condition is written out with its grace and tested to the second. |
| 5 | Rule M2 never checked that the named miner was the largest, and skipping an "Unknown" row could give "supported". | For M2 the model copies every row; code checks the rows against the printed total; each catch-all row and the unlisted remainder count as one miner each. |
| 6 | The P receipts only proved that some line existed; "supported" could come from the model seeing nothing. | P1 is the bounties P1 rule (block number printed, amount exact on the copied line, agreed exactly). P2 quotes block 1's reward line with its amount, checked the same way. FAIR_LAUNCH is never "supported". Allocations made in a chain's genesis state are stated as not covered. |

Also taken from the review: no number is stored that validators did not agree on; the same rule must hold on both pages; thresholds are exact integers; IP addresses are refused; the coin's name must stand near the top of each page; for an undetermined verdict validators compare the class and whether the explorers disagree, not every sub-reason; a model answer out of form makes that page unreadable; the word "challenge" instead of "appeal", since GenLayer has its own protocol appeal; window floors of 10 minutes, no owner and no setter. The reviewer agreed that the shape (two sources, a bonded challenge, a new Bradbury deployment) is clearly different from the claim-bounties milestone.

## 2. The first build (24 November 2026)

Two reviewer sessions, run side by side, neither of which had seen the build: one on the contract, the money and the tests (2a), one on the write-up, the article, the video and the page, checked against the code, the live records and the chain (2b). Recorded here by the builder from the reviewers' reports. The reviewers' probe tests were folded into [`tests/direct/test_checker_v2_review.py`](../../tests/direct/test_checker_v2_review.py), each now asserting the fixed behaviour.

### 2a. Contract, money and tests: not ready, three blockers

| # | Blocker in the first build | What the fixed contract does |
|---|---|---|
| 1 | A FAIR_LAUNCH verdict could be bonded but never overturned (FAIR_LAUNCH is never SUPPORTED); and "upheld" compared only the verdict, so a re-check that found a mining majority upheld a block-1 bond. | Only NO_PREMINE and NO_FOUNDER_REWARD verdicts can be bonded. UPHELD needs the same fact: the same rule, and for P1 the same block and amount (for P2 the same block); anything else is NOT CONFIRMED. |
| 2 | A requester could challenge its own bond from other addresses: on an overturn its loss fell to B/(k+1) with k extra addresses. | Half of an overturned bond (rounded down) is burned. The challengers get their deposits back and share the other half, so the requester loses at least half however many addresses it uses. `totals()` counts the burned GEN. |
| 3 | For an undetermined verdict, each page's amount, block, line and miner were the leader's alone: validators compared only the class. | An undetermined result is passed on and stored in short form: the reason and each page's class and rule, all compared by every validator. No amount or line is stored that the validators did not all see. |

Also fixed: a model answer out of form makes the page unreadable (it counted as "nothing"); in a re-check, a page that cannot be read or does not show the coin (an error page) decides nothing (it ended the bond as not confirmed at once); BOTH:M1 needs the same miner on both explorers; M2 no longer stores a miner name (two pools tied at the top split honest validators); coin names made only of generic words or numbers ("Block 1", "Coinbase") are refused; a block number counts only on a line that says "block" or "height" (a lone "1", as in "Confirmations: 1", no longer counts); dead time guards were removed. Stated in the README rather than changed: whoever controls one of the two explorers can keep a re-check from deciding (the bond then ends not confirmed); a bond's challenge window runs from the time the bond was sent, so the 600-second windows of the live deployments are for demonstration (the defaults are 60 minutes to bond and 24 hours to challenge); a Bradbury withdrawal sent without a fee allocation loses the amount.

The tests did not exercise some guards that the code handled correctly (a withdrawal above the credit, the D1 page classes, the P2 block, the constructor's caps, ports, the anchor and page limits): tests and mutants were added for each. The random walk now keeps a separate model of every account's credit and takes every outcome, refused bonds and challenges, an unreadable re-check and partial withdrawals.

Confirmed correct by the reviewer: the Bradbury build is byte for byte what the packer makes; the overturn share is exact (tested with 50 challengers); paid in = locked + credited + withdrawn after every step; refused payments are credited back and never raise; every time boundary holds to the second; validators agree exactly on definite verdicts; the URL and domain filters.

### 2b. Write-up, article, video and page: ready with changes

Must-fix: MILESTONE-2 said every run ended with a zero balance, but the free-check deployment kept 1 GEN credited back for a late bond; and one record's expectation had been rewritten after the run. Both records are kept unchanged in [`examples/live/v2-first-build/`](../../examples/live/v2-first-build/); the live runs were repeated on the fixed build and the write-up now describes those. Other changes: the verifiers now compare every verdict and re-check with the chain and check the page record and the page contract's code; page buttons appear only for accounts that can use them; the page checks domains as the contract does; the wording on block numbers, corrections, validator votes, the line count and `get_check(at)` was corrected; missing transaction links were added; setup lines for the verifiers were added.

Confirmed correct by the reviewer: nearly every figure; all 29 transaction links; the timing of every page correction against the chain; the live pages equal the repositories; the page loads with no errors on both networks; no secret in the repository.

# Reviews of Launch Claim Checker v2 (two explorers, a bond and a challenge)

Contract [`contracts/launch_claim_checker_v2.py`](../../contracts/launch_claim_checker_v2.py), its tests, the site page and these documents were built by an AI session (Claude, Anthropic) working for Brilliant Nodes. As for the claim bounties ([`reviews/README.md`](../README.md)), the work goes to a **separate reviewer session** before each step forward: another Claude session, started fresh with a written brief, that has not seen the work being done and is asked to find what is wrong. No person outside Brilliant Nodes and no other model has reviewed it.

| # | What was reviewed | Verdict |
|---|---|---|
| 1 | The design (first version), before any code | not ready, 6 blockers |
| 2a | The first build: contract, money and tests | not ready, 3 blockers |
| 2b | The first build: every claim in the write-up, the article, the video and the page, against the code, the records and the chain | ready with changes, 2 must-fix |
| 3a | The second build: contract, money, tests, tools and records | not ready, 1 blocker |
| 3b | The second build: every figure, link and claim in the package, against the code, the records and the chain | ready with changes, 11 must-fix |
| 4a | The third build: contract, money, tests, Bradbury Phase 3 port, tools and records | ready with changes, 6 must-fix |
| 4b | The third build: every figure, link and claim in the package, against the code, the records and the chain | ready with changes, 8 must-fix |

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

Also fixed: a model answer out of form makes the page unreadable (it counted as "nothing"); in a re-check, a page that cannot be read or does not show the coin (an error page) decides nothing (it ended the bond as not confirmed at once); BOTH:M1 needs the same miner on both explorers; M2 no longer stores a miner name (two pools tied at the top split honest validators); coin names made only of generic words or numbers ("Block 1", "Coinbase") are refused; a block number counts only on a line that says "block" or "height" (a lone "1", as in "Confirmations: 1", no longer counts); dead time guards were removed. Stated in the README rather than changed: whoever controls one of the two explorers can keep a re-check from deciding (the bond then ends not confirmed); a bond's challenge window runs from the time the bond was sent, so the short windows of the live deployments (600 seconds; on the second build's Bradbury deployment 1,200 seconds to re-check) are for demonstration (the defaults are 60 minutes to bond and 24 hours to challenge); a Bradbury withdrawal sent without a fee allocation loses the amount.

The tests did not exercise some guards that the code handled correctly (a withdrawal above the credit, the D1 page classes, the P2 block, the constructor's caps, ports, the anchor and page limits): tests and mutants were added for each. The random walk now keeps a separate model of every account's credit and takes every outcome, refused bonds and challenges, an unreadable re-check and partial withdrawals.

Confirmed correct by the reviewer: the Bradbury build is byte for byte what the packer makes; the overturn share is exact (tested with 50 challengers); paid in = locked + credited + withdrawn after every step; refused payments are credited back and never raise; every time boundary holds to the second; validators agree exactly on definite verdicts; the URL and domain filters.

### 2b. Write-up, article, video and page: ready with changes

Must-fix: MILESTONE-2 said every run ended with a zero balance, but the free-check deployment kept 1 GEN credited back for a late bond; and one record's expectation had been rewritten after the run. Both records are kept unchanged in [`examples/live/v2-first-build/`](../../examples/live/v2-first-build/); the live runs were repeated on the fixed build and the write-up now describes those. Other changes: the verifiers now compare every verdict and re-check with the chain and check the page record and the page contract's code; page buttons appear only for accounts that can use them; the page checks domains as the contract does; the wording on block numbers, corrections, validator votes, the line count and `get_check(at)` was corrected; missing transaction links were added; setup lines for the verifiers were added.

Confirmed correct by the reviewer: nearly every figure; all 29 transaction links; the timing of every page correction against the chain; the live pages equal the repositories; the page loads with no errors on both networks; no secret in the repository.

## 3. The second build (25 November 2026)

Two more reviewer sessions, run side by side on the second build (commit df3567b), neither of which had seen the work: one on the contract, money, tests, run tools, verifiers and records (3a), one on every figure, link and claim of the package (3b). Recorded here by the builder from the reviewers' reports; the reviewers' probe tests became [`tests/direct/test_checker_v2_review3.py`](../../tests/direct/test_checker_v2_review3.py), each asserting the fixed behaviour.

### 3a. Contract, money, tests, tools: not ready, one blocker

| # | Finding in the second build | What the final contract and tools do |
|---|---|---|
| Blocker | A `BOTH:P1` verdict on a block from 2 to 100 could be bonded but never overturned: P2, the opposite reading, exists only for block 0 or 1. The requester could not lose. | Only a verdict on block 0 or 1 can be bonded; any other is refused and credited back. |
| Must-fix | An overturn did not check the block: a clean block 0 overturned a bond on block 1. | An overturn needs the opposite rule about the same block on both explorers. |
| Must-fix | An error page that keeps the explorer's header (the coin's name in it) passed the anchor, read as nothing, and decided the re-check at once as not confirmed. | A re-check decides only when both explorers show a definite fact or opposite facts; any other reading decides nothing and the window stays open. |
| Must-fix | Two mutants the mutation script dropped as equivalent were not: without the class comparison, a validator accepted an undetermined result with the two page classes swapped; and M1 and M2 can both match one answer, so their order matters. | Both have tests and are in the mutation set; the script's notes were corrected. |
| Must-fix | Some verifier excuses were broader than needed: a failed read was excused if the same read passed at any other moment, a note excused a failed check with nothing read from the chain, and the page record's sender, arguments, value and time were not compared. | A failed read is excused only if it passed later or found the case's recorded final state; a note excuses only with a value read again from the chain; the page record is compared in full; a not-agreed step is accepted only as a note when the same call was sent again and agreed. |
| Must-fix | Write-up statements the chain contradicts (the stopped Bradbury contract named as the current one; "600 seconds for every window"; "GEN depends only on the class"; a too-early re-check on Studio that did not happen). | Corrected (see 3b). |

Also done: the mining prompt now asks for counts as digits only (explorer B printed "200 blocks", which made its page read as nothing on some validators); common block-page field names ("Difficulty", "Nonce", "Timestamp", ...) are refused as coin names; the Bradbury run retries only a send refused for its fee, not a dropped connection; the Studio run counts only agreed checks. Stated in the README rather than changed: "upheld with n challengers" can be staged from a requester's own addresses; the first decided re-check is final, so a correction must be on both explorers when the window opens; the stored evidence line is the leader's choice among lines carrying the agreed amount; on Bradbury anything beyond a demonstration should use the default re-check window or longer.

Confirmed correct by the reviewer: the packed build is byte for byte what the packer makes; 131 tests passed on both GenVM versions and 119 of 119 mutants were caught; the half burn and the share of the rest are exact; locked + credited + burned equals the balance on all three live contracts; a requester challenging itself still loses at least half; the undetermined short form and the agreement rules hold; the time boundaries hold to the second; the committed records equal the raw run files apart from labelled additions; every page correction came after its bond and before its re-check.

### 3b. The package: ready with changes

Eleven text corrections: the README named the stopped Bradbury deployment as the current one; said every deployment used 600-second windows (Bradbury re-checked in 1,200), that an explorer that is down decides the outcome, that GEN depends only on the class, that the balance matched after every step (it was checked at the end, and on Studio after the transfers), and that `get_check` returns a phase (it returns times and `as_of`); MILESTONE-2 said the stopped attempt's disagreement case was not decided (its re-check had been sent and decided a minute before the stop), described a too-early re-check on Studio that did not happen, and said "two" reviewer sessions; the article said an error page gives "not confirmed", and the article and the video said "independent reviews" without saying they were AI sessions. Each was corrected in the final package, and the second build's records were moved to [`examples/live/v2-second-build/`](../../examples/live/v2-second-build/) with a note correcting the stopped record. Smaller suggestions taken: plainer wording in the article, the page's limits covering all four rules, and the first-build videos removed from the site.

Confirmed correct by the reviewer: all 46 transaction links resolved to the right case, method and network, and all were read on chain; every figure, payout and balance; the test, mutant, line and byte counts; the timing of every page correction; the live explorer pages equal the repositories; the page loads with no errors on both networks; every number in the video; nothing factually wrong in the X post or the YouTube text.

After both reports the contract was fixed (commit 8b9496b), deployed again on Studio and on Bradbury (by then Testnet Bradbury Phase 3), and every live run except the two real-explorer checks was made again.

## 4. The third build (26 November 2026)

Two more reviewer sessions, run side by side on the third build (commit c91f300, with the Bradbury Phase 3 port), neither of which had seen the work: one on the contract, money, tests, the Phase 3 port, the run tools, verifiers and records (4a), one on every figure, link and claim of the package (4b). Both re-ran the verifiers against the chain (0 mismatches) and confirmed every review-3 finding fixed. Recorded here by the builder from the reviewers' reports; the reviewers' probe tests became [`tests/direct/test_checker_v2_review4.py`](../../tests/direct/test_checker_v2_review4.py), each asserting the fixed behaviour.

### 4a. Contract, money, tests, tools: ready with changes

| # | Finding in the third build | What the final contract and tools do |
|---|---|---|
| Must-fix | A `BOTH:P1` verdict on a block whose pages show no ordinary reward, or a reward of 0 (usual for a chain's first block), could be bonded but never overturned: P2, the opposite reading, needs a non-zero reward on a line of the page, so a corrected page reads as nothing and the bond ends not confirmed. A right challenger only got its deposit back. | A `BOTH:P1` verdict can be bonded only when both pages also show the block's ordinary reward, not zero, on a line of the page. The model is asked for the reward whatever the page shows; each validator checks the leader's reward line on its own copy. |
| Must-fix | The edge of the review-3 fix was untested: allowing block 2 still passed every test. | A block-2 test and that mutant. |
| Must-fix | The `milestone-two-explorers` branch on GitHub had stopped at a commit from before a rebase: the page tool's pushes to it were refused and ignored. | The page tool pushes `main` only; the branch is brought up to date once, at submission. |
| Must-fix | The page tool committed whatever was staged and pushed every local commit: the swervecoin correction commit also deleted four old video files. | It commits only the corrected pages and refuses to run with local commits not on GitHub. |
| Must-fix | The stopped Phase 3 record's note gave a wrong time, a wrong account of the commits on GitHub, and left out 0.4 GEN credited back. | Corrected in [`examples/live/v2-third-build/README.md`](../../examples/live/v2-third-build/README.md). |
| Must-fix | MILESTONE-2 named the Phase 2 helper folder for the Phase 3 verifier. | Corrected. |

Also done: the run tools send a re-check again when it agreed but decided nothing, and the Studio run, like the Bradbury one, never re-checks before the corrected pages are live; the verifiers accept such a re-check only as a note when the same call was sent again and decided; the Bradbury verifier ties a note to the value the failed check wanted; the Studio verifier compares arguments when it looks for a call sent again; the contract's note on time names the transaction's own timestamp for the re-check; the mutation notes say that the per-page block test in `_outcome` is defensive. Stated in the README rather than changed: coin names made only of field words are refused; an explorer down for the whole re-check window ends a bond not confirmed, which is cheap to cause on the short live windows.

Confirmed correct by the reviewer: every review-3 finding fixed; 151 tests on GenVM v0.2, v0.6.0-rc10 and v0.6.0-rc17 and 128 of 128 mutants; every dropped mutant truly equivalent; both Bradbury builds byte for byte what the packer makes, and the Phase 3 header and runner those of GenLayer's own Phase 3 contracts; locked + credited + burned equals the balance on all four live contracts; the committed records equal the raw run files apart from labelled additions; every page correction after its bond and live before its re-check.

### 4b. The package: ready with changes

Eight corrections: the milestone branch showed the old build (see 4a); the Phase 3 withdrawals were finalized about 30 minutes after they were sent, not 40; the verifier's setup folder (see 4a); the README named only Studio's balance delay, not Bradbury's; the stopped record's note (see 4a); the video's overturn scene showed Flipcoin, a coin from the superseded first build; the page and the article left out that a definite reading of another block or amount ends a bond not confirmed at once; and the review counts needed this round. Smaller suggestions taken: which check failed on Bradbury, the votes on Studio, how the Studio run stopped, which earlier checks the real-explorer rules still match, the Bradbury fee note, page details (the Bond button for blocks above 1, the rules table, the W1 description, the network tooltip) and plainer article wording.

Confirmed correct by the reviewer: all 51 transaction links, every one read on chain; every figure, payout and balance, and the state of all four contracts; the test, line and byte counts; the timing of every page correction; the page loads with no errors on both networks; every narration line of the video; nothing factually wrong in the X post or the YouTube text.

After both reports the contract was fixed (commit d7535d5) and deployed again. The first Studio run of that build refused its first bond: page A's reward was not kept, because the model copied "50" from one line and the table row, which prints "50.00000000". The contract now takes the same value printed in another form on the copied line, for this reward and for P2 (commit 56abe9e); a probe on Studio kept the reward on both pages, and the build was deployed again. Every live run except the two real-explorer checks was then made again on that build (commit cb4261e), on Studio and on Bradbury Phase 3; the stopped runs are kept in [`examples/live/v2-review4-stopped/`](../../examples/live/v2-review4-stopped/).

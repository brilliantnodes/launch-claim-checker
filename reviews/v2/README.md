# Reviews of Launch Claim Checker v2 (two explorers, a bond and a challenge)

Contract [`contracts/launch_claim_checker_v2.py`](../../contracts/launch_claim_checker_v2.py), its tests, the site page and these documents were built by an AI session (Claude, Anthropic) working for Brilliant Nodes. As for the claim bounties ([`reviews/README.md`](../README.md)), the work goes to a **separate reviewer session** before each step forward: another Claude session, started fresh with a written brief, that has not seen the work being done and is asked to find what is wrong. No person outside Brilliant Nodes and no other model has reviewed it.

| # | What was reviewed | Verdict |
|---|---|---|
| 1 | The design (first version), before any code | not ready, 6 blockers |

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

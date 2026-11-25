# Launch Claim Checker: start here (for reviewers, 5 minutes)

## Milestone 2: two explorers, a bond and a challenge

**What it is, in plain words:** version 2 of the checker reads a launch claim such as "no founder reward" on two block explorers on different domains, and keeps a definite verdict only when both show the same fact by the same rule. A requester can bond a "no premine" or "no founder reward" verdict about a coin's block 0 or 1; anyone can challenge it with the same amount; the validators read both explorers again and the outcome moves the money. An overturned bond is half burned. Contract [`contracts/launch_claim_checker_v2.py`](contracts/launch_claim_checker_v2.py); the accepted checker and the bounties contract are unchanged. What changed: [`MILESTONE-2.md`](MILESTONE-2.md).

### 1. How consensus binds the money

- **Two explorers, read by every validator.** Each validator renders both pages itself, one model call per page. Code checks the coin's name near the top of each page, then every value the model gives against that validator's own copy (block number printed on a line that says block or height, amount exact on the copied line, catch-all miner rows refused); an answer out of form makes the page unreadable. README, [How each validator reads one page](README.md#how-each-validator-reads-one-page).
- **Agreement on what moves money:** the verdict and rule exactly; per page the class and rule; for `BOTH:P1` the block and the amount exactly; for `BOTH:P2` the block. An undetermined result is stored in short form (the reason and each page's class and rule), all of it compared by every validator. When the explorers show opposite facts, validators agree on `D1_EXPLORERS_DISAGREE`, and that verdict cannot be bonded.
- **The re-check decides the bond.** The same fact (same rule, same block, and for P1 the same amount): upheld, the requester takes the deposits. The opposite rule about the same block (`BOTH:P1` ↔ `BOTH:P2`): overturned, half the bond is burned and the challengers share the rest, so a requester challenging itself from other addresses still loses half. The explorers showing opposite facts, a definite reading of another block or amount, or no decided re-check in its window: not confirmed, everyone gets their own money back. Any other reading (a page that cannot be read, another coin, an error page with the explorer's header) decides nothing. Only a verdict on block 0 or 1 can be bonded, since only there can it be overturned.
- **No model where GEN arrives.** `bond` and `challenge` run no model and never raise; a refused payment is credited back. Time is each transaction's own timestamp. Pull payments only; `totals()` = locked + credited + burned, equal to the contract's balance once withdrawals' transfers are made.

### 2. Check it in five steps

1. Open https://checker.brilliantnodes.com/two-explorers.html, make three temporary accounts, check the example "Examplecoin, no founder reward", bond it and challenge it twice (about five minutes; the re-check opens 20 minutes later).
2. Import the Studio contract: [`0x624c…49F9`](https://studio.genlayer.com/?import-contract=0x624c4Af62668A6ac6C82040F61d9d0dDaCEa49F9).
3. Read the live cases in [`MILESTONE-2.md`](MILESTONE-2.md#how-it-was-checked): upheld with two challengers, released, overturned after both explorers corrected block 1, not confirmed when only one did, not confirmed with no re-check, and the refusals; each links its transactions.
4. Records: Studio [`examples/live/v2-studio.json`](examples/live/v2-studio.json) and the page click-through [`examples/live/v2-site-studio.json`](examples/live/v2-site-studio.json) (`python tools/verify_v2.py` checks both against the chain); Bradbury Phase 3 [`0xBa37…6e46`](https://scan.bradbury.genlayer.com/address/0xBa377D0FED0E0A40eA3978716F4495D234DF6e46), [`examples/live/v2-bradbury.json`](examples/live/v2-bradbury.json) (`python tools/verify_v2_bradbury.py`).
5. Video (92 s): https://checker.brilliantnodes.com/two-explorers-demo-v5.mp4. Tests: 151 for version 2 on GenVM v0.2 and v0.6, 128 of 128 deliberate breaks caught; five independent AI reviewer sessions in three rounds, recorded in [`reviews/v2/`](reviews/v2/README.md), every blocker fixed before the final runs; limits in the README ([Limits of version 2](README.md#limits-of-version-2)).

*All coins and both explorers in the examples are fictional test pages run by Brilliant Nodes. Test GEN only.*

## Milestone 1: claim bounties

**What it is, in plain words:** money behind a crypto launch claim. Anyone posts a GEN pot behind a claim such as "no premine"; the pot pays the first person who shows, on the explorer pages the poster pinned, that the claim is false. A second contract, [`contracts/launch_claim_bounties.py`](contracts/launch_claim_bounties.py); the accepted checker contract is unchanged. What changed since the accepted version: [`MILESTONE.md`](MILESTONE.md). Why it matters: crypto scams took in at least $14bn in 2025, per Chainalysis ([Decrypt](https://decrypt.co/354624/ai-impersonation-drove-crypto-scam-losses-record-17-billion-2025-chainalysis)).

### 1. How consensus binds the money

- **The model copies; code decides.** Each validator renders the pinned page itself; its model fills a fixed form; plain Python checks every value against that validator's own copy of the page (block number printed and equal to the revealed one, amount parsed exactly, the quoted line standing on one line of the validator's copy; catch-all rows such as "unknown", "others" or burn addresses refused). README, [What decides a payout](README.md#what-decides-a-payout).
- **Agreement on what moves money:** for `P1` (premine), the outcome and the amount exactly; for `M1` (mining), the outcome and the top miner by name. The three no-pay outcomes are not interchangeable.
- **No model where GEN arrives.** `post_bounty` and `file_claim` run no model, read no page and never raise; a refused payment is credited back.
- **Sealed filings and transaction time.** Only a digest goes on chain at filing; ranking and deadlines use each transaction's own timestamp, so nobody can make an in-time claim late. Payouts are credits; `totals()` = locked + credited + burned, equal to the balance at the end of both live runs.

### 2. Check it in five steps

1. Open https://checker.brilliantnodes.com/bounties.html, make two temporary accounts, post the example bounty "Examplecoin, no founder reward", file a claim on block 1, judge it (about two minutes).
2. Import the Studio contract: [`0x5839…BDca`](https://studio.genlayer.com/?import-contract=0x583995CE8814C987e888070352A3F1d3AF9BBDca).
3. Read the seven live cases in the README ([Live runs](README.md#live-runs)): won under P1, won under M1, a true claim keeps its bounty, first sender wins, and more; each links its transactions.
4. Records: Studio 46 of 46 as expected ([`examples/live/bounties-studio.json`](examples/live/bounties-studio.json)); Bradbury [`0xc437…257b`](https://scan.bradbury.genlayer.com/address/0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b), 41 of 41 ([`examples/live/bounties-bradbury.json`](examples/live/bounties-bradbury.json)).
5. Tests: 419 for the bounties contract (481 with the checker's), on GenVM v0.2 and v0.6; limits stated plainly in the README ([Limits, stated plainly](README.md#limits-stated-plainly)).

### 3. Links

- Video (86 s): https://checker.brilliantnodes.com/claim-bounties-demo.mp4
- Changes since the accepted version: [compare v1-accepted...milestone-claim-bounties](https://github.com/brilliantnodes/launch-claim-checker/compare/v1-accepted...milestone-claim-bounties)

*Examplecoin, Controlcoin, their pools and explorer pages are fictional. Test GEN only.*

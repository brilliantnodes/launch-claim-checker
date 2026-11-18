# Milestone: claim bounties

Launch Claim Checker was accepted as a Project in its first version: a contract that says what two pages show about a launch claim. This milestone adds **claim bounties**: money behind a launch claim.

- **Accepted version:** branch [`v1-accepted`](https://github.com/brilliantnodes/launch-claim-checker/tree/v1-accepted) (commit `50e39ab`)
- **This milestone:** branch [`milestone-claim-bounties`](https://github.com/brilliantnodes/launch-claim-checker/tree/milestone-claim-bounties), a snapshot of `main` as submitted
- **Everything that changed:** [compare `v1-accepted...milestone-claim-bounties`](https://github.com/brilliantnodes/launch-claim-checker/compare/v1-accepted...milestone-claim-bounties)
- **Try it:** https://checker.brilliantnodes.com/bounties.html ([five steps, two minutes](README.md#try-it-in-two-minutes))
- **Video (86 seconds, with voice-over):** https://checker.brilliantnodes.com/claim-bounties-demo.mp4
- **Contract on Studio:** [`0x583995CE8814C987e888070352A3F1d3AF9BBDca`](https://explorer-studio.genlayer.com/address/0x583995CE8814C987e888070352A3F1d3AF9BBDca) · [open it in GenLayer Studio](https://studio.genlayer.com/?import-contract=0x583995CE8814C987e888070352A3F1d3AF9BBDca)
- **Contract on Testnet Bradbury Phase 2:** [`0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b`](https://scan.bradbury.genlayer.com/address/0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b)

Test GEN only. Examplecoin and Controlcoin, their pools and their explorer pages are fictional.

## What is new

| | Accepted version | This milestone |
|---|---|---|
| Contracts | `launch_claim_checker.py`: a verdict on two pages, no money | the same file, byte for byte, plus `launch_claim_bounties.py` (1,252 lines): escrowed bounties on a claim |
| Money | none | GEN in escrow; pull payments only; a burned filing fee; `totals()` accounts for every wei paid in through `post_bounty` and `file_claim` |
| Who supplies the page | the requester | the poster pins the pages when posting; a hunter never supplies an address |
| What validators agree on | a verdict, with a 2-point tolerance on shares | the outcome and, exactly, an amount (rule P1) or a miner's name (rule M1) |
| Front-running | not relevant | filings are sealed (sha256 commit, reveal at judgement) and rank by the time they were sent, as finely as the network stamps it: to the microsecond on Studio, to the second on Bradbury |
| Time | none | 30 minutes to reveal, 60 to be processed, a provisional window, reclaim 60 minutes after expiry; all decided on each transaction's own timestamp |
| Networks | Studio, Bradbury | Studio, Bradbury (packed GenVM v0.6 build); the same seven live cases run on both |
| Site | one page | a second page, `bounties.html`: post, file a sealed claim, reveal and judge, finalize, reclaim, withdraw; a read-only Bradbury view |
| Tests | 62 | the same 62, plus 419 for bounties on both GenVM versions, 239 deliberate breaks all caught, a seeded random walk |

## What the contract does

1. **Post.** A pot behind one claim about one coin, with pinned explorer pages.
2. **File.** A sealed claim (a sha256 of the bounty's id, the filer's address, the rule, the block and a salt), for a fee of 2% of the pot that is burned. No model runs.
3. **Judge.** The filer reveals. Validators render the pinned page; each one's model fills in a fixed form; plain Python checks every value against that validator's own copy and decides. Validators must agree on the amount exactly, or on the top miner by name.
4. **Pay.** A filing that pays wins once no filing sent before it is still waiting. Otherwise the poster takes the pot back 60 minutes after the expiry.

The full rules, the interface and the limits are in the [README](README.md#claim-bounties).

## How it was checked

**Tests.** 419 direct-mode tests, passing on GenVM v0.2 (Studio) and on v0.6 against the packed Bradbury build. `tools/mutate_bounties.py` breaks the contract in 239 ways, one at a time, and the tests catch every one. A seeded random walk posts, files, judges, finalizes, reclaims and withdraws with transactions processed out of order, and checks the money and the queue after every step.

**Reviews.** Seven reviews, each by a separate AI reviewer session (Claude) that got a written brief and the repository and had not seen the work being done. The contract was built by an AI session as well, working for Brilliant Nodes. No person outside Brilliant Nodes and no other model has reviewed it. [`reviews/README.md`](reviews/README.md) records each one; the reviewers' own probe scripts are in [`reviews/probes/`](reviews/probes/).

| Review | Verdict | What changed because of it |
|---|---|---|
| Design, first version | not ready as written, 5 blockers | among the changes: hunters no longer send an address: the poster pins the pages; claims are no longer free: every filing pays a fee, which is burned so that nobody profits from failed claims; lateness is judged on the transaction's own time, so nobody can push a pending claim past the expiry; validators must agree on the amount exactly, with the leader's line on their own copy |
| Code, first build | not ready, 3 blockers | filings became sealed (a paid sha256 commitment bound to the filer's address) and rank by the time they were sent, because a copier whose filing was processed first could win; M1 stores only the agreed miner name (block counts no validator checked were stored); placeholder rows such as "N/A (solo)" and "37 others" no longer pay |
| Code, second build | ready with changes, no blockers | amounts written "2 000 000" can no longer pay as "2"; the miner's name and its count must stand on the same line; a model that fails costs a try, not the filing; a lead wins as soon as nothing sent before it is waiting; what sealing does not do is stated |
| Contract, before submission | ready with changes, no blockers | whether a number is ambiguous is decided on the page's own line, not on the quoted part of it; block counts get the same rule; the catch-all filter reads the whole row; the limit of a seal under rule M1 is stated |
| Repository, site and video, before submission | ready with changes | twelve statements that were wrong or not backed were corrected or backed: the Bradbury run now covers all seven cases; the network measurements are recorded with their transactions; the page was run against the deployed contract; the verifiers decode method and arguments from the chain; this table |
| The changes made after those two reviews | fix first; after the fixes, no code change needed to deploy | a zero address printed in shortened form, or with a label next to it, no longer pays under M1; an output index 0, a percentage with decimals and a time of day are no longer taken for one group of a number; a total equal to the miner's count must be printed twice; the amount must be clear at every place it has on the page line; the description's sentences on these points were corrected |
| The published repository, site and video, after the live runs | ready with changes; every figure and transaction link checked out | wording only: what `totals()` covers; which limits are stated only in the README; the example pages were written for these tests; who reviewed; the two-minute walkthrough |

**Measured on the network, not assumed.** A small probe contract on Studio, [`tools/probes/probe.py`](tools/probes/probe.py), with every transaction in [`examples/live/network-probes-studio.json`](examples/live/network-probes-studio.json): the transaction time a contract sees is the network's creation time, to the microsecond; a payable call that raises keeps the GEN, which is why the two calls that take GEN never raise; GEN sent with a call that takes none, or with a wrong number of arguments, stays in the contract; `web.render` returns a table row as one line, raises for a missing page and follows a redirect without saying so. On Bradbury a transaction's creation time is stamped in whole seconds, and a withdrawal carries its transfer as a message on the transaction; both are in the Bradbury record.

**Live runs.**

| | GenLayer Studio | Testnet Bradbury Phase 2 |
|---|---|---|
| Contract | [`0x5839…BDca`](https://explorer-studio.genlayer.com/address/0x583995CE8814C987e888070352A3F1d3AF9BBDca) | [`0xc437…257b`](https://scan.bradbury.genlayer.com/address/0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b) |
| Transactions after the deployment | 46 | 41 |
| Came out as expected | 46 of 46 | 41 of 41 |
| Checks against the contract's views | 16 of 16 | 46 of 46 |
| Validators | 5 per transaction. Studio accepts a transaction as soon as a majority has voted: the record shows 3 to 5 of 5 agreeing at that moment | 5 per transaction; on the 8 judgements, where each validator renders the page itself (in 7 its model then reads it; in one the page does not exist), 3 to 5 of 5 gave the leader's result |
| Record | [`examples/live/bounties-studio.json`](examples/live/bounties-studio.json) | [`examples/live/bounties-bradbury.json`](examples/live/bounties-bradbury.json) |

**The same seven cases on both networks** (17 Nov 2026, UTC), with the validators' own models reading the pages. Studio returns what a call returned; Bradbury transactions carry no return value, so there every step is recorded with the chain's consensus result, each validator's vote and the execution result, and with what the contract's views show afterwards.

1. **Won under P1.** Examplecoin's block 1 pays its founders 2,000,000 EXM. The sealed filing showed only a digest (Studio [0x04e0…58b4](https://explorer-studio.genlayer.com/tx/0x04e0b6ada2f9daad33acbc6846ff6ce9f5fb2828188d830b7d072cc02a7458b4), Bradbury [0xcf1c…0085](https://scan.bradbury.genlayer.com/tx/0xcf1c053e7feac71ee7d4653866531f290d79b0eed04f73af12591ff510c80085)). The reveal was judged `PAYS_P1`, the validators agreed on the amount exactly, and the hunter won the pot (Studio [0x4de9…4cf5](https://explorer-studio.genlayer.com/tx/0x4de9cfc050f5fec43b6709b1b8a837ef4f7ae0693f534f0d9a808588ffb44cf5), Bradbury [0xe598…5a86](https://scan.bradbury.genlayer.com/tx/0xe598272a699d3bb394d8c0574b4659c76809f6e7bec10c5090e2f2f4675b5a86)). On Bradbury a reveal with a wrong salt was refused first (Bradbury [0x7d83…e63c](https://scan.bradbury.genlayer.com/tx/0x7d838986718e01397f997b2e4e7499b82a415e5b2ca15fad9ce6a84aac5de63c)).
2. **Won under M1.** One miner has 840 of the last 1,000 Examplecoin blocks (Studio [0x817d…0412](https://explorer-studio.genlayer.com/tx/0x817d321b8579c8d36da82bb80c263eb5cf3e87305ca242ddc3046a1facff0412), Bradbury [0x2ff6…d45a](https://scan.bradbury.genlayer.com/tx/0x2ff6fcf5f0df77cf694e4706645521c256671888cf1284be9ff0d2e784a9d45a)). Only the agreed miner name is stored.
3. **A true claim keeps its bounty.** Controlcoin's block 1 holds only the block reward: `NO_PAY` (Studio [0x5d53…4974](https://explorer-studio.genlayer.com/tx/0x5d53d85948662784629984f433e4dc0b3d6470b0186719dfcad47c1833de4974), Bradbury [0x6729…2141](https://scan.bradbury.genlayer.com/tx/0x67297cc1ed6f84c5e8f41b8bb7c714ca3fadaa5b2bbb8d797838e536244e2141)). A second judgement of the same filing, a filing after the expiry and an early reclaim were refused. 60 minutes after the expiry the poster reclaimed the pot (Studio [0x447b…fe1b](https://explorer-studio.genlayer.com/tx/0x447bec9e381a65486b0e1187ddf0f2f492725bda95796a1e254dafb3bde4fe1b), Bradbury [0x11eb…90fd](https://scan.bradbury.genlayer.com/tx/0x11ebb7f88994eb942b673cde802fede138fef01db97d7a93597edc15aa0490fd)).
4. **Of two claims that pay, the one sent first wins.** The second hunter was judged first and led provisionally (Studio [0xb9fd…965a](https://explorer-studio.genlayer.com/tx/0xb9fde7ee83085551e547924b73baed62209777eda41a5ce758908606eab7965a), Bradbury [0x28d8…9630](https://scan.bradbury.genlayer.com/tx/0x28d87fce3662b3d6852ff799145b8005b0ca93ec602eb7eee9856df2ecf79630)). The first hunter's judgement took the lead and the pot (Studio [0xde94…79c4](https://explorer-studio.genlayer.com/tx/0xde94b50c5bd751b041ebe24f82b919dbb2a3e49f56aaa8a4e91f1d11cc4079c4), Bradbury [0x74d2…18ce](https://scan.bradbury.genlayer.com/tx/0x74d21aba8f118e47101dc09221516621ec19d9e4097539e47af394ecd4b518ce)).
5. **Refusals.** A filing with a wrong fee was taken by the network, refused by the contract and credited back (Studio [0x744d…8426](https://explorer-studio.genlayer.com/tx/0x744df708aff88e1deeb76207053a9a453d0a4bbd6ac6ffd1700c9841f6138426), Bradbury [0xd762…1b16](https://scan.bradbury.genlayer.com/tx/0xd7628007a587d211ed271cb62660b590e29bad7d450b2d05a5f361a6a7271b16)). A reveal with block 101, or with a rule the bounty does not pay on, was refused and cost nothing. The right reveal pointed at a page that does not exist: `UNREADABLE`, and the filing stayed live (Studio [0x21a0…51d8](https://explorer-studio.genlayer.com/tx/0x21a03957668149870f5a7fa6548d63627c967fdabd6fda617455e486fcfc51d8), Bradbury [0x0a60…aa46](https://scan.bradbury.genlayer.com/tx/0x0a606b36e3bcf4055626ca6db902e2e1507c2d414d175389d720278c1838aa46)). A copier who filed the hunter's digest after that reveal could not open it (Studio [0xee90…26cd](https://explorer-studio.genlayer.com/tx/0xee90de654b509acf98ea9cabc34d95113c1d326bacd02fbb0924db534dc026cd), Bradbury [0x37a9…763e](https://scan.bradbury.genlayer.com/tx/0x37a9a9517a33a691b43f2c9d2bf0246472e04a871abdd4a53fa7b4633894763e)).
6. **Wrong page.** A pinned address that always shows block 1 was claimed for block 2: `WRONG_PAGE` (Studio [0x5000…d561](https://explorer-studio.genlayer.com/tx/0x50005b5d1e9ff0c42ddb26638423b727a724bcd032c4c37c258fbc5b7d13d561), Bradbury [0x93bc…bf4d](https://scan.bradbury.genlayer.com/tx/0x93bcbfa30c85058dfd3b29a2012e8607489f0f2b105ec7bf6f5a51eeb119bf4d)).
7. **A lead that has to wait.** An earlier filing was never judged, so a paying claim led provisionally, and the pot was credited when that filing's 60 minutes were over (Studio [0xbeae…1e41](https://explorer-studio.genlayer.com/tx/0xbeae278a9c4f2b7e6f63dd187389f8e474b8bcfb9d39df3d588cd39cc4bd1e41), Bradbury [0xdd1b…66f1](https://scan.bradbury.genlayer.com/tx/0xdd1bb28f9868cc8085c9e6c253c220994c757276682493ce137ed726200066f1)).

**Withdrawals.** On Studio the hunter, the poster and the copier withdrew what was credited to them; the contract's balance fell by exactly those amounts, and for the first withdrawal the run also checked that the pot arrived in the hunter's wallet (Studio [0x4843…fdf7](https://explorer-studio.genlayer.com/tx/0x4843c81d86a3a46e58dff84bc0753b269c9aebd3e4d91acb3a849e3748aefdf7)). On Bradbury each withdrawal carries exactly one transfer, to its own sender: four pots to the hunter (Bradbury [0xfb31…2f68](https://scan.bradbury.genlayer.com/tx/0xfb31b5b62ca6c7a581f2665f8db750456dbff00eda45c94817df9d179de02f68)), its two refused payments to the copier (Bradbury [0x3e62…7dcb](https://scan.bradbury.genlayer.com/tx/0x3e62a19104d99d5a9ce66ed915182dd011f11eca5f57fccb6c9c002072a27dcb)) and the reclaimed pot to the poster (Bradbury [0x2f05…bc5a](https://scan.bradbury.genlayer.com/tx/0x2f05d9e37bdf986fed31cab121b90aaee9003569905cb497f0af23b9892cbc5a)).

At the end of both runs the contract's balance equalled locked + credited + burned, and the burned amount equalled the fees of the ten filings taken. All 46 Studio transactions and all 41 Bradbury transactions came out as expected, and so did every check against the contract's views (16 on Studio, 46 on Bradbury). The 8 Bradbury judgements took 34 to 210 seconds (41 to 210 where a model read a page).

`python tools/verify_bounties.py` and `python tools/verify_bounties_bradbury.py` check the two records against the chain: the deployed code is this repository's code byte for byte, and every transaction's sender, method, arguments, result and votes, the digest of every filing that was judged, every final state and the balance match.

**The page, used as a visitor would.** `tools/site_flow.py` opened https://checker.brilliantnodes.com/bounties.html in a headless browser and clicked through it against the deployed Studio contract: temporary accounts, the three examples posted as bounties, a sealed claim filed and judged on each (`PAYS_P1` [0x3494…5d6c](https://explorer-studio.genlayer.com/tx/0x3494407f65ece845385bd7072e4aa0fe801228985bebebdf475256277fac5d6c), `PAYS_M1` [0xe680…7ea1](https://explorer-studio.genlayer.com/tx/0xe6809aa650298e381c405683f85d1517d870f1dc28530f61349411ae1da67ea1), Controlcoin `NO_PAY` [0xcc76…626b](https://explorer-studio.genlayer.com/tx/0xcc7675c5b46ed3356b7a21796c27a600603a5501f358c74dd35e43a30ac2626b)) and the hunter's withdrawal ([0x4db2…0c3b](https://explorer-studio.genlayer.com/tx/0x4db217acb589cf1c0eff4bba60c619e4185c8187a60b949e694bd948cd610c3b)). The page made the keys, the salts and the digests in the browser. All 10 transactions came out as expected; what the chain has for each is in [`examples/live/bounties-site-studio.json`](examples/live/bounties-site-studio.json).

## New files

- `contracts/launch_claim_bounties.py`: the contract. `bradbury/build/launch_claim_bounties.py`: the packed GenVM v0.6 build.
- `tests/direct/test_bounties.py`, `tests/conftest_v6.py`, `tools/test_v6.sh`, `tools/mutate_bounties.py`: tests on both GenVM versions and the mutation check.
- `tools/bounty.py`: command-line client. `tools/live_bounties.py`, `tools/live_bounties_bradbury.py`: the live runs. `tools/verify_bounties.py`, `tools/verify_bounties_bradbury.py`: the checks against the chain. `tools/bradbury/`: the Bradbury client.
- `tools/probes/`: the network probe. `tools/site_flow.py`: the page, driven in a headless browser.
- `tools/make_bounty_pages.py`, `docs/examples/bounty/`: the fictional explorer pages.
- `web/bounties.html`, `web/src/bounties.js`, `web/src/bounties.css`: the bounties page. `tools/video/`: how the video was made.
- `reviews/`: the record of the reviews and the reviewers' probe scripts.

## Limits

Stated in full in the [README](README.md#limits-stated-plainly). In short: a bounty trusts its pinned pages; both rules are a model's reading with code checks, not a proof; pool names are written by miners and the catch-all word list is a filter; a reveal is public, so a hunter should reveal early enough to try again; under rule M1 a seal hides nothing; a number printed next to another short number can be refused as ambiguous. The example pages were written for these tests and state the allocation in a sentence; no bounty judgement has been run on a real explorer page yet. No outside party has used a bounty yet.

# Milestone: claim bounties

Launch Claim Checker was accepted as a Project in its first version: a contract that says what two pages show about a launch claim. This milestone adds **claim bounties**: money behind a launch claim.

- **Accepted version:** branch [`v1-accepted`](https://github.com/brilliantnodes/launch-claim-checker/tree/v1-accepted) (commit `50e39ab`)
- **This milestone:** branch `main`
- **Everything that changed:** [compare `v1-accepted...main`](https://github.com/brilliantnodes/launch-claim-checker/compare/v1-accepted...main)
- **Try it:** https://checker.brilliantnodes.com/bounties.html
- **Video (83 seconds, with voice-over):** https://checker.brilliantnodes.com/claim-bounties-demo.mp4

Test GEN only. Examplecoin and Controlcoin, their pools and their explorer pages are fictional.

## What is new

| | Accepted version | This milestone |
|---|---|---|
| Contracts | `launch_claim_checker.py`: a verdict on two pages, no money | the same file, byte for byte, plus `launch_claim_bounties.py` (1149 lines): escrowed bounties on a claim |
| Money | none | GEN in escrow; pull payments only; a burned filing fee; `totals()` accounts for every wei |
| Who supplies the page | the requester | the poster pins the pages when posting; a hunter never supplies an address |
| What validators agree on | a verdict, with a 2-point tolerance on shares | the outcome and, exactly, an amount (rule P1) or a miner's name (rule M1) |
| Front-running | not relevant | filings are sealed (sha256 commit, reveal at judgement) and rank by the time they were sent, to the microsecond |
| Time | none | 30 minutes to reveal, 60 to be processed, a provisional window, reclaim 60 minutes after expiry; all decided on each transaction's own timestamp |
| Networks | Studio, Bradbury | Studio, Bradbury (packed GenVM v0.6 build), both with full live runs |
| Site | one page | a second page, `bounties.html`: post, file a sealed claim, reveal and judge, finalize, reclaim, withdraw; a read-only Bradbury view |
| Tests | 62 | 62, plus 357 for bounties on both GenVM versions, 199 deliberate breaks all caught, a seeded random walk |

## What the contract does

1. **Post.** A pot behind one claim about one coin, with pinned explorer pages.
2. **File.** A sealed claim (a sha256 of rule, block and salt), for a fee of 2% of the pot that is burned. No model runs.
3. **Judge.** The filer reveals. Validators render the pinned page; each one's model fills in a fixed form; plain Python checks every value against that validator's own copy and decides. Validators must agree on the amount exactly, or on the top miner by name.
4. **Pay.** A filing that pays wins once no filing sent before it is still waiting. Otherwise the poster takes the pot back 60 minutes after the expiry.

The full rules, the interface and the limits are in the [README](README.md#claim-bounties).

## How it was checked

**Tests.** 357 direct-mode tests, passing on GenVM v0.2 (Studio) and on v0.6 against the packed Bradbury build. `tools/mutate_bounties.py` breaks the contract in 199 ways, one at a time, and the tests catch every one. A seeded random walk posts, files, judges, finalizes, reclaims and withdraws with transactions processed out of order, and checks the money and the queue after every step.

**Independent reviews.** The design and then the code were each reviewed by a separate reviewer that had not seen the work being done. What they changed:

| Review | Verdict | What changed because of it |
|---|---|---|
| Design, first version | not ready as written, 5 blockers | hunters no longer send an address: the poster pins the pages; claims are no longer free: every filing pays a fee, which is burned so that nobody profits from failed claims; lateness is judged on the transaction's own time, so nobody can push a pending claim past the expiry; validators must agree on the amount exactly, with the leader's line on their own copy |
| Code, first build | not ready, 3 blockers | filings became sealed (a paid sha256 commitment bound to the filer's address) and rank by the time they were sent, because a copier whose filing was processed first could win; M1 stores only the agreed miner name (block counts no validator checked were stored); placeholder rows such as "N/A (solo)" and "37 others" no longer pay |
| Code, second build | ready with changes, no blockers | amounts written "2 000 000" can no longer pay as "2"; the miner's name and its count must stand on the same line; a model that fails costs a try, not the filing; a lead wins as soon as nothing sent before it is waiting; every limit the reviewer found is now stated in the contract, the README and on the site |

**Measured on the network, not assumed.** The transaction time a contract sees is the network's creation time, to the microsecond. A payable call that raises keeps the GEN, which is why the two calls that take GEN never raise. `web.render` follows redirects silently and returns a table row as one line. A withdrawal reaches the wallet when its transaction is finalized.

**Live runs.**

| | GenLayer Studio | Testnet Bradbury Phase 2 |
|---|---|---|
| Contract | [`0x234D…bB8e`](https://explorer-studio.genlayer.com/address/0x234D26C4f2477EC4ef1b0FCA1f0ad0dA5c03bB8e) | [`0x8d2A…614f`](https://scan.bradbury.genlayer.com/address/0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f) |
| Transactions | 46 plus the deployment | 15 plus the deployment |
| As expected | 46 of 46 | 15 of 15 |
| Record | [`examples/live/bounties-studio.json`](examples/live/bounties-studio.json) | [`examples/live/bounties-bradbury.json`](examples/live/bounties-bradbury.json) |

**Studio, 46 transactions after the deployment, in seven cases** (17 Nov 2026, UTC):

1. **Won under P1.** Examplecoin's block 1 pays its founders 2,000,000 EXM. The sealed filing showed only a digest ([0x9cca…9fe1](https://explorer-studio.genlayer.com/tx/0x9ccae7d00f64b8e59182155c6f0cca386adb985ce206e56cdcc3ac15d4be9fe1)); the reveal was judged `PAYS_P1`, the validators agreed on the amount exactly, and the hunter withdrew the 1 GEN pot ([0x0899…2df5](https://explorer-studio.genlayer.com/tx/0x0899d65ef4d1c2dc90f7f7873168bb21c5c5bd4da05a9ce86a5d177bf20b2df5), [0x3a4c…7eb5](https://explorer-studio.genlayer.com/tx/0x3a4c30a1f6264ecdedb7ef24d82fa26feb6e206c53e073817b5670fe9aa47eb5)).
2. **Won under M1.** One miner has 840 of the last 1,000 Examplecoin blocks ([0x8bf2…63e4](https://explorer-studio.genlayer.com/tx/0x8bf2a77802945b8015edc151976c2518606b06d4269acbdc290e6fbda77d63e4)). Only the agreed miner name is stored.
3. **A true claim keeps its bounty.** Controlcoin's block 1 holds only the block reward: `NO_PAY` ([0xebba…97d7](https://explorer-studio.genlayer.com/tx/0xebba506c27702af3a0f962b55f0d54e57a1325d1ecd26a3b9e74c3ae6bd097d7)). A second judgement of the same filing, a filing after the expiry and an early reclaim were all refused; 60 minutes after the expiry the poster took the pot back ([0xf78f…b3d5](https://explorer-studio.genlayer.com/tx/0xf78fc120af25f181a7b4af1ccd6bd39fdcccf58ebf2966e24ebb8841dbf8b3d5)).
4. **Of two claims that pay, the one sent first wins.** The second hunter was judged first and led provisionally ([0x71e9…8afd](https://explorer-studio.genlayer.com/tx/0x71e974f9b59bcb989f42a8499009d97c7349af19a53e743767ed7527b0418afd)); the first hunter's judgement took the lead and the pot ([0xb17a…efb0](https://explorer-studio.genlayer.com/tx/0xb17a1038e265abb7261f50ce3bbe65b1bceb1b7352e280f89735bc499f40efb0)). The second hunter got nothing.
5. **Refusals.** A wrong fee, a digest that is not a sha256 and an unknown bounty were refused and credited back. A reveal with another salt, another block, block 101 or a rule the bounty does not pay on was refused and cost nothing. A copier who filed the hunter's digest once it was public could not open it ([0xa74e…ae61](https://explorer-studio.genlayer.com/tx/0xa74e20466d9d061a71674234601b40702f3c7031b35dae6e8f65fc8de627ae61)). A page that does not exist was `UNREADABLE` and left the filing live.
6. **Wrong page.** A pinned address that always shows block 1 was claimed for block 2: `WRONG_PAGE` ([0x9f38…4152](https://explorer-studio.genlayer.com/tx/0x9f38409f30fbe068d5a02c126e36f2c8eda479d919724c204e0c89de26fd4152)).
7. **A lead that has to wait.** An earlier filing was never judged, so a paying claim led provisionally and the pot was credited when that filing's 60 minutes were over ([0xf2a5…cd5d](https://explorer-studio.genlayer.com/tx/0xf2a5a28cff431a0d20d6b73fddc0db1bb493755c0fc2778cf83bb73f0912cd5d)).

At the end the contract's balance equalled locked + credited + burned, and the burned amount equalled the fees of the ten filings taken. What is still locked is the 1 GEN of bounties 5 and 6, which nobody won and whose poster has not taken them back. 46 of 46 transactions and 16 of 16 checks came out as expected.

**Bradbury, 15 transactions after the deployment** (17 Nov 2026, UTC), with the validators' own models and web access, on the packed GenVM v0.6 build. Bradbury transactions carry no return value, so every step is recorded with the chain's consensus and execution result and with what the contract's views showed afterwards.

1. **Won under P1** ([0x5a73…fabc](https://scan.bradbury.genlayer.com/tx/0x5a73291f2e96889aea9c6c7891ed13284f93c61b8518c0ec0af67a71999ffabc)), after a reveal with a wrong salt was refused ([0x08d7…fd78](https://scan.bradbury.genlayer.com/tx/0x08d7580022a6a2fa27690290900c5183d64d47b069b5145663e60612d385fd78)).
2. **Won under M1** ([0x9a9b…b1f8](https://scan.bradbury.genlayer.com/tx/0x9a9bb704bc507d1da5530dd631488a865cc1917794d8541102beac9b32b5b1f8)).
3. **A true claim keeps its bounty**: Controlcoin `NO_PAY` ([0x646b…e98c](https://scan.bradbury.genlayer.com/tx/0x646be6c9c7b99f05c68c5053ced6c8da7e07d3273dd8b5d3c478e7e7efdde98c)), an early reclaim refused, and the pot reclaimed 60 minutes after the expiry ([0xf8f0…3bfa](https://scan.bradbury.genlayer.com/tx/0xf8f0aa7729d8b7e9a351fb19a4d248405b8645bad2a1ba908c5384f628373bfa)).
4. **Withdrawals.** The hunter's withdrawal carries exactly one transfer, 0.2 GEN to the hunter ([0xccf0…6f4d](https://scan.bradbury.genlayer.com/tx/0xccf0df26989513c244b9c77bfeae96ac1b11511de34913a2665628d85f566f4d)); the poster's carries the reclaimed pot.

15 of 15 transactions came out as expected. Judgements, where validators read the page, took 55 to 64 seconds.

**Recorded as it happened.** On Studio, the finalize of case 7 went through on the chain, but Studio's gateway answered the script with an error page (HTTP 520) while it waited, and the script stopped. The transaction was found on the chain by its sender and time and entered in the record from the chain, the run was resumed from the next step with `--resume`, and the record says so on that step. The client now looks for a transaction on the chain when a send is not confirmed, and never sends it twice.

One check in the Bradbury record is marked as not met: it expected the hunter's wallet to rise by no more than the 0.2 GEN withdrawn. The wallet rose by more, because on Bradbury a wallet also gets back the unused part of earlier transactions' fee budgets. The check was wrong, not the payout: the withdrawal transaction itself carries one transfer of exactly 0.2 GEN to the hunter, which `tools/verify_bounties_bradbury.py` reads from the chain, and the live script now checks that instead. 19 of 20 checks in the record are met.

`python tools/verify_bounties.py` checks the Studio record against the chain: the deployed code is this repository's source byte for byte, and every transaction, digest, final state and the balance match.

## New files

- `contracts/launch_claim_bounties.py`: the contract. `bradbury/build/launch_claim_bounties.py`: the packed GenVM v0.6 build.
- `tests/direct/test_bounties.py`, `tests/conftest_v6.py`, `tools/test_v6.sh`, `tools/mutate_bounties.py`: tests on both GenVM versions and the mutation check.
- `tools/bounty.py`: command-line client. `tools/live_bounties.py`, `tools/live_bounties_bradbury.py`, `tools/verify_bounties.py`: the live runs and the check against the chain. `tools/bradbury/`: the Bradbury client.
- `tools/make_bounty_pages.py`, `docs/examples/bounty/`: the fictional explorer pages.
- `web/bounties.html`, `web/src/bounties.js`, `web/src/bounties.css`: the bounties page. `tools/video/`: how the video was made.

## Limits

Stated in full in the [README](README.md#limits-stated-plainly). In short: a bounty trusts its pinned pages; rule P1 is a model's reading with code checks, not a proof; pool names are written by miners and the catch-all word list is a filter; a reveal is public, so a hunter should reveal early enough to try again.

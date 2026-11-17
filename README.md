# Launch Claim Checker

A GenLayer Intelligent Contract that checks a crypto launch claim against two public pages: the project's announcement and a block explorer page.

New coins routinely launch with claims such as "no premine", "no founder reward" or "decentralized mining". The chain usually shows whether that is true, but someone has to look. This contract makes the look repeatable and puts the result on record: validators each read the pages themselves, and a verdict is stored only if a majority reach it independently.

- **Live site:** https://checker.brilliantnodes.com/
- **Demo video (50 seconds):** https://youtu.be/fFNq9PY1vSI
- **Contract (GenLayer Studio, studionet):** [`0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8`](https://explorer-studio.genlayer.com/address/0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8)
- **Source:** [`contracts/launch_claim_checker.py`](contracts/launch_claim_checker.py)
- **New: claim bounties.** Money behind a launch claim: a pot that pays the first person who shows the claim is false. [Jump to the section](#claim-bounties) · [try it](https://checker.brilliantnodes.com/bounties.html) · [what changed since the accepted version](MILESTONE.md)

## What a verdict means

A verdict is one of **supported**, **contradicted** or **undetermined**. It describes what the two supplied pages showed at the time of the check. It is not a proof about anything outside those pages. Both URLs are stored with every check, so anyone can see exactly what was examined.

## How a verdict is decided

1. **Read.** Every validator fetches both pages itself.
2. **Extract.** Its language model fills in a short fixed form: whether each page supports or contradicts the claim, the top miner's share of blocks, how many blocks that share covers, and whether the earliest blocks show an extra allocation. The model never chooses the verdict.
3. **Decide.** A rule table in plain Python turns those facts into the verdict.
4. **Agree.** A validator accepts the leader's result only if
   - the leader's own facts reproduce the leader's verdict under the rule table,
   - the validator reaches the same verdict by the same rule, and
   - for the mining rules, the top miner's share agrees within 2 percentage points.

   Free-text notes are stored but never compared. If validators do not agree, nothing is recorded.

### Rule table

| Claim | Contradicted when | Supported when |
|---|---|---|
| `DECENTRALIZED_MINING` | one miner has more than 50% of at least 50 inspected blocks, or the announcement itself contradicts the claim | the top miner has 33% or less of at least 50 inspected blocks |
| `NO_PREMINE`, `NO_FOUNDER_REWARD` | the explorer shows an extra allocation in the earliest blocks, or either page contradicts the claim | the explorer shows the earliest blocks with only the ordinary reward and agrees with the claim |
| `FAIR_LAUNCH` | any of the conditions above | the explorer shows clean earliest blocks and agrees with the claim |
| `CUSTOM` | either page contradicts the claim | the explorer agrees with the claim |

Everything else is **undetermined**. Two properties hold for every claim type:

- A project's own announcement can never produce "supported". That always needs explorer evidence.
- For `DECENTRALIZED_MINING` the numbers decide. The model's opinion of the explorer page is ignored.

The thresholds are returned by the `get_rules` view, so a verdict can be audited against them.

## Claim bounties

The checker says what two pages show. A **claim bounty** puts money behind that: GEN held by a second contract, [`contracts/launch_claim_bounties.py`](contracts/launch_claim_bounties.py), that pays the first person who shows, on the explorer pages the poster pinned, that a launch claim is false. The checker contract is unchanged.

- **Try it:** https://checker.brilliantnodes.com/bounties.html (GenLayer Studio, free temporary accounts) · [Bradbury view](https://checker.brilliantnodes.com/bounties.html?net=bradbury) (read-only)
- **Video (83 seconds, with voice-over):** https://checker.brilliantnodes.com/claim-bounties-demo.mp4
- **Contract on Studio:** [`0x234D26C4f2477EC4ef1b0FCA1f0ad0dA5c03bB8e`](https://explorer-studio.genlayer.com/address/0x234D26C4f2477EC4ef1b0FCA1f0ad0dA5c03bB8e)
- **Contract on Testnet Bradbury Phase 2:** [`0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f`](https://scan.bradbury.genlayer.com/address/0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f)
- **What changed since the accepted version:** [`MILESTONE.md`](MILESTONE.md)

Test GEN only. Examplecoin and Controlcoin, their pools and their explorer pages are fictional.

### How a bounty runs

1. **Post.** Anyone posts a bounty for one claim about one coin and deposits the pot. The poster pins the pages: a block page address with `{n}` for the block number, and/or one mining page. Hunters never supply an address. A bounty cannot be cancelled, shortened or topped up.
2. **File.** A hunter files a **sealed** claim: only `sha256("<bounty id>|<hunter address>|<rule>|<block>|<salt>")` goes on chain. Filing runs no model, reads no page and costs 2% of the pot (at least 0.001 GEN), which is burned: it stays in the contract and goes to nobody. Filings rank by the network's creation time of their transaction, to the microsecond.
3. **Judge.** Only the filer can have the filing judged, by revealing the rule, the block and the salt within 30 minutes. Every validator renders the pinned page, its model fills in a fixed form, and plain Python checks each value against that validator's own copy of the page.
4. **Pay.** A filing that is judged to pay takes the lead. It wins the whole pot as soon as no filing sent before it is still waiting to be judged (at most 60 minutes). With no paying claim by the expiry, the poster takes the pot back, from 60 minutes after the expiry.

### What decides a payout

| Rule | Pays when | Code checks on every validator | Validators must agree on |
|---|---|---|---|
| `P1` (claims `NO_PREMINE`, `NO_FOUNDER_REWARD`, `FAIR_LAUNCH`) | a block from 0 to 100 creates coins for someone beyond the ordinary block reward | the block number copied from the page equals the number revealed and is printed on the page; the amount parses exactly; the line that shows it is 12 to 200 characters and stands, as whole words and numbers, on one line of the validator's own copy | the outcome, and the amount exactly; the leader's line must stand on each accepting validator's own copy |
| `M1` (claims `DECENTRALIZED_MINING`, `FAIR_LAUNCH`) | one named miner has more than half of at least `min_blocks` blocks (500 to 10,000, set by the poster) | whole block counts printed on the page; the miner's name and its count on the same line; catch-all rows ("unknown", "others", a zero address) refused by a word list | the outcome, and the top miner by name |

Outcomes are `PAYS_P1`, `PAYS_M1`, `NO_PAY` (the filing is used up), `WRONG_PAGE` and `UNREADABLE` (the filing stays live for three tries). The three outcomes that pay nothing are not interchangeable: a validator that sees another one refuses the leader.

### Money and time

- **Pull payments.** Every payout, refund and refused payment is a credit that its owner takes with `withdraw()`. No call sends GEN to anyone but the caller.
- **No model where GEN arrives.** `post_bounty` and `file_claim`, the two calls that take GEN, run no model and read no page, and do not raise for any value of their arguments: a refused payment is credited straight back.
- **Every wei accounted for.** `totals()` returns locked, credited and burned GEN; their sum equals the contract's balance (checked at the end of both live runs). GEN sent with a call that takes none, or with a wrong number of arguments, stays in the contract outside that sum; we measured this on Studio.
- **Time is the transaction's own.** Whether a filing or a judgement was sent in time is decided by the transaction's timestamp, so nobody can make an in-time claim late by getting another transaction processed first. The bounty's clock never runs backwards and only releases money, retires filings whose 60 minutes have passed, and refuses a filing that arrives too late to be judged.

### Interface

| Method | Kind | Purpose |
|---|---|---|
| `post_bounty(claim_type, subject_name, block_url_template, mining_url, expires_at, min_blocks=1000)` | payable | Post a bounty; the value sent is the pot |
| `file_claim(bounty_id, digest)` | payable | File a sealed claim; the value sent must be the bounty's fee |
| `judge(bounty_id, rule, height, salt)` | write | Reveal the caller's own live filing and have it judged |
| `finalize(bounty_id)` | write | Anyone: credit the pot to the leading filer once the window has ended |
| `reclaim(bounty_id)` | write | The poster: take back an unclaimed pot, from 60 minutes after the expiry |
| `withdraw(amount=0)` | write | Send the caller what is credited to it |
| `get_bounty(id, at=0)`, `get_latest(limit=10, at=0)`, `get_count()`, `get_by_address(address)`, `get_claimable(address)`, `totals()`, `get_rules()` | view | The record, the money and the rules |

### Limits, stated plainly

- **A bounty trusts its pinned pages.** Whoever controls that site can make a claim look true or false, and the network follows redirects without saying so. A poster can also win its own bounty. An unclaimed bounty proves nothing; a won bounty means the pinned pages showed it.
- **P1 is a model's reading with code checks, not a proof.** Whether a block "creates coins beyond the ordinary block reward" is the model's reading; code then checks every copied value. It covers blocks 0 to 100 and the first 6,000 characters of a page. A coin with a disclosed developer fee in its early blocks pays out under it.
- **Amount formats.** Amounts must be printed with a dot for decimals and commas, or nothing, between thousands. An amount written with spaces between groups, or right next to another number, is refused as ambiguous, so a true allocation on such a page cannot be claimed.
- **For M1 the hunter picks the moment, and pool names are written by miners.** The catch-all word list is a filter, not a guarantee: a label in another language, or an unusual one, can pass it. Text a pool writes into a page can pay if every validator's model takes it for the table; the prompt tells the models not to.
- **M1 and luck.** A miner below half can show above half in one window by chance. With a true share of 45%, the chance is about 0.07% over 1,000 blocks and about 1.1% over 500 (binomial); at 48% it is about 9.7% and 17%. A hunter can look at many windows during a bounty's term, so the chance over the whole term is higher. The more blocks a bounty asks for, the less luck decides. A pot larger than the cost of renting a majority of the hash rate for `min_blocks` blocks pays for exactly that.
- **What P1 does not cover.** Token mints outside the first 101 blocks and instamines are not covered. For a coin whose first blocks are already mined, the answer is known the day the bounty is posted: such a bounty is a public statement with money behind it, not a contest.
- **Appeals** were not exercised in the live runs.
- **Sealing hides a claim only until it is revealed.** A reveal is public from the moment it is sent, even if the call is refused or the validators do not agree. If the filer's own judgement then fails (no majority, the page unreadable three times, or the 30 minutes run out), someone else can file the same claim and win. Reveal once the filing is on record, and early enough to try again. A filing processed only after a judgement has already paid out is refused and refunded, even if it was sent earlier.
- **Withdrawals on Bradbury** need an external-message fee allocation for the transfer to the caller's own address (as in `tools/bradbury/gl.mjs`); one sent without it can be dropped by the network. A withdrawal reaches the wallet when its transaction is finalized.

### Tests and reviews

```bash
PYTHONPATH=. pytest tests/direct/test_bounties.py      # 357 tests, web and model mocked (GenVM v0.2, as on Studio)
tools/test_v6.sh /path/to/venv                          # the same tests on GenVM v0.6 against the packed Bradbury build
PYTHONPATH=. python tools/mutate_bounties.py            # 199 deliberate breaks of the contract; the tests catch every one
genvm-lint check contracts/launch_claim_bounties.py
```

- The tests cover every refusal, every boundary second of the time rules, the validator agreement rules (including leaders that lie), sealed filings and wrong reveals, the queue with transactions processed out of the order they were sent, and a seeded random walk that checks after every step that all GEN paid in is locked, credited, burned or withdrawn, and that a won bounty's winner is the earliest-sent filing judged to pay.
- `tools/mutate_bounties.py` changes the contract in 199 ways, one at a time (a check removed, a boundary moved by one), and confirms that the tests fail each time. The few changes no test can see are listed, with the reason, at the top of that file.
- The design and the code each went through independent reviews before any live run. The first code review found three real holes (a copier processed first could win; block counts stored that no validator had checked; payouts on "unknown" rows). The fixes are what made filings sealed. The second review found no blockers and asked for the limits above to be stated. [`MILESTONE.md`](MILESTONE.md) lists what each review changed.

### Live runs

Every transaction of both runs is in the record files, and a script checks a record against the chain.

| | GenLayer Studio | Testnet Bradbury Phase 2 |
|---|---|---|
| Contract | [`0x234D…bB8e`](https://explorer-studio.genlayer.com/address/0x234D26C4f2477EC4ef1b0FCA1f0ad0dA5c03bB8e) | [`0x8d2A…614f`](https://scan.bradbury.genlayer.com/address/0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f) |
| Code deployed | the source file | the packed GenVM v0.6 build in `bradbury/build/` |
| Transactions | 46 plus the deployment | 15 plus the deployment |
| As expected | 46 of 46 | 15 of 15 |
| Checks against the contract's views | 16 of 16 | 19 of 20 (see below) |
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

```bash
pip install genlayer-py==0.18.0
python tools/verify_bounties.py                         # the Studio record against the chain: code, every transaction, every digest, final states, balance
python tools/bounty.py latest                           # LCB_ADDRESS=<contract>; post, file, judge, finalize, reclaim, withdraw from the command line
```

## Why this needs GenLayer

The inputs are live web pages and the reading step needs a language model. A single server doing that is a single party to trust. Here the reading is done independently by several validators running different models, and the part that matters, the verdict, comes from deterministic code that each of them runs on its own extraction.

## Contract interface

| Method | Kind | Purpose |
|---|---|---|
| `check_claim(announcement_url, explorer_url, claim_type, claim_text="")` | write | Runs a check and stores the result |
| `get_check(check_id)` | view | One stored check |
| `get_latest(limit=10)` | view | Most recent checks, newest first (up to 50) |
| `get_checks_by(address)` | view | Ids of the checks an address requested |
| `get_count()` | view | Number of stored checks |
| `get_rules()` | view | The rule table's thresholds |

Input rules: `http` or `https` URLs only, at most 300 characters, no private or local addresses. `claim_text` is at most 400 characters and is required for `CUSTOM`.

## Safeguards against misleading pages

- Page text is passed to the model as data inside fixed delimiters, and any copy of those delimiters inside a page is removed first.
- The model can only return fixed options and numbers. Unknown values fall back to the most cautious option.
- The verdict is computed by code, and each validator extracts on its own, so a page that tries to instruct the model has to mislead several different models in the same way.
- An explorer page that cannot be read records nothing. An announcement that cannot be read is treated as silent.

## Tests

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/direct     # 62 tests, web and model mocked
genvm-lint check contracts/launch_claim_checker.py
```

These are the checker's tests; the bounties contract has its own (see [Claim bounties](#tests-and-reviews)). The direct tests cover the rule table at every threshold, the validator agreement rules (including a leader that lies about its own facts), input checks, storage, and a page that tries to close the data block and dictate the answer. The page snapshots under `tests/snapshots` are reconstructions written for testing, not copies of live pages.

## Command line

```bash
pip install genlayer-py==0.18.0
python tools/check.py ANNOUNCEMENT_URL EXPLORER_URL DECENTRALIZED_MINING --text "the claim in the project's words"
```

It sends the check, waits for consensus and prints the recorded result as JSON. No wallet or funds are needed on Studio: a throwaway key is made for the run unless `LCC_PRIVATE_KEY` is set. `LCC_ADDRESS` points it at another deployment, which is how a team keeps its own working record separate from the public demo contract.

## Monitoring

The verdicts depend on how the validators' models read a page, and models change. [`tools/canary.py`](tools/canary.py) reruns the four fictional examples, whose pages never change, and fails if any verdict or rule differs from the expected one. A [scheduled workflow](.github/workflows/canary.yml) runs it every day.

## Also on Testnet Bradbury Phase 2

The same contract (GenVM v0.6 build, unchanged tests passing) is live on Bradbury Phase 2 at [`0x9639…dA9C`](https://scan.bradbury.genlayer.com/address/0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C). The four canary cases gave the expected verdicts there, each decided by 5 validators: Examplecoin contradicted twice, Controlcoin supported twice. Details and transaction links: [`bradbury/README.md`](bradbury/README.md).

The website runs on both networks: switch to **Bradbury testnet** at the top of the page, or open [checker.brilliantnodes.com/?net=bradbury](https://checker.brilliantnodes.com/?net=bradbury). Recorded checks load at once with no wallet; a new check there needs MetaMask with Bradbury test GEN. Studio keeps the free temporary account.

## Live runs on GenLayer Studio

Run on 14 Nov 2026 against the deployed contract, with the Studio validators' models fetching the pages themselves. The examples use two fictional coins whose announcement and explorer pages are test pages hosted with the site: Examplecoin's claims fail and Controlcoin's hold. No real project is used as an example.

| Case | Explorer page shows | Recorded runs | Outcome |
|---|---|---|---|
| Examplecoin, `DECENTRALIZED_MINING` | one miner with 168 of 200 blocks | 4 | contradicted every time (rule `M1`), share read as 84.00% |
| Examplecoin, `NO_FOUNDER_REWARD` and `NO_PREMINE` | block 1 with a 2,000,000 EXM founders output | 3 | contradicted every time (rule `P1`) |
| Controlcoin, `NO_FOUNDER_REWARD` and `NO_PREMINE` | first five blocks, each a single 50 CTL miner reward | 4 | supported every time (rule `P2`) |
| Controlcoin, `DECENTRALIZED_MINING` | top miner with 36 of 200 blocks | 3 | supported every time (rule `M2`), share read as 18.00% |
| Unreachable explorer | a host that does not exist | 1 | validators agreed in one round that the page could not be read; nothing recorded |

Every recorded run reached a majority in a single round, and no case produced two different verdicts.

Earlier deployments were also run against live explorers of real chains, including pages whose figures move between reads. Those runs led to three changes:

- **Script-loaded pages.** Explorer pages that load their data with scripts returned no figures at first, and the verdict was, correctly, undetermined. The contract now waits 4 seconds after the page loads.
- **Unreadable explorer pages.** At first the leader raised an error, validators rejected it, and the transaction went through four leader rotations before failing. Now "could not be read" is an outcome validators agree on, only when they cannot read the page either. It settles in one round and nothing is recorded.
- **Live drift.** On a live mining summary the top miner's share moved by up to 2.8 points over an hour. Every run still reached the same verdict in one round.

## Who uses it

The checker was built by Brilliant Nodes, a small desk that mines new proof-of-work coins and has to decide quickly whether a launch is what it says it is. Checking the launch claims against the chain is a step in that vetting: each candidate's claims are run through the contract before the candidate is scored.

## Front end

`web/` is a small static site (Vite, `genlayer-js`). It reads the contract, lets a visitor run a check with a browser wallet or with a temporary in-browser Studio account, follows the transaction through every consensus stage, and explains the outcome when validators do not agree or the check could not be carried out. The built site is committed under `docs/` for GitHub Pages. A 50-second demo video is on the site and on [YouTube](https://youtu.be/fFNq9PY1vSI).

Both account paths were tested end to end against the live contract on the live site.

- **Wallet path:** the real MetaMask extension (13.56.0) in Chrome 153: connect, add and switch to the Studio network, approve the account, confirm the transaction, follow it to Accepted, show the recorded card. MetaMask shows no site warning for `checker.brilliantnodes.com`. The site adds the network before it asks for the account, because MetaMask refuses to send from an account that was approved before the network existed. The wallet is only asked for accounts, the network and the transaction. It is not asked to install anything.
- **Temporary account path:** Chrome 153, Firefox 155 and WebKit 26.6 (the Safari engine) on desktop, plus an iPhone 15 profile in WebKit and a Pixel 7 profile in Chrome. Every run reached Accepted and showed its card. The phone runs are device profiles in desktop engines, not physical phones.
- **Layout:** no sideways scrolling at 320, 393 and 810 pixels wide, with every section open.
- **Dropped connection:** if the send fails on a network error, a temporary account retries once on its own. A wallet is never asked twice. This was tested by cutting the first send.

```bash
cd web && npm install && npm run dev     # local
npm run build                            # writes ../docs
```

The bounties page (`web/bounties.html`, `web/src/bounties.js`) was tested the same way in headless Chrome against the live contract: post, file a sealed claim, reveal and judge, withdraw, the refusal messages, a judgement asked for after the browser's storage was cleared, no sideways scrolling at 320, 393 and 810 pixels, and the read-only Bradbury view.

After a new deployment, set the contract addresses in `web/src/config.js`.

## Why these thresholds

- **Above 50%: contradicted.** A miner with most of the hash power can out-build everyone else and rewrite recent blocks. No reading of "decentralized" survives that.
- **At or below 33%: supported.** Above a third, withholding blocks pays for a miner however poorly connected it is (Eyal and Sirer, "Majority is not Enough", 2014). At or below a third the largest miner is under that bound.
- **Between the two: undetermined.** The claim is neither clearly true nor clearly false.
- **At least 50 blocks.** With fewer, a miner holding a third of the hash power is too likely to show a majority by luck. At 50 blocks that chance is under 1% (binomial, 0.49%).
- **2 points of tolerance.** A live explorer moves by a block or two between two validators' reads. At 145 blocks one block is 0.7 points.
- **6,000 characters per page.** Enough for a block page or a mining summary in every live run so far, and it bounds what each validator's model has to read.

## Scope

- A verdict covers the two supplied pages at the time of the check. The stored URLs show exactly what was examined.
- The contract does not know which explorer is authoritative for a chain. A requester who supplies a misleading explorer page gets a verdict about that page, with the page on record.
- Notes attached to a check are written by one validator and are labelled on the site as not verified by the others.
- For claim types without numbers, the verdict rests on each validator's model reading the page the same way, and a majority must do so independently.
- Deployed on GenLayer Studio and on Testnet Bradbury Phase 2. Test GEN only.
- Appeals were not exercised in any live run.

## License

MIT. See [LICENSE](LICENSE).

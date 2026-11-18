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
- **Video (84 seconds, with voice-over):** https://checker.brilliantnodes.com/claim-bounties-demo.mp4
- **Contract on Studio:** [`0x583995CE8814C987e888070352A3F1d3AF9BBDca`](https://explorer-studio.genlayer.com/address/0x583995CE8814C987e888070352A3F1d3AF9BBDca) · [open it in GenLayer Studio](https://studio.genlayer.com/?import-contract=0x583995CE8814C987e888070352A3F1d3AF9BBDca)
- **Contract on Testnet Bradbury Phase 2:** [`0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b`](https://scan.bradbury.genlayer.com/address/0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b)
- **What changed since the accepted version:** [`MILESTONE.md`](MILESTONE.md)

Test GEN only. Examplecoin and Controlcoin, their pools and their explorer pages are fictional.

### Try it in two minutes

1. Open https://checker.brilliantnodes.com/bounties.html. No wallet is needed.
2. Under **Accounts**, click **Use a temporary account** for the Poster and for the Hunter. Each gets test GEN from Studio's faucet.
3. Under **Post a bounty**, click the example **Examplecoin, no founder reward**, then **Post the bounty as Poster**.
4. On the new bounty, click **File block claim** (as Hunter, block 1). The chain now shows a digest, not the block.
5. Click **Judge**: the page reveals the claim. The validators read Examplecoin's block 1, which pays its founders 2,000,000 EXM, and the bounty is won. Click **Withdraw** next to the Hunter's balance.

The same steps were run from the page in a browser against the deployed contract; every transaction is in [`examples/live/bounties-site-studio.json`](examples/live/bounties-site-studio.json).

### How a bounty runs

1. **Post.** Anyone posts a bounty for one claim about one coin and deposits the pot. The poster pins the pages: a block page address with `{n}` for the block number, and/or one mining page. Hunters never supply an address. A bounty cannot be cancelled, shortened or topped up.
2. **File.** A hunter files a **sealed** claim: only a digest goes on chain. The digest is the sha256, in lower-case hex, of `<bounty id>|<hunter address, lower case>|<rule>|<block>|<salt>`, where the rule is `P1` or `M1`, the block is `0` for `M1`, and the salt is 32 random lower-case hex characters. Filing runs no model, reads no page and costs 2% of the pot (at least 0.001 GEN), which is burned: it stays in the contract and goes to nobody. Filings rank by the network's creation time of their transaction (stamped to the microsecond on Studio, to the second on Bradbury) and then by the order in which they were processed.
3. **Judge.** Only the filer can have the filing judged, by revealing the rule, the block and the salt within 30 minutes. Every validator renders the pinned page, its model fills in a fixed form, and plain Python checks each value against that validator's own copy of the page.
4. **Pay.** A filing that is judged to pay takes the lead. It wins the whole pot as soon as no filing sent before it is still waiting to be judged (at most 60 minutes). With no paying claim by the expiry, the poster takes the pot back, from 60 minutes after the expiry.

### What decides a payout

| Rule | Pays when | Code checks on every validator | Validators must agree on |
|---|---|---|---|
| `P1` (claims `NO_PREMINE`, `NO_FOUNDER_REWARD`, `FAIR_LAUNCH`) | a block from 0 to 100 creates coins for someone beyond the ordinary block reward | the block number copied from the page equals the number revealed and is printed on the page; the amount parses exactly; the line that shows it is 12 to 200 characters and stands, as whole words and numbers, on one line of the validator's own copy | the outcome, and the amount exactly; the leader's line must stand on each accepting validator's own copy |
| `M1` (claims `DECENTRALIZED_MINING`, `FAIR_LAUNCH`) | one named miner has more than half of at least `min_blocks` blocks (500 to 10,000, set by the poster) | whole block counts printed on the page; the miner's name and its count on the same line; a row whose line has a catch-all word ("unknown", "others", "burn") or the all-zero or 0x…dead address, in full or shortened ("0x0000…0000"), is refused; a total that is the same number as the miner's count must be printed twice | the outcome, and the top miner by name |

Outcomes are `PAYS_P1`, `PAYS_M1`, `NO_PAY` (the filing is used up), `WRONG_PAGE` and `UNREADABLE` (the filing stays live for three tries). The three outcomes that pay nothing are not interchangeable: a validator that sees another one refuses the leader.

### Money and time

- **Pull payments.** Every payout, refund and refused payment is a credit that its owner takes with `withdraw()`. No call sends GEN to anyone but the caller.
- **No model where GEN arrives.** `post_bounty` and `file_claim`, the two calls that take GEN, run no model and read no page, and do not raise for any value of their arguments: a refused payment is credited straight back.
- **Every wei accounted for.** `totals()` returns locked, credited and burned GEN; their sum equals the contract's balance (checked at the end of both live runs). GEN sent with a call that takes none, or with a wrong number of arguments, stays in the contract outside that sum.
- **Time is the transaction's own.** Whether a filing or a judgement was sent in time is decided by the transaction's timestamp, so nobody can make an in-time claim late by getting another transaction processed first. The bounty's clock is the latest timestamp that bounty has seen. It never runs backwards and only releases money, retires filings whose 60 minutes have passed, and refuses a filing that arrives too late to be judged.
- **Measured, with transactions.** What the contract relies on about the network was measured on Studio with a small probe contract, [`tools/probes/probe.py`](tools/probes/probe.py): the transaction time a contract sees, what happens to GEN sent with a call that raises or that takes none, sha256, how `web.render` returns a table row, a missing page and a redirect. The eight measurements and their transaction hashes are in [`examples/live/network-probes-studio.json`](examples/live/network-probes-studio.json). On Bradbury the creation time of a transaction is stamped in whole seconds; that is read from the transactions of the Bradbury run.

### Bounties contract interface

| Method | Kind | Purpose |
|---|---|---|
| `post_bounty(claim_type, subject_name, block_url_template, mining_url, expires_at, min_blocks=1000)` | payable | Post a bounty; the value sent is the pot |
| `file_claim(bounty_id, digest)` | payable | File a sealed claim; the value sent must be the bounty's fee |
| `judge(bounty_id, rule, height, salt)` | write | Reveal the caller's own live filing and have it judged |
| `finalize(bounty_id)` | write | Anyone: credit the pot to the leading filer once the window has ended |
| `reclaim(bounty_id)` | write | The poster: take back an unclaimed pot, from 60 minutes after the expiry |
| `withdraw(amount=0)` | write | Send the caller what is credited to it |
| `get_bounty(bounty_id, at=0)` | view | One bounty with its filings and log; with `at` set to the current unix time, the state as a transaction sent now would find it |
| `get_latest(limit=10, at=0)` | view | The newest bounties (at most 20) |
| `get_count()`, `get_by_address(address)`, `get_claimable(address)`, `totals()`, `get_rules()` | view | The number of bounties, an address's bounties (its latest 200), its credit, the money, the rules |

### Limits, stated plainly

- **A bounty trusts its pinned pages.** Whoever controls that site can make a claim look true or false, and the network follows redirects without saying so. A poster can also win its own bounty. An unclaimed bounty proves nothing; a won bounty means the pinned pages showed it.
- **Both rules are a model's reading with code checks, not a proof.** Whether a block "creates coins beyond the ordinary block reward", which amount on the page that is, which row of a mining page is the top miner and which number is the total: those are the model's readings. Code then checks that every value is printed on the validator's own copy; it cannot see a majority of models taking a header for a miner. Both rules read the first 6,000 characters of a page; P1 covers blocks 0 to 100. A coin with a disclosed developer fee in its early blocks pays out under P1.
- **Number formats.** Amounts and block counts must be printed with a dot for decimals and commas, or nothing, between thousands. An amount with exactly three decimals, no comma and a whole part other than 0 ("2000000.125") is refused, because "12.450" is 12,450 in much of Europe. A number that could be one group of a longer number written with spaces is refused as ambiguous: "2" in "2 000 000"; "500.00" right after another short number, as in "1 500.00", also when that "1" is an output index or a rank; a number of up to three digits right before a three-digit column, as in "840 512 MH/s"; an amount with exactly three decimals right before another number, as in "0.125 3 confirmations". The page need not have written anything with spaces for this to apply, and for rule P1 it is enough that the page line has the amount once in such a place. A middle dot between two numbers joins them like a comma. A true allocation or count printed in one of these ways cannot be claimed, and neither can an allocation whose page line is shorter than 12 characters.
- **For M1 the hunter picks the moment, and pool names are written by miners.** The catch-all word list is a filter, not a guarantee, in both directions: a label in another language, or an unusual one, can pass it, and a real name that contains a listed word is refused. Of burn addresses it knows only the all-zero address and the 0x…dead address. Text a pool writes into a page can pay if every validator's model takes it for the table; the prompt tells the models not to.
- **What a seal hides.** A sealed filing does not show which block it is about, nor which rule where a bounty pays on both; most claim types pay on one rule only. Under M1 there is only one possible claim, so a seal hides nothing there. A filing made blind and kept live (it costs the fee every 30 minutes) outranks a later hunter whose reveal shows that the mining page now pays. The same holds under P1 for a poster who knows which block pays.
- **M1 and luck.** A miner below half can show above half in one window by chance. With a true share of 45%, the chance is about 0.07% over 1,000 blocks and about 1.1% over 500 (binomial); at 48% it is about 9.7% and 17%. A hunter can look at many windows during a bounty's term, so the chance over the whole term is higher. The more blocks a bounty asks for, the less luck decides. A pot larger than the cost of renting a majority of the hash rate for `min_blocks` blocks pays for exactly that.
- **What P1 does not cover.** Token mints outside the first 101 blocks and instamines are not covered. For a coin whose first blocks are already mined, the answer is known the day the bounty is posted: such a bounty is a public statement with money behind it, not a contest.
- **A reveal is public.** It is public from the moment it is sent, even if the call is refused or the validators do not agree. If the filer's own judgement then does not pay (no majority, a reading that finds nothing, three judgements that end with the page unreadable, the wrong page or a model answer out of form, or the 30 minutes run out), someone else can file the same claim and win. Reveal once the filing is on record, and early enough to try again.
- **A filing processed late can be refused.** A filing that is processed only after another filing has been judged to pay (the bounty is then provisional or won) is refused and refunded, even if it was sent earlier. On a bounty nobody has touched for a while the bounty's clock lags, and a filing processed very late can still be taken.
- **Withdrawals on Bradbury** need an external-message fee allocation for the transfer to the caller's own address (as in `tools/bradbury/gl.mjs`). One sent without it can be dropped by the network, and the amount withdrawn is then gone: the credit is cleared and the GEN stays in the contract, outside `totals()`. A withdrawal reaches the wallet when its transaction is finalized.
- **Appeals** were not exercised in the live runs.
- **Where each limit is stated.** All of the above are in this README. The contract's own description states those that concern the contract. The site shows the ones a user of the page needs.

### Who would post a bounty

- **A project team**, on its own launch claims: a pot that anyone can take by showing the claim is false says more than the sentence "no premine" does.
- **Someone who has to vouch for a coin**: a listing desk, a pool or a community fund can pay for the look before it lists, mines or funds, and only pays if something is found.
- **Us.** Brilliant Nodes mines new proof-of-work coins and already runs every candidate's claims through the checker. A bounty is the next step for a claim that matters to a decision.

No outside party has posted a bounty yet. Everything on record was done by us with test GEN, on fictional coins.

### Tests and reviews

```bash
PYTHONPATH=. pytest tests/direct/test_bounties.py      # 419 tests, web and model mocked (GenVM v0.2, as on Studio)
tools/test_v6.sh /path/to/venv                          # the same tests on GenVM v0.6 against the packed Bradbury build
PYTHONPATH=. python tools/mutate_bounties.py            # 239 deliberate breaks of the contract; the tests catch every one
genvm-lint check contracts/launch_claim_bounties.py
```

- The tests cover every refusal, every boundary second of the time rules, the validator agreement rules (including leaders that lie), sealed filings and wrong reveals, the queue with transactions processed out of the order they were sent, the limits listed above as they are (tests named `test_known_limit_...`), and a seeded random walk that checks after every step that all GEN paid in is locked, credited, burned or withdrawn, and that a won bounty's winner is the earliest-sent filing judged to pay.
- `tools/mutate_bounties.py` changes the contract in 239 ways, one at a time (a check removed, a boundary moved by one), and confirms that the tests fail each time. The few changes that make no difference to what the contract does are listed, with the reason, at the top of that file.
- **Reviews.** The design and the code were reviewed six times before this version, each time by a separate AI reviewer session (Claude) that was given a written brief and the repository and had not seen the work being done. The contract was built by an AI session as well, working for Brilliant Nodes. The first code review found three real holes (a copier processed first could win; block counts stored that no validator had checked; payouts on "unknown" rows); the fixes are what made filings sealed. [`reviews/README.md`](reviews/README.md) records each review: what it was asked, its verdict, what it found and what changed.

### Live runs

Every transaction of both runs is in the record files, and a script checks each record against the chain.

| | GenLayer Studio | Testnet Bradbury Phase 2 |
|---|---|---|
| Contract | [`0x5839…BDca`](https://explorer-studio.genlayer.com/address/0x583995CE8814C987e888070352A3F1d3AF9BBDca) | [`0xc437…257b`](https://scan.bradbury.genlayer.com/address/0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b) |
| Code deployed | the source file | the packed GenVM v0.6 build in `bradbury/build/` |
| Transactions after the deployment | 46 | 41 |
| Came out as expected | 46 of 46 | 41 of 41 |
| Checks against the contract's views | 16 of 16 | 46 of 46 |
| Validators | 5 per transaction. Studio accepts a transaction as soon as a majority has voted: the record shows 3 to 5 of 5 agreeing at that moment | 5 per transaction; on the 8 judgements, where each validator's own model reads the page, 3 to 5 of 5 gave the leader's result |
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

At the end of both runs the contract's balance equalled locked + credited + burned, and the burned amount equalled the fees of the ten filings taken. All 46 Studio transactions and all 41 Bradbury transactions came out as expected, and so did every check against the contract's views (16 on Studio, 46 on Bradbury). Bradbury judgements, where validators read the page, took 34 to 210 seconds.

```bash
python -m venv venv-live && source venv-live/bin/activate   # its own environment: the test tools pin an older genlayer-py
pip install genlayer-py==0.18.0
python tools/verify_bounties.py                         # the Studio record against the chain
(cd tools/bradbury && npm ci)
python tools/verify_bounties_bradbury.py                # the Bradbury record against the chain
python tools/bounty.py latest                           # LCB_ADDRESS=<contract>; post, file, judge, finalize, reclaim, withdraw from the command line
```

Both verifiers read only. They check that the deployed code is this repository's code byte for byte (on Bradbury: that the build is what `tools/port_bradbury.py --pack` makes from the source, and that the deployed code is that build), and that every recorded transaction is on the chain with the recorded sender, method and arguments (decoded from the call data on the chain), consensus result, validator votes and execution result. They recompute every digest from the revealed rule, block and salt, read every bounty's final state from the contract, and compare the contract's balance with `totals()`.

## Why this needs GenLayer

The inputs are live web pages and the reading step needs a language model. A single server doing that is a single party to trust. Here the reading is done independently by several validators running different models, and the part that matters, the verdict, comes from deterministic code that each of them runs on its own extraction.

## Checker contract interface

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

## Checker tests

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/direct/test_checker.py     # 62 tests, web and model mocked
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

## The checker on Testnet Bradbury Phase 2

The checker contract (GenVM v0.6 build, unchanged tests passing) is live on Bradbury Phase 2 at [`0x9639…dA9C`](https://scan.bradbury.genlayer.com/address/0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C). The four canary cases gave the expected verdicts there, each decided by 5 validators: Examplecoin contradicted twice, Controlcoin supported twice. Details and transaction links: [`bradbury/README.md`](bradbury/README.md).

The website runs on both networks: switch to **Bradbury testnet** at the top of the page, or open [checker.brilliantnodes.com/?net=bradbury](https://checker.brilliantnodes.com/?net=bradbury). Recorded checks load at once with no wallet; a new check there needs MetaMask with Bradbury test GEN. Studio keeps the free temporary account.

## Checker live runs on GenLayer Studio

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

# Launch Claim Checker

A GenLayer Intelligent Contract that checks a crypto launch claim against two public pages: the project's announcement and a block explorer page.

New coins routinely launch with claims such as "no premine", "no founder reward" or "decentralized mining". The chain usually shows whether that is true, but someone has to look. This contract makes the look repeatable and puts the result on record: validators each read the pages themselves, and a verdict is stored only if a majority reach it independently.

- **Live site:** https://brilliantnodes.github.io/launch-claim-checker/
- **Demo video (50 seconds):** https://youtu.be/CT43rmc5cAA
- **Contract (GenLayer Studio, studionet):** [`0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8`](https://explorer-studio.genlayer.com/address/0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8)
- **Source:** [`contracts/launch_claim_checker.py`](contracts/launch_claim_checker.py)

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

The direct tests cover the rule table at every threshold, the validator agreement rules (including a leader that lies about its own facts), input checks, storage, and a page that tries to close the data block and dictate the answer. The page snapshots under `tests/snapshots` are reconstructions written for testing, not copies of live pages.

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

`web/` is a small static site (Vite, `genlayer-js`). It reads the contract, lets a visitor run a check with a browser wallet or with a temporary in-browser Studio account, follows the transaction through every consensus stage, and explains the outcome when validators do not agree or the check could not be carried out. The built site is committed under `docs/` for GitHub Pages. A 50-second demo video is on the site and on [YouTube](https://youtu.be/CT43rmc5cAA).

Both account paths were tested end to end against the live contract in headless Chrome: the temporary account, and the wallet path with a stand-in EIP-1193 provider that signs with a throwaway key (connect, add and switch to the Studio network, send, follow to Accepted, show the recorded card). The wallet is only asked for accounts, the network and the transaction. It is not asked to install anything.

```bash
cd web && npm install && npm run dev     # local
npm run build                            # writes ../docs
```

After a new deployment, set the contract address in `web/src/config.js`.

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
- Deployed on GenLayer Studio.

## License

MIT. See [LICENSE](LICENSE).

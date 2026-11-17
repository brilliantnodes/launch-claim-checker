# Launch Claim Checker on Testnet Bradbury Phase 2

On the website: [checker.brilliantnodes.com/?net=bradbury](https://checker.brilliantnodes.com/?net=bradbury) lists these checks and can run a new one with MetaMask. Check #5 was run through the site itself on 15 Nov 2026 (transaction [0x4147…378a](https://scan.bradbury.genlayer.com/tx/0x414702a821ef4d9d310d12b95ed06f87046f3137d5ff4c2eec55f9bb834a378a), accepted in about 90 seconds).

The contract also runs on **GenLayer Testnet Bradbury Phase 2** (chain 4221), whose validators use real models and real web access. Recorded 15 Nov 2026 with a throwaway account holding faucet GEN; fictional coins only.

- Contract: [`0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C`](https://scan.bradbury.genlayer.com/address/0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C) (deploy [0xf777…162c](https://scan.bradbury.genlayer.com/tx/0xf7773f5e225ff998ef130a05a9c24a8e4d44945b35188f5454f9c08466e5162c), 5 of 5 validators).
- Build: [`build/launch_claim_checker.py`](build/launch_claim_checker.py), made from [`../contracts/launch_claim_checker.py`](../contracts/launch_claim_checker.py) by `port.py` in [brilliantnodes/genlayer-patterns](https://github.com/brilliantnodes/genlayer-patterns/tree/main/bradbury) (GenVM v0.6 dialect: header, imports and API renames, docstrings stripped; the syntax tree is asserted otherwise unchanged).
- Tests: the unchanged 62 direct-mode tests pass against the Bradbury build on GenVM v0.6 (genlayer-test 0.30.0rc2, `GENVM_VERSION=v0.6.0-rc10`).

## The four canary cases on Bradbury

| Check | Coin | Claim | Verdict, rule | Validators agreeing | Transaction |
|---|---|---|---|---|---|
| 1 | Examplecoin (fictional) | DECENTRALIZED_MINING | **contradicted**, M1_TOP_MINER_ABOVE_HALF | 5 of 5 | [0x247a…a6f2](https://scan.bradbury.genlayer.com/tx/0x247aaa917692074610915e3758594aad43ccd4641b1bab625ac4c7e920bea6f2) |
| 2 | Examplecoin (fictional) | NO_FOUNDER_REWARD | **contradicted**, P1_EARLY_ALLOCATION_FOUND | 5 of 5 | [0x990e…45fc](https://scan.bradbury.genlayer.com/tx/0x990eb7a1aa430ae77d3d7d6c06f7f6528fbe332ce5f2ebcb3bebd5e37d4a45fc) |
| 3 | Controlcoin (fictional) | NO_FOUNDER_REWARD | **supported**, P2_EARLY_BLOCKS_SHOWN_CLEAN | 5 of 5 | [0xc8fa…8d5b](https://scan.bradbury.genlayer.com/tx/0xc8fac0ee8b36fff4f8494afd602e27ae229f8907eefe2baf14bc7e153af58d5b) |
| 4 | Controlcoin (fictional) | DECENTRALIZED_MINING | **supported**, M2_TOP_MINER_AT_OR_BELOW_THIRD | 5 of 5 | [0x1b92…9c63](https://scan.bradbury.genlayer.com/tx/0x1b9260cdfabe2f1cb000bbd4e12cb9941da452303be09c94ca1fc7c006789c63) |

All four match the expected verdicts (the same cases the daily Canary runs on Studio). Raw values: [`results/checks.json`](results/checks.json); script: [`live_cases.py`](live_cases.py).

**Recorded as it happened:** the first attempt at the Controlcoin "no founder reward" check finalized with **NO_MAJORITY** (the validators did not agree) and stored nothing ([0x651b…a27a](https://scan.bradbury.genlayer.com/tx/0x651b35b7e6dcc12eeea1f34dde96eff3123560d085df4e07aeb7ff28bc68a27a)); the retry above was accepted 5 of 5. That is the design: without agreement, no verdict is recorded.

The website reads these checks at [checker.brilliantnodes.com/?net=bradbury](https://checker.brilliantnodes.com/?net=bradbury) and can run a new one with MetaMask and Bradbury test GEN. A free try with a temporary account stays on GenLayer Studio.

## Claim bounties on Bradbury

The second contract, `LaunchClaimBounties`, also runs here: [`0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f`](https://scan.bradbury.genlayer.com/address/0x8d2AA0F7eA864909391C76c6f55BddCdA64a614f).

- Build: [`build/launch_claim_bounties.py`](build/launch_claim_bounties.py), made from [`../contracts/launch_claim_bounties.py`](../contracts/launch_claim_bounties.py) by `tools/port_bradbury.py --pack` (the GenVM v0.6 dialect, packed into a short stub that decompresses and runs it). [`build/launch_claim_bounties.unpacked.py`](build/launch_claim_bounties.unpacked.py) is the same code before packing, for reading.
- Tests: the same 357 direct-mode tests pass against this build on GenVM v0.6 (`tools/test_v6.sh`).
- Live run of 17 Nov 2026: 15 transactions after the deployment, all as expected, with rule P1 and rule M1 both paid, a clean coin's claim surviving, and the pot reclaimed. Details and transaction links are in the main [README](../README.md#live-runs); the record is [`../examples/live/bounties-bradbury.json`](../examples/live/bounties-bradbury.json).
- `python tools/verify_bounties_bradbury.py` reads the deployment transaction and every recorded transaction from Bradbury and checks that the deployed code is this build byte for byte, that every result matches the record, that every revealed claim gives the digest that was filed, and that each withdrawal carries one transfer to its own sender.
- The website's [Bradbury view](https://checker.brilliantnodes.com/bounties.html?net=bradbury) reads these bounties without a wallet.

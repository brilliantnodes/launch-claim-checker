# Launch Claim Checker on Testnet Bradbury Phase 2

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

The website at checker.brilliantnodes.com stays on GenLayer Studio, where anyone can try it with Studio's free test accounts.

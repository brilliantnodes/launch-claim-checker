# Live records of the second v2 build (superseded)

These records are from the second build of `contracts/launch_claim_checker_v2.py` (commit 0fd8c39, the fixes after review 2), run on 24 Nov 2026. Review 3 ([`reviews/v2/README.md`](../../../reviews/v2/README.md)) then found one more blocker (a `BOTH:P1` verdict on a block from 2 to 100 could be bonded but never overturned) and smaller problems; the contract was fixed again (commit 8b9496b), deployed again, and the live runs were repeated. The current records are the ones in `examples/live/` (see [`MILESTONE-2.md`](../../../MILESTONE-2.md)). These are kept unchanged as a record of what was run.

- `v2-studio.json`: bonds and challenges on Studio `0xf7A2399D91144AdF06550889fE16e919dD685F61`; 45 of 45 transactions as expected.
- `v2-site-studio.json`: the page clicked through on Studio `0xE9f2cA19bf87110fc188030264beb1c0c0C9Dd57`; 8 of 8.
- `v2-bradbury.json`: the same stories on Bradbury `0x2cc43Dab1D122258bAc2653877C6c100e8816bFa`; 44 of 45 (a mining check had no majority and agreed when sent again).
- `v2-bradbury-stopped.json`: a first Bradbury attempt on `0x106980F7bA1C2101488b99f13df51b07C0DAAc16`, stopped.

## A correction to the stopped attempt's record

Review 3 read the stopped deployment and found its record's `stopped` note wrong in two places; the record itself is left as it was written:

- **Case D (Veercoin) was decided.** The run sent its re-check about a minute before it was stopped, and the record was not saved after it: the transaction is missing from the record's 26 steps. On chain, `get_check("4")` on `0x1069…Ac16` shows the bond `NOT_CONFIRMED` by `D1_EXPLORERS_DISAGREE`, re-checked at 16:50:52 UTC, inside its window. So only case C's re-check window closed undecided, not C's and D's.
- **What is left on that deployment.** Cases A and B were decided (upheld, released) but never collected; case D was decided but not collected; cases C and E were bonded and challenged and never settled. Their test GEN stays in the contract until someone settles and collects them.

## Verifying these records

The builds and tools have changed since: to verify these records, check out commit df3567b (the tools and builds they were made with) and run `tools/verify_v2.py` and `tools/verify_v2_bradbury.py` there. (The records' Bradbury build has `build_sha256` `aa32cf2f…`; later Phase 2 builds differ.)

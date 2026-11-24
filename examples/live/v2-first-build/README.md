# Live records of the first v2 build (superseded)

These four records are from the first build of `contracts/launch_claim_checker_v2.py` (commit 26b1a6f), run on 24 Nov 2026 before the independent review of that build ([`reviews/v2/README.md`](../../../reviews/v2/README.md)). The review found three blockers, the contract was fixed (commit 0fd8c39) and deployed again, and the live runs were repeated; the current records are the ones in `examples/live/` (see [`MILESTONE-2.md`](../../../MILESTONE-2.md)). These are kept unchanged as a record of what was run.

- `v2-studio-checks.json`: nine free checks on Studio `0x775B1f1E20c23C3A5b59135b1a70f2c0C29294c5`; the late bond was refused and its 1 GEN stays credited there.
- `v2-studio-money.json`: bonds and challenges on Studio `0x9aA412AdaB30Fe4A4f90D9C84421AB0C7a14436F`.
- `v2-bradbury.json`: the same stories on Bradbury `0xC1b4AD9cd4D1609461B6eabbBb78a0B1F4FC8E22`.
- `v2-site-studio.json`: the page clicked through on Studio `0x0239d9Dcf10F3D868F00d37b2363794c0715A866`.

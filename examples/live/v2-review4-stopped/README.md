# Stopped runs of the first two builds after review 4 (26 Nov 2026)

Review 4 found that a `BOTH:P1` verdict on a block whose pages show no ordinary reward could be bonded but never overturned. The fix (commit d7535d5) lets a `BOTH:P1` verdict be bonded only when both pages also show the block's ordinary reward. Its first live runs showed that the validators' model did not always copy that reward in a form the contract accepted, so a sound verdict could not be bonded: the bond was refused and credited back, and nobody lost anything. The contract was changed twice more before the runs on record (commits 56abe9e and cb4261e). These are the raw records of the stopped runs, kept unchanged; the runs on record are in `examples/live/` (see [`MILESTONE-2.md`](../../../MILESTONE-2.md)).

**First build after review 4 (d7535d5).**
- `v2-studio-first-build.json`: Studio `0x0caB55BE266F4DCDb3EbeAD4cD2C558d2F8126ce`. Case A's check came out `BOTH:P1`, but page A's reward was not kept, so its bond was refused and credited back (the model had copied "50" with the table row, which prints "50.00000000"). The run went on to two challenges, refused because nothing was bonded, and was stopped. The contract holds 3 test GEN credited back and not withdrawn.
- A Bradbury Phase 3 deployment of this build, `0xc3f9D3F114CF1E5Dc7B9CD8958F8C7fE2a8787e5`, was never used.

**Probe of the second build (56abe9e).** Studio `0xCDA594045839D57ceCdcE58593Aa2ED014Da2315`, two free checks (Examplecoin, Wobblecoin): both `BOTH:P1`, with the reward kept on both pages.

**Second build after review 4 (56abe9e).**
- `v2-studio-second-build.json`: Studio `0x1b58E337089C22d77E6e0Fe4B531F58a259F8dD1`. Cases A, B and C were bonded and challenged as planned, and Wobblecoin's pages were corrected (checker `122f101`, demo explorer `2526d27`). Case D's check (Nudgecoin) came out `BOTH:P1` with page A's reward not kept again, so its bond was refused and credited back; Nudgecoin's page B had already been corrected (`71b4540`). The run was stopped there. The contract holds 6 test GEN locked and 4.999999999999999999 credited.
- `v2-bradbury-second-build.json`: Bradbury Phase 3 `0x1c6865E54bfdC9FC84D75857b5D1D3bFce2494eE`, the same stories with a bond of 0.1 GEN. Stopped after case C's challenge, together with the Studio run; Twirlcoin's pages had been corrected (checker `d7ea7cc`, demo explorer). The contract holds 0.6 test GEN locked and 0.299999999999999999 credited.
- `v2-site-studio-second-build.json`: the page click-through against Studio `0x4CE7DBAdE67a234caC50a61480cC08558B598D81`. Its check came out `BOTH:P1` without page A's reward, so the page did not offer the bond, and the run stopped waiting for the button.

**Probe of the final build (cb4261e).** Studio `0xe0b9E5C107b4A022AB4a405a125fE39df116e365`, five free checks: four `BOTH:P1` (Examplecoin and Joltcoin, each on both premine claims) with the reward kept on both pages each time, and one `BOTH:P2` (Controlcoin).

The final build takes the reward from the model's line when it stands on the page, in the copied form or another form of the same value, and otherwise from the page's first line that says "reward" and prints that value.

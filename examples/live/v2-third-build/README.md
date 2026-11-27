# Live records of the third v2 build (superseded)

These records are from the third build of `contracts/launch_claim_checker_v2.py` (commit 8b9496b, the fixes after review 3), run on 25 Nov 2026, the Bradbury ones on Testnet Bradbury Phase 3. Review 4 ([`reviews/v2/README.md`](../../../reviews/v2/README.md)) then found one more way a bond could not be lost: a `BOTH:P1` verdict on a block whose pages show no ordinary reward, or a reward of 0, could be bonded but never overturned, because the opposite reading (P2) needs that reward. The contract was fixed again (commits d7535d5, 56abe9e and cb4261e, then b4966bf after review 5), deployed again, and the live runs were repeated. The current records are the ones in `examples/live/` (see [`MILESTONE-2.md`](../../../MILESTONE-2.md)). These are kept unchanged as a record of what was run; to verify them, check out commit c91f300 (the tools and builds they were made with) and run `tools/verify_v2.py` and `tools/verify_v2_bradbury.py` there.

- `v2-studio.json`: bonds and challenges on Studio `0xe1b1770448731b0AABf1DF9E62Df2faEf71d95dA`; 45 of 47 transactions as expected (two were sent again and went through).
- `v2-site-studio.json`: the page clicked through on Studio `0x624c4Af62668A6ac6C82040F61d9d0dDaCEa49F9`; 8 of 8.
- `v2-bradbury.json`: the same stories on Bradbury Phase 3 `0xBa377D0FED0E0A40eA3978716F4495D234DF6e46`; 44 of 44.
- `v2-bradbury-stopped.json`: a first Bradbury Phase 3 attempt on `0x99B5E0ce1942574A37B0125C185939295cC91672`, stopped.

## Corrections to these records

Review 4 read these deployments again and found the following; the records themselves are left as they were written.

**`v2-studio.json`, step 13.** The step `case D check` (`0xdeff6cd7…c88b`) timed out (2 of 5 validators agreed; nothing was stored) but the record marks it `as_expected: true`, so the record's own summary says 46 of 47. It was written by the run tool before it had the rule that only an agreed check counts, and was not recomputed when the run resumed. The right count is 45 of 47, as MILESTONE-2 said; the same check was sent again and agreed (step 14).

**`v2-bradbury.json`, the `after_the_run` note.** The three withdrawals were finalized about 30 minutes after they were sent (21:38:12, 21:38:36 and 21:38:54 UTC, by the Bradbury Phase 3 explorer), not "about 40 minutes later"; the balance then read 50000000000000000 wei, as the note says. Verifying this record at c91f300 still prints the note as written.

**`v2-bradbury-stopped.json`, the `stopped` note.**
- Swervecoin's correction (case C) was committed at 19:42:33 UTC (checker repository, `3fdad6e`) and 19:42:52 UTC (demo explorer, `1718cfd`), not at 19:53.
- The run was stopped at about 20:04 UTC, not 20:08: check 4 was sent at 20:03:58 and the next deployment, from the same account, at 20:05:05.
- The corrected page A did go live, at 20:03:54 UTC, but only after case C's re-check had read the old page; "did not go live" is wrong.
- `3fdad6e` is on GitHub as well as `e178d8f`: it stayed the head of the `milestone-two-explorers` branch, which the page tool could no longer update after the rebase (the tool now pushes `main` only).
- Besides the test GEN of A, B and C, the contract also holds 0.399999999999999999 GEN credited back for four refused challenges and never withdrawn (`totals`: locked 0.6 GEN, credited 0.399999999999999999 GEN, burned 0; balance 0.999999999999999999 GEN).
- Its verifier stops with one mismatch, "the contract holds 4 checks; the record has 3 agreed checks": that is expected. Check 4 (Skewcoin, case D) was sent by the run's requester when the run was stopped and is not in the record.

**The swervecoin correction commit.** `e178d8f` (and `3fdad6e`), titled "Fictional explorer data correction for swervecoin", also deleted four earlier video files that were staged at the time (`two-explorers-demo.mp4` and `two-explorers-demo-v3.mp4`, in `web/public/` and `docs/`). No page linked them. The page tool now commits only the corrected pages.

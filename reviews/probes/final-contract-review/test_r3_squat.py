from tests.direct.test_bounties import (env, mod, post, post_m1, file, file_m1, judge, judge_m1, get, balanced, mocks, p1, m1, iso, mining,
    T0, TTL, MARGIN, POT, FEE, G, SALT, BLOCK1, CLEAN1, MINING, LINE)

def test_blind_m1_filing_opened_after_someone_elses_reveal(env, capsys):
    post_m1(env)
    # T0+60: S files the only claim an M1 bounty can hold, blind, and does not reveal. The page shows 45% at this time.
    assert file_m1(env, who=env.charlie, at=T0 + 60)["ok"]
    # T0+900: the page now shows 84%. X sees it, files, reveals.
    assert file_m1(env, who=env.bob, at=T0 + 900)["ok"]
    out = judge_m1(env, who=env.bob, at=T0 + 960)
    with capsys.disabled():
        print("R3| X judged", out, "window_end-T0", get(env)["window_end"] - T0)
    # T0+1000: S, who never looked at the page, opens its earlier filing.
    out = judge_m1(env, who=env.charlie, at=T0 + 1000)
    with capsys.disabled():
        print("R3| S judged", out, "S credited", env.c.get_claimable(env.copier), "X credited", env.c.get_claimable(env.hunter))

import pytest
import tests.direct.test_bounties as tb
from tests.direct.test_bounties import env, mod  # fixtures

SEEN = {"OUTRANKED": 0, "PROVISIONAL_steps": 0, "WON": 0, "two_live": 0}

@pytest.mark.parametrize("seed", range(12))
def test_stats(env, seed, capsys):
    real_get = tb.get
    def spy(e, at=0, bid="1"):
        b = real_get(e, at, bid)
        if b["stored_state"] == "PROVISIONAL":
            SEEN["PROVISIONAL_steps"] += 1
        return b
    tb.get = spy
    try:
        tb.test_random_walk_keeps_the_money_and_the_queue_right.__wrapped__(env, seed) if hasattr(tb.test_random_walk_keeps_the_money_and_the_queue_right, "__wrapped__") else tb.test_random_walk_keeps_the_money_and_the_queue_right(env, seed)
    finally:
        tb.get = real_get
    n = env.c.get_count()
    for i in range(1, n + 1):
        b = real_get(env, bid=str(i))
        SEEN["OUTRANKED"] += sum(1 for f in b["filings"] if f["status"] == "OUTRANKED")
        SEEN["WON"] += b["stored_state"] == "WON"
    with capsys.disabled():
        print("R3| repo walk", seed, dict(SEEN))

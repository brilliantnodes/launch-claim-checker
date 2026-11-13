"""Direct-mode tests for LaunchClaimChecker (web and LLM are mocked)."""

import json
import sys
from pathlib import Path

import pytest

CONTRACT = "contracts/launch_claim_checker.py"
SNAP = Path(__file__).resolve().parents[1] / "snapshots"

ANN_EXM = "https://examplecoin.example/announcement"
EXP_EXM = "https://xplorer.exm.example/mining-summary"
ANN_BIG = "https://forum.example/samplecoin-announcement"
EXP_BIG = "http://203.0.113.10/block/1"
ANN_CTL = "https://controlcoin.example/announcement"
EXP_CTL = "https://explorer.example/ctl/block/1"


def snap(name: str) -> str:
    return (SNAP / name).read_text()


def llm(**over) -> str:
    base = {
        "ann_direction": "silent",
        "ev_direction": "silent",
        "top_miner_share_pct": None,
        "blocks_inspected": None,
        "early_allocation_found": "not_shown",
        "reasons": ["mocked"],
    }
    base.update(over)
    # Fenced on purpose: the contract asks for a text answer and parses it
    # itself, as a real LLM often wraps JSON in a code fence.
    return "```json\n" + json.dumps(base) + "\n```"


def mock_pages(vm, ann_url, ann_file, exp_url, exp_file):
    import re

    vm.mock_web(re.escape(ann_url), {"status": 200, "body": snap(ann_file)})
    vm.mock_web(re.escape(exp_url), {"status": 200, "body": snap(exp_file)})


@pytest.fixture
def contract(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    return c


@pytest.fixture
def mod(contract):
    """The loaded contract module, for testing the pure helpers."""
    for m in list(sys.modules.values()):
        if getattr(m, "LaunchClaimChecker", None) is not None and hasattr(m, "_decide"):
            return m
    raise RuntimeError("contract module not found")


EXM_LLM = dict(
    ann_direction="supports",
    ev_direction="contradicts",
    top_miner_share_pct=86.9,
    blocks_inspected=145,
)


# ---------------------------------------------------------------- cases 1-4


def test_case1_examplecoin_concentration_contradicted(direct_vm, contract):
    mock_pages(direct_vm, ANN_EXM, "examplecoin_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    # The mock only answers if the prompt really carries the explorer figures.
    direct_vm.mock_llm(r"(?s).*126\s+86\.9%.*", llm(**EXM_LLM))
    out = contract.check_claim(ANN_EXM, EXP_EXM, "DECENTRALIZED_MINING")
    assert out["verdict"] == "contradicted"
    assert out["rule"] == "M1_TOP_MINER_ABOVE_HALF"
    assert out["facts"]["top_miner_share_bp"] == 8690
    assert out["facts"]["blocks_inspected"] == 145
    assert out["id"] == "1"
    assert contract.get_count() == 1


def test_case2_samplecoin_founder_reward_contradicted(direct_vm, contract):
    mock_pages(direct_vm, ANN_BIG, "samplecoin_announcement.txt", EXP_BIG, "samplecoin_block1.txt")
    direct_vm.mock_llm(
        r"(?s).*1,000,000\.00000000 SMP.*",
        llm(ann_direction="supports", ev_direction="contradicts", early_allocation_found="yes"),
    )
    out = contract.check_claim(ANN_BIG, EXP_BIG, "NO_FOUNDER_REWARD")
    assert out["verdict"] == "contradicted"
    assert out["rule"] == "P1_EARLY_ALLOCATION_FOUND"


def test_case3_controlcoin_control_supported(direct_vm, contract):
    mock_pages(direct_vm, ANN_CTL, "controlcoin_announcement.txt", EXP_CTL, "controlcoin_block1.txt")
    direct_vm.mock_llm(
        r"(?s).*50\.00000000 CTL.*",
        llm(ann_direction="supports", ev_direction="supports", early_allocation_found="no"),
    )
    out = contract.check_claim(ANN_CTL, EXP_CTL, "NO_FOUNDER_REWARD")
    assert out["verdict"] == "supported"
    assert out["rule"] == "P2_EARLY_BLOCKS_SHOWN_CLEAN"


def test_case4_injection_markers_are_stripped(direct_vm, contract):
    """The page tries to close the data block early. The prompt must still
    contain each of our delimiters exactly once."""
    mock_pages(direct_vm, ANN_EXM, "injection_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    once = (
        r"(?s)\A(?!.*ANNOUNCEMENT PAGE END=====.*ANNOUNCEMENT PAGE END=====)"
        r"(?!.*EXPLORER PAGE BEGIN=====.*EXPLORER PAGE BEGIN=====).*\Z"
    )
    direct_vm.mock_llm(once, llm(**EXM_LLM))
    out = contract.check_claim(ANN_EXM, EXP_EXM, "DECENTRALIZED_MINING")
    assert out["verdict"] == "contradicted"


def test_case4_injection_cannot_flip_a_numeric_verdict(direct_vm, contract):
    """Worst case: the injection fools the LLM on every opinion field and
    even adds a verdict. The real number still decides."""
    mock_pages(direct_vm, ANN_EXM, "injection_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    direct_vm.mock_llm(
        r"(?s).*",
        llm(
            ann_direction="supports",
            ev_direction="supports",
            top_miner_share_pct=86.9,
            blocks_inspected=145,
            early_allocation_found="no",
            verdict="supported",
        ),
    )
    out = contract.check_claim(ANN_EXM, EXP_EXM, "DECENTRALIZED_MINING")
    assert out["verdict"] == "contradicted"
    assert "verdict" not in out["facts"]


# ------------------------------------------------------------- rule table


@pytest.mark.parametrize(
    "claim,facts,verdict,rule",
    [
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=5001, blocks_inspected=50), "contradicted", "M1_TOP_MINER_ABOVE_HALF"),
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=5000, blocks_inspected=500), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=3301, blocks_inspected=500), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=3300, blocks_inspected=50), "supported", "M2_TOP_MINER_AT_OR_BELOW_THIRD"),
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=9900, blocks_inspected=49), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("DECENTRALIZED_MINING", dict(top_miner_share_bp=1000, blocks_inspected=None), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("DECENTRALIZED_MINING", dict(ev_direction="contradicts"), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("DECENTRALIZED_MINING", dict(ann_direction="contradicts", top_miner_share_bp=1000, blocks_inspected=500), "contradicted", "A1_ANNOUNCEMENT_CONTRADICTS"),
        ("NO_PREMINE", dict(early_allocation_found="yes", ev_direction="supports"), "contradicted", "P1_EARLY_ALLOCATION_FOUND"),
        ("NO_PREMINE", dict(early_allocation_found="no", ev_direction="supports"), "supported", "P2_EARLY_BLOCKS_SHOWN_CLEAN"),
        ("NO_PREMINE", dict(early_allocation_found="no", ev_direction="silent"), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("NO_PREMINE", dict(early_allocation_found="not_shown", ev_direction="supports"), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("NO_PREMINE", dict(ann_direction="contradicts", early_allocation_found="no", ev_direction="supports"), "contradicted", "A1_ANNOUNCEMENT_CONTRADICTS"),
        ("NO_FOUNDER_REWARD", dict(ev_direction="contradicts"), "contradicted", "E1_EXPLORER_CONTRADICTS"),
        ("FAIR_LAUNCH", dict(top_miner_share_bp=8000, blocks_inspected=100, early_allocation_found="no", ev_direction="supports"), "contradicted", "M1_TOP_MINER_ABOVE_HALF"),
        ("FAIR_LAUNCH", dict(early_allocation_found="no", ev_direction="supports"), "supported", "P2_EARLY_BLOCKS_SHOWN_CLEAN"),
        ("FAIR_LAUNCH", dict(), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("CUSTOM", dict(ev_direction="supports"), "supported", "C1_EXPLORER_SUPPORTS"),
        ("CUSTOM", dict(ann_direction="supports"), "undetermined", "U1_NOT_ENOUGH_EVIDENCE"),
        ("CUSTOM", dict(ev_direction="supports", ann_direction="contradicts"), "contradicted", "A1_ANNOUNCEMENT_CONTRADICTS"),
    ],
)
def test_rule_table(mod, claim, facts, verdict, rule):
    base = dict(
        ann_direction="silent",
        ev_direction="silent",
        early_allocation_found="not_shown",
        top_miner_share_bp=None,
        blocks_inspected=None,
        reasons=[],
    )
    base.update(facts)
    assert mod._decide(claim, base) == (verdict, rule)


def test_announcement_alone_never_gives_supported(mod):
    """A project's own page saying 'trust us' is not evidence."""
    for claim in mod.CLAIM_TYPES:
        facts = mod._normalize({"ann_direction": "supports"})
        assert mod._decide(claim, facts)[0] == "undetermined"


def test_normalize_is_cautious(mod):
    f = mod._normalize(
        {
            "ann_direction": "SUPPORTS ",
            "ev_direction": "definitely supports",
            "early_allocation_found": "maybe",
            "top_miner_share_pct": "86.9%",
            "blocks_inspected": "1,450",
            "reasons": ["a" * 500, "b", "c", "d"],
        }
    )
    assert f["ann_direction"] == "supports"
    assert f["ev_direction"] == "silent"
    assert f["early_allocation_found"] == "not_shown"
    assert f["top_miner_share_bp"] == 8690
    assert f["blocks_inspected"] == 1450
    assert len(f["reasons"]) == 3 and len(f["reasons"][0]) == 160
    for bad in (-1, 101, "abc", True, float("nan")):
        assert mod._normalize({"top_miner_share_pct": bad})["top_miner_share_bp"] is None
    assert mod._normalize({})["ann_direction"] == "silent"


def test_parse_llm_json(mod):
    assert mod._parse_llm_json({"a": 1}) == {"a": 1}
    assert mod._parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert mod._parse_llm_json('Sure: {"a": 1} done') == {"a": 1}
    with pytest.raises(ValueError):
        mod._parse_llm_json("no json here")


# -------------------------------------------------------------- validators


def _run_case1(direct_vm, contract):
    mock_pages(direct_vm, ANN_EXM, "examplecoin_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    direct_vm.mock_llm(r"(?s).*", llm(**EXM_LLM))
    return contract.check_claim(ANN_EXM, EXP_EXM, "DECENTRALIZED_MINING")


def _swap_llm(direct_vm, **over):
    direct_vm.clear_mocks()
    mock_pages(direct_vm, ANN_EXM, "examplecoin_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    direct_vm.mock_llm(r"(?s).*", llm(**{**EXM_LLM, **over}))


def test_validator_agrees_on_same_data(direct_vm, contract):
    _run_case1(direct_vm, contract)
    assert direct_vm.run_validator() is True


def test_validator_ignores_reasons_and_opinions(direct_vm, contract):
    _run_case1(direct_vm, contract)
    _swap_llm(direct_vm, reasons=["completely different wording"], ev_direction="silent", ann_direction="silent")
    assert direct_vm.run_validator() is True


def test_validator_tolerates_small_live_drift(direct_vm, contract):
    _run_case1(direct_vm, contract)
    _swap_llm(direct_vm, top_miner_share_pct=85.2, blocks_inspected=150)
    assert direct_vm.run_validator() is True


def test_validator_rejects_large_number_gap(direct_vm, contract):
    _run_case1(direct_vm, contract)
    _swap_llm(direct_vm, top_miner_share_pct=70.0)
    assert direct_vm.run_validator() is False


def test_validator_rejects_different_verdict(direct_vm, contract):
    _run_case1(direct_vm, contract)
    _swap_llm(direct_vm, top_miner_share_pct=20.0)
    assert direct_vm.run_validator() is False


def test_validator_rejects_leader_error(direct_vm, contract):
    _run_case1(direct_vm, contract)
    assert direct_vm.run_validator(leader_error=Exception("boom")) is False


def test_validator_rejects_lying_leader(direct_vm, contract):
    """Leader reports 'supported' while its own facts say 86.9%."""
    _run_case1(direct_vm, contract)
    lie = {
        "verdict": "supported",
        "rule": "M2_TOP_MINER_AT_OR_BELOW_THIRD",
        "facts": {
            "ann_direction": "supports",
            "ev_direction": "supports",
            "early_allocation_found": "not_shown",
            "top_miner_share_bp": 8690,
            "blocks_inspected": 145,
            "reasons": [],
        },
        "announcement_read": True,
    }
    assert direct_vm.run_validator(leader_result=lie) is False


def test_validator_rejects_leader_whose_facts_do_not_give_its_verdict(direct_vm, contract):
    """The verdict and rule match the validator's own, but the leader's facts
    would store a different verdict. That must be rejected."""
    mock_pages(direct_vm, ANN_BIG, "samplecoin_announcement.txt", EXP_BIG, "samplecoin_block1.txt")
    direct_vm.mock_llm(r"(?s).*", llm(ev_direction="contradicts", early_allocation_found="yes"))
    contract.check_claim(ANN_BIG, EXP_BIG, "NO_FOUNDER_REWARD")
    sneaky = {
        "verdict": "contradicted",
        "rule": "P1_EARLY_ALLOCATION_FOUND",
        "facts": {
            "ann_direction": "silent",
            "ev_direction": "supports",
            "early_allocation_found": "no",
            "top_miner_share_bp": None,
            "blocks_inspected": None,
            "reasons": [],
        },
        "announcement_read": True,
    }
    assert direct_vm.run_validator(leader_result=sneaky) is False


@pytest.mark.parametrize(
    "bad",
    [
        "supported",
        {"verdict": "contradicted", "rule": "M1_TOP_MINER_ABOVE_HALF"},
        {"verdict": "contradicted", "rule": "M1_TOP_MINER_ABOVE_HALF", "facts": {"top_miner_share_bp": "8690", "blocks_inspected": 145}},
        {"verdict": "contradicted", "rule": "M1_TOP_MINER_ABOVE_HALF", "facts": {"top_miner_share_bp": 999999, "blocks_inspected": 145}},
    ],
)
def test_validator_rejects_malformed_leader_result(direct_vm, contract, bad):
    _run_case1(direct_vm, contract)
    assert direct_vm.run_validator(leader_result=bad) is False


# ------------------------------------------------------- inputs and storage


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.com/x",
        "example.com",
        "http://localhost/x",
        "http://127.0.0.1:8080/x",
        "http://10.1.2.3/x",
        "http://192.168.1.1/",
        "http://172.20.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/x",
        "http://user@localhost/x",
        "https://example.com/a b",
        "https://example.com/" + "a" * 400,
    ],
)
def test_bad_urls_are_refused(direct_vm, contract, mod, url):
    for label in ("announcement_url", "explorer_url"):
        with pytest.raises(Exception) as err:
            mod._check_url(url, label)
        assert label in str(err.value)
    with direct_vm.expect_revert("announcement_url must"):
        contract.check_claim(url, EXP_EXM, "NO_PREMINE")
    with direct_vm.expect_revert("explorer_url must"):
        contract.check_claim(ANN_EXM, url, "NO_PREMINE")
    assert contract.get_count() == 0


def test_public_raw_ip_is_allowed(mod):
    assert mod._check_url("http://203.0.113.10/block/1", "explorer_url")


def test_bad_claim_inputs_are_refused(direct_vm, contract):
    with direct_vm.expect_revert("claim_type must be one of"):
        contract.check_claim(ANN_EXM, EXP_EXM, "TO_THE_MOON")
    with direct_vm.expect_revert("claim_text is required"):
        contract.check_claim(ANN_EXM, EXP_EXM, "CUSTOM", "   ")
    with direct_vm.expect_revert("at most"):
        contract.check_claim(ANN_EXM, EXP_EXM, "CUSTOM", "x" * 401)


def test_unreadable_explorer_records_nothing(direct_vm, contract):
    import re

    direct_vm.mock_web(re.escape(ANN_EXM), {"status": 200, "body": snap("examplecoin_announcement.txt")})
    with direct_vm.expect_revert("explorer page could not be read"):
        contract.check_claim(ANN_EXM, EXP_EXM, "NO_PREMINE")
    assert contract.get_count() == 0


def test_validators_agree_only_when_both_cannot_read_the_explorer(direct_vm, contract):
    import re

    # Leader could not read the explorer. A validator that also cannot agrees.
    with direct_vm.expect_revert("explorer page could not be read"):
        contract.check_claim(ANN_EXM, EXP_EXM, "DECENTRALIZED_MINING")
    assert direct_vm.run_validator() is True
    # A validator that CAN read it must not agree.
    mock_pages(direct_vm, ANN_EXM, "examplecoin_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    direct_vm.mock_llm(r"(?s).*", llm(**EXM_LLM))
    assert direct_vm.run_validator() is False
    assert contract.get_count() == 0


def test_validator_that_cannot_read_rejects_a_real_verdict(direct_vm, contract):
    _run_case1(direct_vm, contract)
    direct_vm.clear_mocks()  # this validator can no longer fetch the pages
    assert direct_vm.run_validator() is False
    fake = {"verdict": "unreadable", "rule": "X1_EXPLORER_UNREADABLE", "facts": {}, "announcement_read": False}
    mock_pages(direct_vm, ANN_EXM, "examplecoin_announcement.txt", EXP_EXM, "examplecoin_mining_summary.txt")
    direct_vm.mock_llm(r"(?s).*", llm(**EXM_LLM))
    assert direct_vm.run_validator(leader_result=fake) is False


def test_unreadable_announcement_is_treated_as_silent(direct_vm, contract):
    import re

    direct_vm.mock_web(re.escape(EXP_CTL), {"status": 200, "body": snap("controlcoin_block1.txt")})
    direct_vm.mock_llm(
        r"(?s).*",
        llm(ann_direction="contradicts", ev_direction="supports", early_allocation_found="no"),
    )
    out = contract.check_claim(ANN_CTL, EXP_CTL, "NO_PREMINE")
    assert out["facts"]["announcement_read"] is False
    assert out["facts"]["ann_direction"] == "silent"
    assert out["verdict"] == "supported"


def test_long_pages_are_cut(direct_vm, contract, mod):
    import re

    direct_vm.mock_web(re.escape(ANN_EXM), {"status": 200, "body": "A" * 50000})
    direct_vm.mock_web(re.escape(EXP_EXM), {"status": 200, "body": "B" * 50000})
    direct_vm.mock_llm(r"(?s)\A(?!.*A{%d}).*\Z" % (mod.PAGE_CHARS + 1), llm())
    out = contract.check_claim(ANN_EXM, EXP_EXM, "NO_PREMINE")
    assert out["verdict"] == "undetermined"


def test_storage_and_views(direct_vm, contract, direct_alice, direct_bob):
    from tests.direct.conftest import to_hex

    _run_case1(direct_vm, contract)
    direct_vm.clear_mocks()
    mock_pages(direct_vm, ANN_CTL, "controlcoin_announcement.txt", EXP_CTL, "controlcoin_block1.txt")
    direct_vm.mock_llm(r"(?s).*", llm(ev_direction="supports", early_allocation_found="no"))
    direct_vm.sender = direct_bob
    second = contract.check_claim(ANN_CTL, EXP_CTL, "no_premine", "  no   premine  ")

    assert second["id"] == "2"
    assert second["claim_type"] == "NO_PREMINE"
    assert second["claim_text"] == "no premine"
    assert contract.get_count() == 2
    assert contract.get_check("1")["verdict"] == "contradicted"
    assert contract.get_check("2")["verdict"] == "supported"
    latest = contract.get_latest(10)
    assert [c["id"] for c in latest] == ["2", "1"]
    assert [c["id"] for c in contract.get_latest(1)] == ["2"]
    assert contract.get_checks_by(to_hex(direct_alice)) == ["1"]
    assert contract.get_checks_by(to_hex(direct_bob)) == ["2"]
    assert contract.get_check("1")["submitter"] == to_hex(direct_alice)
    assert contract.get_check("1")["checked_at"] != ""
    with direct_vm.expect_revert("no such check"):
        contract.get_check("99")
    rules = contract.get_rules()
    assert rules["contradict_share_bp"] == 5000 and rules["min_blocks"] == 50


def test_nondet_closures_are_picklable(direct_vm, contract, recwarn):
    """On a real network the leader and validator functions are pickled.
    The test VM warns if that would fail."""
    direct_vm.check_pickling = True
    _run_case1(direct_vm, contract)
    assert not [w for w in recwarn.list if "not picklable" in str(w.message)]

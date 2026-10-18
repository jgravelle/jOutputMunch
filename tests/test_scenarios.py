"""The scenarios are the published run's scenarios, byte for byte."""

import hashlib

from joutputmunch.bench.scenarios import _SPECS, RULE_SETS, load_scenarios

# sha256(system_baseline + NUL + user) for each scenario, taken from
# benchmarks/harness.py at cac4bad, the commit that added benchmarks/results.md.
PUBLISHED = {
    "code_explanation": ("7f6133caa67755f856fd182e131f1a009f6939b1caba2e0a040b9ef9b3dbc4fd", "core+code"),
    "bug_diagnosis": ("655dad068ab7302ede1b454a65e6e231b2cc49459fd138b4cbe8588e47bc0f51", "core+code"),
    "pr_review": ("1946bb611f4c34f5cc0db835f422cecf06a79e3864b53cbcc7975427e63c9f48", "core+code"),
    "data_summary": ("30513e6e222ca8ab5d7fbf4e4aa6c08198b4a51fa55f3c8de0149dd3dad16dc6", "core"),
    "general_question": ("5b12268d88909227357848f166f30d0b272332fbfdf1503d4f3e1ac2217c81f3", "core"),
}


def _digest(s):
    return hashlib.sha256((s.system_baseline + "\x00" + s.user).encode("utf-8")).hexdigest()


def test_the_scenarios_are_the_published_ones():
    scenarios = load_scenarios()
    assert list(scenarios) == list(PUBLISHED)
    for key, (digest, rule_set) in PUBLISHED.items():
        assert _digest(scenarios[key]) == digest, key
        assert _SPECS[key]["system_munch"] == rule_set, key


def test_the_rules_arm_carries_the_rule_files_and_the_baseline_does_not(repo):
    core = (repo / "rules" / "core.md").read_text(encoding="utf-8")
    code = (repo / "rules" / "code-assistant.md").read_text(encoding="utf-8")
    for s in load_scenarios().values():
        assert s.system_munch.startswith(core)
        assert (code in s.system_munch) == (_SPECS[s.key]["system_munch"] == "core+code")
        assert "jOutputMunch" not in s.system_baseline


def test_a_rules_dir_can_be_passed(tmp_path):
    for files in RULE_SETS.values():
        for f in files:
            (tmp_path / f).write_text(f"rules from {f}", encoding="utf-8")
    s = load_scenarios(tmp_path)["code_explanation"]
    assert s.system_munch == "rules from core.md\nrules from code-assistant.md"

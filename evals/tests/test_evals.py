"""Tests for the eval tools. No model is called.

    python3 -m unittest discover -s evals/tests -v
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVALS))
import check  # noqa: E402
import run  # noqa: E402

SCHEMA = json.loads(check.RESULT_SCHEMA.read_text(encoding="utf-8"))


def unit(verdict):
    return {"perspective": "p", "verdict": verdict, "confidence": "medium", "rationale": ["because"]}


def result(grade="normal", votes=("approve", "approve", "reject"), **extra):
    """A deliberation result whose resolution follows the rules, unless overridden."""
    r = {"version": 2, "mode": "deliberation", "agenda": "add X", "grade": grade,
         "verdict": check.expected_verdict(grade, list(votes)), "approve_count": list(votes).count("approve"),
         "units": dict(zip(check.UNIT_NAMES, (unit(v) for v in votes)))}
    if r["verdict"] == "on_hold":
        r["debate"] = "one round; nobody changed position"
    r.update(extra)
    return r


def information():
    return {"version": 2, "mode": "information", "agenda": "what are the trade-offs?",
            "units": {name: {"answer": "it depends"} for name in check.UNIT_NAMES}}


def fixture(fid, must=None, should=None, **extra):
    return {"id": fid, "category": "test", "request": "r", "facts": [],
            "expect": {"must": must or {}, "should": should or {}}, **extra}


def write_run(root, fid, k, res=None, log=None, meta=None):
    run_dir = Path(root) / fid / f"run-{k}"
    (run_dir / "result").mkdir(parents=True)
    if res is not None:
        (run_dir / "result" / "20260101-000000-x.json").write_text(json.dumps(res), encoding="utf-8")
    if log is not None:
        (run_dir / "result" / "20260101-000000-x.jsonl").write_text(
            "\n".join(json.dumps(e) for e in log), encoding="utf-8")
    if meta is not None:
        (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


ASKED = [{"event": "framing_done", "data": {"questions": ["which reading?"]}}]


class FixtureTests(unittest.TestCase):
    def test_repository_fixtures_are_valid(self):
        fixtures, errors = check.load_fixtures(check.FIXTURES_DIR)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(fixtures), 12)

    def test_every_fixture_builds_a_prompt_with_its_request(self):
        fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
        for fx in fixtures.values():
            self.assertIn(fx["request"], run.build_prompt(fx))

    def test_ask_fixture_prompt_does_not_say_go_ahead(self):
        fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
        prompt = run.build_prompt(fixtures["ask-ambiguous-release"])
        self.assertNotIn("go ahead", prompt)
        self.assertNotIn("unattended", prompt)

    def _errors(self, fx):
        return check.validate_fixture(Path(f"{fx.get('id')}.json"), fx)

    def test_bad_fixtures_are_rejected(self):
        self.assertEqual(self._errors(fixture("ok", must={"mode": "deliberation"})), [])
        self.assertTrue(self._errors(fixture("Bad_Id", must={"mode": "deliberation"})))
        self.assertTrue(self._errors(fixture("x")))  # nothing expected
        self.assertTrue(self._errors(fixture("x", must={"mood": "good"})))  # unknown check
        self.assertTrue(self._errors(fixture("x", must={"outcome": "passed"})))  # bad value
        self.assertTrue(self._errors(fixture("x", must={"agenda_match": "("})))  # bad regex
        self.assertTrue(self._errors(fixture("x", must={"grade": "normal"}, should={"grade": "normal"})))
        self.assertTrue(self._errors(fixture("x", must={"asks_questions": True})))  # needs interaction 'ask'
        self.assertTrue(self._errors(fixture("x", must={"asks_questions": True, "mode": "deliberation"},
                                             interaction="ask")))
        self.assertEqual(self._errors(fixture("x", must={"asks_questions": True}, interaction="ask")), [])

    def test_pair_needs_two_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = fixture("lonely", must={"mode": "deliberation"}, pair="p")
            (Path(tmp) / "lonely.json").write_text(json.dumps(fx), encoding="utf-8")
            _, errors = check.load_fixtures(Path(tmp))
        self.assertTrue(any("pair" in e for e in errors))


class SchemaTests(unittest.TestCase):
    def samples(self):
        bad_enum = result()
        bad_enum["units"]["melchior"]["verdict"] = "conditional"
        extra_unit = result()
        extra_unit["units"]["magi_core"] = unit("approve")
        long_rationale = result()
        long_rationale["units"]["casper"]["rationale"] = ["a", "b", "c", "d"]
        no_units = result()
        del no_units["units"]
        return [
            (result(), True), (information(), True),
            (result(follow_ups=[{"agenda": "then Y", "grade": "normal", "verdict": "passed"}]), True),
            (bad_enum, False), (extra_unit, False), (long_rationale, False), (no_units, False),
            (result(version=1), False), (result(approve_count=4), False), (result(approve_count=True), False),
            (result(agenda=""), False), (result(grade_raised="yes"), False),
            (result(follow_ups=[{"agenda": "a"}]), False),
            (result(follow_ups=[{"agenda": str(i), "verdict": "passed"} for i in range(3)]), False),
        ]

    def test_validator(self):
        for sample, valid in self.samples():
            errors = check.validate_schema(sample, SCHEMA, SCHEMA)
            self.assertEqual(errors == [], valid, f"{errors} for {json.dumps(sample)[:200]}")

    def test_agrees_with_jsonschema_when_installed(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        reference = jsonschema.Draft202012Validator(SCHEMA)
        for sample, _ in self.samples():
            ours = check.validate_schema(sample, SCHEMA, SCHEMA) == []
            self.assertEqual(ours, reference.is_valid(sample), json.dumps(sample)[:200])

    def test_unknown_keyword_is_an_error_not_a_pass(self):
        with self.assertRaises(check.SchemaError):
            check.validate_schema("x", {"type": "string", "pattern": "^x$"}, {})


class RuleTests(unittest.TestCase):
    def problems(self, res):
        return check.check_rules(res)[0]

    def test_resolutions_that_follow_the_rules(self):
        for grade, votes in [("normal", "aaa"), ("normal", "aar"), ("normal", "arr"), ("normal", "rrr"),
                             ("critical", "aaa"), ("critical", "aar"), ("critical", "arr"), ("critical", "rrr")]:
            votes = [{"a": "approve", "r": "reject"}[v] for v in votes]
            self.assertEqual(self.problems(result(grade, votes)), [], (grade, votes))
        self.assertEqual(self.problems(information()), [])

    def test_expected_verdicts(self):
        a, r = "approve", "reject"
        self.assertEqual(check.expected_verdict("normal", [a, a, r]), "passed")
        self.assertEqual(check.expected_verdict("normal", [a, r, r]), "rejected")
        self.assertEqual(check.expected_verdict("critical", [a, a, a]), "passed")
        self.assertEqual(check.expected_verdict("critical", [a, a, r]), "on_hold")
        self.assertEqual(check.expected_verdict("critical", [r, r, r]), "rejected")

    def test_majority_does_not_pass_a_critical_proposal(self):
        self.assertTrue(self.problems(result("critical", ("approve", "approve", "reject"), verdict="passed")))

    def test_normal_proposal_cannot_be_on_hold(self):
        self.assertTrue(self.problems(result("normal", ("approve", "reject", "reject"),
                                             verdict="on_hold", debate="x")))

    def test_on_hold_needs_a_debate_record(self):
        res = result("critical", ("approve", "approve", "reject"))
        del res["debate"]
        self.assertTrue(self.problems(res))

    def test_approve_count_must_match_the_units(self):
        self.assertTrue(self.problems(result(approve_count=3)))

    def test_unit_error_is_never_outvoted(self):
        res = result(votes=("approve", "approve", "error"), verdict="passed")
        self.assertTrue(self.problems(res))
        res["verdict"] = "error"
        self.assertEqual(self.problems(res), [])

    def test_grade_raised_means_critical(self):
        self.assertTrue(self.problems(result("normal", grade_raised=True)))

    def test_follow_ups_follow_the_same_rules(self):
        units = dict(zip(check.UNIT_NAMES, ({"verdict": v} for v in ("approve", "reject", "reject"))))
        bad = result(follow_ups=[{"agenda": "then Y", "grade": "normal", "verdict": "passed", "units": units}])
        self.assertTrue(self.problems(bad))
        good = result(follow_ups=[{"agenda": "then Y", "grade": "normal", "verdict": "rejected", "units": units}])
        self.assertEqual(self.problems(good), [])

    def test_information_mode_needs_every_answer(self):
        res = information()
        res["units"]["casper"]["answer"] = " "
        self.assertTrue(self.problems(res))


class ResultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def check(self, *fixtures):
        return check.check_results(self.root, {fx["id"]: fx for fx in fixtures})

    def test_pass_warn_fail(self):
        passing = fixture("passing", must={"mode": "deliberation", "outcome": "change"}, should={"grade": "normal"})
        warning = fixture("warning", must={"outcome": "change"}, should={"grade": "critical"})
        failing = fixture("failing", must={"outcome": "no_change"})
        for fid in ("passing", "warning", "failing"):
            for k in (1, 2):
                write_run(self.root, fid, k, result())
        summary = self.check(passing, warning, failing)
        self.assertEqual({f: e["status"] for f, e in summary["fixtures"].items()},
                         {"passing": "pass", "warning": "warn", "failing": "fail"})
        self.assertEqual(summary["totals"], {"pass": 1, "warn": 1, "fail": 1, "skipped": 0})

    def test_must_has_to_hold_in_every_run(self):
        write_run(self.root, "flaky", 1, result(votes=("approve", "approve", "reject")))
        write_run(self.root, "flaky", 2, result(votes=("approve", "reject", "reject")))
        e = self.check(fixture("flaky", must={"outcome": "change"}))["fixtures"]["flaky"]
        self.assertEqual(e["status"], "fail")
        self.assertEqual(e["must"]["outcome"]["met"], 1)
        self.assertEqual(e["results"], {"passed": 1, "rejected": 1})

    def test_on_hold_counts_as_no_change(self):
        write_run(self.root, "held", 1, result("critical", ("approve", "reject", "reject")))
        e = self.check(fixture("held", must={"outcome": "no_change", "split": True}))["fixtures"]["held"]
        self.assertEqual(e["status"], "pass")

    def test_rule_break_fails_whatever_the_fixture_expects(self):
        write_run(self.root, "broken", 1, result("critical", ("approve", "approve", "reject"), verdict="passed"))
        e = self.check(fixture("broken", should={"grade": "critical"}))["fixtures"]["broken"]
        self.assertEqual(e["status"], "fail")

    def test_missing_result_fails_and_no_runs_is_skipped(self):
        write_run(self.root, "died", 1, meta={"exit_code": 1, "timed_out": False})
        summary = self.check(fixture("died", must={"mode": "deliberation"}),
                             fixture("never-run", must={"mode": "deliberation"}))
        self.assertEqual(summary["fixtures"]["died"]["status"], "fail")
        self.assertEqual(summary["fixtures"]["never-run"]["status"], "skipped")

    def test_text_checks(self):
        units = {name: {"verdict": "approve"} for name in check.UNIT_NAMES}
        follow_up = {"agenda": "then Y", "grade": "normal", "verdict": "passed", "units": units}
        write_run(self.root, "text", 1, result(agenda="Add the lint check to CI", preset="ethics",
                                                follow_ups=[follow_up]))
        ok = fixture("text", must={"agenda_match": "lint", "agenda_not_match": "do not|don't",
                                   "preset_match": "ethic", "follow_ups_min": 1, "verdict": ["passed"]})
        self.assertEqual(self.check(ok)["fixtures"]["text"]["status"], "pass")
        bad = fixture("text", must={"agenda_not_match": "LINT"})
        self.assertEqual(self.check(bad)["fixtures"]["text"]["status"], "fail")

    def test_stopping_to_ask(self):
        ask = lambda fid: fixture(fid, must={"asks_questions": True}, interaction="ask")
        write_run(self.root, "asked", 1, log=ASKED)
        write_run(self.root, "no-log", 1)
        write_run(self.root, "answered-itself", 1, result(), log=ASKED + [{"event": "final", "data": {}}])
        write_run(self.root, "died-before-framing", 1, log=[{"event": "run_started", "data": {}}])
        summary = self.check(ask("asked"), ask("no-log"), ask("answered-itself"), ask("died-before-framing"))
        self.assertEqual({f: e["status"] for f, e in summary["fixtures"].items()},
                         {"asked": "pass", "no-log": "warn", "answered-itself": "fail",
                          "died-before-framing": "fail"})

    def test_pair_must_reach_the_same_outcome(self):
        a = fixture("add", should={"grade": "normal"}, pair="p")
        b = fixture("not-add", should={"grade": "normal"}, pair="p")
        for k in (1, 2, 3):
            write_run(self.root, "add", k, result(votes=("approve", "approve", "approve")))
            # Framed as "do not add": the same units now reject the proposal.
            write_run(self.root, "not-add", k, result(votes=("reject", "reject", "reject")))
        summary = self.check(a, b)
        self.assertEqual(summary["pairs"]["p"]["status"], "fail")
        self.assertEqual(summary["pairs_failed"], 1)
        self.assertEqual(summary["fixtures"]["add"]["status"], "pass")  # the pair is what fails

    def test_pair_passes_on_same_majority(self):
        a, b = fixture("add", should={"grade": "normal"}, pair="p"), fixture("not-add", should={"grade": "normal"}, pair="p")
        for k in (1, 2, 3):
            write_run(self.root, "add", k, result())
            write_run(self.root, "not-add", k, result(votes=("approve", "approve", "approve") if k < 3
                                                      else ("reject", "reject", "reject")))
        summary = self.check(a, b)
        self.assertEqual(summary["pairs"]["p"]["status"], "pass")
        self.assertEqual(summary["fixtures"]["not-add"]["approvals_mean"], 2.0)

    def test_report_and_compare(self):
        fx = fixture("f", must={"outcome": "change"})
        write_run(self.root, "f", 1, result())
        before = self.check(fx)
        self.assertIn("| f | pass |", check.render_report(before))

        other = Path(self._tmp.name) / "after"
        write_run(other, "f", 1, result(votes=("approve", "reject", "reject")))
        after = check.check_results(other, {"f": fx})
        report, regressions = check.render_compare(before, after)
        self.assertEqual(regressions, ["f"])
        self.assertIn("regression", report)
        self.assertEqual(check.render_compare(after, before)[1], [])


class RunnerTests(unittest.TestCase):
    def test_run_then_check_with_a_fake_agent(self):
        fake = [sys.executable, str(Path(__file__).with_name("fake_agent.py")), "{prompt}"]
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["--name", "t", "--out", tmp, "--runs", "2", "--cmd-json", json.dumps(fake),
                    "--only", "direction-lint,ask-ambiguous-release"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(argv), 0)
                self.assertEqual(run.main(argv), 0)  # second time: everything is skipped
            run_dir = Path(tmp) / "t"
            self.assertTrue((run_dir / "direction-lint-add" / "run-2" / "meta.json").exists())
            self.assertIn("넣지 말까", (run_dir / "direction-lint-not-add" / "run-1" / "prompt.txt").read_text(encoding="utf-8"))

            fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
            summary = check.check_results(run_dir, fixtures)
            ran = {f: e["status"] for f, e in summary["fixtures"].items() if e["status"] != "skipped"}
            self.assertEqual(ran, {"direction-lint-add": "pass", "direction-lint-not-add": "pass",
                                   "ask-ambiguous-release": "pass"})
            self.assertEqual(summary["pairs"]["direction-lint"]["status"], "pass")
            self.assertEqual(summary["agent"], sys.executable)

    def test_only_rejects_unknown_names(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            run.main(["--dry-run", "--only", "no-such-fixture"])


if __name__ == "__main__":
    unittest.main()

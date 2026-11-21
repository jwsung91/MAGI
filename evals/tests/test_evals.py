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
            self.assertIn(fx["request"], check.build_prompt(fx))

    def test_ask_fixture_prompt_does_not_say_go_ahead(self):
        fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
        prompt = check.build_prompt(fixtures["ask-ambiguous-release"])
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
        self.assertEqual(self._errors(fixture("x", should={"units": {"melchior": "reject"}})), [])
        for bad in ({}, {"melchior": "yes"}, {"gaspar": "approve"}, ["melchior"]):
            self.assertTrue(self._errors(fixture("x", should={"units": bad})), bad)

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

    def test_rules_from_1_6_0_have_no_debate_round(self):
        a, r = "approve", "reject"
        self.assertEqual(check.expected_verdict("critical", [a, a, r], debate=False), "rejected")
        self.assertEqual(check.expected_verdict("critical", [a, a, a], debate=False), "passed")
        self.assertEqual(check.expected_verdict("normal", [a, a, r], debate=False), "passed")
        split = result("critical", (a, a, r))                        # on hold with a debate record
        self.assertEqual(self.problems(split), [])
        self.assertTrue(check.check_rules(split, debate=False)[0])    # 1.6.0: should be rejected
        new = result("critical", (a, a, r), verdict="rejected")
        del new["debate"]  # result() adds one for the on hold it computes under the earlier rules
        self.assertEqual(check.check_rules(new, debate=False), ([], []))
        self.assertTrue(self.problems(new))                           # before 1.6.0: should be on hold
        self.assertIn("a debate round is recorded, but this skill version has none",
                      check.check_rules(dict(new, debate="one round"), debate=False)[1])

    def test_rules_follow_the_run_skill_version(self):
        for version, debate in (("1.5.2", True), ("1.6.0", False), ("2.0.1", False), (None, True), ("x", True)):
            self.assertEqual(check.debate_rules(version), debate, version)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            res = result("critical", ("approve", "approve", "reject"), verdict="rejected")
            del res["debate"]
            write_run(root, "f", 1, res)
            fx = {"f": fixture("f", must={"mode": "deliberation"})}
            for version, status in (("1.5.1", "fail"), ("1.6.0", "pass")):
                (root / "run.json").write_text(json.dumps({"skill_version": version}), encoding="utf-8")
                self.assertEqual(check.check_results(root, fx)["fixtures"]["f"]["status"], status, version)

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

    def test_follow_ups_max(self):
        units = {name: {"verdict": "approve"} for name in check.UNIT_NAMES}
        follow_up = {"agenda": "then Y", "grade": "normal", "verdict": "passed", "units": units}
        write_run(self.root, "one", 1, result(follow_ups=[follow_up]))
        write_run(self.root, "none", 1, result())
        summary = self.check(fixture("one", must={"follow_ups_max": 0}), fixture("none", must={"follow_ups_max": 0}))
        self.assertEqual(summary["fixtures"]["one"]["status"], "fail")
        self.assertEqual(summary["fixtures"]["none"]["status"], "pass")
        self.assertEqual(self.check(fixture("one", must={"follow_ups_max": 1}))["fixtures"]["one"]["status"], "pass")

    def test_grade_raised(self):
        write_run(self.root, "raised", 1, result("critical", ("approve", "approve", "approve"), grade_raised=True))
        write_run(self.root, "plain", 1, result())
        summary = self.check(fixture("raised", must={"grade_raised": True}),
                             fixture("plain", must={"grade_raised": False}))
        self.assertEqual(summary["fixtures"]["raised"]["status"], "pass")
        self.assertEqual(summary["fixtures"]["plain"]["status"], "pass")
        self.assertEqual(self.check(fixture("plain", must={"grade_raised": True}))["fixtures"]["plain"]["status"], "fail")

    def test_agenda_ignores_quoted_text(self):
        cases = [
            ("CI에 린트 검사를 넣는다. (원 질문은 부정형 '넣지 말까?')", "넣지 말", True),
            ("Add the database (asked as \u201cshould we hold off?\u201d)", "hold off", True),
            ("Add the database (asked as `hold off`)", "hold off", True),
            ("We don't add the database", "don't add", False),  # an apostrophe is not a quote
            ("CI에 린트 검사를 넣지 말자", "넣지 말", False),
            ("Add MongoDB (Asked in the negative; rejected = yes, hold off.)", "hold off", True),
            ("Add MongoDB (note: 'a)b' quoted) now", "now", False),  # a ")" in a quote does not end the note
        ]
        for agenda, pattern, passes in cases:
            with self.subTest(agenda=agenda):
                self.assertEqual(check.meets("agenda_not_match", pattern, {"result": {"agenda": agenda}}), passes)

    def test_moderator_framing_warns_only_with_subagents(self):
        fx = fixture("framed", must={"mode": "deliberation"})
        write_run(self.root, "framed", 1, result(framing="moderator directly"))
        write_run(self.root, "framed", 2, result(framing="모더레이터 직접"))
        write_run(self.root, "framed", 3, result(framing="framing agent"))
        self.assertEqual(self.check(fx)["fixtures"]["framed"]["status"], "pass")  # no run.json: unknown
        (self.root / "run.json").write_text(json.dumps({"command": ["claude", "--allowedTools", "Agent"]}))
        out = self.check(fx)["fixtures"]["framed"]
        self.assertEqual(out["status"], "warn")
        self.assertEqual(sum("moderator directly" in n for n in out["notes"]), 2)

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

    def test_unit_votes_are_checked_and_counted(self):
        fx = fixture("u", should={"units": {"melchior": "reject", "casper": "approve"}})
        write_run(self.root, "u", 1, result(votes=("reject", "approve", "approve")))   # meets it
        write_run(self.root, "u", 2, result(votes=("approve", "approve", "approve")))  # melchior wrong
        write_run(self.root, "u", 3, information())                                    # not voted on
        e = self.check(fx)["fixtures"]["u"]
        self.assertEqual(e["should"]["units"]["met"], 1)
        self.assertEqual(e["status"], "warn")
        self.assertEqual(e["votes"]["results"], 2)
        self.assertEqual(e["unit_approvals"], {"melchior": 1, "balthasar": 2, "casper": 2})
        self.assertIn("| 1/2 · 2/2 · 2/2 |", check.render_report(self.check(fx)))

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


class StatsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_agent_cost(self):
        self.assertEqual(check.agent_cost('{"type": "result", "total_cost_usd": 0.81237}'), 0.8124)
        self.assertEqual(check.agent_cost('[{"type": "system"}, {"type": "result", "total_cost_usd": 1}]'), 1.0)
        for text in ("", "done", '{"type": "result"}', '{"total_cost_usd": true}', '"0.5"'):
            self.assertIsNone(check.agent_cost(text), text)

    def test_agent_error(self):
        not_logged_in = '{"type": "result", "subtype": "success", "is_error": true, ' \
                        '"result": "Authentication error · please\\ntry again", "total_cost_usd": 0}'
        self.assertEqual(check.agent_error(not_logged_in), "Authentication error · please try again")
        self.assertEqual(check.agent_cost(not_logged_in), 0.0)
        self.assertIsNone(check.agent_error('{"type": "result", "is_error": false, "result": "done"}'))
        self.assertIsNone(check.agent_error("done"))

        write_run(self.root, "f", 1, meta={"exit_code": 1, "agent_error": "Authentication error"})
        e = check.check_results(self.root, {"f": fixture("f", must={"mode": "deliberation"})})["fixtures"]["f"]
        self.assertEqual(e["status"], "fail")
        self.assertIn("run-1: agent error: Authentication error", e["notes"])

    def test_cost_is_read_from_stdout_when_meta_has_none(self):
        # A run made before run.py recorded the cost.
        write_run(self.root, "old", 1, result(), meta={"exit_code": 0, "seconds": 120.0})
        (self.root / "old" / "run-1" / "stdout.txt").write_text('{"total_cost_usd": 0.5}', encoding="utf-8")
        summary = check.check_results(self.root, {"old": fixture("old", must={"mode": "deliberation"})})
        self.assertEqual((summary["cost_usd"], summary["seconds"], summary["executions"]), (0.5, 120, 1))

    def test_unanimous_and_direct_framing_are_counted(self):
        (self.root / "run.json").write_text(json.dumps({"command": ["claude", "--allowedTools", "Agent"]}),
                                            encoding="utf-8")
        write_run(self.root, "f", 1, result(votes=("approve", "approve", "approve")))
        write_run(self.root, "f", 2, result(votes=("approve", "approve", "reject"), framing="moderator directly"))
        write_run(self.root, "f", 3, information())           # not voted on
        write_run(self.root, "f", 4, log=ASKED)               # no result
        summary = check.check_results(self.root, {"f": fixture("f", should={"grade": "normal"})})
        self.assertEqual(summary["votes"], {"results": 2, "unanimous": 1})
        self.assertEqual(summary["framing"], {"results": 3, "direct": 1})
        report = check.render_report(summary)
        self.assertIn("Unanimous votes: 1 of 2 voted results", report)
        self.assertIn("Framed by the moderator directly: 1 of 3 results", report)
        self.assertNotIn("Executions: 4 ·", report)  # no cost or time known: the count stands alone
        self.assertIn("Executions: 4", report)

    def test_framing_is_not_counted_when_subagents_are_unknown(self):
        write_run(self.root, "f", 1, result(framing="moderator directly"))
        summary = check.check_results(self.root, {"f": fixture("f", must={"mode": "deliberation"})})
        self.assertIsNone(summary["framing"])
        self.assertNotIn("Framed by", check.render_report(summary))

    def test_compare_shows_the_run_wide_numbers_and_reads_old_summaries(self):
        write_run(self.root, "f", 1, result(), meta={"seconds": 4000, "cost_usd": 2.0})
        new = check.check_results(self.root, {"f": fixture("f", must={"mode": "deliberation"})})
        old = json.loads(json.dumps(new))
        for key in ("executions", "cost_usd", "seconds", "votes", "framing", "model"):
            del old[key]  # a summary written before these numbers existed
        report, regressions = check.render_compare(old, new)
        self.assertEqual(regressions, [])
        self.assertIn("| Executions | — | 1 · $2.00 ($2.00 each) · 1h 07m of agent time |", report)
        self.assertIn("# MAGI Eval Report", check.render_report(old))

    def test_results_refuses_a_folder_without_runs(self):
        (self.root / "report.md").write_text("kept", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check.main(["results", str(self.root)]), 2)
        self.assertEqual((self.root / "report.md").read_text(encoding="utf-8"), "kept")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check.main(["results", str(check.HERE / "baseline" / "1.5.0")]), 2)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_control_prompt_and_answer(self):
        fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
        prompt = check.build_control_prompt(fixtures["direction-lint-en-not-add"])
        self.assertIn("Should we not add a lint check to CI?", prompt)
        self.assertIn("adding X is still \"change\"", prompt)
        self.assertNotIn("MAGI", prompt)
        self.assertIn("넣지 말까", check.build_control_prompt(fixtures["direction-lint-not-add"]))
        eligible = {fid for fid, fx in fixtures.items() if check.control_eligible(fx)}
        self.assertNotIn("information-rest-vs-grpc", eligible)
        self.assertNotIn("ask-ambiguous-release", eligible)
        self.assertIn("split-monorepo", eligible)

        answer = lambda text: check.control_answer(json.dumps({"type": "result", "result": text}))
        self.assertEqual(answer("Reasons...\nDECISION: no_change"), "no_change")
        self.assertEqual(answer("**DECISION:** change"), "change")  # a bold label still counts
        self.assertEqual(answer("DECISION: **change**"), "change")
        self.assertEqual(answer("decision: Change"), "change")
        self.assertEqual(answer("DECISION: change ... on reflection DECISION: no_change"), "no_change")
        self.assertIsNone(answer("I would leave it."))

    def _control_run(self, fid, k, prompt, answer):
        run_dir = self.root / "control" / fid / f"run-{k}"
        run_dir.mkdir(parents=True)
        (run_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
        (run_dir / "meta.json").write_text(json.dumps({"answer": answer}), encoding="utf-8")

    def _magi_run(self, base, fid, k, prompt, votes):
        write_run(self.root / base, fid, k, result(votes=votes))
        (self.root / base / fid / f"run-{k}" / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    def test_comparison_counts_only_runs_with_the_current_facts(self):
        fx = fixture("f", should={"split": True}, facts=["a fact"])
        old = dict(fx, facts=["an earlier fact"])
        for k, answer in enumerate(("no_change", "no_change", "change"), 1):
            self._control_run("f", k, check.build_control_prompt(fx), answer)
        self._control_run("f", 4, check.build_control_prompt(old), "change")      # earlier facts: ignored
        self._magi_run("a", "f", 1, check.build_prompt(old), ("approve",) * 3)     # earlier facts: ignored
        self._magi_run("b", "f", 1, check.build_prompt(fx), ("reject",) * 3)
        self._magi_run("b", "f", 2, check.build_prompt(fx), ("approve", "reject", "reject"))
        (self.root / "control" / "run.json").write_text(json.dumps({"control": True}), encoding="utf-8")

        summary = check.check_control(self.root / "control", [self.root / "a", self.root / "b"], {"f": fx})
        row = summary["fixtures"]["f"]
        self.assertEqual(row["control"], ["no_change", "no_change", "change"])
        self.assertEqual((row["control_majority"], row["magi_majority"], row["agree"]), ("no_change", "no_change", True))
        self.assertEqual(row["magi_sources"], ["b (2)"])
        self.assertEqual((summary["agreed"], summary["compared"]), (1, 1))
        self.assertIn("Control agreed with MAGI on 1 of 1 fixtures", check.render_control(summary))

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(["control", str(self.root / "control"), str(self.root / "b")]), 0)
        self.assertTrue((self.root / "control" / "control.md").exists())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check.main(["control", str(self.root / "b"), str(self.root / "a")]), 2)  # not a control
            self.assertEqual(check.main(["results", str(self.root / "control")]), 2)  # results refuses a control


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

    def test_smoke_runs_the_marked_fixtures_once(self):
        fake = [sys.executable, str(Path(__file__).with_name("fake_agent.py")), "{prompt}"]
        fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
        marked = {fid for fid, fx in fixtures.items() if fx.get("smoke")}
        # One per kind of behaviour: every category but the trade-offs and designed conflicts, which say nothing in one run.
        self.assertEqual({fixtures[f]["category"] for f in marked},
                         {fx["category"] for fx in fixtures.values()} - {"split", "conflict", "preset", "bundled"})
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(["--name", "s", "--out", tmp, "--smoke", "--cmd-json", json.dumps(fake)]), 0)
            run_dir = Path(tmp) / "s"
            ran = {p.name for p in run_dir.iterdir() if p.is_dir()}
            self.assertEqual(ran, marked)
            self.assertEqual(len(list(run_dir.glob("*/run-*"))), len(marked))
            self.assertTrue(json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["smoke"])

            meta = json.loads((run_dir / "pressure-authority" / "run-1" / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["cost_usd"], 0.25)
            summary = check.check_results(run_dir, fixtures)
            self.assertEqual(summary["executions"], len(marked))
            self.assertEqual(summary["cost_usd"], 0.25 * len(marked))
            self.assertIn(f"${summary['cost_usd']:.2f} ($0.25 each)", check.render_report(summary))

    def test_control_run_with_a_fake_agent(self):
        fake = [sys.executable, str(Path(__file__).with_name("fake_agent.py")), "{prompt}"]
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run.main(["--name", "m", "--out", tmp, "--runs", "1", "--cmd-json", json.dumps(fake),
                                           "--only", "direction-lint-en,information"]), 0)
                self.assertEqual(run.main(["--name", "c", "--out", tmp, "--runs", "2", "--control",
                                           "--cmd-json", json.dumps(fake),
                                           "--only", "direction-lint-en,information"]), 0)
            control = Path(tmp) / "c"
            self.assertFalse((control / "information-rest-vs-grpc").exists())  # not a deliberation fixture
            meta = json.loads((control / "direction-lint-en-add" / "run-2" / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["answer"], "no_change")
            self.assertTrue(json.loads((control / "run.json").read_text(encoding="utf-8"))["control"])
            fixtures, _ = check.load_fixtures(check.FIXTURES_DIR)
            summary = check.check_control(control, [Path(tmp) / "m"], fixtures)
            self.assertEqual((summary["agreed"], summary["compared"]), (0, 2))  # fake MAGI approves, control does not
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(run.main(["--dry-run", "--control", "--only", "split-monorepo"]), 0)
        self.assertIn('"--safe-mode", "--tools", ""', out.getvalue())

    def test_smoke_and_only_narrow_together(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(run.main(["--dry-run", "--smoke", "--only", "direction"]), 0)
        self.assertEqual(out.getvalue().count("\n=== "), 1)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main(["--dry-run", "--smoke", "--runs", "0"]), 2)

    def test_only_rejects_unknown_names(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            run.main(["--dry-run", "--only", "no-such-fixture"])


if __name__ == "__main__":
    unittest.main()

"""Tests for e2e.py — each one builds a throwaway git repo and walks the real commands.

Run: python3 -m unittest skills/e2e-saas/scripts/test_e2e.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import e2e

STORY_MAP = """---
scope_approved: {approved}
autonomy: {autonomy}
threshold: 2
---
# Stories

## s01-skeleton — Walking skeleton
Lot: 0
Complexity: 2
Depends on: —
Signals: new-dependency

## s02-sign-up — Sign up with email
Lot: 1
Complexity: 3
Depends on: s01-skeleton
Signals: auth
"""

PLAN = """---
story: {id}
approved: no
complexity: {complexity}
signals: [{signals}]
premise: verified
owner_questions: no
---
# Plan
"""

REVIEW = """# Review
Review status: complete
Reviewed tree: {tree}
Pass: {passes}
Max severity: {severity}
Integration allowed: {allowed}
"""


def sh(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Project(unittest.TestCase):
    """A fresh project, framed and sliced, with the cwd inside it."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "acme"
        self.root.mkdir()
        self.previous_cwd = os.getcwd()
        os.chdir(self.root)
        sh("git", "init", "-q", "-b", "main", cwd=self.root)
        sh("git", "config", "user.email", "t@example.com", cwd=self.root)
        sh("git", "config", "user.name", "Test", cwd=self.root)
        e2e.init("acme")

    def tearDown(self) -> None:
        os.chdir(self.previous_cwd)
        self.tmp.cleanup()

    def write(self, relative: str, text: str, root: Path | None = None) -> Path:
        path = (root or self.root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit_on_build(self, message: str = "docs") -> None:
        sh("git", "add", "--all", cwd=self.root)
        sh("git", "commit", "-q", "-m", message, cwd=self.root)

    def frame(self, approved: str = "yes", autonomy: str = "full") -> None:
        self.write("docs/e2e/prd.md", "# PRD\n")
        self.write("docs/e2e/stories.md", STORY_MAP.format(approved=approved, autonomy=autonomy))
        self.write("docs/e2e/story-review.md", "Max severity: none\nStories ready: yes\n")
        self.set_checks({"test": "test -f app.txt", "build": "test -d docs"})
        self.commit_on_build("docs: frame")

    def set_checks(self, checks: dict[str, str], root: Path | None = None) -> None:
        path = (root or self.root) / e2e.CONFIG
        config = json.loads(path.read_text())
        config["checks"] = checks
        path.write_text(json.dumps(config, indent=2))

    def plan(self, story_id: str, complexity: int = 2, signals: str = "") -> Path:
        folder, _ = e2e.open_workshop(story_id)
        self.write(f"docs/e2e/stories/{story_id}/plan.md", PLAN.format(id=story_id, complexity=complexity, signals=signals), folder)
        return folder

    def build_and_verify(self, story_id: str, content: str = "hello") -> Path:
        folder = self.plan(story_id)
        e2e.approve(story_id, "loop")
        self.write("app.txt", content, folder)
        self.assertTrue(e2e.verify(story_id).startswith("passed"))
        return folder

    def review(self, story_id: str, folder: Path, allowed: str = "yes", severity: str = "none", passes: int = 1) -> None:
        tree = e2e.field_value(e2e.read_story_file(story_id, "verify.md"), "Tree")
        text = REVIEW.format(tree=tree, passes=passes, severity=severity, allowed=allowed)
        self.write(f"docs/e2e/stories/{story_id}/review.md", text, folder)

    def state_of(self, story_id: str) -> dict:
        return next(s for s in e2e.status()["stories"] if s["id"] == story_id)


class InitTest(Project):
    def test_init_creates_config_gitignore_and_checks_out_the_build_branch(self):
        self.assertTrue((self.root / "docs/e2e/config.json").exists())
        self.assertIn("node_modules/", (self.root / ".gitignore").read_text())
        self.assertEqual(e2e.current_branch(self.root), "e2e/build")

    def test_right_after_init_status_asks_for_the_interview(self):
        self.assertIn("Frame", e2e.status()["next"])


class StoryMapTest(unittest.TestCase):
    def test_parses_the_four_fields(self):
        story_map = e2e.parse_story_map(STORY_MAP.format(approved="yes", autonomy="full"))
        second = story_map.get("s02-sign-up")
        self.assertEqual((second.lot, second.complexity, second.depends_on, second.signals), ("1", 3, ["s01-skeleton"], ["auth"]))
        self.assertEqual(story_map.anomalies, [])

    def test_flags_backward_dependency_unknown_signal_and_duplicates(self):
        text = (
            "## s01-a — A\nLot: 0\nComplexity: 2\nDepends on: s02-b\nSignals: magic\n\n"
            "## s02-b — B\nLot: 0\nComplexity: 5\nDepends on: —\nSignals: —\n\n"
            "## s02-b — B again\nLot: 0\nComplexity: 1\nDepends on: —\nSignals: —\n"
        )
        anomalies = " | ".join(e2e.parse_story_map(text).anomalies)
        for expected in ("placed AFTER it", "unknown signal 'magic'", "complexity 5", "duplicate id"):
            self.assertIn(expected, anomalies)


class ApprovalTest(Project):
    def test_full_autonomy_lets_the_loop_approve_signals_except_data_deletion(self):
        self.frame(autonomy="full")
        story_map = e2e.require_story_map()
        story = story_map.get("s01-skeleton")
        self.assertIsNone(e2e.why_the_loop_cannot_approve(story, PLAN.format(id="x", complexity=4, signals="auth"), story_map))
        reason = e2e.why_the_loop_cannot_approve(story, PLAN.format(id="x", complexity=2, signals="data-deletion"), story_map)
        self.assertIn("data-deletion", reason)

    def test_guarded_autonomy_refuses_any_signal_and_high_complexity(self):
        self.frame(autonomy="guarded")
        story_map = e2e.require_story_map()
        story = story_map.get("s01-skeleton")  # carries new-dependency
        self.assertIn("signals", e2e.why_the_loop_cannot_approve(story, PLAN.format(id="x", complexity=1, signals=""), story_map))

    def test_the_planner_can_raise_the_score_never_lower_it(self):
        self.frame(autonomy="guarded")
        story_map = e2e.require_story_map()
        story = e2e.Story("s09-x", "X", "1", 3, [], [])
        self.assertIn("complexity 3", e2e.why_the_loop_cannot_approve(story, PLAN.format(id="x", complexity=1, signals=""), story_map))

    def test_an_unverified_premise_goes_to_the_owner(self):
        self.frame()
        story_map = e2e.require_story_map()
        plan = PLAN.format(id="x", complexity=1, signals="").replace("premise: verified", "premise: false")
        self.assertIn("premise", e2e.why_the_loop_cannot_approve(story_map.get("s01-skeleton"), plan, story_map))

    def test_no_story_opens_before_the_scope_is_approved(self):
        self.frame(approved="no")
        with self.assertRaises(e2e.Refusal):
            e2e.open_workshop("s01-skeleton")


class CycleTest(Project):
    def test_full_cycle_plan_verify_review_integrate_check(self):
        self.frame()
        self.assertEqual(self.state_of("s01-skeleton")["action"], "plan")
        folder = self.plan("s01-skeleton")
        self.assertEqual(self.state_of("s01-skeleton")["action"], "approve")
        e2e.approve("s01-skeleton", "loop")
        self.assertEqual(self.state_of("s01-skeleton")["action"], "build")
        self.write("app.txt", "hello", folder)
        self.assertTrue(e2e.verify("s01-skeleton").startswith("passed"))
        self.assertEqual(self.state_of("s01-skeleton")["action"], "review")
        self.review("s01-skeleton", folder)
        self.assertEqual(self.state_of("s01-skeleton")["action"], "integrate")
        e2e.integrate("s01-skeleton")
        self.assertIn("s01-skeleton", e2e.integrated(e2e.load_config()))
        self.assertFalse(folder.exists())
        self.assertEqual(e2e.status()["check"], "due")
        self.assertEqual(e2e.check(), "green")
        self.assertEqual(e2e.status()["for_the_loop"][0], {"story": None, "action": "lot-review", "lot": "0"})

    def test_failed_checks_are_recorded_and_never_committed(self):
        self.frame()
        folder = self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        self.assertTrue(e2e.verify("s01-skeleton").startswith("FAILED"))  # app.txt missing
        self.assertEqual(self.state_of("s01-skeleton")["action"], "fix")
        self.assertIn("Verification status: failed", (folder / "docs/e2e/stories/s01-skeleton/verify.md").read_text())

    def test_code_changed_after_verification_makes_the_record_stale(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.write("app.txt", "changed behind the record's back", folder)
        self.assertEqual(self.state_of("s01-skeleton")["action"], "verify")
        with self.assertRaises(e2e.Refusal):
            e2e.gate_verify_current("s01-skeleton")

    def test_a_refused_review_sends_the_story_back_then_to_the_owner_after_two_fixes(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder, allowed="no", severity="critical", passes=1)
        self.assertEqual(self.state_of("s01-skeleton")["action"], "fix")
        self.review("s01-skeleton", folder, allowed="no", severity="critical", passes=3)
        self.assertEqual(self.state_of("s01-skeleton")["state"], "stuck")

    def test_a_review_of_an_older_tree_does_not_open_integration(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        self.write("app.txt", "v2", folder)
        e2e.verify("s01-skeleton")
        with self.assertRaises(e2e.Refusal):
            e2e.gate_review_passed("s01-skeleton")
        self.assertEqual(self.state_of("s01-skeleton")["action"], "review")

    def test_integration_refuses_while_the_build_check_is_due(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        e2e.integrate("s01-skeleton")
        second = self.plan("s02-sign-up")
        e2e.approve("s02-sign-up", "loop")
        self.write("app.txt", "v2", second)
        e2e.verify("s02-sign-up")
        self.review("s02-sign-up", second)
        with self.assertRaisesRegex(e2e.Refusal, "due"):
            e2e.integrate("s02-sign-up")

    def test_a_red_build_check_blocks_integration_and_asks_for_repair(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        e2e.integrate("s01-skeleton")
        self.set_checks({"test": "test -f app.txt", "build": "false"})
        self.commit_on_build("break the build")
        self.assertEqual(e2e.check(), "red")
        self.assertEqual(e2e.status()["for_the_loop"][0]["action"], "repair-build")

    def test_dependencies_must_be_integrated_before_a_story_opens(self):
        self.frame()
        with self.assertRaisesRegex(e2e.Refusal, "waits for s01-skeleton"):
            e2e.open_workshop("s02-sign-up")

    def test_verify_refuses_a_project_without_checks(self):
        self.frame()
        self.set_checks({})
        self.commit_on_build("no checks yet")
        folder = self.plan("s01-skeleton")
        self.set_checks({}, folder)
        with self.assertRaisesRegex(e2e.Refusal, "No checks"):
            e2e.verify("s01-skeleton")

    def test_a_project_without_checks_is_never_green(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        e2e.integrate("s01-skeleton")
        self.set_checks({})
        self.commit_on_build("drop checks")
        self.assertEqual(e2e.check(), "red")

    def test_checks_that_cannot_fail_are_refused(self):
        self.frame()
        self.set_checks({"test": "true", "lint": "echo ok"})
        self.commit_on_build("fake checks")
        self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        with self.assertRaisesRegex(e2e.Refusal, "never fail"):
            e2e.verify("s01-skeleton")

    def test_an_approval_typed_by_an_agent_does_not_open_the_gate(self):
        self.frame()
        folder = self.plan("s01-skeleton", signals="data-deletion")
        plan = folder / "docs/e2e/stories/s01-skeleton/plan.md"
        plan.write_text(plan.read_text().replace("approved: no", "approved: yes\napproved_by: loop"))
        with self.assertRaisesRegex(e2e.Refusal, "may not"):
            e2e.gate_plan_approved("s01-skeleton")
        plan.write_text(plan.read_text().replace("approved_by: loop\n", ""))
        with self.assertRaisesRegex(e2e.Refusal, "approved_by"):
            e2e.gate_plan_approved("s01-skeleton")

    def test_a_story_cannot_loosen_an_existing_check_without_the_owner(self):
        self.frame()
        self.integrate_first_story()
        e2e.check()
        folder = self.plan("s02-sign-up")
        e2e.approve("s02-sign-up", "loop")
        self.set_checks({"test": "test -d docs", "build": "test -d docs", "e2e": "test -f app.txt"}, folder)
        e2e.verify("s02-sign-up")
        self.review("s02-sign-up", folder)
        with self.assertRaisesRegex(e2e.Refusal, "rewrites existing checks"):
            e2e.integrate("s02-sign-up")
        self.assertEqual(self.state_of("s02-sign-up")["state"], "checks-changed")

    def test_a_renamed_secret_is_still_refused(self):
        self.frame()
        folder = self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        self.write("app.txt", "x", folder)
        (folder / ".gitignore").write_text("")
        self.write("config.txt", "SECRET=1", folder)
        sh("git", "add", "config.txt", cwd=folder)
        sh("git", "commit", "-q", "-m", "tmp", cwd=folder)
        sh("git", "mv", "config.txt", ".env.production", cwd=folder)
        self.assertTrue(e2e.verify("s01-skeleton").startswith("FAILED"))

    def test_stop_file_empties_the_loop_queue(self):
        self.frame()
        self.write("docs/e2e/STOP", "")
        self.assertEqual(e2e.status()["for_the_loop"], [])

    def test_migrations_must_be_listed_in_the_ship_log(self):
        self.frame()
        config = json.loads((self.root / e2e.CONFIG).read_text())
        config["migration_dirs"] = ["migrations/"]
        (self.root / e2e.CONFIG).write_text(json.dumps(config))
        self.commit_on_build("migration dirs")
        folder = self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        self.write("app.txt", "x", folder)
        self.write("migrations/001_users.sql", "create table users();", folder)
        e2e.verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        with self.assertRaisesRegex(e2e.Refusal, "001_users.sql"):
            e2e.integrate("s01-skeleton")
        self.write("docs/e2e/stories/s01-skeleton/ship.md", "- migrations/001_users.sql before going live", folder)
        e2e.integrate("s01-skeleton")

    def integrate_first_story(self) -> None:
        folder = self.build_and_verify("s01-skeleton")
        self.review("s01-skeleton", folder)
        e2e.integrate("s01-skeleton")

    def test_a_repair_story_may_integrate_on_a_red_build_and_turns_it_green(self):
        self.frame()
        self.integrate_first_story()
        self.set_checks({"test": "test -f app.txt", "build": "test -f fixed.txt"})
        self.commit_on_build("a check the code does not meet")
        self.assertEqual(e2e.check(), "red")
        self.assertEqual(e2e.status()["for_the_loop"][0]["action"], "repair-build")
        stories = self.root / "docs/e2e/stories.md"
        stories.write_text(stories.read_text() + "\n## s03-repair-build — Repair the build\nLot: 0\nComplexity: 1\nDepends on: —\nSignals: —\nKind: repair\n")
        self.commit_on_build("repair story")
        self.assertNotIn("repair-build", [a["action"] for a in e2e.status()["for_the_loop"]])
        folder = self.plan("s03-repair-build")
        e2e.approve("s03-repair-build", "loop")
        self.write("fixed.txt", "x", folder)
        e2e.verify("s03-repair-build")
        self.review("s03-repair-build", folder)
        self.assertIn({"story": "s03-repair-build", "action": "integrate"}, e2e.status()["for_the_loop"])
        e2e.integrate("s03-repair-build")
        self.assertEqual(e2e.check(), "green")

    def test_a_feature_story_may_not_integrate_on_a_red_build(self):
        self.frame()
        self.integrate_first_story()
        self.set_checks({"test": "test -f app.txt", "build": "false"})
        self.commit_on_build("break")
        e2e.check()
        folder = self.plan("s02-sign-up")
        e2e.approve("s02-sign-up", "loop")
        self.write("more.txt", "x", folder)
        e2e.verify("s02-sign-up")
        self.review("s02-sign-up", folder)
        with self.assertRaisesRegex(e2e.Refusal, "red"):
            e2e.integrate("s02-sign-up")

    def test_changing_the_checks_on_the_build_branch_makes_the_check_due(self):
        self.frame()
        self.integrate_first_story()
        self.assertEqual(e2e.check(), "green")
        self.set_checks({"test": "test -d docs", "build": "test -d docs"})
        self.commit_on_build("weaken")
        self.assertEqual(e2e.status()["check"], "due")

    def test_a_story_cannot_weaken_its_own_checks(self):
        self.frame()
        folder = self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        self.set_checks({"test": "test -d docs"}, folder)  # app.txt never written
        self.assertTrue(e2e.verify("s01-skeleton").startswith("FAILED"))

    def test_secrets_and_dependencies_are_never_committed(self):
        self.frame()
        (self.root / ".gitignore").write_text("")
        self.commit_on_build("empty gitignore")
        folder = self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        self.write("app.txt", "x", folder)
        (folder / ".gitignore").write_text("")
        self.write(".env.local", "STRIPE_SECRET_KEY=sk_test_x", folder)
        self.write("node_modules/pkg/index.js", "", folder)
        self.assertTrue(e2e.verify("s01-skeleton").startswith("FAILED"))
        record = (folder / "docs/e2e/stories/s01-skeleton/verify.md").read_text()
        self.assertIn(".env.local", record)
        self.assertIn("node_modules/pkg/index.js", record)

    def test_repeated_failed_verifications_go_to_the_owner(self):
        self.frame()
        self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        for _ in range(e2e.MAX_VERIFY_ATTEMPTS + 1):
            e2e.verify("s01-skeleton")
        self.assertEqual(self.state_of("s01-skeleton")["state"], "stuck")

    def test_a_claimed_story_is_busy_and_offers_no_action(self):
        self.frame()
        self.plan("s01-skeleton")
        e2e.approve("s01-skeleton", "loop")
        e2e.claim("s01-skeleton", "builder")
        self.assertEqual(self.state_of("s01-skeleton")["state"], "busy")
        with self.assertRaises(e2e.Refusal):
            e2e.claim("s01-skeleton", "reviewer")
        e2e.release("s01-skeleton")
        self.assertEqual(self.state_of("s01-skeleton")["action"], "build")

    def test_a_false_premise_asks_for_a_rewrite_not_an_approval(self):
        self.frame()
        folder, _ = e2e.open_workshop("s01-skeleton")
        plan = PLAN.format(id="s01-skeleton", complexity=2, signals="").replace("premise: verified", "premise: false")
        self.write("docs/e2e/stories/s01-skeleton/plan.md", plan, folder)
        state = self.state_of("s01-skeleton")
        self.assertEqual((state["action"], state["for_the_owner"]), ("rewrite", None))

    def test_a_conflict_is_resolved_by_merging_not_by_rebuilding(self):
        self.frame()
        self.integrate_first_story()
        self.assertEqual(e2e.check(), "green")
        folder = self.plan("s02-sign-up")
        e2e.approve("s02-sign-up", "loop")
        self.write("notes.txt", "from the story", folder)
        e2e.verify("s02-sign-up")
        self.review("s02-sign-up", folder)
        self.write("notes.txt", "from the build branch")
        self.commit_on_build("someone else touched notes.txt")
        e2e.check()
        with self.assertRaisesRegex(e2e.Refusal, "Conflict"):
            e2e.integrate("s02-sign-up")
        self.assertEqual(self.state_of("s02-sign-up")["action"], "resume")
        e2e.resume("s02-sign-up")
        self.assertEqual(self.state_of("s02-sign-up")["action"], "fix")
        self.write("notes.txt", "both", folder)
        sh("git", "add", "notes.txt", cwd=folder)
        self.assertTrue(e2e.verify("s02-sign-up").startswith("passed"))
        self.assertFalse(e2e.merge_in_progress(folder))
        self.assertEqual(self.state_of("s02-sign-up")["action"], "review")

    def test_a_blocked_review_of_an_older_tree_no_longer_blocks(self):
        self.frame()
        folder = self.build_and_verify("s01-skeleton")
        self.write("docs/e2e/stories/s01-skeleton/review.md", "Review status: blocked\nReviewed tree: " + e2e.field_value(e2e.read_story_file("s01-skeleton", "verify.md"), "Tree") + "\nIntegration allowed: no\n", folder)
        self.assertEqual(self.state_of("s01-skeleton")["state"], "review-blocked")
        e2e.unblock("s01-skeleton")
        self.assertEqual(self.state_of("s01-skeleton")["action"], "review")

    def test_planner_raising_complexity_to_5_stops_the_loop(self):
        self.frame()
        story_map = e2e.require_story_map()
        reason = e2e.why_the_loop_cannot_approve(story_map.get("s01-skeleton"), PLAN.format(id="x", complexity=5, signals=""), story_map)
        self.assertIn("split", reason)


if __name__ == "__main__":
    unittest.main()

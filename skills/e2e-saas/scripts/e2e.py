#!/usr/bin/env python3
"""e2e — the mechanical half of E2E-SaaS.

STATE IS DERIVED FROM FILES, NEVER STORED. A story is planned when its plan
exists, verified when the script recorded a tree that still matches its code,
integrated when a commit on the build branch carries its `E2E-Story:` trailer.
Nothing else to keep in sync, so nothing can lie after an interruption: the
orchestrator resumes exactly where the files are.

GATES READ FILES, THEY DO NOT JUDGE. A gate never asks for an opinion: an exact
line is there or it is not.

    e2e.py init [--name NAME]           config, ship log and .gitignore; build branch checked out
    e2e.py doctor [--json]              git, python, companion plugins, config
    e2e.py status [--json]              every story, what the loop can do, what waits for you
    e2e.py gate {plan-approved|verify-current|review-passed} ID
    e2e.py approve ID --by {loop|owner}
    e2e.py workshop ID                  the story's worktree (created and set up if needed)
    e2e.py claim ID ROLE / release ID   a lease, so two agents never work in one worktree
    e2e.py verify ID                    runs the checks in the worktree, commits, writes verify.md
    e2e.py integrate ID                 squashes the story into the build branch, then cleans up
    e2e.py resume ID                    merges the current build branch into a conflicting story
    e2e.py unblock ID                   clears a blocked review once its cause is fixed
    e2e.py check                        setup, then every check, slow ones included, on the build branch

Standard library only: runs without a virtualenv, from any folder of the repo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

DOCS = "docs/e2e"
CONFIG = f"{DOCS}/config.json"
STORIES = f"{DOCS}/stories.md"
TRAILER = "E2E-Story"

SIGNALS = frozenset(
    {"migration", "auth", "payments", "external-api", "new-dependency", "new-screen", "data-deletion", "prod"}
)
ALWAYS_FOR_THE_OWNER = frozenset({"data-deletion"})
DEFAULT_THRESHOLD = 2
MAX_FIX_PASSES = 2
MAX_VERIFY_ATTEMPTS = 6
LEASE_HOURS = 3
DEFAULT_SLOW_CHECKS = ("build", "e2e", "audit")
ROOT_PORT = 3099
COMPANIONS = {
    "superpowers": "TDD, systematic debugging, verification before completion",
    "code-simplifier": "the simplification pass after every story",
    "pr-review-toolkit": "the lot reviews (silent failures, tests, type design)",
    "security-guidance": "security warnings on every edit",
}
# Never committed by `verify`, whatever the project's .gitignore says.
FORBIDDEN_STAGED = re.compile(
    r"(^|/)(node_modules|\.next|\.turbo|coverage|playwright-report|test-results)/"
    r"|(^|/)\.env(?!\.example$)[^/]*$"
    r"|\.(db|sqlite|sqlite3|log)$"
)
MAX_STAGED_BYTES = 5_000_000
BASE_GITIGNORE = """node_modules/
.env*
!.env.example
.next/
dist/
coverage/
playwright-report/
test-results/
*.log
*.db
*.sqlite
.DS_Store
"""

# A check that cannot fail is a lie told by a green light.
_NO_OP = re.compile(r"^\s*(?:true|:|exit\s+0|echo\b.*|printf\b.*|node\s+-e\s+['\"]?(?:process\.exit\(0\))?['\"]?)\s*$")
_ID = re.compile(r"^s(\d{2,3})-[a-z0-9]+(?:-[a-z0-9]+)*$")
_STORY_TITLE = re.compile(r"^## (s\d{2,3}-[a-z0-9-]+)\s+[—–-]\s+(.+?)\s*$")
_TREE = re.compile(r"^[0-9a-f]{40}$")
# What a tree comparison ignores: the paper trail written AFTER the checks it reports.
# config.json, the ship logs and the PRD are compared: changing the checks IS changing the code.
_OUTSIDE_DOCS = (
    ":(top)",
    *(f":(top,exclude){DOCS}/{path}" for path in (
        "stories/", "lots/", "journal.md", "check.md", "stories.md", "story-review.md", "STOP",
    )),
)


class Refusal(Exception):
    """A closed gate or a missing prerequisite. The message says what to do."""


# ─── Git ────────────────────────────────────────────────────────────────────


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def git_ok(*args: str, cwd: Path | None = None) -> bool:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False).returncode == 0


def changed_paths(folder: Path, *, untracked: bool) -> set[str]:
    """`git status --porcelain -z`, read WITHOUT strip(): the leading space is a column."""
    raw = subprocess.run(
        ["git", "status", "--porcelain", "-z", f"--untracked-files={'all' if untracked else 'no'}"],
        cwd=folder, capture_output=True, text=True, check=True,
    ).stdout
    paths, entries, i = set(), raw.split("\0"), 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) > 3:
            paths.add(entry[3:])
            if entry[0] in "RC":  # a rename carries the old path in the next entry
                i += 1
        i += 1
    return paths


def branch_exists(branch: str) -> bool:
    return git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")


def current_branch(folder: Path) -> str | None:
    return git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=folder, check=False) or None


def merge_in_progress(folder: Path) -> bool:
    return git_ok("rev-parse", "--verify", "--quiet", "MERGE_HEAD", cwd=folder)


def require_branch(folder: Path, branch: str) -> None:
    actual = current_branch(folder)
    if actual != branch:
        raise Refusal(
            f"{folder} is on {actual or 'a detached HEAD'}, not on {branch}. "
            "Stopping: never checkout or switch inside a working folder."
        )


def require_clean(folder: Path) -> None:
    if changed_paths(folder, untracked=False):
        raise Refusal(f"{folder} has uncommitted changes.")


def show(ref: str, path: str) -> str | None:
    if git_ok("cat-file", "-e", f"{ref}:{path}"):
        return git("show", f"{ref}:{path}")
    return None


# ─── Where things live ──────────────────────────────────────────────────────


def project_root() -> Path:
    """The main working tree, whichever worktree we are called from."""
    if not git_ok("rev-parse", "--git-dir"):
        raise Refusal("Not inside a git repository: run `e2e.py init` in the project folder.")
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common.parent


def story_branch(story_id: str) -> str:
    return f"e2e/story/{story_id}"


def worktrees_dir() -> Path:
    """Story worktrees are SIBLINGS of the project: no tool of the project ever scans them."""
    root = project_root()
    return root.parent / f"{root.name}.e2e"


def workshop_dir(story_id: str) -> Path:
    return worktrees_dir() / story_id


def story_docs(story_id: str) -> str:
    return f"{DOCS}/stories/{story_id}"


def read_story_file(story_id: str, name: str) -> str | None:
    """A story document: from its worktree when it exists, otherwise from its branch."""
    relative = f"{story_docs(story_id)}/{name}"
    folder = workshop_dir(story_id)
    if folder.exists():
        path = folder / relative
        return path.read_text(encoding="utf-8") if path.exists() else None
    branch = story_branch(story_id)
    return show(branch, relative) if branch_exists(branch) else None


# ─── Reading markdown ───────────────────────────────────────────────────────


def frontmatter(text: str | None) -> dict[str, str]:
    if not text or not text.startswith("---"):
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def field_value(text: str | None, key: str) -> str | None:
    """The value of an exact `Key: value` line at the start of a line; the LAST one wins.

    Records written by this script put their key lines LAST, after any free text, so a
    pasted `Tree:` in the middle can never replace the one recorded.
    """
    if not text:
        return None
    found = re.findall(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", text, flags=re.MULTILINE)
    return found[-1] if found else None


def as_list(value: str | None) -> list[str]:
    """`a, b` or `[a, b]`; `—`, `-`, `none` and empty mean the empty list."""
    if value is None:
        return []
    raw = value.strip().strip("[]")
    if raw.lower() in ("", "—", "-", "none"):
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def as_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def set_frontmatter(text: str, values: dict[str, str]) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise Refusal("The document has no `---` frontmatter.")
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise Refusal("The frontmatter is not closed.")
    pending = dict(values)
    for i in range(1, end):
        key = lines[i].split(":", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}: {pending.pop(key)}\n"
    added = [f"{key}: {value}\n" for key, value in pending.items()]
    return "".join(lines[:end] + added + lines[end:])


# ─── Config ─────────────────────────────────────────────────────────────────


@dataclass
class Config:
    name: str
    build_branch: str
    setup: str
    checks: dict[str, str]
    slow_checks: list[str]
    migration_dirs: list[str]

    @property
    def story_checks(self) -> dict[str, str]:
        return {name: command for name, command in self.checks.items() if name not in self.slow_checks}


def parse_config(text: str) -> Config:
    raw = json.loads(text)
    return Config(
        name=raw.get("name", "saas"),
        build_branch=raw.get("build_branch", "e2e/build"),
        setup=raw.get("setup", ""),
        checks={k: v for k, v in raw.get("checks", {}).items() if v},
        slow_checks=list(raw.get("slow_checks", DEFAULT_SLOW_CHECKS)),
        migration_dirs=list(raw.get("migration_dirs", [])),
    )


def load_config(folder: Path | None = None) -> Config:
    path = (folder or project_root()) / CONFIG
    if not path.exists():
        raise Refusal(f"No {CONFIG}. Run `e2e.py init` first.")
    return parse_config(path.read_text(encoding="utf-8"))


def no_op_checks(checks: dict[str, str]) -> list[str]:
    return sorted(name for name, command in checks.items() if _NO_OP.match(command))


def build_branch_config(config: Config) -> Config:
    """The checks a story must pass are the BUILD BRANCH's: a story cannot weaken its own gate."""
    text = show(config.build_branch, CONFIG)
    return parse_config(text) if text else config


# ─── The story map ──────────────────────────────────────────────────────────


@dataclass
class Story:
    id: str
    title: str
    lot: str | None
    complexity: int | None
    depends_on: list[str]
    signals: list[str]
    kind: str = "feature"

    @property
    def is_repair(self) -> bool:
        return self.kind == "repair"


@dataclass
class StoryMap:
    scope_approved: bool
    autonomy: str
    threshold: int
    stories: list[Story]
    anomalies: list[str] = field(default_factory=list)

    def get(self, story_id: str) -> Story:
        for story in self.stories:
            if story.id == story_id:
                return story
        known = ", ".join(s.id for s in self.stories) or "none"
        raise Refusal(f"Unknown story: {story_id}. Stories: {known}")

    def lots(self) -> list[str]:
        return list(dict.fromkeys(s.lot for s in self.stories if s.lot is not None))


def parse_story_map(text: str) -> StoryMap:
    head = frontmatter(text)
    stories: list[Story] = []
    for section in re.split(r"(?m)^(?=## )", text):
        match = _STORY_TITLE.match(section.splitlines()[0]) if section.strip() else None
        if match:
            story_id, title = match.groups()
            stories.append(Story(
                id=story_id,
                title=title,
                lot=field_value(section, "Lot"),
                complexity=as_int(field_value(section, "Complexity")),
                depends_on=as_list(field_value(section, "Depends on")),
                signals=as_list(field_value(section, "Signals")),
                kind=field_value(section, "Kind") or "feature",
            ))
    threshold = as_int(head.get("threshold"))
    return StoryMap(
        scope_approved=head.get("scope_approved") == "yes",
        autonomy=head.get("autonomy", "full"),
        threshold=DEFAULT_THRESHOLD if threshold is None else threshold,
        stories=stories,
        anomalies=story_map_anomalies(stories),
    )


def story_map_anomalies(stories: list[Story]) -> list[str]:
    anomalies = []
    ids = [s.id for s in stories]
    for story in stories:
        if not _ID.match(story.id):
            anomalies.append(f"{story.id}: malformed id (expected s01-slug)")
        if story.lot is None:
            anomalies.append(f"{story.id}: no `Lot:` line")
        if story.complexity is None or not 1 <= story.complexity <= 5:
            anomalies.append(f"{story.id}: complexity missing or outside 1-5")
        elif story.complexity == 5:
            anomalies.append(f"{story.id}: complexity 5, split it before planning")
        if story.kind not in ("feature", "repair"):
            anomalies.append(f"{story.id}: unknown kind '{story.kind}' (feature or repair)")
        anomalies.extend(f"{story.id}: unknown signal '{s}'" for s in story.signals if s not in SIGNALS)
        for dependency in story.depends_on:
            if dependency not in ids:
                anomalies.append(f"{story.id}: depends on {dependency}, which is not in the map")
            elif ids.index(dependency) > ids.index(story.id):
                anomalies.append(f"{story.id}: depends on {dependency}, placed AFTER it")
    anomalies.extend(f"{i}: duplicate id" for i in sorted({i for i in ids if ids.count(i) > 1}))
    numbers = [m.group(1) for m in (_ID.match(i) for i in ids) if m]
    anomalies.extend(f"s{n}: number used twice (ports are derived from it)" for n in sorted({n for n in numbers if numbers.count(n) > 1}))
    return anomalies


def load_story_map() -> StoryMap | None:
    path = project_root() / STORIES
    return parse_story_map(path.read_text(encoding="utf-8")) if path.exists() else None


def require_story_map() -> StoryMap:
    story_map = load_story_map()
    if story_map is None:
        raise Refusal(f"No story map ({STORIES}). Frame the SaaS first.")
    return story_map


def integrated(config: Config) -> set[str]:
    """Stories whose commit on the build branch carries the trailer: proof, not a promise."""
    if not branch_exists(config.build_branch):
        return set()
    out = git("log", config.build_branch, f"--format=%(trailers:key={TRAILER},valueonly)")
    return {value.strip() for value in out.splitlines() if value.strip()}


# ─── Gates ──────────────────────────────────────────────────────────────────


def gate_plan_approved(story_id: str) -> None:
    plan = read_story_file(story_id, "plan.md")
    if plan is None:
        raise Refusal(f"No plan for {story_id}. Plan it first.")
    if frontmatter(plan).get("approved") != "yes":
        raise Refusal(f"Plan of {story_id} is not approved (`approved: yes` missing).")


def gate_verify_current(story_id: str) -> None:
    """Does the verification record still describe the story's committed code?"""
    record = read_story_file(story_id, "verify.md")
    if record is None:
        raise Refusal(f"No verification record for {story_id}. Run `e2e.py verify {story_id}`.")
    if field_value(record, "Verification status") != "passed":
        raise Refusal(f"Verification of {story_id} did not pass.")
    tree = field_value(record, "Tree") or ""
    if not _TREE.match(tree):
        raise Refusal(f"Verification of {story_id} has no valid `Tree:` line.")
    folder = workshop_dir(story_id)
    where = folder if folder.exists() else None
    reference = "HEAD" if where else story_branch(story_id)
    if not git_ok("cat-file", "-e", f"{tree}^{{tree}}", cwd=where):
        raise Refusal(f"Tree {tree[:10]} of {story_id}'s record does not exist in the repo.")
    if not git_ok("diff", "--quiet", tree, reference, "--", *_OUTSIDE_DOCS, cwd=where):
        raise Refusal(f"The code of {story_id} changed after its verification: record is stale.")
    if where and uncommitted_code(story_id, where):
        raise Refusal(f"{story_id}'s worktree has uncommitted code: record is stale.")


def uncommitted_code(story_id: str, folder: Path) -> set[str]:
    prefix = f"{story_docs(story_id)}/"
    return {p for p in changed_paths(folder, untracked=True) if not p.startswith(prefix)}


def gate_review_passed(story_id: str) -> None:
    review = read_story_file(story_id, "review.md")
    if review is None:
        raise Refusal(f"No review for {story_id}.")
    if field_value(review, "Review status") != "complete":
        raise Refusal(f"The review of {story_id} is not complete.")
    if field_value(review, "Integration allowed") != "yes":
        raise Refusal(f"Review of {story_id}: integration not allowed.")
    if field_value(review, "Reviewed tree") != field_value(read_story_file(story_id, "verify.md"), "Tree"):
        raise Refusal(f"The review of {story_id} covers another tree than the last verification: review again.")


GATES = {
    "plan-approved": gate_plan_approved,
    "verify-current": gate_verify_current,
    "review-passed": gate_review_passed,
}


def gate_failure(gate, *args) -> str | None:
    """None when the gate is open, otherwise why it is closed."""
    try:
        gate(*args)
    except Refusal as refusal:
        return str(refusal)
    return None


# ─── Who may approve a plan ─────────────────────────────────────────────────


def why_the_loop_cannot_approve(story: Story, plan: str | None, story_map: StoryMap) -> str | None:
    """None when the loop may approve this plan itself; otherwise the reason it may not."""
    head = frontmatter(plan)
    notes = [n for n in (story.complexity, as_int(head.get("complexity"))) if n is not None]
    complexity = max(notes) if notes else None  # the planner can raise the score, never lower it
    signals = sorted(set(story.signals) | set(as_list(head.get("signals"))))
    if head.get("premise") != "verified":
        return f"premise '{head.get('premise') or 'not stated'}'"
    if head.get("owner_questions", "no") != "no":
        return "open questions for the owner"
    if complexity is None:
        return "complexity not stated"
    if complexity >= 5:
        return "complexity 5: split the story"
    blocking = ALWAYS_FOR_THE_OWNER if story_map.autonomy == "full" else SIGNALS
    if flagged := [s for s in signals if s in blocking]:
        return f"signals {', '.join(flagged)}"
    if story_map.autonomy != "full" and complexity > story_map.threshold:
        return f"complexity {complexity} above the threshold {story_map.threshold}"
    return None


# ─── Leases ─────────────────────────────────────────────────────────────────


def lease_path(story_id: str) -> Path | None:
    """Kept in the worktree's private git dir: never tracked, gone with the worktree."""
    folder = workshop_dir(story_id)
    if not folder.exists():
        return None
    return Path(git("rev-parse", "--absolute-git-dir", cwd=folder)) / "e2e-lease.json"


def active_lease(story_id: str) -> dict | None:
    path = lease_path(story_id)
    if path is None or not path.exists():
        return None
    lease = json.loads(path.read_text(encoding="utf-8"))
    taken = dt.datetime.fromisoformat(lease["since"])
    if dt.datetime.now(dt.timezone.utc) - taken > dt.timedelta(hours=LEASE_HOURS):
        return None
    return lease


def claim(story_id: str, role: str) -> None:
    path = lease_path(story_id)
    if path is None:
        raise Refusal(f"No worktree for {story_id}.")
    if (lease := active_lease(story_id)) and lease["role"] != role:
        raise Refusal(f"{story_id} is already being worked on by {lease['role']} since {lease['since']}.")
    path.write_text(json.dumps({"role": role, "since": now()}), encoding="utf-8")


def release(story_id: str) -> None:
    path = lease_path(story_id)
    if path is not None and path.exists():
        path.unlink()


# ─── Status ─────────────────────────────────────────────────────────────────


@dataclass
class StoryState:
    id: str
    title: str
    lot: str | None
    state: str
    action: str | None  # what the LOOP may do on its own; None = nothing
    for_the_owner: str | None
    detail: str = ""


def story_state(story: Story, story_map: StoryMap, done: set[str]) -> StoryState:
    def state(name, action=None, owner=None, detail=""):
        return StoryState(story.id, story.title, story.lot, name, action, owner, detail)

    missing = [d for d in story.depends_on if d not in done]
    if story.id in done:
        return state("integrated")
    if story.complexity == 5:
        return state("needs-split", owner=f"{story.id} scores 5: split it")
    if not branch_exists(story_branch(story.id)):
        return state("waiting", detail=", ".join(missing)) if missing else state("to-plan", "plan")
    if lease := active_lease(story.id):
        return state("busy", detail=f"{lease['role']} since {lease['since']}")

    plan = read_story_file(story.id, "plan.md")
    if plan is None:
        return state("to-plan", "plan", detail="worktree open, no plan")
    head = frontmatter(plan)
    if head.get("approved") != "yes":
        if head.get("premise") == "false":
            return state("premise-false", "rewrite", detail="research proved the story wrong")
        reason = why_the_loop_cannot_approve(story, plan, story_map)
        if reason is None:
            return state("plan-to-approve", "approve")
        return state("plan-to-approve", owner=f"approve the plan of {story.id} ({reason})", detail=reason)

    folder = workshop_dir(story.id)
    if read_story_file(story.id, "conflict.md") is not None:
        if folder.exists() and merge_in_progress(folder):
            return state("conflict", "fix", detail="resolve the merge with the build branch")
        return state("conflict", "resume", detail="integration hit the build branch")

    record = read_story_file(story.id, "verify.md")
    review = read_story_file(story.id, "review.md")
    passes = as_int(field_value(review, "Pass")) or 0
    attempts = as_int(field_value(record, "Attempts")) or 0
    review_is_current = review is not None and field_value(review, "Reviewed tree") == field_value(record, "Tree")

    if attempts > MAX_VERIFY_ATTEMPTS:
        return state("stuck", owner=f"{story.id} failed or repeated verification {attempts} times")
    if review_is_current and field_value(review, "Review status") == "blocked":
        return state("review-blocked", owner=f"the review of {story.id} could not complete: fix its cause, then `e2e.py unblock {story.id}`")
    if review_is_current and field_value(review, "Integration allowed") == "no":
        if passes > MAX_FIX_PASSES:
            return state("stuck", owner=f"{story.id} still refused after {passes} reviews")
        return state("to-fix", "fix", detail=f"review pass {passes} refused")
    if record is None:
        return state("to-build", "build")
    if field_value(record, "Verification status") == "failed":
        return state("to-fix", "fix", detail=f"checks failed (attempt {attempts}), see verify.md")
    if stale := gate_failure(gate_verify_current, story.id):
        return state("to-verify", "verify", detail=stale)
    if not review_is_current:
        return state("to-review", "review")
    if field_value(review, "Integration allowed") == "yes":
        return state("waiting", detail=", ".join(missing)) if missing else state("to-integrate", "integrate")
    return state("review-unreadable", owner=f"the review of {story.id} has no readable verdict")


def check_state(config: Config, done: set[str]) -> str:
    """`n/a` (nothing integrated), `due`, `green` or `red`, on the CURRENT build branch code."""
    if not done:
        return "n/a"
    root = project_root()
    path = root / DOCS / "check.md"
    if not path.exists():
        return "due"
    text = path.read_text(encoding="utf-8")
    tree = field_value(text, "Tree") or ""
    if not _TREE.match(tree) or not git_ok("cat-file", "-e", f"{tree}^{{tree}}", cwd=root):
        return "due"
    if not git_ok("diff", "--quiet", tree, config.build_branch, "--", *_OUTSIDE_DOCS, cwd=root):
        return "due"
    return "green" if field_value(text, "Check status") == "green" else "red"


def lot_review_done(lot: str) -> bool:
    path = project_root() / DOCS / "lots" / f"lot-{lot}-review.md"
    return path.exists() and field_value(path.read_text(encoding="utf-8"), "Lot review") == "done"


def framing_started() -> bool:
    docs = project_root() / DOCS
    return (docs / "prd.md").exists()


def status() -> dict:
    root = project_root()
    docs = root / DOCS
    report: dict = {
        "project": root.name,
        "stopped": (docs / "STOP").exists(),
        "prd": framing_started(),
        "stories_ready": None,
        "scope_approved": False,
        "check": "n/a",
        "anomalies": [],
        "stories": [],
        "for_the_loop": [],
        "for_the_owner": [],
        "next": "",
    }
    if not (root / CONFIG).exists():
        report["next"] = "Run `e2e.py init`, then frame the SaaS"
        return report
    config = load_config()
    review_of_map = docs / "story-review.md"
    if review_of_map.exists():
        report["stories_ready"] = field_value(review_of_map.read_text(encoding="utf-8"), "Stories ready") == "yes"
    story_map = load_story_map()
    if not report["prd"]:
        report["next"] = "Frame: interview the owner, then write docs/e2e/prd.md and stack.md"
    elif story_map is None:
        report["next"] = "Slice: write docs/e2e/stories.md"
    elif report["stories_ready"] is not True:
        report["next"] = "Have the story map reviewed (agent story-reviewer)"
    elif not story_map.scope_approved:
        report["next"] = "The owner approves the scope (scope_approved: yes)"
        report["for_the_owner"].append("approve the scope")
    if story_map is None:
        return report

    done = integrated(config)
    report["scope_approved"] = story_map.scope_approved
    report["anomalies"] = story_map.anomalies
    loop_may_act = story_map.scope_approved and report["stories_ready"]
    for story in story_map.stories:
        state = story_state(story, story_map, done)
        report["stories"].append(asdict(state))
        if state.for_the_owner:
            report["for_the_owner"].append(state.for_the_owner)
        if state.action and loop_may_act:
            report["for_the_loop"].append({"story": state.id, "action": state.action})

    report["check"] = check_state(config, done)
    repairs = {s.id for s in story_map.stories if s.is_repair}
    if report["check"] in ("due", "red"):
        # Nothing but a repair integrates onto a build branch whose current code is not green.
        report["for_the_loop"] = [
            a for a in report["for_the_loop"]
            if a["action"] != "integrate" or (report["check"] == "red" and a["story"] in repairs)
        ]
    if report["check"] == "due" and loop_may_act:
        report["for_the_loop"].insert(0, {"story": None, "action": "check"})
    open_repairs = [s for s in report["stories"] if s["id"] in repairs and s["state"] != "integrated"]
    if report["check"] == "red" and loop_may_act and not open_repairs:
        report["for_the_loop"].insert(0, {"story": None, "action": "repair-build"})
    if report["check"] == "green" and loop_may_act:
        # A finished lot is reviewed before anything new starts: its findings may become stories.
        finished = [
            lot for lot in story_map.lots()
            if all(s["state"] == "integrated" for s in report["stories"] if s["lot"] == lot)
        ]
        for lot in reversed([lot for lot in finished if not lot_review_done(lot)]):
            report["for_the_loop"].insert(0, {"story": None, "action": "lot-review", "lot": lot})

    all_in = story_map.stories and all(s["state"] == "integrated" for s in report["stories"])
    if all_in and report["check"] == "green" and all(lot_review_done(lot) for lot in story_map.lots()):
        report["next"] = "Everything is integrated, checked and reviewed: ship"
    elif not report["next"]:
        busy = any(s["state"] == "busy" for s in report["stories"])
        report["next"] = (
            "Loop round" if report["for_the_loop"]
            else "Agents are working: wait for them" if busy
            else "Nothing to do alone: see the owner queue"
        )
    if report["anomalies"]:
        report["for_the_loop"] = []  # a malformed map (duplicate, backward dependency) skews everything after it
        report["for_the_owner"].append("fix the story map (anomalies above)")
    if report["stopped"]:
        report["for_the_loop"] = []
        report["next"] = f"Stop requested ({DOCS}/STOP): the loop does nothing"
    return report


def render(report: dict) -> str:
    lines = [f"Project {report['project']} · build check: {report['check']}"]
    for story in report["stories"]:
        then = story["action"] or ("OWNER" if story["for_the_owner"] else "—")
        detail = f"  ({story['detail']})" if story["detail"] else ""
        lines.append(f"  {story['id']:<32} {story['state']:<16} → {then}{detail}")
    lines.extend(f"  ⚠️  {anomaly}" for anomaly in report["anomalies"])
    if report["for_the_owner"]:
        lines.append("For the owner:")
        lines.extend(f"  - {item}" for item in report["for_the_owner"])
    lines.append(f"Next: {report['next']}")
    return "\n".join(lines)


# ─── Running commands ───────────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    command: str
    code: int
    summary: str
    tail: str


def command_env(port: int, story_id: str) -> dict[str, str]:
    """What every setup and check command receives, so each worktree gets its own port and database."""
    return {
        **os.environ,
        "CI": "1",
        "E2E_PORT": str(port),
        "E2E_STORY": story_id,
        "E2E_PROJECT_ROOT": str(project_root()),
    }


def run_commands(commands: dict[str, str], folder: Path, env: dict[str, str]) -> list[CheckResult]:
    results = []
    for name, command in commands.items():
        done = subprocess.run(["bash", "-c", command], cwd=folder, env=env, capture_output=True, text=True, check=False)
        output = done.stdout + done.stderr
        results.append(CheckResult(name, command, done.returncode, summarize(output), last_lines(output, 40)))
    return results


def summarize(output: str) -> str:
    """The line that states counts ("42 passed"), otherwise the last line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    counts = [line for line in lines if re.search(r"\b(passed|failed|errors?|tests?)\b", line, re.IGNORECASE)]
    return (counts or lines or ["(no output)"])[-1].replace("|", "/")[:160]


def last_lines(output: str, count: int) -> str:
    return "\n".join(output.splitlines()[-count:])


def results_table(results: list[CheckResult]) -> str:
    rows = [f"| {r.name} | `{r.command}` | exit {r.code} · {r.summary} |" for r in results]
    return "| Step | Command | Result |\n|---|---|---|\n" + "\n".join(rows)


def failure_sections(results: list[CheckResult]) -> str:
    return "\n".join(f"### {r.name}\n\n```\n{r.tail}\n```\n" for r in results if r.code != 0)


def port_for(story_id: str) -> int:
    """A port per worktree derived from the story NUMBER (unique in the map): no collisions."""
    match = _ID.match(story_id)
    return 3100 + 10 * int(match.group(1)) if match else 3100


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def forbidden_staged(folder: Path) -> list[str]:
    """Paths about to be committed that never belong in a repo: dependencies, secrets, databases, blobs."""
    staged = git("diff", "--cached", "--name-only", "--diff-filter=AM", cwd=folder).splitlines()
    bad = [p for p in staged if FORBIDDEN_STAGED.search(p)]
    bad += [p for p in staged if (folder / p).is_file() and (folder / p).stat().st_size > MAX_STAGED_BYTES]
    return sorted(set(bad))


# ─── Actions ────────────────────────────────────────────────────────────────


def init(name: str | None) -> str:
    root = Path(git("rev-parse", "--show-toplevel", check=False) or os.getcwd())
    if not (root / ".git").exists():
        git("init", "--quiet", "-b", "main", cwd=root)
    templates = Path(__file__).resolve().parent.parent / "templates"
    docs = root / DOCS
    docs.mkdir(parents=True, exist_ok=True)
    ship = docs / "ship.md"
    if not ship.exists():
        ship.write_text((templates / "ship.md").read_text(encoding="utf-8"), encoding="utf-8")
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(BASE_GITIGNORE, encoding="utf-8")
    config_path = root / CONFIG
    if not config_path.exists():
        config = {
            "name": name or root.name,
            "build_branch": "e2e/build",
            "setup": "",
            "checks": {"typecheck": "", "lint": "", "design": "", "test": "", "build": "", "e2e": "", "audit": ""},
            "design": {"tokens_file": "src/app/globals.css", "source_dirs": ["src"], "primitives_dir": "src/components/ui"},
            "slow_checks": list(DEFAULT_SLOW_CHECKS),
            "migration_dirs": [],
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    git("add", "--", DOCS, ".gitignore", cwd=root)
    if not git_ok("rev-parse", "--verify", "--quiet", "HEAD", cwd=root) or changed_paths(root, untracked=False):
        git("commit", "--quiet", "-m", "chore(e2e): start the project", cwd=root)
    build = load_config(root).build_branch
    if current_branch(root) != build:
        require_clean(root)
        git("switch", "--quiet", *(() if branch_exists(build) else ("-c",)), build, cwd=root)
    return (
        f"Ready: {root} on {build}.\n"
        f"Story worktrees will live in {root.parent / (root.name + '.e2e')} — "
        f"allow it once so agents are never blocked: /add-dir {root.parent / (root.name + '.e2e')}\n"
        "Next: frame the SaaS with the owner."
    )


def doctor() -> dict:
    installed_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    installed: set[str] = set()
    if installed_file.exists():
        plugins = json.loads(installed_file.read_text(encoding="utf-8")).get("plugins", {})
        installed = {key.split("@", 1)[0] for key in plugins}
    report = {
        "git": git("--version", check=False),
        "python": sys.version.split()[0],
        "companions": {name: name in installed for name in COMPANIONS},
        "missing": [name for name in COMPANIONS if name not in installed],
        "note": "only user-scope plugins are visible here; a project-scope install shows as missing",
        "config": None,
    }
    try:
        config = load_config()
        report["config"] = {"setup": bool(config.setup), "checks": sorted(config.checks), "build_branch": config.build_branch}
    except Refusal as refusal:
        report["config"] = str(refusal)
    return report


def render_doctor(report: dict) -> str:
    lines = [f"git: {report['git']}", f"python: {report['python']}"]
    for name, present in report["companions"].items():
        mark = "✓" if present else "✗ missing"
        lines.append(f"{mark:<10} {name:<18} {COMPANIONS[name]}")
    if report["missing"]:
        lines.append(f"Install the missing companions ({report['note']}):")
        lines.extend(f"  /plugin install {name}@claude-plugins-official" for name in report["missing"])
    lines.append(f"config: {report['config']}")
    return "\n".join(lines)


def approve(story_id: str, by: str) -> None:
    story_map = require_story_map()
    story = story_map.get(story_id)
    path = workshop_dir(story_id) / story_docs(story_id) / "plan.md"
    if not path.exists():
        raise Refusal(f"No plan to approve at {path}.")
    text = path.read_text(encoding="utf-8")
    if by == "loop" and (reason := why_the_loop_cannot_approve(story, text, story_map)):
        raise Refusal(f"The loop cannot approve {story_id}: {reason}. For the owner.")
    values = {"approved": "yes", "approved_by": by, "approved_on": dt.date.today().isoformat()}
    path.write_text(set_frontmatter(text, values), encoding="utf-8")


def run_setup(folder: Path, config: Config, story_id: str) -> CheckResult | None:
    if not config.setup:
        return None
    return run_commands({"setup": config.setup}, folder, command_env(port_for(story_id), story_id))[0]


def open_workshop(story_id: str) -> tuple[Path, CheckResult | None]:
    story_map = require_story_map()
    if not story_map.scope_approved:
        raise Refusal("Scope not approved by the owner: no story opens.")
    story = story_map.get(story_id)
    config = load_config()
    branch, folder = story_branch(story_id), workshop_dir(story_id)
    if folder.exists():
        require_branch(folder, branch)
        return folder, None
    if missing := [d for d in story.depends_on if d not in integrated(config)]:
        raise Refusal(f"{story_id} waits for {', '.join(missing)}, not integrated yet.")
    folder.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "prune")
    if branch_exists(branch):
        git("worktree", "add", str(folder), branch)
    else:
        git("worktree", "add", "--no-track", "-b", branch, str(folder), config.build_branch)
    return folder, run_setup(folder, build_branch_config(config), story_id)


def verify(story_id: str) -> str:
    """Runs the story checks IN the worktree, commits the code, records the exact tree tested.

    The record is written by this script, never by an agent: a check that did not
    run cannot be reported as passed. The checks come from the BUILD BRANCH; only the
    skeleton story, when the build branch has none yet, brings its own.
    """
    story = require_story_map().get(story_id)
    folder = workshop_dir(story_id)
    if not folder.exists():
        raise Refusal(f"No worktree for {story_id}.")
    require_branch(folder, story_branch(story_id))
    official = build_branch_config(load_config())
    config = official if official.story_checks else load_config(folder)
    if not config.story_checks:
        raise Refusal(f"No checks in {CONFIG}: the skeleton story must configure typecheck, lint and test.")
    if fake := no_op_checks(config.checks):
        raise Refusal(f"Checks that can never fail in {CONFIG}: {fake}. Give each one a real command.")
    docs = folder / story_docs(story_id)
    docs.mkdir(parents=True, exist_ok=True)
    record_path = docs / "verify.md"
    attempts = (as_int(field_value(record_path.read_text(encoding="utf-8"), "Attempts")) or 0) + 1 if record_path.exists() else 1

    results = run_commands(config.story_checks, folder, command_env(port_for(story_id), story_id))
    tree, problem = "—", ""
    if all(r.code == 0 for r in results):
        conflict = docs / "conflict.md"
        if conflict.exists():
            conflict.unlink()
        git("add", "--all", cwd=folder)
        if forbidden := forbidden_staged(folder):
            git("reset", "--quiet", "--", ".", cwd=folder)  # path form: an ongoing merge survives
            problem = f"## Refused files\n\nThese never belong in the repo; fix .gitignore:\n\n" + "\n".join(f"- `{p}`" for p in forbidden) + "\n\n"
        else:
            tree = git("write-tree", cwd=folder)
    passed = tree != "—"
    notes = docs / "build-notes.md"
    record_path.write_text(
        f"# Verification — {story_id}\n\n"
        "> Written by `e2e.py verify`, never by hand. The tree is exactly the code the checks ran on.\n\n"
        f"{results_table(results)}\n\n{failure_sections(results)}{problem}"
        f"## Builder notes\n\n{notes.read_text(encoding='utf-8') if notes.exists() else '(none)'}\n\n"
        "## Not proven here\n\nSlow checks (" + ", ".join(config.slow_checks) + ") run on the build branch "
        "after integration (`e2e.py check`).\n\n"
        f"When: {now()}\nPort: {port_for(story_id)}\nAttempts: {attempts}\nTree: {tree}\n"
        f"Verification status: {'passed' if passed else 'failed'}\n",
        encoding="utf-8",
    )
    if not passed:
        return f"FAILED — see {record_path}"
    git("add", "--all", cwd=folder)
    if changed_paths(folder, untracked=False) or merge_in_progress(folder):
        git("commit", "--quiet", "--no-verify", "-m", f"feat: {story.title}", cwd=folder)
    return f"passed — tree {tree[:10]}"


def migrations_missing_from_ship_log(story_id: str, config: Config) -> list[str]:
    """A migration the story adds must be listed in the story's own ship notes."""
    if not config.migration_dirs:
        return []
    branch = story_branch(story_id)
    touched = git(
        "diff", "--name-only", "--diff-filter=AMR", f"{config.build_branch}...{branch}", "--", *config.migration_dirs,
    ).splitlines()
    notes = read_story_file(story_id, "ship.md") or ""
    return sorted(path for path in touched if path not in notes)


def integrate(story_id: str) -> str:
    """Squash the story into the build branch. Never main: the owner ships."""
    story_map = require_story_map()
    story = story_map.get(story_id)
    config = load_config()
    root = project_root()
    done = integrated(config)
    if story_id in done:
        raise Refusal(f"{story_id} is already integrated.")
    if missing := [d for d in story.depends_on if d not in done]:
        raise Refusal(f"Dependencies first: {', '.join(missing)}")
    if (root / DOCS / "STOP").exists():
        raise Refusal("Stop requested: no integration.")
    # Gates live HERE, not only in `status`: a direct call goes through them too.
    check = check_state(config, done)
    if check == "due" or (check == "red" and not story.is_repair):
        raise Refusal(f"Build check is '{check}': only a green check (or a repair story on red) lets a story in.")
    gate_plan_approved(story_id)
    gate_verify_current(story_id)
    gate_review_passed(story_id)
    if forgotten := migrations_missing_from_ship_log(story_id, config):
        raise Refusal(f"{story_id} adds migrations missing from {story_docs(story_id)}/ship.md: {forgotten}")

    require_branch(root, config.build_branch)
    require_clean(root)
    folder = workshop_dir(story_id)
    if folder.exists():
        commit_review(story_id, folder)
    merge = subprocess.run(
        ["git", "merge", "--squash", story_branch(story_id)], cwd=root, capture_output=True, text=True, check=False
    )
    if merge.returncode != 0:
        git("reset", "--merge", cwd=root, check=False)
        if folder.exists():
            conflict = folder / story_docs(story_id) / "conflict.md"
            conflict.write_text(f"# Integration conflict\n\n```\n{merge.stdout}{merge.stderr}```\n", encoding="utf-8")
        raise Refusal(f"Conflict integrating {story_id}: nothing integrated. Resume it.\n{merge.stdout}{merge.stderr}")
    scope = f"lot-{story.lot}" if story.lot else "e2e"
    message = f"feat({scope}): {story.title}\n\n{TRAILER}: {story_id}\n"
    commit = subprocess.run(
        ["git", "commit", "--quiet", "--no-verify", "-F", "-"], cwd=root, input=message, text=True, capture_output=True, check=False
    )
    if commit.returncode != 0 or story_id not in integrated(config):
        git("reset", "--merge", cwd=root, check=False)
        raise Refusal(f"The integration commit of {story_id} failed, nothing integrated: {commit.stderr.strip()}")
    # Cleanup only on PROOF: the trailer is in the build branch history.
    if folder.exists():
        git("worktree", "remove", "--force", str(folder), cwd=root)
    git("branch", "-D", story_branch(story_id), cwd=root)
    return git("rev-parse", "--short", "HEAD", cwd=root)


def commit_review(story_id: str, folder: Path) -> None:
    """Only the story's own documents may be pending (the review is written after the code commit)."""
    require_branch(folder, story_branch(story_id))
    if foreign := sorted(uncommitted_code(story_id, folder)):
        raise Refusal(f"{story_id}'s worktree is not clean, nothing integrated: {foreign}")
    if changed_paths(folder, untracked=True):
        git("add", "--", story_docs(story_id), cwd=folder)
        git("commit", "--quiet", "--no-verify", "-m", f"docs(e2e): review of {story_id}", cwd=folder)


def resume(story_id: str) -> str:
    """A story that hit the build branch takes the build branch IN, instead of being rebuilt.

    A clean merge goes straight back to verification. A conflicting one stays in progress,
    markers and all, for the builder to resolve; `verify` then concludes the merge.
    """
    folder = workshop_dir(story_id)
    if not folder.exists():
        folder, _ = open_workshop(story_id)
    require_branch(folder, story_branch(story_id))
    commit_review(story_id, folder)
    build = load_config().build_branch
    merge = subprocess.run(["git", "merge", "--no-edit", build], cwd=folder, capture_output=True, text=True, check=False)
    if merge.returncode == 0:
        conflict = folder / story_docs(story_id) / "conflict.md"
        if conflict.exists():
            conflict.unlink()
        return f"{story_id}: {build} merged cleanly. Verify it again."
    conflicts = git("diff", "--name-only", "--diff-filter=U", cwd=folder)
    (folder / story_docs(story_id) / "conflict.md").write_text(
        f"# Merge conflict with {build}\n\nResolve these files, `git add` them, do not commit:\n\n```\n{conflicts}\n```\n",
        encoding="utf-8",
    )
    return f"{story_id}: conflicts left for the builder to resolve:\n{conflicts}"


def unblock(story_id: str) -> None:
    folder = workshop_dir(story_id)
    review = folder / story_docs(story_id) / "review.md"
    if not review.exists() or field_value(review.read_text(encoding="utf-8"), "Review status") != "blocked":
        raise Refusal(f"{story_id} has no blocked review.")
    review.unlink()


def check() -> str:
    """Two stories right on their own can be wrong together: setup, then every check, once."""
    config = load_config()
    root = project_root()
    require_branch(root, config.build_branch)
    require_clean(root)
    tree = git("rev-parse", "HEAD^{tree}", cwd=root)
    env = command_env(ROOT_PORT, "build")
    steps = ({"setup": config.setup} if config.setup else {}) | config.checks
    fake = no_op_checks(config.checks)
    results = run_commands(steps, root, env) if config.checks and not fake else []
    verdict = "green" if results and all(r.code == 0 for r in results) else "red"
    body = (
        results_table(results) if results
        else f"Checks that can never fail: {fake}. A no-op is never green." if fake
        else "No checks configured: a project without tests is never green."
    )
    path = root / DOCS / "check.md"
    path.write_text(
        f"# Build check\n\n{body}\n\n{failure_sections(results)}\nWhen: {now()}\nTree: {tree}\nCheck status: {verdict}\n",
        encoding="utf-8",
    )
    git("add", "--", str(path.relative_to(root)), cwd=root)
    git("commit", "--quiet", "--no-verify", "-m", f"docs(e2e): build check ({verdict})", cwd=root)
    return verdict


# ─── CLI ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e2e.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--name")
    sub.add_parser("doctor").add_argument("--json", action="store_true")
    sub.add_parser("status").add_argument("--json", action="store_true")
    p = sub.add_parser("gate")
    p.add_argument("gate", choices=sorted(GATES))
    p.add_argument("story")
    p = sub.add_parser("approve")
    p.add_argument("story")
    p.add_argument("--by", choices=["loop", "owner"], required=True)
    p = sub.add_parser("claim")
    p.add_argument("story")
    p.add_argument("role")
    for name in ("workshop", "release", "verify", "integrate", "resume", "unblock"):
        sub.add_parser(name).add_argument("story")
    sub.add_parser("check")
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            print(init(args.name))
        elif args.command == "doctor":
            report = doctor()
            print(json.dumps(report, indent=2) if args.json else render_doctor(report))
        elif args.command == "status":
            report = status()
            print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render(report))
        elif args.command == "gate":
            GATES[args.gate](args.story)
            print(f"Gate {args.gate} open for {args.story}.")
        elif args.command == "approve":
            approve(args.story, args.by)
            print(f"Plan of {args.story} approved by: {args.by}.")
        elif args.command == "workshop":
            folder, setup = open_workshop(args.story)
            print(folder)
            print(f"Port for this worktree: {port_for(args.story)} (E2E_PORT in every setup and check)")
            if setup is not None:
                print(f"Setup: exit {setup.code} · {setup.summary}")
                if setup.code != 0:
                    print(setup.tail)
        elif args.command == "claim":
            claim(args.story, args.role)
            print(f"{args.story} claimed by {args.role}.")
        elif args.command == "release":
            release(args.story)
            print(f"{args.story} released.")
        elif args.command == "verify":
            outcome = verify(args.story)
            print(f"{args.story}: {outcome}")
            return 0 if outcome.startswith("passed") else 1
        elif args.command == "integrate":
            print(f"{args.story} integrated: {integrate(args.story)}")
        elif args.command == "resume":
            print(resume(args.story))
        elif args.command == "unblock":
            unblock(args.story)
            print(f"{args.story}: blocked review cleared.")
        elif args.command == "check":
            verdict = check()
            print(f"Build check: {verdict}.")
            return 0 if verdict == "green" else 1
    except Refusal as refusal:
        print(f"e2e: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

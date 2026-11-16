#!/usr/bin/env python3
"""Version and release checks for the MAGI repository.

The skill version lives in .claude-plugin/plugin.json. Claude Code skips a plugin
update when the version string is unchanged, so every change under skills/ must
come with a version bump, or installed users never receive it. The manifests for
other hosts (Codex, Gemini CLI) carry the same version and must match it.

Subcommands:
  check-pr BASE      Fail if skills/ changed since BASE without a version bump,
                     if the version went down, or if the new version has no
                     CHANGELOG section. Used by the PR check workflow.
  check-release      Validate the current tree and print the version.
                     Used by the release workflow.
  notes VERSION      Print the CHANGELOG section for VERSION.
  bump PART          Raise the version (patch, minor or major) in every
                     manifest and add an empty CHANGELOG section. For local use.

Standard library only; run from the repository root.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_JSON = ".claude-plugin/plugin.json"
# Other hosts' manifests; each carries the same version as PLUGIN_JSON.
MIRROR_JSONS = [".codex-plugin/plugin.json", "gemini-extension.json"]
CHANGELOG = "CHANGELOG.md"
SKILL_MD = "skills/magi/SKILL.md"
SKILL_DIR = "skills/"
DESCRIPTION_LIMIT = 200
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class CheckError(Exception):
    pass


def parse_version(text: str) -> tuple:
    m = VERSION_RE.match(text or "")
    if not m:
        raise CheckError(f"version must be MAJOR.MINOR.PATCH, got {text!r}")
    return tuple(int(x) for x in m.groups())


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def version_at(ref: str):
    """plugin.json version at a git ref, or None if the file does not exist there."""
    try:
        return json.loads(git("show", f"{ref}:{PLUGIN_JSON}"))["version"]
    except subprocess.CalledProcessError:
        return None


def current_version() -> str:
    return json.loads(Path(PLUGIN_JSON).read_text(encoding="utf-8"))["version"]


def changelog_section(version: str) -> str:
    text = Path(CHANGELOG).read_text(encoding="utf-8")
    m = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return ""
    # A bare "-" bullet (the placeholder that bump adds) does not count as content.
    lines = [line for line in m.group(1).splitlines() if not re.fullmatch(r"\s*-?\s*", line)]
    return m.group(1).strip() if lines else ""


def check_description() -> None:
    text = Path(SKILL_MD).read_text(encoding="utf-8")
    m = re.search(r'^description: "(.*)"$', text, re.M)
    if not m:
        raise CheckError(f"no description line in {SKILL_MD}")
    if len(m.group(1)) > DESCRIPTION_LIMIT:
        raise CheckError(f"{SKILL_MD} description is {len(m.group(1))} characters (limit {DESCRIPTION_LIMIT})")


def check_mirrors(version: str) -> None:
    for path in MIRROR_JSONS:
        other = json.loads(Path(path).read_text(encoding="utf-8")).get("version")
        if other != version:
            raise CheckError(
                f"{path} version is {other!r} but {PLUGIN_JSON} is {version!r}. "
                f"Run: python3 .github/scripts/release_tools.py bump <part>, or fix it by hand"
            )


def check_tree() -> str:
    version = current_version()
    parse_version(version)
    check_mirrors(version)
    if not changelog_section(version):
        raise CheckError(f"{CHANGELOG} has no non-empty section '## [{version}]'")
    check_description()
    return version


def check_pr(base: str) -> None:
    merge_base = git("merge-base", base, "HEAD").strip()
    changed = [p for p in git("diff", "--name-only", merge_base, "HEAD").splitlines() if p]
    skill_changed = any(p.startswith(SKILL_DIR) for p in changed)
    old, new = version_at(merge_base), current_version()
    new_t = parse_version(new)

    if old is not None:
        old_t = parse_version(old)
        if new_t < old_t:
            raise CheckError(f"version went down: {old} -> {new}")
        if skill_changed and new_t == old_t:
            files = ", ".join(p for p in changed if p.startswith(SKILL_DIR))
            raise CheckError(
                f"{SKILL_DIR} changed ({files}) but {PLUGIN_JSON} is still {new}. "
                f"Installed users only get an update when the version changes. "
                f"Run: python3 .github/scripts/release_tools.py bump patch"
            )
    version_changed = old != new
    if version_changed or skill_changed:
        check_tree()
    else:
        check_mirrors(new)
        check_description()
    state = f"{old} -> {new}" if version_changed else f"{new} (unchanged)"
    print(f"OK: version {state}; skill files changed: {'yes' if skill_changed else 'no'}")


def bump(part: str) -> None:
    major, minor, patch = parse_version(current_version())
    new = {"major": (major + 1, 0, 0), "minor": (major, minor + 1, 0), "patch": (major, minor, patch + 1)}[part]
    new_s = ".".join(map(str, new))
    for name in [PLUGIN_JSON, *MIRROR_JSONS]:
        path = Path(name)
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r'("version"\s*:\s*")[^"]*(")', rf"\g<1>{new_s}\2", text, count=1), encoding="utf-8")
    log = Path(CHANGELOG).read_text(encoding="utf-8")
    first = re.search(r"^## ", log, re.M)
    entry = f"## [{new_s}]\n\n- \n\n"
    log = log[: first.start()] + entry + log[first.start():] if first else log.rstrip() + "\n\n" + entry
    Path(CHANGELOG).write_text(log, encoding="utf-8")
    print(f"{new_s}: updated {', '.join([PLUGIN_JSON, *MIRROR_JSONS])}; fill in the new section in {CHANGELOG}")


def main(argv: list) -> int:
    try:
        if len(argv) == 2 and argv[0] == "check-pr":
            check_pr(argv[1])
        elif argv == ["check-release"]:
            print(check_tree())
        elif len(argv) == 2 and argv[0] == "notes":
            section = changelog_section(argv[1])
            if not section:
                raise CheckError(f"no CHANGELOG section for {argv[1]}")
            print(section)
        elif len(argv) == 2 and argv[0] == "bump" and argv[1] in ("patch", "minor", "major"):
            bump(argv[1])
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except CheckError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

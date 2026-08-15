#!/usr/bin/env python3
"""Offline structural and interaction-contract validation for H-SmartLearn.

This is deliberately stricter than a simple button count. It verifies that the
three user-selectable learning flows bind visible selected state and submit
enablement to explicit primitive @State values.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ETS_ROOT = ROOT / "entry" / "src" / "main" / "ets"
PAGES_JSON = ROOT / "entry" / "src" / "main" / "resources" / "base" / "profile" / "main_pages.json"


def fail(message: str) -> None:
    raise AssertionError(message)


def strip_strings_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    state = "code"
    quote = ""
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line_comment"; out.extend("  "); i += 2; continue
            if ch == "/" and nxt == "*":
                state = "block_comment"; out.extend("  "); i += 2; continue
            if ch in ("'", '"', "`"):
                state = "string"; quote = ch; out.append(" "); i += 1; continue
            out.append(ch); i += 1; continue
        if state == "line_comment":
            if ch == "\n": state = "code"; out.append("\n")
            else: out.append(" ")
            i += 1; continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"; out.extend("  "); i += 2
            else:
                out.append("\n" if ch == "\n" else " "); i += 1
            continue
        if state == "string":
            if ch == "\\":
                out.append(" ");
                if i + 1 < len(source): out.append(" ")
                i += 2; continue
            if ch == quote:
                state = "code"; quote = ""; out.append(" "); i += 1; continue
            out.append("\n" if ch == "\n" else " "); i += 1
    if state in {"string", "block_comment"}:
        fail(f"unterminated {state}")
    return "".join(out)


def validate_balanced(path: Path) -> None:
    cleaned = strip_strings_comments(path.read_text(encoding="utf-8"))
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    for index, char in enumerate(cleaned):
        if char in "([{": stack.append((char, index))
        elif char in ")]}":
            if not stack or stack[-1][0] != pairs[char]:
                fail(f"{path}: unmatched {char} at offset {index}")
            stack.pop()
    if stack:
        fail(f"{path}: unclosed {stack[-1][0]} at offset {stack[-1][1]}")


def validate_imports(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for relative in re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", source):
        base = (path.parent / relative).resolve()
        candidates = [base, base.with_suffix(".ets"), base / "index.ets"]
        if not any(candidate.exists() for candidate in candidates):
            fail(f"{path}: unresolved relative import {relative}")


def require(source: str, pattern: str, label: str) -> None:
    if re.search(pattern, source, flags=re.S) is None:
        fail(f"missing interaction contract: {label}")


def reject(source: str, pattern: str, label: str) -> None:
    if re.search(pattern, source, flags=re.S) is not None:
        fail(f"fragile interaction pattern remains: {label}")


def validate_quiz_contract() -> None:
    source = (ETS_ROOT / "pages" / "QuizPage.ets").read_text(encoding="utf-8")
    require(source, r"@State\s+private\s+currentSelectedKey:\s*string", "diagnostic primitive selected key")
    require(source, r"@State\s+private\s+progressState:\s*number", "diagnostic primitive progress state")
    require(source, r"@State\s+private\s+canSubmit:\s*boolean", "diagnostic primitive submit flag")
    require(source, r"this\.selectedKeys\s*=\s*nextKeys", "diagnostic array reassignment")
    require(source, r"this\.currentSelectedKey\s*=\s*key", "diagnostic selected-state assignment")
    require(source, r"this\.canSubmit\s*=\s*SelectionStateUtil\.allAnswered\(nextKeys,\s*this\.items\.length\)", "diagnostic explicit submit calculation")
    require(source, r"Radio\([\s\S]*?\.checked\(this\.currentSelectedKey\s*===\s*option\.key\)", "diagnostic native Radio binding")
    require(source, r"\.onClick\(\(\)\s*=>\s*this\.selectAnswer\(option\.key\)\)", "diagnostic whole-card selection")
    require(source, r"\.enabled\(!this\.submitting\)", "diagnostic submit remains actionable for missing-answer guidance")
    require(source, r"backgroundColor\(this\.currentSelectedKey\s*===\s*option\.key", "diagnostic visible highlight")
    require(source, r"\(this\.selectedKeys\[index\]\s*\|\|\s*''\)\.length\s*>\s*0", "diagnostic direct question-marker state")
    reject(source, r"get\s+selectedAnswer", "diagnostic getter-derived selected state")
    reject(source, r"get\s+allAnswered", "diagnostic getter-derived submit state")
    reject(source, r"answers\.find", "diagnostic object-array lookup in render")


def validate_resource_contract() -> None:
    source = (ETS_ROOT / "pages" / "ResourceViewPage.ets").read_text(encoding="utf-8")
    require(source, r"@State\s+private\s+testSelectedKeys:\s*string\[\]", "resource test primitive answers")
    require(source, r"@State\s+private\s+canSubmitTest:\s*boolean", "resource test submit flag")
    require(source, r"@State\s+private\s+practiceStatuses:\s*string\[\]", "practice primitive statuses")
    require(source, r"Radio\([\s\S]*?\.checked\(\(this\.testSelectedKeys\[index\]\s*\|\|\s*''\)\s*===\s*option\.key\)", "resource test Radio binding")
    require(source, r"\.enabled\(!this\.testSubmitting\)", "resource test submit remains actionable for missing-answer guidance")
    require(source, r"this\.canSubmitTest\s*=\s*SelectionStateUtil\.allAnswered\(next,\s*items\.length\)", "resource test explicit submit calculation")
    require(source, r"this\.practiceStatuses\s*=\s*next", "practice status array reassignment")
    require(source, r"!this\.testSubmitted\s*\?[\s\S]*?this\.testSelectedKeys\[index\]", "resource direct pre-submit highlight")
    reject(source, r"testAnswers\.find", "resource test object lookup")
    reject(source, r"completedSteps|failedSteps", "parallel practice status stores")


def validate_profile_contract() -> None:
    profile = (ETS_ROOT / "pages" / "LearnerProfilePage.ets").read_text(encoding="utf-8")
    for group, state in (
        ("profile_education", "education"),
        ("profile_explain_style", "explainStyle"),
        ("profile_resource_priority", "resourcePriority"),
    ):
        require(profile, rf"Radio\(\{{\s*value:\s*option,\s*group:\s*'{group}'\s*\}}\)[\s\S]*?\.checked\(this\.{state}\s*===\s*option\)", f"profile {state} Radio")


def validate_pages_and_routes() -> None:
    page_data = json.loads(PAGES_JSON.read_text(encoding="utf-8"))
    pages = set(page_data["src"])
    for page in pages:
        if not (ETS_ROOT / f"{page}.ets").exists():
            fail(f"registered page does not exist: {page}")
    routes: set[str] = set()
    for path in ETS_ROOT.rglob("*.ets"):
        routes.update(re.findall(r"url:\s*['\"](pages/[^'\"]+)['\"]", path.read_text(encoding="utf-8")))
    missing = sorted(route for route in routes if route not in pages)
    if missing:
        fail(f"unregistered route targets: {missing}")



def validate_button_contracts() -> int:
    """Reject visible Button declarations that lack a nearby action or state feedback.

    ArkUI modifier chains in this project are kept within 40 lines of the
    Button declaration. Builder invocations are validated at their definitions.
    """
    builder_invocations = (
        "this.navButton(", "this.domainButton(", "this.actionButton(", "this.toolButton(",
    )
    button_count = 0
    for path in ETS_ROOT.rglob("*.ets"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "Button(" not in line or any(name in line for name in builder_invocations):
                continue
            button_count += line.count("Button(")
            window = "\n".join(lines[index:index + 40])
            if ".onClick" not in window:
                fail(f"{path}:{index + 1}: Button lacks an onClick action")
            if ".stateStyles" not in window:
                fail(f"{path}:{index + 1}: Button lacks pressed/focused/disabled feedback")
    if button_count == 0:
        fail("no Button declarations found")
    return button_count


def validate_no_empty_catches() -> None:
    for path in ETS_ROOT.rglob("*.ets"):
        source = strip_strings_comments(path.read_text(encoding="utf-8"))
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", source):
            fail(f"{path}: empty catch block")




def validate_single_runtime() -> None:
    forbidden = [
        "DemoBackend", "DemoCenterPage", "createDemo(", "demoMode", "SPRING DEMO",
        "embedded-demo", "免配置演示", "演示中心",
    ]
    for path in ETS_ROOT.rglob("*.ets"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in source:
                fail(f"{path}: removed demo runtime token remains: {token}")
    page_data = json.loads(PAGES_JSON.read_text(encoding="utf-8"))
    if "pages/DemoCenterPage" in page_data["src"]:
        fail("DemoCenterPage must not be registered")

def validate_build_safety() -> None:
    hvigor = (ROOT / "hvigor" / "hvigor-config.json5").read_text(encoding="utf-8")
    if re.search(r'"typeCheck"\s*:\s*false', hvigor):
        fail("Hvigor type checking must not be disabled")
    unit_test = (ROOT / "entry" / "src" / "test" / "LocalUnit.test.ets").read_text(encoding="utf-8")
    require(unit_test, r"SelectionStateUtil\.replace", "selection unit test exercises replacement")
    require(unit_test, r"SelectionStateUtil\.allAnswered", "selection unit test exercises submit unlock")


def validate_python_syntax() -> None:
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in (ROOT / "backend" / "tests").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def main() -> int:
    ets_files = sorted(ETS_ROOT.rglob("*.ets"))
    for path in ets_files:
        validate_balanced(path)
        validate_imports(path)
    validate_pages_and_routes()
    button_count = validate_button_contracts()
    validate_no_empty_catches()
    validate_quiz_contract()
    validate_resource_contract()
    validate_profile_contract()
    validate_single_runtime()
    validate_build_safety()
    validate_python_syntax()
    print(json.dumps({
        "status": "passed",
        "ets_files": len(ets_files),
        "registered_pages": len(json.loads(PAGES_JSON.read_text())["src"]),
        "button_contracts": button_count,
        "interaction_contracts": ["diagnostic", "resource_test", "practice", "profile"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

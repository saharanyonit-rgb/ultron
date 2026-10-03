"""Guarantees that must hold for tool discovery, metadata, routing and packaging.

These encode invariants that previously had no test coverage, which is how the
following shipped unnoticed:

- 53 tools were registered but unreachable, because routing was driven by a
  hand-maintained keyword table that only listed 20 of them.
- `DEFAULT_RISK_MAP` rated tools that do not exist (`delete_file`,
  `execute_shell`, `rename_file`, `windows_shutdown`) while real tools went
  unrated and fell through to a MEDIUM default.
- The router refused mouse/voice/shell requests as "unsupported" while those
  tools sat in the registry.
- `jarvis.spec` omitted `ultron.tools.catalog`, so a frozen build discovered no
  tools at all, because discovery is dynamic and invisible to PyInstaller.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from ultron.core.router import IntentRouter, RouteType, validate_out_of_scope
from ultron.risk import RiskLevel
from ultron.tools import ToolRegistry, default_tools
from ultron.tools.base import InvalidToolError, Tool
from ultron.tools.catalog import build_catalog, default_catalog

ROOT = Path(__file__).resolve().parents[1]


class _Fake(Tool):
    """Minimal concrete tool used to probe catalog validation."""

    description = "Probe tool."
    parameters = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {}}

    def __init__(self, name="probe", risk=RiskLevel.LOW, mutates=False, keywords=()):
        self.name = name
        self.risk = risk
        self.mutates = mutates
        self.keywords = tuple(keywords)

    def run(self, **kwargs):
        return {}


# ── discovery ────────────────────────────────────────────────────────
def test_every_tool_module_yields_a_tool():
    """Discovery must return a real catalog, not an empty or stub list."""
    discovered = {t.name for t in default_tools()}
    assert len(discovered) > 50, "discovery returned an implausibly small catalog"


def test_discovery_is_not_an_eager_module_list():
    """`ALL_TOOLS` must resolve via discovery, not a literal list."""
    source = open(ROOT / "ultron" / "tools" / "__init__.py", encoding="utf-8").read()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ALL_TOOLS":
                    pytest.fail(
                        "ultron/tools/__init__.py still defines an eager ALL_TOOLS list; "
                        "tools must come from ultron.tools.catalog.discover_tools()"
                    )


def test_all_tools_alias_matches_discovery():
    assert {t.name for t in default_tools()} == set(default_catalog().names)


# ── metadata is the source of truth ──────────────────────────────────
def test_every_tool_declares_risk():
    for tool in default_tools():
        assert tool.risk is not None, f"{tool.name} has no risk"


def test_no_tool_is_read_risk_but_mutating():
    for name, meta in default_catalog().metadata.items():
        assert not (meta.risk == RiskLevel.READ and meta.mutates), (
            f"{name} is risk=READ but mutates=True; a mutating tool must declare at "
            f"least LOW or it can pass a read-only gate"
        )


def test_catalog_rejects_undeclared_risk():
    with pytest.raises(InvalidToolError, match="does not declare a 'risk'"):
        build_catalog([_Fake(risk=None)])


def test_catalog_rejects_read_plus_mutates():
    with pytest.raises(InvalidToolError, match="risk=READ but mutates=True"):
        build_catalog([_Fake(risk=RiskLevel.READ, mutates=True)])


def test_categories_are_derived_not_leaky():
    """Category derivation must not leak module suffixes like `_unrestricted`."""
    for name, meta in default_catalog().metadata.items():
        assert meta.category, f"{name} has no category"
        assert not meta.category.endswith("_unrestricted"), (
            f"{name} category {meta.category!r} still carries the module suffix"
        )


def test_risk_classifier_reads_tool_metadata():
    from ultron.risk import RiskClassifier

    catalog = default_catalog()
    classifier = RiskClassifier(catalog=catalog)
    for name in catalog.names:
        assert classifier.classify(name) == catalog.risk_of(name)


def test_deleted_side_tables_are_gone():
    """The parallel tables this work removed must not creep back."""
    import ultron.core.router as router_mod
    import ultron.risk as risk_mod

    assert not hasattr(router_mod, "TOOL_KEYWORD_MAP")
    assert not hasattr(router_mod, "UNSUPPORTED_PATTERNS")
    assert not hasattr(risk_mod, "DEFAULT_RISK_MAP")


# ── routing ─────────────────────────────────────────────────────────
def test_every_tool_is_reachable_by_phrase():
    """No tool may be registered but unreachable, which was the 53-tool bug."""
    catalog = default_catalog()
    unreachable = []
    for name in catalog.metadata:
        probe = "please " + name.replace("_", " ") + " now"
        if catalog.best_phrase_match(probe) is None:
            unreachable.append(name)
    assert not unreachable, f"tools with no phrase match their own name: {unreachable}"


def test_phrase_match_respects_word_boundaries():
    """A derived single-word category must not fire inside a longer word."""
    catalog = default_catalog()
    # 'file' is a category; 'profile' must not route to a file tool.
    hit = catalog.best_phrase_match("check my github profile")
    assert hit is None or hit[0] != "file"


def test_router_does_not_refuse_registered_capabilities():
    """The router must never claim UNSUPPORTED for something it can do."""
    catalog = default_catalog()
    router = IntentRouter(catalog=catalog)
    for text, expected in (
        ("click the mouse button", "mouse_click"),
        ("speak hello out loud", "speak"),
        ("run a powershell script", "execute_powershell"),
    ):
        decision = router.route(text)
        assert decision.route_type != RouteType.UNSUPPORTED, (
            f"{text!r} was refused as unsupported but {expected!r} is registered"
        )


def test_out_of_scope_entries_have_no_tools():
    validate_out_of_scope(default_catalog())


def test_conversation_is_not_hijacked_by_tools():
    """Ordinary chat must not be diverted into a tool route."""
    router = IntentRouter()
    for text in (
        "What is the speed of light?",
        "Tell me a story about space",
        "Help me write an essay",
        "How are you today?",
    ):
        assert router.route(text).route_type == RouteType.CONVERSATIONAL, (
            f"{text!r} was routed to {router.route(text).route_type}"
        )


def test_router_never_targets_an_unregistered_tool():
    router = IntentRouter()
    for text in ("take a screenshot", "play some music", "what time is it"):
        decision = router.route(text)
        if decision.route_type == RouteType.TOOL:
            assert decision.target in default_catalog().names


def test_self_introduction_stays_conversational():
    """'call me' used to collide with a memory keyword."""
    router = IntentRouter()
    assert router.route("my name is Bob").route_type == RouteType.CONVERSATIONAL
    assert router.route("call me Bob").route_type == RouteType.CONVERSATIONAL


# ── scoping ──────────────────────────────────────────────────────────
def _agent():
    import tempfile
    from pathlib import Path as _P

    from ultron.actions import PermissionGate
    from ultron.actions.audit_log import AuditLog
    from ultron.core.agent import Agent

    log = _P(tempfile.gettempdir()) / "jarvis_scope_test.log"
    return Agent(
        provider=None,
        tools=ToolRegistry().all(),
        audit_log=AuditLog(log),
        gate=PermissionGate(),
    )


def test_relevance_scoping_narrows_specific_requests():
    agent = _agent()
    total = len(agent.registry.all())
    for text, expected in (
        ("take a screenshot", "take_screenshot"),
        ("run a powershell script", "execute_powershell"),
        ("play some music", "play_song"),
    ):
        names = [t.name for t in agent.relevant_tools(text)]
        assert expected in names, f"{text!r} lost {expected}"
        assert len(names) < total, f"{text!r} was not narrowed ({len(names)}/{total})"


def test_relevance_scoping_never_returns_empty():
    """Showing the model zero tools would break tool use entirely."""
    agent = _agent()
    for text in ("asdf qwerty zxcv", "", "tell me something about the weather"):
        assert agent.relevant_tools(text), f"{text!r} produced no tools"


def test_scoping_only_narrows_the_prompt_not_execution():
    """A filtered-out tool must still execute, so scoping can't cause a hard fail."""
    agent = _agent()
    scoped = agent.relevant_tools("take a screenshot")
    names = [t.name for t in scoped]
    assert "execute_powershell" not in names
    # The executor still resolves against the full registry.
    assert agent.registry.get("execute_powershell") is not None


# ── packaging ────────────────────────────────────────────────────────
def _spec_generator_output(spec_name: str) -> set[str]:
    """Execute the spec's own generator and return what it produces.

    Regexing the spec file would only see the literal strings and miss the
    `*TOOL_HIDDENIMPORTS` splat, so the generator is actually run instead.
    """
    source = open(ROOT / spec_name, encoding="utf-8").read()
    start = source.index("def discovered_tool_modules")
    end = source.index("TOOL_HIDDENIMPORTS = ")
    snippet = source[start:end]
    # `discovered_tool_modules` reads the module-level ROOT, which sits above
    # the extracted region, so provide it directly.
    namespace: dict[str, object] = {"os": os, "ROOT": str(ROOT)}
    exec(compile(snippet, spec_name, "exec"), namespace)  # noqa: S102
    return set(namespace["discovered_tool_modules"]())  # type: ignore[operator]


def _tool_modules_on_disk() -> set[str]:
    tools_dir = ROOT / "ultron" / "tools"
    modules = set()
    for entry in sorted(os.listdir(tools_dir)):
        if entry.endswith(".py") and entry != "__init__.py":
            modules.add("ultron.tools." + entry[:-3])
    return modules


def test_spec_generator_bundles_the_discovery_engine():
    """Without catalog the frozen build discovers zero tools.

    Discovery is dynamic (pkgutil + importlib), so PyInstaller's static
    analysis cannot see the tool modules at all.
    """
    produced = _spec_generator_output("jarvis.spec")
    assert "ultron.tools.catalog" in produced


def test_spec_generator_covers_every_tool_module():
    produced = _spec_generator_output("jarvis.spec")
    missing = sorted(_tool_modules_on_disk() - produced)
    assert not missing, (
        f"jarvis.spec generator omits {missing}; it is derived from "
        f"ultron/tools/*.py so this indicates a broken generator"
    )


def test_spec_does_not_hand_list_tool_modules():
    """The static tool block is gone; the list is derived."""
    source = open(ROOT / "jarvis.spec", encoding="utf-8").read()
    assert "discovered_tool_modules()" in source
    assert "*TOOL_HIDDENIMPORTS" in source
    assert '"ultron.tools.browser_tools"' not in source, (
        "jarvis.spec still hand-lists a tool module; the list must be generated"
    )


def test_onefile_spec_collects_the_whole_package():
    """The onefile spec relies on collect_submodules rather than a literal list."""
    source = open(ROOT / "jarvis_onefile.spec", encoding="utf-8").read()
    assert 'collect_submodules(package)' in source
    assert '"ultron"' in source


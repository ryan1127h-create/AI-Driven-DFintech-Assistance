"""Architecture rules, checked on the source:

  - the import contracts in app/.importlinter (layers, domain order,
    specialists reading no data, specialists independent of each other);
  - each schema adapter is imported only by the module that owns its
    schema, and the shared pool only by the schema adapters;
  - the SQL each owner issues names no other schema's tables.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]

# schema adapter module -> (its schema, the one module allowed to use it)
_OWNERS = {
    "app.adapters.account_db_adapter": ("account", "app.domains.auth.repository"),
    "app.adapters.profile_db_adapter": ("profile", "app.domains.profile.repository"),
    "app.adapters.sis_db_adapter": ("sis", "app.domains.sis.repository"),
    "app.adapters.chat_db_adapter": ("chat", "app.domains.conversation.repository"),
    "app.adapters.knowledge_db_adapter": ("knowledge", "app.domains.knowledge_retrieval.service"),
}
_SCHEMA_ADAPTERS = set(_OWNERS)
_SCHEMAS = ("account", "profile", "sis", "chat", "knowledge")
_SQL = re.compile(r"\b(select|insert\s+into|update|delete\s+from)\b", re.IGNORECASE)
_TABLE_REF = re.compile(r"\b(?:from|join|into|update)\s+(" + "|".join(_SCHEMAS) + r")\.", re.IGNORECASE)


def _modules():
    for path in APP.rglob("*.py"):
        if "tests" in path.relative_to(APP).parts:
            continue
        name = ".".join(("app",) + path.relative_to(APP).with_suffix("").parts)
        yield name.removesuffix(".__init__"), path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
    return found


def test_import_contracts_are_kept():
    cli = pytest.importorskip("importlinter.cli")
    assert cli.lint_imports(config_filename=str(APP / ".importlinter"), no_cache=True) == 0


def test_schema_adapters_are_used_only_by_their_owner():
    violations = []
    for name, path in _modules():
        for imported in _imports(path):
            if imported in _SCHEMA_ADAPTERS and name != _OWNERS[imported][1]:
                violations.append(f"{name} imports {imported}")
            if imported == "app.adapters.postgres_pool" and name not in _SCHEMA_ADAPTERS:
                violations.append(f"{name} imports the shared pool directly")
    assert violations == []


@pytest.mark.parametrize("adapter", sorted(_OWNERS))
def test_owner_sql_names_only_its_own_schema(adapter):
    schema, owner = _OWNERS[adapter]
    for module in (owner, adapter):
        path = APP.joinpath(*module.split(".")[1:]).with_suffix(".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        foreign = sorted({
            ref.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _SQL.search(node.value)
            for ref in _TABLE_REF.findall(node.value)
            if ref.lower() != schema
        })
        assert foreign == [], f"{module} queries other schemas: {foreign}"

"""Tree-sitter-backed helpers for JavaScript and TypeScript repositories."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from tree_sitter import Language, Parser
    import tree_sitter_javascript
    import tree_sitter_typescript
except ImportError:  # pragma: no cover - exercised through fallback behavior
    Language = None  # type: ignore[assignment]
    Parser = None  # type: ignore[assignment]
    tree_sitter_javascript = None  # type: ignore[assignment]
    tree_sitter_typescript = None  # type: ignore[assignment]

JS_TS_SUFFIXES = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"})
_GENERIC_FRONTEND_NAMES = frozenset(
    {
        "api",
        "app",
        "component",
        "components",
        "e2e",
        "error",
        "index",
        "layout",
        "loading",
        "page",
        "pages",
        "route",
        "routes",
        "screen",
        "screens",
        "spec",
        "src",
        "test",
        "tests",
        "__tests__",
        "ui",
        "view",
        "views",
        "web",
    }
)
_COMPONENT_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(slots=True)
class JSTreeSitterAnalysis:
    imports: set[str] = field(default_factory=set)
    defined_symbols: set[str] = field(default_factory=set)
    referenced_symbols: set[str] = field(default_factory=set)


def tree_sitter_js_ts_available() -> bool:
    return (
        Language is not None
        and Parser is not None
        and tree_sitter_javascript is not None
        and tree_sitter_typescript is not None
    )


def is_js_ts_path(relative_path: str) -> bool:
    return Path(relative_path).suffix.lower() in JS_TS_SUFFIXES


def is_frontend_code_path(relative_path: str) -> bool:
    path = Path(relative_path)
    suffix = path.suffix.lower()
    if suffix not in JS_TS_SUFFIXES:
        return False
    lowered = relative_path.lower()
    return (
        suffix in {".jsx", ".tsx"}
        or any(part in {"app", "apps", "components", "pages", "routes", "web"} for part in path.parts)
        or any(token in lowered for token in ("/components/", "/pages/", "/routes/", "/app/", "/ui/"))
    )


def frontend_anchor_tokens(relative_path: str) -> set[str]:
    path = Path(relative_path)
    candidate_parts = list(path.parts[-4:])
    if path.stem.lower() in _GENERIC_FRONTEND_NAMES and path.parent.name:
        candidate_parts.append(path.parent.name)
    else:
        candidate_parts.append(path.stem)

    tokens: set[str] = set()
    for part in candidate_parts:
        part_text = Path(part).stem if "." in part else str(part)
        lowered = part_text.lower()
        if lowered in _GENERIC_FRONTEND_NAMES:
            continue
        for piece in _split_identifier_tokens(part_text):
            if len(piece) >= 3 and piece not in _GENERIC_FRONTEND_NAMES:
                tokens.add(piece)
        compact = _normalize_identifier(part_text)
        if len(compact) >= 3 and compact not in _GENERIC_FRONTEND_NAMES:
            tokens.add(compact)
    return tokens


def analyze_js_ts_file(file_path: Path) -> JSTreeSitterAnalysis | None:
    if not tree_sitter_js_ts_available() or file_path.suffix.lower() not in JS_TS_SUFFIXES:
        return None
    try:
        source_bytes = file_path.read_bytes()
    except OSError:
        return None
    parser = _parser_for_suffix(file_path.suffix.lower())
    if parser is None:
        return None
    tree = parser.parse(source_bytes)
    analysis = JSTreeSitterAnalysis()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.children))

        if node.type in {"import_statement", "export_statement"}:
            analysis.imports.update(_string_literals(node, source_bytes))
            if node.type == "export_statement":
                analysis.defined_symbols.update(_exported_identifiers(node, source_bytes))
            continue

        if node.type == "call_expression":
            callee = _call_expression_name(node, source_bytes)
            if callee in {"import", "require", "require.resolve", "React.lazy", "lazy"}:
                analysis.imports.update(_string_literals(node, source_bytes))
            continue

        if node.type in {
            "class_declaration",
            "enum_declaration",
            "function_declaration",
            "interface_declaration",
            "type_alias_declaration",
        }:
            identifier = _first_identifier(node, source_bytes)
            if identifier:
                analysis.defined_symbols.add(identifier)
            continue

        if node.type == "variable_declarator":
            identifier = _first_identifier(node, source_bytes)
            if identifier:
                analysis.defined_symbols.add(identifier)
            continue

        if node.type in {"jsx_opening_element", "jsx_self_closing_element"}:
            identifier = _first_identifier(node, source_bytes)
            if identifier and _COMPONENT_NAME_RE.match(identifier):
                analysis.referenced_symbols.add(identifier)

    return analysis


@lru_cache(maxsize=8)
def _parser_for_suffix(suffix: str) -> Parser | None:
    if not tree_sitter_js_ts_available():
        return None
    language_fn = None
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        language_fn = tree_sitter_javascript.language
    elif suffix in {".ts", ".mts", ".cts"}:
        language_fn = tree_sitter_typescript.language_typescript
    elif suffix == ".tsx":
        language_fn = tree_sitter_typescript.language_tsx
    if language_fn is None:
        return None
    parser = Parser(Language(language_fn()))
    return parser


def _string_literals(node, source_bytes: bytes) -> set[str]:
    values: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        stack.extend(reversed(current.children))
        if current.type != "string":
            continue
        text = _node_text(current, source_bytes)
        if len(text) >= 2 and text[0] in {"'", '"', "`"} and text[-1] == text[0]:
            text = text[1:-1]
        text = text.strip()
        if text and "${" not in text:
            values.add(text)
    return values


def _exported_identifiers(node, source_bytes: bytes) -> set[str]:
    values: set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        stack.extend(reversed(current.children))
        if current.type not in {"identifier", "type_identifier"}:
            continue
        text = _node_text(current, source_bytes)
        if text and text != "default":
            values.add(text)
    return values


def _first_identifier(node, source_bytes: bytes) -> str:
    for child in node.children:
        if child.type in {"identifier", "type_identifier"}:
            return _node_text(child, source_bytes)
    return ""


def _call_expression_name(node, source_bytes: bytes) -> str:
    for child in node.children:
        if child.type in {"identifier", "member_expression"}:
            return _node_text(child, source_bytes)
    return ""


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _normalize_identifier(value: str) -> str:
    return "".join(_split_identifier_tokens(value))


def _split_identifier_tokens(value: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return [token.lower() for token in _WORD_RE.findall(expanded)]

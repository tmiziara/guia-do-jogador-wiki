from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\Tiagin\Desktop\RPG\Thyrmhald-Vault\Guia do Jogador")
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(#[^\]|]+)?(?:\|([^\]]+))?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n+", re.DOTALL)

MKDOCS_HEADER = """site_name: Thyrmhald - Guia do Jogador
site_description: Wiki pública do Guia do Jogador de Thyrmhald.
site_url: https://tmiziara.github.io/guia-do-jogador-wiki/
repo_url: https://github.com/tmiziara/guia-do-jogador-wiki
repo_name: tmiziara/guia-do-jogador-wiki

theme:
  name: material
  language: pt-BR
  features:
    - navigation.sections
    - navigation.expand
    - navigation.indexes
    - toc.follow
    - search.suggest
    - search.highlight
    - content.code.copy

markdown_extensions:
  - admonition
  - attr_list
  - md_in_html
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true

extra:
  generator: false

nav:
"""


def sort_key(path: Path) -> tuple[str, ...]:
    return tuple(part.lower() for part in path.parts)


def scan_notes() -> list[Path]:
    return sorted(SOURCE.rglob("*.md"), key=lambda p: sort_key(p.relative_to(SOURCE)))


def destination_for(relative_source: Path) -> Path:
    if relative_source.name == "00 - Guia do Jogador.md":
        return Path("index.md")
    if relative_source.name.startswith("00 - "):
        return relative_source.parent / "index.md"
    return relative_source


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def canonical_lookup(source_files: list[Path]) -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for source in source_files:
        rel = source.relative_to(SOURCE)
        no_suffix = rel.with_suffix("")
        full_key = no_suffix.as_posix()
        lookup[full_key] = rel
        lookup.setdefault(no_suffix.name, rel)
    return lookup


def candidate_variants(source_rel: Path, cleaned: str) -> list[Path]:
    variants: list[Path] = []
    seen: set[str] = set()

    def add(rel_path: Path) -> None:
        key = rel_path.as_posix()
        if key not in seen:
            seen.add(key)
            variants.append(rel_path)

    add((source_rel.parent / cleaned).with_suffix(".md"))
    add(Path(f"{cleaned}.md"))

    stripped = cleaned
    while stripped.startswith("../"):
        stripped = stripped[3:]
        if stripped:
            add(Path(f"{stripped}.md"))

    return variants


def resolve_target(source_rel: Path, target: str, lookup: dict[str, Path]) -> Path | None:
    cleaned = target.replace("\\", "/").strip().lstrip("./")

    for rel_candidate in candidate_variants(source_rel, cleaned):
        candidate = SOURCE / rel_candidate
        if candidate.exists() and candidate.is_relative_to(SOURCE):
            return rel_candidate

    return lookup.get(cleaned) or lookup.get(Path(cleaned).name)


def markdown_link(from_dest: Path, to_dest: Path, label: str) -> str:
    relative = Path(os.path.relpath(to_dest, from_dest.parent)).as_posix()
    if relative == "":
        relative = "index.md"
    return f"[{label}]({relative})"


def convert_links(
    text: str,
    source_rel: Path,
    source_map: dict[Path, Path],
    lookup: dict[str, Path],
) -> tuple[str, list[str]]:
    broken: list[str] = []

    def replacer(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        label = (match.group(3) or Path(raw_target).name).strip()
        resolved_source = resolve_target(source_rel, raw_target, lookup)
        if resolved_source is None or resolved_source not in source_map:
            broken.append(raw_target)
            return label

        from_dest = source_map[source_rel]
        to_dest = source_map[resolved_source]
        return markdown_link(from_dest, to_dest, label)

    return WIKILINK_RE.sub(replacer, text), broken


def clean_label(value: str) -> str:
    label = value.removesuffix(".md")
    if " - " in label:
        prefix, rest = label.split(" - ", 1)
        if prefix.isdigit():
            return rest
    return label


def build_nav_tree(paths: list[Path]) -> list[dict[str, object]]:
    tree: dict[str, object] = {}

    for path in sorted(paths, key=sort_key):
        if path == Path("index.md"):
            continue

        current = tree
        parts = list(path.parts)
        for index, part in enumerate(parts):
            is_last = index == len(parts) - 1
            if is_last:
                if part == "index.md":
                    current["__index__"] = path.as_posix()
                else:
                    current.setdefault("__pages__", [])
                    current["__pages__"].append((clean_label(part), path.as_posix()))  # type: ignore[index]
                continue

            folder = part
            current.setdefault(folder, {})
            current = current[folder]  # type: ignore[assignment,index]

    def render(node: dict[str, object]) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []

        for key in sorted(k for k in node.keys() if not k.startswith("__")):
            child = node[key]  # type: ignore[index]
            label = clean_label(key)
            child_index = child.get("__index__") if isinstance(child, dict) else None

            if child_index:
                items.append({label: child_index})

            child_items = render(child) if isinstance(child, dict) else []
            if child_items:
                items.append({label: child_items})

        for label, target in node.get("__pages__", []):  # type: ignore[assignment]
            items.append({label: target})

        return items

    return render(tree)


def yaml_lines(nav: list[dict[str, object]], indent: int = 2) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for item in nav:
        for label, value in item.items():
            if isinstance(value, list):
                lines.append(f"{prefix}- {label}:")
                lines.extend(yaml_lines(value, indent + 2))
            else:
                lines.append(f"{prefix}- {label}: {value}")
    return lines


def write_mkdocs_nav(doc_paths: list[Path]) -> None:
    nav_items = build_nav_tree(doc_paths)
    nav_lines = ["  - Início: index.md"] + yaml_lines(nav_items)
    MKDOCS.write_text(MKDOCS_HEADER + "\n".join(nav_lines) + "\n", encoding="utf-8")


def main() -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True, exist_ok=True)

    source_files = scan_notes()
    lookup = canonical_lookup(source_files)
    source_map = {
        source.relative_to(SOURCE): destination_for(source.relative_to(SOURCE))
        for source in source_files
    }
    written_docs: list[Path] = []
    unresolved: dict[str, list[str]] = {}

    for source in source_files:
        source_rel = source.relative_to(SOURCE)
        dest_rel = source_map[source_rel]
        dest_path = DOCS / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        raw = source.read_text(encoding="utf-8")
        text = strip_frontmatter(raw)
        converted, broken = convert_links(text, source_rel, source_map, lookup)
        dest_path.write_text(converted, encoding="utf-8")
        written_docs.append(dest_rel)

        if broken:
            unresolved[source_rel.as_posix()] = sorted(set(broken))

    write_mkdocs_nav(written_docs)

    print(f"Imported {len(written_docs)} notes into {DOCS}")
    if unresolved:
        print("\nUnresolved wikilinks:")
        for source, links in unresolved.items():
            print(f"- {source}")
            for link in links:
                print(f"  - {link}")


if __name__ == "__main__":
    main()

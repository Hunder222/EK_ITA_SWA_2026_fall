#!/usr/bin/env python3
r"""
update_sidebar.py

Automatically generates or updates _sidebar.md based on the root session
folders present in the repository.
- Scans for directories matching '^[xX]?\d+' that contain a 'README.md'.
- Preserves existing custom titles for folders that are still present.
- Generates clean, formatted titles for new or renamed folders.
- Groups regular sessions under 'IT-Infrastructure' (sessions 1-5) and 'Software Architecture' (sessions 6+).
- Groups 'x'-prefixed sessions separately at the bottom under 'Skipped sessions'.
- Prunes deleted folders.
"""

import os
import re
import sys
from pathlib import Path

# Ensure UTF-8 output even in Windows cmd/powershell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ACRONYMS = {
    "api": "API",
    "rest": "REST",
    "http": "HTTP",
    "git": "Git",
    "adrs": "ADRs",
    "c4": "C4",
    "openapi": "OpenAPI",
    "docker": "Docker",
    "compose": "Compose",
    "linux": "Linux",
    "bash": "Bash",
    "intro": "Intro",
    "hands": "Hands",
    "on": "On",
    "vs": "vs",
    "and": "&",
}


def get_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    candidate = script_path.parent.parent.parent
    if (candidate / "_sidebar.md").exists() or (candidate / ".git").exists():
        return candidate
    return Path.cwd()


def parse_existing_sidebar(sidebar_path: Path):
    """
    Parses existing _sidebar.md to extract previously configured titles
    mapped by folder name.
    """
    titles = {}
    if not sidebar_path.exists():
        return titles

    with open(sidebar_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*\*\s*\[(.*?)\]\((.*?)/README\.md\)", line)
            if m:
                title, folder = m.group(1), m.group(2)
                titles[folder] = title
    return titles


def format_title_from_folder(folder_name: str) -> str:
    """
    Generates a clean human-readable title from folder name.
    Example:
      '09._Layered_architecture_hands_on' -> '09. Layered Architecture Hands On'
      '12._openapi'                       -> '12. OpenAPI'
      'x11._hexagonal_architecture'        -> 'x11. Hexagonal Architecture'
    """
    m = re.match(r"^([xX]?\d+(?:[-–]\d+)?)(?:[._]+([a-zA-Z]))?[._]+(.*)$", folder_name)
    if m:
        num, sub, slug = m.group(1), m.group(2), m.group(3)
        prefix = num
        if sub and len(sub) == 1 and sub.isalpha() and not slug.startswith(sub):
            prefix += sub
        prefix = prefix.replace("-", "–") + "."
    else:
        prefix = ""
        slug = folder_name

    words = slug.split("_")
    formatted = []
    for w in words:
        if not w:
            continue
        w_lower = w.lower()
        if w_lower in ACRONYMS:
            formatted.append(ACRONYMS[w_lower])
        else:
            formatted.append(w.capitalize())

    title_text = " ".join(formatted)
    # Common contextual replacements
    title_text = title_text.replace("3rd Semester", "(3rd Semester)")
    title_text = title_text.replace("Linux Git", "Linux & Git")
    title_text = title_text.replace("Terminal Linux", "Terminal, Linux")
    title_text = title_text.replace("Project Distributed", "Project: Distributed")
    title_text = title_text.replace("Documentation ADRs", "Documentation, ADRs")

    if prefix:
        return f"{prefix} {title_text}"
    return title_text


def get_sort_key(folder_name: str):
    """
    Sort key for ordering sessions numerically.
    """
    m = re.match(r"^[xX]?(\d+)(?:[-–](\d+))?(?:[._]+([a-zA-Z]))?", folder_name)
    if m:
        start_num = int(m.group(1))
        end_num = int(m.group(2)) if m.group(2) else start_num
        sub = m.group(3).lower() if m.group(3) else ""
        return (start_num, sub, end_num, folder_name)
    return (999, "", 999, folder_name)


def generate_sidebar_content(repo_root: Path) -> tuple[str, list[str], list[str]]:
    sidebar_path = repo_root / "_sidebar.md"
    existing_titles = parse_existing_sidebar(sidebar_path)

    # Discover valid session folders
    regular_sessions = []
    skipped_sessions = []

    for entry in repo_root.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            if (entry / "README.md").exists():
                if re.match(r"^[xX]\d+", entry.name):
                    skipped_sessions.append(entry.name)
                elif re.match(r"^\d+", entry.name):
                    regular_sessions.append(entry.name)

    regular_sessions.sort(key=get_sort_key)
    skipped_sessions.sort(key=get_sort_key)

    all_sessions = regular_sessions + skipped_sessions

    it_infra = []
    soft_arch = []
    skipped_list = []

    used_folders = set(all_sessions)

    for folder in regular_sessions:
        title = existing_titles.get(folder, format_title_from_folder(folder))
        m = re.match(r"^(\d+)", folder)
        num = int(m.group(1)) if m else 99
        entry_line = f"  * [{title}]({folder}/README.md)"

        if 1 <= num <= 5:
            it_infra.append(entry_line)
        else:
            soft_arch.append(entry_line)

    for folder in skipped_sessions:
        title = existing_titles.get(folder, format_title_from_folder(folder))
        entry_line = f"  * [{title}]({folder}/README.md)"
        skipped_list.append(entry_line)

    removed_folders = [f for f in existing_titles if f not in used_folders]
    added_folders = [f for f in all_sessions if f not in existing_titles]

    lines = [
        "* [Overview](README.md)",
        "* [Curriculum](curriculum.md)",
        "",
        "* **IT-Infrastructure**",
    ]
    lines.extend(it_infra)
    lines.append("* **Software Architecture**")
    lines.extend(soft_arch)

    if skipped_list:
        lines.append("* **Skipped sessions**")
        lines.extend(skipped_list)

    lines.append("")

    content = "\n".join(lines)
    return content, added_folders, removed_folders


def main():
    repo_root = get_repo_root()
    sidebar_path = repo_root / "_sidebar.md"

    new_content, added, removed = generate_sidebar_content(repo_root)

    current_content = sidebar_path.read_text(encoding="utf-8") if sidebar_path.exists() else ""

    if current_content == new_content:
        print("[INFO] _sidebar.md is already up to date. No changes needed.")
        return 0

    print("[INFO] Updating _sidebar.md...")
    if added:
        print(f"  [+] Added sessions ({len(added)}): {', '.join(added)}")
    if removed:
        print(f"  [-] Removed obsolete sessions ({len(removed)}): {', '.join(removed)}")

    sidebar_path.write_text(new_content, encoding="utf-8")
    print("[SUCCESS] Successfully updated _sidebar.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


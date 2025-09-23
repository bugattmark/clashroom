
# python ff_all.py --root . --out ff_all.txt


# ff_all.py
import argparse
import os
import sys
from pathlib import Path
from typing import List, Set
import pyperclip

DEFAULT_EXCLUDES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".idea", ".vscode", ".next", ".cache", ".tox", ".mypy_cache", ".pytest_cache"
}

def scandir_sorted(path: Path) -> List[os.DirEntry]:
    with os.scandir(path) as it:
        entries = [e for e in it]
    entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
    return entries

def build_tree(root: Path, excludes: Set[str], include_all: bool) -> str:
    lines: List[str] = [str(root.resolve())]

    def walk(dir_path: Path, prefix: str = ""):
        try:
            entries = [e for e in scandir_sorted(dir_path)
                       if (include_all or e.name not in excludes)]
        except (PermissionError, OSError):
            lines.append(f"{prefix}… [skipped: permission]")
            return

        total = len(entries)
        for idx, entry in enumerate(entries):
            is_last = idx == total - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir(follow_symlinks=False):
                extension = "    " if is_last else "│   "
                walk(dir_path / entry.name, prefix + extension)

    walk(root)
    return "\n".join(lines)

def collect_all_files(root: Path, excludes: Set[str], include_all: bool) -> List[Path]:
    root_resolved = root.resolve()
    results: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        if not include_all:
            dirnames[:] = [d for d in dirnames if d not in excludes]

        for fname in filenames:
            p = Path(dirpath) / fname
            try:
                p_resolved = p.resolve()
            except (PermissionError, OSError):
                continue

            try:
                if hasattr(p_resolved, "is_relative_to"):
                    inside = p_resolved.is_relative_to(root_resolved)
                else:
                    inside = str(p_resolved).startswith(str(root_resolved) + os.sep) or p_resolved == root_resolved
            except Exception:
                inside = False

            if not inside:
                continue

            if p.is_file():
                results.append(p)

    results.sort(key=lambda x: str(x).lower())
    return results

def read_text_file(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[error reading file: {e}]"

def main():
    parser = argparse.ArgumentParser(
        description="Print project tree and contents of every file under the given root (root-only)."
    )
    parser.add_argument("--root", default=".", help="Root directory to search from (default: .)")
    parser.add_argument("--all", action="store_true", help="Include typical heavy/hidden directories (no excludes).")
    parser.add_argument("--out", help="Write output to a file with UTF-8 encoding instead of stdout.")
    args = parser.parse_args()

    # Try to make stdout UTF-8 with replacement for characters that can't be encoded.
    # Works in Python 3.7+. If it fails, we continue (we'll still write to --out file if provided).
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root = Path(args.root).resolve()
    include_all = args.all

    output_lines = []
    output_lines.append("Entire project structure:")
    output_lines.append(build_tree(root, DEFAULT_EXCLUDES, include_all=include_all))
    output_lines.append("")

    files = collect_all_files(root, DEFAULT_EXCLUDES, include_all=include_all)

    if not files:
        output_lines.append("--no files found--")
    else:
        for p in files:
            try:
                rel = p.relative_to(root)
            except Exception:
                rel = p
            output_lines.append(f"START OF {p.name} ({rel})")
            output_lines.append(read_text_file(p))
            output_lines.append(f"END OF {p.name} ({rel})")
            output_lines.append("")

    final_output = "\n".join(output_lines)

    if args.out:
        # write to a UTF-8 encoded file (safe)
        try:
            with open(args.out, "w", encoding="utf-8", errors="replace") as f:
                f.write(final_output)
            print(f"Written to {args.out}")
        except Exception as e:
            print(f"Failed to write to {args.out}: {e}")
    else:
        # Print to stdout (now reconfigured to utf-8 where possible)
        try:
            print(final_output)
        except Exception as e:
            # As a fallback, write bytes to stdout.buffer forcing utf-8
            try:
                sys.stdout.buffer.write(final_output.encode("utf-8", errors="replace"))
            except Exception:
                # Last resort: write a small error then exit
                sys.stderr.write(f"Failed to print output: {e}\n")
                return

    # Clipboard: only attempt if output is not huge
    try:
        MAX_CLIP = 2_000_000  # 2 MB
        if len(final_output) <= MAX_CLIP:
            pyperclip.copy(final_output)
            print("[Copied to clipboard]")
        else:
            print(f"[Output too large for clipboard ({len(final_output)} bytes); skipping clipboard copy]")
    except Exception as e:
        print(f"[Clipboard copy failed: {e}]")

if __name__ == "__main__":
    main()

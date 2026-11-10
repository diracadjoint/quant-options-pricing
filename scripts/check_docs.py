"""Check local Markdown link targets from the repository root (no network)."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    documents = [root / "README.md", root / "PROJECT_SPEC.md", *sorted((root / "docs").rglob("*.md"))]
    failures = []
    count = 0
    for document in documents:
        if not document.exists():
            failures.append(str(document.relative_to(root)))
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", document.read_text()):
            url = urlsplit(target.strip("<>"))
            if url.scheme or not url.path:
                continue
            count += 1
            if not (document.parent / unquote(url.path)).exists():
                failures.append(f"{document.relative_to(root)} -> {target}")
    if failures:
        raise SystemExit("Broken documentation targets:\n" + "\n".join(failures))
    print(f"Checked {count} relative links in {len(documents)} Markdown documents")


if __name__ == "__main__":
    main()

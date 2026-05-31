from __future__ import annotations

import re
from pathlib import Path


def derive_slug(project_root: Path) -> str:
    """Derive a stable, filesystem-safe repo slug from the project directory name.

    Rules:
      - lowercase
      - spaces and underscores become hyphens
      - strip anything that is not a letter, digit, dot, or hyphen
    """
    name = project_root.name
    slug = name.lower()
    slug = slug.replace("_", "-").replace(" ", "-")
    slug = re.sub(r"[^a-z0-9.-]", "", slug)
    slug = re.sub(r"-+", "-", slug)  # collapse multiple hyphens
    slug = slug.strip("-.")
    if not slug:
        slug = "project"
    return slug

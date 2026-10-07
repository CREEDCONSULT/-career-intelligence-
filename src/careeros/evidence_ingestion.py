"""Evidence ingestion adapters (M3.4): GitHub + Google Drive → EvidenceStore.

Both adapters import external metadata as UNVERIFIED evidence. The founder
must explicitly promote items through the verification workflow before
they can appear in application materials.

Provenance formats:
- GitHub:    github:<owner>/<repo>@<commit_or_branch>
- Drive:     drive:<file_id>

Hard constraints:
- Never auto-promote to VERIFIED
- Never fabricate achievements or responsibilities
- Never mutate the source (read-only)
- GitHub: repo existence does NOT imply expertise — the founder must confirm
"""

from __future__ import annotations

import json
import subprocess
from typing import Optional

from careeros.evidence import Evidence, EvidenceStore
from careeros.google_drive import DriveConnector, DiscoveredFile


# ---------------------------------------------------------------------------
# GitHub adapter
# ---------------------------------------------------------------------------


def fetch_github_repo(owner: str, repo: str) -> Optional[dict]:
    """Fetch repository metadata via the `gh` CLI. Returns None on failure."""
    try:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "view",
                f"{owner}/{repo}",
                "--json",
                "name,description,primaryLanguage,languages,repositoryTopics,createdAt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def github_repo_to_evidence(owner: str, repo: str, data: dict) -> Evidence:
    """Convert GitHub repository metadata to an UNVERIFIED Evidence item.

    Records the repo name, description, and languages as skills — but NEVER
    infers achievements, responsibility, or expertise from repo existence.
    The founder must review and promote before use.
    """
    languages = [
        lang.get("name", "")
        for lang in (data.get("languages") or {}).get("edges", [])
        if lang.get("name")
    ]
    if not languages and data.get("primaryLanguage"):
        languages = [data["primaryLanguage"].get("name", "")]

    topics = [
        t.get("name", "")
        for t in (data.get("repositoryTopics") or {}).get("nodes", [])
        if t.get("name")
    ]

    # Skills from languages (deterministic, safe — they're what the repo uses)
    skills = [lang for lang in languages if lang]
    skills.extend(topics)

    description_parts = []
    if data.get("description"):
        description_parts.append(data["description"])
    if languages:
        description_parts.append(f"Languages: {', '.join(languages)}")
    if topics:
        description_parts.append(f"Topics: {', '.join(topics)}")
    description = " | ".join(description_parts) if description_parts else None

    return Evidence(
        evidence_id=0,
        type="github_repository",
        title=f"GitHub: {data.get('name', repo)}",
        organization=owner,
        description=description,
        skills=skills,
        verification_state="UNVERIFIED",
        provenance=f"github:{owner}/{repo}",
    )


def ingest_github_evidence(store: EvidenceStore, owner: str, repo: str) -> Optional[Evidence]:
    """Fetch a GitHub repo and add it as UNVERIFIED evidence."""
    data = fetch_github_repo(owner, repo)
    if not data:
        return None
    ev = github_repo_to_evidence(owner, repo, data)
    return store.add(ev)


# ---------------------------------------------------------------------------
# Drive adapter
# ---------------------------------------------------------------------------


def drive_file_to_evidence(file: DiscoveredFile) -> Evidence:
    """Convert a Drive career artifact to an UNVERIFIED Evidence item.

    The artifact_type from the Drive connector (resume, cover_letter,
    certificate, portfolio, employment_evidence) maps to a specific
    Evidence type. Only metadata is imported — no file content.
    """
    type_map = {
        "resume": "employment",
        "cover_letter": "portfolio",
        "certificate": "certification",
        "portfolio": "portfolio",
        "employment_evidence": "employment",
    }
    ev_type = type_map.get(file.artifact_type or "", "portfolio")

    return Evidence(
        evidence_id=0,
        type=ev_type,
        title=f"Drive: {file.name}",
        description=f"Discovered in Google Drive (type: {file.artifact_type}, "
        f"mime: {file.mime_type}, modified: {file.modified_time}). "
        "Metadata only — content not read.",
        verification_state="UNVERIFIED",
        provenance=f"drive:{file.file_id}",
    )


def ingest_drive_evidence(store: EvidenceStore, drive_connector: DriveConnector) -> list[Evidence]:
    """Discover career-relevant Drive files and add them as UNVERIFIED evidence."""
    artifacts = drive_connector.discover_career_artifacts()
    added = []
    for artifact in artifacts:
        if not artifact.relevant:
            continue
        ev = drive_file_to_evidence(artifact)
        # Deduplicate by provenance
        existing = [e for e in store.list_all() if e.provenance == ev.provenance]
        if existing:
            continue
        added.append(store.add(ev))
    return added


# ---------------------------------------------------------------------------
# Manual structured import (helper for founder-seeded evidence)
# ---------------------------------------------------------------------------


def ingest_structured(
    store: EvidenceStore, items: list[dict], default_state: str = "UNVERIFIED"
) -> list[Evidence]:
    """Import structured evidence dicts. All items default to UNVERIFIED
    unless the founder explicitly sets verification_state in the item."""
    added = []
    for item in items:
        item.setdefault("verification_state", default_state)
        item.setdefault("provenance", "founder:structured-import")
        d = dict(item)
        for k in ("metrics", "skills", "artifacts", "target_role_families"):
            if k in d and isinstance(d[k], str):
                d[k] = json.loads(d[k])
        ev = Evidence(evidence_id=0, **d)
        added.append(store.add(ev))
    return added

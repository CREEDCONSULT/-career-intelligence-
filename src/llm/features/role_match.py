"""Phase 4: semantic profile -> role matching.

Embedded Qdrant (no server) + fastembed (ONNX, no torch): dense (bge-small) +
sparse BM25 hybrid fused with RRF — the Qdrant-documented pattern. The corpus is
one document per NOC occupation (title + top LLM-extracted skills + example
posting titles), fused downstream with structured demand and wage signals:

    score = SEMANTIC_WEIGHT * semantic_rrf_norm + (1 - SEMANTIC_WEIGHT) * demand_norm

Runs fully locally — no API key required for matching.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import lru_cache

import duckdb

SEMANTIC_WEIGHT = float(os.getenv("ROLE_MATCH_SEMANTIC_WEIGHT", "0.7"))
_DENSE_MODEL = "BAAI/bge-small-en-v1.5"
_SPARSE_MODEL = "Qdrant/bm25"


@dataclass
class RoleDoc:
    noc_code: str
    title: str
    text: str
    demand: int
    median_wage: float | None
    top_skills: list = field(default_factory=list)


@lru_cache(maxsize=1)
def _models():
    from fastembed import SparseTextEmbedding, TextEmbedding
    return TextEmbedding(_DENSE_MODEL), SparseTextEmbedding(_SPARSE_MODEL)


def build_role_docs(con: duckdb.DuckDBPyConnection, min_postings: int = 20) -> list[RoleDoc]:
    """One document per NOC occupation with enough postings to matter."""
    from pipeline.market import load_market
    region = load_market().economic_region_name
    rows = con.execute(f"""
        WITH demand AS (
            SELECT noc_code, count(*) AS n FROM job_postings
            WHERE noc_code IS NOT NULL AND noc_code != '' GROUP BY 1 HAVING count(*) >= {min_postings}
        ),
        skills AS (
            SELECT noc_code, list(skill_name ORDER BY cnt DESC)[:10] AS top_skills FROM (
                SELECT noc_code, skill_name, count(DISTINCT job_id) AS cnt
                FROM job_skills_llm GROUP BY 1, 2
            ) GROUP BY noc_code
        ),
        titles AS (
            SELECT noc_code, list(title ORDER BY cnt DESC)[:3] AS examples FROM (
                SELECT noc_code, title, count(*) AS cnt FROM job_postings GROUP BY 1, 2
            ) GROUP BY noc_code
        ),
        wage AS (
            SELECT noc_code, round(median(median_wage), 2) AS w FROM wages_job_bank
            WHERE region = '{region}' AND year = (SELECT max(year) FROM wages_job_bank)
            GROUP BY 1
        )
        SELECT d.noc_code, m.title, d.n, s.top_skills, t.examples, wage.w
        FROM demand d
        JOIN noc_mapping m ON d.noc_code = m.noc_code
        LEFT JOIN skills s ON d.noc_code = s.noc_code
        LEFT JOIN titles t ON d.noc_code = t.noc_code
        LEFT JOIN wage ON d.noc_code = wage.noc_code
        ORDER BY d.n DESC
    """).fetchall()

    docs = []
    for noc, title, n, top_skills, examples, wage in rows:
        top_skills = list(top_skills or [])
        examples = list(examples or [])
        text = f"{title}. Skills: {', '.join(top_skills)}. Example titles: {', '.join(examples)}"
        docs.append(RoleDoc(noc, title, text, demand=int(n), median_wage=wage, top_skills=top_skills))
    return docs


class RoleIndex:
    """Embedded-Qdrant hybrid index over RoleDocs (in-memory, rebuilt from the DB)."""

    def __init__(self):
        from qdrant_client import QdrantClient
        self.client = QdrantClient(":memory:")
        self.docs: list[RoleDoc] = []

    def build(self, docs: list[RoleDoc]) -> None:
        from qdrant_client import models
        dense_m, sparse_m = _models()
        texts = [d.text for d in docs]
        dense = list(dense_m.embed(texts))
        sparse = list(sparse_m.embed(texts))
        self.client.create_collection(
            "roles",
            vectors_config={"dense": models.VectorParams(size=len(dense[0]), distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        self.client.upsert("roles", points=[
            models.PointStruct(
                id=i,
                vector={
                    "dense": dense[i].tolist(),
                    "bm25": models.SparseVector(
                        indices=sparse[i].indices.tolist(), values=sparse[i].values.tolist()
                    ),
                },
                payload={"i": i},
            )
            for i in range(len(docs))
        ])
        self.docs = docs

    def query(self, text: str, limit: int = 10) -> list[tuple[RoleDoc, float]]:
        from qdrant_client import models
        dense_m, sparse_m = _models()
        qd = list(dense_m.embed([text]))[0]
        qs = list(sparse_m.embed([text]))[0]
        res = self.client.query_points(
            "roles",
            prefetch=[
                models.Prefetch(query=qd.tolist(), using="dense", limit=limit * 2),
                models.Prefetch(
                    query=models.SparseVector(indices=qs.indices.tolist(), values=qs.values.tolist()),
                    using="bm25", limit=limit * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        )
        return [(self.docs[p.payload["i"]], float(p.score)) for p in res.points]


def match_profile(profile_text: str, index: RoleIndex, limit: int = 8) -> list[dict]:
    """Rank roles for a free-text profile: hybrid semantic + demand fusion."""
    hits = index.query(profile_text, limit=max(limit, 10))
    if not hits:
        return []
    max_sem = max(s for _, s in hits) or 1.0
    max_demand = max(math.log1p(d.demand) for d, _ in hits) or 1.0
    profile_lc = profile_text.lower()

    out = []
    for doc, sem in hits:
        sem_n = sem / max_sem
        demand_n = math.log1p(doc.demand) / max_demand
        score = SEMANTIC_WEIGHT * sem_n + (1 - SEMANTIC_WEIGHT) * demand_n
        matched = [s for s in doc.top_skills if s.lower() in profile_lc
                   or any(w in profile_lc for w in s.lower().split() if len(w) > 4)]
        out.append({
            "noc_code": doc.noc_code,
            "title": doc.title,
            "score": round(score, 3),
            "semantic": round(sem_n, 3),
            "demand": doc.demand,
            "median_wage": doc.median_wage,
            "matched_skills": matched[:6],
            "top_skills": doc.top_skills[:6],
        })
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:limit]

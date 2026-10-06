"""Shared live-model validation helpers (M2 1B).

Importable by both the standalone validation script and the pytest live tests.
This module lives in the installed ``careeros`` package so tests import it
cleanly with zero path hacks (the ``scripts/`` directory is not a package).

Two public functions:
- ``build_validation_fixture()`` — deterministic opportunity + evidence + resume
- ``validate_evidence_contract()`` — evidence-citation contract validator
"""

from __future__ import annotations


def build_validation_fixture():
    """Deterministic real-world-shaped opportunity + evidence ledger.

    Returns (opportunity, evidence_items, base_resume_text). The third
    evidence item is deliberately non-claimable to verify it is never cited.
    """
    from careeros.evidence import Evidence
    from careeros.opportunity import Opportunity

    opportunity = Opportunity(
        opportunity_id=1,
        source="validation",
        role_title="Senior Analytics Engineer",
        company="Northwind Analytics",
        location="Toronto",
        work_mode="hybrid",
        employment_type="full-time",
        salary_min=120000.0,
        salary_max=145000.0,
        currency="CAD",
        description_raw=(
            "We need strong Python, SQL and Airflow skills; dbt and Docker are "
            "nice to have. You will own the warehouse and pipeline roadmap, "
            "partner with data science, and raise data quality. 5+ years."
        ),
        description_normalized=(
            "Senior Analytics Engineer Northwind Analytics Toronto hybrid "
            "Python SQL Airflow dbt Docker warehouse pipeline roadmap"
        ),
        required_skills=["Python", "SQL", "Airflow"],
        preferred_skills=["dbt", "Docker"],
        seniority="senior",
    )
    evidence = [
        Evidence(
            evidence_id=1,
            type="employment",
            title="Analytics Engineer",
            organization="Old Co",
            start_date="2020-01-01",
            end_date="2024-05-01",
            description=(
                "Built Python/SQL pipelines in Airflow; cut refresh "
                "times 40%. Owned the warehouse roadmap."
            ),
            skills=["Python", "SQL", "Airflow"],
            verification_status="documented",
        ),
        Evidence(
            evidence_id=2,
            type="project",
            title="dbt warehouse migration",
            description="Rebuilt the warehouse with dbt and Docker.",
            skills=["dbt", "Docker"],
            verification_status="self_reported",
        ),
        Evidence(
            evidence_id=3,
            type="certification",
            title="Empty certification slot",
            description="Placeholder that must never be cited.",
            claims_allowed=False,
            verification_status="self_reported",
        ),
    ]
    base_resume = (
        "Analytics engineer. Built and owned ETL pipelines (Python, SQL, Airflow) "
        "at Old Co. Led a dbt warehouse migration with Docker. Cut refresh times 40%."
    )
    return opportunity, evidence, base_resume


def validate_evidence_contract(result, valid_ids: set[int], label: str) -> list[str]:
    """Return a list of evidence-citation contract violations (empty = valid).

    Checks:
    1. output is non-empty
    2. every cited evidence ID exists in the provided ledger
    3. evidence_used and excluded_claims are disjoint
    4. excluded (unsupported) claims do not appear woven into the output
    """
    problems = []
    if not result.markdown or not result.markdown.strip():
        problems.append(f"{label}: empty markdown")
    bad = [i for i in result.evidence_used if i not in valid_ids]
    if bad:
        problems.append(f"{label}: cited evidence IDs not in ledger: {bad}")
    if set(result.evidence_used) & set(result.excluded_claims):
        problems.append(f"{label}: evidence/excluded sets overlap")
    # honesty check: excluded keywords must not appear as claims in the output
    for claim in result.excluded_claims:
        if claim.lower() in (result.markdown or "").lower():
            problems.append(f"{label}: excluded claim '{claim}' appears in output anyway")
    return problems

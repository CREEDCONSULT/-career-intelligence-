# Data Source Verification — Findings (spike, 2026-06-29/30)

Live probe of every data source. **These supersede the original PRD assumptions.**

## Summary table

| Source | Status | Verified endpoint / method | Critical notes |
|--------|--------|----------------------------|----------------|
| Job Bank postings | ✅ works | CKAN `package_show?id=ea639e28-c0fc-48bf-b5dd-b8899bd43072` → pick English resources, use `resource.url` (direct `.../download/...csv`) | **UTF-16 LE, TAB-delimited.** 81 English monthly CSVs. **No job-requirements free text.** |
| Job Bank wages | ✅ works | CKAN `package_show?id=adad580f-76b0-4502-bd05-20c125de9116` → 14 annual CSVs (2012–2025) | CKAN JSON occasionally flaky → retry. |
| StatsCan JVWS 14-10-0444 | ⚠️ blocked here | WDS `getFullTableDownloadCSV/14100444/en` → JSON `.object` → ZIP. **`www150.statcan.gc.ca` blocked from this sandbox (WinError 10054), every other host works.** | Code correct-by-structure; will run on user's CA connection. **Indeed metro is the primary Toronto market source instead.** |
| NOC 2021 | ✅ works | Direct: `https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/noc-2021-v1.0-classification-structure.csv` (`www.statcan` host is NOT blocked) | Cols: `Level, Hierarchical structure, Code - NOC 2021 V1.0, Class title, Class definition`. UTF-8 BOM, comma. |
| Lightcast Open Skills | ✅ works (mirror) | Gist raw: `https://gist.githubusercontent.com/ThatGuySam/8a6e7bd152793ac12b7f60420d1017c8/raw` | JSON `{"data":[{"id":"KS…","name":…,...}]}`. May 2023 snapshot, ~34K skills. No OAuth. Official API requires registration. |
| Indeed Hiring Lab | ✅ works | Repo `hiring-lab/job_postings_tracker`, **branch `master`** (not `main`) | `metro_job_postings_CA.csv` has **`Toronto, ON`**; also provincial/sector. Wage: `hiring-lab/indeed-wage-tracker/posted-wage-growth-by-sector.csv`. AI: `hiring-lab/ai-tracker/AI_posting.csv`. |

## Real Job Bank postings columns (TAB-sep, UTF-16)
`WIC Job Location Snapshot ID, Job Title, Original Job Title, NOC 2016 Code, NOC 2016 Code Name, NOC21 Code, NOC21 Code Name, External Indicator, First Posting Date, Vacancy Count, Education LOS, Experience Level, Government Type, Placement Agency, NAICS, Province/Territory, City, Work Location Postal Code, Economic  Region (double space), Various Location, Employment Type, Employment Term, …(many Salary Condition flags)…, Salary Per, Salary Minimum, Salary Maximum, …, Hours Per, Hours Minimum, Hours Maximum, Work Hours, Work Hours From Time, Work Hours To Time`

## Consequences for the design
1. **OQ-1 resolved (negative):** no requirements text. Skill extraction draws from `Original Job Title` + `Job Title` + `NOC21 Code Name`. Skill Demand view is **role/title-based**; state this honestly in methodology.
2. **Encoding:** postings reader MUST use `encoding="utf-16"`, `sep="\t"`. Wages/NOC are UTF-8(-BOM)/comma. Auto-detect BOM to be safe.
3. **Toronto filter:** postings `City` ∈ GTA set OR `Economic  Region` (double space) contains "Toronto".
4. **StatsCan optional here:** Market Context primary = Indeed metro (`Toronto, ON`) + sector wage growth + AI share. StatsCan JVWS is a documented, structurally-correct add-on the user runs locally.
5. **NOC join:** wages use `NOC_xxxxx`/5-digit; postings use `NOC21 Code` (5-digit). Strip prefix, zero-pad to 5 for the join key.

# Data Career Radar

## Proof of Concept and Technical Validation Plan

## 1. Document Purpose

This document defines the Proof of Concept, or PoC, for the Data Career Radar project.

The purpose of the PoC is to validate the most uncertain and technically important parts of the project before building the complete product.

The PoC should answer the following questions:

* Can the project collect a useful number of job postings?
* Can it obtain sufficiently rich job descriptions?
* Which sources are reliable enough for continued use?
* Can different source formats be normalized into one data model?
* Can a local language model extract useful structured information?
* Can the local GPU process enough jobs within an acceptable time?
* Can duplicate postings be identified with reasonable accuracy?
* Can the system rank jobs according to a candidate profile?
* Are the resulting analytics useful and trustworthy?
* Which parts are feasible for a weekend MVP?
* Which parts require future research or additional infrastructure?
* Which parts should explicitly not be implemented?

The PoC is not intended to be a polished product.

Its objective is to reduce uncertainty and support evidence-based architectural decisions.

---

# 2. PoC Philosophy

The PoC should prioritize learning over completeness.

The project should not begin by implementing a large application architecture. It should first test the assumptions that determine whether the product is viable.

The most important principle is:

> Build the smallest experiment capable of proving or disproving an important assumption.

The PoC should avoid:

* Complex frontend development.
* Production deployment.
* Multi-user support.
* Advanced authentication.
* Complex agent architectures.
* Large-scale scraping.
* Premature cloud infrastructure.
* Automatic job applications.
* Optimizations without measured need.

The PoC should focus on the complete information path:

```text
Source
→ Collection
→ Raw storage
→ Normalization
→ Local enrichment
→ Quality evaluation
→ Basic analytics
→ Decision
```

---

# 3. Main PoC Questions

The PoC should validate seven major areas.

## Area 1: Data Source Feasibility

Can public and authorized sources provide enough job postings with useful information?

## Area 2: Data Quality

Are job descriptions complete enough to support skill extraction and career analysis?

## Area 3: Source Normalization

Can records from different platforms be transformed into a common schema?

## Area 4: Local Model Feasibility

Can a local language model reliably extract structured information from job descriptions?

## Area 5: Processing Performance

Can the user’s local hardware process a practical number of jobs?

## Area 6: Recommendation Usefulness

Can a transparent matching system identify jobs that are genuinely relevant to the candidate?

## Area 7: Product Value

Do the resulting views and analytics answer useful career questions?

---

# 4. PoC Scope

## Included in the PoC

The PoC should include:

* A small set of job sources.
* Job collection through public APIs or public ATS endpoints.
* Raw data preservation.
* A normalized job schema.
* Basic source quality analysis.
* Local model integration.
* Structured skill extraction.
* Role family classification.
* Seniority classification.
* Basic duplicate detection.
* A configurable candidate profile.
* An initial matching score.
* Simple analytics through notebooks or a minimal interface.
* Evaluation datasets.
* Technical documentation.
* Go or no-go decisions.

## Excluded from the PoC

The PoC should not include:

* Authenticated LinkedIn scraping.
* CAPTCHA bypass.
* Browser cookie reuse.
* Automatic job applications.
* Full production-grade frontend.
* User authentication.
* Multiple candidate profiles.
* Cloud deployment.
* Real-time collection.
* Complex distributed processing.
* Fully autonomous career agents.
* Advanced salary prediction.
* Perfect duplicate detection.
* Perfect job classification.
* Complete coverage of the Brazilian or international job market.

---

# 5. PoC Success Definition

The PoC will be considered successful if it demonstrates that:

1. At least three job source connectors can be tested.
2. At least two sources provide job descriptions rich enough for analysis.
3. At least 200 valid job postings can be collected.
4. Raw source data can be stored and replayed.
5. Records from different sources can be normalized.
6. A local model can produce valid structured output for most tested jobs.
7. Basic skill extraction quality can be measured.
8. Obvious duplicate postings can be detected.
9. A candidate matching score produces understandable results.
10. The system can generate at least three useful market insights.
11. The complete experiment can run locally.
12. The results are documented with evidence and known limitations.

A successful PoC does not require every test to pass.

A failed experiment may still be valuable if it clearly identifies a limitation and supports a better design decision.

---

# 6. PoC Hypotheses

## Hypothesis H1: Public Sources Provide Sufficient Volume

Public APIs and public ATS endpoints can provide at least 200 relevant Data and AI job postings without requiring authenticated scraping.

### Evidence Required

* Number of records collected.
* Number of unique jobs.
* Number of relevant roles.
* Number of complete descriptions.
* Number of active application links.

### Pass Condition

At least 200 valid jobs are collected from at least two reliable sources.

### Fail Condition

Fewer than 100 valid jobs are collected or most records lack usable descriptions.

---

## Hypothesis H2: Source Data Is Rich Enough for Analysis

Most collected postings contain enough text to identify skills, seniority, work arrangement, and experience requirements.

### Evidence Required

For each source, measure:

* Percentage with descriptions.
* Average description length.
* Percentage with location.
* Percentage with publication date.
* Percentage with company information.
* Percentage with application URL.
* Percentage with salary information.
* Percentage with identifiable technical requirements.

### Pass Condition

At least one primary source provides complete descriptions for more than 80% of collected jobs.

### Partial Pass Condition

Descriptions are rich but metadata such as salary or publication date is often missing.

### Fail Condition

Most sources only provide titles and short summaries.

---

## Hypothesis H3: A Common Schema Can Represent Multiple Sources

Records from different sources can be mapped into one normalized model without losing important source-specific information.

### Evidence Required

* Successful schema mapping.
* Percentage of normalized records.
* Number of source-specific unmapped fields.
* Number of invalid records.
* Number of fields requiring source-specific logic.

### Pass Condition

At least 90% of valid source jobs can be mapped into the common schema.

### Fail Condition

The schema requires excessive source-specific exceptions or loses essential data.

---

## Hypothesis H4: A Local Model Can Extract Structured Information

A local language model can extract skills, role family, seniority, and experience requirements into valid structured output.

### Evidence Required

* JSON validation rate.
* Extraction accuracy.
* Classification accuracy.
* Processing time.
* Retry rate.
* Error examples.
* Hallucination examples.

### Pass Condition

* At least 90% valid JSON output after retries.
* At least 80% acceptable skill extraction on the evaluation sample.
* At least 80% acceptable role family classification.
* At least 75% acceptable seniority classification.

### Fail Condition

The model frequently produces invalid output, invents skills, or fails to distinguish required and preferred qualifications.

---

## Hypothesis H5: Local Processing Performance Is Practical

The local GPU can process a useful batch of job postings within an acceptable period.

### Evidence Required

* Jobs processed per minute.
* Average tokens processed.
* GPU utilization.
* VRAM usage.
* Failure rate.
* Average processing latency.
* Power or thermal issues, if observed.

### Initial Practical Target

The PoC should aim to process at least 100 jobs in one unattended batch.

### Pass Condition

A batch of 100 jobs completes reliably without manual intervention.

### Partial Pass Condition

Processing is reliable but slow enough to require incremental background execution.

### Fail Condition

The model cannot run reliably, repeatedly crashes, or requires more resources than available.

---

## Hypothesis H6: Duplicate Detection Is Feasible

The system can identify obvious duplicate job postings using deterministic rules and text similarity.

### Evidence Required

* Number of exact duplicates.
* Number of likely duplicates.
* False positive examples.
* False negative examples.
* Manual validation sample.

### Pass Condition

The system identifies most obvious duplicates while keeping false positives low.

### Fail Condition

Normal differences in title or description make deduplication unreliable.

---

## Hypothesis H7: Candidate Matching Produces Useful Rankings

A transparent scoring system can separate highly relevant jobs from clearly unsuitable jobs.

### Evidence Required

* Top-ranked jobs.
* Low-ranked jobs.
* Score breakdown.
* Manual relevance labels.
* Common disagreement cases.

### Pass Condition

At least 8 of the top 10 jobs are manually considered relevant.

### Fail Condition

The score is dominated by keyword overlap or recommends jobs with incompatible seniority or location.

---

## Hypothesis H8: The Product Generates Actionable Insights

The processed dataset can answer career questions better than manually browsing job boards.

### Evidence Required

At least three insights such as:

* Most requested skills.
* Most common skill combinations.
* Differences between role families.
* Most common missing candidate skills.
* Companies with relevant openings.
* Cloud platform distribution.
* Seniority distribution.
* Remote work distribution.

### Pass Condition

The results produce at least three insights that could influence learning, applications, or career decisions.

### Fail Condition

The analytics only reproduce obvious counts without supporting useful decisions.

---

# 7. PoC Architecture

The PoC should use a simple, modular architecture.

```text
Source Connectors
        ↓
Raw Job Records
        ↓
Normalization
        ↓
Local LLM Enrichment
        ↓
Validation
        ↓
Candidate Matching
        ↓
Evaluation and Analytics
```

## Recommended Components

### Collection

* Python HTTP client.
* Source-specific connector modules.
* Local fixture files for repeatable testing.

### Storage

* Raw JSON files or a raw database table.
* DuckDB for local structured analysis.
* Optional Parquet files for analytical experiments.

### Transformation

* Python.
* Pydantic models.
* Polars or Pandas.

### Local Model

* Ollama or another local inference runtime.
* One primary model.
* Optional second model for comparison.
* JSON Schema or Pydantic validation.

### Analysis

* Jupyter notebooks.
* SQL through DuckDB.
* Optional minimal Streamlit page.

### Testing

* Pytest.
* Saved API responses.
* Manually labeled evaluation samples.
* Snapshot tests for normalized outputs.

---

# 8. Data Source Proof of Concept

## 8.1 Source Candidate List

The PoC should test a small number of representative source types.

### Source Type A: Aggregator API

Possible candidates:

* Adzuna.
* Arbeitnow.
* Remotive.
* Remote OK.

The objective is to measure volume and general coverage.

### Source Type B: Greenhouse

The objective is to test a public ATS endpoint with rich company-originated data.

### Source Type C: Lever

The objective is to test a second ATS structure.

### Source Type D: Experimental Brazilian Source

The objective is to investigate whether public Brazilian company career pages provide reusable structured data.

This test should be optional and must not block the PoC.

---

## 8.2 Source Test Procedure

For each source:

1. Read the public access documentation or terms.
2. Identify the expected request format.
3. Make one manual request.
4. Save the complete response as a fixture.
5. Inspect available fields.
6. Count available jobs.
7. Filter for Data and AI roles.
8. Fetch complete job details if necessary.
9. Measure response stability.
10. Test pagination.
11. Test error responses.
12. Test empty results.
13. Record rate limit information when available.
14. Measure data completeness.
15. Document whether the source should be retained.

---

## 8.3 Source Evaluation Table

Each source should be evaluated using the following fields:

| Criterion            | Description                                |
| -------------------- | ------------------------------------------ |
| Access method        | API, ATS endpoint, feed, HTML, browser     |
| Authentication       | None, API key, token                       |
| Description quality  | Complete, partial, unavailable             |
| Location quality     | Structured, textual, missing               |
| Publication date     | Available, unreliable, missing             |
| Company information  | Complete, partial                          |
| Application URL      | Direct, redirect, missing                  |
| Pagination           | Supported, limited, unknown                |
| Rate limits          | Documented, inferred, unknown              |
| Brazil coverage      | High, medium, low                          |
| Remote coverage      | High, medium, low                          |
| Data role coverage   | High, medium, low                          |
| Stability            | Stable, uncertain, fragile                 |
| Legal or access risk | Low, medium, high                          |
| Recommended use      | Primary, secondary, experimental, rejected |

---

## 8.4 Source Acceptance Criteria

A source may be classified as:

### Primary Source

Use when:

* Descriptions are usually complete.
* Access is stable.
* Source identifiers are reliable.
* Application URLs are available.
* Terms and access patterns are acceptable.

### Secondary Source

Use when:

* Volume is useful.
* Some fields are incomplete.
* Duplicates are common.
* It supplements primary sources.

### Experimental Source

Use when:

* Technical access appears possible.
* Stability or terms require additional validation.
* The source may provide strategic coverage.

### Rejected Source

Reject when:

* Authentication scraping is required.
* Access depends on browser cookies.
* CAPTCHA bypass would be necessary.
* Descriptions are mostly unavailable.
* The source is too unstable.
* Legal or operational risk is too high.
* Maintenance cost exceeds expected value.

---

# 9. Data Richness Validation

## 9.1 Required Fields

The PoC should measure the availability of:

* Source identifier.
* Job title.
* Company.
* Description.
* Location.
* Application URL.
* Collection timestamp.

Records missing title, description, or source identifier should generally be rejected or quarantined.

## 9.2 Important Optional Fields

* Publication date.
* Salary.
* Employment type.
* Department.
* Remote status.
* Country.
* City.
* Workplace type.
* Job category.
* Company logo.
* Recruiter contact.
* Application deadline.

The project should not assume these fields are always available.

## 9.3 Description Quality Categories

Descriptions should be classified as:

### Complete

Contains responsibilities, requirements, and contextual information.

### Partial

Contains useful requirements but lacks sections or detail.

### Summary Only

Contains only a short paragraph or preview.

### Missing

No meaningful job description.

## 9.4 Data Richness Metrics

For every source, calculate:

```text
Description completeness rate
Location completeness rate
Publication date completeness rate
Application URL completeness rate
Salary transparency rate
Technical requirement detection rate
Average description character count
Median description character count
```

---

# 10. Raw Data Preservation Test

## Objective

Verify that original source responses can be stored and reprocessed.

## Procedure

1. Collect a sample response.
2. Store the entire payload.
3. Assign a collection timestamp.
4. Calculate a content hash.
5. Normalize the record.
6. Delete the normalized output.
7. Recreate the normalized output using only the stored raw payload.
8. Compare both normalized results.

## Pass Condition

The normalized result can be recreated without another network request.

## Important Decision

The project should preserve raw payloads even when they appear redundant.

Without raw preservation, future changes to the schema, parser, or local model would require recollecting the data.

---

# 11. Normalization PoC

## 11.1 Canonical Job Schema

The PoC should define a minimal canonical schema.

```json
{
  "source": "greenhouse",
  "source_job_id": "12345",
  "source_url": "https://example.com/job/12345",
  "application_url": "https://example.com/apply/12345",
  "title_raw": "Data Engineer II",
  "title_normalized": "Data Engineer",
  "company_raw": "Example Technologies Ltd.",
  "company_normalized": "Example Technologies",
  "description_raw": "Complete original description",
  "description_clean": "Cleaned plain text",
  "location_raw": "São Paulo, Brazil / Remote",
  "country": "Brazil",
  "region": "São Paulo",
  "city": "São Paulo",
  "work_arrangement": "hybrid",
  "employment_type": "full_time",
  "published_at": null,
  "collected_at": "2026-07-25T22:00:00",
  "first_seen_at": "2026-07-25T22:00:00",
  "last_seen_at": "2026-07-25T22:00:00"
}
```

## 11.2 Normalization Tests

Test at least the following cases:

* Missing location.
* Multiple locations.
* Remote only.
* Hybrid without city.
* International remote.
* Portuguese titles.
* English titles.
* Abbreviated seniority.
* Roman numerals.
* Level numbers.
* Company suffixes.
* HTML descriptions.
* Duplicate whitespace.
* Invalid dates.
* Redirect application links.

## 11.3 Normalization Principles

* Preserve the raw value.
* Add a normalized value separately.
* Do not invent missing information.
* Use explicit unknown values.
* Record normalization confidence where necessary.
* Prefer deterministic mappings.
* Make normalization rules testable.

---

# 12. Local Model Proof of Concept

## 12.1 Objective

Determine whether a local model can enrich job descriptions reliably and efficiently.

## 12.2 Initial Model Tasks

The PoC should test the model on:

* Role family classification.
* Seniority classification.
* Technical skill extraction.
* Soft skill extraction.
* Required versus preferred skill classification.
* Minimum experience extraction.
* Education requirement extraction.
* Language requirement extraction.
* Work arrangement interpretation.
* Short job summary.

## 12.3 Initial Output Schema

```json
{
  "role_family": "data_engineering",
  "seniority": "mid_level",
  "technical_skills": [
    {
      "name": "Python",
      "requirement_type": "required",
      "evidence": "Strong experience with Python is required"
    }
  ],
  "soft_skills": [
    {
      "name": "Communication",
      "requirement_type": "required"
    }
  ],
  "minimum_years_experience": 2,
  "education_required": false,
  "required_languages": ["English"],
  "work_arrangement": "remote",
  "summary": "Data engineering role focused on cloud pipelines and analytics."
}
```

## 12.4 Important Model Restrictions

The model must:

* Return only structured output.
* Use values from controlled enumerations.
* Avoid inventing missing requirements.
* Return null or unknown when uncertain.
* Include textual evidence for important extractions.
* Separate explicit information from inferred information.
* Never modify the original job description.

## 12.5 Prompt Comparison Test

Create at least three prompt versions.

### Prompt A: Minimal Extraction Prompt

Short instructions and output schema.

### Prompt B: Detailed Extraction Prompt

Includes field definitions and examples.

### Prompt C: Evidence-Based Prompt

Requires evidence excerpts for every important field.

Compare:

* JSON validity.
* Accuracy.
* Processing speed.
* Output length.
* Hallucination rate.
* Consistency.

## 12.6 Model Comparison Test

Test one primary local model and optionally one alternative.

Compare:

* Valid output rate.
* Latency.
* VRAM usage.
* Skill extraction quality.
* Classification quality.
* Stability.
* Ease of deployment.

The PoC should not select a model only because it is larger.

The selected model should provide the best balance between:

```text
Accuracy
+ reliability
+ processing speed
+ hardware compatibility
+ implementation simplicity
```

---

# 13. Local GPU and Runtime Validation

## 13.1 Objective

Verify that the local inference runtime uses the GPU reliably.

## 13.2 Tests

### Test 1: Runtime Detection

Confirm that the inference runtime detects the GPU.

### Test 2: Single Job Inference

Run enrichment for one representative job.

Measure:

* Response time.
* GPU usage.
* VRAM usage.
* Output validity.

### Test 3: Sequential Batch

Process 20 jobs sequentially.

Measure:

* Total duration.
* Average duration.
* Failures.
* Memory growth.
* Thermal stability.

### Test 4: Larger Batch

Process 100 jobs.

Measure:

* Jobs per minute.
* Invalid outputs.
* Retry rate.
* Runtime crashes.
* GPU utilization consistency.

### Test 5: Long Description

Process a job with an unusually long description.

Measure:

* Context handling.
* Truncation behavior.
* Response quality.
* Processing time.

### Test 6: CPU Fallback

Verify whether the system can still run in reduced mode without GPU acceleration.

## 13.3 Performance Metrics

Record:

```text
Model name
Model quantization
Prompt version
Average input length
Average output length
Average latency
Median latency
95th percentile latency
Jobs per minute
GPU utilization
VRAM usage
Retry rate
Failure rate
```

## 13.4 Performance Decision

### Accept

The model can process normal daily batches reliably.

### Accept with Limitation

The model works but should run incrementally or overnight.

### Reject

The runtime is unstable or impractical for the intended volume.

---

# 14. Evaluation Dataset

## 14.1 Objective

Create a manually reviewed dataset for measuring extraction quality.

## 14.2 Initial Sample Size

The initial evaluation dataset should contain between 30 and 50 job postings.

## 14.3 Dataset Diversity

Include:

* Data Engineering jobs.
* Data Science jobs.
* Machine Learning jobs.
* Analytics Engineering jobs.
* MLOps jobs.
* Junior positions.
* Mid-level positions.
* Senior positions.
* Portuguese descriptions.
* English descriptions.
* Remote roles.
* Hybrid roles.
* Ambiguous titles.
* Long descriptions.
* Short descriptions.

## 14.4 Manual Labels

For each job, manually record:

* Role family.
* Seniority.
* Required technical skills.
* Preferred technical skills.
* Minimum experience.
* Education requirement.
* Required languages.
* Work arrangement.

## 14.5 Evaluation Metrics

### Classification Metrics

* Accuracy.
* Precision.
* Recall.
* F1 score.
* Confusion matrix.

### Extraction Metrics

* Exact skill match.
* Normalized skill match.
* Required versus preferred accuracy.
* Unsupported skill rate.
* Missed skill rate.

### Structural Metrics

* Valid JSON rate.
* Schema validation rate.
* Retry rate.
* Missing field rate.

### Evidence Metrics

* Percentage of extracted claims supported by job text.
* Percentage of evidence snippets that genuinely support the field.

---

# 15. Skill Taxonomy PoC

## Objective

Determine whether extracted skill names can be normalized into a useful taxonomy.

## Example Normalization Cases

```text
PySpark → Apache Spark
Postgres → PostgreSQL
MS SQL Server → SQL Server
Azure Data Factory → ADF
Amazon Web Services → AWS
GCP → Google Cloud Platform
PowerBI → Power BI
Scikit Learn → scikit-learn
```

## Test Questions

* Can synonyms be normalized without losing meaning?
* Should cloud services be separate skills?
* Should generic SQL and database-specific skills coexist?
* How should versions be represented?
* How should broad concepts such as data modeling be stored?
* How should soft skills be categorized?
* Should inferred skills be separated from explicit skills?

## Initial Taxonomy Structure

```text
Skill
├── Programming Language
├── Database
├── Cloud Platform
├── Cloud Service
├── Data Processing
├── Orchestration
├── Data Modeling
├── BI and Visualization
├── Machine Learning
├── Statistics
├── DevOps
├── Software Engineering
└── Soft Skill
```

## Pass Condition

Most common synonyms can be mapped into canonical skill names without excessive manual rules.

---

# 16. Duplicate Detection PoC

## 16.1 Duplicate Types

### Exact Source Duplicate

Same source and same source job identifier.

### Cross-Source Exact Duplicate

Same company, title, location, and nearly identical description.

### Likely Duplicate

Small changes in title or description but probably the same opening.

### Similar but Distinct Job

Same company and title, but different team, location, or requisition.

## 16.2 Initial Duplicate Signals

* Normalized company.
* Normalized title.
* Normalized location.
* Publication date proximity.
* Description hash.
* Text similarity.
* Application URL.
* Requisition identifier.
* Skill overlap.

## 16.3 Initial Deduplication Strategy

### Stage 1: Exact Rules

```text
same source
+ same source job identifier
```

### Stage 2: Strong Cross-Source Rule

```text
same normalized company
+ same normalized title
+ same normalized location
+ high description similarity
```

### Stage 3: Candidate Duplicate Review

Records with medium similarity should be marked as possible duplicates instead of being automatically merged.

## 16.4 Evaluation

Create a manually reviewed set of at least 30 record pairs:

* 10 clear duplicates.
* 10 clearly different jobs.
* 10 ambiguous pairs.

Measure:

* Precision.
* Recall.
* False merges.
* Missed duplicates.

## 16.5 Important Restriction

The PoC should never permanently delete duplicate source records.

It should link them to a canonical job.

---

# 17. Candidate Profile PoC

## 17.1 Candidate Profile Structure

The initial profile should include:

```json
{
  "preferred_roles": [
    "data_engineering",
    "data_science",
    "machine_learning"
  ],
  "current_skills": {
    "Python": "intermediate",
    "SQL": "advanced",
    "Azure Data Factory": "intermediate",
    "Databricks": "intermediate",
    "Power BI": "intermediate"
  },
  "years_experience": 1,
  "preferred_seniority": [
    "junior",
    "mid_level"
  ],
  "preferred_work_arrangements": [
    "remote",
    "hybrid"
  ],
  "eligible_countries": [
    "Brazil"
  ],
  "languages": {
    "Portuguese": "native",
    "English": "intermediate"
  }
}
```

## 17.2 Privacy Test

The candidate profile must:

* Be stored outside the public repository.
* Be replaceable by a fictional sample profile.
* Not require the user’s full résumé.
* Avoid storing unnecessary personal identifiers.
* Be loadable through a local configuration file.

---

# 18. Matching Score PoC

## 18.1 Objective

Determine whether deterministic signals can produce useful job rankings.

## 18.2 Initial Score Components

Example:

```text
Required skill coverage         30%
Preferred skill coverage        10%
Role family compatibility       15%
Seniority compatibility         15%
Location eligibility            10%
Work arrangement compatibility  10%
Experience compatibility         5%
Language compatibility           5%
```

These weights are initial assumptions and must be tested.

## 18.3 Hard Constraints

Certain conditions may strongly reduce the score:

* Job not available in the candidate’s country.
* Seniority far above the candidate profile.
* Missing mandatory language.
* Mandatory experience requirement far above the candidate’s experience.
* On-site role in an incompatible location.

## 18.4 Stretch Role Logic

The platform should distinguish between:

* Strong match.
* Reasonable match.
* Strategic stretch.
* Low match.
* Ineligible.

A job should not be rejected only because the candidate lacks one preferred skill.

## 18.5 Matching Evaluation

Manually label at least 30 jobs as:

* Highly relevant.
* Relevant.
* Possible stretch.
* Not relevant.
* Ineligible.

Compare manual labels with the generated ranking.

## 18.6 Pass Condition

At least 80% of top-ranked jobs should be manually considered highly relevant or relevant.

---

# 19. Analytics PoC

## 19.1 Objective

Validate whether the dataset produces useful market insights.

## 19.2 Initial Questions

The PoC should answer:

* Which technical skills appear most frequently?
* Which skills appear together?
* Which role families are most common?
* Which cloud platforms are most requested?
* Which seniority levels dominate the dataset?
* How many jobs are remote?
* Which companies have the most relevant openings?
* Which skills are frequently missing from the candidate profile?
* What differentiates Data Engineering from Data Science postings?
* Which jobs are most compatible with the candidate?

## 19.3 Initial Outputs

The PoC may use:

* SQL queries.
* Notebook tables.
* Bar charts.
* Skill co-occurrence matrix.
* Candidate gap table.
* Ranked job table.

## 19.4 Insight Quality Test

Each insight should include:

* The metric.
* The filtered population.
* The number of jobs analyzed.
* Known source bias.
* Missing data limitations.
* The practical implication.

Example:

```text
Apache Spark appears in 42% of Data Engineering postings in the sample.

Interpretation:
Spark appears to be a high-value skill for the selected role family.

Limitation:
The sample contains a high number of jobs from companies using Greenhouse,
which may not represent the complete Brazilian market.
```

---

# 20. Data Quality PoC

## 20.1 Required Quality Checks

* Missing title.
* Missing description.
* Missing source identifier.
* Invalid application URL.
* Invalid date.
* Empty company name.
* Unsupported country.
* Description too short.
* Duplicate source identifier.
* Invalid normalized enum.
* Invalid LLM JSON.
* Unsupported LLM claim.

## 20.2 Quality Report

Every PoC execution should generate:

```text
Total records collected
Valid records
Rejected records
Quarantined records
Duplicate records
Records with complete descriptions
Records enriched successfully
Records with invalid model output
Records with low confidence
```

## 20.3 Quarantine Strategy

Invalid records should be preserved in a quarantine area with:

* Original payload.
* Source.
* Error type.
* Error message.
* Pipeline stage.
* Timestamp.

---

# 21. Connector Reliability Tests

Every connector should be tested against:

## Normal Cases

* Multiple results.
* Complete job.
* Pagination.
* Standard text.

## Edge Cases

* Empty result.
* Missing field.
* Invalid date.
* HTML in description.
* Duplicate result.
* International characters.
* Long title.
* Multiple locations.

## Failure Cases

* Timeout.
* HTTP error.
* Rate limit.
* Invalid response format.
* Partial response.
* Temporary source outage.

## Expected Connector Behavior

* Retry temporary failures.
* Stop retrying permanent failures.
* Log the error.
* Continue processing other sources.
* Preserve failed payloads when available.
* Return an execution summary.

---

# 22. Repeatability Tests

## Objective

Ensure the PoC can be reproduced.

## Test Procedure

1. Save source fixtures.
2. Run normalization using fixtures.
3. Run enrichment using fixed model settings.
4. Store prompt version.
5. Store model version.
6. Run the complete pipeline twice.
7. Compare outputs.

## Expected Result

Deterministic stages should produce identical outputs.

Model stages may vary slightly, but structured fields should remain reasonably consistent.

## Important Metadata

Store:

* Connector version.
* Schema version.
* Prompt version.
* Model name.
* Model configuration.
* Execution timestamp.
* Pipeline version.

---

# 23. Security and Privacy Validation

## Required Tests

* Verify API keys are read from environment variables.
* Verify secrets are ignored by Git.
* Verify candidate profile is ignored by Git.
* Verify raw data does not contain unnecessary personal information.
* Verify application logs do not expose secrets.
* Verify the local model does not receive unrelated private files.
* Verify browser automation is not using personal sessions.
* Verify the project operates with least-privilege file access.

## Public Repository Requirements

The public repository should include:

* Sample environment file.
* Fictional candidate profile.
* Small permitted sample dataset.
* Setup instructions.
* No real credentials.
* No private résumé.
* No personal application notes.

---

# 24. Legal and Ethical Validation

The PoC should document for each source:

* Whether the endpoint is public.
* Whether authentication is required.
* Whether attribution is required.
* Whether request limits are documented.
* Whether data redistribution is restricted.
* Whether the project stores full descriptions.
* Whether the source allows automated access.
* Whether the source should be used only locally.

The project must not:

* Bypass authentication.
* Circumvent CAPTCHAs.
* Ignore explicit access restrictions.
* Use stolen or leaked credentials.
* Pretend to be a real user through personal sessions.
* Overload a source with excessive requests.
* Redistribute data when not permitted.
* Collect personal recruiter information unnecessarily.

When access rules are unclear, the connector should remain experimental until reviewed.

---

# 25. What the PoC Can Prove

The PoC can prove:

* Whether selected sources are technically accessible.
* Whether data volume is sufficient for an MVP.
* Whether descriptions are rich enough.
* Whether the canonical schema is practical.
* Whether a local model can enrich postings.
* Whether the GPU can support the workload.
* Whether extraction quality is acceptable.
* Whether basic duplicate detection works.
* Whether matching is useful.
* Whether meaningful analytics can be produced.
* Whether the idea is strong enough for a larger project.

---

# 26. What the PoC Cannot Prove

The PoC cannot prove:

* Complete job market coverage.
* Long-term source stability.
* Commercial product viability.
* Perfect classification accuracy.
* Perfect duplicate detection.
* Long-term user retention.
* Salary prediction accuracy.
* Multi-user scalability.
* Production security.
* Cloud cost.
* Legal acceptability for every possible source.
* Whether job recommendations improve hiring outcomes.
* Historical trends without historical data.
* Whether companies will continue publishing through the same ATS.
* Whether a local model will remain the best option over time.

---

# 27. What Should Not Be Attempted During the PoC

The following should explicitly be avoided:

## Authenticated Platform Scraping

Do not automate personal LinkedIn or Indeed sessions.

## Automatic Application Submission

Do not attempt to fill forms or submit applications.

## Large Browser Automation Framework

Do not create dozens of Playwright scrapers.

## Complex Multi-Agent System

Do not create separate planner, analyst, reviewer, and career coach agents before validating basic extraction.

## Production Cloud Architecture

Do not add Kubernetes, distributed queues, or cloud data lakes during the PoC.

## Perfect Taxonomy

Do not attempt to manually classify every technology in the market.

## Predictive Salary Models

Do not infer salary where no salary data exists.

## Fully Automated Career Advice

Do not allow the model to make unsupported career decisions.

## Unlimited Data Collection

Do not maximize volume before measuring data quality.

---

# 28. Experiment Prioritization

Experiments should be executed in the following order.

## Priority 1: Source Access

Without useful source data, the product is not viable.

## Priority 2: Description Quality

Without complete descriptions, local enrichment will have limited value.

## Priority 3: Local Model Structured Extraction

This validates the main local AI component.

## Priority 4: Hardware Performance

This determines the practical batch size.

## Priority 5: Normalization

This enables multi-source analytics.

## Priority 6: Matching

This validates personal usefulness.

## Priority 7: Deduplication

This improves metric reliability.

## Priority 8: Interface

The interface should only be built after the information pipeline is proven.

---

# 29. Recommended PoC Execution Plan

## Phase 1: Environment Validation

### Deliverables

* Python environment.
* Local inference runtime.
* GPU usage confirmation.
* Local database.
* Test command.
* Project configuration.

### Decision Gate

Can the environment run one local model request reliably?

---

## Phase 2: Source Exploration

### Deliverables

* One aggregator sample.
* One Greenhouse sample.
* One Lever sample.
* Source comparison report.
* Saved fixtures.

### Decision Gate

Do at least two sources provide useful descriptions and application links?

---

## Phase 3: Raw Collection

### Deliverables

* Connector interface.
* Three experimental connectors.
* Raw payload storage.
* Collection summary.

### Decision Gate

Can at least 200 valid jobs be collected?

---

## Phase 4: Normalization

### Deliverables

* Canonical schema.
* Source mappings.
* Validation rules.
* Normalization tests.

### Decision Gate

Can at least 90% of valid records be normalized?

---

## Phase 5: Local Enrichment

### Deliverables

* Structured extraction prompt.
* Validated output schema.
* Enriched sample.
* Error report.
* Performance metrics.

### Decision Gate

Is model output accurate and stable enough for the MVP?

---

## Phase 6: Evaluation

### Deliverables

* Manually labeled dataset.
* Accuracy metrics.
* Failure examples.
* Prompt comparison.
* Model decision.

### Decision Gate

Does the selected model meet minimum extraction quality?

---

## Phase 7: Matching and Analytics

### Deliverables

* Candidate profile.
* Initial match score.
* Ranked jobs.
* Skill frequency analysis.
* Skill gap analysis.

### Decision Gate

Are the top recommendations useful and explainable?

---

## Phase 8: PoC Conclusion

### Deliverables

* Final result report.
* Passed and failed hypotheses.
* Recommended architecture.
* Rejected approaches.
* MVP scope.
* Future research list.

### Decision Gate

Should the project proceed to MVP development?

---

# 30. Go, Conditional Go, and No-Go Criteria

## Go

Proceed to the MVP when:

* Data sources provide sufficient volume.
* Description quality is acceptable.
* Local enrichment works reliably.
* Hardware performance is practical.
* Basic recommendations are useful.
* Risks are manageable.

## Conditional Go

Proceed with restrictions when:

* Data volume is moderate but useful.
* Local processing is slow but reliable.
* Some sources are rejected.
* Duplicate detection is limited.
* Matching needs manual adjustment.

Possible restrictions:

* Run enrichment only on new jobs.
* Use fewer sources.
* Use a smaller model.
* Limit initial geography.
* Delay advanced analytics.
* Use manual company catalog entries.

## No-Go

Do not proceed with the current design when:

* Sources do not provide complete descriptions.
* Most useful sources require prohibited access.
* Local inference is unstable.
* Enrichment quality is too low.
* Recommendations are not meaningfully better than keyword search.
* Maintenance cost appears greater than personal value.

A no-go decision does not necessarily end the project.

It may indicate the need to change:

* Data sources.
* Model.
* project scope.
* target user.
* product focus.
* collection strategy.

---

# 31. PoC Result Report Template

## Executive Summary

Briefly describe:

* What was tested.
* What worked.
* What failed.
* Whether the project should continue.

## Hypothesis Results

| Hypothesis           | Result    | Evidence                   | Decision        |
| -------------------- | --------- | -------------------------- | --------------- |
| H1: Source volume    | Pass/Fail | Collected job count        | Continue/change |
| H2: Data richness    | Pass/Fail | Completeness metrics       | Continue/change |
| H3: Normalization    | Pass/Fail | Valid mapping rate         | Continue/change |
| H4: Local extraction | Pass/Fail | Accuracy metrics           | Continue/change |
| H5: Performance      | Pass/Fail | Jobs per minute            | Continue/change |
| H6: Deduplication    | Pass/Fail | Precision and recall       | Continue/change |
| H7: Matching         | Pass/Fail | Top recommendation quality | Continue/change |
| H8: Product value    | Pass/Fail | Useful insights            | Continue/change |

## Source Decisions

For each tested source:

* Retain.
* Retain with limitations.
* Continue investigating.
* Reject.

## Model Decision

Record:

* Selected model.
* Selected prompt.
* Performance.
* Limitations.
* Fallback model.
* Reprocessing strategy.

## MVP Recommendation

State:

* What should be implemented.
* What should be delayed.
* What should be removed.
* What should be researched.

---

# 32. Recommended Final PoC Deliverables

The complete PoC should produce:

1. Source feasibility report.
2. Source comparison table.
3. Saved source fixtures.
4. Raw data storage prototype.
5. Canonical job schema.
6. Normalization tests.
7. Local model integration prototype.
8. Prompt comparison results.
9. GPU performance report.
10. Manually labeled evaluation dataset.
11. Skill extraction evaluation.
12. Duplicate detection experiment.
13. Candidate matching experiment.
14. Basic analytics notebook.
15. Data quality report.
16. Risk register.
17. Go or no-go recommendation.
18. Refined MVP backlog.
19. Updated architecture proposal.
20. Known limitations document.

---

# 33. Final PoC Recommendation

The PoC should begin with three decisive experiments:

## Experiment 1: Source Quality

Collect approximately 50 jobs from each selected source and compare data richness.

## Experiment 2: Local Extraction

Manually label 30 diverse job descriptions and compare local model extraction against those labels.

## Experiment 3: Candidate Ranking

Score at least 30 jobs against the candidate profile and manually review the ranking.

If these three experiments succeed, the project has a strong foundation.

If one fails, the architecture or scope should be adjusted before building the full application.

The first implementation goal should not be:

> Build a complete job platform.

It should be:

> Prove that reliable job data can be transformed locally into useful and explainable career intelligence.

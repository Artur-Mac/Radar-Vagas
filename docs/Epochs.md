# Data Career Radar

## Project Definition and Product Epics

## 1. Project Overview

### Project Name

**Data Career Radar**

### Project Summary

Data Career Radar is a job market and career intelligence platform with a local-first
development foundation and a future path to an accessible hosted web product. It initially
focuses on Data Engineering, Data Science, Machine Learning, Analytics Engineering, MLOps,
and AI Engineering roles.

The platform collects job postings from multiple public and authorized sources, stores their
original content, normalizes inconsistent information, enriches postings through deterministic
rules and optional replaceable inference providers, and provides analytics about skills,
technologies, companies, seniority levels, locations, and hiring trends.

The first version is designed primarily as a personal career tool. It should help the user:

* Find relevant job opportunities.
* Understand which skills are most demanded.
* Compare their profile with current market requirements.
* Identify career and learning gaps.
* Track changes in the Data and AI job market.
* Prioritize job applications.

The architecture should also allow the project to grow into a broader job market intelligence platform without requiring a complete redesign.

---

## 2. Product Vision

Build a reliable and explainable job intelligence system that transforms fragmented job postings into structured, searchable, and actionable career information.

The platform should answer questions such as:

* Which technologies are most requested for Data Engineering roles?
* Which skills commonly appear together?
* What is the difference between Junior, Mid-level, and Senior positions?
* Which companies are hiring professionals with Azure and Databricks experience?
* Which requirements are mandatory and which are only preferred?
* Which job postings are compatible with the user’s current profile?
* Which missing skills would provide the greatest career return?
* Are certain technologies becoming more or less common over time?
* How long do job postings remain active?
* Which companies frequently reopen similar positions?

---

## 3. Initial Target User

The initial target user is a Data Engineer transitioning toward more advanced Data Science and Machine Learning opportunities.

The user has experience with technologies such as:

* Python
* SQL
* Azure Data Factory
* Azure Databricks
* Azure Data Lake
* Azure SQL
* Power BI
* Data pipeline support
* Data observability
* SAP data integration
* Git
* Automation

The user is interested in:

* Data Engineering
* Data Science
* Machine Learning
* Analytics Engineering
* MLOps
* AI Engineering
* Applied mathematics
* Remote opportunities
* Brazilian and international job markets

The system must remain generic enough to support other user profiles in the future.

---

## 4. Primary Product Goals

### Goal 1: Reliable Job Collection

Collect a meaningful number of job postings from multiple sources while preserving their original content and source information.

### Goal 2: Structured Market Data

Transform inconsistent job descriptions into a normalized data model that supports analytics and filtering.

### Goal 3: Evidence-Based Hybrid Enrichment

Use deterministic extraction first and optional replaceable inference providers for information
that cannot be reliably obtained through rules alone.

### Goal 4: Personal Career Intelligence

Compare job requirements against the user’s skills, experience, preferences, and career goals.

### Goal 5: Historical Market Analysis

Store job posting history so the system can analyze changes over time instead of showing only the current market state.

### Goal 6: Portfolio Quality

Demonstrate practical knowledge of:

* Data ingestion
* API integration
* Web data collection
* Incremental processing
* Data modeling
* Data quality
* NLP
* Provider-independent and local inference
* Search
* Recommendation systems
* Analytics
* Backend development
* Frontend development
* Testing
* Observability
* Documentation

---

## 5. Initial Job Scope

### Included Role Families

The first version should collect and classify the following roles:

* Data Engineer
* Analytics Engineer
* Data Scientist
* Machine Learning Engineer
* MLOps Engineer
* AI Engineer
* Data Platform Engineer
* Business Intelligence Engineer
* Technical Data Analyst

Data Analyst positions may be included when their descriptions contain significant technical requirements such as SQL, Python, cloud platforms, data modeling, or statistical analysis.

### Initial Seniority Levels

The ingestion layer should collect all seniority levels:

* Internship
* Entry-level
* Junior
* Mid-level
* Senior
* Staff
* Principal
* Lead
* Manager

The recommendation layer should initially prioritize:

* Junior roles
* Mid-level roles
* Roles with flexible experience requirements

### Initial Geographic Scope

The platform should prioritize:

* Jobs based in Brazil.
* Remote jobs available to candidates in Brazil.
* Remote jobs available across Latin America.
* International remote jobs that explicitly accept global candidates.

International roles that do not clearly accept Brazilian candidates may still be stored for market trend analysis but should receive a lower application relevance score.

### Supported Languages

The platform should initially process job postings written in:

* English
* Portuguese
* Spanish

The normalized output should use English as the standard internal language.

---

## 6. Initial Data Sources

### Preferred Source Order

Sources should be prioritized in the following order:

1. Official public APIs.
2. Public ATS job board APIs.
3. Public JSON or RSS feeds.
4. Official company career pages.
5. Static HTML scraping.
6. Browser automation as a last resort.

### Initial Aggregator Sources

Potential initial sources include:

* Adzuna
* Arbeitnow
* Remotive
* Remote OK

The project should not depend exclusively on aggregators because they may contain incomplete descriptions, duplicated listings, or reduced coverage for Brazil.

### Initial ATS Sources

The first ATS connectors should prioritize:

* Greenhouse
* Lever
* Ashby, after initial validation
* SmartRecruiters, after initial validation

A company catalog should map organizations to their public career systems.

Example:

```json
{
  "company_name": "Example Company",
  "source_type": "greenhouse",
  "board_identifier": "example-company",
  "career_url": "https://example.com/careers",
  "active": true
}
```

### Experimental Brazilian Sources

Public career pages hosted on Brazilian platforms, particularly Gupy, should be investigated.

Gupy should initially be considered an experimental connector and must not block the delivery of the MVP.

### Excluded Initial Sources

The first version should not use:

* Authenticated LinkedIn scraping.
* Aggressive Indeed scraping.
* CAPTCHA bypass systems.
* Personal browser cookies.
* Unofficial automation that risks user accounts.
* Paid data providers.
* Automatic job applications.

---

## 7. Core Domain Definitions

### Job Source

A platform, API, feed, ATS, or company website from which job data is collected.

Examples:

* Greenhouse
* Lever
* Adzuna
* Remotive
* Company career website

### Source Job

A job listing exactly as it appears in a specific source.

The same real-world opportunity may have multiple source jobs if it appears on different platforms.

### Canonical Job Posting

The internal representation of a unique real-world job opportunity.

Multiple source jobs may be linked to one canonical job posting.

### Raw Payload

The complete original JSON, HTML, or text collected from a source before transformation.

Raw payloads must be preserved so that the data can be reprocessed later without collecting the source again.

### Job Snapshot

A timestamped observation of a source job.

Snapshots allow the system to identify:

* New jobs.
* Updated descriptions.
* Removed jobs.
* Reopened jobs.
* Changes in salary, location, title, or requirements.

### First Seen Date

The first date on which the platform collected the job.

### Last Seen Date

The most recent date on which the job was still available in its source.

### Published Date

The publication date provided by the original source.

This value may be missing or unreliable.

### Job Status

The inferred current condition of a job posting.

Possible values:

* Active
* Possibly inactive
* Closed
* Reopened
* Unknown

A job should not be marked as closed after only one failed observation.

### Role Family

A normalized professional category.

Examples:

* Data Engineering
* Data Science
* Machine Learning
* Analytics Engineering
* MLOps
* AI Engineering
* Data Analytics

### Normalized Title

A standardized job title derived from the original title.

Example:

```text
Original title: Senior Data Engineer II – Azure Platform
Normalized title: Senior Data Engineer
```

### Skill

A technical or professional capability mentioned in a job posting.

Examples:

* Python
* SQL
* Spark
* Databricks
* AWS
* Azure
* Statistics
* Communication

### Skill Requirement Type

The relationship between a skill and the job.

Possible values:

* Required
* Preferred
* Mentioned
* Inferred
* Unknown

### Skill Category

A broader group assigned to a skill.

Examples:

* Programming language
* Cloud platform
* Database
* Data processing
* Orchestration
* BI and visualization
* Machine learning
* DevOps
* Soft skill

### Seniority

The expected professional level of the candidate.

Possible normalized values:

* Internship
* Junior
* Mid-level
* Senior
* Staff
* Principal
* Lead
* Manager
* Unknown

### Work Arrangement

The expected work location model.

Possible values:

* Remote
* Hybrid
* On-site
* Flexible
* Unknown

### Candidate Eligibility

An estimation of whether the user is realistically allowed to apply.

Possible values:

* Eligible
* Probably eligible
* Eligibility unclear
* Probably not eligible
* Not eligible

### Match Score

A numerical estimate of how closely a job matches the user’s profile and preferences.

The match score must not be generated by an LLM alone.

It should combine deterministic signals such as:

* Skill overlap.
* Missing mandatory skills.
* Seniority compatibility.
* Location compatibility.
* Language requirements.
* Years of experience.
* Education requirements.
* Work arrangement.
* Role preference.

### Match Explanation

A human-readable explanation of the match score.

Example:

```text
Strong match because the position requires Python, SQL, Azure, and Databricks.
The main gaps are Airflow and advanced Spark optimization.
The role requests three years of experience, which may be slightly above the
candidate’s current level.
```

### Data Confidence

A score representing confidence in an extracted or normalized field.

Confidence should be recorded for uncertain fields such as:

* Seniority.
* Minimum years of experience.
* Remote eligibility.
* Required skills.
* Salary.
* Education requirements.

---

## 8. MVP Definition

The Minimum Viable Product must prove that the platform can:

1. Collect job postings from at least three different source types.
2. Preserve raw source data.
3. Normalize job information into a common schema.
4. Extract skills and requirements using a local language model.
5. Identify obvious duplicate postings.
6. Search and filter job postings.
7. Compare jobs against a configurable candidate profile.
8. Display basic market analytics.
9. Run locally on Linux.
10. Continue operating without paid LLM APIs.

### MVP Success Criteria

The first version will be considered successful when it can:

* Collect at least 300 valid job postings.
* Store job descriptions and original application links.
* Process postings from at least one aggregator and two ATS connectors.
* Identify role family and seniority for most postings.
* Extract technical skills into structured JSON.
* Filter jobs by role, seniority, location, source, and remote status.
* Rank jobs based on candidate relevance.
* Display the most common skills and technologies.
* Preserve the data required for future historical analysis.
* Run the full pipeline through a documented command.

---

# 9. Product Epics

## Epic 1: Project Foundation

### Objective

Create a maintainable technical foundation for local development and future expansion.

### Scope

* Define the application architecture.
* Configure Python environment and dependency management.
* Configure environment variables.
* Add code formatting and linting.
* Add basic automated tests.
* Create local service configuration.
* Establish development conventions.
* Document how to run the project.

### Expected Outcome

A developer can clone the project, configure the environment, and run the basic application locally.

### Acceptance Criteria

* The project runs on the user’s Linux environment.
* Secrets are not committed to the repository.
* Formatting, linting, and tests can be executed through documented commands.
* The project contains a clear README.
* Local model connectivity can be tested independently.

---

## Epic 2: Source Catalog and Connector Framework

### Objective

Create a reusable system for registering and executing job data sources.

### Scope

* Define a common connector interface.
* Create a source configuration model.
* Create a company-to-ATS catalog.
* Implement connector health status.
* Record source metadata.
* Support pagination and collection limits.
* Implement polite request intervals and retries.

### Expected Outcome

New job sources can be added without modifying the entire ingestion pipeline.

### Acceptance Criteria

* Every connector follows a common interface.
* Every collected record identifies its source.
* Connector failures do not stop unrelated sources.
* Source-specific settings are stored outside business logic.
* Each connector produces a standardized intermediate result.

---

## Epic 3: Initial Job Ingestion

### Objective

Collect a useful initial volume of job postings.

### Initial Connectors

* One aggregator API.
* Greenhouse Job Board API.
* Lever Postings API.
* One additional remote job feed, when time permits.

### Scope

* Fetch job listings.
* Handle pagination.
* Preserve source identifiers.
* Record collection timestamps.
* Store application URLs.
* Store original descriptions.
* Record collection errors.
* Prevent exact duplicate ingestion.

### Expected Outcome

The platform contains a meaningful collection of Data and AI job postings.

### Acceptance Criteria

* At least 300 valid postings are collected.
* At least three source connectors are functional.
* Each posting contains a source URL or application URL.
* Each run produces an ingestion summary.
* Failed records are logged without terminating the complete run.

---

## Epic 4: Raw Data and Historical Storage

### Objective

Preserve source data and create the basis for incremental and historical processing.

### Scope

* Store raw API payloads.
* Store cleaned source text.
* Record first-seen and last-seen timestamps.
* Create job snapshots.
* Detect changed source payloads.
* Support replay and reprocessing.
* Separate raw, normalized, and enriched data.

### Expected Outcome

Collected data can be reprocessed without requiring another network request.

### Acceptance Criteria

* Original payloads remain accessible.
* Existing jobs are updated instead of blindly duplicated.
* Changed descriptions create a new snapshot or version.
* The system can identify jobs that disappeared from a source.
* Raw records are linked to normalized records.

---

## Epic 5: Job Normalization

### Objective

Convert heterogeneous source records into a consistent job schema.

### Scope

Normalize:

* Company name.
* Job title.
* Location.
* Country.
* State or region.
* Work arrangement.
* Employment type.
* Publication date.
* Description.
* Application URL.
* Source.
* Role family.
* Seniority.

### Expected Outcome

Jobs from different platforms can be searched and analyzed together.

### Acceptance Criteria

* All supported sources map to the same canonical schema.
* Original values are preserved alongside normalized values.
* Missing values are represented consistently.
* Normalization rules are covered by tests.
* Invalid records are quarantined instead of silently accepted.

---

## Epic 6: Evidence-Based Hybrid Enrichment

### Objective

Transform unstructured job descriptions into structured, traceable career information through
a replaceable enrichment engine that combines deterministic extraction with optional
language-model inference.

### Initial Responsibilities

* Extract technical skills.
* Extract soft skills.
* Identify required and preferred skills.
* Identify minimum years of experience.
* Identify education requirements.
* Detect language requirements.
* Resolve ambiguous role-family or seniority evidence without replacing reliable Época 5 data.
* Generate a short evidence-based structured summary.
* Attach evidence and provenance to extracted facts.

### Technical Requirements

* Deterministic extraction must run before optional model inference.
* The enrichment engine must expose a provider-independent interface.
* The initial implementation must include a no-LLM rule-based provider and may include Ollama
  as the first inference adapter.
* The architecture must support a future hosted provider without redesigning business logic.
* Ingestion, normalization, search, and basic matching must continue working when model
  inference is disabled or unavailable.
* Model inference should be requested only for fields that remain incomplete or ambiguous.
* Outputs must follow a versioned JSON schema and include supporting evidence where applicable.
* Invalid responses must be retried within configured limits, rejected, or quarantined.
* Provider, model, prompt, and schema versions must be stored with each result.
* Original job text must always remain available.
* Results must be cached by content hash, provider, model, prompt, and schema version.
* Only new or changed descriptions should be enriched.
* Enrichment must run asynchronously and must not block collection or basic product access.
* Batch size, concurrency, timeout, retries, and per-run limits must be configurable.
* The first local evaluation must use bounded batches and concurrency of one.

### Expected Outcome

Unstructured descriptions become structured and traceable records. The initial project can
operate locally without a paid API, while a future web product can use centrally hosted
inference without requiring users to own a powerful computer.

### Acceptance Criteria

* At least one useful deterministic extraction stage operates without an LLM.
* The application remains functional with enrichment inference disabled.
* Previously processed content is not unnecessarily reprocessed.
* Most evaluation postings produce valid structured output.
* Extracted facts include evidence or deterministic provenance where applicable.
* Enrichment results include provider, model, prompt, and schema metadata.
* Failed extractions are traceable, retryable, and quarantined when unrecoverable.
* The same description can be reprocessed with a different provider, model, prompt, or schema.
* A manually reviewed dataset with at least 30 diverse postings measures field-level quality,
  JSON validity, latency, failures, and unsupported claims.
* One bounded Ollama evaluation may be included, but local inference is not a permanent
  requirement for end users.

---

## Epic 7: Duplicate Detection and Canonical Jobs

### Objective

Identify when the same job opportunity appears in multiple sources.

### Scope

* Exact source duplicate detection.
* Normalized company comparison.
* Normalized title comparison.
* Location comparison.
* Description similarity.
* Canonical job creation.
* Source-to-canonical-job relationships.

### Expected Outcome

The system avoids misleading counts while preserving information about every source.

### Acceptance Criteria

* Exact duplicates are automatically merged or linked.
* Potential duplicates receive a similarity score.
* Source records are never permanently discarded.
* Users can inspect which sources reference the same canonical job.
* Duplicate logic can be adjusted and reprocessed.

---

## Epic 8: Candidate Profile and Job Matching

### Objective

Rank job opportunities based on the user’s professional profile and goals.

### Candidate Profile Data

* Current skills.
* Years of experience.
* Preferred role families.
* Preferred seniority.
* Preferred work arrangement.
* Geographic eligibility.
* Languages.
* Education.
* Technologies the user wants to learn.
* Technologies the user does not want to prioritize.

### Matching Signals

* Required skill coverage.
* Preferred skill coverage.
* Missing mandatory skills.
* Role compatibility.
* Seniority compatibility.
* Location and remote eligibility.
* Language compatibility.
* Experience requirements.
* Education requirements.
* Strategic learning value.

### Expected Outcome

The platform helps the user prioritize jobs instead of only listing them.

### Acceptance Criteria

* Every enriched job can receive a match score.
* The score includes a transparent breakdown.
* Mandatory gaps have a stronger negative impact than preferred gaps.
* The user can adjust matching weights.
* The explanation references actual job requirements.
* The user’s private profile is not committed to the public repository.

---

## Epic 9: Job Search and Personal Workflow

### Objective

Allow the user to explore and organize opportunities.

### Scope

* Full-text search.
* Filters.
* Sorting.
* Job details.
* Original application link.
* Save job.
* Ignore job.
* Mark as reviewed.
* Add personal notes.
* Track application status manually.

### Initial Application States

* New
* Reviewed
* Saved
* Applied
* Interviewing
* Rejected
* Offer
* Ignored
* Closed

### Expected Outcome

The platform becomes useful as a daily career tool.

### Acceptance Criteria

* Jobs can be filtered by major normalized fields.
* The user can save and ignore jobs.
* Personal state is preserved between sessions.
* The user can open the original job page.
* Closed or unavailable jobs are clearly identified.

---

## Epic 10: Market Analytics Dashboard

### Objective

Provide a clear view of current Data and AI job market demand.

### Initial Metrics

* Total jobs collected.
* Active jobs.
* New jobs by date.
* Jobs by role family.
* Jobs by seniority.
* Jobs by location.
* Remote versus hybrid versus on-site.
* Most requested skills.
* Most requested cloud platforms.
* Most common skill combinations.
* Companies with the most openings.
* Sources with the highest coverage.
* Average job relevance score.

### Expected Outcome

The user can identify patterns without reading every job description.

### Acceptance Criteria

* Analytics are calculated from normalized canonical jobs.
* Filters affect the displayed metrics.
* Duplicate source postings do not inflate the main job counts.
* Metric definitions are documented.
* Charts remain usable with missing data.

---

## Epic 11: Data Quality and Evaluation

### Objective

Measure the reliability of the collected and enriched data.

### Scope

* Required-field validation.
* Source completeness metrics.
* Duplicate rate.
* Invalid URL rate.
* Missing description rate.
* Enrichment JSON validation rate by provider and version.
* Skill extraction evaluation.
* Seniority classification evaluation.
* Manual review sample.
* Regression test dataset.

### Expected Outcome

The project demonstrates that AI-generated data is evaluated instead of blindly trusted.

### Acceptance Criteria

* A validation report is produced after pipeline execution.
* Common extraction errors are measurable.
* At least 30 manually labeled job postings are used for evaluation.
* Prompt or model changes can be compared against previous results.
* Low-confidence records can be filtered or reviewed.

---

## Epic 12: Pipeline Observability

### Objective

Make ingestion and enrichment failures easy to detect and investigate.

### Scope

* Structured logs.
* Pipeline execution identifier.
* Connector execution status.
* Records collected per source.
* Records rejected.
* Enrichment processing time by provider.
* Enrichment provider failure rate.
* Retry count.
* Pipeline duration.
* Basic operational dashboard or report.

### Expected Outcome

The user can understand what happened during each pipeline execution.

### Acceptance Criteria

* Every pipeline run has a unique identifier.
* Logs identify the source and processing stage.
* Failed records can be traced.
* A run summary is available.
* One connector failure does not hide successful results from other connectors.

---

## Epic 13: Portfolio Presentation

### Objective

Present the project clearly to recruiters, engineers, and hiring managers.

### Scope

* Professional README.
* Architecture diagram.
* Data flow diagram.
* Screenshots or demonstration video.
* Sample dataset.
* Technical decisions.
* Known limitations.
* Hybrid enrichment and provider architecture explanation.
* Evaluation results.
* Setup instructions.
* Future roadmap.

### Expected Outcome

A reviewer can understand the business problem, architecture, technical depth, and results without running the complete application.

### Acceptance Criteria

* The repository contains no personal secrets or private candidate data.
* The project can run with a public sample dataset.
* The README explains the problem before the technology.
* Architecture decisions include trade-offs.
* The demonstration includes real analytics and job recommendations.

---

# 10. Weekend MVP Plan

## Weekend Objective

Deliver a functional vertical slice rather than partially implementing every epic.

The weekend version should demonstrate the complete flow:

```text
Collect jobs
→ store raw data
→ normalize records
→ enrich descriptions deterministically and optionally through a provider
→ calculate basic relevance
→ display searchable results and analytics
```

## Saturday: Data Foundation

### Main Deliverables

* Project initialization.
* Local database.
* Connector interface.
* Greenhouse connector.
* Lever connector.
* One aggregator connector.
* Raw job storage.
* Basic normalized schema.
* First successful ingestion.

## Sunday: Intelligence and Interface

### Main Deliverables

* Local model integration.
* Structured skill extraction.
* Candidate profile configuration.
* Initial matching score.
* Searchable job list.
* Basic analytics dashboard.
* Documentation.
* Demonstration dataset.

## Weekend Scope Restrictions

The weekend version should not include:

* Automatic applications.
* Complex multi-agent architecture.
* Browser automation for many websites.
* Production cloud deployment.
* Advanced semantic search.
* Perfect duplicate detection.
* Real-time ingestion.
* Complete historical analytics.
* Multiple user accounts.
* Paid data providers.
* Complex authentication.

---

# 11. Suggested Technology Direction

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy or another lightweight persistence layer

## Data Processing

* Polars or Pandas
* DuckDB for the initial local version

## Enrichment Providers

* Provider-independent enrichment interface
* Rule-based no-LLM provider
* Optional Ollama adapter for local evaluation
* Future hosted or customer-managed inference adapter
* A separate embedding model when semantic search is introduced

## Frontend

One of the following:

* Streamlit for the fastest MVP.
* React or Next.js for a more professional product interface.
* A minimal server-rendered frontend for reduced complexity.

## Testing

* Pytest
* Connector fixture data
* Prompt regression tests
* Schema validation tests
* Data normalization tests

## Local Infrastructure

* Docker Compose when useful.
* Local database volume.
* Environment-based secrets.
* Optional background worker after the MVP.

## Deployment Evolution

* The current local engine remains the fastest development and personal-use environment.
* A future web application may expose the product through a browser and central API.
* Shared job facts and enrichment results should be processed once and reused across users.
* Candidate profiles, saved jobs, notes, and application state must remain private per user.
* A hosted deployment may replace DuckDB with a server database without changing domain
  contracts or provider interfaces.

---

# 12. Architectural Principles

## Accessible Core

The core product must remain functional without mandatory model inference or paid AI APIs.

Local, hosted, or customer-managed providers may add advanced enrichment, but users of a
future website must not be required to install a model or own a GPU.

## Raw Data Preservation

Never discard the original source data after normalization.

## Source Traceability

Every normalized or enriched field must remain traceable to its source job and original description.

## Deterministic Before Probabilistic

Use deterministic parsing and validation when possible.

Use language models only where ambiguity or unstructured language makes traditional extraction insufficient.

## Explainable Matching

Job recommendations must include reasons, not only numerical scores.

## Incremental Processing

Previously processed jobs should not be repeatedly enriched unless their source content, model, or prompt version changes.

## Replaceable Models

Inference providers and models must be configurable components rather than embedded directly
into business logic.

## Ethical Data Collection

The project should respect public access rules, source limitations, attribution requirements, request limits, and platform terms.

## Privacy by Design

Personal profile information, résumé data, application notes, and credentials must remain outside the public repository.

---

# 13. Non-Goals for the Initial Version

The initial version will not attempt to:

* Replace professional recruiters.
* Guarantee that a user is qualified for a job.
* Automatically submit applications.
* Generate deceptive résumés.
* Scrape authenticated platforms.
* Circumvent anti-bot protections.
* Collect personal information about recruiters.
* Predict salaries when no reliable evidence exists.
* Provide perfect market coverage.
* Treat LLM output as unquestionable truth.
* Support multiple users.
* Operate as a commercial job board.

---

# 14. Risks and Mitigation

## Risk: Incomplete Source Coverage

### Mitigation

Use multiple complementary sources and clearly display coverage limitations.

## Risk: Duplicate Job Postings

### Mitigation

Separate source jobs from canonical jobs and preserve all source relationships.

## Risk: Incorrect LLM Extraction

### Mitigation

Use JSON schema validation, confidence scores, manual evaluation, and deterministic fallback rules.

## Risk: Enrichment Provider Cost or Availability

### Mitigation

Keep inference behind a provider interface, cache shared results, process only changed
descriptions, use deterministic fallback rules, and enforce bounded background workloads.

## Risk: Scraping Instability

### Mitigation

Prioritize APIs and public ATS endpoints before HTML or browser automation.

## Risk: Weekend Scope Expansion

### Mitigation

Prioritize a complete vertical slice and move advanced features into the future roadmap.

## Risk: Public Exposure of Personal Data

### Mitigation

Use local profile files excluded by Git and provide fictional sample profiles publicly.

---

# 15. Future Plans

## Future Epic A: Historical Trend Analysis

### Objective

Transform collected snapshots into time-series market intelligence.

### Potential Features

* Skill demand over time.
* Role growth and decline.
* Technology adoption trends.
* Hiring seasonality.
* Average job lifetime.
* Reopened job detection.
* Company hiring activity timelines.
* Regional comparisons.

---

## Future Epic B: Semantic Search

### Objective

Allow users to search jobs by meaning rather than exact keywords.

### Potential Queries

* “Jobs involving applied statistics and Python.”
* “Azure data roles with limited frontend work.”
* “Machine learning jobs suitable for a Data Engineer.”
* “Roles that value mathematical knowledge.”

### Potential Features

* Local embeddings.
* Vector search.
* Hybrid keyword and semantic retrieval.
* Similar job recommendations.
* Search explanation.

---

## Future Epic C: Advanced Recommendation System

### Objective

Move from simple skill matching to personalized job ranking.

### Potential Features

* Learning-to-rank.
* Feedback from saved, ignored, and applied jobs.
* Candidate preference modeling.
* Skill importance weighting.
* Career transition recommendations.
* Strategic stretch-role detection.
* Application priority score.

---

## Future Epic D: Career Gap Analysis

### Objective

Recommend the most valuable learning priorities based on the job market.

### Potential Features

* Missing skill frequency.
* Skill co-occurrence graphs.
* Skill prerequisites.
* Estimated career impact.
* Learning roadmap generation.
* Portfolio project recommendations.
* Course and documentation mapping.

---

## Future Epic E: Skill Knowledge Graph

### Objective

Model relationships between technologies, responsibilities, roles, and industries.

### Potential Relationships

* Python is commonly required with Spark.
* Databricks frequently appears with Azure.
* Airflow commonly appears in orchestration-focused roles.
* Statistics appears more often in Data Science than Data Engineering.
* Kubernetes appears frequently in MLOps roles.

### Potential Features

* Interactive graph visualization.
* Skill clusters.
* Role transition paths.
* Emerging technology detection.
* Skill neighborhood exploration.

---

## Future Epic F: Salary Intelligence

### Objective

Analyze compensation when reliable salary information is available.

### Potential Features

* Salary normalization by currency and period.
* Salary ranges by role and seniority.
* Remote versus local compensation.
* Geographic comparisons.
* Salary transparency rate.
* Confidence and source quality indicators.

Salary estimates should not be invented when postings do not provide compensation.

---

## Future Epic G: Company Intelligence

### Objective

Create hiring profiles for companies.

### Potential Features

* Historical number of openings.
* Most requested skills.
* Common role families.
* Hiring frequency.
* Remote-work patterns.
* Average posting lifetime.
* Repeated or reopened positions.
* Technology stack indicators.

---

## Future Epic H: Job Change Detection

### Objective

Identify meaningful changes in active job descriptions.

### Potential Features

* Salary changes.
* Requirement changes.
* Remote-policy changes.
* Seniority changes.
* Description edits.
* Application deadline changes.
* Role reopening detection.

---

## Future Epic I: Application Management

### Objective

Support the complete manual application workflow.

### Potential Features

* Application timeline.
* Interview stages.
* Recruiter contacts entered by the user.
* Personal notes.
* Follow-up reminders.
* Résumé version tracking.
* Interview preparation.
* Application conversion analytics.

The system should assist the workflow but not automatically submit applications.

---

## Future Epic J: Résumé and Portfolio Matching

### Objective

Compare specific résumé versions and portfolio projects against job requirements.

### Potential Features

* Résumé parsing.
* Evidence-based skill matching.
* Missing project evidence.
* Suggested résumé emphasis.
* Portfolio relevance analysis.
* Job-specific interview preparation.

The tool should never invent experience that the candidate does not have.

---

## Future Epic K: Local Career Agent

### Objective

Create an agent that can use the platform’s internal tools to perform multi-step career analysis.

### Potential Tools

* Search jobs.
* Compare job requirements.
* Analyze skill trends.
* Inspect candidate profile.
* Generate a learning plan.
* Review saved jobs.
* Produce weekly career reports.

The first version should use one agent with controlled tools before introducing a multi-agent architecture.

---

## Future Epic L: Multi-User Platform

### Objective

Transform the local personal tool into a platform for multiple users.

### Potential Features

* Authentication.
* Independent candidate profiles.
* Private saved jobs.
* Role-based access.
* User-specific recommendations.
* Shared market analytics.
* Secure cloud deployment.

This should only be considered after the personal product demonstrates clear value.

---

## Future Epic M: Broader Professional Domains

### Objective

Expand the platform beyond Data and AI roles.

### Potential Domains

* Backend Engineering
* Cloud Engineering
* DevOps
* Cybersecurity
* Product Analytics
* Software Engineering
* Quantitative Analysis
* Business Intelligence

The domain taxonomy should remain configurable rather than hardcoded.

---

## Future Epic N: Research and Public Datasets

### Objective

Publish privacy-safe and license-compliant market analysis.

### Potential Outputs

* Monthly Data job market reports.
* Open skill frequency datasets.
* Technology trend articles.
* Reproducible notebooks.
* Interactive public dashboards.
* Academic or career research.

Public datasets should contain only information permitted by the original sources.

---

## Future Epic O: Cloud and Scheduled Execution

### Objective

Move from manual local execution to automated incremental processing.

### Potential Features

* Daily scheduled ingestion.
* Background workers.
* Queue-based enrichment.
* Cloud object storage.
* Managed database.
* Incremental model processing.
* Alerting.
* Cost monitoring.
* Deployment pipelines.

The local-first version should remain supported even after a cloud version exists.

---

# 16. Long-Term Product Direction

The long-term vision is not merely to create another job listing interface.

The platform should become a career intelligence system capable of connecting:

```text
Job market demand
→ professional skills
→ candidate profile
→ learning priorities
→ application decisions
→ career outcomes
```

Its central advantage should be the quality and history of its data, not only the presence of a chatbot.

The project should evolve through measured improvements:

1. Reliable collection.
2. Consistent normalization.
3. Accurate enrichment.
4. Explainable matching.
5. Historical intelligence.
6. Personalized recommendations.
7. Broader market research.

Every future feature should strengthen at least one of these layers instead of adding complexity without measurable value.

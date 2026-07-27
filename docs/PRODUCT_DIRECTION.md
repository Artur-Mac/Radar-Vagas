# Product Direction: Accessible Career Intelligence

**Decision date:** 2026-07-27
**Applies from:** Época 6 onward

## Product Positioning

Data Career Radar should evolve from a local job-data pipeline into an accessible career
intelligence product. Its primary value is not listing the largest number of vacancies. It is
helping a person understand:

- which opportunities deserve attention;
- why a job matches their profile;
- which mandatory gaps reduce their chances;
- which skills repeatedly appear in attractive roles;
- which next learning step offers the strongest career return;
- how demand, technologies, and hiring patterns change over time.

The current local workflow remains the development and personal-use foundation. A future
hosted version should be accessible through a website without requiring Python, DuckDB,
Ollama, or a GPU on the user's computer.

## Architectural Direction

```text
Shared job corpus
    -> collection, history, normalization, and deduplication
    -> deterministic enrichment
    -> optional provider inference for unresolved ambiguity
    -> reusable structured market data
    -> private candidate profile
    -> explainable matching, alerts, and career actions
```

Job facts and general enrichment should be computed once and reused. Personalized matching
should primarily use deterministic, inspectable calculations. Provider inference may generate
an explanation on demand, but it should not be required for every user-job pair.

## Supported Product Modes

- **No-LLM mode:** search, filters, history, deterministic extraction, analytics, and basic
  matching remain available.
- **Local development mode:** Ollama can evaluate small models and bounded batches without
  becoming a product requirement.
- **Hosted mode:** a central backend selects and pays for the configured enrichment provider;
  users only need a browser.
- **Customer-managed provider mode:** may be added later for technical or organizational
  deployments, after the main hosted experience is validated.

## Data Ownership Boundary

Shared data:

- source jobs and observations;
- canonical normalization;
- deduplication relationships;
- general enrichment and market analytics.

Private per-user data:

- candidate profile and résumé;
- saved and ignored jobs;
- application states and notes;
- matching preferences and weights;
- alerts and personal recommendations.

This separation must be preserved before a multi-user deployment is introduced.

## Roadmap Consequences

Épocas 1–5 remain unchanged historical milestones. Época 6 becomes evidence-based hybrid
enrichment. Later work should prioritize:

1. reliable enrichment and evaluation;
2. duplicate detection and canonical opportunities;
3. explainable candidate matching;
4. job search and application workflow;
5. market analytics and alerts;
6. hosted API, web interface, accounts, and privacy controls;
7. final product-wide evaluation, accessibility, security, and polish.

Provider cost, commercial licensing, and monetization are future productization concerns.
They should be recorded but should not prevent useful experimentation in the current private
project.

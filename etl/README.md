# AI Tool ETL

This repository discovers AI tools, retrieves official-site content, enriches tool records, builds function and use-case taxonomies, and loads the resulting data into MySQL.

The current production path supports one discovery source: `aitoolsdirectory`. The pipeline is script-oriented; it has no single end-to-end orchestrator.

## Pipeline Overview

```text
configuration/etl_config.yaml
  -> Source Discovery
  -> Candidate filtering
  -> Official-site collection and content filtering
  -> LLM enrichment and quality review
  -> Function and use-case taxonomy mapping
  -> MySQL taxonomy and tool loading
```

```text
candidate_tool_records.json
  -> complete_candidate_tool_records.json
  -> extracted_content.json
  -> filtered_extracted_content.json + garbled_tool_names.txt
  -> enriched_candidate_tool_records.jsonl
  -> enriched_candidate_tool_records.json
  -> enriched_candidate_tool_records_cleaned.json
  -> mapping/output/unique_functions.json + unique_use_cases.json
  -> secondary taxonomy
  -> primary taxonomy
  -> database tables and relationship maps
```

## Repository Layout

```text
configuration/     Runtime configuration and database connection settings.
source_discovery/  Candidate discovery and completeness filtering.
collect/           Official-site retrieval and extracted-content filtering.
enrich/            LLM enrichment, conversion, and quality checks.
mapping/           Taxonomy inputs, generated artifacts, and reusable scripts.
load/              MySQL taxonomy and tool loaders.
outputs/           Inter-stage JSON, JSONL, logs, evaluations, and diagnostics.
experiments/       Non-production experiments.
tests/             Unit tests.
```

`mapping/scripts/archived/` contains superseded scripts and is not part of the current mapping path.

## Configuration

The intended ETL configuration file is `configuration/etl_config.yaml`. It contains the `source_discovery.seed_sources` configuration for `aitoolsdirectory`.

Database credentials are configured in `configuration/aitools-config.ini` in an `[rds]` section. Do not commit credentials.

### Current Configuration Path Limitation

`source_discovery/source_discovery.py` and `enrich/enrich_tools.py` currently resolve `etl_config.yaml` from the ETL root, while the actual configuration file is under `configuration/`. This code-path inconsistency must be aligned before either script can be run from a clean checkout. The configuration location documented here is the intended location.

## Stage 1: Source Discovery

**Responsibility:** discover candidate tools, resolve their official URLs, and retain the source description supplied by the directory API.

**Implementation:** `source_discovery/source_discovery.py`

The active source is `https://aitoolsdirectory.com/`. Its listing page is dynamic, so discovery calls the configured listing API rather than parsing rendered HTML.

For each listed tool the module:

1. Reads the tool name from `table.filtersValues[0].values[].name`.
2. Builds a detail API request by Base64-encoding a `getRowBy.slug` query.
3. Reads `URL-` and `Longdescription-` from the detail response.
4. Follows the third-party redirect in `URL-` with a browser-like User-Agent.
5. Removes query parameters from a successfully resolved final URL.
6. Writes a candidate record and deduplicates records by normalized name.

```json
{
  "name": "...",
  "official_url": "...",
  "source": "aitoolsdirectory",
  "source_url": "https://aitoolsdirectory.com/",
  "source_description": "..."
}
```

Missing or unreliable fields remain `null`; values are never invented. A failed third-party redirect does not stop discovery: `official_url` becomes `null` and the failure is classified as `403` or `other_failure`.

Outputs:

- `outputs/candidate_tool_records.json`
- `outputs/source_discovery_log.txt`
- `outputs/source_discovery_summary.json`

The summary reports `total_tools`, `redirect_success`, `redirect_403`, and `redirect_other_failure`.

`source_discovery/filter_candidate_records.py` retains only records with non-empty `name`, `official_url`, `source`, `source_url`, and `source_description`:

```text
outputs/candidate_tool_records.json
  -> outputs/complete_candidate_tool_records.json
```

## Stage 2: Collect

**Responsibility:** retrieve and filter text from each retained official URL.

`collect/website_content_extractor.py` reads `complete_candidate_tool_records.json`, uses Trafilatura to fetch and extract website content, preserves `name` and `official_url`, and writes:

- `outputs/extracted_content.json`
- `outputs/website_content_extraction_log.txt`

`collect/filter_extracted_content.py` uses `raw_text` when present and otherwise `text`, excludes records without usable text, records source-domain matching, and detects garbled content through replacement-character and unusual Unicode ratios.

It writes:

- `outputs/filtered_extracted_content.json`: records with usable text;
- `outputs/clean_extracted_content.json`: records that also pass the garbling check;
- `outputs/garbled_tool_names.txt`: names excluded by the garbling check.

Enrichment consumes `filtered_extracted_content.json` and excludes names listed in `garbled_tool_names.txt`; `clean_extracted_content.json` is a diagnostic artifact rather than the direct Enrich input.

## Stage 3: Enrich and Review

**Responsibility:** use an LLM to add structured metadata grounded in collected content, then inspect selected quality rules.

`enrich/enrich_tools.py` combines collected content with the original complete candidate record and uses OpenAI structured output with a Pydantic schema. It produces:

```json
{
  "name": "...",
  "official_url": "...",
  "source": "...",
  "source_url": "...",
  "source_description": "...",
  "category": "AI Coding",
  "language": ["English"],
  "use_case": ["..."],
  "function": ["..."],
  "price_type": ["free", "paid"],
  "one_line_desc": "..."
}
```

Rules enforced by the enrichment schema and prompt:

- `category` is one of `AI Video`, `AI Image`, `AI Writing`, `AI Coding`, `AI Chat`, or `AI Audio`.
- `language`, `function`, `use_case`, and `price_type` are non-empty lists.
- `price_type` values are `free`, `free trial`, and/or `paid`; more than one value is allowed.
- `language` contains human natural languages only. English is always present.
- If no pricing evidence is available, `price_type` defaults to `["free"]`.
- LLM-generated values must be grounded in the selected source text.

The enrichment writer appends each successful result to JSONL and records each failure separately, allowing later runs to skip completed tool names:

- `outputs/enriched_candidate_tool_records.jsonl`
- `outputs/enrichment_errors.jsonl`

`enrich/convert_enriched_jsonl_to_json.py` converts JSONL records to `outputs/enriched_candidate_tool_records.json`.

`enrich/evaluate_enriched_records.py` checks language values against `outputs/allowed_human_languages.json` and flags `free trial` values that omit `paid`. Its result is `outputs/enrichment_evaluation.json`.

### Manually Cleaned Enrichment Baseline

`outputs/enriched_candidate_tool_records_cleaned.json` is the downstream input for Mapping and database loading. It is currently a manual correction of the enriched JSON, not an automatically generated stage. The recorded corrections remove programming technologies incorrectly labeled as languages, normalize several language labels to canonical names, and add `paid` to one incomplete price-type record. See `outputs/output_explanation.md` for the recorded detail.

## Stage 4: Taxonomy Mapping

**Responsibility:** build separate hierarchical taxonomies for `functions` and `use_cases`.

```text
raw tags -> secondary tags -> primary tags
```

Functions and use cases remain independent taxonomies. The current production approach uses sentence-transformer embeddings, K-Means clustering, and LLM consolidation. The older semantic-normalization work under `experiments/` is not part of this flow.

### Mapping Flow

1. `extract_tags_from_records.py` extracts and frequency-counts raw `function` and `use_case` values.
2. `count_tag_frequencies.py` writes count distributions for inspection.
3. `cluster_tags.py` embeds tags with `all-MiniLM-L6-v2` and applies K-Means with `random_state=42` and `n_init=10`.
4. `consolidate_clustered_tags.py` uses one of four prompts selected by tag type and target level: functions/use_cases x secondary/primary.
5. `validate_consolidated_tags.py` verifies exactly-once assignment and detects missing, unexpected, duplicate, or cross-pocket conflicting assignments.
6. `deduplicate_primary_tags.py` merges equivalent primary labels across pockets and combines their source secondary tags.
7. `generate_tag_embeddings.py` writes metadata and NumPy embeddings for primary-secondary taxonomy pairs.

Secondary clustering accepts raw records with a `tag` field. Primary clustering reads `secondary_tag` values from consolidated secondary-pocket records.

| Tag type | Target level | Consolidated output |
| --- | --- | --- |
| `functions` | `secondary` | `consolidated_functions_secondary_tags.json` |
| `use_cases` | `secondary` | `consolidated_use_cases_secondary_tags.json` |
| `functions` | `primary` | `consolidated_functions_primary_tags.json` |
| `use_cases` | `primary` | `consolidated_use_cases_primary_tags.json` |

Current artifacts are stored under `mapping/functions/` and `mapping/usecases/`. Secondary experiments may be grouped by `k=<value>`; primary results currently reside directly under the corresponding `primary/` directory.

### Mapping Commands

Run commands from the ETL root. Choose a new output directory for a new run so existing artifacts are not overwritten.

```powershell
# Extract raw tags and count distributions
python mapping/scripts/extract_tags_from_records.py `
  --input outputs/enriched_candidate_tool_records_cleaned.json `
  --output-dir mapping/output

python mapping/scripts/count_tag_frequencies.py `
  --input mapping/output/unique_functions.json mapping/output/unique_use_cases.json `
  --output-dir mapping/output

# Functions: raw tags -> secondary tags
python mapping/scripts/cluster_tags.py `
  --input mapping/output/unique_functions.json `
  --output-dir mapping/functions/secondary/k=300 `
  --k 300 `
  --tag-type functions `
  --target-level secondary

python mapping/scripts/consolidate_clustered_tags.py `
  --input mapping/functions/secondary/k=300/clustered_functions_output_no_vectors.json `
  --output-dir mapping/functions/secondary/k=300`
  --tag-type functions `
  --target-level secondary

python mapping/scripts/validate_consolidated_tags.py `
  --input mapping/functions/secondary/k=300/clustered_functions_output_no_vectors.json `
  --consolidated-input mapping/functions/secondary/k=300/consolidated_functions_secondary_tags.json `
  --tag-type functions `
  --target-level secondary

# Functions: secondary tags -> primary tags
python mapping/scripts/cluster_tags.py `
  --input mapping/functions/secondary/k=300/consolidated_functions_secondary_tags.json `
  --output-dir mapping/functions/primary `
  --k 30 `
  --tag-type functions `
  --target-level primary

python mapping/scripts/consolidate_clustered_tags.py `
  --input mapping/functions/primary/clustered_functions_primary_output_no_vectors.json `
  --output-dir mapping/functions/primary `
  --tag-type functions `
  --target-level primary

python mapping/scripts/deduplicate_primary_tags.py `
  --input mapping/functions/primary/consolidated_functions_primary_tags.json `
  --output mapping/functions/primary/deduplicated_functions_primary_tags.json
```

Use the same commands for use cases with `--tag-type use_cases`, `mapping/output/run-001/unique_use_cases.json`, and `mapping/usecases/` paths.

`sample_clusters_for_evaluation.py` samples a fixed number of pockets using seed `42`. `evaluate_sample_clusters.py` scores CSV samples as `Good`, `Mixed`, or `Bad`; it requires an OpenAI API key. `count_consolidated_tags.py` prints per-pocket and total tag counts.

## Stage 5: Load

Loading writes to MySQL and is not a read-only operation.

`load/load_taxonomy_to_db.py` reads a deduplicated primary taxonomy file and inserts unique `(primary_tag, secondary_tag)` pairs into either `functions` or `use_cases` using `INSERT IGNORE`.

```powershell
python load/load_taxonomy_to_db.py `
  --input mapping/functions/primary/deduplicated_functions_primary_tags.json `
  --tag-type functions
```

`load/load_tools_to_db.py` loads tools and their sources, price types, languages, function mappings, and use-case mappings. It requires the cleaned enriched records plus both taxonomy levels for both tag types. The script uses a transaction and rolls back the current run on error.

```powershell
python load/load_tools_to_db.py `
  --tools-input outputs/enriched_candidate_tool_records_cleaned.json `
  --functions-secondary-input mapping/functions/secondary/k=300/consolidated_functions_secondary_tags.json `
  --use-cases-secondary-input mapping/usecases/secondary/consolidated_use_cases_secondary_tags.json `
  --functions-primary-input mapping/functions/primary/deduplicated_functions_primary_tags.json `
  --use-cases-primary-input mapping/usecases/primary/deduplicated_use_cases_primary_tags.json
```

## Operational Notes and Current Limits

- Source Discovery processes the first configured listing page only.
- Discovery has one source-specific implementation and no fallback discovery source.
- Collection, enrichment, and several review utilities use fixed `outputs/` paths rather than a run-specific CLI contract.
- There is no top-level orchestrator, global run ID, or consolidated ETL report.
- Mapping evaluation and consolidation call OpenAI; database loaders write to MySQL. Review inputs and credentials before running either.
- `experiments/` and archived scripts are retained for investigation and are not authoritative production artifacts.

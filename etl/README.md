# 1. ETL framework

0. Source Discovery
1. Collect
2. Extract & Normalize
3. Review
4. Validate
5. Load
6. Report

# 2. Responsibility, input and output

## 2.0 Source Discovery

**Responsibility:** Find potential AI tool candidates and their official URLs.

**Input:** Seed sources + source-specific discovery rules

**Output:** Candidate tool records

### 2.0.1 Seed Sources

#### Active

- https://aitoolsdirectory.com/

#### To Be Evaluated
- https://tooldirectory.ai/
- https://tooldirectory.ai/research
- https://tooldirectory.ai/top-100-ai-tools
- https://theaidirectory.ai/en
- https://www.aitools-directory.com/
- https://aitools.inc/
- https://beginnersinai.org/ai-tools-directory/
- https://www.toolify.ai/
- https://opentools.ai/
- https://toollist.ai/
- https://aitoptools.com/
- https://www.insidr.ai/ai-tools/
- https://www.futurepedia.io/
- https://aichief.com/ai-tools/


### 2.0.2 Source-Specific Discovery Rules

#### 2.0.2.1 Source: AI Tools Directory

**Base URL**

https://aitoolsdirectory.com/

**Pagination**

Listing pages follow:

https://aitoolsdirectory.com/?page={page_number}


#### 2.0.2.2 Discover tool detail pages

For each listing page, identify tool entries.

Observed tool-name element:

<h3 class="sv-tile__title sv-text-reset sv-is-link">
    Getsolved
</h3>

Extract and trim the tool name.

Tool detail pages follow the observed pattern:

https://aitoolsdirectory.com/tool/{tool_slug}

Examples:

AIWriter
→ https://aitoolsdirectory.com/tool/aiwriter

Mistral AI
→ https://aitoolsdirectory.com/tool/mistral-ai

Getsolved
→ https://aitoolsdirectory.com/tool/getsolved

If the listing page exposes the actual tool-detail href, prefer extracting that href directly instead of reconstructing it from the tool name.

Otherwise, the initial fallback slug rule is:

1. lowercase the tool name
2. replace spaces with "-"

Do not assume this fallback works for every tool name.


#### 2.0.2.3 Discover official URL

Visit each tool detail page.

Find the external URL associated with the "Try it" action.

Observed examples:

https://aitoolsdirectory.com/tool/lynote
→ https://lynote.ai/?utm_source=aitoolsdirectory

https://aitoolsdirectory.com/tool/getsolved
→ https://getsolved.ai/?utm_source=aitoolsdirectory

Normalize the destination URL before storing it as `official_url`.

Normalization rule:
- Remove the entire query string from the destination URL, including all tracking parameters appended after `?`.
- Preserve the URL scheme, domain, and path.
- Do not retain any query parameters.

Examples:

https://getsolved.ai/?utm_source=aitoolsdirectory
→ https://getsolved.ai/

The normalized destination becomes `official_url`.


#### 2.0.2.4 Collect source fields

For each discovered tool, collect the source data needed for:

- name
- official_url
- source
- source_url
- source_description

For this source:

source = "aitoolsdirectory"
source_url = "https://aitoolsdirectory.com/"

source_description: Extract all descriptive text from the tool detail page’s main content section, starting from the first descriptive paragraph and continuing through the end of the Key Features section. Exclude navigation, metadata/badges, footer content, related tools, alternatives, and any content that requires following additional links.

HTML extraction rule:
- Primary container:
  `.sv-product-page__string.sv-product-string.sv-text-reset`
- Extract text from the container in DOM order.
- Include:
  - `<p>` descriptive paragraphs
  - section headings (`<h2>`, `<h3>`, etc.)
  - list items (`<li>`)
- Preserve the original content order.
- For this source, the final included section may be labeled
  `Bullet Point Features`; include its entire following `<ul>`.
- Do not extract content outside the primary container.
- Do not follow links.

Exclude:
- navigation
- metadata / badges
- footer
- related tools
- alternatives

If a field cannot be reliably obtained from the source page, leave it null.
Do not invent missing values during scraping.


#### 2.0.2.5 Produce candidate record

Each discovered tool should produce a structured candidate record containing:

{
  "name": "...",
  "official_url": "...",
  "source": "aitoolsdirectory",
  "source_url": "https://aitoolsdirectory.com/",
  "source_description": "..."
}

#### 2.0.2.6 Deduplicate candidate records
- Within a single source discovery run, candidate records with the same normalized name should be treated as duplicates.
- Emit only one candidate record per unique normalized tool name.
- Name normalization for deduplication should trim leading/trailing whitespace and collapse internal repeated whitespace.
- Do not perform cross-source deduplication in this stage.

### 2.0.3 Observed Examples

#### 2.0.3.1 Ai Tools Directory
These examples were used to derive the current discovery rules:

- https://aitoolsdirectory.com/tool/lynote
  → https://lynote.ai/?utm_source=aitoolsdirectory

- https://aitoolsdirectory.com/tool/getsolved
  → https://getsolved.ai/?utm_source=aitoolsdirectory

- https://aitoolsdirectory.com/tool/dropmagic

These are observations, not hard-coded crawler inputs.



## 2.1 Collect

**Responsibility:** Retrieve raw web pages / raw source data

**Input:** Source URLs

**Output:** Raw source data

## 2.2 Enrich & Normalize

**Responsibility:**

* Extract standardized fields
* Normalize field formats
* Generate function / use case candidates

**Input:** Raw source data

**Output:** Structured candidate records

Each raw datum should produce a structured candidate record containing:
- category
- language
- use_case
- function
- price_type
- one_line_desc

Merge these fields into the original record; the output should look as below:

{
  "name": "...",
  "official_url": "...",
  "source": "aitoolsdirectory",
  "source_url": "https://aitoolsdirectory.com/",
  "source_description": "...",
  "category": "...",
  "language": "...",
  "use_case": "...",
  "function": "...",
  "price_type": "...",
  "one_line_desc": "..."
}

## 2.3 Review

**Responsibility:** Manually review, modify, and approve candidate records

**Input:** Structured candidate records

**Output:** Reviewed records

## 2.4 Validate

**Responsibility:**

* Validate required fields
* Validate function / use case values
* Check for duplicates and constraint violations
* Determine whether each record is eligible to be loaded into the database

**Input:** Reviewed records

**Output:** Valid records + rejected records

This stage performs validation-time duplicate checks beyond the in-source deduplication already done during Source Discovery

## 2.5 Load

**Responsibility:** Write data into the `tools`, `function`, `use_case`, and mapping tables

**Input:** Valid records

**Output:** Database write results

## 2.6 Report

**Responsibility:** Summarize added, failed, skipped, and errored records

**Input:** Execution results from all stages of the current ETL run

**Output:** ETL run report

# 3 Data Flow

AI Tools Directory
        ↓
Discovery / Collection
        ↓
name
official_url
source
source_url
source_description
        ↓
Fetch official website
        ↓
official_raw_text
        ↓
LLM enrichment
        ↓
category
language
use_case
function
price_type
one_line_desc

# 4 Implementation

## 4.1 Source Discovery

### 4.1.1 Purpose

Implement Source Discovery as a standalone stage that discovers candidate AI tools from configured external sources.

The module:

- accepts YAML-configured `seed_sources` and `source_specific_discovery_rules`
- validates configuration using Pydantic models
- retrieves the required source listing and detail pages
- extracts source-level candidate data
- returns `candidate_tool_records`

Source Discovery only retrieves the source pages required to discover candidate tools, official URLs, and source descriptions.

It does not fetch or analyze content from the tools' official websites.


### 4.1.2 Scope of this increment

This increment supports only the `aitoolsdirectory` source.

For this increment:

- each active source processes exactly one configured listing page
- the listing-page count remains configurable rather than embedding page-1 logic directly in parsing code
- pagination beyond the configured first page is not implemented
- official website content is not fetched
- no fallback extraction strategies are implemented except the documented name-to-slug rule for detail-page URL construction

The implementation should remain extensible so additional sources and pagination behavior can be added later without restructuring the Source Discovery module.


### 4.1.3 Execution flow

Source Discovery follows this pipeline:

YAML configuration

→ Pydantic validation

→ Load the configured listing page for each active source

→ Extract tool name + detail page URL

→ Visit each tool detail page

→ Extract `official_url` + `source_description`

→ Build `candidate_tool_records`

→ Deduplicate records by normalized `name`

→ Persist results to JSON


### 4.1.4 Configuration and schema

#### 4.1.4.1 Configuration

Discovery inputs are stored in `source_discovery.yaml`.

The configuration contains:

- `seed_sources`
- `source_specific_discovery_rules`

The YAML configuration must be parsed and validated with Pydantic before discovery begins.

For this increment, the configuration contains one active source definition for `aitoolsdirectory`.

Source-specific discovery rules should remain outside crawler logic so additional sources can be added later without rewriting the module.

#### 4.1.4.2 Schemas

`schemas.py` defines the data structures used by Source Discovery:

- `SeedSource`
- `SourceDiscoveryRule`
- `CandidateToolRecord`

These schemas define the explicit input and output contracts of the stage.

If a candidate tool is successfully discovered but a field cannot be reliably extracted, the field must be `null`.

No field value may be invented during scraping.


### 4.1.5 Files

This increment contains three files:

#### 4.1.5.1 `source_discovery.py`

Responsibility: implement and orchestrate Source Discovery.

Public entrypoint:

`discover_sources(seed_sources, source_specific_discovery_rules) -> list[CandidateToolRecord]`

Internal responsibilities:

- iterate configured seed sources
- apply the matching source-specific discovery rules
- retrieve configured listing pages
- discover tool detail pages
- extract official URLs and source descriptions
- build candidate records
- deduplicate the final records

Expected functions:

- `discover_sources(...)`
  - top-level orchestration
  - returns all candidate records

- `discover_from_source(seed_source, rule)`
  - runs discovery for one source

- `get_listing_page_urls(...)`
  - determines which configured listing pages should be processed

- `extract_tool_links(...)`
  - extracts tool names and corresponding detail-page URLs
  - prefers actual `href` values when available

- `extract_official_url(detail_page)`
  - locates the "Try it" destination URL
  - applies the documented URL normalization rules

- `extract_source_description(detail_page)`
  - extracts the configured main description content according to the source-specific extraction rule

- `build_candidate_record(...)`
  - assembles a `CandidateToolRecord`
  - uses `null` for missing or unreliable fields


#### 4.1.5.2 `schemas.py`

Responsibility: define the Source Discovery configuration and output data structures.

Contains:

- `SeedSource`
- `SourceDiscoveryRule`
- `CandidateToolRecord`


#### 4.1.5.3 `source_discovery.yaml`

Responsibility: define seed sources and source-specific discovery rules.

For this increment, it contains the configuration for `aitoolsdirectory` only.


### 4.1.6 Deduplication

Deduplication occurs within a single Source Discovery run.

Rules:

- normalize the tool name before comparison
- emit only one record for each unique normalized tool name
- do not perform cross-source deduplication at this stage


### 4.1.7 Output contract

Source Discovery returns:

`list[CandidateToolRecord]`

Each discovered tool produces one candidate record.

Requirements:

- missing or unreliable fields must be `null`
- scraped values must come from the configured source; values must not be invented
- records must be deduplicated by normalized tool name before final output
- the final result must also be persisted as a human-readable JSON file for inspection and use by the next pipeline stage



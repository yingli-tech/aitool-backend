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

**Input:** Seed sources

**Output:** Candidate tool records

### 2.0.1 Seed Sources

#### Active

- https://aitoolsdirectory.com/

#### To Be Evaluated

At the moment, this is not a near-term priority.

The current `aitoolsdirectory` source already yields 600+ candidate tools, which is sufficient for the current increment and near-term ETL needs.

Additional discovery sources may be evaluated later, but they are not needed right now.

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


### 2.0.2 Source-Specific Discovery Logic

#### 2.0.2.1 Source: AI Tools Directory

**Base URL**

https://aitoolsdirectory.com/

**Corresponding API**

https://spread.name/sheet/Ch-JZHaS1Jr33yDMpDzHjQD1JJAP5FHRF3LI221VGFm-12MzaYevvfCflDPkrrRlLppo/filters/?query=e30%3D&options=eyJyb3dzTGltaXQiOjUwMDAsImRlYWxUeXBlIjoiYXBwc3VtbyIsImR5bmFtaWNEYXRhIjp7InNoZWV0SGFzaCI6IjE4MDM3NTYzODciLCJTQ1BUYWJsZUxhdGVzdFVwZGF0ZVRpbWVzdGFtcCI6MTc4Nzk5ODI5MDUwOH0sInNlYXJjaCI6eyJlbmFibGVkIjp0cnVlLCJjb2x1bW5zIjpbIk5hbWUtIiwiUHJpY2UtIiwiQ2F0ZWdvcnktIiwiSGFzaHRhZy0iLCJMb25nZGVzY3JpcHRpb24tIl19LCJzb3J0aW5nIjp7ImVuYWJsZWQiOmZhbHNlLCJzaHVmZmxlIjpmYWxzZX0sInBhZ2luYXRpb24iOnsiZW5hYmxlZCI6dHJ1ZSwiaXRlbXNQZXJQYWdlIjoiMTAwIn0sImZpbHRlcnMiOnsiZW5hYmxlZCI6dHJ1ZSwidmFsdWVzIjpbeyJpZCI6Ik5hbWUtIiwidHlwZSI6Im11bHRpcGxlIn0seyJpZCI6IkNhdGVnb3J5LSIsInR5cGUiOiJtdWx0aXBsZSJ9LHsiaWQiOiJQcmljZS0iLCJ0eXBlIjoibXVsdGlwbGUifV19LCJtYXBWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJpZCI6bnVsbCwibWFya2VyVHlwZSI6InBpbiIsImltYWdlQ29sSWQiOiIifSwiY2FsZW5kYXJWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJzdGFydERhdGVDb2xJZCI6bnVsbCwidGl0bGVDb2xJZCI6Ik5hbWUtIn19

This is a dynamic website.

#### 2.0.2.2 Discover tools

AI Tools Directory loads its tool data dynamically rather than embedding the tool records directly in the initial HTML response.

Therefore, Source Discovery does not extract tool entries from the rendered listing-page DOM.

Instead:

1. Call the discovered listing data API.
2. Parse the returned JSON response.
3. Extract the available tool names.
4. Normalize each extracted name by trimming leading and trailing whitespace.


#### 2.0.2.3 Resolve tool detail data

For each discovered tool, retrieve its corresponding detail record through the
site's underlying detail data API.

The detail API request contains a Base64-encoded `query` parameter representing
a JSON structure of the form:

{
  "getRowBy": {
    "slug": "<tool_slug>"
  }
}

Construct the query dynamically for each tool:

1. determine the tool slug;
2. construct the `getRowBy` JSON object;
3. serialize the object to JSON;
4. Base64-encode the serialized JSON;
5. send the encoded value as the API's `query` parameter;
6. parse the returned JSON detail record.

Observed example:

{
  "getRowBy": {
    "slug": "getsolved"
  }
}

The request configuration contained in the API's `options` parameter should
remain unchanged unless further investigation shows that dynamic construction
is required.

If the detail record cannot be reliably retrieved, do not invent missing data.


#### 2.0.2.4 Collect source fields

For each tool detail record, collect the source data needed for:

- name
- official_url
- source
- source_url
- source_description

For this source:

source = "aitoolsdirectory"

source_url = "https://aitoolsdirectory.com/"

`official_url`:

- Extract the external destination URL from the `URL-` field in the detail API response.
- Treat this URL as a third-party destination that may redirect rather than assuming it is already the final official URL.
- Request the extracted URL and follow HTTP redirects.
- Use the final resolved URL as the candidate official URL.
- Normalize the resolved URL by removing the entire query string while preserving the scheme, domain, and path.
- If the destination cannot be successfully resolved, leave `official_url` null.

Example:

Detail API `URL-` value:

https://example-redirect.com/...

→ follow redirects

→ final resolved URL:

https://getsolved.ai/?utm_source=aitoolsdirectory

→ normalize

→ official_url:

https://getsolved.ai/

`source_description`:
- Extract the descriptive content directly from the detail API response.
- Preserve the relevant descriptive text returned by the source.

If a required field cannot be reliably obtained from the API response, leave it null.

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

- Within a single source discovery run, candidate records with the same
  normalized name should be treated as duplicates.
- Emit only one candidate record per unique normalized tool name.
- Name normalization for deduplication should trim leading/trailing whitespace
  and collapse internal repeated whitespace.
- Do not perform cross-source deduplication in this stage.


### 2.0.3 Observed Examples

Null


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

- accepts YAML-configured `seed_sources` 
- validates configuration using Pydantic models
- retrieves the required source listing API, detail API, and third-party redirect targets
- extracts source-level candidate data
- returns `candidate_tool_records`

Source Discovery only retrieves the source/API data required to discover candidate tools, official URLs, and source descriptions.

It does not fetch or analyze content from the tools' official websites.


### 4.1.2 Scope of this increment

This increment supports only the `aitoolsdirectory` source.

For this increment:

- each active source processes exactly one configured listing page
- official website content is not fetched
- source-specific discovery logic is embedded in code rather than stored as external source-specific rule objects
- no additional discovery sources are needed at this time because `aitoolsdirectory` already provides 600+ tools for this stage


### 4.1.3 Execution flow

Source Discovery follows this pipeline:

YAML configuration

→ Pydantic validation

→ Load the configured listing API for each active source

→ Extract tool name  

→ Build tool detail API request

→ Call tool detail API

→ Extract redirect URL and `source_description` from the detail API response

→ Follow the redirect URL to resolve the final `official_url`

→ Build `candidate_tool_records`

→ Deduplicate records by normalized `name`

→ Persist results, summary, and logs


### 4.1.4 Configuration and schema

#### 4.1.4.1 Configuration

Discovery inputs are stored in `source_discovery.yaml`.

The configuration contains:

- `seed_sources`

The YAML configuration must be parsed and validated with Pydantic before discovery begins.

For this increment, the configuration contains one active source definition for `aitoolsdirectory`.


#### 4.1.4.2 Schemas

`schemas.py` defines the data structures and serialization contract used by Source Discovery:

- `SeedSource` — defines a configured discovery source and its listing pages.
- `CandidateToolRecord` — defines the output schema for each discovered tool.
- `SourceDiscoveryConfig` — defines the top-level Source Discovery configuration containing the seed sources.
- `UrlResolutionSummary` — records summary statistics for official URL resolution, including successful resolutions, `403` responses, and other failures.
- `dump_candidate_records()` — converts validated `CandidateToolRecord` objects into JSON-serializable dictionaries for persistence.

All Pydantic models use `extra="forbid"` to reject fields that are not explicitly defined in their schemas.

If a candidate tool is discovered but a field cannot be reliably extracted, the field must be `null`.

No field value may be invented during discovery.


### 4.1.5 Files

This increment contains three files:

#### 4.1.5.1 `source_discovery.py`

Responsibility: implement and orchestrate Source Discovery.

Public entrypoint:

`discover_sources(seed_sources) -> list[CandidateToolRecord]`

Internal responsibilities:

- iterate configured seed sources
- retrieve configured listing pages
- build and call tool detail APIs
- extract official URLs and source descriptions
- build candidate records
- deduplicate the final records
- persist candidate records, resolution summary, and run logs

Expected functions:

- `discover_sources(...)`
  - top-level orchestration
  - returns all candidate records

- `discover_from_source(seed_source)`
  - runs discovery for one source

- `get_listing_page_urls(...)`
  - determines which configured listing pages should be processed

- `extract_tool_names(...)`
  - extracts tool names from the listing API response

- `build_detail_request(...)`
  - builds the detail API request for a tool using its derived slug and the listing API `options` value

- `extract_official_url(detail_response)`
  - extracts the redirect target from the detail API response
  - follows redirects and applies the documented URL normalization rules

- `extract_source_description(detail_response)`
  - extracts the description directly from the detail API response

- `resolve_final_url(...)`
  - follows the third-party redirect URL
  - returns the resolved final URL when successful
  - catches third-party URL resolution failures so one bad tool URL does not stop the full discovery run

- `configure_logging(...)`
  - configures console and file logging for the discovery run

- `persist_summary(...)`
  - writes the URL-resolution summary JSON document

- `build_candidate_record(...)`
  - assembles a `CandidateToolRecord`
  - uses `null` for missing or unreliable fields

- `load_config(...)`
  - loads the Source Discovery configuration from YAML
  - validates the configuration against `SourceDiscoveryConfig`

- `fetch_json(...)`
  - sends an HTTP GET request to the specified API endpoint
  - validates the HTTP response status
  - returns the response body as JSON

- `deduplicate_records(...)`
  - removes duplicate candidate records based on normalized tool names
  - preserves the first occurrence of each tool

- `persist_results(...)`
  - serializes candidate records into JSON-compatible dictionaries
  - writes the final candidate records to the configured output JSON file

- `main()`
  - configures logging and loads the Source Discovery configuration
  - runs the Source Discovery pipeline


#### 4.1.5.2 `schemas.py`

Responsibility: define the Source Discovery configuration and output data structures.

Contains:

- `SeedSource`
- `CandidateToolRecord`
- `SourceDiscoveryConfig`
- `UrlResolutionSummary`
- `dump_candidate_records`


#### 4.1.5.3 `source_discovery.yaml`

Responsibility: define seed sources.

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

### 4.1.8 Detail API field contract

For the current `aitoolsdirectory` implementation, Source Discovery depends on the following response fields:

- listing API tool names:
  - `table.filtersValues[0].values[].name`
- detail API redirect URL:
  - `table.rows[0].cells["URL-"].value`
- detail API source description:
  - `table.rows[0].cells["Longdescription-"].value`

If these fields are missing or malformed, the implementation must not invent replacement values.

### 4.1.9 Third-party URL resolution error handling

The redirect URL extracted from the detail API is treated as a third-party URL resolution step.

Rules:

- a single tool's redirect failure must not stop the full Source Discovery run
- if redirect resolution fails, continue processing the next tool
- if redirect resolution fails, set `official_url` to `null`
- classify redirect outcomes into:
  - success
  - `403`
  - other failure
- for non-`403` failures, preserve the current handling behavior while logging the returned status code and error details when available

### 4.1.11 Failure Modes and Handling

Source Discovery handles failures at the individual tool level where possible so that one failed official URL does not terminate the full discovery run.

- **Missing redirect URL**
  - The detail API response does not contain a usable `URL-` value.
  - `official_url` is set to `null`.
  - The failure is counted as `other_failure`.

- **HTTP 403 during URL resolution**
  - The redirect URL exists, but the target website returns HTTP 403 when requested.
  - `official_url` is set to `null`.
  - The failure is classified and counted as `403`.
  - Discovery continues with the remaining tools.

- **Other HTTP errors during URL resolution**
  - The target website returns another unsuccessful HTTP status.
  - `official_url` is set to `null`.
  - The failure is classified and counted as `other_failure`.
  - Discovery continues with the remaining tools.

- **Network, connection, or SSL failure**
  - The redirect URL cannot be resolved because of a request-level failure.
  - `official_url` is set to `null`.
  - The failure is classified and counted as `other_failure`.
  - Discovery continues with the remaining tools.

- **Missing source description**
  - The detail API response does not contain a usable `Longdescription-` value.
  - `source_description` is set to `null`.
  - No value is invented or inferred.

- **Missing tool name**
  - A listing record does not contain a usable tool name.
  - Detail retrieval is skipped because the detail request cannot be constructed reliably.
  - The candidate record is retained with unavailable fields set to `null`.
  - The failure is counted as `other_failure`.

Incomplete candidate records may remain in the Source Discovery output. Records with required fields set to `null` can be excluded before downstream enrichment and normalization.

### 4.1.10 Logging and summary outputs

Source Discovery should produce observable run outputs in addition to `candidate_tool_records`.

Logging:

- print progress messages during execution so the operator can see what the stage is currently doing
- write the same progress information to:
  - `outputs/source_discovery_log.txt`

Typical log events include:

- fetching the tool list
- fetching a specific tool
- resolving a tool's `official_url`
- extracting a tool's `source_description`
- logging redirect-resolution failures with status code and error details when available

Summary:

- persist URL-resolution summary statistics to:
  - `outputs/source_discovery_summary.json`

The summary should include:

- `total_tools`
- `redirect_success`
- `redirect_403`
- `redirect_other_failure`



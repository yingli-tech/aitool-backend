# AI Tool Recommendation Backend

## Overview

This project is a backend service for an AI tool recommendation system.

It helps users find suitable AI tools by converting natural language queries into structured tags, retrieving matching tools from a curated database, and ranking them with a rule-based scoring system.

Instead of relying on LLMs to directly recommend tools, this system separates:
- **LLM for query understanding**
- **Structured system for retrieval and ranking**

This improves controllability, stability, and explainability.

---

## Problem

AI tools are highly fragmented across the internet. Users face two main challenges:

- High search cost (tools are scattered across websites)
- High decision cost (hard to find tools that match specific needs)

Pure LLM-based recommendations are:
- unstable
- hard to control
- prone to hallucination

This project addresses these issues using a **tag-driven recommendation pipeline**.

---

## Architecture

Frontend:
- React + Vercel

Backend:
- AWS API Gateway
- AWS Lambda (Python)
- MySQL (RDS)

Pipeline:
flowchart TD
    classDef node fill:#232427,stroke:#8C7A5B,color:#F3EFE6,stroke-width:1.2px
    classDef decision fill:#2A2A2D,stroke:#B89A63,color:#F3EFE6,stroke-width:1.4px

    A["User Query"] --> B["LLM Parsing<br/>(query -> structured tags)"]
    B --> C["Validation + Normalization"]
    C --> D["Strict Retrieval<br/>(must-have filtering)"]

    D --> E{"Strict result empty?"}
    class E decision

    E -->|Yes| F["Fallback Retrieval<br/>(constraint relaxation)"]
    E -->|No| G["Skip fallback<br/>→ Continue"]

    F --> H["Scoring + Ranking"]
    G --> H

    H --> I["Fetch Tool Details"]
    I --> J["JSON Response"]

    class A,B,C,D,F,G,H,I,J node

    %% Edge line color (gold gray)
    linkStyle 0 stroke:#6F624D,stroke-width:1.4px
    linkStyle 1 stroke:#6F624D,stroke-width:1.4px
    linkStyle 2 stroke:#6F624D,stroke-width:1.4px
    linkStyle 3 stroke:#A88D5C,stroke-width:1.5px
    linkStyle 4 stroke:#A88D5C,stroke-width:1.5px
    linkStyle 5 stroke:#6F624D,stroke-width:1.4px
    linkStyle 6 stroke:#6F624D,stroke-width:1.4px
    linkStyle 7 stroke:#6F624D,stroke-width:1.4px


---

## Backend Modules

- `handler.py`  
  API entry point and orchestration

- `datatier.py`  
  Database access layer (MySQL)

- `parser.py`  
  Prompt construction, LLM call, validation, normalization

- `retriever.py`  
  Filtering, scoring, ranking, fallback logic

- `response.py`  
  Response formatting and logging

---

## Database Design

The database is designed to reduce redundancy and support flexible querying.

Key design principles:
- Many-to-many relationships are decomposed into junction tables
- Core entities are normalized for scalability

Main tables:
- `tools`
- `functions`
- `use_cases`
- `price_types`
- `sources`

Mapping tables:
- `tool_function_map`
- `tool_usecase_map`
- `tool_price_map`
- `tool_source_map`

---

## Recommendation Logic

### Filtering (must-have)
- category
- price_type
- language
- use_cases

### Scoring
score = 3 × matched_use_case_count + 2 × matched_function_count + matched_nice_to_have_count


### Tie-break
1. matched_use_case_count
2. matched_function_count
3. tool name / id

### Fallback Strategy

If no result:
- keep category
- keep primary use case
- relax language or price_type

---

## API

### POST /aitool

Request:

```bash
json
{
  "query": "free chinese podcast editing tool"
}
```
Response:

```bash
json
{
  "query": "...",
  "parsed_query": {...},
  "fallback_used": false,
  "result_count": 3,
  "results": [
    {
      "rank": 1,
      "tool_id": 3,
      "name": "Tool A",
      "score": 8
    }
  ]
}
```

## Run Locally

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
endpoint=...
dbname=...
username=...
pwd=...
OPENAI_API_KEY=...
openai_model=...
```

### 3. Run Lambda handler locally or test via API Gateway

## Design Decision

### Instead of using LLMs for direct recommendation, this project separates:
- LLM → semantic understanding
- system → decision making

### Reasons:

- improves stability
- avoids hallucination
- ensures recommendations are based on real tools
- easier to debug through CloudWatch

## Future Improvements
- improve taxonomy (reduce ambiguity)
- optimize ranking (learned weights)
- introduce embeddings for semantic matching
- collect user feedback for evaluation
- build evaluation pipeline for recommendation quality

## Notes

This project represents a cold-start recommendation system, where no user interaction data is available.
The system relies on structured data + rule-based ranking for the first version.

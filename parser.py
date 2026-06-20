import json
import re


###############################################################
# build_parsing_prompt
#
# Builds the prompt for the LLM to parse the user's query into
# a structured JSON object with core/sub taxonomy tags.
#
def build_parsing_prompt(query, taxonomy_context):
  """
  Builds the prompt sent to the LLM for structured query parsing.

  Parameters
  ----------
  query : user input query (string)
  taxonomy_context : dict containing:
      {
        "categories": [...],
        "price_types": [...],
        "languages": [...],
        "use_cases": [{"core": "...", "sub": "..."}, ...],
        "functions": [{"core": "...", "sub": "..."}, ...]
      }

  Returns
  -------
  prompt string
  """

  try:
    categories = taxonomy_context.get("categories", [])
    price_types = taxonomy_context.get("price_types", [])
    languages = taxonomy_context.get("languages", [])
    use_cases = taxonomy_context.get("use_cases", [])
    functions = taxonomy_context.get("functions", [])

    prompt = f"""
You are a query parser for an AI tool recommendation system.

Your job is to convert the user's query into a structured JSON object.

You must follow these rules carefully:

1. Infer the best category from the provided category list.
2. Extract must-have constraints for:
   - price_type
   - language
   - use_cases
3. Extract nice-to-have use_cases if present.
4. Extract function tags from the provided function taxonomy whenever possible.
5. Use the provided database taxonomy as the first-choice source of truth.
6. For use_cases and functions, return objects with:
   - core: required string
   - sub: string or null
7. Prefer existing core/sub combinations from the taxonomy.
8. Only generate a new core or sub label when the existing taxonomy truly cannot express the meaning.
9. Multiple use_cases and multiple functions are allowed when the query contains multiple intents.
10. If you are only confident about the core but not the sub, set sub to null.
11. Return JSON only. Do not include explanation, markdown, or extra text.

Important rule for price_type:
- If the user does NOT mention price preference, then include all available price types in must_have.price_type.
- In this case, do not treat price as a restrictive preference.

JSON schema:
{{
  "category": "string",
  "must_have": {{
    "price_type": ["string", "..."],
    "language": ["string", "..."],
    "use_cases": [
      {{"core": "string", "sub": "string or null"}}
    ]
  }},
  "nice_to_have": {{
    "use_cases": [
      {{"core": "string", "sub": "string or null"}}
    ]
  }},
  "functions": [
    {{"core": "string", "sub": "string or null"}}
  ]
}}

Available categories:
{json.dumps(categories, ensure_ascii=False)}

Available price_types:
{json.dumps(price_types, ensure_ascii=False)}

Available languages:
{json.dumps(languages, ensure_ascii=False)}

Available use_case taxonomy:
{json.dumps(use_cases, ensure_ascii=False)}

Available function taxonomy:
{json.dumps(functions, ensure_ascii=False)}

User query:
{query}
"""
    return prompt

  except Exception as err:
    print("parser.build_parsing_prompt() failed:")
    print(str(err))
    raise


###############################################################
# parse_query_with_llm
#
# Calls the LLM API and parses the returned JSON.
#
def parse_query_with_llm(prompt, client=None, model=None):
  """
  Calls the LLM and parses the response into a Python dict.
  """

  try:
    if client is None:
      raise ValueError("LLM client is required")

    if model is None:
      raise ValueError("Model name is required")

    response = client.chat.completions.create(
      model=model,
      messages=[
        {"role": "system", "content": "You are a precise JSON generator."},
        {"role": "user", "content": prompt}
      ],
      temperature=0
    )

    content = response.choices[0].message.content.strip()
    content = _strip_code_fences(content)

    parsed = json.loads(content)
    return parsed

  except Exception as err:
    print("parser.parse_query_with_llm() failed:")
    print(str(err))
    raise


###############################################################
# validate_llm_output
#
# Validates that the LLM output follows the required JSON schema.
#
def validate_llm_output(parsed):
  """
  Validates LLM output schema.
  """

  try:
    if not isinstance(parsed, dict):
      raise ValueError("LLM output must be a dictionary")

    if "category" not in parsed:
      raise ValueError("Missing 'category' in LLM output")
    if not isinstance(parsed["category"], str):
      raise ValueError("'category' must be a string")

    if "must_have" not in parsed:
      raise ValueError("Missing 'must_have' in LLM output")
    if not isinstance(parsed["must_have"], dict):
      raise ValueError("'must_have' must be a dictionary")

    must_have = parsed["must_have"]
    for field in ["price_type", "language", "use_cases"]:
      if field not in must_have:
        raise ValueError(f"Missing 'must_have.{field}' in LLM output")
      if not isinstance(must_have[field], list):
        raise ValueError(f"'must_have.{field}' must be a list")

    for field in ["price_type", "language"]:
      for item in must_have[field]:
        if not isinstance(item, str):
          raise ValueError(f"All items in 'must_have.{field}' must be strings")

    _validate_tag_list(must_have["use_cases"], "must_have.use_cases")

    if "nice_to_have" not in parsed:
      raise ValueError("Missing 'nice_to_have' in LLM output")
    if not isinstance(parsed["nice_to_have"], dict):
      raise ValueError("'nice_to_have' must be a dictionary")

    nice_to_have = parsed["nice_to_have"]
    if "use_cases" not in nice_to_have:
      raise ValueError("Missing 'nice_to_have.use_cases' in LLM output")
    if not isinstance(nice_to_have["use_cases"], list):
      raise ValueError("'nice_to_have.use_cases' must be a list")

    _validate_tag_list(nice_to_have["use_cases"], "nice_to_have.use_cases")

    if "functions" not in parsed:
      raise ValueError("Missing 'functions' in LLM output")
    if not isinstance(parsed["functions"], list):
      raise ValueError("'functions' must be a list")

    _validate_tag_list(parsed["functions"], "functions")

    return parsed

  except Exception as err:
    print("parser.validate_llm_output() failed:")
    print(str(err))
    raise


###############################################################
# normalize_parsed_query
#
# Normalizes LLM output before retrieval.
#
def normalize_parsed_query(parsed, taxonomy_context=None):
  """
  Normalizes parsed query output.
  """

  try:
    allowed_categories = set()
    allowed_price_types = set()
    allowed_languages = set()
    use_case_index = _build_taxonomy_index([])
    function_index = _build_taxonomy_index([])

    if taxonomy_context is not None:
      allowed_categories = set(_normalize_string(x) for x in taxonomy_context.get("categories", []))
      allowed_price_types = set(_normalize_price_type(x) for x in taxonomy_context.get("price_types", []))
      allowed_languages = set(_normalize_string(x) for x in taxonomy_context.get("languages", []))
      use_case_index = _build_taxonomy_index(taxonomy_context.get("use_cases", []))
      function_index = _build_taxonomy_index(taxonomy_context.get("functions", []))

    category = _normalize_string(parsed.get("category", ""))

    must_have = parsed.get("must_have", {})
    must_price = must_have.get("price_type", [])
    must_language = must_have.get("language", [])
    must_use_cases = must_have.get("use_cases", [])

    nice_to_have = parsed.get("nice_to_have", {})
    nice_use_cases = nice_to_have.get("use_cases", [])

    functions = parsed.get("functions", [])

    normalized_price = _dedupe_preserve_order(
      [_normalize_price_type(x) for x in must_price if _normalize_price_type(x)]
    )

    normalized_language = _dedupe_preserve_order(
      [_normalize_string(x) for x in must_language if _normalize_string(x)]
    )

    normalized_use_cases = _normalize_tag_list(must_use_cases, use_case_index)
    normalized_nice_use_cases = _normalize_tag_list(nice_use_cases, use_case_index)
    normalized_functions = _normalize_tag_list(functions, function_index)

    normalized_category = category

    if allowed_categories and normalized_category not in allowed_categories:
      normalized_category = category

    if allowed_price_types:
      normalized_price = _keep_known_or_original(normalized_price, allowed_price_types)

    if allowed_languages:
      normalized_language = _keep_known_or_original(normalized_language, allowed_languages)

    normalized = {
      "category": normalized_category,
      "must_have": {
        "price_type": normalized_price,
        "language": normalized_language,
        "use_cases": normalized_use_cases
      },
      "nice_to_have": {
        "use_cases": normalized_nice_use_cases
      },
      "functions": normalized_functions
    }

    return normalized

  except Exception as err:
    print("parser.normalize_parsed_query() failed:")
    print(str(err))
    raise


###############################################################
# Helpers
#
def _validate_tag_list(tags, field_name):
  for item in tags:
    if isinstance(item, str):
      continue

    if not isinstance(item, dict):
      raise ValueError(f"All items in '{field_name}' must be strings or objects")

    if "core" not in item:
      raise ValueError(f"Each item in '{field_name}' must contain 'core'")

    if not isinstance(item["core"], str):
      raise ValueError(f"'core' in '{field_name}' must be a string")

    sub = item.get("sub")
    if sub is not None and not isinstance(sub, str):
      raise ValueError(f"'sub' in '{field_name}' must be a string or null")


def _strip_code_fences(text):
  if not isinstance(text, str):
    return text

  text = text.strip()

  if text.startswith("```"):
    text = re.sub(r"^```[a-zA-Z0-9_]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

  return text.strip()


def _normalize_string(value):
  if value is None:
    return ""

  value = str(value).strip().lower()
  value = re.sub(r"\s+", " ", value)
  return value


def _normalize_price_type(value):
  value = _normalize_string(value)

  if value in ["free trial", "free-trial", "trial", "free_trial"]:
    return "free trial"

  if value in ["free"]:
    return "free"

  if value in ["paid", "pay", "subscription", "annual paid", "monthly paid"]:
    return "paid"

  return value


def _normalize_tag_list(tags, taxonomy_index):
  normalized = []
  seen = set()

  for item in tags:
    normalized_tag = _normalize_tag(item, taxonomy_index)
    key = (normalized_tag["core"], normalized_tag["sub"])

    if key in seen:
      continue

    seen.add(key)
    normalized.append(normalized_tag)

  return normalized


def _normalize_tag(item, taxonomy_index):
  if isinstance(item, str):
    core, sub = _resolve_from_string(item, taxonomy_index)
    return {"core": core, "sub": sub}

  core = _normalize_string(item.get("core"))
  sub = item.get("sub")
  sub = _normalize_string(sub) if sub is not None else None

  if sub == "":
    sub = None

  matched = _match_known_tag(core, sub, taxonomy_index)
  if matched is not None:
    return matched

  return {"core": core, "sub": sub}


def _resolve_from_string(value, taxonomy_index):
  normalized_value = _normalize_string(value)
  candidates = taxonomy_index["sub_to_pairs"].get(normalized_value, [])

  if len(candidates) == 1:
    return candidates[0]

  if normalized_value in taxonomy_index["cores"]:
    return normalized_value, None

  return "", normalized_value


def _match_known_tag(core, sub, taxonomy_index):
  if core and (core, sub) in taxonomy_index["pairs"]:
    return {"core": core, "sub": sub}

  if sub:
    candidates = taxonomy_index["sub_to_pairs"].get(sub, [])

    if core:
      for candidate_core, candidate_sub in candidates:
        if candidate_core == core:
          return {"core": candidate_core, "sub": candidate_sub}

    if len(candidates) == 1:
      candidate_core, candidate_sub = candidates[0]
      return {"core": candidate_core, "sub": candidate_sub}

  if core and core in taxonomy_index["cores"]:
    return {"core": core, "sub": sub}

  return None


def _build_taxonomy_index(tags):
  pairs = set()
  cores = set()
  sub_to_pairs = {}

  for tag in tags:
    core = _normalize_string(tag.get("core"))
    sub = tag.get("sub")
    sub = _normalize_string(sub) if sub is not None else None

    if not core:
      continue

    pairs.add((core, sub))
    cores.add(core)

    if sub:
      sub_to_pairs.setdefault(sub, []).append((core, sub))

  return {
    "pairs": pairs,
    "cores": cores,
    "sub_to_pairs": sub_to_pairs
  }


def _dedupe_preserve_order(items):
  seen = set()
  result = []

  for item in items:
    if item not in seen:
      seen.add(item)
      result.append(item)

  return result


def _keep_known_or_original(labels, allowed_set):
  result = []

  for label in labels:
    if label in allowed_set:
      result.append(label)
    else:
      result.append(label)

  return result

import json
import re


###############################################################
# build_parsing_prompt
#
# Builds the prompt for the LLM to parse the user's query into
# a structured JSON object with primary/secondary taxonomy tags.
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
        "use_cases": [{"primary_tag": "...", "secondary_tag": "..."}, ...],
        "functions": [{"primary_tag": "...", "secondary_tag": "..."}, ...]
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
4. For use_cases and functions, return objects with:
   - primary_tag: required string
   - secondary_tag: string or null
5. Multiple use_cases and multiple functions are allowed when the query contains multiple intents.
6. If you are only confident about the primary tag but not the secondary tag, set secondary_tag to null.
7. Return JSON only. Do not include explanation, markdown, or extra text.

Tag Selection Rules for use_cases and functions:
1. Primary tags represent broad capabilities and are used for candidate tool filtering. Strongly prefer selecting primary tags from the provided canonical primary-tag candidates.
2. Select the closest applicable canonical primary tag whenever the user's intent can reasonably be covered by it. A primary tag does not need to describe the request with fine-grained precision.
3. Do NOT generate a new primary tag merely because a canonical primary tag is broader than the exact request.
4. Generate a new primary tag only when none of the provided canonical primary tags can reasonably represent the requested capability.
5. Secondary tags represent more specific capabilities and are primarily used for ranking. Prefer canonical secondary tags when they adequately describe the intent, but allow more flexibility than for primary tags.
6. If no canonical secondary tag adequately captures an important specific capability, a new secondary tag may be generated.
7. Do not generate a new tag merely to paraphrase, rename, or combine existing canonical tags.

Primary tags are intentionally broad. Semantic coverage is more important than exact wording or fine-grained specificity when selecting a primary tag.

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
      {{"primary_tag": "string", "secondary_tag": "string or null"}}
    ]
  }},
  "nice_to_have": {{
    "use_cases": [
      {{"primary_tag": "string", "secondary_tag": "string or null"}}
    ]
  }},
  "functions": [
    {{"primary_tag": "string", "secondary_tag": "string or null"}}
  ]
}}

Available categories:
{json.dumps(categories, ensure_ascii=False)}

Available price_types:
{json.dumps(price_types, ensure_ascii=False)}

Available languages:
{json.dumps(languages, ensure_ascii=False)}

Canonical use_case tag candidates selected by semantic similarity:
{json.dumps(use_cases, ensure_ascii=False)}

Canonical function tag candidates selected by semantic similarity:
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

    if "primary_tag" not in item:
      raise ValueError(f"Each item in '{field_name}' must contain 'primary_tag'")

    if not isinstance(item["primary_tag"], str):
      raise ValueError(f"'primary_tag' in '{field_name}' must be a string")

    secondary_tag = item.get("secondary_tag")
    if secondary_tag is not None and not isinstance(secondary_tag, str):
      raise ValueError(
        f"'secondary_tag' in '{field_name}' must be a string or null"
      )


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
    key = (
      normalized_tag["primary_tag"],
      normalized_tag["secondary_tag"]
    )

    if key in seen:
      continue

    seen.add(key)
    normalized.append(normalized_tag)

  return normalized


def _normalize_tag(item, taxonomy_index):
  if isinstance(item, str):
    primary_tag, secondary_tag = _resolve_from_string(item, taxonomy_index)
    return {
      "primary_tag": primary_tag,
      "secondary_tag": secondary_tag
    }

  primary_tag = _normalize_string(item.get("primary_tag"))
  secondary_tag = item.get("secondary_tag")
  secondary_tag = (
    _normalize_string(secondary_tag)
    if secondary_tag is not None
    else None
  )

  if secondary_tag == "":
    secondary_tag = None

  matched = _match_known_tag(primary_tag, secondary_tag, taxonomy_index)
  if matched is not None:
    return matched

  return {
    "primary_tag": primary_tag,
    "secondary_tag": secondary_tag
  }


def _resolve_from_string(value, taxonomy_index):
  normalized_value = _normalize_string(value)
  candidates = taxonomy_index["secondary_to_pairs"].get(normalized_value, [])

  if len(candidates) == 1:
    return candidates[0]

  if normalized_value in taxonomy_index["primary_tags"]:
    return normalized_value, None

  return "", normalized_value


def _match_known_tag(primary_tag, secondary_tag, taxonomy_index):
  if primary_tag and (primary_tag, secondary_tag) in taxonomy_index["pairs"]:
    return {"primary_tag": primary_tag, "secondary_tag": secondary_tag}

  if secondary_tag:
    candidates = taxonomy_index["secondary_to_pairs"].get(secondary_tag, [])

    if primary_tag:
      for candidate_primary_tag, candidate_secondary_tag in candidates:
        if candidate_primary_tag == primary_tag:
          return {
            "primary_tag": candidate_primary_tag,
            "secondary_tag": candidate_secondary_tag
          }

    if len(candidates) == 1:
      candidate_primary_tag, candidate_secondary_tag = candidates[0]
      return {
        "primary_tag": candidate_primary_tag,
        "secondary_tag": candidate_secondary_tag
      }

  if primary_tag and primary_tag in taxonomy_index["primary_tags"]:
    return {
      "primary_tag": primary_tag,
      "secondary_tag": secondary_tag
    }

  return None


def _build_taxonomy_index(tags):
  pairs = set()
  primary_tags = set()
  secondary_to_pairs = {}

  for tag in tags:
    primary_tag = _normalize_string(tag.get("primary_tag"))
    secondary_tag = tag.get("secondary_tag")
    secondary_tag = (
      _normalize_string(secondary_tag)
      if secondary_tag is not None
      else None
    )

    if not primary_tag:
      continue

    pairs.add((primary_tag, secondary_tag))
    primary_tags.add(primary_tag)

    if secondary_tag:
      secondary_to_pairs.setdefault(secondary_tag, []).append(
        (primary_tag, secondary_tag)
      )

  return {
    "pairs": pairs,
    "primary_tags": primary_tags,
    "secondary_to_pairs": secondary_to_pairs
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

import json
import re


###############################################################
# build_parsing_prompt
#
# Builds the prompt for the LLM to parse the user's query into
# a structured JSON object.
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
        "use_cases": [...]
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
4. Extract functions from the provided function list whenever possible. Only generate a new function label if the existing function labels truly cannot express the user's meaning.
5. Prefer selecting labels from the provided taxonomy lists.
6. Only generate a new label if the existing labels truly cannot express the user's meaning.
7. If generating a new label, keep it short and consistent with the existing taxonomy style.
8. Return JSON only. Do not include explanation, markdown, or extra text.

Important rule for price_type:
- If the user does NOT mention price preference, then include all available price types in must_have.price_type.
- In this case, do not treat price as a restrictive preference.

JSON schema:
{{
  "category": "string",
  "must_have": {{
    "price_type": ["string", "..."],
    "language": ["string", "..."],
    "use_cases": ["string", "..."]
  }},
  "nice_to_have": {{
    "use_cases": ["string", "..."]
  }},
  "functions": ["string", "..."]
}}

Available categories:
{json.dumps(categories, ensure_ascii=False)}

Available price_types:
{json.dumps(price_types, ensure_ascii=False)}

Available languages:
{json.dumps(languages, ensure_ascii=False)}

Available use_cases:
{json.dumps(use_cases, ensure_ascii=False)}

Available functions:
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
#
#
def parse_query_with_llm(prompt, client=None, model=None):
  """
  Calls the LLM and parses the response into a Python dict.

  Parameters
  ----------
  prompt : prompt string
  client : optional LLM client object
  model : optional model name string

  Returns
  -------
  parsed dict

  Notes
  -----
  This function uses OpenAI API.
  """

  try:
    if client is None:
      raise ValueError("LLM client is required")

    if model is None:
      raise ValueError("Model name is required")

    #
    # Example OpenAI-style call:
    #
    response = client.chat.completions.create(
      model=model,
      messages=[
        {"role": "system", "content": "You are a precise JSON generator."},
        {"role": "user", "content": prompt}
      ],
      temperature=0
    )

    content = response.choices[0].message.content.strip()

    #
    # In case the model wraps JSON in ```json ... ```
    #
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

  Parameters
  ----------
  parsed : dict

  Returns
  -------
  validated parsed dict

  Raises
  ------
  ValueError if schema is invalid
  """

  try:
    if not isinstance(parsed, dict):
      raise ValueError("LLM output must be a dictionary")

    #
    # category
    #
    if "category" not in parsed:
      raise ValueError("Missing 'category' in LLM output")
    if not isinstance(parsed["category"], str):
      raise ValueError("'category' must be a string")

    #
    # must_have
    #
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

      for item in must_have[field]:
        if not isinstance(item, str):
          raise ValueError(f"All items in 'must_have.{field}' must be strings")

    #
    # nice_to_have
    #
    if "nice_to_have" not in parsed:
      raise ValueError("Missing 'nice_to_have' in LLM output")
    if not isinstance(parsed["nice_to_have"], dict):
      raise ValueError("'nice_to_have' must be a dictionary")

    nice_to_have = parsed["nice_to_have"]

    if "use_cases" not in nice_to_have:
      raise ValueError("Missing 'nice_to_have.use_cases' in LLM output")
    if not isinstance(nice_to_have["use_cases"], list):
      raise ValueError("'nice_to_have.use_cases' must be a list")

    for item in nice_to_have["use_cases"]:
      if not isinstance(item, str):
        raise ValueError("All items in 'nice_to_have.use_cases' must be strings")

    #
    # functions
    #
    if "functions" not in parsed:
      raise ValueError("Missing 'functions' in LLM output")
    if not isinstance(parsed["functions"], list):
      raise ValueError("'functions' must be a list")

    for item in parsed["functions"]:
      if not isinstance(item, str):
        raise ValueError("All items in 'functions' must be strings")

    return parsed

  except Exception as err:
    print("parser.validate_llm_output() failed:")
    print(str(err))
    raise


###############################################################
# normalize_parsed_query
#
# Normalizes LLM output before retrieval:
#   - trim whitespace
#   - lowercase labels
#   - normalize formatting
#   - deduplicate
#   - optionally drop labels not found in taxonomy_context
#
def normalize_parsed_query(parsed, taxonomy_context=None):
  """
  Normalizes parsed query output.

  Parameters
  ----------
  parsed : dict
  taxonomy_context : optional dict of allowed labels:
      {
        "categories": [...],
        "price_types": [...],
        "languages": [...],
        "use_cases": [...],
        "functions": [...]
      }

  Returns
  -------
  normalized parsed dict
  """

  try:
    allowed_categories = set()
    allowed_price_types = set()
    allowed_languages = set()
    allowed_use_cases = set()
    allowed_functions = set()

    if taxonomy_context is not None:
      allowed_categories = set(_normalize_string(x) for x in taxonomy_context.get("categories", []))
      allowed_price_types = set(_normalize_price_type(x) for x in taxonomy_context.get("price_types", []))
      allowed_languages = set(_normalize_string(x) for x in taxonomy_context.get("languages", []))
      allowed_use_cases = set(_normalize_string(x) for x in taxonomy_context.get("use_cases", []))
      allowed_functions = set(_normalize_string(x) for x in taxonomy_context.get("functions", []))

    #
    # category
    #
    category = _normalize_string(parsed.get("category", ""))

    #
    # must_have
    #
    must_have = parsed.get("must_have", {})
    must_price = must_have.get("price_type", [])
    must_language = must_have.get("language", [])
    must_use_cases = must_have.get("use_cases", [])

    #
    # nice_to_have
    #
    nice_to_have = parsed.get("nice_to_have", {})
    nice_use_cases = nice_to_have.get("use_cases", [])

    #
    # functions
    #
    functions = parsed.get("functions", [])

    #
    # normalize fields
    #
    normalized_price = _dedupe_preserve_order(
      [_normalize_price_type(x) for x in must_price if _normalize_price_type(x)]
    )

    normalized_language = _dedupe_preserve_order(
      [_normalize_string(x) for x in must_language if _normalize_string(x)]
    )

    normalized_use_cases = _dedupe_preserve_order(
      [_normalize_string(x) for x in must_use_cases if _normalize_string(x)]
    )

    normalized_nice_use_cases = _dedupe_preserve_order(
      [_normalize_string(x) for x in nice_use_cases if _normalize_string(x)]
    )

    normalized_functions = _dedupe_preserve_order(
      [_normalize_string(x) for x in functions if _normalize_string(x)]
    )

    #
    # if taxonomy_context is provided, prefer keeping only known labels
    # except generated new labels are allowed to remain if no match exists.
    #
    if allowed_categories and category in allowed_categories:
        normalized_category = category
    else:
        normalized_category = category

    if allowed_price_types:
        normalized_price = _keep_known_or_original(normalized_price, allowed_price_types)

    if allowed_languages:
        normalized_language = _keep_known_or_original(normalized_language, allowed_languages)

    if allowed_use_cases:
        normalized_use_cases = _keep_known_or_original(normalized_use_cases, allowed_use_cases)
        normalized_nice_use_cases = _keep_known_or_original(normalized_nice_use_cases, allowed_use_cases)

    if allowed_functions:
        normalized_functions = _keep_known_or_original(normalized_functions, allowed_functions)

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
# _strip_code_fences
#
# Removes markdown code fences if present.
#
def _strip_code_fences(text):
  if not isinstance(text, str):
    return text

  text = text.strip()

  if text.startswith("```"):
    text = re.sub(r"^```[a-zA-Z0-9_]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

  return text.strip()


###############################################################
# _normalize_string
#
def _normalize_string(value):
  if value is None:
    return ""

  value = str(value).strip().lower()
  value = re.sub(r"\s+", " ", value)
  return value


###############################################################
# _normalize_price_type
#
# Normalizes price type synonyms to schema-friendly values.
#
def _normalize_price_type(value):
  value = _normalize_string(value)

  if value in ["free trial", "free-trial", "trial", "free_trial"]:
    return "free trial"

  if value in ["free"]:
    return "free"

  if value in ["paid", "pay", "subscription", "annual paid", "monthly paid"]:
    return "paid"

  return value


###############################################################
# _dedupe_preserve_order
#
def _dedupe_preserve_order(items):
  seen = set()
  result = []

  for item in items:
    if item not in seen:
      seen.add(item)
      result.append(item)

  return result


###############################################################
# _keep_known_or_original
#
# Keeps labels as-is for now; if a label matches known taxonomy,
# it stays. If not, it is also kept, because current project rule
# allows new labels when needed.
#
# This helper mainly exists so later you can switch strategy easily:
#   - keep all
#   - drop unknown
#   - log unknown
#
def _keep_known_or_original(labels, allowed_set):
  result = []

  for label in labels:
    if label in allowed_set:
      result.append(label)
    else:
      #
      # Current policy:
      # keep generated labels if needed
      #
      result.append(label)

  return result
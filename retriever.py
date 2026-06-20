import copy

import datatier as db


USE_CASE_CORE_WEIGHT = 2
USE_CASE_SUB_WEIGHT = 4
FUNCTION_CORE_WEIGHT = 2
FUNCTION_SUB_WEIGHT = 4
NICE_TO_HAVE_CORE_WEIGHT = 1
NICE_TO_HAVE_SUB_WEIGHT = 2

FALLBACK_RELAX_ORDER = ["functions", "price_type", "language"]


###############################################################
# retrieve_candidates
#
# Apply strict filtering:
#   - category match
#   - must-have price_type match
#   - must-have language match
#   - must-have use case core match
#   - function core match
#
def retrieve_candidates(dbConn, parsed_query):
  """
  Retrieves candidate tools that satisfy all hard filters.
  """
  try:
    category = parsed_query.get("category", "").strip().lower()
    must_have = parsed_query.get("must_have", {})

    must_have_price_types = must_have.get("price_type", [])
    must_have_languages = must_have.get("language", [])
    must_have_use_cases = must_have.get("use_cases", [])
    functions = parsed_query.get("functions", [])

    category_tools = db.get_tools_by_category(dbConn, category)
    if not category_tools:
      return []

    category_tool_map = {tool["tool_id"]: tool for tool in category_tools}
    candidate_ids = set(category_tool_map.keys())

    use_case_cores = _extract_cores(must_have_use_cases)
    if use_case_cores:
      use_case_ids = db.get_tool_ids_by_use_case_cores(dbConn, use_case_cores)
      candidate_ids = candidate_ids & use_case_ids

    function_cores = _extract_cores(functions)
    if function_cores:
      function_ids = db.get_tool_ids_by_function_cores(dbConn, function_cores)
      candidate_ids = candidate_ids & function_ids

    if must_have_price_types:
      price_type_ids = db.get_tool_ids_by_price_types(dbConn, must_have_price_types)
      candidate_ids = candidate_ids & price_type_ids

    if must_have_languages:
      language_ids = db.get_tool_ids_by_language(dbConn, must_have_languages)
      candidate_ids = candidate_ids & language_ids

    return [category_tool_map[tool_id] for tool_id in candidate_ids]

  except Exception as err:
    print("retriever.retrieve_candidates() failed:")
    print(str(err))
    raise


###############################################################
# get_primary_use_case
#
def get_primary_use_case(parsed_query):
  """
  Returns the most important use case for fallback logic.
  """
  try:
    must_have = parsed_query.get("must_have", {})
    use_cases = must_have.get("use_cases", [])

    if use_cases:
      return use_cases[0]

    return None

  except Exception as err:
    print("retriever.get_primary_use_case() failed:")
    print(str(err))
    raise


###############################################################
# build_default_fallback_info
#
def build_default_fallback_info(parsed_query):
  return {
    "fallback_used": False,
    "relaxed_field": None,
    "relaxed_fields": [],
    "original_constraints": _extract_constraints_snapshot(parsed_query),
    "relaxed_constraints": None,
    "retry_count": 0,
    "retry_history": []
  }


###############################################################
# fallback_retrieve
#
def fallback_retrieve(dbConn, parsed_query):
  """
  Performs iterative fallback retrieval.

  Relax order:
    1. functions
    2. price_type
    3. language

  Retrieval is retried after each single relaxation until results
  are found or only use case remains as the hard requirement.
  """
  try:
    active_query = copy.deepcopy(parsed_query)
    fallback_info = build_default_fallback_info(parsed_query)

    for field_name in FALLBACK_RELAX_ORDER:
      if not _has_relaxable_constraint(active_query, field_name):
        continue

      active_query = relax_single_constraint(active_query, field_name)
      candidates = retrieve_candidates(dbConn, active_query)

      fallback_info["fallback_used"] = True
      fallback_info["relaxed_field"] = field_name
      fallback_info["relaxed_fields"].append(field_name)
      fallback_info["relaxed_constraints"] = _extract_constraints_snapshot(active_query)
      fallback_info["retry_count"] = len(fallback_info["relaxed_fields"])
      fallback_info["retry_history"].append({
        "step": len(fallback_info["relaxed_fields"]),
        "relaxed_field": field_name,
        "active_constraints": _extract_constraints_snapshot(active_query),
        "result_count": len(candidates)
      })

      if candidates:
        return candidates, fallback_info, active_query

    return [], fallback_info, active_query

  except Exception as err:
    print("retriever.fallback_retrieve() failed:")
    print(str(err))
    raise


###############################################################
# relax_single_constraint
#
def relax_single_constraint(parsed_query, field_name):
  """
  Relaxes one hard constraint while keeping use case hard filters.
  """
  try:
    relaxed_query = copy.deepcopy(parsed_query)

    if field_name == "functions":
      relaxed_query["functions"] = []
    elif field_name == "price_type":
      relaxed_query.setdefault("must_have", {})["price_type"] = []
    elif field_name == "language":
      relaxed_query.setdefault("must_have", {})["language"] = []
    else:
      raise ValueError(f"Unsupported fallback field: {field_name}")

    return relaxed_query

  except Exception as err:
    print("retriever.relax_single_constraint() failed:")
    print(str(err))
    raise


###############################################################
# score_candidates
#
def score_candidates(dbConn, candidates, parsed_query):
  """
  Scores candidate tools using core/sub-aware ranking.
  """
  try:
    if not candidates:
      return []

    must_have = parsed_query.get("must_have", {})
    nice_to_have = parsed_query.get("nice_to_have", {})

    must_have_use_cases = must_have.get("use_cases", [])
    nice_to_have_use_cases = nice_to_have.get("use_cases", [])
    functions = parsed_query.get("functions", [])

    must_usecase_core_tool_ids = {}
    must_usecase_sub_tool_ids = {}
    for use_case in must_have_use_cases:
      core = use_case.get("core")
      if core:
        must_usecase_core_tool_ids[core] = db.get_tool_ids_by_use_case_cores(dbConn, [core])
      must_usecase_sub_tool_ids[_tag_key(use_case)] = db.get_tool_ids_by_use_case_tag(dbConn, use_case)

    nice_usecase_core_tool_ids = {}
    nice_usecase_sub_tool_ids = {}
    for use_case in nice_to_have_use_cases:
      core = use_case.get("core")
      if core:
        nice_usecase_core_tool_ids[core] = db.get_tool_ids_by_use_case_cores(dbConn, [core])
      nice_usecase_sub_tool_ids[_tag_key(use_case)] = db.get_tool_ids_by_use_case_tag(dbConn, use_case)

    function_core_tool_ids = {}
    function_sub_tool_ids = {}
    for func in functions:
      core = func.get("core")
      if core:
        function_core_tool_ids[core] = db.get_tool_ids_by_function_cores(dbConn, [core])
      function_sub_tool_ids[_tag_key(func)] = db.get_tool_ids_by_function_tag(dbConn, func)

    scored_candidates = []

    for candidate in candidates:
      tool_id = candidate["tool_id"]
      name = candidate["name"]

      matched_use_case_core_count = 0
      matched_use_case_sub_count = 0
      matched_nice_to_have_core_count = 0
      matched_nice_to_have_sub_count = 0
      matched_function_core_count = 0
      matched_function_sub_count = 0

      for use_case in must_have_use_cases:
        core = use_case.get("core")
        sub = use_case.get("sub")

        if core and tool_id in must_usecase_core_tool_ids.get(core, set()):
          matched_use_case_core_count += 1

        if sub and tool_id in must_usecase_sub_tool_ids.get(_tag_key(use_case), set()):
          matched_use_case_sub_count += 1

      for use_case in nice_to_have_use_cases:
        core = use_case.get("core")
        sub = use_case.get("sub")

        if core and tool_id in nice_usecase_core_tool_ids.get(core, set()):
          matched_nice_to_have_core_count += 1

        if sub and tool_id in nice_usecase_sub_tool_ids.get(_tag_key(use_case), set()):
          matched_nice_to_have_sub_count += 1

      for func in functions:
        core = func.get("core")
        sub = func.get("sub")

        if core and tool_id in function_core_tool_ids.get(core, set()):
          matched_function_core_count += 1

        if sub and tool_id in function_sub_tool_ids.get(_tag_key(func), set()):
          matched_function_sub_count += 1

      score = (
        USE_CASE_CORE_WEIGHT * matched_use_case_core_count
        + USE_CASE_SUB_WEIGHT * matched_use_case_sub_count
        + FUNCTION_CORE_WEIGHT * matched_function_core_count
        + FUNCTION_SUB_WEIGHT * matched_function_sub_count
        + NICE_TO_HAVE_CORE_WEIGHT * matched_nice_to_have_core_count
        + NICE_TO_HAVE_SUB_WEIGHT * matched_nice_to_have_sub_count
      )

      scored_candidates.append({
        "tool_id": tool_id,
        "name": name,
        "matched_use_case_core_count": matched_use_case_core_count,
        "matched_use_case_sub_count": matched_use_case_sub_count,
        "matched_function_core_count": matched_function_core_count,
        "matched_function_sub_count": matched_function_sub_count,
        "matched_nice_to_have_core_count": matched_nice_to_have_core_count,
        "matched_nice_to_have_sub_count": matched_nice_to_have_sub_count,
        "matched_use_case_count": matched_use_case_core_count + matched_use_case_sub_count,
        "matched_function_count": matched_function_core_count + matched_function_sub_count,
        "matched_nice_to_have_count": matched_nice_to_have_core_count + matched_nice_to_have_sub_count,
        "score": score
      })

    return scored_candidates

  except Exception as err:
    print("retriever.score_candidates() failed:")
    print(str(err))
    raise


###############################################################
# sort_candidates
#
def sort_candidates(scored_candidates):
  """
  Sorts candidates according to score and tie-break rules.
  """
  try:
    sorted_candidates = sorted(
      scored_candidates,
      key=lambda x: (
        -x["score"],
        -x["matched_use_case_sub_count"],
        -x["matched_function_sub_count"],
        -x["matched_use_case_core_count"],
        -x["matched_function_core_count"],
        x["name"].lower(),
        x["tool_id"]
      )
    )

    for i, candidate in enumerate(sorted_candidates, start=1):
      candidate["rank"] = i

    return sorted_candidates

  except Exception as err:
    print("retriever.sort_candidates() failed:")
    print(str(err))
    raise


###############################################################
# limit_top_results
#
def limit_top_results(sorted_candidates, limit=3):
  """
  Returns top N ranked results.
  """
  try:
    if limit <= 0:
      return []

    return sorted_candidates[:limit]

  except Exception as err:
    print("retriever.limit_top_results() failed:")
    print(str(err))
    raise


def _has_relaxable_constraint(parsed_query, field_name):
  if field_name == "functions":
    return len(parsed_query.get("functions", [])) > 0

  must_have = parsed_query.get("must_have", {})

  if field_name == "price_type":
    return len(must_have.get("price_type", [])) > 0

  if field_name == "language":
    return len(must_have.get("language", [])) > 0

  return False


def _extract_constraints_snapshot(parsed_query):
  must_have = parsed_query.get("must_have", {})

  return {
    "functions": copy.deepcopy(parsed_query.get("functions", [])),
    "price_type": list(must_have.get("price_type", [])),
    "language": list(must_have.get("language", [])),
    "use_cases": copy.deepcopy(must_have.get("use_cases", []))
  }


def _extract_cores(tags):
  cores = []
  seen = set()

  for tag in tags:
    core = (tag.get("core") or "").strip().lower()
    if core and core not in seen:
      seen.add(core)
      cores.append(core)

  return cores


def _tag_key(tag):
  return (
    (tag.get("core") or "").strip().lower(),
    (tag.get("sub") or "").strip().lower() if tag.get("sub") else ""
  )

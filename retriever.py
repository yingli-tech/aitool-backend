import datatier as db


###############################################################
# retrieve_candidates
#
# Apply strict filtering:
#   - category match
#   - must-have price_type match
#   - must-have language match
#   - must-have use case match
#
# Returns:
#   list of candidate dicts:
#   [
#     {"tool_id": 1, "name": "Tool A"},
#     ...
#   ]
#
def retrieve_candidates(dbConn, parsed_query):
  """
  Retrieves candidate tools that satisfy all must-have filters.

  Parameters
  ----------
  dbConn : database connection
  parsed_query : dict

  Returns
  -------
  list of candidate dicts
  """
  try:
    category = parsed_query.get("category", "").strip().lower()
    must_have = parsed_query.get("must_have", {})

    must_have_price_types = must_have.get("price_type", [])
    must_have_languages = must_have.get("language", [])
    must_have_use_cases = must_have.get("use_cases", [])

    #
    # Step 1: category filter
    #
    category_tools = db.get_tools_by_category(dbConn, category)
    if not category_tools:
      return []

    category_tool_map = {tool["tool_id"]: tool for tool in category_tools}
    candidate_ids = set(category_tool_map.keys())

    #
    # Step 2: must-have use case filter
    #
    if must_have_use_cases:
      use_case_ids = db.get_tool_ids_by_use_cases(dbConn, must_have_use_cases)
      candidate_ids = candidate_ids & use_case_ids

    #
    # Step 3: must-have price_type filter
    #
    if must_have_price_types:
      price_type_ids = db.get_tool_ids_by_price_types(dbConn, must_have_price_types)
      candidate_ids = candidate_ids & price_type_ids

    #
    # Step 4: must-have language filter
    #
    if must_have_languages:
      language_ids = db.get_tool_ids_by_language(dbConn, must_have_languages)
      candidate_ids = candidate_ids & language_ids

    #
    # Build candidate list
    #
    candidates = []
    for tool_id in candidate_ids:
      candidates.append(category_tool_map[tool_id])

    return candidates

  except Exception as err:
    print("retriever.retrieve_candidates() failed:")
    print(str(err))
    raise


###############################################################
# get_primary_use_case
#
# For MVP:
#   use the first must-have use case as the primary use case
#
def get_primary_use_case(parsed_query):
  """
  Returns the most important use case for fallback logic.

  Parameters
  ----------
  parsed_query : dict

  Returns
  -------
  primary use case string or None
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
# relax_constraints
#
# Fallback rule:
#   1. keep category
#   2. keep the primary use case
#   3. relax language first if present
#   4. otherwise relax price_type if present
#
# Returns:
#   relaxed_query, fallback_info
#
def relax_constraints(parsed_query):
  """
  Relaxes part of the must-have constraints for fallback retrieval.

  Parameters
  ----------
  parsed_query : dict

  Returns
  -------
  (relaxed_query, fallback_info)
  """
  try:
    must_have = parsed_query.get("must_have", {})
    nice_to_have = parsed_query.get("nice_to_have", {})
    functions = parsed_query.get("functions", [])
    category = parsed_query.get("category", "")

    original_price_types = list(must_have.get("price_type", []))
    original_languages = list(must_have.get("language", []))
    original_use_cases = list(must_have.get("use_cases", []))

    primary_use_case = get_primary_use_case(parsed_query)

    relaxed_price_types = list(original_price_types)
    relaxed_languages = list(original_languages)
    relaxed_use_cases = [primary_use_case] if primary_use_case else []

    relaxed_field = None

    #
    # Relax language first
    #
    if relaxed_languages:
      relaxed_languages = []
      relaxed_field = "language"

    #
    # If no language to relax, relax price_type
    #
    elif relaxed_price_types:
      relaxed_price_types = []
      relaxed_field = "price_type"

    #
    # If neither language nor price_type exists,
    # then fallback cannot further relax under current rule.
    #
    relaxed_query = {
      "category": category,
      "must_have": {
        "price_type": relaxed_price_types,
        "language": relaxed_languages,
        "use_cases": relaxed_use_cases
      },
      "nice_to_have": nice_to_have,
      "functions": functions
    }

    fallback_info = {
      "fallback_used": True,
      "relaxed_field": relaxed_field,
      "original_constraints": {
        "price_type": original_price_types,
        "language": original_languages,
        "use_cases": original_use_cases
      },
      "relaxed_constraints": relaxed_query["must_have"]
    }

    return relaxed_query, fallback_info

  except Exception as err:
    print("retriever.relax_constraints() failed:")
    print(str(err))
    raise


###############################################################
# fallback_retrieve
#
# Runs fallback retrieval if strict retrieval returns no result.
#
# Returns:
#   candidates, fallback_info, active_query
#
def fallback_retrieve(dbConn, parsed_query):
  """
  Performs fallback retrieval using relaxed constraints.

  Parameters
  ----------
  dbConn : database connection
  parsed_query : dict

  Returns
  -------
  (candidates, fallback_info, active_query)
  """
  try:
    relaxed_query, fallback_info = relax_constraints(parsed_query)
    candidates = retrieve_candidates(dbConn, relaxed_query)

    return candidates, fallback_info, relaxed_query

  except Exception as err:
    print("retriever.fallback_retrieve() failed:")
    print(str(err))
    raise


###############################################################
# score_candidates
#
# score =
#   3 * matched_use_case_count
# + 2 * matched_function_count
# + 1 * matched_nice_to_have_count
#
def score_candidates(dbConn, candidates, parsed_query):
  """
  Scores candidate tools using rule-based ranking.

  Parameters
  ----------
  dbConn : database connection
  candidates : list of {"tool_id": int, "name": str}
  parsed_query : dict

  Returns
  -------
  list of scored candidate dicts
  """
  try:
    if not candidates:
      return []

    must_have = parsed_query.get("must_have", {})
    nice_to_have = parsed_query.get("nice_to_have", {})

    must_have_use_cases = must_have.get("use_cases", [])
    nice_to_have_use_cases = nice_to_have.get("use_cases", [])
    functions = parsed_query.get("functions", [])

    #
    # Pre-fetch tool id sets by label group
    #
    must_usecase_tool_ids = {}
    for use_case in must_have_use_cases:
      must_usecase_tool_ids[use_case] = db.get_tool_ids_by_use_cases(dbConn, [use_case])

    nice_usecase_tool_ids = {}
    for use_case in nice_to_have_use_cases:
      nice_usecase_tool_ids[use_case] = db.get_tool_ids_by_use_cases(dbConn, [use_case])

    function_tool_ids = {}
    for func in functions:
      function_tool_ids[func] = db.get_tool_ids_by_functions(dbConn, [func])

    scored_candidates = []

    for candidate in candidates:
      tool_id = candidate["tool_id"]
      name = candidate["name"]

      matched_use_case_count = 0
      matched_nice_to_have_count = 0
      matched_function_count = 0

      #
      # Count matched must-have use cases
      #
      for use_case in must_have_use_cases:
        if tool_id in must_usecase_tool_ids.get(use_case, set()):
          matched_use_case_count += 1

      #
      # Count matched nice-to-have use cases
      #
      for use_case in nice_to_have_use_cases:
        if tool_id in nice_usecase_tool_ids.get(use_case, set()):
          matched_nice_to_have_count += 1

      #
      # Count matched functions
      #
      for func in functions:
        if tool_id in function_tool_ids.get(func, set()):
          matched_function_count += 1

      score = (
        3 * matched_use_case_count
        + 2 * matched_function_count
        + 1 * matched_nice_to_have_count
      )

      scored_candidates.append({
        "tool_id": tool_id,
        "name": name,
        "matched_use_case_count": matched_use_case_count,
        "matched_function_count": matched_function_count,
        "matched_nice_to_have_count": matched_nice_to_have_count,
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
# Tie-break:
#   1. score desc
#   2. matched_use_case_count desc
#   3. matched_function_count desc
#   4. name asc
#   5. tool_id asc
#
def sort_candidates(scored_candidates):
  """
  Sorts candidates according to score and tie-break rules.

  Parameters
  ----------
  scored_candidates : list of dicts

  Returns
  -------
  sorted list of dicts
  """
  try:
    sorted_candidates = sorted(
      scored_candidates,
      key=lambda x: (
        -x["score"],
        -x["matched_use_case_count"],
        -x["matched_function_count"],
        x["name"].lower(),
        x["tool_id"]
      )
    )

    #
    # add rank
    #
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
# Returns top N results only
#
def limit_top_results(sorted_candidates, limit=3):
  """
  Returns top N ranked results.

  Parameters
  ----------
  sorted_candidates : list of dicts
  limit : int

  Returns
  -------
  truncated list of dicts
  """
  try:
    if limit <= 0:
      return []

    return sorted_candidates[:limit]

  except Exception as err:
    print("retriever.limit_top_results() failed:")
    print(str(err))
    raise
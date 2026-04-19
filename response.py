import json
from datetime import datetime

###############################################################
# _cors_headers
#
# Shared CORS headers for all API Gateway responses.
#
def _cors_headers():
  return {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
  }


###############################################################
# format_response
#
# Builds the final successful API Gateway response.
#
def format_response(query, parsed_query, results, fallback_info=None):
  """
  Builds a successful API response.

  Parameters
  ----------
  query : original user query (string)
  parsed_query : dict
  results : list of result dicts
  fallback_info : dict or None

  Returns
  -------
  API Gateway-compatible response dict
  """

  try:
    if fallback_info is None:
      fallback_info = {
        "fallback_used": False,
        "relaxed_field": None,
        "original_constraints": parsed_query.get("must_have", {}),
        "relaxed_constraints": None
      }

    response_body = {
      "query": query,
      "parsed_query": parsed_query,
      "fallback_used": fallback_info.get("fallback_used", False),
      "relaxed_field": fallback_info.get("relaxed_field", None),
      "original_constraints": fallback_info.get("original_constraints", {}),
      "relaxed_constraints": fallback_info.get("relaxed_constraints", None),
      "result_count": len(results),
      "results": results
    }

    if len(results) == 0:
      response_body["message"] = (
        "No fully matching tools were found."
        if not fallback_info.get("fallback_used", False)
        else "No tools were found even after relaxing constraints."
      )
    elif fallback_info.get("fallback_used", False):
      response_body["message"] = (
        "No tools fully matched all constraints. "
        "Returning the closest matches after relaxing one requirement."
      )
    else:
      response_body["message"] = "Success"

    return {
      "statusCode": 200,
      "headers": _cors_headers(),
      "body": json.dumps(response_body, ensure_ascii=False)
    }

  except Exception as err:
    print("response.format_response() failed:")
    print(str(err))
    raise


###############################################################
# build_error_response
#
# Builds a standardized API Gateway error response.
#
def build_error_response(status_code, message, detail=None):
  """
  Builds a standardized error response.

  Parameters
  ----------
  status_code : int
  message : string
  detail : string or None

  Returns
  -------
  API Gateway-compatible error response dict
  """

  try:
    error_body = {
      "error": {
        "message": message,
        "detail": detail
      }
    }

    return {
      "statusCode": status_code,
      "headers": _cors_headers(),
      "body": json.dumps(error_body, ensure_ascii=False)
    }

  except Exception as err:
    print("response.build_error_response() failed:")
    print(str(err))
    raise


###############################################################
# build_options_response
#
# Builds response for CORS preflight requests.
#
def build_options_response():
  try:
    return {
      "statusCode": 200,
      "headers": _cors_headers(),
      "body": json.dumps({"message": "CORS preflight OK"}, ensure_ascii=False)
    }
  except Exception as err:
    print("response.build_options_response() failed:")
    print(str(err))
    raise
    

###############################################################
# merge_ranked_results_with_details
#
# Merges ranking metadata with tool detail records.
#
def merge_ranked_results_with_details(ranked_results, tool_details):
  """
  Merges ranked scoring results with tool detail rows.

  Parameters
  ----------
  ranked_results : list of dicts, for example:
      [
        {
          "rank": 1,
          "tool_id": 3,
          "name": "Tool A",
          "matched_use_case_count": 2,
          "matched_function_count": 1,
          "matched_nice_to_have_count": 1,
          "score": 9
        }
      ]

  tool_details : list of dicts, for example:
      [
        {
          "tool_id": 3,
          "name": "Tool A",
          "url": "...",
          "description": "...",
          "category": "audio",
          "language": "chinese"
        }
      ]

  Returns
  -------
  merged list of dicts
  """

  try:
    if not ranked_results:
      return []

    detail_map = {}
    for tool in tool_details:
      detail_map[tool["tool_id"]] = tool

    merged = []

    for ranked in ranked_results:
      tool_id = ranked["tool_id"]
      detail = detail_map.get(tool_id, {})

      merged.append({
        "rank": ranked.get("rank"),
        "tool_id": tool_id,
        "name": detail.get("name", ranked.get("name")),
        "url": detail.get("url"),
        "description": detail.get("description"),
        "category": detail.get("category"),
        "language": detail.get("language"),
        "score": ranked.get("score", 0),
        "matched_use_case_count": ranked.get("matched_use_case_count", 0),
        "matched_function_count": ranked.get("matched_function_count", 0),
        "matched_nice_to_have_count": ranked.get("matched_nice_to_have_count", 0)
      })

    return merged

  except Exception as err:
    print("response.merge_ranked_results_with_details() failed:")
    print(str(err))
    raise


###############################################################
# log_request
#
# Logs request information for debugging / evaluation.
# For MVP, prints structured logs to CloudWatch.
#
def log_request(query, parsed_query=None, fallback_info=None, result_count=0, error=None):
  """
  Logs request-level information.

  Parameters
  ----------
  query : string
  parsed_query : dict or None
  fallback_info : dict or None
  result_count : int
  error : string or None

  Returns
  -------
  None
  """

  try:
    log_data = {
      "timestamp": datetime.utcnow().isoformat() + "Z",
      "query": query,
      "parsed_query": parsed_query,
      "fallback_info": fallback_info,
      "result_count": result_count,
      "error": error
    }

    print(json.dumps(log_data, ensure_ascii=False))

  except Exception as err:
    print("response.log_request() failed:")
    print(str(err))
    # do not re-raise: logging failure should not break request
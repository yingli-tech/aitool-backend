import json

import datatier as db
import parser
import retriever
import response

import os

from openai import OpenAI


###############################################################
# get_http_method
#
# Extracts HTTP method from different API Gateway event shapes.
#
def get_http_method(event):
  try:
    if not isinstance(event, dict):
      return ""

    # REST API / Lambda proxy
    if "httpMethod" in event:
      return (event.get("httpMethod") or "").upper()

    # HTTP API v2
    request_context = event.get("requestContext", {})
    http_info = request_context.get("http", {})
    if "method" in http_info:
      return (http_info.get("method") or "").upper()

    return ""

  except Exception as err:
    print("handler.get_http_method() failed:")
    print(str(err))
    raise


###############################################################
# extract_query_from_event
#
# Extracts the user query from the API Gateway event.
#
def extract_query_from_event(event):
  """
  Extracts query string from Lambda event.

  Expected body format:
    {
      "query": "I want a free Chinese podcast editing tool"
    }

  Parameters
  ----------
  event : dict

  Returns
  -------
  query string
  """

  try:
    if event is None:
      raise ValueError("event is missing")

    body = event.get("body")

    #
    # API Gateway often passes body as a JSON string
    #
    if body is None:
      raise ValueError("request body is missing")

    if isinstance(body, str):
      body = json.loads(body)

    if not isinstance(body, dict):
      raise ValueError("request body must be a JSON object")

    query = body.get("query")
    if query is None:
      raise ValueError("query is missing from request body")

    return query

  except Exception as err:
    print("handler.extract_query_from_event() failed:")
    print(str(err))
    raise


###############################################################
# validate_request
#
# Validates and cleans the user query.
#
def validate_request(query):
  """
  Validates query input.

  Parameters
  ----------
  query : string

  Returns
  -------
  cleaned query string
  """

  try:
    if query is None:
      raise ValueError("query is missing")

    if not isinstance(query, str):
      raise ValueError("query must be a string")

    cleaned = query.strip()

    if cleaned == "":
      raise ValueError("query cannot be empty")

    #
    # simple max length guard for MVP
    #
    if len(cleaned) > 1000:
      raise ValueError("query is too long")

    return cleaned

  except Exception as err:
    print("handler.validate_request() failed:")
    print(str(err))
    raise


###############################################################
# lambda_handler
#
# Main Lambda entry point.
#
def lambda_handler(event, context):
  """
  Main Lambda handler for the AI tool recommendation API.

  Flow
  ----
  1. Extract query from request
  2. Validate query
  3. Connect to database
  4. Load taxonomy context
  5. Build LLM parsing prompt
  6. Parse query with LLM
  7. Validate and normalize parsed query
  8. Strict retrieval
  9. Fallback retrieval if needed
  10. Score and sort candidates
  11. Fetch tool details
  12. Merge and return formatted response
  """

  dbConn = None

  try:
      
    ###########################################################
    # 0. CORS preflight + method check
    ###########################################################
    http_method = get_http_method(event)

    if http_method == "OPTIONS":
      return response.build_options_response()

    if http_method and http_method != "POST":
      return response.build_error_response(
        status_code=405,
        message="Method not allowed",
        detail=f"Unsupported method: {http_method}"
      )  
      
      
    ###########################################################
    # 1. request parsing + validation
    ###########################################################
    query = extract_query_from_event(event)
    query = validate_request(query)

    ###########################################################
    # 2. database connection
    #
    #
    ###########################################################
    
    
    #---- ENV VARIABLES for Database ----
    endpoint = os.environ["endpoint"]
    dbname = os.environ["dbname"]
    username = os.environ["username"]
    pwd = os.environ["pwd"]
    portnum = int(os.environ["portnum"])
    
    #---- ENV VARIABLES for Open AI API ----
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    model = os.environ["openai_model"]
    client = OpenAI(api_key=OPENAI_API_KEY)

    dbConn = db.get_db_connection(endpoint, portnum, username, pwd, dbname)

    ###########################################################
    # 3. taxonomy context for prompt / simple RAG
    ###########################################################
    taxonomy_context = db.get_taxonomy_context(dbConn)

    ###########################################################
    # 4. build prompt
    ###########################################################
    prompt = parser.build_parsing_prompt(query, taxonomy_context)

    ###########################################################
    # 5. call LLM
    ###########################################################
    

    parsed_query = parser.parse_query_with_llm(
      prompt=prompt,
      client=client,
      model=model
    )

    ###########################################################
    # 6. validate + normalize parsed query
    ###########################################################
    parsed_query = parser.validate_llm_output(parsed_query)
    parsed_query = parser.normalize_parsed_query(parsed_query, taxonomy_context)

    ###########################################################
    # 7. strict retrieval
    ###########################################################
    candidates = retriever.retrieve_candidates(dbConn, parsed_query)

    fallback_info = {
      "fallback_used": False,
      "relaxed_field": None,
      "original_constraints": parsed_query.get("must_have", {}),
      "relaxed_constraints": None
    }

    active_query = parsed_query

    ###########################################################
    # 8. fallback retrieval if strict result is empty
    ###########################################################
    if not candidates:
      candidates, fallback_info, active_query = retriever.fallback_retrieve(
        dbConn,
        parsed_query
      )

    ###########################################################
    # 9. if still empty, return empty result response
    ###########################################################
    if not candidates:
      response.log_request(
        query=query,
        parsed_query=parsed_query,
        fallback_info=fallback_info,
        result_count=0,
        error=None
      )

      return response.format_response(
        query=query,
        parsed_query=parsed_query,
        results=[],
        fallback_info=fallback_info
      )

    ###########################################################
    # 10. score + sort + limit top results
    ###########################################################
    scored_candidates = retriever.score_candidates(
      dbConn,
      candidates,
      active_query
    )

    sorted_candidates = retriever.sort_candidates(scored_candidates)
    top_results = retriever.limit_top_results(sorted_candidates, limit=3)

    ###########################################################
    # 11. fetch tool details
    ###########################################################
    tool_ids = [item["tool_id"] for item in top_results]
    tool_details = db.fetch_tool_details(dbConn, tool_ids)

    ###########################################################
    # 12. merge ranking info + tool details
    ###########################################################
    merged_results = response.merge_ranked_results_with_details(
      top_results,
      tool_details
    )

    ###########################################################
    # 13. log success
    ###########################################################
    response.log_request(
      query=query,
      parsed_query=parsed_query,
      fallback_info=fallback_info,
      result_count=len(merged_results),
      error=None
    )

    ###########################################################
    # 14. return final response
    ###########################################################
    return response.format_response(
      query=query,
      parsed_query=parsed_query,
      results=merged_results,
      fallback_info=fallback_info
    )

  except ValueError as err:
    response.log_request(
      query=event.get("body") if isinstance(event, dict) else None,
      parsed_query=None,
      fallback_info=None,
      result_count=0,
      error=str(err)
    )

    return response.build_error_response(
      status_code=400,
      message="Invalid request",
      detail=str(err)
    )

  except Exception as err:
    response.log_request(
      query=event.get("body") if isinstance(event, dict) else None,
      parsed_query=None,
      fallback_info=None,
      result_count=0,
      error=str(err)
    )

    return response.build_error_response(
      status_code=500,
      message="Internal server error",
      detail=str(err)
    )

  finally:
    if dbConn is not None:
      db.close_db_connection(dbConn)
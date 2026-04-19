import pymysql


###############################################################
# get_db_connection
#
# Opens and returns a connection object for interacting with MySQL
#
def get_db_connection(endpoint, portnum, username, pwd, dbname):
  """
  Opens and returns a connection object for interacting
  with a MySQL database.

  Environment Variables From lambda function

  Returns
  -------
  a connection object
  """
  try:


    dbConn = pymysql.connect(
      host=endpoint,
      port=portnum,
      user=username,
      passwd=pwd,
      database=dbname
    )
    return dbConn

  except Exception as err:
    print("db.get_db_connection() failed:")
    print(str(err))
    raise


###############################################################
# close_db_connection
#
def close_db_connection(dbConn):
  try:
    if dbConn:
      dbConn.close()
  except Exception as err:
    print("db.close_db_connection() failed:")
    print(str(err))


###############################################################
# get_taxonomy_context
#
# Returns categories, price_types, languages, use_cases
#
#
def get_taxonomy_context(dbConn):
  try:
    cursor = dbConn.cursor()

    # categories
    cursor.execute("SELECT DISTINCT category FROM tools")
    categories = [row[0] for row in cursor.fetchall()]

    # price_types
    cursor.execute("SELECT price_type FROM price_types")
    price_types = [row[0] for row in cursor.fetchall()]

    # languages
    cursor.execute("SELECT DISTINCT language FROM tools")
    languages = [row[0] for row in cursor.fetchall()]

    # use_cases (sub)
    cursor.execute("SELECT sub FROM use_cases")
    use_cases = [row[0] for row in cursor.fetchall()]
    
    # functions (sub)
    cursor.execute("SELECT sub FROM functions")
    functions = [row[0] for row in cursor.fetchall()]
    

    return {
      "categories": categories,
      "price_types": price_types,
      "languages": languages,
      "use_cases": use_cases,
      "functions": functions
    }

  except Exception as err:
    print("db.get_taxonomy_context() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# fetch_tool_details
#
# Given tool_ids, returns tool info
#
# TABLE tools (tool_id, name, url, description, category, language) 
#
def fetch_tool_details(dbConn, tool_ids):
  try:
    if not tool_ids:
      return []

    cursor = dbConn.cursor()

    format_strings = ','.join(['%s'] * len(tool_ids))

    sql = f"""
      SELECT tool_id, name, url, description, category, language
      FROM tools
      WHERE tool_id IN ({format_strings})
    """

    cursor.execute(sql, tool_ids)
    rows = cursor.fetchall()

    # convert to dict
    results = []
    for row in rows:
      results.append({
        "tool_id": row[0],
        "name": row[1],
        "url": row[2],
        "description": row[3],
        "category": row[4],
        "language": row[5]
      })

    return results

  except Exception as err:
    print("db.fetch_tool_details() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# get_tools_by_category
#
# Returns tool_ids filtered by category
#
def get_tools_by_category(dbConn, category):
  try:
    cursor = dbConn.cursor()

    sql = """
      SELECT tool_id, name
      FROM tools
      WHERE LOWER(category) = %s
    """

    cursor.execute(sql, [category])
    rows = cursor.fetchall()

    return [{"tool_id": r[0], "name": r[1]} for r in rows]

  except Exception as err:
    print("db.get_tools_by_category() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# get_tool_ids_by_use_cases
#
def get_tool_ids_by_use_cases(dbConn, use_cases):
  try:
    if not use_cases:
      return set()

    cursor = dbConn.cursor()

    format_strings = ','.join(['%s'] * len(use_cases))

    sql = f"""
      SELECT DISTINCT tum.tool_id
      FROM tool_usecase_map tum
      JOIN use_cases uc ON tum.usecase_id = uc.usecase_id
      WHERE uc.sub IN ({format_strings})
    """

    cursor.execute(sql, use_cases)
    rows = cursor.fetchall()

    return set([r[0] for r in rows])

  except Exception as err:
    print("db.get_tool_ids_by_use_cases() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# get_tool_ids_by_price_types
#
def get_tool_ids_by_price_types(dbConn, price_types):
  try:
    if not price_types:
      return set()

    cursor = dbConn.cursor()

    format_strings = ','.join(['%s'] * len(price_types))

    sql = f"""
      SELECT DISTINCT tpm.tool_id
      FROM tool_price_map tpm
      JOIN price_types pt ON tpm.price_type_id = pt.price_type_id
      WHERE pt.price_type IN ({format_strings})
    """

    cursor.execute(sql, price_types)
    rows = cursor.fetchall()

    return set([r[0] for r in rows])

  except Exception as err:
    print("db.get_tool_ids_by_price_types() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# get_tool_ids_by_language
#
def get_tool_ids_by_language(dbConn, languages):
  try:
    if not languages:
      return set()

    cursor = dbConn.cursor()

    format_strings = ','.join(['%s'] * len(languages))

    sql = f"""
      SELECT tool_id
      FROM tools
      WHERE language IN ({format_strings})
    """

    cursor.execute(sql, languages)
    rows = cursor.fetchall()

    return set([r[0] for r in rows])

  except Exception as err:
    print("db.get_tool_ids_by_language() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# get_tool_ids_by_functions
#
def get_tool_ids_by_functions(dbConn, functions):
  try:
    if not functions:
      return set()

    cursor = dbConn.cursor()

    format_strings = ','.join(['%s'] * len(functions))

    sql = f"""
      SELECT DISTINCT tfm.tool_id
      FROM tool_function_map tfm
      JOIN functions f ON tfm.function_id = f.function_id
      WHERE f.sub IN ({format_strings})
    """

    cursor.execute(sql, functions)
    rows = cursor.fetchall()

    return set([r[0] for r in rows])

  except Exception as err:
    print("db.get_tool_ids_by_functions() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()
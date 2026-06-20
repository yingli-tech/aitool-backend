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
def get_taxonomy_context(dbConn):
  try:
    cursor = dbConn.cursor()

    cursor.execute("SELECT DISTINCT category FROM tools")
    categories = [row[0] for row in cursor.fetchall() if row[0] is not None]

    cursor.execute("SELECT price_type FROM price_types")
    price_types = [row[0] for row in cursor.fetchall() if row[0] is not None]

    cursor.execute("SELECT DISTINCT language FROM tools")
    languages = [row[0] for row in cursor.fetchall() if row[0] is not None]

    cursor.execute("""
      SELECT core, sub
      FROM use_cases
      ORDER BY core, sub
    """)
    use_cases = [
      {"core": row[0], "sub": row[1]}
      for row in cursor.fetchall()
      if row[0] is not None
    ]

    cursor.execute("""
      SELECT core, sub
      FROM functions
      ORDER BY core, sub
    """)
    functions = [
      {"core": row[0], "sub": row[1]}
      for row in cursor.fetchall()
      if row[0] is not None
    ]

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
def fetch_tool_details(dbConn, tool_ids):
  try:
    if not tool_ids:
      return []

    cursor = dbConn.cursor()
    format_strings = ",".join(["%s"] * len(tool_ids))

    sql = f"""
      SELECT tool_id, name, url, description, category, language
      FROM tools
      WHERE tool_id IN ({format_strings})
    """

    cursor.execute(sql, tool_ids)
    rows = cursor.fetchall()

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
# get_tool_ids_by_price_types
#
def get_tool_ids_by_price_types(dbConn, price_types):
  try:
    if not price_types:
      return set()

    cursor = dbConn.cursor()
    format_strings = ",".join(["%s"] * len(price_types))

    sql = f"""
      SELECT DISTINCT tpm.tool_id
      FROM tool_price_map tpm
      JOIN price_types pt ON tpm.price_type_id = pt.price_type_id
      WHERE LOWER(pt.price_type) IN ({format_strings})
    """

    cursor.execute(sql, price_types)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

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
    format_strings = ",".join(["%s"] * len(languages))

    sql = f"""
      SELECT tool_id
      FROM tools
      WHERE LOWER(language) IN ({format_strings})
    """

    cursor.execute(sql, languages)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

  except Exception as err:
    print("db.get_tool_ids_by_language() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


###############################################################
# Taxonomy lookup helpers
#
def get_tool_ids_by_use_case_cores(dbConn, cores):
  return _get_tool_ids_by_taxonomy_cores(
    dbConn=dbConn,
    mapping_table="tool_usecase_map",
    mapping_id_column="usecase_id",
    taxonomy_table="use_cases",
    taxonomy_id_column="usecase_id",
    cores=cores
  )


def get_tool_ids_by_function_cores(dbConn, cores):
  return _get_tool_ids_by_taxonomy_cores(
    dbConn=dbConn,
    mapping_table="tool_function_map",
    mapping_id_column="function_id",
    taxonomy_table="functions",
    taxonomy_id_column="function_id",
    cores=cores
  )


def get_tool_ids_by_use_case_tag(dbConn, tag):
  return _get_tool_ids_by_taxonomy_tag(
    dbConn=dbConn,
    mapping_table="tool_usecase_map",
    mapping_id_column="usecase_id",
    taxonomy_table="use_cases",
    taxonomy_id_column="usecase_id",
    tag=tag
  )


def get_tool_ids_by_function_tag(dbConn, tag):
  return _get_tool_ids_by_taxonomy_tag(
    dbConn=dbConn,
    mapping_table="tool_function_map",
    mapping_id_column="function_id",
    taxonomy_table="functions",
    taxonomy_id_column="function_id",
    tag=tag
  )


def _get_tool_ids_by_taxonomy_cores(
  dbConn,
  mapping_table,
  mapping_id_column,
  taxonomy_table,
  taxonomy_id_column,
  cores
):
  try:
    normalized_cores = [core for core in cores if core]
    if not normalized_cores:
      return set()

    cursor = dbConn.cursor()
    format_strings = ",".join(["%s"] * len(normalized_cores))

    sql = f"""
      SELECT DISTINCT tm.tool_id
      FROM {mapping_table} tm
      JOIN {taxonomy_table} tax
        ON tm.{mapping_id_column} = tax.{taxonomy_id_column}
      WHERE LOWER(tax.core) IN ({format_strings})
    """

    cursor.execute(sql, normalized_cores)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

  except Exception as err:
    print("db._get_tool_ids_by_taxonomy_cores() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()


def _get_tool_ids_by_taxonomy_tag(
  dbConn,
  mapping_table,
  mapping_id_column,
  taxonomy_table,
  taxonomy_id_column,
  tag
):
  try:
    core = (tag.get("core") or "").strip().lower()
    sub = tag.get("sub")
    sub = sub.strip().lower() if isinstance(sub, str) else None

    if not core and not sub:
      return set()

    cursor = dbConn.cursor()

    sql = f"""
      SELECT DISTINCT tm.tool_id
      FROM {mapping_table} tm
      JOIN {taxonomy_table} tax
        ON tm.{mapping_id_column} = tax.{taxonomy_id_column}
      WHERE 1 = 1
    """

    params = []

    if core:
      sql += " AND LOWER(tax.core) = %s"
      params.append(core)

    if sub:
      sql += " AND LOWER(tax.sub) = %s"
      params.append(sub)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

  except Exception as err:
    print("db._get_tool_ids_by_taxonomy_tag() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()

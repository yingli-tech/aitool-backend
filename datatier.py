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

    cursor.execute("SELECT language FROM languages ORDER BY language")
    languages = [row[0] for row in cursor.fetchall() if row[0] is not None]

    cursor.execute("""
      SELECT primary_tag, secondary_tag
      FROM use_cases
      ORDER BY primary_tag, secondary_tag
    """)
    use_cases = [
      {"primary_tag": row[0], "secondary_tag": row[1]}
      for row in cursor.fetchall()
      if row[0] is not None
    ]

    cursor.execute("""
      SELECT primary_tag, secondary_tag
      FROM functions
      ORDER BY primary_tag, secondary_tag
    """)
    functions = [
      {"primary_tag": row[0], "secondary_tag": row[1]}
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
      SELECT
        t.tool_id,
        t.name,
        t.url,
        t.description,
        t.category,
        GROUP_CONCAT(
          DISTINCT l.language
          ORDER BY l.language
          SEPARATOR '||'
        ) AS languages
      FROM tools t
      LEFT JOIN tool_language_map tlm
        ON t.tool_id = tlm.tool_id
      LEFT JOIN languages l
        ON tlm.language_id = l.language_id
      WHERE t.tool_id IN ({format_strings})
      GROUP BY t.tool_id, t.name, t.url, t.description, t.category
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
        "languages": row[5].split("||") if row[5] else []
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
      SELECT DISTINCT tlm.tool_id
      FROM tool_language_map tlm
      JOIN languages l
        ON tlm.language_id = l.language_id
      WHERE LOWER(l.language) IN ({format_strings})
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
def get_tool_ids_by_use_case_primary_tags(dbConn, primary_tags):
  return _get_tool_ids_by_taxonomy_primary_tags(
    dbConn=dbConn,
    mapping_table="tool_usecase_map",
    mapping_id_column="usecase_id",
    taxonomy_table="use_cases",
    taxonomy_id_column="usecase_id",
    primary_tags=primary_tags
  )


def get_tool_ids_by_function_primary_tags(dbConn, primary_tags):
  return _get_tool_ids_by_taxonomy_primary_tags(
    dbConn=dbConn,
    mapping_table="tool_function_map",
    mapping_id_column="function_id",
    taxonomy_table="functions",
    taxonomy_id_column="function_id",
    primary_tags=primary_tags
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


def _get_tool_ids_by_taxonomy_primary_tags(
  dbConn,
  mapping_table,
  mapping_id_column,
  taxonomy_table,
  taxonomy_id_column,
  primary_tags
):
  try:
    normalized_primary_tags = [tag for tag in primary_tags if tag]
    if not normalized_primary_tags:
      return set()

    cursor = dbConn.cursor()
    format_strings = ",".join(["%s"] * len(normalized_primary_tags))

    sql = f"""
      SELECT DISTINCT tm.tool_id
      FROM {mapping_table} tm
      JOIN {taxonomy_table} tax
        ON tm.{mapping_id_column} = tax.{taxonomy_id_column}
      WHERE LOWER(tax.primary_tag) IN ({format_strings})
    """

    cursor.execute(sql, normalized_primary_tags)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

  except Exception as err:
    print("db._get_tool_ids_by_taxonomy_primary_tags() failed:")
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
    primary_tag = (tag.get("primary_tag") or "").strip().lower()
    secondary_tag = tag.get("secondary_tag")
    secondary_tag = (
      secondary_tag.strip().lower()
      if isinstance(secondary_tag, str)
      else None
    )

    if not primary_tag and not secondary_tag:
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

    if primary_tag:
      sql += " AND LOWER(tax.primary_tag) = %s"
      params.append(primary_tag)

    if secondary_tag:
      sql += " AND LOWER(tax.secondary_tag) = %s"
      params.append(secondary_tag)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    return {r[0] for r in rows}

  except Exception as err:
    print("db._get_tool_ids_by_taxonomy_tag() failed:")
    print(str(err))
    raise

  finally:
    cursor.close()

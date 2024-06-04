import pyodbc
import pandas as pd
import sys
import os
from pathlib import Path
import numpy as np
import yaml

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

#from auto_description import describe_table
#from correlation import correlation_embedding
def get_constraints(db_name, table_name, schema_name, connection):
    query = f"""
    SELECT
        tc.constraint_name,
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name,
        tc.constraint_type as constraint_type
    FROM
        information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
    WHERE
        tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
        AND tc.table_catalog = '{db_name}'
        AND tc.table_name = '{table_name}'
        AND tc.table_schema = '{schema_name}'
    ORDER BY
        tc.table_name, kcu.ordinal_position;
    """
    return pd.read_sql(query, connection)
def get_table_names(db_name, connection):
    query = f"""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE
        table_catalog = '{db_name}'
        AND table_type = 'BASE TABLE'
    """
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        tables = cursor.fetchall()
        return [(row.table_schema, row.table_name) for row in tables]
    except Exception as e:
        print(f"An error occurred: {e}")
def get_columns(db_name, table_name, schema_name, connection):
    query = f"""
    SELECT
        table_name,
        column_name,
        data_type
    FROM
        information_schema.columns
    WHERE
        table_catalog = '{db_name}'
        AND table_name = '{table_name}'
        AND table_schema = '{schema_name}'
    ORDER BY
        table_name, ordinal_position;
    """
    try:
        data_frame = pd.read_sql(query, connection)
        if data_frame.empty:
            print(f"No columns found in table '{table_name}' within the '{db_name}' database.")
        return data_frame
    except Exception as e:
        print(f"An error occurred: {e}")

def get_connection(host, username, password, db_name=None):
    if db_name is None:
        connection_str = f"DRIVER=ODBC Driver 17 for SQL Server;SERVER={host};UID={username};PWD={password}"
    else:
        connection_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host};DATABASE={db_name};UID={username};PWD={password}'
    try:
        connection = pyodbc.connect(connection_str)
        return connection
    except Exception as e:
        print(f"An error occurred while connecting to the database: {e}")
        return None
    
def get_connection_with_connection_string(connection_string, db_name=None):
    if db_name is not None:
        connection_string += f';DATABASE={db_name}'
    try:
        connection = pyodbc.connect(connection_string)
        return connection
    except Exception as e:
        print(f"An error occurred while connecting to the database: {e}")
        return None
    
def get_all_databases(connection):
    try:
        cursor = connection.cursor()
        # Exclude system databases
        query = "SELECT name FROM sys.databases WHERE database_id > 4"
        cursor.execute(query)
        # Fetch all user database names
        databases = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return databases
    except Exception as e:
        print(f"An error occurred while fetching databases: {e}")
        return []
def azure_to_yamls(host, username, password):
    connection = get_connection(host, username, password, None)
    databases = get_all_databases(connection)
    yamls = []
    for db_name in databases:
        connection = get_connection(host, username, password, db_name)
        table_schemas = get_table_names(db_name, connection)
        for schema_name, table_name in table_schemas:
            columns = get_columns(db_name, table_name, schema_name, connection)
            #description = describe_table(str(columns))
            constraints = get_constraints(db_name, table_name, schema_name, connection)
            primary_keys = constraints[constraints["constraint_type"] == "PRIMARY KEY"]["column_name"].tolist()
            foreign_keys = constraints[constraints["constraint_type"] == "FOREIGN KEY"]
            dimensions = []
            for _, row in columns.iterrows():
                column = {"name": row["column_name"], "type": row["data_type"], "sql": row["column_name"]}
                column_name = row['column_name']
                # To handle special characters
                quoted_column_name = f'"{column_name}"'
                query = f"SELECT {quoted_column_name} FROM \"{schema_name}\".\"{table_name}\""
                column_data = pd.read_sql(query, connection)
                # if row["data_type"] in ('float', 'double', 'int'):
                #     column["embedding"] = correlation_embedding(column_data[column_name].values)
                if row["column_name"] in primary_keys:
                    column["primary_key"] = True
                elif row["column_name"] in foreign_keys["column_name"].tolist():
                    column["foreign_key"] = True
                dimensions.append(column)
            joins = []
            for _, fk_row in foreign_keys.iterrows():
                join = {
                    "name": fk_row["foreign_table_name"],
                    "sql": f"{{{table_name}}}.{fk_row['column_name']} = {{{fk_row['foreign_table_name']}}}.{fk_row['foreign_column_name']}"
                }
                joins.append(join)
            yaml_structure = {
                "name": table_name,
                "schema": schema_name,
                "sql_name": f"{db_name}.{schema_name}.{table_name}",
                "dimensions": dimensions,
                **({"joins": joins} if joins else {}),
                "description": ""
            }
            yamls.append(yaml_structure)

            yaml_str = yaml.dump(yaml_structure, default_flow_style=None, sort_keys=False)
            os.makedirs(f"models/azure/yamls", exist_ok=True)
            # with open(f"models/azure/yamls/{table}.yaml", 'w') as yaml_file:
            #     yaml_file.write(yaml_str)

    connection.close()
    return yamls

def azure_to_yamls_with_connection_string(connection_string):
    connection = get_connection_with_connection_string(connection_string)
    databases = get_all_databases(connection)
    yamls = []
    for db_name in databases:
        connection = get_connection_with_connection_string(connection_string, db_name)
        table_schemas = get_table_names(db_name, connection)
        for schema_name, table_name in table_schemas:
            columns = get_columns(db_name, table_name, schema_name, connection)
            constraints = get_constraints(db_name, table_name, schema_name, connection)
            primary_keys = constraints[constraints["constraint_type"] == "PRIMARY KEY"]["column_name"].tolist()
            foreign_keys = constraints[constraints["constraint_type"] == "FOREIGN KEY"]
            dimensions = []
            for _, row in columns.iterrows():
                column = {"name": row["column_name"], "type": row["data_type"], "sql": row["column_name"]}
                column_name = row['column_name']
                quoted_column_name = f'"{column_name}"'
                query = f"SELECT {quoted_column_name} FROM \"{schema_name}\".\"{table_name}\""
                column_data = pd.read_sql(query, connection)
                if row["column_name"] in primary_keys:
                    column["primary_key"] = True
                elif row["column_name"] in foreign_keys["column_name"].tolist():
                    column["foreign_key"] = True
                dimensions.append(column)
            joins = []
            for _, fk_row in foreign_keys.iterrows():
                join = {
                    "name": fk_row["foreign_table_name"],
                    "sql": f"{{{table_name}}}.{fk_row['column_name']} = {{{fk_row['foreign_table_name']}}}.{fk_row['foreign_column_name']}"
                }
                joins.append(join)
            yaml_structure = {
                "name": table_name,
                "schema": schema_name,
                "sql_name": f"{db_name}.{schema_name}.{table_name}",
                "dimensions": dimensions,
                **({"joins": joins} if joins else {}),
                "description": ""
            }
            yamls.append(yaml_structure)

            yaml_str = yaml.dump(yaml_structure, default_flow_style=None, sort_keys=False)
            os.makedirs(f"models/azure/yamls", exist_ok=True)

    connection.close()
    return yamls

if __name__ == "__main__":
    host="arvoserver.database.windows.net"
    user="CloudSAcc8c3958"
    password="Myarvodatabase24"

    yaml = azure_to_yamls(host, user, password)

    for i in yaml:
        print(i)
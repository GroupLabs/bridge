import pandas as pd
import psycopg2
import os
import yaml
import sys
from pathlib import Path
import json

# Get the absolute path of the parent directory
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from auto_description import describe_table
# from .correlation import correlation_embedding

# Function to fetch constraints data, adapted for PostgreSQL
def get_constraints(db_name, table_name, conn):
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
    ORDER BY
        tc.table_name, kcu.ordinal_position;
    """
    return pd.read_sql(query, conn)

def get_tables(db_name, conn):
    query = f"""SELECT *
    FROM
        information_schema.tables
    WHERE
        table_catalog = '{db_name}' 
        AND table_schema = 'public' """
        
    try:
        df = pd.read_sql(query, conn)
        if df.empty:
            print(f"No tables found in database '{db_name}' within the 'public' schema.")
        else:
            print(f"Tables found")
        return df
    except Exception as e:
        print(f"An error occurred: {e}")

def get_columns(db_name, table_name, conn):
    query = f"""
    SELECT
        table_name,
        column_name,
        data_type
    FROM
        information_schema.columns
    WHERE
        table_catalog = '{db_name}' AND table_name = '{table_name}'
    ORDER BY
        table_name, ordinal_position;
    
    """
    try:
        df = pd.read_sql(query, conn)
        if df.empty:
            print(f"No columns found in table '{table_name}' within the 'public' schema.")
        return df
    except Exception as e:
        print(f"An error occurred: {e}")

# Function to fetch tables and columns data, adapted for PostgreSQL
# def get_tables_and_columns(db_name):
#     query = f"""
#     SELECT
#         table_name,
#         column_name,
#         data_type
#     FROM
#         information_schema.columns
#     WHERE
#         table_schema = '{db_name}'
#     ORDER BY
#         table_name, ordinal_position;
#     """
#     return pd.read_sql(query, conn)
        

def postgres_to_yamls(host, user, password):
    conn = psycopg2.connect(
        host=host,
        user=user,
        password=password
    )

    # Example of listing all databases in PostgreSQL (requires different approach)
    cur = conn.cursor()
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    all_dbs = cur.fetchall()
    all_dbs = [db[0] for db in all_dbs if db[0] != "postgres"]

    # You can then filter out system databases and process your databases as in the original script
    # Note: PostgreSQL does not have a direct equivalent to MySQL's SHOW DATABASES, and listing databases might require connecting to a specific database first.

    # Ensure to replace `SHOW DATABASES` and other MySQL-specific functions or queries with their PostgreSQL equivalents.

    # Note: This code assumes you have the necessary privileges to access the listed databases and their schemas.

    yamls = []

    for db in all_dbs:
                
        conn = psycopg2.connect(dbname=db, user=user, password=password, host=host)
        
        temp_sys_table = get_tables(db, conn)
        tables = temp_sys_table.loc[:, "table_name"].values.tolist() 

        print(tables)
        
        for table in tables:
            columns = get_columns(db_name=db, table_name=table, conn=conn)
            description = describe_table(str(columns))
            constraints = get_constraints(db_name=db, table_name=table, conn=conn)
            primary_keys = constraints[constraints["constraint_type"] == "PRIMARY KEY"]["column_name"].tolist()
            foreign_keys = constraints[constraints["constraint_type"] == "FOREIGN KEY"]
            
            dimensions = []
            for _, row in columns.iterrows():
                column = {"name": row["column_name"], "type": row["data_type"], "sql": row["column_name"]}

                # Before running the query, ensure the column name is correctly formatted
                column_name = row['column_name']
                quoted_column_name = f'"{column_name}"'  # Enclose the column name in double quotes

                # Use the quoted column name in the SQL query
                query = f"SELECT {quoted_column_name} FROM \"{table}\""
                column_data = pd.read_sql(query, conn)

                # Then use the original column name to access the data, assuming it's correctly cased in `row['column_name']`
                # column["embedding"] = correlation_embedding(column_data[column_name].values)

                if row["column_name"] in primary_keys:
                    column["primary_key"] = True
                elif row["column_name"] in foreign_keys["column_name"].tolist():
                    column["foreign_key"] = True
                dimensions.append(column)
                
            joins = []
            for _, fk_row in foreign_keys.iterrows():
                join = {
                    "name": fk_row["foreign_table_name"],
                    "sql": f"{{{table}}}.{fk_row['column_name']} = {{{fk_row['foreign_table_name']}}}.{fk_row['foreign_column_name']}"
                }
                joins.append(join)

            yaml_structure = {
                "name": table,
                "sql_name": f"{db}.{table}",
                "dimensions": dimensions,
                **({"joins": joins} if joins else {}),
                "description": description
            }

            yamls.append(yaml_structure)

            yaml_str = yaml.dump(yaml_structure, default_flow_style=None, sort_keys=False)
            os.makedirs(f"models/postgres/yamls", exist_ok=True)
            with open(f"models/postgres/yamls/{table}.yaml", 'w') as yaml_file:
                yaml_file.write(yaml_str)

    conn.close()

    return yamls



def postgres_to_dicts(host, user, password):
    conn = psycopg2.connect(
        host=host,
        user=user,
        password=password
    )

    # Example of listing all databases in PostgreSQL (requires different approach)
    cur = conn.cursor()
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    all_dbs = cur.fetchall()
    all_dbs = [db[0] for db in all_dbs if db[0] != "postgres"]

    # You can then filter out system databases and process your databases as in the original script
    # Note: PostgreSQL does not have a direct equivalent to MySQL's SHOW DATABASES, and listing databases might require connecting to a specific database first.

    # Ensure to replace `SHOW DATABASES` and other MySQL-specific functions or queries with their PostgreSQL equivalents.

    # Note: This code assumes you have the necessary privileges to access the listed databases and their schemas.

    yamls = []

    for db in all_dbs:
                
        conn = psycopg2.connect(dbname=db, user=user, password=password, host=host)
        
        temp_sys_table = get_tables(db, conn)
        tables = temp_sys_table.loc[:, "table_name"].values.tolist() 

        print(tables)
        
        for table in tables:
            columns = get_columns(db_name=db, table_name=table, conn=conn)
            description = describe_table(str(columns))
            constraints = get_constraints(db_name=db, table_name=table, conn=conn)
            primary_keys = constraints[constraints["constraint_type"] == "PRIMARY KEY"]["column_name"].tolist()
            foreign_keys = constraints[constraints["constraint_type"] == "FOREIGN KEY"]
            
            dimensions = []
            for _, row in columns.iterrows():
                column = {"name": row["column_name"], "type": row["data_type"], "sql": row["column_name"]}

                # Before running the query, ensure the column name is correctly formatted
                column_name = row['column_name']
                quoted_column_name = f'"{column_name}"'  # Enclose the column name in double quotes

                # Use the quoted column name in the SQL query
                query = f"SELECT {quoted_column_name} FROM \"{table}\""
                column_data = pd.read_sql(query, conn)

                # Then use the original column name to access the data, assuming it's correctly cased in `row['column_name']`
                # column["embedding"] = correlation_embedding(column_data[column_name].values) # Assuming the output can be converted to a list

                if row["column_name"] in primary_keys:
                    column["primary_key"] = True
                elif row["column_name"] in foreign_keys["column_name"].tolist():
                    column["foreign_key"] = True
                dimensions.append(column)
                
            joins = []
            for _, fk_row in foreign_keys.iterrows():
                join = {
                    "name": fk_row["foreign_table_name"],
                    "sql": f"{{{table}}}.{fk_row['column_name']} = {{{fk_row['foreign_table_name']}}}.{fk_row['foreign_column_name']}"
                }
                joins.append(join)

            yaml_structure = {
                "name": table,
                "sql_name": f"{db}.{table}",
                "dimensions": dimensions,
                **({"joins": joins} if joins else {}),
                "description": description
            }

            yamls.append(yaml_structure)

    conn.close()

    return yamls

# TODO: finish this. current format is not croissant supported   
def postgres_to_croissant(host, user, password, auto_describe=True):
    # Connect to PostgreSQL server
    conn = psycopg2.connect(host=host, user=user, password=password)
    cur = conn.cursor()
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    all_dbs = cur.fetchall()
    all_dbs = [db[0] for db in all_dbs if db[0] != "postgres"]

    croissant_metadata_list = []

    for db in all_dbs:
        conn = psycopg2.connect(dbname=db, user=user, password=password, host=host)
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = cur.fetchall()
        tables = [table[0] for table in tables]

        for table in tables:
            cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table}'")
            columns = cur.fetchall()

            dimensions = []
            for column_name, data_type in columns:
                quoted_column_name = f'"{column_name}"'  # Enclose the column name in double quotes

                # Use the quoted column name in the SQL query
                query = f"SELECT {quoted_column_name} FROM \"{table}\""
                column_data = pd.read_sql(query, conn)

                # Then use the original column name to access the data, assuming it's correctly cased in `row['column_name']`
                # embedding = correlation_embedding(column_data[column_name].values, 10)

                column_data = {
                    "name": column_name,
                    "type": data_type,
                    # "emb": embedding
                    # "sql": column_name,  # SQL property seems unnecessary for Croissant format
                    # embedding logic should be defined here if needed
                }
                dimensions.append(column_data)

            description = describe_table(str(columns)) if auto_describe else ""

            croissant_table_metadata = {
                "@type": "sc:Dataset",
                "name": table,
                "description": description,
                "recordSet": [{
                    "@type": "cr:RecordSet",
                    "name": f"{table}_records",
                    "field": dimensions
                }]
            }

            with open('croissant_metadata.json', 'w') as file:
                file.write(json.dumps(croissant_table_metadata, indent=2))

            
            croissant_metadata_list.append(croissant_table_metadata)

    conn.close()

    # Convert the metadata list to JSON
    return json.dumps(croissant_metadata_list, indent=2)


if __name__ == "__main__":
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(".env"))

    host="localhost"
    user=os.getenv("PG_USER")
    password=os.getenv("PG_PWD")

    croissant = postgres_to_croissant(host, user, password, False)

    print(croissant)

    
#TESTING AZURE VM

# hostname = '20.42.102.160'
# database = 'postgres'
# username = 'postgres'
# password = 'password'
# port_id = 5432  # Default PostgreSQL port is 5432

# # Establishing the connection
# conn = psycopg2.connect(
#     database=database,
#     user=username,
#     password=password,
#     host=hostname,
#     port=port_id
# )

# # Create a cursor object
# cur = conn.cursor()

# # Execute a query
# cur.execute('SELECT version();')

# # Fetch and print the result
# db_version = cur.fetchone()
# print(db_version)

# # Close the cursor and connection
# cur.close()
# conn.close()
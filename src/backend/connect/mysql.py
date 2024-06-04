# IMPLEMENTED - NEED TO CHANGE CREDENTIALS TO ENV VARS

import pandas as pd
import mysql.connector
import os
import yaml
import sys
from pathlib import Path

# Get the absolute path of the parent directory
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# from auto_description import desc_gen

# Function to fetch constraints data
def get_constraints(db_name, mydb):
    query = f"""
    SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM KEY_COLUMN_USAGE 
    WHERE TABLE_SCHEMA = '{db_name}'
    ORDER BY TABLE_NAME, ORDINAL_POSITION;
    """
    return pd.read_sql(query, mydb)

# Function to fetch tables and columns data
def get_tables_and_columns(db_name, mydb):
    query = f"""
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE 
    FROM COLUMNS 
    WHERE TABLE_SCHEMA = '{db_name}'
    ORDER BY TABLE_NAME, ORDINAL_POSITION;
    """
    return pd.read_sql(query, mydb)

def mysql_to_yamls(host, user, password):
    # Establish database connection using environment variables // TESTING W AZURE VM
    mydb = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database="information_schema"  # Use the information_schema database for metadata queries
    )

    # Main database for the process // EXCLUDED sys 'world' db for azure vm testing
    system_mysql_dbs = ['information_schema', 'mysql', 'performance_schema','sakila','sys']

    all_dbs = pd.read_sql("SHOW DATABASES", mydb)
    all_dbs = all_dbs['Database'].values.tolist()

    dbs_to_process = [db for db in all_dbs if db not in system_mysql_dbs]

    yamls = []

    for db_name in dbs_to_process:

        # Fetching necessary data
        df = get_tables_and_columns(db_name, mydb)
        df_constraints = get_constraints(db_name, mydb)
        df.columns = df.columns.str.lower()
        df_constraints.columns = df_constraints.columns.str.lower()

        # Process and create a YAML structure for each table
        tables = df['table_name'].unique()
        for table in tables:        
            table_df = df[df['table_name'] == table]
            # description = desc_gen(table_df)
            table_constraints_df = df_constraints[df_constraints['table_name'] == table]
            primary_keys = table_constraints_df[table_constraints_df['constraint_name'] == 'PRIMARY']['column_name'].tolist()
            foreign_keys = table_constraints_df[table_constraints_df['constraint_name'] != 'PRIMARY']

            dimensions = []
            for _, row in table_df.iterrows():
                column = {"name": row["column_name"], "type": row["data_type"], "sql": row["column_name"]}
                if row["column_name"] in primary_keys:
                    column["primary_key"] = True
                elif row["column_name"] in foreign_keys['column_name'].values:
                    column["foreign_key"] = True
                dimensions.append(column)

            joins = []
            for _, fk_row in foreign_keys.iterrows():
                join = {
                    "name": fk_row["referenced_table_name"],
                    "sql": f"{{{table}}}.{fk_row['column_name']} = {{{fk_row['referenced_table_name']}}}.{fk_row['referenced_column_name']}"
                }
                joins.append(join)

            yaml_structure = {
                "name": table,
                "sql_name": f"{db_name}.{table}",
                "dimensions": dimensions,
                **({"joins": joins} if joins else {}),
                # "description":description
            }

            yamls.append(yaml_structure)
            
            yaml_str = yaml.dump(yaml_structure, default_flow_style=False, sort_keys=False)
            os.makedirs("models/yamls", exist_ok=True)
            with open(f"models/yamls/{table}_yaml.yaml", 'w') as yaml_file:
                yaml_file.write(yaml_str)

    # Closing the database connection
    mydb.close()
    
    return yamls

if __name__ == "__main__":

    host="20.42.102.160"
    user='root'
    password="password"

    mysql_to_yamls(host, user, password)

# TO DO - ADD DESCRIPTIONS
# TO DO - ADD ERROR HANDLING, RUN THROUGH ALL DBs, NOT JUST ONE

#TESTIN

# config = {
#   'user': 'root',
#   'password': 'password',
#   'host': '20.42.102.160',  # Or your server's IP address/domain if remote
#   'database': 'world',
#   'raise_on_warnings': True
# }

# try:
#     cnx = mysql.connector.connect(**config)
#     print("Connection successful")
# except mysql.connector.Error as err:
#     print(f"Error: {err}")
    




























# import pandas as pd
# import numpy as np
# import mysql.connector
# import pandas.io.sql as psql
# import os
# import yaml

# mydb = mysql.connector.connect(
#     host = "localhost",
#     user = os.getenv("DB_USER"),
#     password = os.getenv("DB_PWD")
# )

# mycursor = mydb.cursor()

### GET ALL DBs
# mycursor.execute("SHOW DATABASES")

# server_dbs = []

# for db in mycursor:
#     server_dbs.append(db[0])

### GET TABLES FOR EACH DB

#tables_in_db = []

#just for testing purposes, I'm using just one database, for simplicity sake
# server_dbs = []
# server_dbs.append("localdb")

# for db in server_dbs:
    
#     mycursor.execute(f"USE {db}")
#     mycursor.execute("SHOW tables")
    
#     db_name = db
    
#     tables = []
    
#     for table in mycursor:
#         tables.append(table[0])
        #print(table[0])
        
    # temp_dict = {db_name:tables}
    
    # tables_in_db.append(temp_dict)

### CREATE YAML STRUCTURE FOR TABLES+COLUMNS

# for db_table_pair in tables_in_db:
    
#     for key in db_table_pair:
        
#         for table in db_table_pair[key]:
            
            #mycursor.execute("USE information_schema")

            # sql_query = f"""
            #                  SELECT * 
            #                  FROM information_schema.columns
            #                  WHERE table_schema = '{key}' AND table_name = '{table}' 
            #                     """
            
            # query_df = pd.read_sql(sql_query, mydb)
            # print(query_df.head())
            
            # dimensions_name = []
            # dimensions_type = []
            # dimensions_sql = []
            
            #dimensions_arr = []
            
            #for i in range(0, len(query_df["COLUMN_NAME"])-1):
                # dimensions_name.append(query_df[["COLUMN_NAME"]].iloc[i].values[i])
                # dimensions_type.append(query_df[["COLUMN_TYPE"]].iloc[i].values[i])
                # dimensions_sql.append(query_df[["COLUMN_NAME"]].iloc[i].values[i])
                
            #     dimensions_arr.append({"name":query_df[["COLUMN_NAME"]].iloc[i].values[0], "type":query_df[["COLUMN_TYPE"]].iloc[i].values[0], "sql":query_df[["COLUMN_NAME"]].iloc[i].values[0]})                
            
            # yaml_structure = {
            #     "name": table,
            #     "sql_name": key + "." + table,
            #     "dimensions": dimensions_arr
            # }
            
            # yaml_str = yaml.dump(yaml_structure, default_flow_style=False, sort_keys=False)
            
            # with open(fr"yamls/{table}_yaml.yaml", 'w') as yaml_file:
            #     yaml_file.write(yaml_str)
            
            # yaml_file = f"""
            #     name: {table}
            #     sql_name: {key}"."{table}
            #     """
            # for col in range(0, len(query_df["COLUMNS_NAME"])):
                
            #     yaml_file = yaml_file + "\n" 
            #test
    
    #print(db_table_pair[0], db_table_pair[0])




# mycursor.close()
# mydb.close()



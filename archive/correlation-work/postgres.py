import psycopg2
import os
import yaml

def create_node(dbname, user):
    conn = psycopg2.connect(f"dbname={dbname} user={user}")
    cur = conn.cursor()

    columns_by_table = {}
    schema_data = {}

    cur.execute("""
        SELECT a.attrelid::regclass AS table_name, 
                a.attname AS column_name, 
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
        WHERE c.relkind IN ('r', 'v') AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attrelid, a.attnum
    """)
    rows = cur.fetchall()

    for table_name, column_name, data_type in rows:
        if table_name not in columns_by_table:
            columns_by_table[table_name] = {}
        columns_by_table[table_name][column_name] = data_type

    for table, columns in columns_by_table.items():
        schema_data[table] = {'columns': [], 'related_tables': []}
        for column, data_type in columns.items():
            schema_data[table]['columns'].append({'name': column, 'type': data_type})

    for table1, info1 in schema_data.items():
        for table2, info2 in schema_data.items():
            if table1 != table2:
                for col1 in info1['columns']:
                    for col2 in info2['columns']:
                        if col1['name'] == col2['name'] and col1['type'] == col2['type']:
                            schema_data[table1]['related_tables'].append(table2)
                            break
                        
    db_dir = dbname 
    metadata_subdir = os.path.join(db_dir, 'metadata') 

    os.makedirs(metadata_subdir, exist_ok=True)

    for schema, data in schema_data.items():
        yaml_data = yaml.dump({schema: data}, sort_keys=False)

        if schema.startswith('pg_') or schema.startswith('information_schema'):
            filepath = os.path.join(metadata_subdir, f"{schema}.yaml")
        else:
            filepath = os.path.join(db_dir, f"{schema}.yaml")


        with open(filepath, 'w') as f:
            f.write(yaml_data)

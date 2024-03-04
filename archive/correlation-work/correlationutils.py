import duckdb
import pandas as pd
import numpy as np

def simple_correlation(
        target_table,
        dbname = 'noelthomas',
        user = 'postgres',
        password = '',
        host = 'localhost',
        port = 5432
    ):

    node_name = "noelthomas"

    con = duckdb.connect(database=':memory:', read_only=False)

    con.execute("INSTALL postgres;")
    con.execute("LOAD postgres;")

    con.execute(f"""
    ATTACH 'dbname={dbname} user={user} host={host} port={port}' AS {node_name} (TYPE postgres);
    """)

    adjacency_list = {
        'target': ['missing_energy', 'lepton', 'jet', 'm'],
        'missing_energy': ['target', 'lepton', 'jet', 'm'],
        'lepton': ['target', 'missing_energy', 'jet', 'm'],
        'jet': ['target', 'missing_energy', 'lepton', 'm'],
        'm': ['target', 'missing_energy', 'lepton', 'jet']
    }

    visited = set()

    cursor = con.execute(f"SELECT * FROM {node_name}.{target_table}")
    query_result = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]

    target_df = pd.DataFrame(query_result, columns=column_names)

    visited.add(target_table)

    corr = {}

    for axis_0, axis_1 in adjacency_list.items():
        for table in axis_1:
            if table not in visited:
                cursor = con.execute(f"SELECT * FROM {node_name}.{table}")
                query_result = cursor.fetchall()
                column_names = [description[0] for description in cursor.description]

                df = pd.DataFrame(query_result, columns=column_names)

                df_joined = target_df.merge(df, on="index") # TODO: needs to be fixed

                df = pd.DataFrame(df_joined)

                # correlation matrix
                correlation_matrix = df.corr()

                np.fill_diagonal(correlation_matrix.values, np.nan)

                # average of correlation
                avg = correlation_matrix.stack().mean()

                corr[table] = (correlation_matrix, avg) # TODO: This takes way less time if the entire df is available at once

    return corr
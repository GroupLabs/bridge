import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(".env"))

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname = "PostgresTest",
    host="localhost",
    user=os.getenv("PG_USER"),
    password=os.getenv("PG_PWD")
)
cur = conn.cursor()

# Load and preprocess dataframes
sales_df = pd.read_csv("../data/Amazon Sale Report.csv")
sales_df.columns = sales_df.columns.str.strip()
cols_for_status_df = ["Order ID", "Date", "Status", "Fulfilment", "Sales Channel", "ship-service-level"]
sale_status = sales_df.loc[:, cols_for_status_df]
sale_description = sales_df.loc[:, [col for col in sales_df.columns if col not in cols_for_status_df]]
sale_description.drop("Unnamed: 22", axis=1, inplace=True)
sale_description["Order ID"] = sales_df["Order ID"]
sale_description.drop("index", axis=1, inplace=True)
cols_to_drop_desc = sale_description.columns[9:-1]
sale_description.drop(cols_to_drop_desc.tolist(), axis=1, inplace=True)

# Create tables in PostgreSQL
cur.execute("""
CREATE TABLE order_desc (
    Style TEXT, 
    SKU TEXT,
    Category TEXT,
    Size TEXT,
    ASIN TEXT,
    Courier_status TEXT,
    Qty TEXT,
    Currency TEXT,
    Amount FLOAT,
    Order_ID TEXT,
    Desc_ID SERIAL PRIMARY KEY)
""")

cur.execute("""
CREATE TABLE order_stat (
    Order_ID TEXT PRIMARY KEY, 
    Date TEXT,
    Status TEXT,
    Fulfilment TEXT,
    Sales_Channel TEXT,
    Ship_service_level TEXT,
    Desc_ID INT REFERENCES order_desc(Desc_ID))
""")

# Remember to commit your changes
conn.commit()

order_id = pd.Series(np.random.choice(range(0, len(sale_description)), len(sale_description), replace=False))

sale_description["Order ID"] = order_id
sale_status["Order ID"] = order_id

len(sale_description)

desc_id = pd.Series(np.random.choice(range(0, len(sale_description)*2), size = len(sale_description), replace = False))

sale_description["Description_ID"] = desc_id
sale_status["Description_ID"] = desc_id

for index, row in sale_description.iterrows():
    
    cur.execute("""INSERT INTO order_desc
                     (Style, SKU, Category, Size, ASIN, Courier_status, Qty, currency, Amount, Order_ID, Desc_ID) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                     , (row["Style"], row["SKU"], row["Category"], row["Size"], row["ASIN"], row["Courier Status"], row["Qty"], row["currency"], row["Amount"], row["Order ID"], row["Description_ID"]))

#sale_status["Description_ID"] = desc_id

for index, row in sale_status.iterrows():
    
    cur.execute("""INSERT INTO order_stat
                     (Order_ID, Date, Status, Fulfilment, Sales_Channel, Ship_Service_Level, Desc_ID) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                     , (row["Order ID"], row["Date"], row["Status"], row["Fulfilment"], row["Sales Channel"], row["ship-service-level"], row["Description_ID"]))
    
conn.commit()

# Close cursor and connection when done
cur.close()
conn.close()

import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
import os
from datasets import load_dataset
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\.env"))

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname = "PostgresTest",
    host="localhost",
    user=os.getenv("PG_USER"),
    password=os.getenv("PG_PWD")
)
cur = conn.cursor()



dataset = load_dataset("inria-soda/tabular-benchmark", data_files="reg_cat/house_sales.csv")
dataset = pd.DataFrame(dataset["train"])

house_id = pd.Series(np.random.choice(range(0, len(dataset)), len(dataset), replace=False))

houses_part1 = dataset.iloc[:, :9]
houses_part2 = dataset.iloc[:, 9:]

houses_part1["house_id"] = house_id
houses_part2["house_id_foreign"] = house_id

cur.execute("""
                    CREATE TABLE HOUSE_P1 (bedrooms INT, 
                    bathrooms float,
                    sqft_living int,
                    sqft_lot int,
                    waterfront int,
                    garde int,
                    sqft_above int,
                    sqft_basement int,
                    yr_built int,
                    house_id int primary key
                    )
                    """)

cur.execute("""
                    CREATE TABLE HOUSE_P2 (yr_renovated int, 
                    lat float,
                    long float,
                    sqft_living15 int,
                    sqft_lot15 int,
                    date_year int,
                    date_month int,
                    date_day int,
                    price float,
                    house_id_foreign int,
                    foreign key (house_id_foreign) references house_p1(house_id)
                    )
                    """)

for id, row in houses_part2.iterrows():
    
    cur.execute("""
                     INSERT INTO HOUSE_P2 (
                        yr_renovated,
                        lat, 
                        long, 
                        sqft_living15, 
                        sqft_lot15, 
                        date_year, 
                        date_month, 
                        date_day, 
                        price, 
                        house_id_foreign
                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)                     
                     """, (row["yr_renovated"], row["long"], row["lat"], row["sqft_living15"], row["sqft_lot15"], row["date_year"], row["date_month"], row["date_day"], row["price"], row["house_id_foreign"]))


for id, row in houses_part1.iterrows():
    cur.execute("""
                     
                     INSERT INTO HOUSE_P1 (
                         bedrooms, 
                         bathrooms,
                         sqft_living,
                         sqft_lot,
                         waterfront,
                         garde,
                         sqft_above,
                         sqft_basement,
                         yr_built,
                         house_id
                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,%s, %s)
                     
                     """, (row["bedrooms"], row["bathrooms"], row["sqft_living"], row["sqft_lot"], row["waterfront"], row["grade"], row["sqft_above"], row["sqft_basement"], row["yr_built"], row["house_id"]))

conn.commit()

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

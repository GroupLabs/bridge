import pandas as pd
import numpy as np
import mysql.connector
import os
from datasets import load_dataset
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(r"C:\Users\Eugene\Documents\GroupLabs\bridge\MySQL_Cubes_Nodes\.env"))

mydb = mysql.connector.connect(
    host = "localhost",
    user = os.getenv("DB_USER"),
    password = os.getenv("DB_PWD"),
    database = "LocalDB"
)

mycursor = mydb.cursor()

dataset = load_dataset("inria-soda/tabular-benchmark", data_files="reg_cat/house_sales.csv")
dataset = pd.DataFrame(dataset["train"])

house_id = pd.Series(np.random.choice(range(0, len(dataset)), len(dataset), replace=False))

houses_part1 = dataset.iloc[:, :9]
houses_part2 = dataset.iloc[:, 9:]

houses_part1["house_id"] = house_id
houses_part2["house_id_foreign"] = house_id

mycursor.execute("""
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

mycursor.execute("""
                    CREATE TABLE HOUSE_P2 (yr_renovated int, 
                    lat float,
                    `long` float,
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
    
    mycursor.execute("""
                     INSERT INTO HOUSE_P2 (
                        yr_renovated,
                        lat, 
                        `long`, 
                        sqft_living15, 
                        sqft_lot15, 
                        date_year, 
                        date_month, 
                        date_day, 
                        price, 
                        house_id_foreign
                     ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)                     
                     """, (row["yr_renovated"], row["long"], row["lat"], row["sqft_living15"], row["sqft_lot15"], row["date_year"], row["date_month"], row["date_day"], row["price"], row["house_id_foreign"]))

mydb.commit()

for id, row in houses_part1.iterrows():
    mycursor.execute("""
                     
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

sales_df = pd.read_csv(r"../data/Amazon Sale Report.csv")
sales_df.columns = sales_df.columns.str.strip()
cols_for_status_df = ["Order ID", "Date", "Status", "Fulfilment", "Sales Channel", "ship-service-level"]
sale_status = sales_df.loc[:, cols_for_status_df]
sale_description = sales_df.loc[:, [col for col in sales_df.columns if col not in cols_for_status_df]]
sale_description.drop("Unnamed: 22", axis = 1, inplace = True)
sale_description["Order ID"]  = sales_df["Order ID"]
sale_description.drop("index", axis = 1, inplace = True)
cols_to_drop_desc = sale_description.columns
cols_to_drop_desc = cols_to_drop_desc[9:-1]
sale_description.drop(cols_to_drop_desc.tolist(), axis = 1, inplace = True)



mycursor.execute("""
                    CREATE TABLE ORDER_DESC (Style VARCHAR(255), 
                    SKU VARCHAR(255),
                    Category VARCHAR(255),
                    Size VARCHAR(255),
                    ASIN VARCHAR(255),
                    Courier_status VARCHAR(255),
                    Qty VARCHAR(255),
                    currency VARCHAR(255),
                    Amount float,
                    Order_ID VARCHAR(255),
                    
                    Desc_ID int primary key)
                    """)

mycursor.execute("""
                    CREATE TABLE ORDER_STAT (
                    Order_ID VARCHAR(255) primary key, 
                    Date VARCHAR(255),
                    Status VARCHAR(255),
                    Fulfilment VARCHAR(255),
                    Sales_Channel VARCHAR(255),
                    ship_service_level VARCHAR(255),
                    Desc_ID int                
                    )
                    """)


mycursor.execute("""
                 ALTER TABLE ORDER_STAT
                 ADD CONSTRAINT fk_desc
                 foreign key (Desc_ID) references order_desc(Desc_ID)
                 """)

mycursor.execute("""
                 ALTER TABLE ORDER_DESC
                 ADD CONSTRAINT fk_stat
                 foreign key (Order_ID) references order_stat(Order_ID)
                 """)

mydb.commit()
# mycursor.execute("""
#                        CREATE TABLE Stocks (
#                             Date DATE,
#                             Natural_Gas_Price FLOAT,
#                             Natural_Gas_Vol INT,
#                             Crude_Oil_Price FLOAT,
#                             Crude_Oil_Vol INT,
#                             Copper_Price FLOAT,
#                             Copper_Vol INT 
#                        )
#                        """)


apples_df = pd.read_csv(r"data\apple_quality.csv")
apples_df = apples_df.iloc[:-1,:]
apples_df = apples_df.astype({"Acidity":"float"})

stocks_df = pd.read_csv(r"data\Stock Market Dataset.csv")
stocks_df.drop(["Unnamed: 0"], axis = 1, inplace = True)

for name in sale_description.columns:
    if sale_description[[name]].isna().sum()[0] >0:
        sale_description[[name]] = sale_description[[name]].fillna(method='bfill')

for name in sale_status.columns:
    if sale_status[[name]].isna().sum()[0] >0:
        sale_status[[name]] = sale_status[[name]].fillna(method='bfill')


for name in stocks_df.columns:
    if stocks_df[[name]].isna().sum()[0] >0:
        stocks_df[[name]] = stocks_df[[name]].fillna(method='bfill')

for index, el in stocks_df[["Date"]].iterrows():
    stocks_df["Date"][index] = pd.to_datetime(stocks_df["Date"][index])

stocks_df[["Date"]] = stocks_df[["Date"]].to_datetime()

for index, row in apples_df.iterrows():
    
    mycursor.execute("""INSERT INTO Apples 
                     (A_id, Size, Weight, Sweetness, Crunchiness, Juiciness, Ripeness, Acidity, Quality) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                     , (row["A_id"], row["Size"], row["Weight"], row["Sweetness"], row["Crunchiness"], row["Juiciness"], row["Ripeness"], row["Acidity"], row["Quality"]))
    
for index, row in stocks_df.iterrows():
    
    mycursor.execute("""INSERT INTO Stocks
                     (Date, Natural_Gas_Price, Natural_Gas_Vol, Crude_Oil_Price, Crude_Oil_Vol, Copper_Price, Copper_Vol) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                     , (row["Date"], row["Natural_Gas_Price"], row["Natural_Gas_Vol."], row["Crude_oil_Price"], row["Crude_oil_Vol."], row["Copper_Price"], row["Copper_Vol."]))

mycursor.execute("ALTER TABLE order_desc DROP FOREIGN KEY fk_stat")
mycursor.execute("""ALTER TABLE order_stat ADD CONSTRAINT 
                 FOREIGN KEY (Desc_ID) REFERENCES order_desc(Desc_ID)""")

mycursor.execute("DROP TABLE order_desc")
mydb.commit()    

order_id = pd.Series(np.random.choice(range(0, len(sale_description)), len(sale_description), replace=False))

sale_description["Order ID"] = order_id
sale_status["Order ID"] = order_id

len(sale_description)

desc_id = pd.Series(np.random.choice(range(0, len(sale_description)*2), size = len(sale_description), replace = False))

sale_description["Description_ID"] = desc_id

for index, row in sale_description.iterrows():
    
    mycursor.execute("""INSERT INTO order_desc
                     (Style, SKU, Category, Size, ASIN, Courier_status, Qty, currency, Amount, Order_ID, Desc_ID) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                     , (row["Style"], row["SKU"], row["Category"], row["Size"], row["ASIN"], row["Courier Status"], row["Qty"], row["currency"], row["Amount"], row["Order ID"], row["Description_ID"]))

#sale_status["Description_ID"] = desc_id

for index, row in sale_status.iterrows():
    
    mycursor.execute("""INSERT INTO order_stat
                     (Order_ID, Date, Status, Fulfilment, Sales_Channel, Ship_Service_Level, Desc_ID) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                     , (row["Order ID"], row["Date"], row["Status"], row["Fulfilment"], row["Sales Channel"], row["ship-service-level"], row["Description_ID"]))
    
mydb.commit()


df = mycursor.execute("SELECT * FROM localdb.apples")



mycursor.execute("SHOW SCHEMAS")

for x in mycursor:
    print(x)



mycursor.close()
mydb.close()




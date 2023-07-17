# Bridge

To run the API (from within src/ directory):
```
pip install -r requirements.txt
python api.py
```

Server will start at 8000, use Postman to hit the endpoints.

The objective of this project is to compile multiple dynamic data stores that can be queried semantically, and automatically builds relational understanding of information. Then, users are able to ask nearly anything about the data, including forecasts, and so forth.

## Ingestion
- Indexing : generate and store metadata about data sources. For example, if we have an employee table with columns [first_name,last_name,email,make,title,salary], we can generate the following:

    ```
    {
        "columns": [
            {
                "name": "first_name",
                "description": "The first name of the employee",
                "data_type": "string",
            },
            {
                "name": "last_name",
                "description": "The last name of the employee",
                "data_type": "string",
            },
            {
                "name": "email",
                "description": "The email address of the employee",
                "data_type": "string",
            },
            {
                "name": "make",
                "description": "The car make the employee prefers",
                "data_type": "string",
            },
            {
                "name": "title",
                "description": "The job title of the employee",
                "data_type": "string",
            },
            {
                "name": "salary",
                "description": "The annual salary of the employee in USD",
                "data_type": "string",
            }
        ],
        "unique_words": ["first_name", "last_name", "email", "make", "title", "salary"]
    }
    ```

By storing these JSONs, we have a representation of the data. We now know where to get certain columns when generating answers from tables. Notice the actual data (other than the column names) are never exposed. We can now also use semantic search over multiple metadata JSONs to figure out if any other tables have any semantic relationship. This can come in handy when tying togther information from multiple sources.

## Services

Consider the following use cases:

    1. Predictive Maintenance: The system can analyze sensor data from equipment and pipelines to predict potential failures or maintenance needs. This can significantly reduce downtime and repair costs.

    2. Supply and Demand Forecasting: By analyzing market data and trends, the system could predict future supply and demand. This would enable the company to optimize their operations and pricing.

    3. Operational Optimization: The system could identify inefficiencies in the transportation and storage of oil and gas. This could involve optimizing routes, schedules, or storage allocation.

    4. Risk Assessment: The system can analyze a variety of factors such as weather data, equipment status, and market conditions to assess risk levels. This could be used to prevent accidents or make informed business decisions.

    5. Regulatory Compliance: The system could monitor operations and data to ensure regulatory compliance. If any potential issues are identified, it could alert the relevant personnel.

    6. Energy Trading: The system could provide insights to assist with energy trading decisions. This might involve predicting future prices or identifying profitable trading opportunities.
    
    7. Customer Service: The system could answer questions from clients or partners about the status of shipments, prices, etc. It could also automate some aspects of contract management.

Each of them require some specific service. For example, predictive maintainence (1) and supply and demand forecasting (2) could use a forecasting service that analyzes the supplied data, and figures out any trends that could be insightful for the user. Risk assessment (4) could use a tabular classification service that categorizes risk based on certain factors.

Optimally, model training will happen in the background, and not on demand. Once models are trained, they will be able to answer questions like forecasts as inferences.

Here are some potential services:

- Anomaly detection
- Forecasting
- Clustering

## Complete solutions:

- [x] Answer questions from visible text documents
- [x] Generate and execute python code on visible CSVs
- [] Generating metadata, indexing
- [] Calling services
- [] ML services




### Features
- Never exposes actual data
- Self manages models (improves over time, corrects, etc.)


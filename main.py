import logging
from fastapi import FastAPI, HTTPException, Depends
from typing import Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from database import SingletonSQLDatabase
from custom_datatypes import ModelInput
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, SystemMessage
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

import os
load_dotenv()
# OpenAI API Key
# openai_api_key = os.getenv("OPEN_API_KEY")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")

# Initialize FastAPI application
app = FastAPI()
# Function to keep the database connection alive
def keep_connection_alive():
    try:
        db = SingletonSQLDatabase.get_instance()  # Get the singleton database instance
        db.run("SELECT 1")  # Execute a simple query to keep the connection alive
        logging.info("Database connection kept alive.")
    except Exception as e:
        logging.error("Error in keep_connection_alive:", exc_info=True)

# Initialize APScheduler
scheduler = BackgroundScheduler()

# Schedule the keep_connection_alive task to run every 10 seconds
scheduler.add_job(keep_connection_alive, 'interval', seconds=999999)

# Function to get the database connection via dependency injection
def get_db_connection():
    return SingletonSQLDatabase.get_instance()

# The main query handler function
@app.post("/query/")
async def handle_query(userinput: ModelInput, db: SQLDatabase = Depends(get_db_connection)) -> Dict:
    
    try:
    
        llm = AzureChatOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=OPENAI_API_VERSION,
        )  

        # Initialize the SQLDatabaseToolkit with LLM and the database
        
        toolkit = SQLDatabaseToolkit(llm=llm, db=db)
        dialect = toolkit.dialect
        topk = 10

        # Construct the prompt with the provided user input
        column_metadata = """

        **Description:**
        This table contains cleansed and structured item data for equipment and parts used in various systems. It provides detailed information on item descriptions, specifications, manufacturer details, and unique identifiers to ensure accurate item tracking and data integrity.

        **Columns Metadata:**

        - **ITEM_ID**: The unique identifier assigned to each item in the dataset to ensure distinct tracking and reference.
        - **item_description**: Provides a detailed textual explanation of the item's characteristics and purpose.
        - **SPECIFICATION**: Contains technical details and standards relevant to the item, ensuring compliance and quality.
        - **PART_NUMBER**: The manufacturer-assigned code that uniquely identifies the part for cataloging and procurement.
        - **POSITION_NUMBER**: Indicates the item's placement or sequence within a system or assembly for accurate positioning.
        - **DRAWING_NUMBER**: A reference to the engineering or design drawing associated with the item, used for design verification and manufacturing.
        - **MODEL_NUMBER**: Specifies the manufacturer's model designation for the item, facilitating model-specific tracking.
        - **EQUIPMENT_ID**: Uniquely identifies the equipment to which the item belongs, supporting asset management and maintenance.
        - **equipment_name**: Provides the official name of the equipment associated with the item for easier identification.
        - **equipment_code**: A standardized code assigned to the equipment for classification and reporting purposes.
        - **equip_type_id**: Uniquely identifies the category or type of equipment, supporting classification and analysis.
        - **equip_maker_id**: A unique identifier for the manufacturer of the equipment, ensuring accurate supplier tracking.
        - **equip_model_id**: Represents the unique identifier for the specific model of the equipment, aiding in version control.
        - **maker_name**: The official name of the item's manufacturer, essential for supplier management and quality control.
        - **maker_code**: A unique code designated for each manufacturer, simplifying supplier identification.
        - **model_name**: Specifies the item's model designation, providing clarity on product variations.
        - **model_code**: A unique identifier for the model, supporting detailed tracking and categorization.
        - **equip_type_name**: Describes the equipment category, enabling clear classification of equipment types.
        - **unique_id**: A distinct 16-character identifier generated by combining the part number, drawing number, and manufacturer details. This ensures that each item is uniquely identifiable, preventing duplication and facilitating accurate tracking across systems. unique id is created based on some criterias like
            1. If same equipment type, maker name, model name is there with a part number and drawing number combination it should be the first priority for generating the Unique ID.
            2. If same equipment type, maker name, model name is there, but part number is not available and position number and drawing number is available, this combination should be the second priority for generating the Unique ID.
            3. If same equipment type, maker name, model name is there with same part number and with no position number or drawing number, and for those having item description 90 % matching, generate unique id for that combination.
            4. If same equipment type, maker name, model name is there with same position number and with no part number or drawing number, and for those having item description 90 % matching, generate unique id for that combination.
            5. If same equipment type, maker name, model name is there with same drawing number and with no part number or position number, and for those having item description 90 % matching, generate unique id for that combination. 
            6. If same equipment type, maker name, model name is there and dosen't find any of the above combinations generate unique ids for this combination.
       
        **Primary Key:**

        - **unique_id**

        **Purpose:**
        The table ensures data consistency and uniqueness for items used across equipment systems, aiding in efficient inventory management, traceability, and decision-making.



        """
 
        Metadata_Groupings = """
        #### **Item Metadata**:
        - **ITEM_ID**: A unique identifier assigned to each item, crucial for tracking and referencing within the system.
        - **item_description**: A detailed explanation of the item's physical characteristics, purpose, and usage.
        - **SPECIFICATION**: Contains the item's technical details, including materials, dimensions, and performance standards, ensuring compliance with quality requirements.
        - **PART_NUMBER**: The manufacturer's unique code assigned to the part, which is essential for procurement, cataloging, and inventory control.
        - **POSITION_NUMBER**: Indicates the item's specific location or sequence within an assembly or system, ensuring correct placement and functionality.
        - **DRAWING_NUMBER**: A reference to the design or engineering drawing of the item, critical for manufacturing, verification, and modification purposes.
        - **MODEL_NUMBER**: The manufacturer's model number, used to track the specific version or variation of the item across different systems and markets.

        #### **Equipment Metadata**:
        - **EQUIPMENT_ID**: A unique identifier for the equipment to which the item belongs, supporting asset management and maintenance tracking.
        - **equipment_name**: The official name of the equipment, which aids in quick identification and reference in maintenance logs or inventories.
        - **equipment_code**: A standardized code assigned to the equipment for ease of reporting, classification, and tracking within organizational systems.
        - **equip_type_id**: An identifier for the equipment's category or type, aiding in classification and analysis for asset management, operational planning, and reporting.
        - **equip_model_id**: A specific identifier for the model of the equipment, ensuring that the correct model is tracked and managed.
        - **equip_type_name**: Describes the general category or type of the equipment, facilitating the organization of equipment into logical groups based on function or use.
        - **equip_maker_id**: A unique identifier for the maker or manufacturer of the equipment, critical for tracking and managing suppliers, warranty claims, and quality assurance.
        
        #### **Manufacturer Metadata**:
        - **maker_name**: The official name of the item’s manufacturer, critical for supplier identification, vendor management, and warranty processing.
        - **maker_code**: A unique code for the manufacturer, simplifying the identification and tracking of suppliers across systems.
        - **model_name**: A designation for the specific model of the item, clarifying any variations or versions of the product to ensure compatibility and performance expectations.
        - **model_code**: A unique identifier for the model, helping with categorization, inventory control, and detailed tracking of specific product versions.

        #### **Unique Identifier and Tracking**:
        - **unique_id**: A 16-character identifier created by combining the PART_NUMBER, DRAWING_NUMBER, and manufacturer details. This unique ID ensures each item is traceable across systems without duplication, providing seamless integration with inventory management, maintenance, and asset tracking systems.

        """


        prefix = """
        You are an advanced SQL database assistant specializing in answering user queries by interacting with the `tbl_vw_dm_gdb_items_uniqueid_mapped` table in the `Common` schema.
        ### Handling General Queries:
        - If the query is a general greeting (e.g., "Hi", "Hello", "How are you?"), respond with a polite acknowledgment:
          - Example: "Hello! How can I assist you today?"
        - For unrelated or unclear questions, politely guide the user back to database-specific queries.
          - Example: "I'm here to assist with database-related queries. How can I help?"

        ### Responsibilities:
        1. Provide **precise** and **contextually relevant** answers strictly based on the specified table and schema.
        2. Ensure **query normalization and standardization** to deliver consistent and meaningful results for similar questions.
        3. Leverage response history to avoid redundant queries, optimizing efficiency and user satisfaction.
        
        ### Query Normalization Guidelines:
        - **Input Transformation**: 
        1.Convert all input text to lowercase for case-insensitive handling.
        2.Replace punctuation characters (e.g., -, _, ,, .) with spaces for better uniformity.
        3.Remove leading and trailing whitespaces; collapse multiple spaces into a single space.
        - **String Functions**:
        1.Use SQL string functions like `LOWER()`, `TRIM()`, `REPLACE()`, and fuzzy matching (`LIKE`, `LEVENSHTEIN()`, `SOUNDEX`) to account for minor spelling errors or variations.
        - **Case Mismatch Handling**:
        1.If the data in the database is stored in a specific case (e.g., uppercase), ensure that both the input and the database column are transformed to the same case during processing.
        - **For consistent matching**: 
        1.Normalize input to match the stored case (e.g., UPPER() for uppercase or LOWER() for lowercase).
        2.Apply the same transformation on both sides of the comparison.
        3.Use case-insensitive comparisons (e.g., ILIKE for PostgreSQL, collations in MySQL).
        ### SQL Query Construction:
        1. Ensure the query adheres to the **{dialect} dialect** syntax.
        2. Use **specific columns** in the SELECT clause for precision; avoid `SELECT *`.
        4. Order results by **relevant columns** for clarity (e.g., `ITEM_ID ASC` for ordered lists).
        5. Validate query syntax before execution to ensure success and eliminate errors.
        6. Incorporate conditions for **filtering by user intent** and domain-specific logic (e.g., filtering by `SPECIFICATION` or `DRAWING_NUMBER`).
        7. When queried regarding `unique IDs`, construct the response by adhering to the criteria specified in the `column metadata`. Ensure the `unique ID` is identified based on the combination or relevance of the columns outlined in the metadata, such as `ITEM_ID`, `SPECIFICATION`, `DRAWING_NUMBER`, and any additional fields mentioned. Only provide results that meet these criteria for uniqueness."
        8. Use the **SPECIFICATION** column for detailed item descriptions.  
        ### Rules of Engagement:
        - Do not perform Data Manipulation Language (DML) operations such as `INSERT`, `UPDATE`, or `DELETE`.
        - Use **Markdown format** for presenting results:
          - Include bordered tables for tabular data for better readability.
        - If the query is unrelated to the database or cannot be addressed, respond with:
          *"I'm unable to provide an answer for that. This information is not available."*
        - Handle ambiguous questions by:
          1. Politely clarifying the user's intent.
          2. Assuming the most logical interpretation when clarification isn't feasible.
        - **Tone and Style**:
          - Be professional, concise, and courteous in responses.
          - Avoid database-specific jargon unless directly relevant.
          - Use the following metadata {column_metadata} and {Metadata_Groupings}
        
        Your ultimate goal is to ensure clarity, accuracy, and user satisfaction while adhering strictly to data access and usage guidelines.


        """
        
       

        
        suffix = """
        If asked about the database structure, table design, or unavailable data, respond politely:
        *"I can answer questions from this database but cannot provide information about its structure or column names. Let me assist you with the data instead."*
        
        ### Additional Guidelines:
        1. Always validate queries against user intent:
           - Prioritize **relevance and accuracy**.
           - Use domain-specific filtering for improved results
        2. Incorporate prompt optimization techniques:
           - Break down **complex questions** into smaller SQL components to ensure accuracy.
           - Apply **logical conditions** (e.g., combining multiple filters using `AND` or `OR`) for precise results.
        3. Handle ambiguity:
           - Clarify the query if needed.
           - Make reasonable assumptions based on the schema and metadata.
        4. Optimize performance:
           - Use indexed columns in filtering conditions to speed up queries.
           - Aggregate results when large datasets are involved (e.g., using `SUM()`, `AVG()`, `GROUP BY`).
        
        5. Present answers effectively:
           - Use **Markdown** tables with proper column headers and alignments.
           - Provide **concise summaries** when large datasets are returned.

        6. For handling big result data:
           - The result is too large to display. Please refine your query or use filters to reduce the result size to show the `top ten` results only.

        """
        
        # Create the prompt and messages
        human_message = HumanMessagePromptTemplate.from_template("{input}").format(input=userinput)
        messages = [
            SystemMessage(content=prefix),
            human_message,
            AIMessage(content=suffix),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True, prompt=prompt,top_k=topk)

        # Execute the query
        response = agent_executor.invoke(f"Now answer this query: {userinput}")["output"]
        return {"response": response}
    except Exception as e:
        logging.error("Error handling query:", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the request.")

# Basic endpoint for testing
@app.get("/")
def read_root():
    return {"message": "Welcome to my FastAPI app!"}

# Start the scheduler on app startup
@app.on_event("startup")
async def startup():
    scheduler.start()

# Shutdown the scheduler on app shutdown
@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

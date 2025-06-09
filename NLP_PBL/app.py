import os
import streamlit as st
import mysql.connector
import speech_recognition as sr
import pandas as pd
import time  # Import time module for execution time measurement
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv("cred.env")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Fetch Available Databases
def get_databases():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD")
        )
        cur = conn.cursor()
        cur.execute("SHOW DATABASES;")
        databases = [db[0] for db in cur.fetchall()]
        conn.close()
        return databases
    except mysql.connector.Error as e:
        return f"SQL Error: {e}"

# Connect to MySQL & Fetch Tables (For a Selected Database)
def get_tables(database):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=database
        )
        cur = conn.cursor()
        cur.execute("SHOW TABLES;")
        tables = [table[0] for table in cur.fetchall()]
        conn.close()
        return tables
    except mysql.connector.Error as e:
        return f"SQL Error: {e}"

# Fetch Database Schema for Selected DB
def get_schema(database):
    tables = get_tables(database)
    if isinstance(tables, str):  # If error occurred
        return tables
    schema_info = ""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=database
        )
        cur = conn.cursor()
        for table in tables:
            cur.execute(f"DESCRIBE {table};")
            columns = ", ".join([col[0] for col in cur.fetchall()])
            schema_info += f"**{table}**: {columns}\n"
        conn.close()
        return schema_info
    except mysql.connector.Error as e:
        return f"SQL Error: {e}"

# SQL Prompt for AI
def get_sql_prompt(database):
    schema = get_schema(database)
    if "SQL Error" in schema:
        return schema
    return f"""
You are an expert SQL generator! Convert natural language into SQL queries.
Use the following schema for the {database} database:

{schema}

Examples:
1. "How many users signed up?" → SELECT COUNT(*) FROM signup;
2. "Show all login details" → SELECT * FROM login;
3. "Get names from signup2 where age > 18" → SELECT name FROM signup2 WHERE age > 18;
4. "Insert a new user named Alex with age 25" → INSERT INTO users (name, age) VALUES ('Alex', 25);
5. "Update age to 30 for user Alex" → UPDATE users SET age = 30 WHERE name = 'Alex';

Only return the SQL query. Do NOT use markdown, backticks, or explanations.
"""

# Generate SQL Query
def generate_sql(natural_query, database):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content([get_sql_prompt(database), natural_query])
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"

# Execute SQL Query (Supports INSERT & UPDATE)
def execute_sql(query, database):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=database
        )
        cur = conn.cursor()

        start_time = time.time()  # Start time measurement

        if query.lower().startswith(("select", "show", "describe")):
            cur.execute(query)
            rows = cur.fetchall()
            column_names = [desc[0] for desc in cur.description] if cur.description else ["Result"]
            execution_time = time.time() - start_time  # End time measurement
            cur.close()
            conn.close()
            return pd.DataFrame(rows, columns=column_names) if rows else pd.DataFrame(), execution_time

        elif query.lower().startswith(("insert", "update", "delete")):
            cur.execute(query)
            conn.commit()
            execution_time = time.time() - start_time  # End time measurement
            cur.close()
            conn.close()
            return "Query executed successfully.", execution_time

        else:
            return "Only SELECT, SHOW, DESCRIBE, INSERT, UPDATE, and DELETE queries are allowed.", None

    except mysql.connector.Error as e:
        return f"SQL Error: {e}", None

# Speech-to-Text Function
def speech_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now!")
        audio = recognizer.listen(source)
    try:
        text_query = recognizer.recognize_google(audio)
        st.success(f"Recognized Query: {text_query}")
        return text_query
    except sr.UnknownValueError:
        st.error("Could not understand the audio.")
    except sr.RequestError:
        st.error("Error connecting to Google Speech API.")
    return ""

# Streamlit UI Enhancements
st.set_page_config(page_title="AI-Powered SQL Generator", layout="wide")

st.sidebar.header("Select Database")
available_databases = get_databases()
selected_database = st.sidebar.selectbox("Select Database:", available_databases)

st.title("AI-Powered SQL Query System")
st.write("Convert natural language into SQL queries using AI!")

query_input = st.text_input("Type your query in natural language:")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Use Voice Input"):
        query_input = speech_to_text()
        if query_input:
            sql_query = generate_sql(query_input, selected_database)
            if "SQL Error" in sql_query or "Error" in sql_query:
                st.error(sql_query)
            else:
                st.code(sql_query, language="sql")
                if st.checkbox("Manually Edit Query"):
                    sql_query = st.text_area("Edit SQL Query:", sql_query)
                result, exec_time = execute_sql(sql_query, selected_database)
                if isinstance(result, pd.DataFrame):
                    st.subheader("Query Results:")
                    st.dataframe(result, height=600)
                else:
                    st.success(result)
                st.write(f"⏱️ **Execution Time:** {exec_time:.4f} seconds")

with col2:
    if st.button("Generate & Execute Query"):
        if query_input:
            sql_query = generate_sql(query_input, selected_database)
            if "SQL Error" in sql_query or "Error" in sql_query:
                st.error(sql_query)
            else:
                st.code(sql_query, language="sql")
                if st.checkbox("Manually Edit Query"):
                    sql_query = st.text_area("Edit SQL Query:", sql_query)
                result, exec_time = execute_sql(sql_query, selected_database)
                if isinstance(result, pd.DataFrame):
                    st.subheader("Query Results:")
                    st.dataframe(result, height=600)
                else:
                    st.success(result)
                st.write(f"⏱️ **Execution Time:** {exec_time:.4f} seconds")
        else:
            st.warning("Please enter a query first.")

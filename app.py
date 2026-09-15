import sqlite3
import pandas as pd
import streamlit as st
import google.generativeai as genai

st.set_page_config(
    page_title="OSU P-Card Internal Audit Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 OSU P-Card Internal Audit Dashboard")

# Load API key from Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Tabs configuration in English
tab1, tab2 = st.tabs([
    "💬 Natural Language Query (AI)", 
    "🚨 Prohibited Purchases Dashboard"
])

DB_PATH = "pcards.db"

def run_sql(query):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# TAB 1: Natural Language Query (AI)
with tab1:
    st.header("Natural Language Database Query")
    st.write("Ask questions in plain English to analyze the 2014 P-Card dataset.")
    
    if not api_key:
        st.warning("⚠️ Gemini API Key missing. Please set GEMINI_API_KEY in `.streamlit/secrets.toml`.")
        
    user_question = st.text_input(
        "Ask a question about the 2014 transaction data:",
        placeholder="e.g., Which employees spent more than $50,000 in 2014?"
    )
    
    if st.button("Run Query") and user_question:
        if not api_key:
            st.error("Please configure your API key to run queries.")
        else:
            with st.spinner("Translating question into SQL query..."):
                try:
                    system_prompt = """
                    You are an expert SQLite database auditor for Oklahoma State University (OSU).
                    The table is named `pcards` with columns:
                    Amount (REAL), FullName (TEXT), Description (TEXT), Vendor (TEXT), 
                    TransactionDate (TEXT), PostedDate (TEXT), MCC (INTEGER), Month (INTEGER), Year (INTEGER).

                    Guidelines:
                    - Return ONLY the raw SQL query. Do not wrap in markdown like ```sql.
                    - Always restrict queries to Year = 2014 unless specified otherwise.
                    - Output only valid SQLite syntax.
                    """
                    
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    response = model.generate_content(f"{system_prompt}\n\nUser Question: {user_question}")
                    sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()
                    
                    st.subheader("Generated SQL Query:")
                    st.code(sql_query, language="sql")
                    
                    results_df = run_sql(sql_query)
                    st.subheader(f"Results ({len(results_df)} rows found):")
                    st.dataframe(results_df, use_container_width=True)
                except Exception as e:
                    st.error(f"Error executing query: {e}")

# TAB 2: Prohibited Purchases Dashboard
with tab2:
    st.header("Prohibited & High-Risk Purchases Analysis")
    st.write("Filter and review transactions violating university procurement policy.")
    
    category = st.selectbox(
        "Select Audit Risk Category:",
        [
            "Prohibited Keyword Transactions (Personal/Gift/Amazon/Entertainment/Cash)",
            "Single Transactions Exceeding $5,000 Limit",
            "Annual Cumulative Spend Exceeding $50,000 Limit",
            "Generic Purchase Descriptions ('GENERAL PURCHASE')"
        ]
    )
    
    if "Prohibited Keyword" in category:
        query = """
        SELECT Amount, FullName, Description, Vendor, TransactionDate, MCC 
        FROM pcards 
        WHERE Year = 2014 AND (
            Description LIKE '%PERSONAL%' OR Description LIKE '%GIFT%' OR 
            Description LIKE '%AMAZON%' OR Description LIKE '%ENTERTAINMENT%' OR
            Description LIKE '%CASH%' OR Description LIKE '%ATM%'
        )
        ORDER BY Amount DESC;
        """
    elif "Single Transactions" in category:
        query = """
        SELECT Amount, FullName, Description, Vendor, TransactionDate, MCC 
        FROM pcards 
        WHERE Year = 2014 AND Amount > 5000 
        ORDER BY Amount DESC;
        """
    elif "Annual Cumulative" in category:
        query = """
        SELECT FullName, SUM(Amount) AS TotalSpent, COUNT(*) AS TransactionCount 
        FROM pcards 
        WHERE Year = 2014 
        GROUP BY FullName 
        HAVING SUM(Amount) > 50000 
        ORDER BY TotalSpent DESC;
        """
    else:
        query = """
        SELECT Amount, FullName, Description, Vendor, TransactionDate, MCC 
        FROM pcards 
        WHERE Year = 2014 AND Description LIKE '%GENERAL PURCHASE%' 
        ORDER BY Amount DESC 
        LIMIT 500;
        """
        
    try:
        prohibited_df = run_sql(query)
        st.metric(label="Total Audit Risk Records Identified", value=len(prohibited_df))
        st.dataframe(prohibited_df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading prohibited items: {e}")

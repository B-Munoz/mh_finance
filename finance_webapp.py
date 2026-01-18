import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- Configuration & Setup ---
DB_PATH = "expenses.db"
CATEGORIES = ["Transporte", "Vivienda", "Misceláneo"]

class ExpenseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """
        Initializes the table with a Primary Key.
        BEST PRACTICE: Always use an ID column for reliable row referencing.
        """
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    Category TEXT,
                    Description TEXT,
                    Amount REAL
                )
            """)

    def load_data(self):
        """Loads data including the ID, but keeps it hidden in UI later."""
        with self.get_connection() as conn:
            try:
                df = pd.read_sql("SELECT * FROM expenses", conn, parse_dates=["Date"])
                return df
            except Exception:
                return pd.DataFrame(columns=["id", "Date", "Category", "Description", "Amount"])

    def save_bulk_data(self, df):
        """
        Safely updates the database without dropping the table.
        Strategy: Truncate (Delete all) -> Append. 
        This preserves the Table Schema (Primary Keys, constraints).
        """
        with self.get_connection() as conn:
            conn.execute("DELETE FROM expenses") 
            df.to_sql("expenses", conn, if_exists="append", index=False)

    def add_expense(self, category, description, amount):
        """Inserts a single row letting SQL handle the Timestamp and ID."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO expenses (Date, Category, Description, Amount) VALUES (?, ?, ?, ?)",
                (datetime.now(), category, description, amount)
            )
        return self.load_data()

# Instanciamos el manager
manager = ExpenseManager(DB_PATH)

st.set_page_config(page_title="Finance Manager", page_icon="💰")
st.title("💰 Personal Finance Manager")

if 'df' not in st.session_state:
    st.session_state.df = manager.load_data()

# --- Sidebar: Add New Expense ---
with st.sidebar:
    st.header("Add New Expense")
    with st.form("expense_form", clear_on_submit=True):
        amount = st.number_input("Amount ($)", min_value=0, step=100)
        description = st.text_input("Description")
        category = st.selectbox("Category", CATEGORIES)
        
        submitted = st.form_submit_button("Add Expense")
        
        if submitted:
            st.session_state.df = manager.add_expense(category, description, amount)
            st.toast("Expense added to Database!")

# --- Main Page: Dashboard ---
if st.session_state.df.empty:
    st.info("Start by adding expenses in the sidebar!")
else:
    # 1. Metrics Row
    total_spent = st.session_state.df["Amount"].sum()
    col1, col2 = st.columns(2)
    col1.metric("Total Spent", f"${total_spent:,.2f}")
    col2.metric("Total Transactions", len(st.session_state.df))

    # 2. Charts
    st.subheader("Expenses by Category")
    # Grouping by category for visual
    if not st.session_state.df.empty:
        chart_data = st.session_state.df.groupby("Category")["Amount"].sum()
        st.bar_chart(chart_data)

    # 3. Data Table (Editable)
    st.subheader("Transactions Editor")
    
    df_display = st.session_state.df.sort_values(by="Date", ascending=False)
    
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "id": None, # Best Practice: Hide implementation details (Primary Key) from users
            "Amount": st.column_config.NumberColumn(format="$%d"),
            "Date": st.column_config.DatetimeColumn(format="D MMM YYYY, HH:mm")
        },
        key="main_editor"
    )

    if st.button("💾 Save Changes to DB"):
        st.session_state.df = edited_df
        manager.save_bulk_data(edited_df)
        st.success("Database updated successfully (Schema preserved)!")
        st.rerun()

    # 4. Category Matrix View
    st.subheader("Category Matrix View")
    st.caption("Each column represents a category, showing individual transaction amounts.")
    
    data_dict = {}
    max_len = 0
    
    for cat in CATEGORIES:
        amounts = st.session_state.df[st.session_state.df["Category"] == cat]["Amount"].tolist()
        data_dict[cat] = amounts
        max_len = max(max_len, len(amounts))
    
    # Pad lists to same length to create a DataFrame
    for cat in data_dict:
        data_dict[cat] += [None] * (max_len - len(data_dict[cat]))
        
    compact_df = pd.DataFrame(data_dict)
    
    st.dataframe(
        compact_df.style.format("${:.2f}", na_rep=""),
        use_container_width=True,
        hide_index=True 
    )
import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# --- HELPER: Database Connection ---
@st.cache_resource
def get_db_engine():
    # Looks for the secret in .streamlit/secrets.toml
    db_info = st.secrets["connections"]["neon"]
    if "url" in db_info:
        # Fix protocol for SQLAlchemy
        url = db_info["url"].replace("postgres://", "postgresql://")
        return create_engine(url)
    # Fallback if using separate fields
    return create_engine(f"postgresql+psycopg2://{db_info['username']}:{db_info['password']}@{db_info['host']}/{db_info['database']}")

class ExpenseManager:
    def __init__(self):
        self.init_db()

    def get_connection(self):
        return get_db_engine().connect()

    def init_db(self):
        """Initializes the table. Uses SERIAL for Postgres auto-increment."""
        with self.get_connection() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    category TEXT,
                    description TEXT,
                    amount REAL
                )
            """))
            conn.commit()

    def load_data(self):
        with self.get_connection() as conn:
            try:
                df = pd.read_sql(text("SELECT * FROM expenses"), conn, parse_dates=["date"])
                return df
            except Exception:
                return pd.DataFrame(columns=["id", "date", "category", "description", "amount"])

    def save_bulk_data(self, df):
        with self.get_connection() as conn:
            with conn.begin(): # Transaction
                conn.execute(text("DELETE FROM expenses")) 
                df.to_sql("expenses", conn, if_exists="append", index=False)

    def add_expense(self, category, description, amount):
        with self.get_connection() as conn:
            with conn.begin(): # Transaction block
                # 1. Record the Transaction
                conn.execute(
                    text("INSERT INTO expenses (date, category, description, amount) VALUES (:d, :c, :desc, :a)"),
                    {"d": datetime.now(), "c": category, "desc": description, "a": amount}
                )         
                # 2. Deduct from the Budget Bucket
                conn.execute(
                    text("UPDATE budgets SET current_balance = current_balance - :a WHERE category = :c"),
                    {"a": amount, "c": category}
                )
        return self.load_data()

    @staticmethod
    def calculate_metrics(df):
        if df.empty: return 0, 0
        return df["amount"].sum(), len(df)

    @staticmethod
    def get_expenses_by_category(df):
        if df.empty: return pd.Series()
        return df.groupby("category")["amount"].sum()

    @staticmethod
    def get_category_matrix(df, categories):
        data_dict = {}
        max_len = 0
        for cat in categories:
            amounts = df[df["category"] == cat]["amount"].tolist()
            data_dict[cat] = amounts
            max_len = max(max_len, len(amounts))
        for cat in data_dict:
            data_dict[cat] += [None] * (max_len - len(data_dict[cat]))
        return pd.DataFrame(data_dict)


class BudgetManager:
    def __init__(self, allocation_map, limit_map):
        self.allocation_map = allocation_map 
        self.limit_map = limit_map
        self.init_db()

    def get_connection(self):
        return get_db_engine().connect()

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS budgets (
                    category TEXT PRIMARY KEY,
                    current_balance REAL DEFAULT 0
                )
            """))
            conn.commit()
            
            # Ensure categories exist
            with conn.begin():
                for cat in self.allocation_map.keys():
                    conn.execute(
                        text("INSERT INTO budgets (category, current_balance) VALUES (:cat, 0) ON CONFLICT (category) DO NOTHING"),
                        {"cat": cat}
                    )

    def get_balances(self):
        with self.get_connection() as conn:
            result = conn.execute(text("SELECT category, current_balance FROM budgets"))
            rows = result.fetchall()
            return {row[0]: row[1] for row in rows}

    def allocate_income(self, income_amount):
        """Distributes income with waterfall logic."""
        current_balances = self.get_balances()
        allocations = {cat: 0.0 for cat in self.allocation_map}
        remaining_income = float(income_amount)
        
        # --- Waterfall Logic ---
        while remaining_income > 0.01:
            active_cats = []
            for cat, pct in self.allocation_map.items():
                if pct <= 0: continue
                limit = self.limit_map.get(cat, 0)
                current = current_balances.get(cat, 0.0) + allocations[cat]
                if limit == 0 or current < limit:
                    active_cats.append(cat)

            if not active_cats: break 

            total_active_weight = sum(self.allocation_map[c] for c in active_cats)
            if total_active_weight == 0: break

            distributed_this_round = 0
            for cat in active_cats:
                weight = self.allocation_map[cat] / total_active_weight
                share = remaining_income * weight
                limit = self.limit_map.get(cat, 0)
                current = current_balances.get(cat, 0.0) + allocations[cat]
                space = (limit - current) if limit > 0 else float('inf')
                actual_add = min(share, space)
                allocations[cat] += actual_add
                distributed_this_round += actual_add

            remaining_income -= distributed_this_round
            if distributed_this_round < 0.01: break

        with self.get_connection() as conn:
            with conn.begin():
                for cat, amount in allocations.items():
                    if amount > 0:
                        conn.execute(
                            text("UPDATE budgets SET current_balance = current_balance + :amt WHERE category = :cat"),
                            {"amt": amount, "cat": cat}
                        )
        
        return allocations
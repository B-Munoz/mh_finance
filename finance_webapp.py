import streamlit as st
from classes import ExpenseManager, BudgetManager
import config

CATEGORIES = config.get_categories()
# Instanciamos los managers
expense_manager = ExpenseManager() 
budget_manager = BudgetManager(config.ALLOCATION_PCT, config.CATEGORY_CONFIG)

st.set_page_config(page_title="Finance Manager", page_icon="💰")
st.title("💰 Personal Finance Manager")

if 'df' not in st.session_state:
    st.session_state.df = expense_manager.load_data()

# --- Sidebar: Add New Expense ---
with st.sidebar:
    st.header("Add New Expense")
    with st.form("expense_form", clear_on_submit=True):
        amount = st.number_input("Amount ($)", min_value=0, step=100)
        description = st.text_input("Description")
        category = st.selectbox("Category", CATEGORIES)
        
        submitted = st.form_submit_button("Add Expense")
        
        if submitted:
            st.session_state.df = expense_manager.add_expense(category, description, amount)
            st.toast("Expense added to Database!")
     
    st.markdown("---")
    st.header("Add Income")
    
    with st.form("income_form", clear_on_submit=True):
        income_amount = st.number_input("Income Amount ($)", min_value=0, step=1000)
        submitted_income = st.form_submit_button("Allocate Income")
        
        if submitted_income and income_amount > 0:
            allocations = budget_manager.allocate_income(income_amount)
            st.toast(f"Income of ${income_amount} distributed!")
            
            # Optional: Show breakdown
            with st.expander("See Allocation Breakdown", expanded=True):
                for cat, amt in allocations.items():
                    if amt > 0:
                        st.write(f"**{cat}**: +${amt:,.0f}")

# --- Main Page: Dashboard ---
if st.session_state.df.empty:
    st.info("Start by adding expenses in the sidebar!")
else:
    # 1. Metrics Row
    total_spent, total_count = ExpenseManager.calculate_metrics(st.session_state.df)
    col1, col2 = st.columns(2)
    col1.metric("Total Spent", f"${total_spent:,.0f}")
    col2.metric("Total Transactions", len(st.session_state.df))
    st.markdown("---")
    st.subheader("Budgets")
    
    balances = budget_manager.get_balances()
    cols = st.columns(3) 
    
    for i, (category, limit) in enumerate(config.CATEGORY_CONFIG.items()):
        current = balances.get(category, 0.0)
        
        # Calculate percentage (handle division by zero if limit is 0)
        if limit > 0:
            percent = min(current / limit, 1.0)
        else:
            pass

        with cols[i % 3]: 
            st.metric(
                label=category, 
                value=f"${current:,.0f}", 
                delta=f"Budget: ${limit:,.0f}" if limit > 0 else "Unlimited"
            )
            try:
                st.progress(percent)
            except:
                pass

    # 2. Charts
    st.subheader("Expenses by Category")
    # Grouping by category for visual
    if not st.session_state.df.empty:
        chart_data = ExpenseManager.get_expenses_by_category(st.session_state.df)
        st.bar_chart(chart_data)

    # 3. Data Table (Editable)
    st.subheader("Transactions Editor")
    
    df_display = st.session_state.df.sort_values(by="date", ascending=False)
    
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "id": None,
            # Change "Amount" and "Date" to lowercase keys
            "amount": st.column_config.NumberColumn(label="Amount ($)", format="$%d"),
            "date": st.column_config.DatetimeColumn(label="Date", format="D MMM YYYY, HH:mm"),
            "category": st.column_config.TextColumn(label="Category"),
            "description": st.column_config.TextColumn(label="Description")
        },
        key="main_editor"
    )

    if st.button("💾 Save Changes to DB"):
        st.session_state.df = edited_df
        expense_manager.save_bulk_data(edited_df)
        st.success("Database updated successfully!")
        st.rerun()

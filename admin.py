import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import os
import uuid
from PIL import Image

# Configuration
st.set_page_config(page_title="Admin Dashboard", layout="wide", page_icon="📊")

# Hide Streamlit style
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stActionButton > button[title="Open source on GitHub"] {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Constants
SALES_SHEET_COLUMNS = [
    "Invoice Number", "Invoice Date", "Employee Name", "Employee Code", "Designation",
    "Discount Category", "Transaction Type", "Outlet Name", "Outlet Contact", "Outlet Address",
    "Outlet State", "Outlet City", "Distributor Firm Name", "Distributor ID", "Distributor Contact Person",
    "Distributor Contact Number", "Distributor Email", "Distributor Territory", "Product ID",
    "Product Name", "Product Category", "Quantity", "Unit Price", "Product Discount (%)",
    "Discounted Unit Price", "Total Price", "GST Rate", "CGST Amount", "SGST Amount",
    "Grand Total", "Overall Discount (%)", "Amount Discount (INR)", "Payment Status",
    "Amount Paid", "Payment Receipt Path", "Employee Selfie Path", "Invoice PDF Path",
    "Remarks", "Delivery Status"
]

VISIT_SHEET_COLUMNS = [
    "Visit ID", "Employee Name", "Employee Code", "Designation", "Outlet Name",
    "Outlet Contact", "Outlet Address", "Outlet State", "Outlet City", "Visit Date",
    "Entry Time", "Exit Time", "Visit Duration (minutes)", "Visit Purpose", "Visit Notes",
    "Visit Selfie Path", "Visit Status", "Remarks"
]

ATTENDANCE_SHEET_COLUMNS = [
    "Attendance ID", "Employee Name", "Employee Code", "Designation", "Date",
    "Status", "Location Link", "Leave Reason", "Check-in Time", "Check-in Date Time"
]

# Establish connections
conn = st.connection("gsheets", type=GSheetsConnection)
Person = pd.read_csv('Invoice - Person.csv')

# Helper functions
def load_data(worksheet_name, columns):
    try:
        data = conn.read(worksheet=worksheet_name, usecols=list(range(len(columns))), ttl=5)
        data = data.dropna(how='all')
        
        # Fix data types for Arrow compatibility
        for col in data.columns:
            if data[col].dtype == 'object':
                data[col] = data[col].astype(str)
            elif pd.api.types.is_numeric_dtype(data[col]):
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        return data
    except Exception as e:
        st.error(f"Error loading {worksheet_name} data: {e}")
        return pd.DataFrame(columns=columns)

def format_currency(amount):
    if pd.isna(amount):
        return "₹0.00"
    return f"₹{amount:,.2f}".replace(",", " ")  # Replace commas with spaces for better visibility

def format_number(value):
    if pd.isna(value):
        return "0"
    return f"{int(value):,}".replace(",", " ")  # Replace commas with spaces for better visibility

def format_percentage(value):
    if pd.isna(value):
        return "0.0%"
    return f"{float(value):.1f}%"

def get_date_range():
    today = datetime.now().date()
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    last_quarter = today - timedelta(days=90)
    return today, last_week, last_month, last_quarter

# Dashboard layout
def main():
    st.title("Biolume Employee Dashboard")
    
    # Authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        with st.form("admin_auth"):
            st.subheader("Admin Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login"):
                if username == "admin" and password == "admin123":  # Replace with secure auth
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        return
    
    # Load all data
    with st.spinner("Loading data..."):
        sales_data = load_data("Sales", SALES_SHEET_COLUMNS)
        visits_data = load_data("Visits", VISIT_SHEET_COLUMNS)
        attendance_data = load_data("Attendance", ATTENDANCE_SHEET_COLUMNS)
    
    # Convert date columns
    if not sales_data.empty:
        sales_data['Invoice Date'] = pd.to_datetime(sales_data['Invoice Date'], dayfirst=True, errors='coerce')
    if not visits_data.empty:
        visits_data['Visit Date'] = pd.to_datetime(visits_data['Visit Date'], dayfirst=True, errors='coerce')
    if not attendance_data.empty:
        attendance_data['Date'] = pd.to_datetime(attendance_data['Date'], dayfirst=True, errors='coerce')
    
    # Date filters
    st.sidebar.header("Filters")
    
    # Custom date range selector
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now().date())
    
    # Employee filter
    all_employees = Person['Employee Name'].unique().tolist()
    selected_employee = st.sidebar.selectbox(
        "Employee (All)",
        ["All Employees"] + all_employees
    )
    
    # Filter data based on date range
    if not sales_data.empty:
        sales_data = sales_data[
            (sales_data['Invoice Date'].dt.date >= start_date) & 
            (sales_data['Invoice Date'].dt.date <= end_date)
        ]
    if not visits_data.empty:
        visits_data = visits_data[
            (visits_data['Visit Date'].dt.date >= start_date) & 
            (visits_data['Visit Date'].dt.date <= end_date)
        ]
    if not attendance_data.empty:
        attendance_data = attendance_data[
            (attendance_data['Date'].dt.date >= start_date) & 
            (attendance_data['Date'].dt.date <= end_date)
        ]
    
    if selected_employee != "All Employees":
        if not sales_data.empty:
            sales_data = sales_data[sales_data['Employee Name'] == selected_employee]
        if not visits_data.empty:
            visits_data = visits_data[visits_data['Employee Name'] == selected_employee]
        if not attendance_data.empty:
            attendance_data = attendance_data[attendance_data['Employee Name'] == selected_employee]
    
    # Main dashboard
    tab1, tab2, tab3 = st.tabs(["📈 Overview", "👥 Employee Performance", "📋 Detailed Records"])
    
    with tab1:
        st.header("Business Overview")
        
        # KPI Cards
        if not sales_data.empty:
            total_sales = sales_data['Grand Total'].sum()
            total_invoices = sales_data['Invoice Number'].nunique()
            avg_sale_per_invoice = total_sales / total_invoices if total_invoices > 0 else 0
            payment_completion = (sales_data[sales_data['Payment Status'] == 'paid']['Grand Total'].sum() / total_sales * 100) if total_sales > 0 else 0
        else:
            total_sales = 0
            total_invoices = 0
            avg_sale_per_invoice = 0
            payment_completion = 0
        
        if not visits_data.empty:
            total_visits = len(visits_data)
            avg_visit_duration = visits_data['Visit Duration (minutes)'].mean()
        else:
            total_visits = 0
            avg_visit_duration = 0
        
        if not attendance_data.empty:
            # Get only today's attendance
            today_attendance = attendance_data[attendance_data['Date'].dt.date == datetime.now().date()]
            present_count = len(today_attendance[today_attendance['Status'] == 'Present'])
            leave_count = len(today_attendance[today_attendance['Status'] == 'Leave'])
        else:
            present_count = 0
            leave_count = 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sales", format_currency(total_sales))
        with col2:
            st.metric("Total Invoices", format_number(total_invoices))
        with col3:
            st.metric("Avg. Sale/Invoice", format_currency(avg_sale_per_invoice))
        with col4:
            st.metric("Payment Completion", format_percentage(payment_completion))
        
        col5, col6, col7 = st.columns(3)
        with col5:
            st.metric("Total Visits", format_number(total_visits))
        with col6:
            st.metric("Avg. Visit Duration", f"{avg_visit_duration:.1f} mins" if avg_visit_duration else "0 mins")
        with col7:
            st.metric("Present Today", format_number(present_count))
        
        # Sales Trend Chart
        st.subheader("Sales Trend")
        if not sales_data.empty:
            sales_trend = sales_data.groupby(sales_data['Invoice Date'].dt.date)['Grand Total'].sum().reset_index()
            fig = px.line(
                sales_trend,
                x='Invoice Date',
                y='Grand Total',
                title=f"Daily Sales ({start_date} to {end_date})",
                labels={'Invoice Date': 'Date', 'Grand Total': 'Total Sales (₹)'}
            )
            fig.update_layout(
                height=400,
                yaxis_tickformat=',.0f',
                yaxis_tickprefix='₹ ',
                yaxis_tickvals=sales_trend['Grand Total'].tolist()
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No sales data available for the selected period")
        
        # Employee Performance Grid
        st.subheader("Employee Performance Summary")
        if not sales_data.empty:
            employee_performance = sales_data.groupby(['Employee Name', 'Employee Code', 'Designation']).agg({
                'Grand Total': 'sum',
                'Invoice Number': 'nunique',
                'Product Name': 'count'
            }).reset_index()
            employee_performance.columns = ['Employee Name', 'Employee Code', 'Designation', 'Total Sales', 'Invoices', 'Products Sold']
            
            # Add visit data if available
            if not visits_data.empty:
                visits_summary = visits_data.groupby('Employee Name').agg({
                    'Visit ID': 'count',
                    'Visit Duration (minutes)': 'mean'
                }).reset_index()
                visits_summary.columns = ['Employee Name', 'Total Visits', 'Avg. Visit Duration']
                employee_performance = pd.merge(employee_performance, visits_summary, on='Employee Name', how='left')
            
            st.dataframe(
                employee_performance.sort_values('Total Sales', ascending=False),
                column_config={
                    "Total Sales": st.column_config.NumberColumn(
                        format="₹ %.2f",
                        help="Total sales amount"
                    ),
                    "Invoices": st.column_config.NumberColumn(
                        format="%d",
                        help="Number of invoices"
                    ),
                    "Products Sold": st.column_config.NumberColumn(
                        format="%d",
                        help="Total products sold"
                    ),
                    "Total Visits": st.column_config.NumberColumn(
                        format="%d",
                        help="Total visits made"
                    ),
                    "Avg. Visit Duration": st.column_config.NumberColumn(
                        format="%.1f mins",
                        help="Average visit duration in minutes"
                    )
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No performance data available for the selected period")
    
    with tab2:
        st.header("Employee Performance Analysis")
        
        if selected_employee == "All Employees":
            st.warning("Please select an employee from the sidebar to view detailed performance")
        else:
            st.subheader(f"Performance Report: {selected_employee}")
            
            # Employee details
            employee_details = Person[Person['Employee Name'] == selected_employee].iloc[0]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Employee Code", employee_details['Employee Code'])
            with col2:
                st.metric("Designation", employee_details['Designation'])
            with col3:
                st.metric("Discount Category", employee_details['Discount Category'])
            
            # Sales performance
            st.subheader("Sales Performance")
            if not sales_data.empty:
                # Sales metrics
                employee_sales = sales_data[sales_data['Employee Name'] == selected_employee]
                total_sales = employee_sales['Grand Total'].sum()
                total_invoices = employee_sales['Invoice Number'].nunique()
                avg_sale_per_invoice = total_sales / total_invoices if total_invoices > 0 else 0
                payment_completion = (employee_sales[employee_sales['Payment Status'] == 'paid']['Grand Total'].sum() / total_sales * 100) if total_sales > 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Sales", format_currency(total_sales))
                with col2:
                    st.metric("Total Invoices", format_number(total_invoices))
                with col3:
                    st.metric("Avg. Sale/Invoice", format_currency(avg_sale_per_invoice))
                with col4:
                    st.metric("Payment Completion", format_percentage(payment_completion))
                
                # Sales by product category
                st.subheader("Sales by Product Category")
                sales_by_category = employee_sales.groupby('Product Category')['Grand Total'].sum().reset_index()
                fig = px.pie(
                    sales_by_category,
                    values='Grand Total',
                    names='Product Category',
                    title="Sales Distribution by Product Category"
                )
                fig.update_traces(textinfo='value+percent', textposition='inside')
                st.plotly_chart(fig, use_container_width=True)
                
                # Top products
                st.subheader("Top Selling Products")
                top_products = employee_sales.groupby('Product Name').agg({
                    'Grand Total': 'sum',
                    'Quantity': 'sum'
                }).sort_values('Grand Total', ascending=False).head(10)
                st.dataframe(
                    top_products,
                    column_config={
                        "Grand Total": st.column_config.NumberColumn(format="₹ %.2f"),
                        "Quantity": st.column_config.NumberColumn(format="%d")
                    },
                    use_container_width=True
                )
            else:
                st.warning("No sales data available for this employee")
            
            # Visit performance
            st.subheader("Visit Performance")
            if not visits_data.empty:
                employee_visits = visits_data[visits_data['Employee Name'] == selected_employee]
                total_visits = len(employee_visits)
                avg_visit_duration = employee_visits['Visit Duration (minutes)'].mean()
                visits_by_purpose = employee_visits['Visit Purpose'].value_counts().reset_index()
                visits_by_purpose.columns = ['Purpose', 'Count']
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Visits", format_number(total_visits))
                with col2:
                    st.metric("Avg. Visit Duration", f"{avg_visit_duration:.1f} mins" if avg_visit_duration else "0 mins")
                
                # Visits by purpose
                fig = px.bar(
                    visits_by_purpose,
                    x='Purpose',
                    y='Count',
                    title="Visits by Purpose",
                    text='Count'
                )
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No visit data available for this employee")
            
            # Attendance performance
            st.subheader("Attendance Record")
            if not attendance_data.empty:
                employee_attendance = attendance_data[attendance_data['Employee Name'] == selected_employee]
                present_days = len(employee_attendance[employee_attendance['Status'] == 'Present'])
                leave_days = len(employee_attendance[employee_attendance['Status'] == 'Leave'])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Present Days", format_number(present_days))
                with col2:
                    st.metric("Leave Days", format_number(leave_days))
            else:
                st.warning("No attendance data available for this employee")
    
    with tab3:
        st.header("Detailed Records")
        
        # Sales records
        st.subheader("Sales Records")
        if not sales_data.empty:
            st.dataframe(
                sales_data,
                column_config={
                    "Grand Total": st.column_config.NumberColumn(format="₹ %.2f"),
                    "Invoice Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Quantity": st.column_config.NumberColumn(format="%d"),
                    "Unit Price": st.column_config.NumberColumn(format="₹ %.2f"),
                    "Total Price": st.column_config.NumberColumn(format="₹ %.2f"),
                    "Amount Paid": st.column_config.NumberColumn(format="₹ %.2f")
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Export options
            csv = sales_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Sales Data",
                csv,
                f"sales_records_{start_date}_to_{end_date}.csv",
                "text/csv",
                key='download-sales-csv'
            )
        else:
            st.warning("No sales data available for the selected period")
        
        # Visit records
        st.subheader("Visit Records")
        if not visits_data.empty:
            st.dataframe(
                visits_data,
                column_config={
                    "Visit Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Visit Duration (minutes)": st.column_config.NumberColumn(format="%.1f mins")
                },
                use_container_width=True,
                hide_index=True
            )
            
            csv = visits_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Visit Data",
                csv,
                f"visit_records_{start_date}_to_{end_date}.csv",
                "text/csv",
                key='download-visit-csv'
            )
        else:
            st.warning("No visit data available for the selected period")
        
        # Attendance records
        st.subheader("Attendance Records")
        if not attendance_data.empty:
            st.dataframe(
                attendance_data,
                column_config={
                    "Date": st.column_config.DateColumn(format="DD/MM/YYYY")
                },
                use_container_width=True,
                hide_index=True
            )
            
            csv = attendance_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Attendance Data",
                csv,
                f"attendance_records_{start_date}_to_{end_date}.csv",
                "text/csv",
                key='download-attendance-csv'
            )
        else:
            st.warning("No attendance data available for the selected period")

if __name__ == "__main__":
    main()

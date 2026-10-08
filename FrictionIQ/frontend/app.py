import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import os

# Page config
st.set_page_config(page_title="FrictionIQ", layout="wide")

st.title("FrictionIQ: Customer Journey Intelligence")

# Fake API URL for local dev
API_URL = "http://localhost:8000"

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Executive Overview", "Friction Detection Center"])

# Load dummy data for UI if available
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("../data/session_features.csv")
        return df
    except:
        return pd.DataFrame()

df = load_data()

if page == "Executive Overview":
    st.header("Executive Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions", len(df) if not df.empty else 0)
    with col2:
        abandoned = df['is_abandoned'].sum() if not df.empty else 0
        st.metric("Abandonment Rate", f"{(abandoned / len(df) * 100):.1f}%" if not df.empty else "0%")
    with col3:
        st.metric("Revenue at Risk", "$45,200") # Dummy metric
    with col4:
        st.metric("Recovered", "$12,400") # Dummy metric
        
    if not df.empty and 'friction_label' in df.columns:
        st.subheader("Friction Types Breakdown")
        friction_counts = df[df['is_abandoned'] == 1]['friction_label'].value_counts().reset_index()
        friction_counts.columns = ['Friction Type', 'Count']
        fig = px.bar(friction_counts, x='Friction Type', y='Count', title="Abandonment by Friction Type")
        st.plotly_chart(fig, use_container_width=True)

elif page == "Friction Detection Center":
    st.header("Friction Detection Center")
    st.write("Live analysis of high-risk sessions.")
    
    session_id = st.text_input("Enter Session ID to analyze (e.g., test_123)", "test_123")
    
    # Mock some features to send
    mock_features = {
        "session_id": session_id,
        "payment_fail": 2,
        "checkout_start": 1
    }
    
    if st.button("Analyze Risk & Root Cause"):
        with st.spinner("Calling Intelligence API..."):
            try:
                # In a real app, this would hit the FastAPI backend
                # Since we want to ensure it works, we will simulate the request or hit it if running
                res = requests.post(f"{API_URL}/friction/root-causes", json={
                    "session_id": session_id,
                    "features": mock_features,
                    "feedback_text": ""
                }, params={"session_id": session_id})
                
                if res.status_code == 200:
                    data = res.json()
                    st.success("Analysis Complete")
                    
                    st.subheader(f"Root Cause: {data.get('root_cause')}")
                    st.metric("Confidence", f"{data.get('confidence', 0) * 100}%")
                    
                    st.info(f"**Recommended Intervention:** {data.get('recommended_intervention')}")
                    st.write(f"Compliance Approved: {data.get('compliance_approved')}")
                    
                    if st.button("Trigger Intervention"):
                        st.success("Intervention triggered successfully!")
                else:
                    st.error(f"API Error: {res.status_code} - {res.text}")
            except Exception as e:
                st.error(f"Failed to connect to backend: {e}. Make sure FastAPI is running on port 8000.")

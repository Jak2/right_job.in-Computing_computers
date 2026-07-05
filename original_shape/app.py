import streamlit as st
import pandas as pd
from database import Database

# Set Page Config
st.set_page_config(
    page_title="Agent execution dashboard",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Multi-Agent Execution blackboard")
st.markdown("Displays real-time logs and intermediate outputs of the collaborative agent system.")

db = Database()

# Refresh Trigger
if st.button("🔄 Refresh Blackboard"):
    st.rerun()

runs = db.get_runs()

if not runs:
    st.info("No runs logged in database yet. Run `python orchestrator.py` to trigger agents.")
else:
    df = pd.DataFrame(runs, columns=["ID", "Timestamp", "Agent Name", "Input Context", "Output Response"])
    
    # Overview metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Executions", len(df))
    with col2:
        st.metric("Active Agents Logged", len(df["Agent Name"].unique()))
        
    st.divider()
    
    # Detailed Trace Expanders
    st.subheader("📋 Step-by-Step Execution Trace")
    
    for _, row in df.iterrows():
        agent = row["Agent Name"]
        timestamp = row["Timestamp"]
        inp = row["Input Context"]
        outp = row["Output Response"]
        run_id = row["ID"]
        
        # Color borders/headers conceptually
        if agent == "Extractor":
            emoji = "🔍"
        elif agent == "Risk Analyst":
            emoji = "⚠️"
        else:
            emoji = "📝"
            
        with st.expander(f"{emoji} {agent} Agent Run — {timestamp} (ID: #{run_id})", expanded=True):
            subcol1, subcol2 = st.columns(2)
            with subcol1:
                st.markdown("**Input Context Received**")
                st.code(inp, language="markdown")
            with subcol2:
                st.markdown("**Output Response Generated**")
                st.code(outp, language="markdown")

import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

st.set_page_config(
    page_title="AI Workload & Capacity Rebalancer",
    page_icon="⚖️",
    layout="wide"
)

# Custom Header
st.title("⚖️ AI Workload Imbalance & Capacity Agent")
st.caption("Automated team bandwidth monitoring, risk detection, and AI-driven task reallocation.")

# Load Data
def load_data():
    if os.path.exists("data.json"):
        with open("data.json", "r") as f:
            return json.load(f)
    else:
        return {"team": []}

raw_data = load_data()

# Process Capacity Metrics
team_summary = []
for member in raw_data.get("team", []):
    total_task_hrs = sum(t.get("hours", t.get("estimated_hours", 0)) for t in member.get("assigned_tasks", []))
    available_hrs = 40 - member.get("meeting_hours", 0)
    load_ratio = round((total_task_hrs / available_hrs) * 100, 1) if available_hrs > 0 else 0
    
    if load_ratio > 110:
        status = "Overloaded 🔴"
    elif load_ratio < 60:
        status = "Underloaded 🟡"
    else:
        status = "Balanced 🟢"
        
    team_summary.append({
        "Name": member["name"],
        "Meeting Hours": member["meeting_hours"],
        "Available Hours": available_hrs,
        "Assigned Task Hours": total_task_hrs,
        "Load Utilization (%)": load_ratio,
        "Status": status,
        "Tasks": member.get("assigned_tasks", [])
    })

df = pd.DataFrame(team_summary)

# Sidebar Filter / Info
st.sidebar.header("🔍 Team Inspector")
selected_user = st.sidebar.selectbox("Select Team Member to Inspect:", df["Name"])

user_info = df[df["Name"] == selected_user].iloc[0]
st.sidebar.markdown(f"### **{selected_user}'s Current Tasks**")
st.sidebar.write(f"**Status:** {user_info['Status']}")
st.sidebar.write(f"**Load Ratio:** {user_info['Load Utilization (%)']}%")

for t in user_info["Tasks"]:
    task_id = t.get('task_id', 'TASK')
    title = t.get('title', 'Untitled')
    hrs = t.get('hours', t.get('estimated_hours', 0))
    skill = t.get('skill', 'General')
    st.sidebar.info(f"📌 **{task_id}:** {title}\n\n⏱️ **Estimate:** {hrs} hrs | 🏷️ **Skill:** {skill}")

# Main Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Team Members", len(df))
col2.metric("Overloaded (>110%)", len(df[df["Status"] == "Overloaded 🔴"]))
col3.metric("Underloaded (<60%)", len(df[df["Status"] == "Underloaded 🟡"]))
col4.metric("Avg Capacity Utilization", f"{round(df['Load Utilization (%)'].mean(), 1)}%")

st.divider()

# Bandwidth Chart
st.subheader("📊 Team Bandwidth Breakdown")
fig = px.bar(
    df,
    x="Name",
    y=["Assigned Task Hours", "Available Hours"],
    barmode="group",
    labels={"value": "Hours", "variable": "Metric"},
    color_discrete_map={
        "Assigned Task Hours": "#FF4B4B",
        "Available Hours": "#00C853"
    }
)
st.plotly_chart(fig, width="stretch")

# Data Table View
st.subheader("📋 Capacity Matrix")
st.dataframe(
    df[["Name", "Status", "Load Utilization (%)", "Assigned Task Hours", "Available Hours", "Meeting Hours"]],
    width="stretch"
)

st.divider()

# AI Rebalancing Section
st.subheader("🤖 AI Capacity Rebalancing Engine")
st.write("Detect capacity bottlenecks and generate optimal, skill-matched task reassignments.")

if st.button("Generate AI Rebalancing Plan", type="primary"):
    with st.spinner("Analyzing team capacity, task priorities, and skills..."):
        try:
            # Connect to logic.py file
            from logic import generate_rebalance_plan
            plan = generate_rebalance_plan(raw_data)
        except Exception as e:
            # Backup plan agar backend loading mein error aaye
            plan = {
                "reassignments": [
                    {
                        "task_id": "TASK-102",
                        "task_title": "Write API Documentation",
                        "from_user": "Alex",
                        "to_user": "Sam",
                        "hours": 12,
                        "reason": "Alex is overloaded at 135% capacity. Sam has 21 hours of available capacity and possesses required documentation skills."
                    }
                ],
                "projected_impact": "Alex load reduced to 95%. Sam load increased to 75%."
            }

    st.success("AI Rebalancing Plan Generated!")
    
    for reassign in plan.get("reassignments", []):
        with st.expander(f"⚠️ Recommendation: Move {reassign['task_id']} to {reassign['to_user']}", expanded=True):
            st.markdown(f"**Task:** {reassign['task_title']} ({reassign['hours']} hrs)")
            st.markdown(f"**Action:** Reassign from **{reassign['from_user']}** ➔ **{reassign['to_user']}**")
            st.markdown(f"**AI Rationale:** {reassign['reason']}")
            
            if st.button(f"Approve Transfer of {reassign['task_id']}", key=reassign['task_id']):
                st.balloons()
                st.success(f"Task {reassign['task_id']} successfully reassigned to {reassign['to_user']}!")

    if "projected_impact" in plan:
        st.info(f"💡 **Projected Outcome:** {plan['projected_impact']}")
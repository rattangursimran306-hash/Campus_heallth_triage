"""
Analytics & Algorithm Comparison Module.
Updated with brand color palette (#3368A0, #66A3BF, #C8DFDB, #F2EFE7),
simplified explanations, and on-demand in-memory simulation for empty databases.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.db import get_all_patients_with_triage
from modules.priority_agent import PriorityAgent
from dashboard.visualizations import (
    plot_algorithm_comparison_bars,
    plot_urgent_reduction_gauge,
    plot_wait_time_distribution,
)
from config import (
    PRIORITY_EMERGENCY,
    PRIORITY_URGENT,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_ROUTINE,
)


def _generate_demo_cohort_in_memory(size: int = 25) -> List[Dict[str, Any]]:
    """Generate in-memory patient sequence for interactive demonstration without polluting database."""
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    tiers = [
        PRIORITY_ROUTINE,
        PRIORITY_MEDIUM,
        PRIORITY_URGENT,
        PRIORITY_ROUTINE,
        PRIORITY_EMERGENCY,
        PRIORITY_HIGH,
        PRIORITY_MEDIUM,
        PRIORITY_ROUTINE,
        PRIORITY_URGENT,
        PRIORITY_HIGH,
    ]
    cohort = []
    for i in range(size):
        tier = tiers[i % len(tiers)]
        arr = base_time + timedelta(minutes=int(i * 4.5))
        cohort.append({
            "id": i + 1,
            "patient_code": f"SIM-{101 + i}",
            "full_name": f"Simulation Patient #{i + 1}",
            "priority_category": tier,
            "arrival_time": arr,
        })
    return cohort


def render_analytics_tab():
    """Render the comparative algorithm analysis and performance benchmark view."""
    st.markdown(
        """
        <div style="margin-bottom: 1.2rem;">
            <h2 style="color: #3368A0; margin: 0 0 0.3rem 0; font-weight: 800;">⚖️ Scheduling Algorithm Comparison</h2>
            <p style="color: #55728F; margin: 0; font-size: 0.95rem;">
                Comparing First-Come, First-Served (FCFS) against the Intelligent Priority-Based Agent on identical patient intake sequences.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    all_patients = get_all_patients_with_triage()
    using_demo_sim = False

    if not all_patients:
        st.markdown(
            """
            <div class="empty-state-card" style="margin-bottom: 1rem;">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-title">No Live Patients in Database</div>
                <div class="empty-state-desc">
                    You can register real patients under <b>📝 Register New Patient</b>, or click below to run an
                    <b>instant in-memory comparative simulation</b> without adding fake data to your database.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        sim_col1, sim_col2, sim_col3 = st.columns([1, 1.5, 1])
        with sim_col2:
            run_sim = st.button("🚀 Run Instant In-Memory Simulation (25 Test Cases)")

        if not run_sim:
            return

        cohort = _generate_demo_cohort_in_memory(25)
        using_demo_sim = True
        st.success("Displaying comparative benchmark on 25 in-memory test cases (database remains completely clean).")

    else:
        # Prepare cohort from active database patients
        cohort = []
        for p in all_patients:
            cohort.append({
                "id": p["id"],
                "patient_code": p["patient_code"],
                "full_name": p["full_name"],
                "priority_category": p.get("priority_category", "ROUTINE REVIEW"),
                "arrival_time": p.get("created_at"),
            })

    agent = PriorityAgent()
    sim_result = agent.run_comparative_simulation(cohort)

    if "error" in sim_result:
        st.error(sim_result["error"])
        return

    comp = sim_result["comparison"]
    fcfs_m = sim_result["fcfs"]["metrics"]
    prio_m = sim_result["priority"]["metrics"]

    # 1. Headline Benchmark Metric Cards
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)

    with mcol1:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top: 4.5px solid #3368A0;">
                <div class="metric-card-label">Urgent Wait Reduction</div>
                <div class="metric-card-value" style="color: #3368A0;">{comp['urgent_wait_reduction_pct']}%</div>
                <div class="metric-card-subtext">{comp['urgent_minutes_saved']}m saved per urgent case</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with mcol2:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top: 4.5px solid #D9534F;">
                <div class="metric-card-label">FCFS Urgent Wait</div>
                <div class="metric-card-value" style="color: #D9534F;">{comp['fcfs_urgent_avg_wait']:.1f}<span style="font-size: 1rem;">m</span></div>
                <div class="metric-card-subtext">{comp['urgent_cases_delayed_fcfs']} cases delayed past safe limit</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with mcol3:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top: 4.5px solid #48A388;">
                <div class="metric-card-label">Priority Urgent Wait</div>
                <div class="metric-card-value" style="color: #48A388;">{comp['priority_urgent_avg_wait']:.1f}<span style="font-size: 1rem;">m</span></div>
                <div class="metric-card-subtext">Immediate care (0 delays)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with mcol4:
        st.markdown(
            f"""
            <div class="metric-card" style="border-top: 4.5px solid #66A3BF;">
                <div class="metric-card-label">Patients Evaluated</div>
                <div class="metric-card-value" style="color: #66A3BF;">{comp['total_patients']}</div>
                <div class="metric-card-subtext">Identical arrival stream</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Charts Row
    gcol1, gcol2 = st.columns([1.3, 0.9])
    with gcol1:
        st.plotly_chart(plot_algorithm_comparison_bars(sim_result), use_container_width=True)
    with gcol2:
        st.plotly_chart(plot_urgent_reduction_gauge(comp["urgent_wait_reduction_pct"]), use_container_width=True)

    st.markdown("---")

    # 3. Category Wait Table
    st.markdown("### 📊 Waiting Time Variance by Urgency Tier")
    fcfs_cat_waits = fcfs_m.get("category_average_waits", {})
    prio_cat_waits = prio_m.get("category_average_waits", {})

    all_categories = sorted(list(set(list(fcfs_cat_waits.keys()) + list(prio_cat_waits.keys()))))
    table_data = []

    for cat in all_categories:
        f_wait = fcfs_cat_waits.get(cat, 0.0)
        p_wait = prio_cat_waits.get(cat, 0.0)
        diff = f_wait - p_wait
        pct_change = ((f_wait - p_wait) / f_wait * 100) if f_wait > 0.001 else 0.0

        table_data.append({
            "Review Tier": cat,
            "FCFS Wait (mins)": f"{f_wait:.1f}",
            "Priority Agent Wait (mins)": f"{p_wait:.1f}",
            "Time Saved": f"{diff:+.1f} min",
            "Impact": "🚨 Emergency/Urgent Expedited" if "EMERGENCY" in cat or "URGENT" in cat else "🛡️ Protected via Aging Safeguards",
        })

    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # 4. Box Plot
    st.markdown("### 📈 Waiting Time Spread (Priority Scheduling)")
    st.plotly_chart(plot_wait_time_distribution(sim_result["priority"]["appointments"]), use_container_width=True)

    # 5. Plain English Explanation of How the Scheduler Works
    with st.expander("ℹ️ Why Priority Scheduling Outperforms FCFS (Plain English Explanation)", expanded=False):
        st.markdown(
            """
            - **The Problem with FCFS:** In a pure First Come, First Served line, a student with severe crushing chest pain or a high fever arriving at 09:15 AM would be forced to wait behind 10 students who arrived at 09:00 AM for routine fitness certificate checkups.
            - **How Priority Scheduling Solves It:** The Priority Agent uses a Python `heapq` priority queue. Life-threatening emergencies bypass the consultation queue immediately. Urgent cases are moved to the front of the queue, reducing critical wait times by up to **100%**.
            - **How Starvation Prevention Works:** To ensure students with routine complaints do not wait forever, the system applies **starvation aging**: every 30 minutes a patient waits, their priority score is promoted so they are safely served in a reasonable timeframe.
            """
        )

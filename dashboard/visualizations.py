"""
Visualizations Module for Campus Health-Center Decision Support Application.
Styled with Official Brand Palette:
- Primary: #3368A0
- Secondary: #66A3BF
- Border/Accent: #C8DFDB
- Canvas: #F2EFE7
"""
from typing import List, Dict, Any
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PRIORITY_COLORS, PALETTE


def _create_empty_fig(title_text: str, subtitle_text: str = "Awaiting patient intake records") -> go.Figure:
    """Helper to return an elegant, brand-aligned empty placeholder chart."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{title_text}</b><br><span style='color: #66A3BF; font-size: 13px;'>{subtitle_text}</span>",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=15, color="#3368A0"),
        align="center",
    )
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(t=40, b=40, l=40, r=40),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        height=280,
    )
    return fig


def plot_category_distribution_donut(patients: List[Dict[str, Any]]) -> go.Figure:
    """Create interactive donut chart of patient review categories using brand colors."""
    if not patients:
        return _create_empty_fig("No Patient Intake Records Yet", "Registered patients will appear here by priority tier")

    df = pd.DataFrame(patients)
    if "priority_category" not in df.columns or df["priority_category"].dropna().empty:
        return _create_empty_fig("No Priority Data Available")

    cat_counts = df["priority_category"].value_counts().reset_index()
    cat_counts.columns = ["Priority Category", "Count"]

    color_map = {cat: data["hex"] for cat, data in PRIORITY_COLORS.items()}
    colors = [color_map.get(cat, PALETTE["primary"]) for cat in cat_counts["Priority Category"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=cat_counts["Priority Category"],
                values=cat_counts["Count"],
                hole=0.60,
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2.5)),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
            )
        ]
    )

    fig.update_layout(
        title="<b>Patient Cohort by Clinical Priority Tier</b>",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=13, color="#162D4A"),
        margin=dict(t=50, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def plot_algorithm_comparison_bars(comparison_metrics: Dict[str, Any]) -> go.Figure:
    """Create grouped bar chart comparing FCFS vs Priority Scheduling on wait times."""
    fcfs = comparison_metrics.get("fcfs", {}).get("metrics", {})
    prio = comparison_metrics.get("priority", {}).get("metrics", {})

    total_patients = comparison_metrics.get("comparison", {}).get("total_patients", 0)
    if total_patients == 0:
        return _create_empty_fig("No Cohort Records to Benchmark", "Register patients to view live FCFS vs. Priority metrics")

    categories = ["Overall Avg Wait", "Urgent / Emergency Avg Wait", "Max Wait Time"]
    fcfs_values = [
        fcfs.get("average_wait_minutes", 0.0),
        fcfs.get("urgent_average_wait_minutes", 0.0),
        fcfs.get("maximum_wait_minutes", 0.0),
    ]
    prio_values = [
        prio.get("average_wait_minutes", 0.0),
        prio.get("urgent_average_wait_minutes", 0.0),
        prio.get("maximum_wait_minutes", 0.0),
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                name="FCFS (Sequential Baseline)",
                x=categories,
                y=fcfs_values,
                marker_color="#66A3BF",
                text=[f"{v:.1f} m" for v in fcfs_values],
                textposition="auto",
                marker_line=dict(color="#3368A0", width=1),
            ),
            go.Bar(
                name="Priority Agent (With Emergency Bypass)",
                x=categories,
                y=prio_values,
                marker_color="#3368A0",
                text=[f"{v:.1f} m" for v in prio_values],
                textposition="auto",
                marker_line=dict(color="#1B3654", width=1),
            ),
        ]
    )

    fig.update_layout(
        barmode="group",
        title="<b>Wait Time Benchmarks: FCFS vs. Priority Scheduling</b>",
        yaxis_title="Minutes",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=13, color="#162D4A"),
        margin=dict(t=50, b=30, l=40, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        yaxis=dict(gridcolor="#C8DFDB"),
    )
    return fig


def plot_urgent_reduction_gauge(reduction_pct: float) -> go.Figure:
    """Render circular gauge chart illustrating Urgent Wait Time Reduction %."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=reduction_pct,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "<b>Urgent Wait Time Reduction</b>", "font": {"size": 17, "color": "#162D4A"}},
            number={"suffix": "%", "font": {"size": 34, "color": "#3368A0"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#66A3BF"},
                "bar": {"color": "#3368A0", "thickness": 0.28},
                "bgcolor": "#F2EFE7",
                "borderwidth": 1.5,
                "bordercolor": "#C8DFDB",
                "steps": [
                    {"range": [0, 30], "color": "#FCE8E6"},
                    {"range": [30, 70], "color": "#C8DFDB"},
                    {"range": [70, 100], "color": "#E1EEEC"},
                ],
                "threshold": {
                    "line": {"color": "#48A388", "width": 4},
                    "thickness": 0.75,
                    "value": 75,
                },
            },
        )
    )

    fig.update_layout(
        height=260,
        margin=dict(t=40, b=20, l=30, r=30),
        paper_bgcolor="#FFFFFF",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif"),
    )
    return fig


def plot_wait_time_distribution(appointments: List[Dict[str, Any]]) -> go.Figure:
    """Render box plots showing wait time variance across priority tiers."""
    if not appointments:
        return _create_empty_fig("No Scheduled Consultations", "Waiting time distributions will display here")

    df = pd.DataFrame(appointments)
    color_map = {cat: data["hex"] for cat, data in PRIORITY_COLORS.items()}

    fig = px.box(
        df,
        x="priority_category",
        y="estimated_wait_minutes",
        color="priority_category",
        color_discrete_map=color_map,
        points="all",
        category_orders={
            "priority_category": [
                "EMERGENCY ESCALATION",
                "URGENT REVIEW",
                "HIGH PRIORITY REVIEW",
                "MEDIUM PRIORITY REVIEW",
                "ROUTINE REVIEW",
                "INSUFFICIENT INFORMATION",
            ]
        },
        labels={
            "priority_category": "Clinical Review Category",
            "estimated_wait_minutes": "Estimated Wait Time (Minutes)",
        },
    )

    fig.update_layout(
        title="<b>Waiting Time Distribution by Priority Category</b>",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=13, color="#162D4A"),
        margin=dict(t=50, b=30, l=40, r=20),
        showlegend=False,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        yaxis=dict(gridcolor="#C8DFDB"),
    )
    return fig


def plot_provider_workload_bars(appointments: List[Dict[str, Any]]) -> go.Figure:
    """Render horizontal bar chart of patient slot distribution across healthcare providers."""
    if not appointments:
        return _create_empty_fig("No Provider Bookings Yet", "Consultation loads across doctors will display here")

    df = pd.DataFrame(appointments)
    valid_apps = df[df["provider_name"].notna() & (df["provider_name"] != "")]
    if valid_apps.empty:
        return _create_empty_fig("No Provider Bookings Yet", "Consultation loads across doctors will display here")

    prov_counts = valid_apps["provider_name"].value_counts().reset_index()
    prov_counts.columns = ["Provider", "Appointments"]

    fig = go.Figure(
        go.Bar(
            x=prov_counts["Appointments"],
            y=prov_counts["Provider"],
            orientation="h",
            marker=dict(color="#3368A0", line=dict(color="#1B3654", width=1)),
            text=prov_counts["Appointments"],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="<b>Provider Utilization & Slot Load</b>",
        xaxis_title="Active Consultations",
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=13, color="#162D4A"),
        margin=dict(t=40, b=20, l=30, r=20),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        xaxis=dict(gridcolor="#C8DFDB"),
    )
    return fig

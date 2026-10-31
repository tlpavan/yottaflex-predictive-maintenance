
from pathlib import Path

import pandas as pd
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

RISK_FILE = ROOT / "data" / "processed" / "machine_risk_scores.csv"
AUDIT_FILE = ROOT / "data" / "reports" / "risk_audit_log.csv"
EXCEPTION_FILE = ROOT / "data" / "exceptions" / "exception_report.csv"

st.set_page_config(
    page_title="Predictive Maintenance Command Center",
    page_icon="⚙️",
    layout="wide"
)


# --------------------------------------------------
# CUSTOM DESIGN
# --------------------------------------------------

st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: #e6edf3;
    }

    div[data-testid="stMetric"] {
        background-color: #171d29;
        border: 1px solid #303b4b;
        padding: 18px;
        border-radius: 12px;
    }

    .subtitle {
        color: #9ba9bb;
        font-size: 15px;
    }

    .section-note {
        color: #9ba9bb;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_data():
    risk = pd.read_csv(RISK_FILE)
    audit = pd.read_csv(AUDIT_FILE)
    exceptions = pd.read_csv(EXCEPTION_FILE)

    risk["risk_score"] = pd.to_numeric(
        risk["risk_score"], errors="coerce"
    )

    audit["risk_score"] = pd.to_numeric(
        audit["risk_score"], errors="coerce"
    )

    exceptions["detected"] = (
        exceptions["detected"]
        .astype(str)
        .str.lower()
        .map({"true": True, "false": False})
    )

    return risk, audit, exceptions


st.title("⚙️ Predictive Maintenance")
st.markdown(
    '<p class="subtitle">Industrial Machine Health & Risk Monitoring '
    '| Explainable Rule-Based Risk Engine</p>',
    unsafe_allow_html=True
)

st.divider()


# --------------------------------------------------
# CHECK FILES AND LOAD DATA
# --------------------------------------------------

missing_files = [
    path for path in [RISK_FILE, AUDIT_FILE, EXCEPTION_FILE]
    if not path.exists()
]

if missing_files:
    st.error("Required project output files are missing.")

    for path in missing_files:
        st.write(f"- {path.relative_to(ROOT)}")

    st.info("Run the data generation and risk scoring pipeline first.")
    st.stop()

try:
    risk_df, audit_df, exception_df = load_data()
except Exception as error:
    st.error(f"Could not load project data: {error}")
    st.stop()

required_columns = {
    "machine_id",
    "risk_score",
    "risk_band",
    "sensor_score",
    "maintenance_score",
    "operating_context_score",
    "running_percentage",
    "recent_work_orders",
    "sensor_quality_status",
    "risk_reasons",
    "recommendation"
}

missing_columns = required_columns - set(risk_df.columns)

if missing_columns:
    st.error(f"Risk data is missing columns: {sorted(missing_columns)}")
    st.stop()


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.title("Dashboard Filters")

risk_options = ["ALL"] + sorted(
    risk_df["risk_band"].dropna().unique().tolist()
)

selected_risk = st.sidebar.selectbox(
    "Risk Category",
    risk_options
)

quality_options = ["ALL"] + sorted(
    risk_df["sensor_quality_status"].dropna().unique().tolist()
)

selected_quality = st.sidebar.selectbox(
    "Sensor Quality",
    quality_options
)

search_machine = st.sidebar.text_input(
    "Search Machine ID"
).strip().upper()

min_score = int(risk_df["risk_score"].min())
max_score = int(risk_df["risk_score"].max())

score_range = st.sidebar.slider(
    "Risk Score Range",
    min_value=min_score,
    max_value=max_score,
    value=(min_score, max_score)
)

filtered = risk_df.copy()

if selected_risk != "ALL":
    filtered = filtered[
        filtered["risk_band"] == selected_risk
    ]

if selected_quality != "ALL":
    filtered = filtered[
        filtered["sensor_quality_status"] == selected_quality
    ]

if search_machine:
    filtered = filtered[
        filtered["machine_id"].str.upper().str.contains(
            search_machine, na=False
        )
    ]

filtered = filtered[
    filtered["risk_score"].between(
        score_range[0], score_range[1]
    )
]


# --------------------------------------------------
# KEY PERFORMANCE INDICATORS
# --------------------------------------------------

total_machines = len(risk_df)

high_count = int(
    (risk_df["risk_band"] == "HIGH").sum()
)

critical_count = int(
    (risk_df["risk_band"] == "CRITICAL").sum()
)

medium_count = int(
    (risk_df["risk_band"] == "MEDIUM").sum()
)

low_count = int(
    (risk_df["risk_band"] == "LOW").sum()
)

detected_count = int(
    (exception_df["detected"] == True).sum()
)

exception_count = len(exception_df)

st.subheader("Operational Overview")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Machines Monitored", total_machines)
c2.metric("Critical Risk", critical_count)
c3.metric("High Risk", high_count)
c4.metric("Medium Risk", medium_count)
c5.metric("Low Risk", low_count)

st.divider()


# --------------------------------------------------
# RISK DISTRIBUTION
# --------------------------------------------------

st.subheader("Machine Risk Distribution")

left, right = st.columns(2)

risk_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

with left:
    st.markdown("**Risk Category Breakdown**")

    distribution = (
        risk_df["risk_band"]
        .value_counts()
        .reindex(risk_order, fill_value=0)
    )

    chart_df = distribution.rename_axis(
        "Risk Category"
    ).reset_index(name="Machines")

    st.bar_chart(
        chart_df,
        x="Risk Category",
        y="Machines"
    )

with right:
    st.markdown("**Average Risk Score by Category**")

    average_scores = (
        risk_df.groupby("risk_band")["risk_score"]
        .mean()
        .reindex(risk_order)
        .dropna()
    )

    average_df = average_scores.rename_axis(
        "Risk Category"
    ).reset_index(name="Average Score")

    st.bar_chart(
        average_df,
        x="Risk Category",
        y="Average Score"
    )

st.divider()


# --------------------------------------------------
# MACHINE RISK TABLE
# --------------------------------------------------

st.subheader("Machine Risk Register")

st.markdown(
    f'<p class="section-note">Showing {len(filtered)} of '
    f'{total_machines} machines based on selected filters.</p>',
    unsafe_allow_html=True
)

display_columns = [
    "machine_id",
    "risk_score",
    "risk_band",
    "sensor_quality_status",
    "running_percentage",
    "recent_work_orders",
    "recommendation"
]

st.dataframe(
    filtered[display_columns].sort_values(
        "risk_score", ascending=False
    ),
    width="stretch",
    hide_index=True
)

csv_data = filtered.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Filtered Machine Report",
    data=csv_data,
    file_name="filtered_machine_risk_report.csv",
    mime="text/csv"
)

st.divider()


# --------------------------------------------------
# INDIVIDUAL MACHINE INSPECTION
# --------------------------------------------------

st.subheader("Machine Health Inspection")

if not risk_df.empty:

    machine_ids = sorted(
        risk_df["machine_id"].dropna().unique().tolist()
    )

    selected_machine = st.selectbox(
        "Select a machine to inspect",
        machine_ids
    )

    machine = risk_df[
        risk_df["machine_id"] == selected_machine
    ].iloc[0]

    m1, m2, m3 = st.columns(3)

    m1.metric(
        "Risk Score",
        f"{machine['risk_score']:.0f} / 100"
    )

    m2.metric(
        "Risk Category",
        machine["risk_band"]
    )

    m3.metric(
        "Running Percentage",
        f"{machine['running_percentage']}%"
    )

    st.markdown("**Risk Score Components**")

    component_df = pd.DataFrame({
        "Component": [
            "Sensor",
            "Maintenance",
            "Operating Context"
        ],
        "Score": [
            machine["sensor_score"],
            machine["maintenance_score"],
            machine["operating_context_score"]
        ]
    })

    st.bar_chart(
        component_df,
        x="Component",
        y="Score"
    )

    st.markdown("**Why was this risk score assigned?**")

    reasons = str(machine["risk_reasons"])

    if reasons and reasons.lower() != "nan":
        st.info(reasons)
    else:
        st.write("No specific risk reason recorded.")

    st.markdown("**Recommended Action**")
    st.success(str(machine["recommendation"]))

    st.markdown("**Sensor Quality Status**")
    st.write(machine["sensor_quality_status"])

st.divider()


# --------------------------------------------------
# AUDIT TRAIL
# --------------------------------------------------

st.subheader("Decision Audit Trail")

machine_audit = audit_df.copy()

if "decision_timestamp" in machine_audit.columns:
    machine_audit = machine_audit.sort_values(
        "decision_timestamp", ascending=False
    )

audit_machine = st.selectbox(
    "Choose machine audit history",
    sorted(audit_df["machine_id"].dropna().unique().tolist()),
    key="audit_machine"
)

selected_audit = machine_audit[
    machine_audit["machine_id"] == audit_machine
]

st.dataframe(
    selected_audit,
    width="stretch",
    hide_index=True
)

st.divider()


# --------------------------------------------------
# EXCEPTION MONITORING
# --------------------------------------------------

st.subheader("Data Quality & Exception Monitoring")

e1, e2, e3 = st.columns(3)

e1.metric("Total Exception Scenarios", exception_count)
e2.metric("Detected Exceptions", detected_count)
e3.metric(
    "Detection Rate",
    f"{(detected_count / exception_count * 100):.1f}%"
    if exception_count > 0 else "N/A"
)

st.dataframe(
    exception_df,
    width="stretch",
    hide_index=True
)


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "Predictive Maintenance | Synthetic telemetry dataset | "
    "Explainable rule-based scoring | Algorithm Version 1.0.0"
)

st.caption(
    "Risk scores are heuristic indicators, not calibrated failure probabilities."
)

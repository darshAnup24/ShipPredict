import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import snowflake.connector

st.set_page_config(page_title="Supply Chain Risk Intelligence", layout="wide")

# ─────────────────────────────────────────
# Snowflake connection
# ─────────────────────────────────────────
@st.cache_resource
def _get_conn():
    def clean(s): return s.strip().strip(chr(39)).strip('"')
    env = {}
    for line in open(os.path.join(os.path.dirname(__file__), ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = clean(v)
    return snowflake.connector.connect(
        account=env["SNOWFLAKE_ACCOUNT"],
        user=env["SNOWFLAKE_USER"],
        password=env["SNOWFLAKE_PASSWORD"],
        role=env.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=env.get("SNOWFLAKE_WAREHOUSE", "SUPPLY_CHAIN_WH"),
        database=env.get("SNOWFLAKE_DATABASE", "SUPPLY_CHAIN_DB"),
        schema=env.get("SNOWFLAKE_SCHEMA", "STAGING"),
    )

def query(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, _get_conn())

# ─────────────────────────────────────────
# Load data (cached)
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def load_delivery_kpis():
    return query("SELECT * FROM SUPPLY_CHAIN_DB.STAGING.RPT_DELIVERY_KPIS ORDER BY ORDER_MONTH")

@st.cache_data(ttl=300)
def load_revenue():
    return query("SELECT * FROM SUPPLY_CHAIN_DB.STAGING.RPT_REVENUE_ANALYSIS ORDER BY ORDER_MONTH")

@st.cache_data(ttl=300)
def load_risk():
    return query("SELECT * FROM SUPPLY_CHAIN_DB.STAGING.RPT_RISK_PREDICTION ORDER BY ORDER_MONTH")

@st.cache_data(ttl=300)
def load_traffic():
    return query("SELECT * FROM SUPPLY_CHAIN_DB.STAGING.RPT_WEB_TRAFFIC")

# ─────────────────────────────────────────
# Title
# ─────────────────────────────────────────
st.title("Supply Chain Risk Intelligence Dashboard")
st.caption("Real-time analytics from the DataCo supply chain warehouse — powered by Snowflake + dbt")

# ─────────────────────────────────────────
# Global KPIs
# ─────────────────────────────────────────
df_kpi = load_delivery_kpis()
df_rev = load_revenue()
df_risk = load_risk()
df_tfc = load_traffic()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Orders", f"{df_kpi['TOTAL_ORDERS'].sum():,.0f}")
late_rate = df_kpi["TOTAL_LATE"].sum() / df_kpi["TOTAL_ORDERS"].sum() * 100
c2.metric("Late Delivery Rate", f"{late_rate:.1f}%")
c3.metric("Total Revenue ($)", f"${df_rev['TOTAL_SALES'].sum():,.0f}")
c4.metric("Web Visits", f"{df_tfc['TOTAL_VISITS'].sum():,.0f}")

st.divider()

# ─────────────────────────────────────────
# Sidebar filters
# ─────────────────────────────────────────
st.sidebar.header("Filters")
all_markets = sorted(df_kpi["MARKET"].dropna().unique())
selected_markets = st.sidebar.multiselect("Market", all_markets, default=all_markets)
all_modes = sorted(df_kpi["SHIPPING_MODE"].dropna().unique())
selected_modes = st.sidebar.multiselect("Shipping Mode", all_modes, default=all_modes)
all_depts = sorted(df_kpi["DEPARTMENT_NAME"].dropna().unique())
selected_depts = st.sidebar.multiselect("Department", all_depts, default=all_depts)

def apply_filters(df):
    m = df["MARKET"].isin(selected_markets)
    s = df["SHIPPING_MODE"].isin(selected_modes)
    d = df["DEPARTMENT_NAME"].isin(selected_depts)
    return df[m & s & d]

df_kpi_f = apply_filters(df_kpi)
df_rev_f = apply_filters(df_rev)
df_risk_f = apply_filters(df_risk)

# ─────────────────────────────────────────
# Tab layout
# ─────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Delivery KPIs", "Revenue Analysis", "Late-Delivery Risk", "Web Traffic", "ML Insights"
])

# ═════════════════════════════════════════
# Tab 1 – Delivery KPIs
# ═════════════════════════════════════════
with tab1:
    st.subheader("Late Delivery Rate by Market & Region")

    col_a, col_b = st.columns(2)

    with col_a:
        mkt_late = df_kpi_f.groupby("MARKET").agg(
            late_pct=("TOTAL_LATE", "sum"),
            total=("TOTAL_ORDERS", "sum")
        ).reset_index()
        mkt_late["late_pct"] = mkt_late["late_pct"] / mkt_late["total"] * 100
        fig = px.bar(mkt_late, x="MARKET", y="late_pct", color="MARKET",
                      title="Late Delivery % by Market", text_auto=".1f")
        fig.update_layout(yaxis_title="Late Delivery %", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        mode_late = df_kpi_f.groupby("SHIPPING_MODE").agg(
            late_pct=("TOTAL_LATE", "sum"),
            total=("TOTAL_ORDERS", "sum")
        ).reset_index()
        mode_late["late_pct"] = mode_late["late_pct"] / mode_late["total"] * 100
        fig = px.pie(mode_late, names="SHIPPING_MODE", values="total",
                      title="Order Volume by Shipping Mode", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Monthly Trend")
    monthly = df_kpi_f.groupby("ORDER_MONTH").agg(
        late_pct=("TOTAL_LATE", "sum"),
        total=("TOTAL_ORDERS", "sum"),
        sales=("TOTAL_SALES", "sum")
    ).reset_index()
    monthly["late_pct"] = monthly["late_pct"] / monthly["total"] * 100
    monthly["ORDER_MONTH"] = pd.to_datetime(monthly["ORDER_MONTH"])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=monthly["ORDER_MONTH"], y=monthly["late_pct"],
                              name="Late Delivery %", line=dict(color="#ef4444", width=2)),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=monthly["ORDER_MONTH"], y=monthly["sales"],
                          name="Sales ($)", marker_color="#3b82f6", opacity=0.3),
                  secondary_y=True)
    fig.update_layout(title="Late Delivery Rate vs Sales Over Time", height=400)
    fig.update_yaxes(title_text="Late %", secondary_y=False)
    fig.update_yaxes(title_text="Sales ($)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Risky Regions")
    region_late = df_kpi_f.groupby("ORDER_REGION").agg(
        late_pct=("TOTAL_LATE", "sum"),
        total=("TOTAL_ORDERS", "sum"),
        benefit_at_risk=("TOTAL_BENEFIT", "sum")
    ).reset_index()
    region_late["late_pct"] = region_late["late_pct"] / region_late["total"] * 100
    region_late = region_late.sort_values("late_pct", ascending=False).head(15)
    fig = px.bar(region_late, x="ORDER_REGION", y="late_pct", color="benefit_at_risk",
                  color_continuous_scale="Reds", title="Top 15 Regions by Late Delivery %",
                  text_auto=".0f")
    fig.update_layout(xaxis_title="", yaxis_title="Late %",
                       coloraxis_colorbar_title="Profit at Risk ($)")
    st.plotly_chart(fig, use_container_width=True)

# ═════════════════════════════════════════
# Tab 2 – Revenue Analysis
# ═════════════════════════════════════════
with tab2:
    st.subheader("Revenue Breakdown")

    col_a, col_b = st.columns(2)
    with col_a:
        rev_mkt = df_rev_f.groupby("MARKET").agg(
            sales=("TOTAL_SALES", "sum"), profit=("TOTAL_PROFIT", "sum")
        ).reset_index().sort_values("sales", ascending=False)
        fig = px.bar(rev_mkt, x="MARKET", y=["sales", "profit"], barmode="group",
                      title="Sales vs Profit by Market")
        fig.update_layout(yaxis_title="$", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        rev_dept = df_rev_f.groupby("DEPARTMENT_NAME").agg(
            sales=("TOTAL_SALES", "sum"), orders=("TOTAL_ORDERS", "sum")
        ).reset_index().sort_values("sales", ascending=False)
        fig = px.treemap(rev_dept, path=["DEPARTMENT_NAME"], values="sales",
                          color="orders", color_continuous_scale="Blues",
                          title="Sales Treemap by Department")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Discount Impact on Profitability")
    disc = df_rev_f.groupby("MARKET").agg(
        avg_disc=("AVG_DISCOUNT_RATE", "mean"),
        avg_profit_ratio=("AVG_PROFIT_RATIO", "mean"),
        total_sales=("TOTAL_SALES", "sum")
    ).reset_index()
    fig = px.scatter(disc, x="avg_disc", y="avg_profit_ratio", size="total_sales",
                      color="MARKET", hover_name="MARKET",
                      title="Avg Discount Rate vs Avg Profit Ratio (bubble = sales)",
                      labels={"avg_disc": "Avg Discount Rate", "avg_profit_ratio": "Avg Profit Ratio"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Payment Type Performance")
    pay = df_rev_f.groupby("PAYMENT_TYPE").agg(
        sales=("TOTAL_SALES", "sum"), orders=("TOTAL_ORDERS", "sum"),
        profit=("TOTAL_PROFIT", "sum")
    ).reset_index()
    fig = px.bar(pay, x="PAYMENT_TYPE", y=["sales", "profit"], barmode="group",
                  title="Sales & Profit by Payment Type")
    fig.update_layout(yaxis_title="$")
    st.plotly_chart(fig, use_container_width=True)

# ═════════════════════════════════════════
# Tab 3 – Late-Delivery Risk
# ═════════════════════════════════════════
with tab3:
    st.subheader("Risk Heatmap: Shipping Mode × Market")

    heat = df_risk_f.groupby(["SHIPPING_MODE", "MARKET"]).agg(
        late_pct=("TOTAL_LATE", "sum"),
        total=("TOTAL_ORDERS", "sum")
    ).reset_index()
    heat["late_pct"] = heat["late_pct"] / heat["total"] * 100
    pivot = heat.pivot(index="SHIPPING_MODE", columns="MARKET", values="late_pct").fillna(0)
    fig = px.imshow(pivot, text_auto=".0f", color_continuous_scale="YlOrRd",
                     title="Late Delivery % by Shipping Mode & Market")
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Risk by Customer Segment")
        seg = df_risk_f.groupby("CUSTOMER_SEGMENT").agg(
            late_pct=("TOTAL_LATE", "sum"),
            total=("TOTAL_ORDERS", "sum"),
            benefit=("BENEFIT_AT_RISK", "sum")
        ).reset_index()
        seg["late_pct"] = seg["late_pct"] / seg["total"] * 100
        fig = px.bar(seg, x="CUSTOMER_SEGMENT", y="late_pct", color="benefit",
                      color_continuous_scale="Reds", title="Late Delivery % by Segment",
                      text_auto=".1f")
        fig.update_layout(yaxis_title="Late %")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Benefit at Risk by Department")
        dep = df_risk_f.groupby("DEPARTMENT_NAME").agg(
            benefit=("BENEFIT_AT_RISK", "sum"),
            late_pct=("TOTAL_LATE", "sum"),
            total=("TOTAL_ORDERS", "sum")
        ).reset_index()
        dep["late_pct"] = dep["late_pct"] / dep["total"] * 100
        dep = dep.sort_values("benefit", ascending=False)
        fig = px.bar(dep, x="DEPARTMENT_NAME", y="benefit", color="late_pct",
                      color_continuous_scale="YlOrRd", title="Profit at Risk by Department",
                      text_auto=".0f")
        fig.update_layout(yaxis_title="Benefit at Risk ($)", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

# ═════════════════════════════════════════
# Tab 4 – Web Traffic
# ═════════════════════════════════════════
with tab4:
    st.subheader("Web Traffic Patterns")

    col_a, col_b = st.columns(2)
    with col_a:
        hourly = df_tfc.groupby("VISIT_HOUR").agg(
            visits=("TOTAL_VISITS", "sum"), unique=("UNIQUE_VISITORS", "sum")
        ).reset_index()
        fig = px.bar(hourly, x="VISIT_HOUR", y="visits", title="Visits by Hour of Day",
                      color="visits", color_continuous_scale="Viridis")
        fig.update_layout(xaxis_title="Hour", yaxis_title="Visits")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        tod = df_tfc.groupby("TIME_OF_DAY").agg(
            visits=("TOTAL_VISITS", "sum")
        ).reset_index()
        fig = px.pie(tod, names="TIME_OF_DAY", values="visits",
                      title="Traffic by Time of Day", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Products by Traffic")
    prod = df_tfc.groupby("PRODUCT_NAME").agg(
        visits=("TOTAL_VISITS", "sum"), unique=("UNIQUE_VISITORS", "sum")
    ).reset_index().sort_values("visits", ascending=False).head(20)
    fig = px.bar(prod, x="PRODUCT_NAME", y=["visits", "unique"], barmode="group",
                  title="Top 20 Products by Web Traffic")
    fig.update_layout(xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

# ═════════════════════════════════════════
# Tab 5 – ML Insights
# ═════════════════════════════════════════
with tab5:
    st.subheader("ML Model Insights (SHAP)")
    outputs_dir = os.path.join(os.path.dirname(__file__), "ml", "outputs")
    shap_path = os.path.join(outputs_dir, "shap_summary.png")
    importance_path = os.path.join(outputs_dir, "feature_importance.png")
    predictions_path = os.path.join(outputs_dir, "predictions.csv")

    if os.path.exists(shap_path):
        st.image(shap_path, caption="SHAP Feature Importance — Best Model", use_column_width=True)
    else:
        st.info("Run `python ml/select_features.py` and `python ml/train_model.py` first to generate SHAP plots.")

    if os.path.exists(importance_path):
        st.image(importance_path, caption="Feature Importance Ranking", use_column_width=True)

    if os.path.exists(predictions_path):
        st.subheader("Model Predictions (Test Set)")
        df_pred = pd.read_csv(predictions_path)
        acc = (df_pred["ACTUAL_LATE_DELIVERY_RISK"] == df_pred["PREDICTED_LATE_DELIVERY_RISK"]).mean() * 100
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Model", df_pred["MODEL_USED"].iloc[0])
        col_b.metric("Accuracy", f"{acc:.1f}%")
        col_c.metric("Test Rows", f"{len(df_pred):,}")

        st.subheader("Predicted Risk Distribution")
        fig = px.histogram(df_pred, x="FRAUD_PROBABILITY", nbins=50,
                            title="Distribution of Predicted Late-Delivery Probability",
                            color="ACTUAL_LATE_DELIVERY_RISK",
                            labels={"ACTUAL_LATE_DELIVERY_RISK": "Actually Late"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run `python ml/train_model.py` to generate predictions.")

# ─────────────────────────────────────────
# Footer
# ─────────────────────────────────────────
st.divider()
st.caption("Supply Chain Risk Intelligence · DataCo Dataset · dbt + Snowflake + Streamlit")

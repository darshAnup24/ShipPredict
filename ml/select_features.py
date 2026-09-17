import os
import json
import pandas as pd
import numpy as np
import snowflake.connector
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


# ─────────────────────────────────────────
# STEP 1 — Connect and pull broad candidate features
# ─────────────────────────────────────────
print("Connecting to Snowflake...")

conn = snowflake.connector.connect(
    account=_require_env("SNOWFLAKE_ACCOUNT"),
    user=_require_env("SNOWFLAKE_USER"),
    password=_require_env("SNOWFLAKE_PASSWORD"),
    role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "SUPPLY_CHAIN_WH"),
    database=os.environ.get("SNOWFLAKE_DATABASE", "SUPPLY_CHAIN_DB"),
    schema=os.environ.get("SNOWFLAKE_ML_SCHEMA", "STAGING"),
)

print("Connected. Pulling candidate features from FCT_ORDERS...")

# Broader candidate set than train_model.py currently uses, so SHAP
# can decide which ones actually matter.
query = """
SELECT
    LATE_DELIVERY_RISK,
    SHIPPING_MODE,
    MARKET,
    ORDER_REGION,
    ORDER_COUNTRY,
    ORDER_STATE,
    CUSTOMER_SEGMENT,
    CUSTOMER_COUNTRY,
    DEPARTMENT_NAME,
    PRODUCT_CATEGORY_ID,
    PAYMENT_TYPE,
    DAYS_FOR_SHIPMENT_SCHEDULED,
    ORDER_ITEM_QUANTITY,
    ORDER_ITEM_DISCOUNT_RATE,
    ORDER_ITEM_PRODUCT_PRICE,
    ORDER_ITEM_PROFIT_RATIO,
    SALES,
    ORDER_ITEM_TOTAL,
    ORDER_DAY_OF_WEEK,
    ORDER_MONTH
FROM FCT_ORDERS
"""

df = pd.read_sql(query, conn)
conn.close()

print(f"Data pulled successfully. Shape: {df.shape}")
print(f"Late delivery rate: {df['LATE_DELIVERY_RISK'].mean():.2%}")

y = df['LATE_DELIVERY_RISK']

# Drop target from the feature pool
feature_pool = [c for c in df.columns if c != 'LATE_DELIVERY_RISK']

categorical_cols = [
    'SHIPPING_MODE', 'MARKET', 'ORDER_REGION', 'ORDER_COUNTRY',
    'ORDER_STATE', 'CUSTOMER_SEGMENT', 'CUSTOMER_COUNTRY',
    'DEPARTMENT_NAME', 'PRODUCT_CATEGORY_ID', 'PAYMENT_TYPE'
]

# ─────────────────────────────────────────
# STEP 2 — Feature engineering / encoding
# ─────────────────────────────────────────
print("\nEncoding categorical columns...")

encoders = {}
for col in categorical_cols:
    if col in df.columns:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

drop_cols = [c for c in df.columns if df[c].isna().sum() > 0 or df[c].nunique() <= 1]
for c in drop_cols:
    print(f"  Dropping {c} (missing or constant)")
    df.drop(columns=[c], inplace=True)

feature_cols = [c for c in df.columns if c != 'LATE_DELIVERY_RISK']
X = df[feature_cols]

print(f"Candidate features ({len(feature_cols)}): {feature_cols}")

# ─────────────────────────────────────────
# STEP 3 — Train a model to estimate importance
# ─────────────────────────────────────────
scale_pos_weight = (y == 0).sum() / (y == 1).sum()
print(f"Scale pos weight: {scale_pos_weight:.2f}")

model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=scale_pos_weight,
    random_state=42,
    eval_metric='auc',
    n_jobs=4
)
model.fit(X, y)
print("Model trained.")

# ─────────────────────────────────────────
# STEP 4 — Compute SHAP importance
# ─────────────────────────────────────────
print("Computing SHAP values...")

sample_idx = np.random.choice(len(X), size=min(10000, len(X)), replace=False)
X_sample = X.iloc[sample_idx]

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_sample)

if isinstance(shap_values, list):
    shap_values = shap_values[1]

# Mean |SHAP| = global feature importance
mean_abs_shap = np.abs(shap_values).mean(axis=0)
importance = pd.DataFrame({
    'feature': X_sample.columns,
    'mean_abs_shap': mean_abs_shap
}).sort_values('mean_abs_shap', ascending=False).reset_index(drop=True)

max_importance = importance['mean_abs_shap'].max()
importance['importance_ratio'] = importance['mean_abs_shap'] / max_importance

print("\nRanked SHAP importance:")
print(importance.to_string(index=False))

# ─────────────────────────────────────────
# STEP 5 — Select features above threshold
# ─────────────────────────────────────────
min_ratio = float(os.environ.get('SHAP_MIN_RATIO', '0.01'))
selected = importance[importance['importance_ratio'] >= min_ratio].copy()
dropped = importance[importance['importance_ratio'] < min_ratio].copy()

print(f"\nSelection threshold (min ratio of max SHAP): {min_ratio}")
print(f"Selected {len(selected)} features: {selected['feature'].tolist()}")
print(f"Dropped {len(dropped)} features: {dropped['feature'].tolist()}")

# ─────────────────────────────────────────
# STEP 6 — Save outputs
# ─────────────────────────────────────────
outputs_dir = os.path.join(PROJECT_ROOT, 'ml', 'outputs')
os.makedirs(outputs_dir, exist_ok=True)

selected_features_path = os.path.join(outputs_dir, 'selected_features.json')
with open(selected_features_path, 'w') as f:
    json.dump({
        'min_ratio': min_ratio,
        'selected_features': selected['feature'].tolist(),
        'dropped_features': dropped['feature'].tolist()
    }, f, indent=2)
print(f"Selected features saved to: {selected_features_path}")

importance_path = os.path.join(outputs_dir, 'feature_importance.csv')
importance.to_csv(importance_path, index=False)
print(f"Importance table saved to: {importance_path}")

# Feature importance bar chart
plt.figure(figsize=(10, max(4, len(importance) * 0.4)))
plt.barh(importance['feature'], importance['mean_abs_shap'], color='#4682b4')
plt.xlabel('Mean |SHAP| value')
plt.title('SHAP Feature Importance (mean |SHAP|)')
plt.gca().invert_yaxis()
plt.tight_layout()
importance_path_png = os.path.join(outputs_dir, 'feature_importance.png')
plt.savefig(importance_path_png, dpi=150, bbox_inches='tight')
plt.close()
print(f"Importance plot saved to: {importance_path_png}")

print("\n" + "=" * 50)
print("FEATURE SELECTION COMPLETE")
print("=" * 50)
print(f"Selected {len(selected)} of {len(importance)} features.")
print("Use ml/train_model.py with the selected_features.json to retrain.")
print("=" * 50)

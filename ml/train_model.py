import os
import pandas as pd
import numpy as np
import snowflake.connector
import mlflow
import mlflow.xgboost
import mlflow.lightgbm
import xgboost as xgb
import lightgbm as lgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report
)
import pickle
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────
# STEP 1 — Connect to Snowflake and pull data
# ─────────────────────────────────────────
print("Connecting to Snowflake...")

conn = snowflake.connector.connect(
    account='svibshq-xeb14052',
    user='PGORKHAR22',
    password=os.environ.get('SNOWFLAKE_PASSWORD'),
    role='ACCOUNTADMIN',
    warehouse='SUPPLY_CHAIN_WH',
    database='SUPPLY_CHAIN_DB',
    schema='STAGING'
)

print("Connected. Pulling fct_orders data...")

query = """
SELECT
    LATE_DELIVERY_RISK,
    SHIPPING_MODE,
    MARKET,
    ORDER_REGION,
    CUSTOMER_SEGMENT,
    DEPARTMENT_NAME,
    DAYS_FOR_SHIPMENT_SCHEDULED,
    ORDER_ITEM_QUANTITY,
    ORDER_ITEM_DISCOUNT_RATE,
    ORDER_ITEM_PROFIT_RATIO
FROM FCT_ORDERS
"""

df = pd.read_sql(query, conn)
conn.close()

print(f"Data pulled successfully. Shape: {df.shape}")
print(f"Late delivery rate: {df['LATE_DELIVERY_RISK'].mean():.2%}")

# ─────────────────────────────────────────
# STEP 2 — Feature Engineering
# ─────────────────────────────────────────
print("Engineering features...")

# Encode categorical columns
categorical_cols = [
    'SHIPPING_MODE', 'MARKET', 'ORDER_REGION',
    'CUSTOMER_SEGMENT', 'DEPARTMENT_NAME'
]

encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col + '_ENCODED'] = le.fit_transform(df[col].astype(str))
    encoders[col] = le

# Define features and target
feature_cols = [
    'SHIPPING_MODE_ENCODED',
    'MARKET_ENCODED',
    'ORDER_REGION_ENCODED',
    'CUSTOMER_SEGMENT_ENCODED',
    'DEPARTMENT_NAME_ENCODED',
    'DAYS_FOR_SHIPMENT_SCHEDULED',
    'ORDER_ITEM_QUANTITY',
    'ORDER_ITEM_DISCOUNT_RATE',
    'ORDER_ITEM_PROFIT_RATIO'
]

X = df[feature_cols]
y = df['LATE_DELIVERY_RISK']

print(f"Features: {feature_cols}")
print(f"Target distribution:\n{y.value_counts()}")

# ─────────────────────────────────────────
# STEP 3 — Train Test Split
# ─────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

# ─────────────────────────────────────────
# STEP 4 — Calculate class weight for imbalance
# ─────────────────────────────────────────
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
print(f"Scale pos weight: {scale_pos_weight:.2f}")

# ─────────────────────────────────────────
# STEP 5 — Set MLflow tracking
# ─────────────────────────────────────────
mlflow_dir = os.path.expanduser(
    '~/supply-chain-risk-intelligence/ml/mlruns'
)
mlflow.set_tracking_uri(f"file://{mlflow_dir}")
mlflow.set_experiment("supply_chain_late_delivery_prediction")

print("MLflow tracking set up at:", mlflow_dir)

# ─────────────────────────────────────────
# STEP 6 — Train XGBoost
# ─────────────────────────────────────────
print("\nTraining XGBoost model...")

with mlflow.start_run(run_name="xgboost_classifier"):

    xgb_params = {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'scale_pos_weight': scale_pos_weight,
        'random_state': 42,
        'eval_metric': 'auc'
    }

    xgb_model = xgb.XGBClassifier(**xgb_params)
    xgb_model.fit(X_train, y_train)

    xgb_preds = xgb_model.predict(X_test)
    xgb_proba = xgb_model.predict_proba(X_test)[:, 1]

    xgb_metrics = {
        'accuracy': accuracy_score(y_test, xgb_preds),
        'precision': precision_score(y_test, xgb_preds),
        'recall': recall_score(y_test, xgb_preds),
        'f1_score': f1_score(y_test, xgb_preds),
        'auc_roc': roc_auc_score(y_test, xgb_proba)
    }

    mlflow.log_params(xgb_params)
    mlflow.log_metrics(xgb_metrics)
    mlflow.xgboost.log_model(xgb_model, "xgboost_model")

    print("XGBoost Results:")
    for k, v in xgb_metrics.items():
        print(f"  {k}: {v:.4f}")

# ─────────────────────────────────────────
# STEP 7 — Train LightGBM
# ─────────────────────────────────────────
print("\nTraining LightGBM model...")

with mlflow.start_run(run_name="lightgbm_classifier"):

    lgb_params = {
        'n_estimators': 200,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'scale_pos_weight': scale_pos_weight,
        'random_state': 42,
        'verbose': -1
    }

    lgb_model = lgb.LGBMClassifier(**lgb_params)
    lgb_model.fit(X_train, y_train)

    lgb_preds = lgb_model.predict(X_test)
    lgb_proba = lgb_model.predict_proba(X_test)[:, 1]

    lgb_metrics = {
        'accuracy': accuracy_score(y_test, lgb_preds),
        'precision': precision_score(y_test, lgb_preds),
        'recall': recall_score(y_test, lgb_preds),
        'f1_score': f1_score(y_test, lgb_preds),
        'auc_roc': roc_auc_score(y_test, lgb_proba)
    }

    mlflow.log_params(lgb_params)
    mlflow.log_metrics(lgb_metrics)
    mlflow.lightgbm.log_model(lgb_model, "lightgbm_model")

    print("LightGBM Results:")
    for k, v in lgb_metrics.items():
        print(f"  {k}: {v:.4f}")

# ─────────────────────────────────────────
# STEP 8 — Select best model
# ─────────────────────────────────────────
print("\nSelecting best model based on AUC-ROC...")

if xgb_metrics['auc_roc'] >= lgb_metrics['auc_roc']:
    best_model = xgb_model
    best_model_name = "XGBoost"
    best_metrics = xgb_metrics
    best_proba = xgb_proba
    print(f"Best model: XGBoost (AUC-ROC: {xgb_metrics['auc_roc']:.4f})")
else:
    best_model = lgb_model
    best_model_name = "LightGBM"
    best_metrics = lgb_metrics
    best_proba = lgb_proba
    print(f"Best model: LightGBM (AUC-ROC: {lgb_metrics['auc_roc']:.4f})")

# ─────────────────────────────────────────
# STEP 9 — SHAP Explainability
# ─────────────────────────────────────────
print("\nGenerating SHAP explainability...")

os.makedirs(
    os.path.expanduser('~/supply-chain-risk-intelligence/ml/outputs'),
    exist_ok=True
)

# Use sample of 5000 rows for SHAP speed
sample_idx = np.random.choice(len(X_test), size=min(5000, len(X_test)), replace=False)
X_sample = X_test.iloc[sample_idx]

explainer = shap.TreeExplainer(best_model)
shap_values = explainer.shap_values(X_sample)

# Handle LightGBM which returns list
if isinstance(shap_values, list):
    shap_values = shap_values[1]

# Feature importance plot
plt.figure(figsize=(10, 6))
shap.summary_plot(
    shap_values,
    X_sample,
    feature_names=feature_cols,
    show=False
)
plt.title(f'SHAP Feature Importance — {best_model_name}')
plt.tight_layout()
shap_path = os.path.expanduser(
    '~/supply-chain-risk-intelligence/ml/outputs/shap_summary.png'
)
plt.savefig(shap_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"SHAP plot saved to: {shap_path}")

# ─────────────────────────────────────────
# STEP 10 — Save model and encoders
# ─────────────────────────────────────────
model_path = os.path.expanduser(
    '~/supply-chain-risk-intelligence/ml/outputs/best_model.pkl'
)
encoders_path = os.path.expanduser(
    '~/supply-chain-risk-intelligence/ml/outputs/encoders.pkl'
)

with open(model_path, 'wb') as f:
    pickle.dump(best_model, f)

with open(encoders_path, 'wb') as f:
    pickle.dump(encoders, f)

print(f"Model saved to: {model_path}")
print(f"Encoders saved to: {encoders_path}")

# ─────────────────────────────────────────
# STEP 11 — Save predictions to CSV
# ─────────────────────────────────────────
predictions_df = X_test.copy()
predictions_df['ACTUAL_LATE_DELIVERY_RISK'] = y_test.values
predictions_df['PREDICTED_LATE_DELIVERY_RISK'] = best_model.predict(X_test)
predictions_df['FRAUD_PROBABILITY'] = best_proba
predictions_df['MODEL_USED'] = best_model_name

predictions_path = os.path.expanduser(
    '~/supply-chain-risk-intelligence/ml/outputs/predictions.csv'
)
predictions_df.to_csv(predictions_path, index=False)
print(f"Predictions saved to: {predictions_path}")

# ─────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────
print("\n" + "="*50)
print("TRAINING COMPLETE")
print("="*50)
print(f"Best Model: {best_model_name}")
print(f"Accuracy:   {best_metrics['accuracy']:.4f}")
print(f"Precision:  {best_metrics['precision']:.4f}")
print(f"Recall:     {best_metrics['recall']:.4f}")
print(f"F1 Score:   {best_metrics['f1_score']:.4f}")
print(f"AUC-ROC:    {best_metrics['auc_roc']:.4f}")
print("="*50)
print("\nOutputs saved to: ~/supply-chain-risk-intelligence/ml/outputs/")
print("MLflow UI: run 'mlflow ui' to view experiments")

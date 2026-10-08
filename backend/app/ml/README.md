# Machine Learning & Forecasting Layer (Phase 5)

This directory is reserved for future machine learning and demand forecasting capabilities.

## Architectural Separation

1. **Strict Isolation from Core Modules**:
   - ML feature engineering, training, and inference must never leak into `auth`, `shops`, `uploads`, or `db/models/sale.py`.
2. **Actual Sales vs. Predictions**:
   - The `sales` table stores verified historical transactions only.
   - Model predictions will be stored in dedicated forecasting tables or served via isolated ML endpoints.
3. **Planned Structure**:
   ```text
   app/ml/
   ├── features/     # Time-series lag, rolling window, and calendar feature pipelines
   ├── training/     # Per-shop model training workflows
   ├── models/       # XGBoost, LightGBM, Random Forest, Prophet adapters
   ├── prediction/   # Forecast generation services
   └── evaluation/   # Backtesting and metric evaluation (MAE, RMSE, MAPE)
   ```

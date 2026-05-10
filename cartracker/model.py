"""Train and apply price models for a single vehicle model (e.g. Tacoma).

We fit two estimators side-by-side:
- LinearRegression: interpretable; coefficients reveal $/mile, $/year, trim premiums.
- GradientBoostingRegressor: handles depreciation curvature and trim×year interactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

NUMERIC_FEATURES = ["year", "mileage"]
CATEGORICAL_FEATURES = ["model", "trim", "drivetrain", "cab_style", "engine"]
TARGET = "price"


@dataclass
class ModelBundle:
    pipeline: Pipeline
    mae: float
    r2: float
    name: str


def _build_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("num", "passthrough", NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("pre", pre), ("est", estimator)])


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    needed = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    out = df.copy()
    for col in CATEGORICAL_FEATURES:
        if col not in out:
            out[col] = "unknown"
        out[col] = out[col].fillna("unknown").astype(str)
    out = out.dropna(subset=NUMERIC_FEATURES + [TARGET])
    return out[needed]


def train(df: pd.DataFrame) -> dict[str, ModelBundle]:
    """Fit both models on df and return them with cross-validated metrics.

    Raises ValueError if df has fewer than ~20 usable rows — too few to model.
    """
    data = _prepare(df)
    if len(data) < 20:
        raise ValueError(f"need at least 20 rows to fit a model, got {len(data)}")

    X = data[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = data[TARGET].astype(float)

    bundles: dict[str, ModelBundle] = {}
    cv = KFold(n_splits=5, shuffle=True, random_state=0)
    for name, estimator in [
        ("linear", LinearRegression()),
        ("gbm", GradientBoostingRegressor(random_state=0)),
    ]:
        pipe = _build_pipeline(estimator)
        preds = cross_val_predict(pipe, X, y, cv=cv)
        mae = float(mean_absolute_error(y, preds))
        r2 = float(r2_score(y, preds))
        pipe.fit(X, y)
        bundles[name] = ModelBundle(pipeline=pipe, mae=mae, r2=r2, name=name)
    return bundles


def predict(bundle: ModelBundle, listing: dict) -> float:
    row = pd.DataFrame([{k: listing.get(k) for k in NUMERIC_FEATURES + CATEGORICAL_FEATURES}])
    for col in CATEGORICAL_FEATURES:
        row[col] = row[col].fillna("unknown").astype(str)
    return float(bundle.pipeline.predict(row)[0])


def linear_coefficients(bundle: ModelBundle) -> pd.DataFrame:
    """Return human-readable coefficients for the linear model."""
    pipe = bundle.pipeline
    pre = pipe.named_steps["pre"]
    est = pipe.named_steps["est"]
    names: list[str] = list(NUMERIC_FEATURES)
    ohe: OneHotEncoder = pre.named_transformers_["cat"]
    names.extend(ohe.get_feature_names_out(CATEGORICAL_FEATURES))
    coefs = pd.DataFrame({"feature": names, "coefficient": est.coef_})
    coefs["abs"] = coefs["coefficient"].abs()
    return coefs.sort_values("abs", ascending=False).drop(columns="abs")


def gbm_importances(bundle: ModelBundle) -> pd.DataFrame:
    pipe = bundle.pipeline
    pre = pipe.named_steps["pre"]
    est = pipe.named_steps["est"]
    names: list[str] = list(NUMERIC_FEATURES)
    ohe: OneHotEncoder = pre.named_transformers_["cat"]
    names.extend(ohe.get_feature_names_out(CATEGORICAL_FEATURES))
    return (
        pd.DataFrame({"feature": names, "importance": est.feature_importances_})
        .sort_values("importance", ascending=False)
    )

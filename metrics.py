import pandas as pd
import numpy as np
from typing import Any


def safe_float(value) -> float:
    try:
        v = float(value)
        return round(v, 2) if not np.isnan(v) else 0.0
    except Exception:
        return 0.0


def calc_revenue(df: pd.DataFrame) -> dict[str, Any]:
    col = next((c for c in df.columns if "revenue" in c.lower() or "сумма" in c.lower()), None)
    if col is None:
        return {"error": "Не найден столбец с выручкой"}
    total = safe_float(df[col].sum())
    monthly = {}
    date_col = _find_date_col(df)
    if date_col:
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
        monthly = (
            df.groupby(df["_date"].dt.to_period("M"))[col]
            .sum()
            .apply(safe_float)
            .to_dict()
        )
        monthly = {str(k): v for k, v in monthly.items()}
    return {"total": total, "monthly": monthly, "label": "Revenue (выручка)"}


def calc_arpu(df: pd.DataFrame) -> dict[str, Any]:
    rev_col = next((c for c in df.columns if "revenue" in c.lower() or "сумма" in c.lower()), None)
    user_col = _find_user_col(df)
    if rev_col is None or user_col is None:
        return {"error": "Нужны столбцы с выручкой и user_id"}
    total_rev = df[rev_col].sum()
    unique_users = df[user_col].nunique()
    arpu = safe_float(total_rev / unique_users) if unique_users else 0.0
    return {"value": arpu, "users": int(unique_users), "label": "ARPU (выручка на пользователя)"}


def calc_dau_mau(df: pd.DataFrame) -> dict[str, Any]:
    user_col = _find_user_col(df)
    date_col = _find_date_col(df)
    if user_col is None or date_col is None:
        return {"error": "Нужны столбцы user_id и date"}
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    dau = df.groupby(df["_date"].dt.date)[user_col].nunique().mean()
    mau = df.groupby(df["_date"].dt.to_period("M"))[user_col].nunique().mean()
    ratio = safe_float(dau / mau * 100) if mau else 0.0
    return {
        "dau": safe_float(dau),
        "mau": safe_float(mau),
        "ratio_pct": ratio,
        "label": "DAU / MAU",
    }


def calc_retention(df: pd.DataFrame) -> dict[str, Any]:
    user_col = _find_user_col(df)
    date_col = _find_date_col(df)
    if user_col is None or date_col is None:
        return {"error": "Нужны столбцы user_id и date"}
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["_month"] = df["_date"].dt.to_period("M")
    first_month = df.groupby(user_col)["_month"].min().rename("first_month")
    df = df.join(first_month, on=user_col)
    cohorts = df.groupby(["first_month", "_month"])[user_col].nunique().unstack()
    if cohorts.empty:
        return {"error": "Недостаточно данных для расчёта Retention"}
    retention = cohorts.divide(cohorts.iloc[:, 0], axis=0) * 100
    monthly_avg = retention.mean().apply(safe_float).to_dict()
    monthly_avg = {str(k): v for k, v in monthly_avg.items()}
    return {"monthly_avg": monthly_avg, "label": "Retention Rate (%)"}


def calc_churn(df: pd.DataFrame) -> dict[str, Any]:
    user_col = _find_user_col(df)
    date_col = _find_date_col(df)
    if user_col is None or date_col is None:
        return {"error": "Нужны столбцы user_id и date"}
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["_month"] = df["_date"].dt.to_period("M")
    monthly_users = df.groupby("_month")[user_col].nunique()
    if len(monthly_users) < 2:
        return {"error": "Нужно минимум 2 месяца данных"}
    churn_rates = {}
    months = list(monthly_users.index)
    for i in range(1, len(months)):
        prev, curr = months[i - 1], months[i]
        churn = safe_float((monthly_users[prev] - monthly_users[curr]) / monthly_users[prev] * 100)
        churn_rates[str(curr)] = max(churn, 0.0)
    avg_churn = safe_float(np.mean(list(churn_rates.values())))
    return {"monthly": churn_rates, "average": avg_churn, "label": "Churn Rate (%)"}


def calc_ltv(df: pd.DataFrame) -> dict[str, Any]:
    arpu_data = calc_arpu(df)
    churn_data = calc_churn(df)
    if "error" in arpu_data or "error" in churn_data:
        return {"error": "Недостаточно данных для LTV"}
    arpu = arpu_data["value"]
    churn = churn_data["average"]
    ltv = safe_float(arpu / (churn / 100)) if churn > 0 else 0.0
    return {"value": ltv, "arpu": arpu, "churn": churn, "label": "LTV (ценность клиента)"}


def calc_conversion(df: pd.DataFrame) -> dict[str, Any]:
    status_col = next(
        (c for c in df.columns if any(w in c.lower() for w in ["status", "converted", "purchased", "статус"])),
        None,
    )
    user_col = _find_user_col(df)
    if status_col is None or user_col is None:
        return {"error": "Нужны столбцы user_id и status/converted"}
    total = len(df)
    converted = df[status_col].astype(str).str.lower().isin(["1", "true", "yes", "да", "purchased", "converted"]).sum()
    rate = safe_float(converted / total * 100) if total else 0.0
    return {"rate_pct": rate, "converted": int(converted), "total": int(total), "label": "Conversion Rate (%)"}


# ── helpers ──────────────────────────────────────────

def _find_user_col(df: pd.DataFrame):
    return next(
        (c for c in df.columns if any(w in c.lower() for w in ["user_id", "user", "пользователь", "client_id", "client"])),
        None,
    )


def _find_date_col(df: pd.DataFrame):
    return next(
        (c for c in df.columns if any(w in c.lower() for w in ["date", "дата", "time", "timestamp", "created"])),
        None,
    )


METRICS_MAP = {
    "revenue":    calc_revenue,
    "arpu":       calc_arpu,
    "dau_mau":    calc_dau_mau,
    "retention":  calc_retention,
    "churn":      calc_churn,
    "ltv":        calc_ltv,
    "conversion": calc_conversion,
}

METRICS_LABELS = {
    "revenue":    "Revenue (выручка)",
    "arpu":       "ARPU",
    "dau_mau":    "DAU / MAU",
    "retention":  "Retention Rate",
    "churn":      "Churn Rate",
    "ltv":        "LTV",
    "conversion": "Conversion Rate",
}

METRICS_GROUPS = {
    "Финансовые метрики": ["revenue", "arpu", "ltv"],
    "Метрики вовлечённости": ["dau_mau", "retention"],
    "Метрики конверсии": ["churn", "conversion"],
}

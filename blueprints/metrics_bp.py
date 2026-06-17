import os
import io
import csv
import json
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from sqlalchemy import text
from database import SessionLocal, engine, Project, Dataset, Report
from auth import login_required, roles_required, get_current_user
from datetime import datetime, timezone

metrics_bp = Blueprint("metrics", __name__, url_prefix="/projects")

METRICS_GROUPS = {
    "Финансовые метрики": [
        ("revenue", "Revenue — суммарная выручка"),
        ("arpu", "ARPU — выручка на пользователя"),
        ("ltv", "LTV — ценность клиента"),
    ],
    "Метрики вовлечённости": [
        ("dau_mau", "DAU / MAU — соотношение аудитории"),
        ("retention", "Retention Rate — удержание пользователей"),
    ],
    "Метрики конверсии": [
        ("churn", "Churn Rate — отток пользователей"),
        ("conversion", "Conversion Rate — конверсия"),
    ],
}

METRICS_LABELS = {k: v for group in METRICS_GROUPS.values() for k, v in group}



def _find_col(columns, keywords):
    for col in columns:
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


def _load_to_temp(df, conn):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    tmp = "tmp_dataset"

    col_defs = []
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            pg_type = "BIGINT"
        elif pd.api.types.is_float_dtype(dtype):
            pg_type = "DOUBLE PRECISION"
        else:
            pg_type = "TEXT"
        col_defs.append(f'"{col}" {pg_type}')

    conn.execute(text(f"DROP TABLE IF EXISTS {tmp}"))
    conn.execute(text(f"CREATE TEMP TABLE {tmp} ({', '.join(col_defs)})"))

    if not df.empty:
        placeholders = ", ".join([f":col_{i}" for i in range(len(df.columns))])
        col_names    = ", ".join([f'"{c}"' for c in df.columns])
        insert_sql   = text(f"INSERT INTO {tmp} ({col_names}) VALUES ({placeholders})")
        rows = []
        for _, row in df.iterrows():
            rows.append({f"col_{i}": (None if pd.isna(v) else v)
                         for i, v in enumerate(row)})
        conn.execute(insert_sql, rows)

    conn.commit()
    return tmp, df.columns.tolist()



def calc_revenue(conn, tmp, columns):
    rev = _find_col(columns, ["revenue", "сумма", "amount", "price"])
    if not rev:
        return {"error": "Не найден столбец с выручкой (revenue / amount / price)"}
    date = _find_col(columns, ["date", "дата", "time", "timestamp", "created"])

    row = conn.execute(text(
        f'SELECT ROUND(SUM("{rev}")::numeric, 2) FROM {tmp}'
    )).fetchone()
    total = float(row[0] or 0)

    monthly = {}
    if date:
        rows = conn.execute(text(f"""
            SELECT TO_CHAR(DATE_TRUNC('month', "{date}"::date), 'YYYY-MM'),
                   ROUND(SUM("{rev}")::numeric, 2)
            FROM {tmp}
            WHERE "{date}" IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)).fetchall()
        monthly = {r[0]: float(r[1]) for r in rows}

    return {"total": total, "monthly": monthly, "label": "Revenue (выручка)"}


def calc_arpu(conn, tmp, columns):
    rev  = _find_col(columns, ["revenue", "сумма", "amount", "price"])
    user = _find_col(columns, ["user_id", "user", "client_id", "пользователь"])
    if not rev or not user:
        return {"error": "Нужны столбцы с выручкой и user_id"}
    row = conn.execute(text(f"""
        SELECT ROUND((SUM("{rev}") / NULLIF(COUNT(DISTINCT "{user}"), 0))::numeric, 2),
               COUNT(DISTINCT "{user}")
        FROM {tmp}
    """)).fetchone()
    return {"value": float(row[0] or 0), "users": int(row[1] or 0),
            "label": "ARPU (выручка на пользователя)"}


def calc_dau_mau(conn, tmp, columns):
    user = _find_col(columns, ["user_id", "user", "client_id"])
    date = _find_col(columns, ["date", "дата", "time", "timestamp", "created"])
    if not user or not date:
        return {"error": "Нужны столбцы user_id и date"}
    row = conn.execute(text(f"""
        WITH daily AS (
            SELECT "{date}"::date AS day, COUNT(DISTINCT "{user}") AS dau
            FROM {tmp} WHERE "{date}" IS NOT NULL GROUP BY day
        ),
        monthly AS (
            SELECT DATE_TRUNC('month', "{date}"::date) AS month,
                   COUNT(DISTINCT "{user}") AS mau
            FROM {tmp} WHERE "{date}" IS NOT NULL GROUP BY month
        )
        SELECT ROUND(AVG(d.dau)::numeric, 2), ROUND(AVG(m.mau)::numeric, 2)
        FROM daily d, monthly m
    """)).fetchone()
    dau, mau = float(row[0] or 0), float(row[1] or 0)
    ratio = round(dau / mau * 100, 2) if mau else 0.0
    return {"dau": dau, "mau": mau, "ratio_pct": ratio, "label": "DAU / MAU"}


def calc_retention(conn, tmp, columns):
    user = _find_col(columns, ["user_id", "user", "client_id"])
    date = _find_col(columns, ["date", "дата", "time", "timestamp", "created"])
    if not user or not date:
        return {"error": "Нужны столбцы user_id и date"}
    rows = conn.execute(text(f"""
        WITH first_month AS (
            SELECT "{user}",
                   DATE_TRUNC('month', MIN("{date}"::date)) AS cohort
            FROM {tmp} WHERE "{date}" IS NOT NULL GROUP BY "{user}"
        ),
        activity AS (
            SELECT fm.cohort,
                   DATE_TRUNC('month', t."{date}"::date) AS month,
                   COUNT(DISTINCT t."{user}") AS active
            FROM {tmp} t JOIN first_month fm ON t."{user}" = fm."{user}"
            WHERE t."{date}" IS NOT NULL GROUP BY fm.cohort, month
        ),
        sizes AS (
            SELECT cohort, COUNT(DISTINCT "{user}") AS total
            FROM first_month GROUP BY cohort
        )
        SELECT TO_CHAR(a.month, 'YYYY-MM'),
               ROUND((AVG(a.active::float / NULLIF(s.total,0)) * 100)::numeric, 2)
        FROM activity a JOIN sizes s ON a.cohort = s.cohort
        GROUP BY a.month ORDER BY a.month
    """)).fetchall()
    return {"monthly_avg": {r[0]: float(r[1]) for r in rows},
            "label": "Retention Rate (%)"}


def calc_churn(conn, tmp, columns):
    user = _find_col(columns, ["user_id", "user", "client_id"])
    date = _find_col(columns, ["date", "дата", "time", "timestamp", "created"])
    if not user or not date:
        return {"error": "Нужны столбцы user_id и date"}
    rows = conn.execute(text(f"""
        WITH monthly AS (
            SELECT DATE_TRUNC('month', "{date}"::date) AS month,
                   COUNT(DISTINCT "{user}") AS cnt
            FROM {tmp} WHERE "{date}" IS NOT NULL GROUP BY month ORDER BY month
        ),
        lagged AS (
            SELECT month, cnt, LAG(cnt) OVER (ORDER BY month) AS prev
            FROM monthly
        )
        SELECT TO_CHAR(month, 'YYYY-MM'),
               ROUND(GREATEST(0,((prev - cnt)::float / NULLIF(prev,0) * 100))::numeric, 2)
        FROM lagged WHERE prev IS NOT NULL ORDER BY month
    """)).fetchall()
    monthly = {r[0]: float(r[1]) for r in rows}
    avg = round(sum(monthly.values()) / len(monthly), 2) if monthly else 0.0
    return {"monthly": monthly, "average": avg, "label": "Churn Rate (%)"}


def calc_ltv(conn, tmp, columns):
    arpu  = calc_arpu(conn, tmp, columns)
    churn = calc_churn(conn, tmp, columns)
    if "error" in arpu or "error" in churn:
        return {"error": "Недостаточно данных для LTV"}
    ltv = round(arpu["value"] / (churn["average"] / 100), 2) if churn["average"] > 0 else 0.0
    return {"value": ltv, "arpu": arpu["value"], "churn": churn["average"],
            "label": "LTV (ценность клиента)"}


def calc_conversion(conn, tmp, columns):
    status = _find_col(columns, ["status", "converted", "purchased", "статус"])
    user   = _find_col(columns, ["user_id", "user", "client_id"])
    if not status or not user:
        return {"error": "Нужны столбцы user_id и status/converted"}
    row = conn.execute(text(f"""
        SELECT COUNT(*),
               SUM(CASE WHEN LOWER("{status}"::text)
                   IN ('1','true','yes','да','purchased','converted')
                   THEN 1 ELSE 0 END)
        FROM {tmp}
    """)).fetchone()
    total = int(row[0] or 0)
    conv  = int(row[1] or 0)
    return {"rate_pct": round(conv / total * 100, 2) if total else 0.0,
            "converted": conv, "total": total, "label": "Conversion Rate (%)"}


METRICS_MAP = {
    "revenue":    calc_revenue,
    "arpu":       calc_arpu,
    "dau_mau":    calc_dau_mau,
    "retention":  calc_retention,
    "churn":      calc_churn,
    "ltv":        calc_ltv,
    "conversion": calc_conversion,
}



@metrics_bp.route("/<project_id>/datasets/<dataset_id>/metrics", methods=["GET", "POST"])
@roles_required("admin", "analyst")
def select(project_id, dataset_id):
    user = get_current_user()
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not project or not dataset:
            flash("Проект или датасет не найден.", "warning")
            return redirect(url_for("projects.index"))

        detected_cols = dataset.columns.split(",") if dataset.columns else []

        if request.method == "POST":
            selected = request.form.getlist("metrics")
            if not selected:
                flash("Выберите хотя бы одну метрику.", "danger")
                return render_template("metrics/select.html",
                                       project=project, dataset=dataset,
                                       detected_cols=detected_cols,
                                       metrics_groups=METRICS_GROUPS,
                                       metrics_labels=METRICS_LABELS, user=user)
            ext = os.path.splitext(dataset.filename)[1].lower()
            df  = pd.read_csv(dataset.file_path) if ext == ".csv" else pd.read_json(dataset.file_path)

            with engine.connect() as conn:
                tmp, cols = _load_to_temp(df, conn)
                results = {}
                for metric in selected:
                    if metric in METRICS_MAP:
                        results[metric] = METRICS_MAP[metric](conn, tmp, cols)

            report = Report(
                dataset_id=dataset_id,
                project_id=project_id,
                metrics=selected,
                result_json=results,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            flash("Метрики успешно вычислены.", "success")
            return redirect(url_for("metrics.report",
                                    project_id=project_id,
                                    report_id=report.id))

        return render_template("metrics/select.html",
                               project=project, dataset=dataset,
                               detected_cols=detected_cols,
                               metrics_groups=METRICS_GROUPS,
                               metrics_labels=METRICS_LABELS, user=user)
    finally:
        db.close()


@metrics_bp.route("/<project_id>/reports/<report_id>")
@login_required
def report(project_id, report_id):
    user = get_current_user()
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        rep     = db.query(Report).filter(Report.id == report_id).first()
        dataset = db.query(Dataset).filter(Dataset.id == rep.dataset_id).first()
        results = rep.result_json
        if isinstance(results, str):
            results = json.loads(results)
        return render_template("metrics/report.html",
                               project=project, report=rep, dataset=dataset,
                               results=results,
                               results_json=json.dumps(results, ensure_ascii=False),
                               user=user)
    finally:
        db.close()


@metrics_bp.route("/<project_id>/reports")
@login_required
def reports_list(project_id):
    user = get_current_user()
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        reports = (
            db.query(Report)
            .filter(Report.project_id == project_id)
            .order_by(Report.created_at.desc())
            .all()
        )
        datasets = {d.id: d for d in
                    db.query(Dataset).filter(Dataset.project_id == project_id).all()}
        return render_template("metrics/reports_list.html",
                               project=project, reports=reports,
                               datasets=datasets, user=user)
    finally:
        db.close()


@metrics_bp.route("/<project_id>/reports/<report_id>/export/csv")
@login_required
def export_csv(project_id, report_id):
    db = SessionLocal()
    try:
        rep = db.query(Report).filter(Report.id == report_id).first()
        results = rep.result_json
        if isinstance(results, str):
            results = json.loads(results)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])

        for metric, data in results.items():
            if not isinstance(data, dict):
                continue
            if "error" in data:
                writer.writerow([metric, "No data"])
                continue
            if data.get("value") is not None:
                writer.writerow([metric, data["value"]])
            elif data.get("total") is not None and metric == "revenue":
                writer.writerow([metric, data["total"]])
            elif data.get("ratio_pct") is not None:
                writer.writerow([metric, f"{data['ratio_pct']}%"])
            elif data.get("rate_pct") is not None:
                writer.writerow([metric, f"{data['rate_pct']}%"])
            elif data.get("average") is not None:
                writer.writerow([metric, f"{data['average']}%"])

        response = make_response(output.getvalue().encode("utf-8-sig"))
        response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
        response.headers["Content-Disposition"] = \
            f"attachment; filename=report_{report_id[:8]}.csv"
        return response
    finally:
        db.close()

import requests
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, dash_table
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import utilities as utl
import json
from agents.mlsysops.logger_util import logger


load_dotenv(override=True)


db_config = {
    "DB_DRIVER":   os.getenv("DB_DRIVER"),
    "DB_USER":     os.getenv("POSTGRES_USER"),
    "DB_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
    "DB_HOST":     os.getenv("DB_HOST_NAME"),
    "DB_PORT":     os.getenv("DB_PORT"),
    "DB_NAME":     os.getenv("POSTGRES_DB")
}


SQLALCHEMY_DATABASE_URL = (
    f"{db_config['DB_DRIVER']}://{db_config['DB_USER']}:"
    f"{db_config['DB_PASSWORD']}@{db_config['DB_HOST']}:"
    f"{db_config['DB_PORT']}/{db_config['DB_NAME']}"
)
engine = create_engine(SQLALCHEMY_DATABASE_URL)


MODEL_API_URL = "http://api:8090/model/all"


external_stylesheets = ["https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"]


app = Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "Drift Monitoring Dashboard"


app.layout = html.Div(className="container-fluid", children=[
    html.H1("📈 Drift Monitoring Dashboard", className="text-center my-4"),

    
    dcc.Interval(id="model-refresh", interval=60*1000, n_intervals=0),

    html.Div(className="row px-4", children=[
        
        html.Div(className="col-md-6 mb-3", children=[
            html.Label("Select Model", className="form-label fw-bold"),
            dcc.Dropdown(
                id="model-dropdown", options=[],
                placeholder="Loading models…",
                disabled=True, className="form-select"
            )
        ]),
        
        html.Div(className="col-md-6 mb-3", children=[
            html.Label("Select Feature", className="form-label fw-bold"),
            dcc.Loading(
                id="feature-loading", type="default",
                children=dcc.Dropdown(
                    id="feature-dropdown", options=[],
                    placeholder="Select a model first…",
                    disabled=True, className="form-select"
                )
            )
        ]),
    ]),

    
    html.Div(className="container", children=[
        dcc.Loading(dcc.Graph(id="drift-graph"), type="circle")
    ]),

   
    html.Div(id="drift-info", className="text-center fs-5 mb-3"),

    
    html.Div(className="container", children=[
        dash_table.DataTable(
            id="drift-table",
            columns=[
                {"name": "Timestamp",      "id": "timestamp"},
                {"name": "Feature",        "id": "feature"},
                {"name": "Type",           "id": "type"},
                {"name": "Statistic",      "id": "statistic"},
                {"name": "P-Value",        "id": "p_value"},
                {"name": "Drift Detected", "id": "drift_detected"},
            ],
            data=[],
            page_size=10,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left"},
            style_header={"fontWeight": "bold"},
        )
    ], style={"marginBottom": "40px"})
])


@app.callback(
    Output("model-dropdown", "options"),
    Output("model-dropdown", "placeholder"),
    Output("model-dropdown", "disabled"),
    Input("model-refresh", "n_intervals")
)
def update_models(n_intervals):
    try:
        resp = requests.get(MODEL_API_URL, timeout=5)
        resp.raise_for_status()
        models = [m["modelid"] for m in resp.json()]
    except Exception:
        models = []

    if not models:
        return [], "⚠️ No models available", True

    opts = [{"label": m, "value": m} for m in models]
    return opts, "Choose a model…", False


@app.callback(
    Output("feature-dropdown", "options"),
    Output("feature-dropdown", "value"),
    Output("feature-dropdown", "placeholder"),
    Output("feature-dropdown", "disabled"),
    Input("model-dropdown", "value")
)
def update_features(selected_model):
    if not selected_model:
        return [], None, "Select a model first…", True

    try:
        q = "SELECT DISTINCT feature FROM drift_metrics WHERE modelid = %s ORDER BY feature"
        features = pd.read_sql(q, engine, params=(selected_model,))["feature"].tolist()
    except Exception as e:
        logger.exception("Error reading features:", str(e))
        return [], None, "❌ Error loading features", True

    if not features:
        return [], None, "⚠️ No features available", True

    opts = [{"label": f, "value": f} for f in features]
    return opts, features[0], "Select a feature…", False


@app.callback(
    Output("drift-graph", "figure"),
    Output("drift-info", "children"),
    Input("model-dropdown", "value"),
    Input("feature-dropdown", "value")
)
def update_graph(selected_model, selected_feature):
    if not selected_model:
        return {}, html.Span("Please select a model.", className="text-warning fw-bold")
    if not selected_feature:
        return {}, html.Span("Please select a feature.", className="text-warning fw-bold")

    try:
        q = """
            SELECT timestamp, feature, type, statistic, p_value, drift_detected
            FROM drift_metrics
            WHERE modelid = %s AND feature = %s
            ORDER BY timestamp
        """
        df = pd.read_sql(q, engine, params=(selected_model, selected_feature))
    except Exception as e:
        logger.error("Error loading drift data:", str(e))
        return {}, html.Span("❌ Error loading data.", className="text-danger fw-bold")

    if df.empty:
        return {}, html.Span("No data for selected feature.", className="text-warning fw-bold")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    fig = px.line(
        df, x="timestamp", y="statistic",
        color="type", markers=True,
        title=f"Drift Metric for '{selected_feature}'"
    )
    fig.update_layout(
        xaxis_title="Timestamp", yaxis_title="Statistic Value",
        legend_title="Feature Type", template="plotly_white"
    )

    
    mask = df["drift_detected"].astype(str).str.lower() == "true"
    count = mask.sum()
    msg = (html.Span([html.Span("⚠️ Drift detected ", className="text-danger fw-bold"),
                      f"{count} occurrences"])
           if count else html.Span("✅ No drift detected", className="text-success fw-bold"))

    return fig, msg


@app.callback(
    Output("drift-table", "data"),
    Input("model-dropdown", "value")
)
def update_table(selected_model):
    if not selected_model:
        return []
    try:
        q = """
            SELECT timestamp, feature, type, statistic, p_value, drift_detected
            FROM drift_metrics
            WHERE modelid = %s
            ORDER BY timestamp
        """
        df = pd.read_sql(q, engine, params=(selected_model,))
        
        df["timestamp"] = df["timestamp"].astype(str)
        return df.to_dict("records")
    except Exception as e:
        logger.error("Error loading table data:", str(e))
        return []
    
def drif_job():
    logging.info("drif detection job starting")
    try:
        logging.info(f"Find all models with drift detection")
        filter = json.dumps([{"is_true": 1}])
        q = """
            SELECT *
            FROM mlmodels
            WHERE drift_detection @> %s::jsonb
        """
        records = pd.read_sql(q, engine, params=(filter,))
        for record in records.to_dict("records"):
            model_details = utl.model_data(engine, record['modelid'])
            if model_details:
                training_data = model_details[0]
                inference_data = model_details[1]["data"].to_frame()
                #logging.info(inference_data)
                cont_features = [
                    f['feature_name']
                    for f in record["featurelist"]
                    if f['kind'] == 0 and f['type'] == 'cont'
                ]

                cat_features = [
                    f['feature_name']
                    for f in record["featurelist"]
                    if f['kind'] == 0 and f['type'] == 'cat'
                ]
                #logging.info(cont_features)
                #logging.info(cat_features)
                logging.info(f"Run the drift detection based on selected method")
                result = utl.calculate_drift(
                            training_data, 
                            inference_data,
                            cont_features, 
                            cat_features, 
                            method = 'mean-shift'
                        )
    except Exception:
        logging.exception("Error in drif_job")
    finally:
        #cur.close()
        #conn.close()
        logging.info("drif_job job finished")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    scheduler = BackgroundScheduler(timezone="UTC")
    # first run immediately, then every 24 h
    scheduler.add_job(
        drif_job,
        trigger='interval',
        hours=24,
        next_run_time=datetime.now()
    )
    scheduler.start()
    logging.info("Scheduler started: drif_job every 24 hours")

    app.run(host="0.0.0.0", port=8050, debug=False)

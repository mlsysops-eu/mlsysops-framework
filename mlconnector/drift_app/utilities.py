import pandas as pd
import numpy as np
from scipy.stats import ttest_ind, ks_2samp, chi2_contingency
from sklearn.metrics.pairwise import rbf_kernel
from datetime import datetime, timedelta
import json
import logging
import os
import tempfile
from manage_s3 import S3Manager
from dotenv import load_dotenv
load_dotenv(override=True)

manager = S3Manager(
        os.getenv("AWS_S3_BUCKET_DATA"),
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY"),
        os.getenv("AWS_ACCESS_URL")
    )

def extract_feature_names(feature_list):
    type_mapping = {
        'cont': "float",
        'cat': "str"
    }
    
    return {
        feature['feature_name']: type_mapping.get(feature['type'], None)
        for feature in feature_list
        if feature.get('kind') == 0
    }

def mean_shift(train, infer):
    return ttest_ind(train, infer, equal_var=False)

def ks_test(train, infer):
    return ks_2samp(train, infer)

def mmd(train, infer, gamma=1.0):
    X = train.values.reshape(-1, 1)
    Y = infer.values.reshape(-1, 1)
    XX = rbf_kernel(X, X, gamma)
    YY = rbf_kernel(Y, Y, gamma)
    XY = rbf_kernel(X, Y, gamma)
    return XX.mean() + YY.mean() - 2 * XY.mean()

def chi_squared_test(train_series, infer_series):
    train_counts = train_series.value_counts(normalize=True)
    infer_counts = infer_series.value_counts(normalize=True)
    all_categories = sorted(set(train_counts.index).union(infer_counts.index))
    train_freq = [train_counts.get(cat, 0) for cat in all_categories]
    infer_freq = [infer_counts.get(cat, 0) for cat in all_categories]
    contingency_table = np.array([train_freq, infer_freq])
    return chi2_contingency(contingency_table)

def calculate_drift(train_df, infer_df, numerical_cols, categorical_cols, method = 'mean-shift'):
    results = []
    
    for col in numerical_cols:
        train_series = train_df[col]
        infer_series = infer_df[col]
        
        if method == 'mean-shift':
            stat, p = mean_shift(train_series, infer_series)
        elif method == 'ks':
            stat, p = ks_test(train_series, infer_series)
        elif method == 'mmd':
            stat = mmd(train_series, infer_series)
            p = np.nan
        else:
            raise ValueError("Invalid method")
            
        results.append({
            'feature': col,
            'type': 'numerical',
            'statistic': stat,
            'p_value': p,
            'method':method,
            'drift_detected': (p < 0.05) if not np.isnan(p) else (stat > 0.1)
        })
    
    for col in categorical_cols:
        chi2, p, _, _ = chi_squared_test(train_df[col], infer_df[col])
        results.append({
            'feature': col,
            'type': 'categorical',
            'statistic': chi2,
            'p_value': p,
            'method':method,
            'drift_detected': p < 0.05
        })
    
    results_df = pd.DataFrame(results)
    return results_df

def model_data(engine, model_id):
    # check for inference data (at least 10 data points)
    q = """
        SELECT *
        FROM mldeploymentsops
        WHERE modelid = %s
    """
    records = pd.read_sql(q, engine, params=(model_id,))
    if records.empty  or len(records) < 10: 
        logging.warning(f"No inference data found for model {model_id}")
        return False
    # check for training data
    file_name = f"{model_id}.csv"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp_path = tmp.name
    tmp.close()

    try:
        manager.download_file(file_name, tmp_path)
        try:
            df = pd.read_csv(tmp_path)
        except pd.errors.EmptyDataError:
            return False
        return df, records

    except (FileNotFoundError, IOError) as e:
        logging.warning(f"Could not download `{file_name}`: {e}")
        return False

    finally:
        # cleanup: only once, and only if it still exists
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
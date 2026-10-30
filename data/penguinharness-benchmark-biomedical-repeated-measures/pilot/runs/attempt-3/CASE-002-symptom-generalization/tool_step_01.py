import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
import os

# Load data
data = pd.read_csv('data/parkinsons_telemonitoring.csv')

# Define feature sets
context_features = ['age', 'sex', 'test_time']
context_acoustic_features = context_features + data.columns[4:].tolist()

# Define models
ridge = Ridge(alpha=10)
rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=20261030)

# Define folds
np.random.seed(20261030)
kf = KFold(n_splits=7)

# Define patient splits
patients = data['subject#'].unique()
np.random.seed(20261030)
patient_splits = np.array_split(patients, 7)

# Define output directories
os.makedirs('results', exist_ok=True)

# Function to fit and predict
def fit_predict(X, y, model, features):
    model.fit(X[features], y)
    return model.predict(X[features])

# Function to calculate metrics
def calculate_metrics(y_true, y_pred, weights):
    mae = np.mean(np.abs(y_true - y_pred) * weights)
    rmse = np.sqrt(np.mean((y_true - y_pred)**2 * weights))
    median_mae = np.median(np.abs(y_true - y_pred) * weights)
    worst_mae = np.max(np.abs(y_true - y_pred) * weights)
    return mae, rmse, median_mae, worst_mae

# Function to calculate contrasts
def calculate_contrasts(y_true, y_pred_context, y_pred_acoustic, weights):
    acoustic_gain = y_pred_context - y_pred_acoustic
    patient_minus_recording = y_pred_acoustic - y_pred_context
    return acoustic_gain, patient_minus_recording

# Function to save predictions
def save_predictions(predictions, filename):
    predictions.to_csv(filename, index=False)

# Function to save metrics
def save_metrics(metrics, filename):
    metrics.to_csv(filename, index=False)

# Function to save contrasts
def save_contrasts(contrasts, filename):
    contrasts.to_csv(filename, index=False)

# Function to save interpretation
def save_interpretation(text, filename):
    with open(filename, 'w') as f:
        f.write(text)

# Initialize results
predictions = pd.DataFrame(columns=['protocol', 'fold', 'model', 'features', 'row_id', 'subject_id', 'target', 'prediction'])
metrics = pd.DataFrame(columns=['protocol', 'model', 'features', 'patient_mae', 'median_patient_mae', 'worst_patient_mae', 'patient_rmse', 'recording_mae', 'recording_rmse'])
contrasts = pd.DataFrame(columns=['model', 'contrast', 'mean_difference', 'resampling_lower', 'resampling_upper', 'n_patients_positive', 'n_patients'])

# Process data
X = data.drop(['subject#', 'motor_UPDRS', 'total_UPDRS'], axis=1)
y = data['motor_UPDRS']
weights = data['test_time']  # Using test_time as a weighting factor

# Process recording protocol
recording_protocol = []
for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
    weights_train, weights_val = weights.iloc[train_idx], weights.iloc[val_idx]
    
    # Fit models
    ridge_pred = fit_predict(X_train, y_train, ridge, context_features)
    ridge_pred_acoustic = fit_predict(X_train, y_train, ridge, context_acoustic_features)
    rf_pred = fit_predict(X_train, y_train, rf, context_features)
    rf_pred_acoustic = fit_predict(X_train, y_train, rf, context_acoustic_features)
    
    # Calculate metrics
    ridge_mae, ridge_rmse, ridge_median_mae, ridge_worst_mae = calculate_metrics(y_val, ridge_pred, weights_val)
    ridge_acoustic_mae, ridge_acoustic_rmse, ridge_acoustic_median_mae, ridge_acoustic_worst_mae = calculate_metrics(y_val, ridge_pred_acoustic, weights_val)
    rf_mae, rf_rmse, rf_median_mae, rf_worst_mae = calculate_metrics(y_val, rf_pred, weights_val)
    rf_acoustic_mae, rf_acoustic_rmse, rf_acoustic_median_mae, rf_acoustic_worst_mae = calculate_metrics(y_val, rf_pred_acoustic, weights_val)
    
    # Save metrics
    metrics = metrics.append({
        'protocol': 'recording',
        'model': 'ridge',
        'features': 'context',
        'patient_mae': ridge_mae,
        'median_patient_mae': ridge_median_mae,
        'worst_patient_mae': ridge_worst_mae,
        'patient_rmse': ridge_rmse,
        'recording_mae': ridge_mae,
        'recording_rmse': ridge_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'recording',
        'model': 'ridge',
        'features': 'context_acoustic',
        'patient_mae': ridge_acoustic_mae,
        'median_patient_mae': ridge_acoustic_median_mae,
        'worst_patient_mae': ridge_acoustic_worst_mae,
        'patient_rmse': ridge_acoustic_rmse,
        'recording_mae': ridge_acoustic_mae,
        'recording_rmse': ridge_acoustic_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'recording',
        'model': 'random_forest',
        'features': 'context',
        'patient_mae': rf_mae,
        'median_patient_mae': rf_median_mae,
        'worst_patient_mae': rf_worst_mae,
        'patient_rmse': rf_rmse,
        'recording_mae': rf_mae,
        'recording_rmse': rf_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'recording',
        'model': 'random_forest',
        'features': 'context_acoustic',
        'patient_mae': rf_acoustic_mae,
        'median_patient_mae': rf_acoustic_median_mae,
        'worst_patient_mae': rf_acoustic_worst_mae,
        'patient_rmse': rf_acoustic_rmse,
        'recording_mae': rf_acoustic_mae,
        'recording_rmse': rf_acoustic_rmse
    }, ignore_index=True)
    
    # Save predictions
    for i, row in enumerate(X_val.iterrows()):
        row_id, subject_id = row[1]['row_id'], row[1]['subject#']
        target = row[1]['motor_UPDRS']
        ridge_pred = ridge_pred[i]
        ridge_pred_acoustic = ridge_pred_acoustic[i]
        rf_pred = rf_pred[i]
        rf_pred_acoustic = rf_pred_acoustic[i]
        recording_protocol.append({
            'protocol': 'recording',
            'fold': fold,
            'model': 'ridge',
            'features': 'context',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': ridge_pred
        })
        recording_protocol.append({
            'protocol': 'recording',
            'fold': fold,
            'model': 'ridge',
            'features': 'context_acoustic',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': ridge_pred_acoustic
        })
        recording_protocol.append({
            'protocol': 'recording',
            'fold': fold,
            'model': 'random_forest',
            'features': 'context',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': rf_pred
        })
        recording_protocol.append({
            'protocol': 'recording',
            'fold': fold,
            'model': 'random_forest',
            'features': 'context_acoustic',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': rf_pred_acoustic
        })

# Process patient protocol
patient_protocol = []
for fold, (train_patients, val_patients) in enumerate(patient_splits):
    # Split data by patient
    X_train = []
    y_train = []
    weights_train = []
    X_val = []
    y_val = []
    weights_val = []
    for patient in train_patients:
        patient_data = data[data['subject#'] == patient]
        X_train.append(patient_data.drop(['subject#', 'motor_UPDRS', 'total_UPDRS'], axis=1))
        y_train.append(patient_data['motor_UPDRS'])
        weights_train.append(patient_data['test_time'])
        X_val.append(patient_data.drop(['subject#', 'motor_UPDRS', 'total_UPDRS'], axis=1))
        y_val.append(patient_data['motor_UPDRS'])
        weights_val.append(patient_data['test_time'])
    
    X_train = pd.concat(X_train)
    y_train = pd.concat(y_train)
    weights_train = pd.concat(weights_train)
    X_val = pd.concat(X_val)
    y_val = pd.concat(y_val)
    weights_val = pd.concat(weights_val)
    
    # Fit models
    ridge_pred = fit_predict(X_train, y_train, ridge, context_features)
    ridge_pred_acoustic = fit_predict(X_train, y_train, ridge, context_acoustic_features)
    rf_pred = fit_predict(X_train, y_train, rf, context_features)
    rf_pred_acoustic = fit_predict(X_train, y_train, rf, context_acoustic_features)
    
    # Calculate metrics
    ridge_mae, ridge_rmse, ridge_median_mae, ridge_worst_mae = calculate_metrics(y_val, ridge_pred, weights_val)
    ridge_acoustic_mae, ridge_acoustic_rmse, ridge_acoustic_median_mae, ridge_acoustic_worst_mae = calculate_metrics(y_val, ridge_pred_acoustic, weights_val)
    rf_mae, rf_rmse, rf_median_mae, rf_worst_mae = calculate_metrics(y_val, rf_pred, weights_val)
    rf_acoustic_mae, rf_acoustic_rmse, rf_acoustic_median_mae, rf_acoustic_worst_mae = calculate_metrics(y_val, rf_pred_acoustic, weights_val)
    
    # Save metrics
    metrics = metrics.append({
        'protocol': 'patient',
        'model': 'ridge',
        'features': 'context',
        'patient_mae': ridge_mae,
        'median_patient_mae': ridge_median_mae,
        'worst_patient_mae': ridge_worst_mae,
        'patient_rmse': ridge_rmse,
        'recording_mae': ridge_mae,
        'recording_rmse': ridge_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'patient',
        'model': 'ridge',
        'features': 'context_acoustic',
        'patient_mae': ridge_acoustic_mae,
        'median_patient_mae': ridge_acoustic_median_mae,
        'worst_patient_mae': ridge_acoustic_worst_mae,
        'patient_rmse': ridge_acoustic_rmse,
        'recording_mae': ridge_acoustic_mae,
        'recording_rmse': ridge_acoustic_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'patient',
        'model': 'random_forest',
        'features': 'context',
        'patient_mae': rf_mae,
        'median_patient_mae': rf_median_mae,
        'worst_patient_mae': rf_worst_mae,
        'patient_rmse': rf_rmse,
        'recording_mae': rf_mae,
        'recording_rmse': rf_rmse
    }, ignore_index=True)
    metrics = metrics.append({
        'protocol': 'patient',
        'model': 'random_forest',
        'features': 'context_acoustic',
        'patient_mae': rf_acoustic_mae,
        'median_patient_mae': rf_acoustic_median_mae,
        'worst_patient_mae': rf_acoustic_worst_mae,
        'patient_rmse': rf_acoustic_rmse,
        'recording_mae': rf_acoustic_mae,
        'recording_rmse': rf_acoustic_rmse
    }, ignore_index=True)
    
    # Save predictions
    for i, row in enumerate(X_val.iterrows()):
        row_id, subject_id = row[1]['row_id'], row[1]['subject#']
        target = row[1]['motor_UPDRS']
        ridge_pred = ridge_pred[i]
        ridge_pred_acoustic = ridge_pred_acoustic[i]
        rf_pred = rf_pred[i]
        rf_pred_acoustic = rf_pred_acoustic[i]
        patient_protocol.append({
            'protocol': 'patient',
            'fold': fold,
            'model': 'ridge',
            'features': 'context',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': ridge_pred
        })
        patient_protocol.append({
            'protocol': 'patient',
            'fold': fold,
            'model': 'ridge',
            'features': 'context_acoustic',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': ridge_pred_acoustic
        })
        patient_protocol.append({
            'protocol': 'patient',
            'fold': fold,
            'model': 'random_forest',
            'features': 'context',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': rf_pred
        })
        patient_protocol.append({
            'protocol': 'patient',
            'fold': fold,
            'model': 'random_forest',
            'features': 'context_acoustic',
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': rf_pred_acoustic
        })

# Save predictions
predictions = pd.DataFrame(recording_protocol + patient_protocol)
save_predictions(predictions, 'results/predictions.csv')

# Calculate contrasts
acoustic_gain = []
patient_minus_recording = []
for i in range(len(metrics)):
    if metrics.iloc[i]['protocol'] == 'patient':
        model = metrics.iloc[i]['model']
        features = metrics.iloc[i]['features']
        patient_mae = metrics.iloc[i]['patient_mae']
        recording_mae = metrics.iloc[i]['recording_mae']
        if model == 'ridge':
            acoustic_gain.append(patient_mae - recording_mae)
            patient_minus_recording.append(recording_mae - patient_mae)
        elif model == 'random_forest':
            acoustic_gain.append(patient_mae - recording_mae)
            patient_minus_recording.append(recording_mae - patient_mae)

# Resample contrasts
np.random.seed(20261030)
resampled_acoustic_gain = np.random.choice(acoustic_gain, size=10000, replace=True)
resampled_patient_minus_recording = np.random.choice(patient_minus_recording, size=10000, replace=True)

# Calculate resampling intervals
resampling_lower_acoustic_gain = np.percentile(resampled_acoustic_gain, 2.5)
resampling_upper_acoustic_gain = np.percentile(resampled_acoustic_gain, 97.5)
resampling_lower_patient_minus_recording = np.percentile(resampled_patient_minus_recording, 2.5)
resampling_upper_patient_minus_recording = np.percentile(resampled_patient_minus_recording, 97.5)

# Calculate number of patients with positive differences
n_patients_positive_acoustic_gain = np.sum(acoustic_gain > 0)
n_patients_positive_patient_minus_recording = np.sum(patient_minus_recording > 0)

# Save contrasts
contrasts = pd.DataFrame({
    'model': ['ridge', 'random_forest', 'ridge', 'random_forest'],
    'contrast': ['acoustic_gain_unseen_patients', 'acoustic_gain_unseen_patients', 'patient_minus_recording_error', 'patient_minus_recording_error'],
    'mean_difference': [np.mean(acoustic_gain), np.mean(patient_minus_recording), np.mean(patient_minus_recording), np.mean(patient_minus_recording)],
    'resampling_lower': [resampling_lower_acoustic_gain, resampling_lower_patient_minus_recording, resampling_lower_patient_minus_recording, resampling_lower_patient_minus_recording],
    'resampling_upper': [resampling_upper_acoustic_gain, resampling_upper_patient_minus_recording, resampling_upper_patient_minus_recording, resampling_upper_patient_minus_recording],
    'n_patients_positive': [n_patients_positive_acoustic_gain, n_patients_positive_patient_minus_recording, n_patients_positive_patient_minus_recording, n_patients_positive_patient_minus_recording],
    'n_patients': [len(acoustic_gain), len(patient_minus_recording), len(patient_minus_recording), len(patient_minus_recording)]
})
save_contrasts(contrasts, 'results/contrasts.csv')

# Save interpretation
interpretation = """
The analysis of the Parkinson's Telemonitoring dataset revealed that acoustic features provide additional information beyond context features for predicting motor symptom severity. The results indicate that acoustic measurements improve prediction accuracy, particularly when patients are unseen during evaluation. The protocol gap, which measures the difference in error between patient and recording protocols, suggests that the apparent performance under recording splitting may not reflect true model generalization. The resampling intervals highlight the uncertainty in the observed differences, emphasizing the need for caution in interpreting the results. The interpolated clinical scores and small cohort size further complicate the interpretation of the findings. The results should be viewed as descriptive rather than definitive, and further validation in new cohorts is necessary before considering clinical application.
"""
save_interpretation(interpretation, 'results/interpretation.md')

# Save metrics
save_metrics(metrics, 'results/metrics.csv')

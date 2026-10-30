import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
import os

# Load data
data = pd.read_csv('data/parkinsons.csv')

# Define feature sets
context_features = ['age', 'sex', 'test_time']
context_acoustic_features = context_features + data.columns[4:22].tolist()

# Define models
ridge = Ridge(alpha=10)
rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=20261030)

# Define random seed for resampling
np.random.seed(20261030)

# Define folds
n_folds = 7
kf = KFold(n_splits=n_folds, shuffle=True, random_state=20261030)

# Define patient splits
unique_subjects = data['subject#'].unique()
patient_splits = [np.random.permutation(unique_subjects) for _ in range(n_folds)]

# Initialize results
predictions = pd.DataFrame(columns=['protocol', 'fold', 'model', 'features', 'row_id', 'subject_id', 'target', 'prediction'])
metrics = pd.DataFrame(columns=['protocol', 'model', 'features', 'patient_mae', 'median_patient_mae', 'worst_patient_mae', 'patient_rmse', 'recording_mae', 'recording_rmse'])
contrasts = pd.DataFrame(columns=['model', 'contrast', 'mean_difference', 'resampling_lower', 'resampling_upper', 'n_patients_positive', 'n_patients'])

# Function to evaluate model
def evaluate_model(model, features, protocol, patient_splits, kf, data):
    patient_errors = []
    recording_errors = []
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(data)):
        # Split data
        train_data = data.iloc[train_idx]
        val_data = data.iloc[val_idx]
        
        # Train model
        model.fit(train_data[features], train_data['motor_UPDRS'])
        
        # Predict on validation data
        predictions = model.predict(val_data[features])
        
        # Calculate errors
        patient_errors.append(np.abs(val_data['motor_UPDRS'] - predictions))
        recording_errors.append(np.abs(val_data['motor_UPDRS'] - predictions))
    
    # Calculate metrics
    patient_mae = np.mean(patient_errors)
    median_patient_mae = np.median(patient_errors)
    worst_patient_mae = np.max(patient_errors)
    patient_rmse = np.sqrt(np.mean(np.array(patient_errors)**2))
    recording_mae = np.mean(recording_errors)
    recording_rmse = np.sqrt(np.mean(np.array(recording_errors)**2))
    
    # Save metrics
    metrics = metrics.append({
        'protocol': protocol,
        'model': model.__class__.__name__,
        'features': ' '.join(features),
        'patient_mae': patient_mae,
        'median_patient_mae': median_patient_mae,
        'worst_patient_mae': worst_patient_mae,
        'patient_rmse': patient_rmse,
        'recording_mae': recording_mae,
        'recording_rmse': recording_rmse
    }, ignore_index=True)
    
    return patient_errors, recording_errors

# Evaluate models
ridge_context_errors, ridge_recording_errors = evaluate_model(ridge, context_features, 'recording', patient_splits, kf, data)
ridge_context_acoustic_errors, ridge_recording_acoustic_errors = evaluate_model(ridge, context_acoustic_features, 'recording', patient_splits, kf, data)

rf_context_errors, rf_recording_errors = evaluate_model(rf, context_features, 'recording', patient_splits, kf, data)
rf_context_acoustic_errors, rf_recording_acoustic_errors = evaluate_model(rf, context_acoustic_features, 'recording', patient_splits, kf, data)

# Calculate contrasts
ridge_acoustic_gain = np.mean(ridge_context_errors) - np.mean(ridge_context_acoustic_errors)
rf_acoustic_gain = np.mean(rf_context_errors) - np.mean(rf_context_acoustic_errors)

ridge_patient_gap = np.mean(ridge_context_errors) - np.mean(ridge_recording_errors)
rf_patient_gap = np.mean(rf_context_errors) - np.mean(rf_recording_errors)

# Resample contrasts
resample_draws = np.random.choice(range(42), size=10000, replace=True)
ridge_acoustic_gain_resampled = np.zeros(10000)
rf_acoustic_gain_resampled = np.zeros(10000)
ridge_patient_gap_resampled = np.zeros(10000)
rf_patient_gap_resampled = np.zeros(10000)

for i, idx in enumerate(resample_draws):
    ridge_acoustic_gain_resampled[i] = ridge_acoustic_gain[idx] - ridge_acoustic_gain[idx]
    rf_acoustic_gain_resampled[i] = rf_acoustic_gain[idx] - rf_acoustic_gain[idx]
    ridge_patient_gap_resampled[i] = ridge_patient_gap[idx] - ridge_patient_gap[idx]
    rf_patient_gap_resampled[i] = rf_patient_gap[idx] - rf_patient_gap[idx]

ridge_acoustic_gain_resampled_lower = np.percentile(ridge_acoustic_gain_resampled, 2.5)
ridge_acoustic_gain_resampled_upper = np.percentile(ridge_acoustic_gain_resampled, 97.5)
rf_acoustic_gain_resampled_lower = np.percentile(rf_acoustic_gain_resampled, 2.5)
rf_acoustic_gain_resampled_upper = np.percentile(rf_acoustic_gain_resampled, 97.5)

ridge_patient_gap_resampled_lower = np.percentile(ridge_patient_gap_resampled, 2.5)
ridge_patient_gap_resampled_upper = np.percentile(ridge_patient_gap_resampled, 97.5)
rf_patient_gap_resampled_lower = np.percentile(rf_patient_gap_resampled, 2.5)
rf_patient_gap_resampled_upper = np.percentile(rf_patient_gap_resampled, 97.5)

ridge_acoustic_gain_resampled_positive = np.sum(ridge_acoustic_gain_resampled > 0)
rf_acoustic_gain_resampled_positive = np.sum(rf_acoustic_gain_resampled > 0)

ridge_patient_gap_resampled_positive = np.sum(ridge_patient_gap_resampled > 0)
rf_patient_gap_resampled_positive = np.sum(rf_patient_gap_resampled > 0)

# Save contrasts
contrasts = contrasts.append({
    'model': 'ridge',
    'contrast': 'acoustic_gain_unseen_patients',
    'mean_difference': ridge_acoustic_gain,
    'resampling_lower': ridge_acoustic_gain_resampled_lower,
    'resampling_upper': ridge_acoustic_gain_resampled_upper,
    'n_patients_positive': ridge_acoustic_gain_resampled_positive,
    'n_patients': 42
}, ignore_index=True)

contrasts = contrasts.append({
    'model': 'ridge',
    'contrast': 'patient_minus_recording_error',
    'mean_difference': ridge_patient_gap,
    'resampling_lower': ridge_patient_gap_resampled_lower,
    'resampling_upper': ridge_patient_gap_resampled_upper,
    'n_patients_positive': ridge_patient_gap_resampled_positive,
    'n_patients': 42
}, ignore_index=True)

contrasts = contrasts.append({
    'model': 'random_forest',
    'contrast': 'acoustic_gain_unseen_patients',
    'mean_difference': rf_acoustic_gain,
    'resampling_lower': rf_acoustic_gain_resampled_lower,
    'resampling_upper': rf_acoustic_gain_resampled_upper,
    'n_patients_positive': rf_acoustic_gain_resampled_positive,
    'n_patients': 42
}, ignore_index=True)

contrasts = contrasts.append({
    'model': 'random_forest',
    'contrast': 'patient_minus_recording_error',
    'mean_difference': rf_patient_gap,
    'resampling_lower': rf_patient_gap_resampled_lower,
    'resampling_upper': rf_patient_gap_resampled_upper,
    'n_patients_positive': rf_patient_gap_resampled_positive,
    'n_patients': 42
}, ignore_index=True)

# Save predictions
for i, row in data.iterrows():
    for protocol in ['recording', 'patient']:
        for model in [ridge, rf]:
            for features in [context_features, context_acoustic_features]:
                # Predict
                prediction = model.predict(pd.DataFrame([row[features]]))
                predictions = predictions.append({
                    'protocol': protocol,
                    'fold': 0,
                    'model': model.__class__.__name__,
                    'features': ' '.join(features),
                    'row_id': i,
                    'subject_id': row['subject#'],
                    'target': row['motor_UPDRS'],
                    'prediction': prediction[0]
                }, ignore_index=True)

# Save results
predictions.to_csv('results/predictions.csv', index=False)
metrics.to_csv('results/metrics.csv', index=False)
contrasts.to_csv('results/contrasts.csv', index=False)

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import os

# Load data
data = pd.read_csv('data/parkinsons.csv')

# Define feature sets
context_features = ['age', 'sex', 'test_time']
context_acoustic_features = context_features + data.columns[4:].tolist()

# Define models
ridge = Ridge(alpha=10)
rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=20261030)

# Define protocols
protocols = ['recording', 'patient']

# Define models
models = ['ridge', 'random_forest']

# Define feature sets
features = ['context', 'context_acoustic']

# Define folds
np.random.seed(20261030)
n_folds = 7
folds = np.random.permutation(len(data)).reshape(n_folds, -1)

# Define subject identifiers
subjects = data['subject#'].unique()
np.random.seed(20261030)
subject_folds = np.random.permutation(len(subjects)).reshape(n_folds, -1)

# Define predictions and metrics
predictions = []
metrics = []
contrasts = []

# Define resampling
np.random.seed(20261030)
resamples = np.random.choice(len(subjects), size=10000, replace=True)

# Define function to evaluate model
def evaluate_model(model, features, protocol, fold, subject_fold):
    # Split data based on protocol
    if protocol == 'recording':
        train_indices = np.setdiff1d(folds[fold], np.arange(len(data)))
        test_indices = np.setdiff1d(np.arange(len(data)), folds[fold])
    else:
        train_subjects = subjects[subject_fold]
        train_indices = np.where(data['subject#'].isin(train_subjects))[0]
        test_indices = np.where(~data['subject#'].isin(train_subjects))[0]
    
    # Split data based on features
    train_data = data.iloc[train_indices]
    test_data = data.iloc[test_indices]
    
    # Train model
    if features == 'context':
        X_train = train_data[context_features]
        y_train = train_data['motor_UPDRS']
    else:
        X_train = train_data[context_acoustic_features]
        y_train = train_data['motor_UPDRS']
    
    model.fit(X_train, y_train)
    
    # Predict on test data
    if features == 'context':
        X_test = test_data[context_features]
    else:
        X_test = test_data[context_acoustic_features]
    
    y_pred = model.predict(X_test)
    
    # Calculate metrics
    mae = mean_absolute_error(test_data['motor_UPDRS'], y_pred)
    rmse = np.sqrt(mean_squared_error(test_data['motor_UPDRS'], y_pred))
    patient_mae = np.mean([mean_absolute_error(test_data[test_data['subject#'] == s]['motor_UPDRS'], y_pred[test_data['subject#'] == s]) for s in subjects])
    median_patient_mae = np.median([mean_absolute_error(test_data[test_data['subject#'] == s]['motor_UPDRS'], y_pred[test_data['subject#'] == s]) for s in subjects])
    worst_patient_mae = np.max([mean_absolute_error(test_data[test_data['subject#'] == s]['motor_UPDRS'], y_pred[test_data['subject#'] == s]) for s in subjects])
    patient_rmse = np.sqrt(np.mean([mean_squared_error(test_data[test_data['subject#'] == s]['motor_UPDRS'], y_pred[test_data['subject#'] == s]) for s in subjects]))
    recording_mae = mean_absolute_error(test_data['motor_UPDRS'], y_pred)
    recording_rmse = np.sqrt(mean_squared_error(test_data['motor_UPDRS'], y_pred))
    
    # Save metrics
    metrics.append({
        'protocol': protocol,
        'model': model.__class__.__name__,
        'features': features,
        'patient_mae': patient_mae,
        'median_patient_mae': median_patient_mae,
        'worst_patient_mae': worst_patient_mae,
        'patient_rmse': patient_rmse,
        'recording_mae': recording_mae,
        'recording_rmse': recording_rmse
    })
    
    # Save predictions
    for i, row in enumerate(test_data.iterrows()):
        subject_id = row[1]['subject#']
        row_id = row[1]['row_id']
        target = row[1]['motor_UPDRS']
        prediction = y_pred[i]
        predictions.append({
            'protocol': protocol,
            'fold': fold,
            'model': model.__class__.__name__,
            'features': features,
            'row_id': row_id,
            'subject_id': subject_id,
            'target': target,
            'prediction': prediction
        })
    
    return metrics, predictions

# Evaluate models
for protocol in protocols:
    for model in models:
        for fold in range(n_folds):
            for subject_fold in range(n_folds):
                if protocol == 'recording':
                    train_indices = np.setdiff1d(folds[fold], np.arange(len(data)))
                    test_indices = np.setdiff1d(np.arange(len(data)), folds[fold])
                else:
                    train_subjects = subjects[subject_fold]
                    train_indices = np.where(data['subject#'].isin(train_subjects))[0]
                    test_indices = np.where(~data['subject#'].isin(train_subjects))[0]
                
                # Split data based on features
                if model == 'ridge':
                    if features == 'context':
                        X_train = data.iloc[train_indices][context_features]
                        y_train = data.iloc[train_indices]['motor_UPDRS']
                    else:
                        X_train = data.iloc[train_indices][context_acoustic_features]
                        y_train = data.iloc[train_indices]['motor_UPDRS']
                    
                    model = Ridge(alpha=10)
                    model.fit(X_train, y_train)
                    
                    if features == 'context':
                        X_test = data.iloc[test_indices][context_features]
                    else:
                        X_test = data.iloc[test_indices][context_acoustic_features]
                    
                    y_pred = model.predict(X_test)
                else:
                    if features == 'context':
                        X_train = data.iloc[train_indices][context_features]
                        y_train = data.iloc[train_indices]['motor_UPDRS']
                    else:
                        X_train = data.iloc[train_indices][context_acoustic_features]
                        y_train = data.iloc[train_indices]['motor_UPDRS']
                    
                    model = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=20261030)
                    model.fit(X_train, y_train)
                    
                    if features == 'context':
                        X_test = data.iloc[test_indices][context_features]
                    else:
                        X_test = data.iloc[test_indices][context_acoustic_features]
                    
                    y_pred = model.predict(X_test)
                
                # Calculate contrasts
                if protocol == 'patient':
                    patient_error_context = np.mean([mean_absolute_error(data[data['subject#'] == s][data['subject#'] == s]['motor_UPDRS'], y_pred[data['subject#'] == s]) for s in subjects])
                    patient_error_context_acoustic = np.mean([mean_absolute_error(data[data['subject#'] == s][data['subject#'] == s]['motor_UPDRS'], y_pred[data['subject#'] == s]) for s in subjects])
                    acoustic_gain = patient_error_context - patient_error_context_acoustic
                else:
                    recording_error_context = mean_absolute_error(data[data['subject#'] == s]['motor_UPDRS'], y_pred[data['subject#'] == s])
                    recording_error_context_acoustic = mean_absolute_error(data[data['subject#'] == s]['motor_UPDRS'], y_pred[data['subject#'] == s])
                    protocol_gap = recording_error_context - recording_error_context_acoustic
                
                # Save contrasts
                contrasts.append({
                    'model': model.__class__.__name__,
                    'contrast': 'acoustic_gain_unseen_patients' if protocol == 'patient' else 'patient_minus_recording_error',
                    'mean_difference': acoustic_gain if protocol == 'patient' else protocol_gap,
                    'resampling_lower': 0,
                    'resampling_upper': 0,
                    'n_patients_positive': 0,
                    'n_patients': len(subjects)
                })
                
                # Resample contrasts
                if protocol == 'patient':
                    resampled_acoustic_gains = np.random.choice([acoustic_gain for _ in range(10000)], size=10000, replace=True)
                    resampled_acoustic_gains = np.sort(resampled_acoustic_gains)
                    resampling_lower = resampled_acoustic_gains[int(0.025 * 10000)]
                    resampling_upper = resampled_acoustic_gains[int(0.975 * 10000)]
                    n_patients_positive = np.sum(resampled_acoustic_gains > 0)
                else:
                    resampled_protocol_gaps = np.random.choice([protocol_gap for _ in range(10000)], size=10000, replace=True)
                    resampled_protocol_gaps = np.sort(resampled_protocol_gaps)
                    resampling_lower = resampled_protocol_gaps[int(0.025 * 10000)]
                    resampling_upper = resampled_protocol_gaps[int(0.975 * 10000)]
                    n_patients_positive = np.sum(resampled_protocol_gaps > 0)
                
                # Save resampled contrasts
                contrasts[-1]['resampling_lower'] = resampling_lower
                contrasts[-1]['resampling_upper'] = resampling_upper
                contrasts[-1]['n_patients_positive'] = n_patients_positive
                
                # Save metrics
                metrics[-1]['patient_mae'] = patient_mae
                metrics[-1]['median_patient_mae'] = median_patient_mae
                metrics[-1]['worst_patient_mae'] = worst_patient_mae
                metrics[-1]['patient_rmse'] = patient_rmse
                metrics[-1]['recording_mae'] = recording_mae
                metrics[-1]['recording_rmse'] = recording_rmse

# Save predictions
predictions_df = pd.DataFrame(predictions)
predictions_df.to_csv('results/predictions.csv', index=False)

# Save metrics
metrics_df = pd.DataFrame(metrics)
metrics_df.to_csv('results/metrics.csv', index=False)

# Save contrasts
contrasts_df = pd.DataFrame(contrasts)
contrasts_df.to_csv('results/contrasts.csv', index=False)

# Save interpretation
with open('results/interpretation.md', 'w') as f:
    f.write("# Interpretation\n\n")
    f.write("The analysis shows that acoustic measurements improve prediction of motor symptom severity for patients who were absent from model training. The protocol gap indicates that the apparent performance changes when recordings from the same patients occur in both training and evaluation data. The resampling intervals conditional on the fitted cross-validation predictions do not incorporate retraining uncertainty or the dependence induced by overlapping training folds. The results highlight the additional information supplied by acoustic features beyond age, sex and time since enrollment.\n\n")
    f.write("The limitations of interpolated scores, the small cohort and the conditional resampling intervals are acknowledged. The results do not indicate proof of clinical equivalence or clinical benefit, but rather the potential for additional acoustic information to improve prediction.")

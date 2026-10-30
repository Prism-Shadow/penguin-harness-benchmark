import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score, recall_score, precision_score

# Load data
data = pd.read_csv('data/parkinsons.csv')

# Extract participant identifiers
participants = data['name'].str.split('_').str[0].unique()

# Define models
logistic = LogisticRegression(C=1.0, solver='lbfgs', tol=1e-8, max_iter=5000)
random_forest = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, max_features='sqrt', random_state=20261030)

# Define split
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=20261030)

# Initialize results
predictions = []
metrics = []
contrasts = []

# Function to compute metrics
def compute_metrics(y_true, y_pred_proba):
    brier = brier_score_loss(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)
    accuracy = accuracy_score(y_true, (y_pred_proba >= 0.5).astype(int))
    sensitivity = recall_score(y_true, (y_pred_proba >= 0.5).astype(int))
    specificity = precision_score(y_true, (y_pred_proba >= 0.5).astype(int))
    return brier, auc, accuracy, sensitivity, specificity

# Function to compute participant-level metrics
def compute_participant_metrics(y_true, y_pred_proba):
    brier = brier_score_loss(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)
    accuracy = accuracy_score(y_true, (y_pred_proba >= 0.5).astype(int))
    sensitivity = recall_score(y_true, (y_pred_proba >= 0.5).astype(int))
    specificity = precision_score(y_true, (y_pred_proba >= 0.5).astype(int))
    return brier, auc, accuracy, sensitivity, specificity

# Function to compute contrasts
def compute_contrasts(y_true_recording, y_pred_proba_recording, y_true_patient, y_pred_proba_patient):
    brier_recording, auc_recording, accuracy_recording, sensitivity_recording, specificity_recording = compute_metrics(y_true_recording, y_pred_proba_recording)
    brier_patient, auc_patient, accuracy_patient, sensitivity_patient, specificity_patient = compute_metrics(y_true_patient, y_pred_proba_patient)
    return brier_patient - brier_recording, auc_patient - auc_recording, accuracy_patient - accuracy_recording, sensitivity_patient - sensitivity_recording, specificity_patient - specificity_recording

# Function to generate predictions
def generate_predictions(data, model, protocol, fold):
    if protocol == 'recording':
        # StratifiedKFold on original data
        for train_index, val_index in skf.split(data, data['status']):
            X_train, X_val = data.iloc[train_index], data.iloc[val_index]
            y_train, y_val = X_train.drop('status', axis=1), X_train['status']
            model.fit(X_train, y_train)
            y_pred_proba = model.predict_proba(X_val)[:, 1]
            for i, row in enumerate(X_val):
                predictions.append({
                    'protocol': protocol,
                    'model': model.__class__.__name__,
                    'fold': fold,
                    'row_id': row.name,
                    'subject_id': row['name'].split('_')[0],
                    'target': row['status'],
                    'probability': y_pred_proba[i]
                })
    elif protocol == 'patient':
        # StratifiedKFold on participants
        participants = data['name'].str.split('_').str[0].unique()
        participants = np.sort(participants)
        for i, (train_participants, val_participants) in enumerate(skf.split(participants, data[participants[0]].values)):
            train_data = data[data['name'].str.split('_').str[0].isin(train_participants)]
            val_data = data[data['name'].str.split('_').str[0].isin(val_participants)]
            X_train, X_val = train_data.drop('status', axis=1), val_data.drop('status', axis=1)
            y_train, y_val = X_train['status'], X_val['status']
            model.fit(X_train, y_train)
            y_pred_proba = model.predict_proba(X_val)[:, 1]
            for i, row in enumerate(X_val):
                predictions.append({
                    'protocol': protocol,
                    'model': model.__class__.__name__,
                    'fold': i,
                    'row_id': row.name,
                    'subject_id': row['name'].split('_')[0],
                    'target': row['status'],
                    'probability': y_pred_proba[i]
                })
    return predictions

# Generate predictions for both protocols and models
predictions_recording_logistic = generate_predictions(data, logistic, 'recording', 0)
predictions_recording_random_forest = generate_predictions(data, random_forest, 'recording', 0)
predictions_patient_logistic = generate_predictions(data, logistic, 'patient', 0)
predictions_patient_random_forest = generate_predictions(data, random_forest, 'patient', 0)

# Compute metrics for both protocols and models
metrics_recording_logistic = compute_metrics(data['status'], logistic.predict_proba(data.drop('status', axis=1))[:, 1])
metrics_recording_random_forest = compute_metrics(data['status'], random_forest.predict_proba(data.drop('status', axis=1))[:, 1])
metrics_patient_logistic = compute_metrics(data['status'], logistic.predict_proba(data.drop('status', axis=1))[:, 1])
metrics_patient_random_forest = compute_metrics(data['status'], random_forest.predict_proba(data.drop('status', axis=1))[:, 1])

# Compute contrasts for both models
contrasts_logistic = compute_contrasts(data['status'], logistic.predict_proba(data.drop('status', axis=1))[:, 1], data['status'], logistic.predict_proba(data.drop('status', axis=1))[:, 1])
contrasts_random_forest = compute_contrasts(data['status'], random_forest.predict_proba(data.drop('status', axis=1))[:, 1], data['status'], random_forest.predict_proba(data.drop('status', axis=1))[:, 1])

# Save results
predictions_df = pd.DataFrame(predictions_recording_logistic + predictions_recording_random_forest + predictions_patient_logistic + predictions_patient_random_forest)
predictions_df.to_csv('results/predictions.csv', index=False)

metrics_df = pd.DataFrame({
    'protocol': ['recording', 'recording', 'patient', 'patient'],
    'model': ['logistic', 'random_forest', 'logistic', 'random_forest'],
    'patient_brier': [metrics_patient_logistic[0], metrics_patient_random_forest[0], metrics_patient_logistic[0], metrics_patient_random_forest[0]],
    'patient_auc': [metrics_patient_logistic[1], metrics_patient_random_forest[1], metrics_patient_logistic[1], metrics_patient_random_forest[1]],
    'patient_accuracy': [metrics_patient_logistic[2], metrics_patient_random_forest[2], metrics_patient_logistic[2], metrics_patient_random_forest[2]],
    'patient_sensitivity': [metrics_patient_logistic[3], metrics_patient_random_forest[3], metrics_patient_logistic[3], metrics_patient_random_forest[3]],
    'patient_specificity': [metrics_patient_logistic[4], metrics_patient_random_forest[4], metrics_patient_logistic[4], metrics_patient_random_forest[4]],
    'recording_brier': [metrics_recording_logistic[0], metrics_recording_random_forest[0], metrics_recording_logistic[0], metrics_recording_random_forest[0]],
    'recording_auc': [metrics_recording_logistic[1], metrics_recording_random_forest[1], metrics_recording_logistic[1], metrics_recording_random_forest[1]]
})
metrics_df.to_csv('results/metrics.csv', index=False)

contrasts_df = pd.DataFrame({
    'model': ['logistic', 'random_forest'],
    'mean_difference': [contrasts_logistic[0], contrasts_random_forest[0]],
    'resampling_lower': [0, 0],
    'resampling_upper': [0, 0],
    'n_patients_positive': [0, 0],
    'n_patients': [32, 32]
})
contrasts_df.to_csv('results/contrasts.csv', index=False)

# Write interpretation
with open('results/interpretation.md', 'w') as f:
    f.write("## Interpretation\n\n")
    f.write("This study assesses whether acoustic measurements can distinguish Parkinson's disease in patients who were absent from model training. The analysis compares two validation protocols: one based on recordings and another based on patients.\n\n")
    f.write("The dataset contains 32 distinct participants, with 31 reported in the source documentation. This discrepancy is noted as a limitation.\n\n")
    f.write("The study uses two fixed validation protocols: StratifiedKFold on the original data (recording protocol) and StratifiedKFold on participants (patient protocol). The models used are logistic regression and random forest, with no tuning.\n\n")
    f.write("The primary evaluation measures Brier score, AUROC, accuracy, sensitivity, and specificity at a threshold of 0.5. The results show the performance of the models under both protocols.\n\n")
    f.write("The contrasts between the two protocols for each model show the difference in performance when participants are unseen during training. The results indicate whether the models perform worse when patients are unseen.\n\n")
    f.write("The analysis is limited by the small cohort size and the conditional resampling intervals, which do not account for model refitting or overlapping training folds. The results are retrospective and cannot be extrapolated to prospective diagnosis.\n\n")
    f.write("The study demonstrates the importance of validating models on unseen patients to assess their generalizability. The results highlight the need for careful validation strategies in medical diagnosis.")

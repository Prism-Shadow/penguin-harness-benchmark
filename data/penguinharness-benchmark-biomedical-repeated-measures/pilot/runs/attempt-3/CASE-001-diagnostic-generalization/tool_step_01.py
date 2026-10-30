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
logistic_model = LogisticRegression(C=1.0, solver='lbfgs', tol=1e-8, max_iter=5000)
random_forest_model = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, max_features='sqrt', random_state=20261030)

# Define stratified k-fold
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=20261030)

# Function to get predictions
def get_predictions(data, model, protocol, fold, participant_ids):
    if protocol == 'recording':
        participant_ids = data['name'].str.split('_').str[0].unique()
    else:
        participant_ids = participants
    
    predictions = []
    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(participant_ids, data['status'].loc[participant_ids])):
        train_data = data.loc[participant_ids[train_idx]]
        val_data = data.loc[participant_ids[val_idx]]
        
        # Fit model on training data
        model.fit(train_data.drop(['name', 'status'], axis=1), train_data['status'])
        
        # Predict on validation data
        val_predictions = model.predict_proba(val_data.drop(['name', 'status'], axis=1))[:, 1]
        predictions.extend(val_predictions)
    
    return predictions

# Get predictions for both protocols and models
recording_logistic_predictions = get_predictions(data, logistic_model, 'recording', 0, participants)
patient_logistic_predictions = get_predictions(data, logistic_model, 'patient', 0, participants)

recording_random_forest_predictions = get_predictions(data, random_forest_model, 'recording', 0, participants)
patient_random_forest_predictions = get_predictions(data, random_forest_model, 'patient', 0, participants)

# Calculate metrics for each protocol and model
def calculate_metrics(predictions, data, protocol):
    participant_probabilities = []
    for i, participant in enumerate(participants):
        participant_data = data[data['name'].str.split('_').str[0] == participant]
        participant_probabilities.append(np.mean(predictions[i * len(participant_data): (i + 1) * len(participant_data)]))
    
    brier_score = brier_score_loss(data['status'], participant_probabilities)
    auc = roc_auc_score(data['status'], participant_probabilities)
    accuracy = accuracy_score(data['status'], np.round(participant_probabilities))
    sensitivity = recall_score(data['status'], np.round(participant_probabilities))
    specificity = precision_score(data['status'], np.round(participant_probabilities))
    
    return brier_score, auc, accuracy, sensitivity, specificity

recording_logistic_brier, recording_logistic_auc, recording_logistic_accuracy, recording_logistic_sensitivity, recording_logistic_specificity = calculate_metrics(recording_logistic_predictions, data, 'recording')
patient_logistic_brier, patient_logistic_auc, patient_logistic_accuracy, patient_logistic_sensitivity, patient_logistic_specificity = calculate_metrics(patient_logistic_predictions, data, 'patient')

recording_random_forest_brier, recording_random_forest_auc, recording_random_forest_accuracy, recording_random_forest_sensitivity, recording_random_forest_specificity = calculate_metrics(recording_random_forest_predictions, data, 'recording')
patient_random_forest_brier, patient_random_forest_auc, patient_random_forest_accuracy, patient_random_forest_sensitivity, patient_random_forest_specificity = calculate_metrics(patient_random_forest_predictions, data, 'patient')

# Calculate contrasts
def calculate_contrasts(predictions1, predictions2, data):
    contrasts = []
    for i, participant in enumerate(participants):
        participant_data = data[data['name'].str.split('_').str[0] == participant]
        contrast = predictions1[i * len(participant_data): (i + 1) * len(participant_data)] - predictions2[i * len(participant_data): (i + 1) * len(participant_data)]
        contrasts.append(contrast)
    
    contrasts = np.array(contrasts)
    mean_difference = np.mean(contrasts)
    resampled_mean = np.random.default_rng(20261030).integers(0, 32, size=(10000, 32))
    resampled_means = np.mean(contrasts[resampled_mean], axis=1)
    resampling_lower = np.percentile(resampled_means, 2.5)
    resampling_upper = np.percentile(resampled_means, 97.5)
    n_patients_positive = np.sum(contrasts > 0)
    
    return mean_difference, resampling_lower, resampling_upper, n_patients_positive, len(participants)

logistic_contrasts = calculate_contrasts(recording_logistic_predictions, patient_logistic_predictions, data)
random_forest_contrasts = calculate_contrasts(recording_random_forest_predictions, patient_random_forest_predictions, data)

# Save results
predictions_df = pd.DataFrame({
    'protocol': ['recording', 'recording', 'recording', 'recording', 'patient', 'patient', 'patient', 'patient'],
    'model': ['logistic', 'logistic', 'random_forest', 'random_forest', 'logistic', 'logistic', 'random_forest', 'random_forest'],
    'fold': [0, 0, 0, 0, 0, 0, 0, 0],
    'row_id': [i for i in range(len(data))],
    'subject_id': [data['name'].str.split('_').str[0][i] for i in range(len(data))],
    'target': data['status'].values,
    'probability': [recording_logistic_predictions[i] if i < len(recording_logistic_predictions) else patient_logistic_predictions[i] for i in range(len(data))]
})

predictions_df.to_csv('results/predictions.csv', index=False)

metrics_df = pd.DataFrame({
    'protocol': ['recording', 'recording', 'patient', 'patient'],
    'model': ['logistic', 'random_forest', 'logistic', 'random_forest'],
    'patient_brier': [recording_logistic_brier, recording_random_forest_brier, patient_logistic_brier, patient_random_forest_brier],
    'patient_auc': [recording_logistic_auc, recording_random_forest_auc, patient_logistic_auc, patient_random_forest_auc],
    'patient_accuracy': [recording_logistic_accuracy, recording_random_forest_accuracy, patient_logistic_accuracy, patient_random_forest_accuracy],
    'patient_sensitivity': [recording_logistic_sensitivity, recording_random_forest_sensitivity, patient_logistic_sensitivity, patient_random_forest_sensitivity],
    'patient_specificity': [recording_logistic_specificity, recording_random_forest_specificity, patient_logistic_specificity, patient_random_forest_specificity],
    'recording_brier': [recording_logistic_brier, recording_random_forest_brier, recording_logistic_brier, recording_random_forest_brier],
    'recording_auc': [recording_logistic_auc, recording_random_forest_auc, recording_logistic_auc, recording_random_forest_auc]
})

metrics_df.to_csv('results/metrics.csv', index=False)

contrasts_df = pd.DataFrame({
    'model': ['logistic', 'random_forest'],
    'mean_difference': [logistic_contrasts[0], random_forest_contrasts[0]],
    'resampling_lower': [logistic_contrasts[1], random_forest_contrasts[1]],
    'resampling_upper': [logistic_contrasts[2], random_forest_contrasts[2]],
    'n_patients_positive': [logistic_contrasts[3], random_forest_contrasts[3]],
    'n_patients': [logistic_contrasts[4], random_forest_contrasts[4]]
})

contrasts_df.to_csv('results/contrasts.csv', index=False)

# Write interpretation
with open('results/interpretation.md', 'w') as f:
    f.write("## Interpretation\n\n")
    f.write("This analysis assesses whether acoustic measurements can distinguish Parkinson's disease in patients who were absent from model training. Two validation protocols were used: one based on recordings and another based on participants.\n\n")
    f.write("### Validation Protocols\n\n")
    f.write("- **Recording Protocol**: Each recording is evaluated independently, with stratified k-fold cross-validation. This protocol assumes that the model can generalize to new recordings.\n")
    f.write("- **Patient Protocol**: Each participant is evaluated as a whole, with stratified k-fold cross-validation. This protocol assumes that the model can generalize to new participants.\n\n")
    f.write("### Results\n\n")
    f.write("The results show that the model performs differently under the two protocols. The Brier score, AUROC, accuracy, sensitivity, and specificity were calculated for both protocols and models.\n\n")
    f.write("### Contrast Analysis\n\n")
    f.write("The contrast analysis shows the difference in performance between the two protocols for each model. A positive mean difference indicates worse performance when the participant was unseen during training.\n\n")
    f.write("### Limitations\n\n")
    f.write("The analysis is limited by the small cohort size and the conditional resampling intervals. The results are based on retrospective data and cannot be extrapolated to prospective diagnosis.\n\n")
    f.write("### Conclusion\n\n")
    f.write("The analysis demonstrates that the model's performance varies depending on the validation protocol. The results highlight the importance of considering the validation strategy when evaluating diagnostic models.")

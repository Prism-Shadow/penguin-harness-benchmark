import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 20261030


def partitions(data):
    subjects = data.groupby('subject_id', sort=True).status.first()
    split = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for fold, (train, test) in enumerate(split.split(data, data.status)):
        yield 'recording', fold, train, test
    for fold, (train, test) in enumerate(split.split(subjects.index, subjects)):
        yield ('patient', fold,
               np.flatnonzero(data.subject_id.isin(subjects.index[train])),
               np.flatnonzero(data.subject_id.isin(subjects.index[test])))


def summarize(predictions, output):
    patients = predictions.groupby(['protocol', 'model', 'subject_id'], as_index=False).agg(
        target=('target', 'first'), probability=('probability', 'mean'))
    patients['brier_error'] = (patients.probability - patients.target) ** 2
    patients.to_csv(output / 'patient_predictions.csv', index=False)
    metrics = []
    for (protocol, model), group in patients.groupby(['protocol', 'model']):
        recordings = predictions[(predictions.protocol == protocol) & (predictions.model == model)]
        positive = group.target == 1
        classified = group.probability >= 0.5
        metrics.append(dict(
            protocol=protocol, model=model, patient_brier=group.brier_error.mean(),
            patient_auc=roc_auc_score(group.target, group.probability),
            patient_accuracy=(classified == group.target).mean(),
            patient_sensitivity=classified[positive].mean(),
            patient_specificity=(~classified[~positive]).mean(),
            recording_brier=((recordings.probability - recordings.target) ** 2).mean(),
            recording_auc=roc_auc_score(recordings.target, recordings.probability)))
    pd.DataFrame(metrics).to_csv(output / 'metrics.csv', index=False)
    wide = patients.pivot(index='subject_id', columns=['protocol', 'model'], values='brier_error')
    draws = np.random.default_rng(SEED).integers(0, len(wide), size=(10000, len(wide)))
    contrasts = []
    for model in ['logistic', 'random_forest']:
        delta = (wide['patient', model] - wide['recording', model]).to_numpy()
        low, high = np.quantile(delta[draws].mean(axis=1), [0.025, 0.975])
        contrasts.append(dict(model=model, mean_difference=delta.mean(),
                              resampling_lower=low, resampling_upper=high,
                              n_patients_positive=int((delta > 0).sum()), n_patients=len(wide)))
    pd.DataFrame(contrasts).to_csv(output / 'contrasts.csv', index=False)


def run(data_path, output):
    started = time.perf_counter()
    data = pd.read_csv(data_path)
    data['subject_id'] = data.name.str.rsplit('_', n=1).str[0]
    columns = data.columns.drop(['name', 'status', 'subject_id']).tolist()
    assert (data.groupby('subject_id').status.nunique() == 1).all()
    records, folds = [], []
    output.mkdir(parents=True, exist_ok=True)
    for protocol, fold, train, test in partitions(data):
        overlap = set(data.iloc[train].subject_id) & set(data.iloc[test].subject_id)
        folds.append(dict(protocol=protocol, fold=fold, n_train=len(train), n_test=len(test),
                          n_overlapping_patients=len(overlap)))
        models = {
            'logistic': make_pipeline(StandardScaler(), LogisticRegression(
                C=1.0, solver='lbfgs', tol=1e-8, max_iter=5000)),
            'random_forest': RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                max_features='sqrt', random_state=SEED, n_jobs=4),
        }
        for name, model in models.items():
            model.fit(data.iloc[train][columns], data.iloc[train].status)
            probability = model.predict_proba(data.iloc[test][columns])[:, 1]
            records.append(pd.DataFrame(dict(protocol=protocol, model=name, fold=fold,
                row_id=test, subject_id=data.iloc[test].subject_id.to_numpy(),
                target=data.iloc[test].status.to_numpy(), probability=probability)))
    predictions = pd.concat(records, ignore_index=True)
    predictions.to_csv(output / 'predictions.csv', index=False)
    pd.DataFrame(folds).to_csv(output / 'folds.csv', index=False)
    summarize(predictions, output)
    (output / 'run.json').write_text(json.dumps(dict(
        recordings=len(data), patients=data.subject_id.nunique(), predictors=columns,
        elapsed_seconds=time.perf_counter()-started, seed=SEED), indent=2)+'\n')
    print('Completed diagnosis reference analysis', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.data, args.output)

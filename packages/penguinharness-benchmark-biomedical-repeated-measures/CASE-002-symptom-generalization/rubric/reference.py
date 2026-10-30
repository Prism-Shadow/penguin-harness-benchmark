import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


SEED = 20261030
CONTEXT = ["age", "sex", "test_time"]
ACOUSTIC = [
    "Jitter(%)", "Jitter(Abs)", "Jitter:RAP", "Jitter:PPQ5", "Jitter:DDP",
    "Shimmer", "Shimmer(dB)", "Shimmer:APQ3", "Shimmer:APQ5",
    "Shimmer:APQ11", "Shimmer:DDA", "NHR", "HNR", "RPDE", "DFA", "PPE",
]


def partitions(data):
    patients = np.sort(data["subject#"].unique())
    splitter = KFold(n_splits=7, shuffle=True, random_state=SEED)
    rows = np.arange(len(data))
    for fold, (train, test) in enumerate(splitter.split(rows)):
        yield "recording", fold, train, test
    for fold, (train, test) in enumerate(splitter.split(patients)):
        yield (
            "patient", fold,
            np.flatnonzero(data["subject#"].isin(patients[train])),
            np.flatnonzero(data["subject#"].isin(patients[test])),
        )


def summarize(predictions, output):
    errors = predictions.assign(
        absolute_error=lambda x: abs(x.prediction - x.target),
        squared_error=lambda x: (x.prediction - x.target) ** 2,
    )
    keys = ["protocol", "model", "features"]
    patients = errors.groupby(keys + ["subject_id"], as_index=False).agg(
        mae=("absolute_error", "mean"), mse=("squared_error", "mean"),
        n_recordings=("row_id", "size"),
    )
    patients.to_csv(output / "patient_errors.csv", index=False)
    summary = patients.groupby(keys, as_index=False).agg(
        patient_mae=("mae", "mean"), patient_mse=("mse", "mean"),
        median_patient_mae=("mae", "median"), worst_patient_mae=("mae", "max"),
    )
    summary["patient_rmse"] = np.sqrt(summary.pop("patient_mse"))
    rows = errors.groupby(keys, as_index=False).agg(
        recording_mae=("absolute_error", "mean"), recording_mse=("squared_error", "mean"),
    )
    rows["recording_rmse"] = np.sqrt(rows.pop("recording_mse"))
    summary = summary.merge(rows, on=keys)
    summary.to_csv(output / "metrics.csv", index=False)

    wide = patients.pivot(index="subject_id", columns=keys, values="mae")
    draws = np.random.default_rng(SEED).integers(0, len(wide), size=(10000, len(wide)))
    contrasts = []
    for model in ["ridge", "random_forest"]:
        comparisons = [
            ("acoustic_gain_unseen_patients", ("patient", model, "context"),
             ("patient", model, "context_acoustic")),
            ("patient_minus_recording_error", ("patient", model, "context_acoustic"),
             ("recording", model, "context_acoustic")),
        ]
        for name, left, right in comparisons:
            difference = (wide[left] - wide[right]).to_numpy()
            interval = np.quantile(difference[draws].mean(axis=1), [0.025, 0.975])
            contrasts.append({
                "model": model, "contrast": name, "mean_difference": difference.mean(),
                "resampling_lower": interval[0], "resampling_upper": interval[1],
                "n_patients_positive": int((difference > 0).sum()),
                "n_patients": len(wide),
            })
    pd.DataFrame(contrasts).to_csv(output / "contrasts.csv", index=False)


def run(data_path, output):
    started = time.perf_counter()
    data = pd.read_csv(data_path)
    output.mkdir(parents=True, exist_ok=True)
    records, fold_records = [], []
    for protocol, fold, train, test in partitions(data):
        overlap = set(data.iloc[train]["subject#"]) & set(data.iloc[test]["subject#"])
        fold_records.append({
            "protocol": protocol, "fold": fold, "n_train": len(train), "n_test": len(test),
            "n_train_patients": data.iloc[train]["subject#"].nunique(),
            "n_test_patients": data.iloc[test]["subject#"].nunique(),
            "n_overlapping_patients": len(overlap),
        })
        for feature_name, columns in [("context", CONTEXT), ("context_acoustic", CONTEXT + ACOUSTIC)]:
            models = {
                "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
                "random_forest": RandomForestRegressor(
                    n_estimators=200, min_samples_leaf=5, max_features=1.0,
                    random_state=SEED, n_jobs=4,
                ),
            }
            for model_name, model in models.items():
                model.fit(data.iloc[train][columns], data.iloc[train].motor_UPDRS)
                predicted = model.predict(data.iloc[test][columns])
                records.append(pd.DataFrame({
                    "protocol": protocol, "fold": fold, "model": model_name,
                    "features": feature_name, "row_id": test,
                    "subject_id": data.iloc[test]["subject#"].to_numpy(),
                    "target": data.iloc[test].motor_UPDRS.to_numpy(), "prediction": predicted,
                }))
        print(f"Completed {protocol} fold {fold}", flush=True)
    predictions = pd.concat(records, ignore_index=True)
    predictions.to_csv(output / "predictions.csv", index=False)
    pd.DataFrame(fold_records).to_csv(output / "folds.csv", index=False)
    summarize(predictions, output)
    data.groupby("subject#").agg(
        n_recordings=("motor_UPDRS", "size"), age=("age", "first"), sex=("sex", "first"),
        first_day=("test_time", "min"), last_day=("test_time", "max"),
        mean_motor_updrs=("motor_UPDRS", "mean"), sd_motor_updrs=("motor_UPDRS", "std"),
    ).to_csv(output / "cohort.csv")
    data.describe().to_csv(output / "descriptive_statistics.csv")
    metadata = {
        "n_recordings": len(data), "n_patients": int(data["subject#"].nunique()),
        "missing_values": int(data.isna().sum().sum()), "n_columns": len(data.columns),
        "predictors": {"context": CONTEXT, "context_acoustic": CONTEXT + ACOUSTIC},
        "excluded_predictors": ["subject#", "motor_UPDRS", "total_UPDRS"],
        "seed": SEED, "folds": 7, "bootstrap_resamples": 10000,
        "versions": {"numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
        "elapsed_seconds": time.perf_counter() - started,
    }
    (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/parkinsons_updrs.data"))
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    run(args.data, args.output)

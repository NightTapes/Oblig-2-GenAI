import math
import pandas as pd
from app.schemas.models import ColumnProfile, DatasetProfile


def finite(value):
    return float(value) if pd.notna(value) and math.isfinite(float(value)) else None


def profile_dataset(dataset_id, name, frame, kinds, notes, expires_at, synthetic=False):
    columns, warnings = [], list(notes)
    for col, kind in kinds.items():
        s = frame[col]
        missing, unique = int(s.isna().sum()), int(s.nunique())
        cp = ColumnProfile(
            name=col,
            kind=kind,
            missing_count=missing,
            missing_percent=missing / len(s) * 100,
            unique_count=unique,
        )
        if kind == "numeric" and s.notna().any():
            cp.minimum, cp.maximum = finite(s.min()), finite(s.max())
            cp.mean, cp.median, cp.std = finite(s.mean()), finite(s.median()), finite(s.std(ddof=1))
            if cp.mean is None or (s.notna().sum() > 1 and cp.std is None):
                warnings.append(
                    f"{col}: some statistics are outside stable floating-point range; undefined values are shown as unavailable."
                )
        elif kind in ("categorical", "boolean"):
            cp.distribution = [
                {"value": str(k), "count": int(v)} for k, v in s.value_counts().head(12).items()
            ]
        if not unique:
            warnings.append(f"{col}: all values are missing.")
        elif unique == 1:
            warnings.append(f"{col}: constant among nonmissing values.")
        if kind == "categorical" and unique > 40:
            warnings.append(f"{col}: {unique:,} distinct categories; grouped charts are limited to 40.")
        if missing:
            warnings.append(
                f"{col}: {missing:,} missing values. Analyses omit only rows missing required variables."
            )
        columns.append(cp)
    missing = sum(c.missing_count for c in columns)
    return DatasetProfile(
        id=dataset_id,
        name=name,
        row_count=len(frame),
        column_count=len(columns),
        missing_count=missing,
        missing_percent=missing / frame.size * 100,
        numeric_count=sum(k == "numeric" for k in kinds.values()),
        columns=columns,
        warnings=warnings,
        synthetic=synthetic,
        expires_at=expires_at,
    )

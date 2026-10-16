"""의도 분류 데이터셋을 학습/검증/평가 데이터로 나눈다 (8:1:1, 의도 비율 유지).

사용법:
    python split_data.py
결과:
    data/train.csv, data/val.csv, data/test.csv
"""
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).resolve().parent / "data"
SOURCE = DATA_DIR / "intent_dataset.csv"
SEED = 42  # 고정해야 매번 같은 분할이 나와서 실험 비교가 가능함


def main():
    df = pd.read_csv(SOURCE, encoding="utf-8-sig", dtype=str).fillna("")
    df["text"] = df["text"].str.strip()
    df = df[df["text"] != ""].drop_duplicates(subset="text")

    # 8:1:1 분할. stratify로 세 데이터의 의도 비율을 똑같이 맞춘다
    train, rest = train_test_split(
        df, test_size=0.2, stratify=df["intent"], random_state=SEED
    )
    val, test = train_test_split(
        rest, test_size=0.5, stratify=rest["intent"], random_state=SEED
    )

    for name, part in [("train", train), ("val", val), ("test", test)]:
        part.to_csv(DATA_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")

    summary = pd.DataFrame({
        "train": train["intent"].value_counts(),
        "val": val["intent"].value_counts(),
        "test": test["intent"].value_counts(),
    })
    summary.loc["합계"] = summary.sum()
    print(summary)


if __name__ == "__main__":
    main()

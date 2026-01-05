import argparse
import json
import random
from pathlib import Path

def reduce_duplicate(examples):
    # reduce duplicate query
    seen = set()
    unique = []
    
    for i in examples:
        if i["query"] not in seen:
            seen.add(i["query"])
            unique.append(i)
    return unique


def load_examples(path: Path):
    """Load records from a JSONL file (one object per line) or a JSON array."""
    with path.open("r", encoding="utf-8") as fp:
        first_char = fp.read(1)
        if not first_char:
            return []
        fp.seek(0)
        if first_char == "[":
            data = json.load(fp)
            if not isinstance(data, list):
                raise ValueError("Expected a JSON array when file starts with '['.")
            return data
        return [json.loads(line) for line in fp if line.strip()]


def write_examples(examples, path: Path):
    """Write records as JSONL."""
    with path.open("w", encoding="utf-8") as fp:
        for item in examples:
            fp.write(json.dumps(item, ensure_ascii=False))
            fp.write("\n")


def split_data(data, val_ratio: float, seed: int):
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1.")
    rng = random.Random(seed)
    rng.shuffle(data)

    split_idx = int(len(data) * (1 - val_ratio))
    split_idx = min(max(split_idx, 1), len(data) - 1)  # ensure both splits are non-empty
    return data[:split_idx], data[split_idx:]


def main():
    parser = argparse.ArgumentParser(
        description="Split data.json into train and validation JSONL files."
    )
    parser.add_argument("--input", default="data.json", help="Input JSON/JSONL file.")
    parser.add_argument(
        "--train-output", default="lora_data_train.json", help="Train split output path."
    )
    parser.add_argument(
        "--val-output", default="lora_data_val.json", help="Validation split output path."
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Fraction of records to place in the validation split.",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducible split."
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    examples = load_examples(input_path)
    if len(examples) < 2:
        raise ValueError("Need at least two records to create a split.")
    
    filtered = reduce_duplicate(examples)
    train_records, val_records = split_data(filtered, args.val_ratio, args.seed)
    write_examples(train_records, Path(args.train_output))
    write_examples(val_records, Path(args.val_output))

    print(
        f"Wrote {len(train_records)} train records to {args.train_output} and "
        f"{len(val_records)} validation records to {args.val_output}."
    )


if __name__ == "__main__":
    main()


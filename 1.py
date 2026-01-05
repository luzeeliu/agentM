import random
import json

FILE = "data.json"
data = []
with open(FILE, "r", encoding="utf-8") as f:
    # first is to check first character
    # seek will reset file pointer to beginning
    first = f.read(1)
    if not first:
        data = []
    f.seek(0)
    # if it start with list like use load else use loads line by line
    if first == "[":
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON array when file starts with '['.")
    else:
        data = [json.loads(lines) for lines in f if lines.strip()]

# reduce duplicate
if data:
    seen = set()
    unique = []
    
    for i in data:
        if i["query"] not in seen:
            seen.add(i["query"])
            unique.append(i)

    data = unique
if len(data) > 2:
    rng = random.Random(42)
    rng.shuffle(data)
    split_idx = int(len(data) * 0.9)
    split_idx = min(max(split_idx, 1), len(data) - 1)  # ensure both splits are non-empty
    train = data[:split_idx]
    val = data[split_idx:]
    print(f"total size: {len(data)}, train size: {len(train)}, val size: {len(val)}")
    
    # save the train.json and val.json 
    with open("lora_data_train.json", "w", encoding="utf-8") as f:
        for i in train:
            f.write(json.dumps(i, ensure_ascii=False))
            f.write("\n")
    with open("lora_data_val.json", "w", encoding="utf-8") as f:
        for i in val:
            f.write(json.dumps(i, ensure_ascii=False))
            f.write("\n")
    print("run successfully")
from datasets import load_dataset

DATA_PATH = "lora_data_train.json"
VAL_DATA_PATH = "lora_data_val.json"
OUTPUT_DIR = "./results_qlora"
dataset = load_dataset("json", data_files={"train": DATA_PATH, "validation": VAL_DATA_PATH})
print("train size: ", len(dataset["train"]))
print("validation size: ", len(dataset["validation"]))
print("overlap: is ", len(set(dataset["train"]["query"]) & set(dataset["validation"]["query"])))
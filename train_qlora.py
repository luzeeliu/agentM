import subprocess
import os

result = subprocess.run('bash -c "source /etc/network_turbo && env | grep proxy"', shell=True, capture_output=True, text=True)
output = result.stdout
for line in output.splitlines():
    if '=' in line:
        var, value = line.split('=', 1)
        os.environ[var] = value

import os
import math
import inspect
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig
from data_collactor import DataCollator

# --- Configuration ---
MODEL_ID = "deepseek-ai/deepseek-coder-7b-instruct-v1.5" # Or "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
DATA_PATH = "lora_data_train.json"
VAL_DATA_PATH = "lora_data_val.json"
OUTPUT_DIR = "./results_qlora"

# QLoRA Parameters
LORA_R = 8
LORA_ALPHA = 32
LORA_DROPOUT = 0.05


def main():
    print(f"Loading model: {MODEL_ID}")
    
    # 1. Quantization Config (8-bit loading)
    # 8-bit provides better precision than 4-bit, but uses more VRAM (~10GB vs ~6GB for 7B model).
    bnb_config = BitsAndBytesConfig(
        load_in_8bit=True,
        bnb_8bit_quant_type="nf8",
        bnb_8bit_use_double_quant=True,
        bnb_8bit_compute_dtype=torch.float16
    )

    # 2. Load Model
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True
    )

    # 3. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right" # Fix for fp16 training

    # 4. Load Dataset
    dataset = load_dataset("json", data_files={"train": DATA_PATH, "validation": VAL_DATA_PATH})

    # 5. Define Masking (Crucial Step)
    # We want the model to learn ONLY the Assistant's response.
    # The DataCollator finds the "response_template" and masks everything before it.
    collator = DataCollator(tokenizer=tokenizer, max_length=1024)

    # 6. LoRA Configuration
    peft_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"] # Target attention layers
    )

    # 7. Training Arguments
    args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs= 1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=10,
        gradient_checkpointing=True,
        save_strategy="epoch",
        eval_strategy="steps",
        eval_steps=50,
        report_to="none",
        remove_unused_columns=False,
        per_device_eval_batch_size=1,
        dataset_kwargs={"skip_prepare_dataset": True},
    )

    # 8. Trainer
    trainer = SFTTrainer(
        model = model, 
        train_dataset = dataset["train"],
        eval_dataset= dataset["validation"],
        remove_unused_columns = False,
        max_seq_length = 1024,
        tokenizer = tokenizer,
        data_collator = collator,
        peft_config = peft_config,
        args = args
    )

    print("Running baseline eval before training...")
    base_metrics = trainer.evaluate()
    base_loss = base_metrics.get("eval_loss")
    if base_loss is not None:
        base_ppl = math.exp(base_loss)
        print(f"Baseline eval_loss: {base_loss:.4f} | ppl: {base_ppl:.2f}")
    else:
        print(f"Baseline eval metrics: {base_metrics}")

    print("Starting training...")
    trainer.train()
    
    print("Running eval after training...")
    final_metrics = trainer.evaluate()
    final_loss = final_metrics.get("eval_loss")
    if final_loss is not None:
        final_ppl = math.exp(final_loss)
        print(f"Final eval_loss: {final_loss:.4f} | ppl: {final_ppl:.2f}")
        if base_loss is not None:
            improvement = base_loss - final_loss
            print(f"Loss improvement: {improvement:.4f}")
    else:
        print(f"Final eval metrics: {final_metrics}")

    print("Saving model...")
    trainer.save_model(os.path.join(OUTPUT_DIR, "final_adapter"))

if __name__ == "__main__":
    main()


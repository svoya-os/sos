"""LoRA fine-tune with TRL (SFT), tracked locally with Trackio. Settings: configs/sft.toml.

Run: sos run src/{{ project.package }}/train.py   (the bar shows the progress)
"""
import tomllib
from pathlib import Path

from datasets import load_dataset
from peft import LoraConfig
from transformers import TrainerCallback
from trl import SFTConfig, SFTTrainer

from {{ project.package }}.sos_progress import report


class SosProgress(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        if state.max_steps:
            report(state.global_step / state.max_steps, f"step {state.global_step}/{state.max_steps}")


def main() -> None:
    cfg = tomllib.loads(Path("configs/sft.toml").read_text(encoding="utf-8"))
    dataset = load_dataset(cfg["dataset"], split=cfg.get("split", "train"))
    trainer = SFTTrainer(
        model=cfg["model"],
        train_dataset=dataset,
        args=SFTConfig(
            output_dir=cfg["output_dir"],
            num_train_epochs=cfg["epochs"],
            per_device_train_batch_size=cfg["batch_size"],
            gradient_accumulation_steps=cfg["grad_accum"],
            learning_rate=cfg["lr"],
            logging_steps=10,
            bf16=cfg.get("bf16", True),
            report_to=cfg.get("report_to", "trackio"),
        ),
        peft_config=LoraConfig(r=cfg["lora_r"], lora_alpha=cfg["lora_alpha"],
                               target_modules="all-linear", task_type="CAUSAL_LM"),
        callbacks=[SosProgress()],
    )
    trainer.train()
    trainer.save_model(cfg["output_dir"])
    report(1.0, "done")


if __name__ == "__main__":
    main()

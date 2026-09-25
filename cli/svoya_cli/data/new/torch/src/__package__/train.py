"""Minimal PyTorch training loop — replace the model and the data with yours.

Run: sos run src/{{ project.package }}/train.py   (the bar shows the progress)
"""
import torch
from torch import nn

from {{ project.package }}.sos_progress import report


def device() -> str:
    if torch.cuda.is_available():          # NVIDIA CUDA and AMD ROCm builds
        return "cuda"
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return "xpu"
    return "cpu"


def main() -> None:
    torch.manual_seed(42)
    dev = device()
    x = torch.randn(4096, 32)
    y = (x.sum(dim=1, keepdim=True) > 0).float()
    model = nn.Sequential(nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, 1)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    epochs, steps = 3, 200
    for epoch in range(epochs):
        for step in range(steps):
            idx = torch.randint(0, len(x), (128,))
            loss = loss_fn(model(x[idx].to(dev)), y[idx].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
            if step % 20 == 0:
                report((epoch * steps + step + 1) / (epochs * steps), f"epoch {epoch + 1}/{epochs}")
        print(f"epoch {epoch + 1}/{epochs}  loss {loss.item():.4f}  ({dev})")
    report(1.0, "done")


if __name__ == "__main__":
    main()

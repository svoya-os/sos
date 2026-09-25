# {{ project.name }}

{{ project.description }}

Created with `sos new --template {{ project.template }}` on SOS («СОС — Своя Операционная Система»).

## Run

```sh
sos run {{ run.entry }}          # environment header + progress in the bar
uv run pytest                    # tests
```

* **GPU**: `{{ gpu.detected }}` · PyTorch wheels `{{ gpu.backend }}` (from `sos doctor`, see `.env` and `pyproject.toml`).
  The project owns its CUDA/ROCm runtime; the OS only owns the driver.
* **Data & models**: `data/` → `{{ paths.datasets }}`, `models/` → `{{ paths.ai }}` (the shared store; nothing is copied).
  Pin what you use in `svoya.toml` (`[[models]]`, `[[datasets]]` with sha256).
* **Tracking**: {{ tracking.tool }} at {{ tracking.url }}.
* **Containers**: `podman build -f Containerfile .` · dev container: `.devcontainer/devcontainer.json` (GPU optional).
* **Cloud burst**: `sky launch sky.yaml` (module `cloud-burst`).

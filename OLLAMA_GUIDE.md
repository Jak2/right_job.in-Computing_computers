# Ollama & GPU Configuration Guide

This guide details the commands to run and monitor local rehearsal runs using Ollama and your NVIDIA GPU.

## 1. Quick Rehearsal Run Command
To run the agent pipeline locally with the **Qwen 2.5 (1.5B)** model (bypassing Gemini API quota limits), run the following from this folder:

```bash
REHEARSAL_MODE=ollama OLLAMA_MODEL=qwen2.5:1.5b ./comp_venv/bin/python3 leaner_cut/main.py
```

To run with the **Qwen 2.5 (3B)** model:
```bash
REHEARSAL_MODE=ollama OLLAMA_MODEL=qwen2.5:3b ./comp_venv/bin/python3 leaner_cut/main.py
```

## 2. Rehearsal Helper Script
A helper script `./run_rehearsal.sh` has been added. You can use it to run the pipeline and update the dashboard automatically:
```bash
# Run with qwen2.5:1.5b (default)
./run_rehearsal.sh

# Or specify a different model (e.g., qwen2.5:3b)
./run_rehearsal.sh qwen2.5:3b
```

## 3. Ollama Commands
* **List installed models:**
  ```bash
  ollama list
  ```
* **Verify active running models (and GPU offloading %):**
  ```bash
  ollama ps
  ```
* **Run a model interactively in terminal:**
  ```bash
  ollama run qwen2.5:1.5b
  ```

## 4. GPU/VRAM Monitoring
* **Check GPU memory usage and active CUDA processes:**
  ```bash
  nvidia-smi
  ```
* **Monitor GPU real-time (refreshing every 1 second):**
  ```bash
  watch -n 1 nvidia-smi
  ```

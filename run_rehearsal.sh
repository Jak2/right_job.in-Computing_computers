#!/bin/bash

# Default model to qwen2.5:1.5b if none specified
MODEL="${1:-qwen2.5:1.5b}"

echo "=========================================================="
echo "Starting local rehearsal run..."
echo "Model: $MODEL"
echo "Mode: Rehearsal (Ollama Local Inference)"
echo "=========================================================="

# Execute main pipeline
REHEARSAL_MODE=ollama OLLAMA_MODEL="$MODEL" ./comp_venv/bin/python3 leaner_cut/main.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================================="
    echo "Pipeline completed successfully. Generating dashboard..."
    echo "=========================================================="
    ./comp_venv/bin/python3 leaner_cut/dashboard.py
else
    echo "Pipeline execution failed. Skipping dashboard generation."
fi

from huggingface_hub import hf_hub_download
import os

print("Starting download of Gemma 3-4B GGUF model...")

# Definire il percorso di output
model_path = "models"
if not os.path.exists(model_path):
    os.makedirs(model_path)

# Download del modello
output_path = hf_hub_download(
    repo_id="unsloth/gemma-3-4b-it-GGUF",
    filename="gemma-3-4b-it-Q4_K_M.gguf",
    local_dir=model_path,
    local_dir_use_symlinks=False
)

print(f"Model downloaded successfully to: {output_path}")

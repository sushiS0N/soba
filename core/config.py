"""
Simple Configuration System using JSON
Users edit config.json - no environment variables needed!
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "build_dir": str(PROJECT_ROOT / "build"),
    "cuda_bin": "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.9/bin",
    "jobs_dir": str(PROJECT_ROOT / "jobs"),
    "server": {"host": "127.0.0.1", "port": 8000},
    "logging": {"level": "INFO"},
}


def load_config():
    """Load configuration from config.json, create if doesn't exist"""
    if not CONFIG_FILE.exists():
        # Create default config file
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Created default config at: {CONFIG_FILE}")
        print("Edit this file to customize paths!")
        return DEFAULT_CONFIG

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


# Load configuration
config = load_config()

# Export configuration values
BUILD_DIR = Path(config["build_dir"])
CUDA_BIN = Path(config["cuda_bin"])
JOBS_DIR = Path(config["jobs_dir"])
JOBS_DIR.mkdir(exist_ok=True, parents=True)

SERVER_HOST = config["server"]["host"]
SERVER_PORT = config["server"]["port"]

LOG_LEVEL = config["logging"]["level"]

# Project structure
CORE_DIR = PROJECT_ROOT / "core"
INTEGRATIONS_DIR = PROJECT_ROOT / "integrations"


def validate_config():
    """Check if configured paths exist"""
    issues = []

    if not BUILD_DIR.exists():
        issues.append(f"  Build directory not found: {BUILD_DIR}")
        issues.append(
            "   Run: cd core && mkdir build && cd build && cmake .. && cmake --build ."
        )

    if not CUDA_BIN.exists():
        issues.append(f"  CUDA directory not found: {CUDA_BIN}")
        issues.append(f"   Edit config.json to set correct CUDA path")

    if issues:
        print("=" * 60)
        print("Configuration Issues:")
        print("=" * 60)
        for issue in issues:
            print(issue)
        print("=" * 60)
        return False

    print(" Configuration is valid!")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Solar Analysis Engine - Configuration")
    print("=" * 60)
    print(f"Config file: {CONFIG_FILE}")
    print(f"Build directory: {BUILD_DIR}")
    print(f"CUDA binary: {CUDA_BIN}")
    print(f"Jobs directory: {JOBS_DIR}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    print("=" * 60)
    print()
    validate_config()

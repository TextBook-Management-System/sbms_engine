#!/usr/bin/env python3
"""
Script to create __init__.py files in all directories
"""
import os
from pathlib import Path


def create_init_files():
    """Create __init__.py files in all directories"""
    
    directories = [
        "app",
        "app/config",
        "app/api",
        "app/api/v1",
        "app/api/v1/endpoints",
        "app/models",
        "app/services",
        "app/ml_models",
        "app/utils",
        "app/core",
        "app/database",
        "app/database/migrations",
        "tests",
        "tests/integration"
    ]
    
    for directory in directories:
        init_file = Path(directory) / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            print(f"Created: {init_file}")
        else:
            print(f"Exists: {init_file}")
    
    print("\nAll __init__.py files have been created/verified!")


if __name__ == "__main__":
    create_init_files()
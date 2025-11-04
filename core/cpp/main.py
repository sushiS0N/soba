#!/usr/bin/env python3
"""
Automated Migration Script
Reorganizes flat structure into modular architecture
"""

import shutil
import os
from pathlib import Path

# File relocation mappings
FILE_MOVES = {
    # C++ Files
    "optix_solar.h": "core/cpp/optix_solar.h",
    "optix_solar.cu": "core/cpp/optix_solar.cu",
    "optix_programs.cu": "core/cpp/optix_programs.cu",
    "python_bindings.cpp": "core/cpp/python_bindings.cpp",
    "geometry.h": "core/cpp/geometry.h",
    "vec3.h": "core/cpp/vec3.h",
    "main.cpp": "core/cpp/main.cpp",
    "CMakeLists.txt": "core/CMakeLists.txt",
    # Core Python Files
    "optix_engine.py": "core/python/engine.py",
    "pipeline.py": "core/python/pipeline.py",
    "usd_io.py": "core/python/usd_io.py",
    "lb_loader.py": "core/python/weather.py",
    # Server Files
    "server.py": "core/server/server.py",
    "solar_client.py": "core/server/client.py",
    # Maya Files
    "solarUI.py": "integrations/maya/scripts/solar_ui.py",
    "usdExporter.py": "integrations/maya/scripts/usd_exporter.py",
}

# Files to keep at root (but may need updating)
ROOT_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "requirements.txt",
    "pyproject.toml",
    "config.py",
]

# Files to skip/delete
SKIP_FILES = [
    "_init_.py",  # Typo file
    "_gitignore",  # Should be .gitignore
    "__pycache__",
    "*.pyc",
]


def create_directory_structure(dest_root):
    """Create the new modular directory structure"""
    directories = [
        "core/cpp",
        "core/python",
        "core/server",
        "integrations/maya/scripts",
        "integrations/maya/ui",
        "integrations/blender",
        "integrations/rhino",
        "tests",
        "docs",
        "examples",
    ]

    for directory in directories:
        path = dest_root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_init_files(dest_root):
    """Create __init__.py files for Python packages"""
    init_files = {
        "core/__init__.py": '''"""
Solar Analysis Core Engine
Platform-agnostic ray tracing and analysis
"""

__version__ = "0.1.0"

from .python.engine import OptiXEngine
from .python.pipeline import SolarPipeline

__all__ = ['OptiXEngine', 'SolarPipeline']
''',
        "core/python/__init__.py": '''"""
Core Python Modules
Analysis engine, USD I/O, weather data processing
"""

from .engine import OptiXEngine, setup_optix_module
from .pipeline import SolarPipeline, analyze_solar_scene
from .usd_io import read_solar_usd, write_results_to_usd
from .weather import WeatherDataLoader, get_sun_vectors

__all__ = [
    'OptiXEngine', 'setup_optix_module',
    'SolarPipeline', 'analyze_solar_scene',
    'read_solar_usd', 'write_results_to_usd',
    'WeatherDataLoader', 'get_sun_vectors',
]
''',
        "core/server/__init__.py": '''"""
Solar Analysis Server
REST API for job queuing and processing
"""

from .server import app
from .client import SolarAnalysisClient

__all__ = ['app', 'SolarAnalysisClient']
''',
        "integrations/__init__.py": '''"""
DCC Integrations
Maya, Blender, Rhino support
"""
''',
        "integrations/maya/__init__.py": '''"""
Maya Integration for Solar Analysis
"""

__version__ = "0.1.0"
''',
    }

    for filepath, content in init_files.items():
        fullpath = dest_root / filepath
        fullpath.write_text(content)
        print(f"✅ Created: {filepath}")


def migrate_files(source_root, dest_root, dry_run=False):
    """Migrate files according to FILE_MOVES mapping"""
    print("\n" + "=" * 60)
    print("File Migration")
    print("=" * 60)

    for source_file, dest_file in FILE_MOVES.items():
        source_path = source_root / source_file
        dest_path = dest_root / dest_file

        if not source_path.exists():
            print(f"⚠️  Source not found: {source_file} (skipping)")
            continue

        if dry_run:
            print(f"📋 Would move: {source_file} → {dest_file}")
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            print(f"✅ Moved: {source_file} → {dest_file}")


def copy_root_files(source_root, dest_root, dry_run=False):
    """Copy files that stay at root"""
    print("\n" + "=" * 60)
    print("Root Files")
    print("=" * 60)

    for filename in ROOT_FILES:
        source_path = source_root / filename
        dest_path = dest_root / filename

        if not source_path.exists():
            print(f"⚠️  File not found: {filename} (skipping)")
            continue

        if dry_run:
            print(f"📋 Would copy: {filename}")
        else:
            shutil.copy2(source_path, dest_path)
            print(f"✅ Copied: {filename}")


def create_readme_files(dest_root):
    """Create README files for each major component"""
    readmes = {
        "core/README.md": "# Solar Analysis Core Engine\n\nCore ray tracing and analysis engine.",
        "core/server/README.md": "# Solar Analysis Server\n\nREST API for job processing.",
        "integrations/maya/README.md": "# Maya Integration\n\nMaya plugin installation and usage.",
        "docs/README.md": "# Documentation\n\nComprehensive project documentation.",
    }

    print("\n" + "=" * 60)
    print("Documentation Files")
    print("=" * 60)

    for filepath, content in readmes.items():
        fullpath = dest_root / filepath
        fullpath.write_text(content)
        print(f"✅ Created: {filepath}")


def main():
    """Main migration script"""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate to modular structure")
    parser.add_argument(
        "source", type=Path, help="Source directory (current flat structure)"
    )
    parser.add_argument(
        "dest", type=Path, help="Destination directory (new modular structure)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it",
    )

    args = parser.parse_args()

    source_root = args.source.resolve()
    dest_root = args.dest.resolve()

    if not source_root.exists():
        print(f"❌ Source directory does not exist: {source_root}")
        return 1

    if dest_root.exists() and not args.dry_run:
        response = input(f"⚠️  Destination exists: {dest_root}\nOverwrite? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Aborted")
            return 1

    print("=" * 60)
    print("Solar Analysis Engine - Migration to Modular Structure")
    print("=" * 60)
    print(f"Source: {source_root}")
    print(f"Destination: {dest_root}")
    print(f"Dry Run: {args.dry_run}")
    print("=" * 60)
    print()

    if not args.dry_run:
        # Create structure
        create_directory_structure(dest_root)
        create_init_files(dest_root)
        create_readme_files(dest_root)

    # Migrate files
    migrate_files(source_root, dest_root, args.dry_run)
    copy_root_files(source_root, dest_root, args.dry_run)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    if args.dry_run:
        print("✅ Dry run complete - no files were moved")
        print("\nTo perform the actual migration, run without --dry-run:")
        print(f"    python migrate.py {source_root} {dest_root}")
    else:
        print("✅ Migration complete!")
        print("\nNext steps:")
        print("1. Update import statements in Python files")
        print("2. Update CMakeLists.txt with new paths")
        print("3. Update config.py for modular structure")
        print("4. Test build: cd core && mkdir build && cmake .. && cmake --build .")
        print("5. Test imports: python -c 'from core.python import engine'")
        print("\nSee MIGRATION_GUIDE.md for detailed instructions.")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

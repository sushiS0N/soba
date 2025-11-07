# SOBA

SOBA - Solar Analysis Engine
A GPU-accelerated solar analysis system for architectural design workflows, built with NVIDIA OptiX and OpenUSD.
Overview
SOBA is a modular, server-based daylight analysis tool designed for architectural visualization pipelines. It provides fast, accurate solar exposure calculations using GPU ray tracing, with seamless integration into Maya, Rhino, and NVIDIA Omniverse through OpenUSD.

Key Features:
- GPU-Accelerated: NVIDIA OptiX ray tracing for high-performance analysis
- Server-Based Architecture: Centralized processing with job queue management
- Non-Blocking Workflow: Maya remains responsive during analysis
- OpenUSD Integration: Cross-platform compatibility and future-proof data format
- Visualization: Built-in Ecotect-style color mapping for results
- Production-Ready: Designed for fast-paced architectural production environments

System Architecture: Maya UI  <──USD──>  FastAPI <──USD──>  OptiX    

The system consists of three main components:

1. **Maya Plugin** (`solarUI.py`): User interface and USD export
2. **FastAPI Server** (`server.py`): Job management and queue processing
3. **OptiX Engine** (`optix_engine.py`): GPU-accelerated ray tracing

## Requirements

### Software
- **Maya 2025** (or compatible version with USD support)
- **Python 3.11+**
- **CUDA Toolkit 12.9**
- **NVIDIA OptiX SDK 9.0.0**
- **CMake 3.18+**
- **Ninja 1.13**
- **Visual Studio 2019/2022** (Windows) or compatible C++ compiler

### Hardware
NVIDIA GPU with compute capability 7.5+ (RTX series recommended - build flags can be adjusted for your specific sm architecture)

#### Installation
1. Clone Repository
```
bashgit clone https://github.com/sushiS0N/soba.git
cd soba
```
2. Set Up Python Environment
```
conda create -n solar python=3.11 
conda activate solar
pip install -r requirements.txt
```
3. Build OptiX Engine
Configure paths in CMakeLists.txt:
cmakeset(Python_EXECUTABLE "path/to/your/python.exe")
set(OptiX_INSTALL_DIR "C:/ProgramData/NVIDIA Corporation/OptiX SDK 9.0.0")
Build:
```
bashmkdir build
cmake --preset=solar
cmake --build build

This generates:
- solar_engine_optix.cp311-win_amd64.pyd (Python module)
- optix_programs.ptx (OptiX kernels)
```
4. Install Maya Plugin
Copy the following to your Maya scripts directory (e.g., Documents/maya/2025/scripts/SolarAnalysis/):
```
solarUI.py
usdExporter.py
solar_client.py
SolarUI.ui

In Maya Script Editor:
pythonimport sys
sys.path.append("path/to/soba")
import solarUI
```

#### Usage
1. Start the Server
bashpython server.py
Server runs on http://localhost:8000. Access API docs at http://localhost:8000/docs.

2. Run Analysis in Maya
Load the UI:
```
Select Weather File:
    Click "Load EPW" and choose your .epw weather file
    Set analysis parameters (date range, time range, timestep, offset)


Select Geometry:
    Select target meshes (buildings to analyze) → Click "Set Target"
    Select context meshes (surrounding geometry) → Click "Set Context"


Run Analysis:
    Click "Run Analysis"
    Maya remains responsive while server processes
    Results automatically import when complete


View Results:
    Colors show sun exposure hours (blue = low, yellow = high)

    Results saved as:
        - {usd_path}_results.usda (colored geometry)
        - {usd_path}_results.csv (numeric data)
```


3. Standalone Pipeline (Python)
```
pythonfrom pipeline import analyze_solar_scene

# Run analysis on existing USD file
usd_path = "path/to/scene.usda"
result_path = analyze_solar_scene(usd_path)
```

## File Structure
```
soba/
├── solarUI.py              # Maya UI and client
├── solar_client.py         # Server communication
├── usdExporter.py          # Maya → USD export
├── server.py               # FastAPI job server
├── pipeline.py             # Complete analysis pipeline
├── optix_engine.py         # OptiX initialization & execution
├── usd_io.py               # USD read/write utilities
├── lb_loader.py            # Ladybug weather data
├── optix_solar.cu          # CUDA/OptiX ray tracing kernel
├── python_bindings.cpp     # Pybind11 interface
├── CMakeLists.txt          # Build configuration
└── geometry.h, vec3.h      # Math utilities
```

## USD File Format

SOBA uses OpenUSD with custom metadata for solar analysis:
```
Root (Xform)
├── TargetMesh              # Geometry to analyze
│   ├── vertices
│   ├── face_centers        # Primvar
│   ├── face_normals        # Primvar
│   └── displayColor        # Results (after analysis)
├── ContextGeometry         # Scene context (combined & triangulated)
└── Metadata
    ├── solar:params        # "month_start,month_end,day_start,..."
    ├── solar:epwFile       # Weather file path
    ├── solar:sunHours      # Analysis results (after analysis)
    └── solar:colormap      # "ecotect" (after analysis)
Configuration
Server Settings (server.py)
pythonJOBS_DIR = Path("path/to/job/storage")
HOST = "127.0.0.1"
PORT = 8000
```

### Analysis Parameters
- **Date Range**: Month/day start and end
- **Time Range**: Hour start and end (0-23)
- **Timestep**: Hours between samples (1 = hourly)
- **Ray Offset**: Distance to offset rays from surface (default: 0.1)

Debug Mode
Enable verbose logging:
python# In pipeline.py
import logging
logging.basicConfig(level=logging.DEBUG)

Roadmap

 Rhino plugin
 Omniverse extension
 Web-based UI for server
 Multiple analysis types (radiation, view analysis)
 Results database and historical comparison
 Batch processing for multiple buildings
 Cloud deployment support

License - MIT

NVIDIA OptiX for GPU ray tracing
Pixar OpenUSD for universal scene description
Ladybug Tools for solar calculation utilities
Christoph Geiger for architectural vision and USD integration support
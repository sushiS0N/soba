
SOBA - Solar Analysis Engine
A GPU-accelerated solar analysis system for architectural design workflows, built with NVIDIA OptiX and OpenUSD.
Overview
SOBA is a modular, server-based daylight analysis tool designed for architectural visualization pipelines. It provides fast, accurate solar exposure calculations using GPU ray tracing, with seamless integration into Maya, Rhino, and NVIDIA Omniverse through OpenUSD.
Key Features

GPU-Accelerated: NVIDIA OptiX ray tracing for high-performance analysis
Server-Based Architecture: Centralized processing with job queue management
Non-Blocking Workflow: Maya remains responsive during analysis
OpenUSD Integration: Cross-platform compatibility and future-proof data format
Visualization: Built-in Ecotect-style color mapping for results
Production-Ready: Designed for fast-paced architectural production environments

System Architecture
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Maya UI   │ ──USD──>│ FastAPI      │ ──USD──>│   OptiX     │
│  (Client)   │ <──USD──│   Server     │ <──USD──│   Engine    │
└─────────────┘         └──────────────┘         └─────────────┘
                              │
                         Job Queue
                         Management
```

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
- **Visual Studio 2019/2022** (Windows) or compatible C++ compiler

### Hardware
- NVIDIA GPU with compute capability 7.5+ (RTX series recommended)
- 8GB+ GPU memory recommended for large scenes

### Python Dependencies
```
pxr (OpenUSD)
numpy
ladybug-core
fastapi
uvicorn
httpx
pybind11
maya-standalone (for Maya integration)
PySide6
Installation
1. Clone Repository
bashgit clone https://github.com/sushiS0N/soba.git
cd soba
2. Set Up Python Environment
bashconda create -n solar python=3.11
conda activate solar
pip install -r requirements.txt
3. Build OptiX Engine
Configure paths in CMakeLists.txt:
cmakeset(Python_EXECUTABLE "path/to/your/python.exe")
set(OptiX_INSTALL_DIR "C:/ProgramData/NVIDIA Corporation/OptiX SDK 9.0.0")
Build:
bashmkdir build
cd build
cmake ..
cmake --build . --config Release
This generates:

solar_engine_optix.pyd (Python module)
optix_programs.ptx (OptiX kernels)

4. Install Maya Plugin
Copy the following to your Maya scripts directory (e.g., Documents/maya/2025/scripts/SolarAnalysis/):

solarUI.py
usdExporter.py
solar_client.py
SolarUI.ui

In Maya Script Editor:
pythonimport sys
sys.path.append("path/to/soba")
import solarUI
Usage
1. Start the Server
bashpython server.py
Server runs on http://localhost:8000. Access API docs at http://localhost:8000/docs.
2. Run Analysis in Maya

Load the UI:

python   import solarUI

Select Weather File:

Click "Load EPW" and choose your .epw weather file
Set analysis parameters (date range, time range, timestep)


Select Geometry:

Select target meshes (buildings to analyze) → Click "Set Target"
Select context meshes (surrounding geometry) → Click "Set Context"


Run Analysis:

Click "Run Analysis"
Maya remains responsive while server processes
Results automatically import when complete


View Results:

Press 6 in viewport for textured display
Colors show sun exposure hours (blue = low, yellow = high)



3. Standalone Pipeline (Python)
pythonfrom pipeline import analyze_solar_scene

# Run analysis on existing USD file
usd_path = "path/to/scene.usda"
result_path = analyze_solar_scene(usd_path)

# Results saved as:
# - {usd_path}_results.usda (colored geometry)
# - {usd_path}_results.csv (numeric data)
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

### Color Mapping (`usd_io.py`)
Available colormaps:
- `ecotect` (default): Blue → Purple → Red → Orange → Yellow
- `viridis`: Blue → Green → Yellow
- `plasma`: Purple → Orange → Yellow
- `hot`: Black → Red → Yellow → White
- `cool`: Blue → White → Red

## API Reference

### Server Endpoints

**Submit Job**
```
POST /submit
Files: usd_file, epw_file
Returns: {job_id, status}
```

**Check Status**
```
GET /status/{job_id}
Returns: {job_id, status, timestamps}
```

**Download Results**
```
GET /result/{job_id}
Returns: USD file with analysis results
```

**Server Health**
```
GET /
Returns: {status, jobs: {total, queued, processing, complete, error}}
Python API
python# Direct analysis (no server)
from optix_engine import setup_optix_module, run_optix_analysis
from usd_io import read_solar_usd

optix = setup_optix_module()
scene_data = read_solar_usd("scene.usda")
results = run_optix_analysis(scene_data, optix)
Troubleshooting
Common Issues
"CUDA runtime DLL not found"

Ensure CUDA 12.9 bin directory is in PATH
Verify cudart64_12.dll exists in CUDA installation

"OptiX initialization failed"

Update NVIDIA drivers to latest version
Verify OptiX SDK 9.0.0 is installed
Check GPU compute capability ≥ 7.5

"Server not responding" in Maya

Verify server is running: http://localhost:8000
Check firewall settings
Try: curl http://localhost:8000

Maya freezes during analysis

Ensure you're using solar_client.py (non-blocking)
Check for errors in Script Editor
Verify httpx is installed

Invalid results (all zeros)

Check sun vectors: ensure EPW file is valid
Verify geometry normals are correct
Increase ray offset if geometry is very small

Debug Mode
Enable verbose logging:
python# In pipeline.py
import logging
logging.basicConfig(level=logging.DEBUG)
Performance
Typical performance on RTX 3080:

100,000 faces × 4,000 sun vectors: ~2-5 seconds
Scene triangulation: ~1 second
USD I/O: ~0.5 seconds

Performance scales with:

Number of analysis faces
Number of sun vectors (date/time range)
Scene complexity (context geometry triangle count)

Roadmap

 Rhino plugin
 Omniverse extension
 Web-based UI for server
 Multiple analysis types (radiation, view analysis)
 Results database and historical comparison
 Batch processing for multiple buildings
 Cloud deployment support

Contributing
Contributions welcome! Please:

Fork the repository
Create a feature branch
Submit a pull request with clear description

License
[Specify your license here - e.g., MIT, Apache 2.0]
Acknowledgments

NVIDIA OptiX for GPU ray tracing
Pixar OpenUSD for universal scene description
Ladybug Tools for solar calculation utilities
Christoph Geiger for architectural vision and USD integration support


# SOBA

SOBA - GPU-Accelerated Solar Analysis Engine
A GPU-accelerated solar analysis system for architectural design workflows, built with NVIDIA OptiX and OpenUSD.
Overview
SOBA is a modular, server-based daylight analysis system designed to replace CPU workflows in high-throughput architectural pipelines. It leverages NVIDIA OptiX for hardware-accelerated ray tracing and OpenUSD for robust, cross-platform geometry interchange.

Key Features:
- GPU-Accelerated: NVIDIA OptiX ray tracing for high-performance analysis
- Server-Based Architecture: Centralized processing with job queue management
- Non-Blocking Workflow: Maya remains responsive during analysis
- OpenUSD Integration: Cross-platform compatibility and future-proof data format
- Visualization: Built-in Ecotect-style color mapping for results
- Production-Ready: Designed for fast-paced architectural production environments

## System Architecture: Maya UI  <──USD──>  FastAPI <──USD──>  OptiX    
The system decouples the heavy compute capability from the DCC (Digital Content Creation) viewport using a microservices architecture. This prevents the "frozen UI" problem common in single-threaded analysis tools and resolves critical OpenGL/CUDA context conflicts.
![DiagramHQ_invert](https://github.com/user-attachments/assets/c3f2f998-7512-4799-80d7-cc83a9388d65)

## Data Flow Pipeline
1. **Client (Maya/Rhino)**: The Python client extracts geometry and analysis parameters (EPW weather data, date/time ranges).

2. **Serialization (OpenUSD)**: Data is composed into a USD stage. Mesh data is flattened, and analysis parameters are injected as custom stage metadata.

3. **Transport (FastAPI)**: The USD payload is sent asynchronously to the analysis server.

4. **Compute (C++/OptiX)**:

- The server deserializes the USD stage.

- Geometry is uploaded to the GPU

- Custom OptiX kernels perform ray-traced solar exposure calculations.

5. **Result**: Results are written back into the USD file as displayColor primvars and returned to the client for immediate visualization.

The system consists of three main components:
1. **Maya Plugin** (`solarUI.py`): User interface and USD export
2. **FastAPI Server** (`server.py`): Job management and queue processing
3. **OptiX Engine** (`optix_engine.py`): GPU-accelerated ray tracing

## Technical Evolution and Challenges

SOBA's architecture evolved through three major iterations, each solving specific production bottlenecks:

### V1: Standalone C++ Engine
- **Implementation**: a standalone console application using Möller–Trumbore's algorithm
- **Bottleneck**: execution time was prohibitive for fast design iterations - Big O(rays * primitives). Lacked integration with DCC

### V2: Maya-Integrated CUDA
- **Implementation**: refactored the engine to use CUDA and integrated Teo Karra’s GPU BVH directly into the Maya process - average Big O(logM)
- **The critical failure**: while performance improved, integrating the CUDA context directly into Maya's process caused instability. Specifically, OptiX context creation clashed with Maya's internal OpenGL viewport context, leading to driver timeouts and crashes even when threaded
  
### V3: Server-Based Architecture (Current)
- **Implementation**: I separated the rendering engine into an independent process managed by a FastAPI server. This allowed OptiX to work as a standalone engine avoiding conflicts with future DCC's integrations.
- **Non-blocking workflow**: Maya remains responsive during analysis
- **Centralized processing**: Multiple designers can queue jobs without local GPU requirements
- **Data persistence**: Results stored in database for training ML models and performance benchmarking
- **Scalability**: Can distribute compute across multiple GPU servers and easily add other analysis algorithms

### Key Technical Decisions

**Why OptiX over vanilla CUDA?**
While a custom CUDA kernel offers control, maintaining a high-performance Bounding Volume Hierarchy (BVH) is non-trivial. SOBA utilizes OptiX to leverage:
-**Hardware Acceleration**: direct utilization of RT (Ray Tracing) cores on RTX architecture.
-**Optimized Traversal**: OptiX provides state-of-the-art BVH construction and traversal algorithms out-of-the-box, significantly outperforming my initial custom CUDA BVH implementation for scenes with millions of triangles. Stack allocation in OptiX is driven by the ray recursion depth compared to the manual one in CUDA.

**Why OpenUSD?**
USD is becoming the industry standard for cross-platform geometry exchange (Blender, Omniverse, Houdini, Katana). By committing to USD, SOBA can integrate with multiple DCCs without custom exporters for each. The learning curve was steep, but the interoperability payoff is significant. I could inject the analysis parameters (solar:sunHours, solar:epwFile) directly into the stage metadata without breaking the geometry schema or sending multiple files

**Why Server-Based?**
FastAPI provides job queue management, automatic API documentation, and async request handling with minimal code. Beyond solving the context crash, the server architecture allows for Scalability. The compute engine can be deployed headless, allowing designers on lightweight laptops to request heavy solar analysis jobs via the REST API.

## Requirements

### Stack
- **Maya 2025** (or compatible version with USD support)
- **Python 3.11**
- **C++17**
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

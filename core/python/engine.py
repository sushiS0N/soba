"""
Complete solar analysis pipeline: USD -> OptiX -> Results
"""

import numpy as np
import os
import sys
from pathlib import Path
import importlib.util
import ctypes
import time

from pxr import Usd, UsdGeom, Sdf, Gf

# Add parent directories to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import weather as lb
import config

def setup_optix_module():
    """
    One-time setup to load OptiX module with all dependencies
    Returns the loaded module
    """
    # Paths 
    BUILD_DIR = str(config.BUILD_DIR)
    CUDA_BIN = str(config.CUDA_BIN)

    # Add CUDA to PATH
    os.environ["PATH"] = CUDA_BIN + os.pathsep + os.environ.get("PATH", "")

    # Load CUDA DLL explicitly
    cuda_dlls = ["cudart64_12.dll", "cudart64_129.dll"]
    cuda_loaded = False
    for dll_name in cuda_dlls:
        dll_path = os.path.join(CUDA_BIN, dll_name)
        if os.path.exists(dll_path):
            try:
                ctypes.CDLL(dll_path)
                print(f" Loaded CUDA: {dll_name}")
                cuda_loaded = True
                break
            except Exception as e:
                print(f"  Failed to load {dll_name}: {e}")

    if not cuda_loaded:
        raise RuntimeError("Failed to load CUDA runtime DLL")

    
    # # Add build directory to path
    # if BUILD_DIR not in sys.path:
    #     sys.path.insert(0, BUILD_DIR)
    # print(f"sys.path[0]: {sys.path[0]}")

    # # Change to build directory (for PTX file)
    # original_cwd = os.getcwd()
    # os.chdir(BUILD_DIR)

    # Find the .pyd file
    pyd_files = list(Path(BUILD_DIR).glob("solar_engine_optix*.pyd"))
    if not pyd_files:
        raise FileNotFoundError(f"solar_engine_optix.pyd not found in {BUILD_DIR}")
    
    pyd_path = pyd_files[0]

    # Change to build directory (for PTX file)
    original_cwd = os.getcwd()
    os.chdir(BUILD_DIR)

    # Import module
    try:
        # Load module directly without modifying sys.path
        spec = importlib.util.spec_from_file_location("solar_engine_optix", pyd_path)
        solar_engine_optix = importlib.util.module_from_spec(spec)
        
        # Register in sys.modules so subsequent imports work
        sys.modules["solar_engine_optix"] = solar_engine_optix
        
        # Execute the module
        spec.loader.exec_module(solar_engine_optix)
        
        print(f"✓ Loaded solar_engine_optix v{solar_engine_optix.__version__}")
        return solar_engine_optix
    
    except ImportError as e:
        print(f" Failed to import solar_engine_optix: {e}")
        raise
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def run_optix_analysis(scene_data, optix_module):
    """
    Run OptiX analysis on USD scene data

    Args:
        scene_data: Dict from read_solar_usd() containing target, context, params
        optix_module: Loaded solar_engine_optix module

    Returns:
        numpy array of sun hours per face
    """

    # Extract data
    face_centers = scene_data["target"]["face_centers"]
    face_normals = scene_data["target"]["face_normals"]
    scene_triangles = scene_data["context"]
    params = scene_data["lb_params"]

    # Generate sun vectors
    print("Generating sun vectors...")
    epw_path = scene_data["epw_file"]
    if not os.path.exists(epw_path):
        raise ValueError("Missing or invalid epw file path")

    sun_vectors = lb.get_sun_vectors(
        epw_path,
        params["month_start"],
        params["month_end"],
        params["day_start"],
        params["day_end"],
        params["hour_start"],
        params["hour_end"],
        params["timestep"],
    )

    # Convert sun vectors to numpy array
    sun_vectors = np.array([(v.x, v.y, v.z) for v in sun_vectors], dtype=np.float32)

    # Validate inputs
    print("\n=== Analysis Input ===")
    print(f"  Face centers: {face_centers.shape}")
    print(f"  Face normals: {face_normals.shape}")
    print(f"  Scene triangles: {scene_triangles.shape}")
    print(f"  Sun vectors: {sun_vectors.shape}")
    print(f"  Ray offset: {params['offset']}")

    # Data validation
    if np.isnan(face_centers).any() or np.isinf(face_centers).any():
        raise ValueError("Invalid face_centers: contains NaN or Inf")
    if np.isnan(face_normals).any() or np.isinf(face_normals).any():
        raise ValueError("Invalid face_normals: contains NaN or Inf")
    if np.isnan(scene_triangles).any() or np.isinf(scene_triangles).any():
        raise ValueError("Invalid scene_triangles: contains NaN or Inf")
    if np.isnan(sun_vectors).any() or np.isinf(sun_vectors).any():
        raise ValueError("Invalid sun_vectors: contains NaN or Inf")

    # Run analysis
    print("\n Running OptiX analysis...")
    start_time = time.time()

    results = optix_module.analyze(
        face_centers,
        face_normals,
        scene_triangles,
        sun_vectors,
        float(params["offset"]),
    )

    elapsed = time.time() - start_time

    print(f"\n Analysis complete in {elapsed:.3f}s")
    print(f"   Total sun hours: {results.sum():.1f}")
    print(f"   Average per face: {results.mean():.1f}")
    print(f"   Max sun hours: {results.max():.1f}")
    print(f"   Faces with sun: {np.count_nonzero(results)}/{len(results)}")

    return results


if __name__ == "__main__":
    
    optix_module = setup_optix_module()
    print(optix_module)
    #results = run_optix_analysis(usd_path, optix_module)

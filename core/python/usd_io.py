from pxr import Usd, UsdGeom, Sdf, Gf
import os
import shutil
import csv
import numpy as np

import weather as lb


def parse_solar_params(params_str):
    """Parse comma separated solar analysis params string"""
    params = params_str.split(",")
    return {
        "month_start": int(params[0]),
        "month_end": int(params[1]),
        "day_start": int(params[2]),
        "day_end": int(params[3]),
        "hour_start": int(params[4]),
        "hour_end": int(params[5]),
        "timestep": int(params[6]),
        "offset": float(params[7]),
    }


def read_target_mesh(stage):
    """Extract target mesh face centers and normals as np arrays"""
    target_prim = stage.GetPrimAtPath("/Root/TargetMesh")
    mesh = UsdGeom.Mesh(target_prim)

    primvars = UsdGeom.PrimvarsAPI(mesh)
    centers = primvars.GetPrimvar("face_centers").Get()
    normals = primvars.GetPrimvar("face_normals").Get()

    return {
        "face_centers": np.array([(p[0], p[1], p[2]) for p in centers]),
        "face_normals": np.array([(v[0], v[1], v[2]) for v in normals]),
    }


def read_context_mesh(stage):
    """Extract context mesh and convert to triangle array"""
    context_prim = stage.GetPrimAtPath("/Root/ContextGeometry/Combined")
    mesh = UsdGeom.Mesh(context_prim)

    points = mesh.GetPointsAttr().Get()
    face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
    face_indices = mesh.GetFaceVertexIndicesAttr().Get()

    # Convert points to numpy
    vertices = np.array([(p[0], p[1], p[2]) for p in points], dtype=np.float32)

    # Build triangles array
    triangles = []
    idx = 0

    for count in face_vertex_counts:
        # Should all be 3 (triangulated), but check just in case
        if count != 3:
            raise RuntimeError(f"Expected triangles, found face with {count} vertices")

        # Get the 3 vertex indices
        i0 = face_indices[idx]
        i1 = face_indices[idx + 1]
        i2 = face_indices[idx + 2]

        # Get actual vertex coordinates
        v0 = vertices[i0]
        v1 = vertices[i1]
        v2 = vertices[i2]

        # Store as [v0, v1, v2]
        triangles.append([v0, v1, v2])

        idx += 3

    # Convert to numpy array: shape (num_triangles, 3, 3)
    return np.array(triangles, dtype=np.float32)


def read_solar_usd(usd_path):
    """Read solar analysis USD and extract parameters"""
    stage = Usd.Stage.Open(usd_path)
    root = stage.GetDefaultPrim()

    params_str = root.GetCustomDataByKey("solar:params")
    params = parse_solar_params(params_str)
    epw_file = root.GetCustomDataByKey("solar:epwFile")

    target_data = read_target_mesh(stage)
    context_data = read_context_mesh(stage)

    return {
        "lb_params": params,
        "epw_file": epw_file,
        "target": target_data,
        "context": context_data,
    }


def ecotect_color(normalized_value):
    """
    Convert normalized value (0-1) to Ecotect colorset 3
    Blue (min) → Purple → Red → Orange → Yellow (max)
    """
    ecotect_colors = [
        (0 / 255, 0 / 255, 255 / 255),  # Blue (minimum)
        (53 / 255, 0 / 255, 202 / 255),  # Blue-purple
        (107 / 255, 0 / 255, 148 / 255),  # Purple
        (160 / 255, 0 / 255, 95 / 255),  # Purple-red
        (214 / 255, 0 / 255, 41 / 255),  # Red-purple
        (255 / 255, 12 / 255, 0 / 255),  # Red
        (255 / 255, 66 / 255, 0 / 255),  # Red-orange
        (255 / 255, 119 / 255, 0 / 255),  # Orange
        (255 / 255, 173 / 255, 0 / 255),  # Orange-yellow
        (255 / 255, 226 / 255, 0 / 255),  # Light yellow
        (255 / 255, 255 / 255, 0 / 255),  # Yellow (maximum)
    ]

    val = max(0.0, min(1.0, normalized_value))

    if val <= 0.0:
        return ecotect_colors[0]
    if val >= 1.0:
        return ecotect_colors[-1]

    # Find segment and interpolate
    num_segments = len(ecotect_colors) - 1
    segment = val * num_segments
    segment_index = int(segment)

    if segment_index >= num_segments:
        return ecotect_colors[-1]

    t = segment - segment_index
    color1 = ecotect_colors[segment_index]
    color2 = ecotect_colors[segment_index + 1]

    r = color1[0] + t * (color2[0] - color1[0])
    g = color1[1] + t * (color2[1] - color1[1])
    b = color1[2] + t * (color2[2] - color1[2])

    return (r, g, b)


def results_to_colors(results, colormap="ecotect"):
    """
    Convert sun hours to RGB colors using a colormap

    Args:
        results: numpy array of sun hours per face
        colormap: 'ecotect' (default), 'viridis', 'plasma', 'hot', 'cool', or 'custom'

    Returns:
        numpy array of shape (N, 3) with RGB colors (0-1 range)
    """
    # Normalize results to 0-1 range
    if results.max() > results.min():
        normalized = (results - results.min()) / (results.max() - results.min())
    else:
        normalized = np.ones_like(results) * 0.5

    colors = np.zeros((len(results), 3), dtype=np.float32)

    if colormap == "ecotect":
        # Use Ecotect colorset 3
        for i, val in enumerate(normalized):
            colors[i] = ecotect_color(val)

    elif colormap == "viridis":
        # Blue → Green → Yellow (low to high sun)
        colors[:, 0] = normalized  # Red
        colors[:, 1] = np.sqrt(normalized)  # Green
        colors[:, 2] = 1.0 - normalized  # Blue

    elif colormap == "plasma":
        # Purple → Orange → Yellow
        colors[:, 0] = normalized  # Red increases
        colors[:, 1] = normalized**2  # Green increases slower
        colors[:, 2] = 1.0 - normalized  # Blue decreases

    elif colormap == "hot":
        # Black → Red → Yellow → White
        colors[:, 0] = np.minimum(1.0, normalized * 3)
        colors[:, 1] = np.maximum(0.0, (normalized - 0.33) * 3)
        colors[:, 2] = np.maximum(0.0, (normalized - 0.66) * 3)

    elif colormap == "cool":
        # Blue → White → Red
        colors[:, 0] = normalized  # Red increases
        colors[:, 1] = 1.0 - np.abs(normalized - 0.5) * 2  # White in middle
        colors[:, 2] = 1.0 - normalized  # Blue decreases

    else:  # 'custom' or default
        # Simple blue (low) to red (high)
        colors[:, 0] = normalized  # Red
        colors[:, 1] = 0.0
        colors[:, 2] = 1.0 - normalized  # Blue

    return colors


def write_results_to_usd(
    input_usd_path, results, output_usd_path=None, colormap="ecotect"
):
    """
    Write analysis results to USD file

    Args:
        input_usd_path: Path to original USD file
        results: numpy array of sun hours per face
        output_usd_path: Output path (defaults to input_results.usda)
        colormap: Color mapping scheme
    """
    if output_usd_path is None:
        base = os.path.splitext(input_usd_path)[0]
        output_usd_path = f"{base}_results.usda"

    print(f"\nWriting results to USD...")
    print(f"  Input: {input_usd_path}")
    print(f"  Output: {output_usd_path}")

    # Copy the input USD to output
    shutil.copy2(input_usd_path, output_usd_path)

    # Open the copied USD for editing
    stage = Usd.Stage.Open(output_usd_path)

    # 1. Remove context geometry
    context_prim = stage.GetPrimAtPath("/Root/ContextGeometry")
    if context_prim:
        stage.RemovePrim("/Root/ContextGeometry")
        print(f"  ✅ Removed context geometry")

    # 2. Get target mesh
    target_prim = stage.GetPrimAtPath("/Root/TargetMesh")
    if not target_prim:
        raise RuntimeError("Target mesh not found at /Root/TargetMesh")

    mesh = UsdGeom.Mesh(target_prim)
    primvars_api = UsdGeom.PrimvarsAPI(mesh)

    # 3. Add sun hours as primvar
    sun_hours_primvar = primvars_api.CreatePrimvar(
        "solar:sunHours",
        Sdf.ValueTypeNames.FloatArray,
        UsdGeom.Tokens.uniform,  # One value per face
    )
    sun_hours_primvar.Set(results.tolist())
    print(f"  ✅ Added solar:sunHours primvar")

    # 4. Convert results to colors
    colors = results_to_colors(results, colormap)

    # 5. Add display colors as uniform primvar (one per face)
    display_color_primvar = primvars_api.CreatePrimvar(
        "displayColor",
        Sdf.ValueTypeNames.Color3fArray,
        UsdGeom.Tokens.uniform,  # One color per face
    )

    # Convert to Gf.Vec3f for USD
    usd_colors = [Gf.Vec3f(float(c[0]), float(c[1]), float(c[2])) for c in colors]
    display_color_primvar.Set(usd_colors)
    print(f"  ✅ Added displayColor primvar ({colormap} colormap)")

    # 6. Add metadata about the analysis
    root = stage.GetDefaultPrim()
    root.SetCustomDataByKey("solar:resultsMin", float(results.min()))
    root.SetCustomDataByKey("solar:resultsMax", float(results.max()))
    root.SetCustomDataByKey("solar:resultsMean", float(results.mean()))
    root.SetCustomDataByKey("solar:resultsTotal", float(results.sum()))
    root.SetCustomDataByKey("solar:colormap", colormap)
    print(f"  ✅ Added result statistics to metadata")

    # 7. Save the stage
    stage.Save()

    print(f"\n✅ Results written successfully!")
    print(f"   Min sun hours: {results.min():.1f}")
    print(f"   Max sun hours: {results.max():.1f}")
    print(f"   Average: {results.mean():.1f}")
    print(f"   Total: {results.sum():.1f}")

    return output_usd_path


def write_results_csv(csv_path, results):
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        # Write a header for clarity
        # writer.writerow(["FaceIndex", "SunHours"])
        # Write each value with its index (assuming one sun hour value per face)
        for i, hours in enumerate(results):
            writer.writerow([hours])


if __name__ == "__main__":
    usd_path = r"C:/Users/wTxT/Documents/maya/2025/scripts/SolarAnalysis\temp\solar_analysis.usda"

    readUSD = read_solar_usd(usd_path)
    print(readUSD)

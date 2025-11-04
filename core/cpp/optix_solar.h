#pragma once
#include <optix.h>
#include <cuda_runtime.h>
#include <vector>
#include "geometry.h" // For point3, vec3, Triangle types

// Triangle_GPU
struct Triangle_GPU
{
    float3 v0, v1, v2;
    Triangle_GPU() = default;
    Triangle_GPU(float3 a, float3 b, float3 c) : v0(a), v1(b), v2(c) {}
};

// Launch parameters that get passed to device
struct LaunchParams
{
    float3 *face_centroids;
    float3 *face_normals;
    float3 *sun_directions;
    float *results;
    int face_count;
    int sun_count;
    OptixTraversableHandle gas_handle;
    float ray_offset;
};

// OptiX state container
struct OptiXSolar
{
    OptixDeviceContext context = nullptr;
    OptixTraversableHandle gas_handle = 0;
    OptixPipeline pipeline = nullptr;
    OptixShaderBindingTable sbt = {};
    CUdeviceptr d_params = 0;
    CUdeviceptr d_gas_buffer = 0; // Keep reference to free later
};

// Simple interface functions
bool init_optix(OptiXSolar &optix, const std::vector<Triangle_GPU> &triangles);
void launch_solar_rays(OptiXSolar &optix, float3 *centroids, float3 *normals,
                       float3 *suns, float *results, int face_count, int sun_count);
void cleanup_optix(OptiXSolar &optix);

// Main wrapper function
void gpu_solar_analysis_series_optix(
    const std::vector<point3> &face_centroids,
    const std::vector<vec3> &face_normals,
    const std::vector<Triangle> &scene_tris,
    const std::vector<vec3> &sun_directions,
    std::vector<float> &results,
    float ray_offset);

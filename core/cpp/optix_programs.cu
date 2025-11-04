// ===== optix_programs.cu =====
#include <optix.h>
#include <cuda_runtime.h>

// Launch parameters - must match host side exactly
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

// OptiX: constant memory for launch params
extern "C"
{
    __constant__ LaunchParams params;
}

// Raygen program - your main solar analysis logic
extern "C" __global__ void __raygen__solar()
{
    // Get thread index
    const uint3 idx = optixGetLaunchIndex();
    const int ray_idx = idx.x;

    // Decode which face and sun direction
    const int face_idx = ray_idx / params.sun_count;
    const int sun_idx = ray_idx % params.sun_count;

    // Verify face id & sun id integrity
    if (face_idx >= params.face_count)
    {
        printf("ERROR: face_idx %d >= face_count %d\n", face_idx, params.face_count);
        return;
    }
    if (sun_idx >= params.sun_count)
    {
        printf("ERROR: sun_idx %d >= sun_count %d\n", sun_idx, params.sun_count);
        return;
    }

    // Get data for this ray
    float3 face_centroid = params.face_centroids[face_idx];
    float3 face_normal = params.face_normals[face_idx];
    float3 sun_dir = params.sun_directions[sun_idx];

    float3 ray_dir = make_float3(-sun_dir.x, -sun_dir.y, -sun_dir.z);

    // Skip back-facing surfaces (dot product check)
    float dot_product = face_normal.x * ray_dir.x +
                        face_normal.y * ray_dir.y +
                        face_normal.z * ray_dir.z;

    if (dot_product <= 0.001f)
        return;

    // Setup shadow ray from face toward sun
    float3 ray_origin = make_float3(
        face_centroid.x + face_normal.x * params.ray_offset, // Offset to avoid self-intersection
        face_centroid.y + face_normal.y * params.ray_offset,
        face_centroid.z + face_normal.z * params.ray_offset);

    // Trace shadow ray
    uint32_t shadow_hit = 0;
    optixTrace(
        params.gas_handle,                     // Scene
        ray_origin,                            // Ray origin
        ray_dir,                               // Ray direction
        0.0001f,                               // tmin
        1e16f,                                 // tmax (very far)
        0.0f,                                  // ray time
        OptixVisibilityMask(255),              // Visibility mask
        OPTIX_RAY_FLAG_TERMINATE_ON_FIRST_HIT, // Stop at first hit
        0,                                     // SBT offset
        1,                                     // SBT stride
        0,                                     // miss SBT index
        shadow_hit                             // Payload: 0 = no shadow, 1 = shadow
    );

    // If no shadow (shadow_hit == 0), add to sun hours
    if (shadow_hit == 0)
    {
        atomicAdd(&params.results[face_idx], 1.0f);
    }
}

// Miss program - ray didn't hit anything (no shadow)
extern "C" __global__ void __miss__shadow()
{
    // printf("Miss shader called\n");
    optixSetPayload_0(0); // No shadow
}

// Closest hit program - ray hit something (shadow)
extern "C" __global__ void __closesthit__shadow()
{
    optixSetPayload_0(1); // Shadow found
}
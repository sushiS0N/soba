#include "optix_solar.h"
#include <optix_stubs.h>
#include <optix_function_table_definition.h>
#include <cuda.h>
#include <fstream>
#include <iostream>
#include <vector>
#include <chrono>

/////////// MACROS ///////////
#define OPTIX_CHECK(call)                                                       \
    do                                                                          \
    {                                                                           \
        OptixResult res = call;                                                 \
        if (res != OPTIX_SUCCESS)                                               \
        {                                                                       \
            std::cerr << "OptiX error " << __FILE__ << ":" << __LINE__ << " - " \
                      << optixGetErrorString(res) << std::endl;                 \
            exit(1);                                                            \
        }                                                                       \
    } while (0)

#define CUDA_CHECK(call)                                                       \
    do                                                                         \
    {                                                                          \
        cudaError_t err = call;                                                \
        if (err != cudaSuccess)                                                \
        {                                                                      \
            std::cerr << "CUDA error " << __FILE__ << ":" << __LINE__ << " - " \
                      << cudaGetErrorString(err) << std::endl;                 \
            exit(1);                                                           \
        }                                                                      \
    } while (0)

// Load PTX file
static std::string load_ptx()
{
    std::ifstream file("optix_programs.ptx");
    if (!file)
    {
        std::cerr << "Error: optix_programs.ptx not found!\n";
        std::cerr << "Generate with: nvcc --ptx -O3 -I/path/to/optix/include optix_programs.cu\n";
        exit(1);
    }
    return std::string((std::istreambuf_iterator<char>(file)),
                       std::istreambuf_iterator<char>());
}

// Initializing optix
bool init_optix(OptiXSolar &optix, const std::vector<Triangle_GPU> &triangles)
{
    std::cout << "Initializing OptiX for " << triangles.size() << " triangles...\n";

    // 1. Initialize OptiX
    OPTIX_CHECK(optixInit());

    // 2. Create context - simplified approach
    OptixDeviceContextOptions ctx_options = {};
    ctx_options.logCallbackFunction = nullptr;
    OPTIX_CHECK(optixDeviceContextCreate(0, &ctx_options, &optix.context));

    // 3. Build GAS (Geometry Acceleration Structure)
    // Convert triangles to flat vertex array
    std::vector<float3> vertices;
    vertices.reserve(triangles.size() * 3);
    for (const auto &tri : triangles)
    {
        vertices.push_back(tri.v0);
        vertices.push_back(tri.v1);
        vertices.push_back(tri.v2);
    }

    // Upload vertices to GPU
    CUdeviceptr d_vertices;
    CUDA_CHECK(cudaMalloc((void **)&d_vertices, vertices.size() * sizeof(float3)));
    CUDA_CHECK(cudaMemcpy((void *)d_vertices, vertices.data(),
                          vertices.size() * sizeof(float3), cudaMemcpyHostToDevice));

    // Setup build input
    OptixBuildInput build_input = {};
    build_input.type = OPTIX_BUILD_INPUT_TYPE_TRIANGLES;
    build_input.triangleArray.vertexBuffers = &d_vertices;
    build_input.triangleArray.numVertices = static_cast<unsigned int>(triangles.size() * 3);
    build_input.triangleArray.vertexFormat = OPTIX_VERTEX_FORMAT_FLOAT3;
    build_input.triangleArray.vertexStrideInBytes = sizeof(float3);
    build_input.triangleArray.numIndexTriplets = 0;
    build_input.triangleArray.indexFormat = OPTIX_INDICES_FORMAT_NONE;
    build_input.triangleArray.indexBuffer = 0;

    uint32_t build_flags[] = {OPTIX_GEOMETRY_FLAG_NONE};
    build_input.triangleArray.flags = build_flags;
    build_input.triangleArray.numSbtRecords = 1;
    build_input.triangleArray.sbtIndexOffsetBuffer = 0;
    build_input.triangleArray.sbtIndexOffsetSizeInBytes = 0;
    build_input.triangleArray.sbtIndexOffsetStrideInBytes = 0;

    // Build options
    OptixAccelBuildOptions build_options = {};
    build_options.buildFlags = OPTIX_BUILD_FLAG_PREFER_FAST_TRACE;
    build_options.operation = OPTIX_BUILD_OPERATION_BUILD;

    std::cout << "Triangles: " << triangles.size() << ", Vertices: " << vertices.size() << std::endl;

    // Get memory requirements
    OptixAccelBufferSizes buffer_sizes;
    OPTIX_CHECK(optixAccelComputeMemoryUsage(optix.context, &build_options,
                                             &build_input, 1, &buffer_sizes));

    // Allocate and build
    CUdeviceptr d_temp_buffer;
    CUDA_CHECK(cudaMalloc((void **)&d_temp_buffer, buffer_sizes.tempSizeInBytes));
    CUDA_CHECK(cudaMalloc((void **)&optix.d_gas_buffer, buffer_sizes.outputSizeInBytes));

    OPTIX_CHECK(optixAccelBuild(optix.context, 0, &build_options, &build_input, 1,
                                d_temp_buffer, buffer_sizes.tempSizeInBytes,
                                optix.d_gas_buffer, buffer_sizes.outputSizeInBytes,
                                &optix.gas_handle, nullptr, 0));

    // Cleanup temp data
    CUDA_CHECK(cudaFree((void *)d_temp_buffer));
    CUDA_CHECK(cudaFree((void *)d_vertices));

    std::cout << "GAS built successfully\n";

    // 4. Create module from PTX
    std::string ptx = load_ptx();

    OptixModuleCompileOptions module_options = {};
    module_options.maxRegisterCount = 50;
    module_options.optLevel = OPTIX_COMPILE_OPTIMIZATION_DEFAULT;

    OptixPipelineCompileOptions pipeline_options = {};
    pipeline_options.traversableGraphFlags = OPTIX_TRAVERSABLE_GRAPH_FLAG_ALLOW_SINGLE_GAS;
    pipeline_options.numPayloadValues = 1;   // Just shadow flag
    pipeline_options.numAttributeValues = 0; // No hit attributes needed
    pipeline_options.pipelineLaunchParamsVariableName = "params";

    OptixModule module;
    char log[2048];
    size_t log_size = sizeof(log);
    OPTIX_CHECK(optixModuleCreate(optix.context, &module_options, &pipeline_options,
                                  ptx.c_str(), ptx.size(), log, &log_size, &module));

    // 5. Create program groups
    OptixProgramGroupOptions pg_options = {};

    // Raygen program
    OptixProgramGroup raygen_pg;
    OptixProgramGroupDesc raygen_desc = {};
    raygen_desc.kind = OPTIX_PROGRAM_GROUP_KIND_RAYGEN;
    raygen_desc.raygen.module = module;
    raygen_desc.raygen.entryFunctionName = "__raygen__solar";
    OPTIX_CHECK(optixProgramGroupCreate(optix.context, &raygen_desc, 1, &pg_options,
                                        log, &log_size, &raygen_pg));

    // Miss program (no shadow)
    OptixProgramGroup miss_pg;
    OptixProgramGroupDesc miss_desc = {};
    miss_desc.kind = OPTIX_PROGRAM_GROUP_KIND_MISS;
    miss_desc.miss.module = module;
    miss_desc.miss.entryFunctionName = "__miss__shadow";
    OPTIX_CHECK(optixProgramGroupCreate(optix.context, &miss_desc, 1, &pg_options,
                                        log, &log_size, &miss_pg));

    // Hit program (shadow found)
    OptixProgramGroup hit_pg;
    OptixProgramGroupDesc hit_desc = {};
    hit_desc.kind = OPTIX_PROGRAM_GROUP_KIND_HITGROUP;
    hit_desc.hitgroup.moduleCH = module;
    hit_desc.hitgroup.entryFunctionNameCH = "__closesthit__shadow";
    OPTIX_CHECK(optixProgramGroupCreate(optix.context, &hit_desc, 1, &pg_options,
                                        log, &log_size, &hit_pg));

    // 6. Create pipeline
    OptixProgramGroup program_groups[] = {raygen_pg, miss_pg, hit_pg};
    OptixPipelineLinkOptions link_options = {};
    link_options.maxTraceDepth = 1; // Only shadow rays
    OPTIX_CHECK(optixPipelineCreate(optix.context, &pipeline_options, &link_options,
                                    program_groups, 3, log, &log_size, &optix.pipeline));

    // 7. Setup Shader Binding Table (SBT)
    CUdeviceptr d_raygen_sbt, d_miss_sbt, d_hit_sbt;

    // Each SBT record is just the program header (no data)
    struct SbtRecord
    {
        char header[OPTIX_SBT_RECORD_HEADER_SIZE];
    };

    SbtRecord raygen_record, miss_record, hit_record;
    OPTIX_CHECK(optixSbtRecordPackHeader(raygen_pg, &raygen_record));
    OPTIX_CHECK(optixSbtRecordPackHeader(miss_pg, &miss_record));
    OPTIX_CHECK(optixSbtRecordPackHeader(hit_pg, &hit_record));

    CUDA_CHECK(cudaMalloc((void **)&d_raygen_sbt, sizeof(SbtRecord)));
    CUDA_CHECK(cudaMalloc((void **)&d_miss_sbt, sizeof(SbtRecord)));
    CUDA_CHECK(cudaMalloc((void **)&d_hit_sbt, sizeof(SbtRecord)));

    CUDA_CHECK(cudaMemcpy((void *)d_raygen_sbt, &raygen_record, sizeof(SbtRecord),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy((void *)d_miss_sbt, &miss_record, sizeof(SbtRecord),
                          cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy((void *)d_hit_sbt, &hit_record, sizeof(SbtRecord),
                          cudaMemcpyHostToDevice));

    optix.sbt.raygenRecord = d_raygen_sbt;
    optix.sbt.missRecordBase = d_miss_sbt;
    optix.sbt.missRecordStrideInBytes = sizeof(SbtRecord);
    optix.sbt.missRecordCount = 1;
    optix.sbt.hitgroupRecordBase = d_hit_sbt;
    optix.sbt.hitgroupRecordStrideInBytes = sizeof(SbtRecord);
    optix.sbt.hitgroupRecordCount = 1;

    // 8. Allocate launch parameters
    CUDA_CHECK(cudaMalloc((void **)&optix.d_params, sizeof(LaunchParams)));

    std::cout << "OptiX initialization complete!\n";
    return true;
}

// Launch Optix
void launch_solar_rays(OptiXSolar &optix, float3 *centroids, float3 *normals,
                       float3 *suns, float *results, int face_count, int sun_count, float ray_offset)
{

    // Setup launch parameters
    LaunchParams params;
    params.face_centroids = centroids;
    params.face_normals = normals;
    params.sun_directions = suns;
    params.results = results;
    params.face_count = face_count;
    params.sun_count = sun_count;
    params.gas_handle = optix.gas_handle;
    params.ray_offset = ray_offset;

    // Copy to GPU
    CUDA_CHECK(cudaMemcpy((void *)optix.d_params, &params, sizeof(params),
                          cudaMemcpyHostToDevice));

    // Launch rays - one thread per (face, sun) pair
    int total_rays = face_count * sun_count;
    OPTIX_CHECK(optixLaunch(optix.pipeline, 0, optix.d_params, sizeof(params),
                            &optix.sbt, total_rays, 1, 1));

    // Wait for completion
    CUDA_CHECK(cudaDeviceSynchronize());
}

// Cleanup function
void cleanup_optix(OptiXSolar &optix)
{
    if (optix.d_gas_buffer)
        CUDA_CHECK(cudaFree((void *)optix.d_gas_buffer));
    if (optix.d_params)
        CUDA_CHECK(cudaFree((void *)optix.d_params));
    if (optix.sbt.raygenRecord)
        CUDA_CHECK(cudaFree((void *)optix.sbt.raygenRecord));
    if (optix.sbt.missRecordBase)
        CUDA_CHECK(cudaFree((void *)optix.sbt.missRecordBase));
    if (optix.sbt.hitgroupRecordBase)
        CUDA_CHECK(cudaFree((void *)optix.sbt.hitgroupRecordBase));
    if (optix.context)
        optixDeviceContextDestroy(optix.context);
}

// Main wrapper function
void gpu_solar_analysis_series_optix(
    const std::vector<point3> &face_centroids,
    const std::vector<vec3> &face_normals,
    const std::vector<Triangle> &scene_tris,
    const std::vector<vec3> &sun_directions,
    std::vector<float> &results,
    float ray_offset)
{

    std::cout << "GPU OptiX: Processing " << face_centroids.size() << " faces...\n";

    const int face_count = static_cast<int>(face_centroids.size());
    const int scene_tris_count = static_cast<int>(scene_tris.size());
    const int sun_count = static_cast<int>(sun_directions.size());

    // Convert to GPU format
    std::vector<Triangle_GPU> gpu_scene_tris(scene_tris_count);
    for (int i = 0; i < scene_tris_count; i++)
    {
        const auto &tri = scene_tris[i];
        gpu_scene_tris[i] = Triangle_GPU(
            make_float3(tri.v0.x(), tri.v0.y(), tri.v0.z()),
            make_float3(tri.v1.x(), tri.v1.y(), tri.v1.z()),
            make_float3(tri.v2.x(), tri.v2.y(), tri.v2.z()));
    }

    // Allocate GPU memory
    float3 *d_centroids, *d_normals, *d_sun_dirs;
    float *d_results;

    CUDA_CHECK(cudaMalloc(&d_centroids, face_count * sizeof(float3)));
    CUDA_CHECK(cudaMalloc(&d_normals, face_count * sizeof(float3)));
    CUDA_CHECK(cudaMalloc(&d_sun_dirs, sun_count * sizeof(float3)));
    CUDA_CHECK(cudaMalloc(&d_results, face_count * sizeof(float)));

    // Convert and transfer data
    std::vector<float3> gpu_centroids(face_count), gpu_normals(face_count), gpu_sun_dirs(sun_count);

    for (int i = 0; i < face_count; i++)
    {
        gpu_centroids[i] = make_float3(face_centroids[i].x(), face_centroids[i].y(), face_centroids[i].z());
        gpu_normals[i] = make_float3(face_normals[i].x(), face_normals[i].y(), face_normals[i].z());
    }

    for (int i = 0; i < sun_count; i++)
    {
        gpu_sun_dirs[i] = make_float3(sun_directions[i].x(), sun_directions[i].y(), sun_directions[i].z());
    }

    CUDA_CHECK(cudaMemcpy(d_centroids, gpu_centroids.data(), face_count * sizeof(float3), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_normals, gpu_normals.data(), face_count * sizeof(float3), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_sun_dirs, gpu_sun_dirs.data(), sun_count * sizeof(float3), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemset(d_results, 0, face_count * sizeof(float)));

    std::cout << "OptiX triangle count: " << gpu_scene_tris.size() << std::endl;

    // Initialize OptiX
    auto start = std::chrono::high_resolution_clock::now();
    OptiXSolar optix;
    if (!init_optix(optix, gpu_scene_tris))
    {
        std::cerr << "OptiX initialization failed!\n";
        return;
    }

    std::cout << "Launching " << face_count * sun_count << " total rays" << std::endl;
    std::cout << "Face count: " << face_count << ", Sun count: " << sun_count << std::endl;

    auto init_end = std::chrono::high_resolution_clock::now();
    auto init_time = std::chrono::duration_cast<std::chrono::milliseconds>(init_end - start).count();
    std::cout << "OptiX init: " << init_time << "ms\n";

    // Launch rays
    auto ray_start = std::chrono::high_resolution_clock::now();
    launch_solar_rays(optix, d_centroids, d_normals, d_sun_dirs, d_results, face_count, sun_count, ray_offset);

    auto ray_end = std::chrono::high_resolution_clock::now();
    auto ray_time = std::chrono::duration_cast<std::chrono::microseconds>(ray_end - ray_start).count();
    std::cout << "OptiX tracing: " << ray_time << "μs (" << ray_time / 1000.0f << "ms)\n";

    // Get results
    results.resize(face_count);
    CUDA_CHECK(cudaMemcpy(results.data(), d_results, face_count * sizeof(float), cudaMemcpyDeviceToHost));

    std::cout << "DEBUG: After memcpy, first 5 results: ";
    for (int i = 0; i < std::min(5, face_count); i++)
    {
        std::cout << results[i] << " ";
    }
    std::cout << std::endl;

    // Cleanup
    cleanup_optix(optix);
    CUDA_CHECK(cudaFree(d_centroids));
    CUDA_CHECK(cudaFree(d_normals));
    CUDA_CHECK(cudaFree(d_sun_dirs));
    CUDA_CHECK(cudaFree(d_results));

    std::cout << "OptiX complete!\n";
}
#include <iostream>
#include <vector>
#include <chrono>
#include <filesystem>

#include "optix_solar.h"

int main()
{
    std::cout << "====CUDA TESTING====" << std::endl;
    /*
        // Read meshes
        SolarMesh building, context;
        building.load_obj("assets/tencent_glass.obj");
        context.load_obj("assets/tencent_context.obj");

        float ray_offset = 0.1f;
        // Compute triangles, normals, centroids
        const std::vector<point3> &centroids = building.get_faces_centroids();
        const std::vector<vec3> &normals = building.get_faces_normals();

        std::vector<Triangle> scene;
        scene.reserve(building.get_triangles().size() + context.get_triangles().size());
        scene.insert(scene.end(), building.get_triangles().begin(), building.get_triangles().end());
        scene.insert(scene.end(), context.get_triangles().begin(), context.get_triangles().end());

        std::cout << "Combined scene sieze: " << scene.size() << std::endl;
        std::cout << "Memory needed: " << scene.size() * sizeof(Triangle_GPU) << std::endl;

        // Import sun vectors
        std::vector<vec3>
            sun_directions;
        std::string filename = "sun_data.txt";
        load_sun_data(filename, sun_directions);

        std::cout << "=== DEBUG INFO ===" << std::endl;
        std::cout << "Face count: " << centroids.size() << std::endl;

        // Results
        std::vector<float> gpu_results;
        gpu_results.resize(building.get_face_count(), 0.0f);

        std::cout << "Main.cpp face 7 centroid: " << centroids[7].x() << ", "
                  << centroids[7].y() << ", " << centroids[7].z() << std::endl;
        std::cout << "Main.cpp face 7 normal: " << normals[7].x() << ", "
                  << normals[7].y() << ", " << normals[7].z() << std::endl;

        // Time the GPU version
        auto start = std::chrono::high_resolution_clock::now();

        gpu_solar_analysis_series_optix(centroids, normals, scene, sun_directions, gpu_results, ray_offset);

        auto gpu_time = std::chrono::high_resolution_clock::now() - start;

        std::cout << "GPU time: " << std::chrono::duration_cast<std::chrono::milliseconds>(gpu_time).count()
                  << " ms" << std::endl;

        // Write results out
        write_results("results.txt", gpu_results);
        return 0;*/
}
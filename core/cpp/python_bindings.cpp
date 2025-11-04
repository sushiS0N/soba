// python_bindings.cpp - CORRECTED VERSION
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <vector>
#include <iostream>

#include "optix_solar.h" // This has your gpu_solar_analysis_series_optix function

namespace py = pybind11;

// Helper function to convert numpy arrays to C++ vectors
std::vector<point3> numpy_to_point3_vector(py::array_t<float> arr)
{
    if (arr.ndim() != 2 || arr.shape(1) != 3)
    {
        throw std::runtime_error("Expected a Nx3 array for points");
    }

    auto r = arr.unchecked<2>();
    std::vector<point3> result;
    result.reserve(r.shape(0));

    for (py::ssize_t i = 0; i < r.shape(0); i++)
    {
        result.emplace_back(r(i, 0), r(i, 1), r(i, 2));
    }
    return result;
}

std::vector<vec3> numpy_to_vec3_vector(py::array_t<float> arr)
{
    if (arr.ndim() != 2 || arr.shape(1) != 3)
    {
        throw std::runtime_error("Expected a Nx3 array for vectors");
    }

    auto r = arr.unchecked<2>();
    std::vector<vec3> result;
    result.reserve(r.shape(0));

    for (py::ssize_t i = 0; i < r.shape(0); i++)
    {
        result.emplace_back(r(i, 0), r(i, 1), r(i, 2));
    }
    return result;
}

std::vector<Triangle> numpy_to_triangles_direct(py::array_t<float> triangles)
{
    // Input: triangles array of shape (num_triangles, 3, 3)
    // Each triangle is 3 vertices, each vertex is (x, y, z)

    if (triangles.ndim() != 3 || triangles.shape(1) != 3 || triangles.shape(2) != 3)
    {
        throw std::runtime_error("Expected triangles array of shape (N, 3, 3)");
    }

    auto t = triangles.unchecked<3>();
    std::vector<Triangle> result;
    result.reserve(t.shape(0));

    for (py::ssize_t i = 0; i < t.shape(0); i++)
    {
        point3 v0(t(i, 0, 0), t(i, 0, 1), t(i, 0, 2));
        point3 v1(t(i, 1, 0), t(i, 1, 1), t(i, 1, 2));
        point3 v2(t(i, 2, 0), t(i, 2, 1), t(i, 2, 2));

        result.emplace_back(v0, v1, v2);
    }
    return result;
}

// Safe wrapper around your OptiX function
void safe_gpu_solar_analysis(
    const std::vector<point3> &centroids,
    const std::vector<vec3> &normals,
    const std::vector<Triangle> &triangles,
    const std::vector<vec3> &sun_dirs,
    std::vector<float> &results,
    float ray_offset)
{
    try
    {
        std::cout << "Safe OptiX: Starting with " << centroids.size() << " faces" << std::endl;

        std::cout << "Safe OptiX: Calling gpu_solar_analysis_series_optix..." << std::endl;
        gpu_solar_analysis_series_optix(centroids, normals, triangles, sun_dirs, results, ray_offset);
        std::cout << "Safe OptiX: Function returned successfully!" << std::endl;

        std::cout << "Safe OptiX: Function returned successfully!" << std::endl;
        std::cout << "Safe OptiX: Results vector size: " << results.size() << std::endl;
        std::cout << "Safe OptiX: First 5 results: ";
        for (int i = 0; i < std::min(5, (int)results.size()); i++)
        {
            std::cout << results[i] << " ";
        }
        std::cout << std::endl;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Safe OptiX Error: " << e.what() << std::endl;
        throw;
    }
}

py::array_t<float> solar_analysis_optix(
    py::array_t<float> face_centroids,
    py::array_t<float> face_normals,
    py::array_t<float> scene_triangles,
    py::array_t<float> sun_directions,
    float ray_offset)
{
    try
    {
        std::cout << "C++: Starting solar_analysis_optix..." << std::endl;

        // Convert data
        auto centroids = numpy_to_point3_vector(face_centroids);
        auto normals = numpy_to_vec3_vector(face_normals);
        auto sun_dirs = numpy_to_vec3_vector(sun_directions);
        auto triangles = numpy_to_triangles_direct(scene_triangles);

        std::cout << "C++: Data converted successfully" << std::endl;

        std::vector<float> results;

        // Use safe wrapper instead of direct OptiX call
        safe_gpu_solar_analysis(centroids, normals, triangles, sun_dirs, results, ray_offset);

        // Convert results back to numpy
        py::array_t<float> py_results({static_cast<py::ssize_t>(results.size())});
        auto r = py_results.mutable_unchecked<1>();
        for (size_t i = 0; i < results.size(); i++)
        {
            r(i) = results[i];
        }

        std::cout << "C++: Analysis complete, returning results" << std::endl;
        return py_results;
    }
    catch (const std::exception &e)
    {
        std::cout << "C++: Exception: " << e.what() << std::endl;
        throw py::value_error(std::string("Solar analysis failed: ") + e.what());
    }
}

PYBIND11_MODULE(solar_engine_optix, m)
{
    m.doc() = "OptiX-accelerated solar analysis engine for architectural visualization";

    m.def("analyze", &solar_analysis_optix,
          "Run solar analysis using OptiX ray tracing",
          py::arg("face_centroids"),
          py::arg("face_normals"),
          py::arg("scene_triangles"),
          py::arg("sun_directions"),
          py::arg("ray_offset"));

    // Version info
    m.attr("__version__") = "1.0.0";
    m.attr("has_optix") = true;
}
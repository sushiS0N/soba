#pragma once
#include "vec3.h"

// Minimal Triangle for data conversion
class Triangle
{
public:
    point3 v0, v1, v2;
    vec3 edge1, edge2;
    vec3 normal;
    point3 centroid;

    Triangle() = default;
    Triangle(point3 a, point3 b, point3 c, int face_id = -1)
        : v0(a), v1(b), v2(c)
    {
        edge1 = v1 - v0;
        edge2 = v2 - v0;
        normal = cross(edge1, edge2);
        normal.normalize_in_place();
        centroid = (a + b + c) / 3.0f;
    }
};
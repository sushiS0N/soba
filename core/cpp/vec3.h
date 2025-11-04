#pragma once
#include <math.h>
#include <stdlib.h>

#include <iostream>

// Math primitives

class vec3
{
public:
  float v[3];

  // Constructors
  vec3() {}
  vec3(float v0, float v1, float v2)
  {
    v[0] = v0;
    v[1] = v1;
    v[2] = v2;
  }

  // Accessors
  float x() const { return v[0]; }
  float y() const { return v[1]; }
  float z() const { return v[2]; }

  // Array access
  float operator[](int i) const { return v[i]; }
  float &operator[](int i) { return v[i]; }

  // Unary operator
  vec3 operator-() const { return vec3(-v[0], -v[1], -v[2]); }

  // Compound assignment
  vec3 &operator+=(const vec3 &other)
  {
    v[0] += other.v[0];
    v[1] += other.v[1];
    v[2] += other.v[2];
    return *this;
  }

  vec3 &operator*=(float t)
  {
    v[0] *= t;
    v[1] *= t;
    v[2] *= t;
    return *this;
  }

  vec3 &operator/=(float t) { return *this *= (1.0f / t); }

  vec3 normalize() const
  {
    float len = length();
    if (len > 0)
    {
      return vec3(v[0] / len, v[1] / len, v[2] / len);
    }
    return vec3(0, 0, 0); // handle zero length
  }

  vec3 &normalize_in_place()
  {
    float len = length();
    if (len > 0)
    {
      v[0] /= len;
      v[1] /= len;
      v[2] /= len;
    }
    return *this;
  }

  vec3 &reverse_in_place()
  {
    v[0] = -v[0];
    v[1] = -v[1];
    v[2] = -v[2];
    return *this;
  }

  // Utility functions
  float length_squared() const
  {
    return v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
  }

  float length() const { return std::sqrt(length_squared()); }
};

// Binary operations (free functions - create new objects)
inline vec3 operator+(const vec3 &a, const vec3 &b)
{
  return vec3(a.v[0] + b.v[0], a.v[1] + b.v[1], a.v[2] + b.v[2]);
}

inline vec3 operator-(const vec3 &a, const vec3 &b)
{
  return vec3(a.v[0] - b.v[0], a.v[1] - b.v[1], a.v[2] - b.v[2]);
}

inline vec3 operator*(const vec3 &v, float t)
{
  return vec3(v.v[0] * t, v.v[1] * t, v.v[2] * t);
}

inline vec3 operator*(float t, const vec3 &v)
{
  return v * t; // commutative
}

inline vec3 operator/(const vec3 &v, float t) { return v * (1.0f / t); }

// Utility functions
inline float dot(const vec3 &a, const vec3 &b)
{
  return a.v[0] * b.v[0] + a.v[1] * b.v[1] + a.v[2] * b.v[2];
}

inline vec3 cross(const vec3 &a, const vec3 &b)
{
  return vec3(a.v[1] * b.v[2] - a.v[2] * b.v[1],
              a.v[2] * b.v[0] - a.v[0] * b.v[2],
              a.v[0] * b.v[1] - a.v[1] * b.v[0]);
}

inline std::ostream &operator<<(std::ostream &out, const vec3 &v)
{
  return out << v.v[0] << ' ' << v.v[1] << ' ' << v.v[2];
}

using point3 = vec3;
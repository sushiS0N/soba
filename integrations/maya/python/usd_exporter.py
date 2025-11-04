import maya.cmds as cmds
import maya.api.OpenMaya as om
from pxr import Usd, UsdGeom, Sdf, Gf
import os
import numpy as np


class USDSolarExporter:
    def __init__(self):
        self.stage = None
        self.root_prim = None

    def create_stage(self, file_path):
        """Create a new USD stage"""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        self.stage = Usd.Stage.CreateNew(file_path)
        UsdGeom.SetStageMetersPerUnit(self.stage, 1.0)
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)

        self.root_prim = self.stage.DefinePrim("/Root", "Xform")
        self.stage.SetDefaultPrim(self.root_prim)

        return self.stage

    def get_mesh_data(self, mesh_name, apply_smooth=False):
        """
        Extract mesh data from Maya mesh

        Args:
            mesh_name: Name of the mesh transform
            apply_smooth: If True, apply smooth mesh preview subdivision
        """
        shapes = cmds.listRelatives(mesh_name, shapes=True, type="mesh")
        if not shapes:
            raise ValueError(f"No mesh shape found for {mesh_name}")

        mesh_shape = shapes[0]

        # Create a duplicate to avoid modifying original
        duplicate_transform = cmds.duplicate(mesh_name, returnRootsOnly=True)[0]
        duplicate_shapes = cmds.listRelatives(
            duplicate_transform, shapes=True, type="mesh"
        )
        duplicate_mesh_shape = duplicate_shapes[0]

        # Apply smooth mesh preview if requested
        if apply_smooth:
            if cmds.getAttr(f"{mesh_shape}.displaySmoothMesh") > 0:
                subdivision_levels = cmds.getAttr(f"{mesh_shape}.smoothLevel")
                cmds.select(duplicate_transform)
                cmds.polySmooth(
                    divisions=subdivision_levels,
                    subdivisionType=2,
                    keepBorder=True,
                    keepHardEdge=True,
                    keepMapBorders=True,
                    ch=False,
                )

        # Set to face normals
        cmds.polySetToFaceNormal(duplicate_mesh_shape, setUserNormal=True)

        # Get mesh function set
        selection_list = om.MSelectionList()
        selection_list.add(duplicate_mesh_shape)
        dag_path = selection_list.getDagPath(0)
        mesh_fn = om.MFnMesh(dag_path)

        # Get vertices
        points = mesh_fn.getPoints(om.MSpace.kWorld)
        vertices = [(p.x, p.y, p.z) for p in points]

        # Get face data
        face_counts, face_indices = mesh_fn.getVertices()
        face_vertex_counts = list(face_counts)
        face_vertex_indices = list(face_indices)

        # Extract face centers and normals
        face_centers, face_normals = self._extract_face_data(mesh_fn, dag_path)

        # Clean up duplicate
        cmds.delete(duplicate_transform)

        return {
            "vertices": vertices,
            "face_vertex_counts": face_vertex_counts,
            "face_vertex_indices": face_vertex_indices,
            "face_centers": face_centers,
            "face_normals": face_normals,
        }

    def _extract_face_data(self, mesh_fn, dag_path):
        """Extract per-face centers and normals"""
        num_faces = mesh_fn.numPolygons
        centers = np.zeros((num_faces, 3), dtype=np.float32)
        normals = np.zeros((num_faces, 3), dtype=np.float32)

        face_it = om.MItMeshPolygon(dag_path)
        face_idx = 0

        while not face_it.isDone():
            vertex_indices = face_it.getVertices()
            vertex_coords = [
                mesh_fn.getPoint(vi, om.MSpace.kWorld) for vi in vertex_indices
            ]
            num_vertices = len(vertex_coords)

            if num_vertices == 4:
                # Quad: calculate center and normal using diagonals
                v0, v1, v2, v3 = (
                    vertex_coords[0],
                    vertex_coords[1],
                    vertex_coords[2],
                    vertex_coords[3],
                )

                center = np.array(
                    [
                        (v0.x + v1.x + v2.x + v3.x) / 4.0,
                        (v0.y + v1.y + v2.y + v3.y) / 4.0,
                        (v0.z + v1.z + v2.z + v3.z) / 4.0,
                    ],
                    dtype=np.float32,
                )

                edge1 = np.array([v1.x - v0.x, v1.y - v0.y, v1.z - v0.z])
                edge2 = np.array([v3.x - v0.x, v3.y - v0.y, v3.z - v0.z])
                normal = np.cross(edge1, edge2)
                normal_length = np.linalg.norm(normal)
                if normal_length > 1e-8:
                    normal = normal / normal_length
                else:
                    normal = np.array([0.0, 0.0, 1.0])

            elif num_vertices == 3:
                # Triangle
                v0, v1, v2 = vertex_coords[0], vertex_coords[1], vertex_coords[2]

                center = np.array(
                    [
                        (v0.x + v1.x + v2.x) / 3.0,
                        (v0.y + v1.y + v2.y) / 3.0,
                        (v0.z + v1.z + v2.z) / 3.0,
                    ],
                    dtype=np.float32,
                )

                edge1 = np.array([v1.x - v0.x, v1.y - v0.y, v1.z - v0.z])
                edge2 = np.array([v2.x - v0.x, v2.y - v0.y, v2.z - v0.z])
                normal = np.cross(edge1, edge2)
                normal_length = np.linalg.norm(normal)
                if normal_length > 1e-8:
                    normal = normal / normal_length
                else:
                    normal = np.array([0.0, 0.0, 1.0])

            else:
                # N-gon: use Maya's built-in
                center_point = face_it.center(om.MSpace.kWorld)
                center = np.array(
                    [center_point.x, center_point.y, center_point.z], dtype=np.float32
                )

                normal_vec = face_it.getNormal(om.MSpace.kWorld)
                normal = np.array(
                    [normal_vec.x, normal_vec.y, normal_vec.z], dtype=np.float32
                )

            centers[face_idx] = center
            normals[face_idx] = normal
            face_idx += 1
            face_it.next()

        return centers, normals

    def combine_and_process_meshes(self, mesh_list, triangulate=False):
        """
        Combine multiple meshes and optionally triangulate
        Returns combined mesh data, then cleans up
        """
        if not mesh_list:
            return None

        # Duplicate all meshes
        duplicates = []
        for mesh in mesh_list:
            dup = cmds.duplicate(mesh, returnRootsOnly=True)[0]
            duplicates.append(dup)

        # Combine all duplicates
        if len(duplicates) > 1:
            combined = cmds.polyUnite(duplicates, ch=False, mergeUVSets=True)[0]
        else:
            combined = duplicates[0]

        # Triangulate if requested
        if triangulate:
            cmds.polyTriangulate(combined, ch=False)

        # Set face normals
        combined_shapes = cmds.listRelatives(combined, shapes=True, type="mesh")
        if combined_shapes:
            cmds.polySetToFaceNormal(combined_shapes[0], setUserNormal=True)

        # Get mesh data
        mesh_data = self.get_mesh_data(combined, apply_smooth=False)

        # Clean up
        cmds.delete(combined)

        return mesh_data

    def process_target_meshes(self, target_mesh_list):
        """
        Process target meshes: subdivide each, then combine
        Returns combined mesh data with face centers/normals
        """
        print(f"Processing {len(target_mesh_list)} target meshes...")

        # Process each target mesh with smooth subdivision
        processed_meshes = []
        for mesh in target_mesh_list:
            # Duplicate
            dup = cmds.duplicate(mesh, returnRootsOnly=True)[0]

            # Check if smooth preview is on and apply subdivision
            shapes = cmds.listRelatives(mesh, shapes=True, type="mesh")
            if shapes:
                mesh_shape = shapes[0]
                if cmds.getAttr(f"{mesh_shape}.displaySmoothMesh") > 0:
                    subdivision_levels = cmds.getAttr(f"{mesh_shape}.smoothLevel")
                    print(f"  Subdividing {mesh} (level {subdivision_levels})...")
                    cmds.select(dup)
                    cmds.polySmooth(
                        divisions=subdivision_levels,
                        subdivisionType=2,
                        keepBorder=True,
                        keepHardEdge=True,
                        keepMapBorders=True,
                        ch=False,
                    )

            processed_meshes.append(dup)

        # Combine all processed targets
        if len(processed_meshes) > 1:
            combined = cmds.polyUnite(processed_meshes, ch=False, mergeUVSets=True)[0]
        else:
            combined = processed_meshes[0]

        # Set face normals
        combined_shapes = cmds.listRelatives(combined, shapes=True, type="mesh")
        if combined_shapes:
            cmds.polySetToFaceNormal(combined_shapes[0], setUserNormal=True)

        # Extract mesh data
        mesh_data = self.get_mesh_data(combined, apply_smooth=False)

        # Clean up
        cmds.delete(combined)

        print(
            f"  Target mesh: {len(mesh_data['vertices'])} vertices, {len(mesh_data['face_vertex_counts'])} faces"
        )

        return mesh_data

    def create_mesh_prim(self, mesh_data, prim_path, include_face_data=False):
        """Create USD mesh primitive from mesh data"""
        mesh_prim = UsdGeom.Mesh.Define(self.stage, prim_path)

        # Set points
        points_attr = mesh_prim.CreatePointsAttr()
        usd_points = [Gf.Vec3f(p[0], p[1], p[2]) for p in mesh_data["vertices"]]
        points_attr.Set(usd_points)

        # Set face vertex counts
        face_counts_attr = mesh_prim.CreateFaceVertexCountsAttr()
        face_counts_attr.Set(mesh_data["face_vertex_counts"])

        # Set face vertex indices
        face_indices_attr = mesh_prim.CreateFaceVertexIndicesAttr()
        face_indices_attr.Set(mesh_data["face_vertex_indices"])

        # Add face centers and normals as primvars if requested
        if include_face_data and "face_centers" in mesh_data:
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)

            # Face centers as uniform primvar
            centers_primvar = primvars_api.CreatePrimvar(
                "face_centers", Sdf.ValueTypeNames.Point3fArray, UsdGeom.Tokens.uniform
            )
            usd_centers = [
                Gf.Vec3f(float(c[0]), float(c[1]), float(c[2]))
                for c in mesh_data["face_centers"]
            ]
            centers_primvar.Set(usd_centers)

            # Face normals as uniform primvar
            normals_primvar = primvars_api.CreatePrimvar(
                "face_normals", Sdf.ValueTypeNames.Normal3fArray, UsdGeom.Tokens.uniform
            )
            usd_normals = [
                Gf.Vec3f(float(n[0]), float(n[1]), float(n[2]))
                for n in mesh_data["face_normals"]
            ]
            normals_primvar.Set(usd_normals)

        return mesh_prim

    def create_sun_attributes(self, solar_params, epw_path):
        """
        Store solar anaylsis parameters in USD metadata

        Args:
            solar_params: List of [monthStart, monthEnd, dayStart, dayEnd,
                                hourStart, hourEnd, timestep, offset]
            epw_path: Path to EPW file (optional)
        """
        if solar_params:
            params_str = ",".join(str(p) for p in solar_params)
            self.root_prim.SetCustomDataByKey("solar:params", params_str)
            print(f"Solar parameters stored: {params_str}")

        if epw_path:
            self.root_prim.SetCustomDataByKey("solar:epwFile", epw_path)
            print(f"EPW copied to: {epw_path}")

    def export_solar_analysis_scene(
        self, target_meshes, context_meshes, output_path, solar_params, epw_path
    ):
        """
        Export solar analysis scene to USD

        Args:
            target_meshes: List of mesh names to analyze (will be subdivided & combined)
            context_meshes: List of mesh names for context (used as-is)
            output_path: Path to output USD file
        """
        print("\n=== USD Solar Analysis Export ===")
        print(f"Target meshes: {target_meshes}")
        print(f"Context meshes: {context_meshes}")
        print("Solar analysis parameters as per UI input")

        # Create stage
        self.create_stage(output_path)

        # Process target meshes (subdivide + combine)
        print("\n1. Processing target meshes...")
        target_data = self.process_target_meshes(target_meshes)

        # Create TargetMesh prim with face data
        print("\n2. Creating TargetMesh in USD...")
        self.create_mesh_prim(target_data, "/Root/TargetMesh", include_face_data=True)

        # Process context geometry (all meshes combined and triangulated)
        print("\n3. Processing context geometry...")
        all_meshes = target_meshes + context_meshes
        context_data = self.combine_and_process_meshes(all_meshes, triangulate=True)

        # Create ContextGeometry prim
        print("\n4. Creating ContextGeometry in USD...")
        self.create_mesh_prim(
            context_data, "/Root/ContextGeometry/Combined", include_face_data=False
        )

        # Create sun parameters attribute
        print("\n5. Adding analysis parameters to USD...")
        self.create_sun_attributes(solar_params, epw_path)

        # Save stage
        print("\n6. Saving USD file...")
        self.stage.GetRootLayer().Save()
        print(f"\nSuccessfully exported to: {output_path}")
        print(f"  TargetMesh: {len(target_data['face_centers'])} faces")
        print(f"  ContextGeometry: {len(context_data['face_vertex_counts'])} triangles")

        return True


# Convenience function
def export_solar_scene(
    target_meshes, context_meshes, output_path, solar_params, epw_path
):
    """
    Export solar analysis scene

    Args:
        target_meshes: List of mesh names to analyze
        context_meshes: List of context mesh names
        output_path: Output USD file path
    """
    exporter = USDSolarExporter()
    return exporter.export_solar_analysis_scene(
        target_meshes, context_meshes, output_path, solar_params, epw_path
    )


# Example usage
if __name__ == "__main__":
    print("n\ This is meant to be run in Maya")
    print(
        'n\ Set the target and context meshes by their name(ex. "pSphere1") and provide an output path'
    )

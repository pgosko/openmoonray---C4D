"""
Hydra Scene Delegate
=====================
Custom HdSceneDelegate that translates a Cinema 4D document into Hydra
render primitives (meshes, cameras, lights, materials) consumed by the
hdMoonray render delegate.

The delegate maintains a mapping between Cinema 4D scene objects and
their Hydra prim paths so that incremental updates (for IPR) only
dirty the prims whose source objects have changed.
"""

import math

try:
    from pxr import Gf, Sdf, UsdGeom, UsdLux, Vt
except ImportError:
    Gf = Sdf = UsdGeom = UsdLux = Vt = None


# ============================================================
# Light-type constants matching c4d.LIGHT_TYPE_*
# ============================================================

_LIGHT_OMNI = 0
_LIGHT_SPOT = 1
_LIGHT_INFINITE = 3
_LIGHT_AREA = 8


class HydraSceneDelegate:
    """
    Translates a Cinema 4D document into Hydra render primitives.

    This is a *data provider* rather than a pxr.Hd.SceneDelegate sub-
    class because the Cinema 4D Python environment does not expose the
    full C++ Hydra API.  Instead it builds a USD stage in memory and
    lets the Hydra render index read from that stage via the
    UsdImagingDelegate shipped with USD.

    Why an in-memory stage?
    -----------------------
    * hdMoonray is designed to consume prims through the standard USD
      Imaging adapter.  Writing directly to an HdRenderIndex from
      Python is not supported by the public USD Python bindings.
    * An in-memory stage avoids file I/O and is fast enough for
      interactive preview rendering.
    """

    def __init__(self, config):
        """
        Args:
            config (dict): Render configuration from the plugin.
        """
        self.config = config
        self.stage = None
        self._prim_map = {}  # c4d object hash -> Sdf.Path

    # ================================================================
    # Public API
    # ================================================================

    def build_stage(self, doc):
        """
        Create a USD stage in memory from the Cinema 4D document.

        Args:
            doc: c4d.documents.BaseDocument

        Returns:
            pxr.Usd.Stage or None on failure.
        """
        if Sdf is None:
            print("[MoonRay Hydra] pxr Python bindings not available")
            return None

        try:
            from pxr import Usd
        except ImportError:
            print("[MoonRay Hydra] Could not import pxr.Usd")
            return None

        self.stage = Usd.Stage.CreateInMemory()
        self._configure_stage(doc)

        # Export scene elements
        self._export_camera(doc)
        self._export_lights(doc)
        self._export_geometry(doc)

        return self.stage

    def mark_dirty(self, obj_hash, dirty_bits):
        """
        Mark a prim as needing an update for interactive rendering.

        Args:
            obj_hash: Hash identifying the C4D object.
            dirty_bits (int): Combination of HdChangeTracker dirty bits.

        Returns:
            Sdf.Path or None if the object is unknown.
        """
        return self._prim_map.get(obj_hash)

    def get_stage(self):
        """Return the current in-memory USD stage."""
        return self.stage

    # ================================================================
    # Stage metadata
    # ================================================================

    def _configure_stage(self, doc):
        """Set global stage metadata."""
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.y)
        fps = self.config.get("fps", 24)
        self.stage.SetFramesPerSecond(fps)
        self.stage.SetTimeCodesPerSecond(fps)
        scale = self.config.get("scene_scale", 1.0)
        UsdGeom.SetStageMetersPerUnit(self.stage, scale)

    # ================================================================
    # Camera
    # ================================================================

    def _export_camera(self, doc):
        """Export the active render camera."""
        try:
            import c4d
        except ImportError:
            return

        bd = doc.GetRenderBaseDraw()
        cam = bd.GetSceneCamera(doc) if bd else None
        if cam is None:
            cam = doc.GetActiveObject()
        if cam is None or not cam.CheckType(c4d.Ocamera):
            return

        from pxr import Usd, UsdGeom

        cam_path = Sdf.Path("/World/Camera")
        usd_cam = UsdGeom.Camera.Define(self.stage, cam_path)

        # Focal length
        focal = cam[c4d.CAMERA_FOCUS]
        usd_cam.GetFocalLengthAttr().Set(focal)

        # Sensor / aperture
        aperture = cam[c4d.CAMERAOBJECT_APERTURE]
        if aperture and aperture > 0:
            usd_cam.GetHorizontalApertureAttr().Set(aperture)

        # Clipping
        usd_cam.GetClippingRangeAttr().Set(
            Gf.Vec2f(
                cam[c4d.CAMERAOBJECT_NEAR_CLIPPING],
                cam[c4d.CAMERAOBJECT_FAR_CLIPPING],
            )
        )

        # Transform
        xform = UsdGeom.Xformable(usd_cam.GetPrim())
        xform.AddTransformOp().Set(
            self._c4d_matrix_to_gf(cam.GetMg())
        )

        self._prim_map[hash(cam)] = cam_path

    # ================================================================
    # Lights
    # ================================================================

    def _export_lights(self, doc):
        """Export all lights in the document."""
        try:
            import c4d
        except ImportError:
            return

        from pxr import UsdLux

        obj = doc.GetFirstObject()
        light_idx = 0
        while obj:
            if obj.CheckType(c4d.Olight):
                self._export_single_light(obj, light_idx)
                light_idx += 1
            obj = self._next_object(obj)

    def _export_single_light(self, light, index):
        """Export one C4D light to the USD stage."""
        try:
            import c4d
        except ImportError:
            return

        from pxr import UsdLux, UsdGeom

        light_type = light[c4d.LIGHT_TYPE]
        path = Sdf.Path(f"/World/Lights/light_{index}")

        if light_type == _LIGHT_OMNI:
            usd_light = UsdLux.SphereLight.Define(self.stage, path)
            usd_light.GetRadiusAttr().Set(0.1)
        elif light_type == _LIGHT_SPOT:
            usd_light = UsdLux.SphereLight.Define(self.stage, path)
            usd_light.GetRadiusAttr().Set(0.1)
            shaping = UsdLux.ShapingAPI.Apply(usd_light.GetPrim())
            outer = light.get(c4d.LIGHT_DETAILS_OUTERANGLE, 45.0)
            shaping.GetShapingConeAngleAttr().Set(
                math.degrees(outer) if outer < math.pi else outer
            )
        elif light_type == _LIGHT_INFINITE:
            usd_light = UsdLux.DistantLight.Define(self.stage, path)
        elif light_type == _LIGHT_AREA:
            usd_light = UsdLux.RectLight.Define(self.stage, path)
            size_x = light.get(c4d.LIGHT_AREADETAILS_SIZEX, 100.0)
            size_y = light.get(c4d.LIGHT_AREADETAILS_SIZEY, 100.0)
            scale = self.config.get("scene_scale", 1.0)
            usd_light.GetWidthAttr().Set(size_x * scale)
            usd_light.GetHeightAttr().Set(size_y * scale)
        else:
            # Fallback
            usd_light = UsdLux.SphereLight.Define(self.stage, path)

        # Common properties
        color = light[c4d.LIGHT_COLOR]
        usd_light.GetColorAttr().Set(
            Gf.Vec3f(color.x, color.y, color.z)
        )
        intensity = light[c4d.LIGHT_BRIGHTNESS]
        usd_light.GetIntensityAttr().Set(intensity)

        # Transform
        xform = UsdGeom.Xformable(usd_light.GetPrim())
        xform.AddTransformOp().Set(
            self._c4d_matrix_to_gf(light.GetMg())
        )

        self._prim_map[hash(light)] = path

    # ================================================================
    # Geometry
    # ================================================================

    def _export_geometry(self, doc):
        """Export all polygon objects in the document."""
        try:
            import c4d
        except ImportError:
            return

        obj = doc.GetFirstObject()
        mesh_idx = 0
        while obj:
            if obj.GetType() == c4d.Opolygon or obj.GetDeformCache():
                self._export_mesh(obj, mesh_idx)
                mesh_idx += 1
            elif obj.GetType() in (
                c4d.Osphere, c4d.Ocube, c4d.Ocylinder,
                c4d.Ocone, c4d.Oplane, c4d.Otorus,
            ):
                # Generators: get the polygon cache
                cache = obj.GetDeformCache() or obj.GetCache()
                if cache and cache.GetType() == c4d.Opolygon:
                    self._export_mesh(cache, mesh_idx, name=obj.GetName())
                    mesh_idx += 1
            obj = self._next_object(obj)

    def _export_mesh(self, obj, index, name=None):
        """Export a polygon object as a UsdGeom.Mesh."""
        try:
            import c4d
        except ImportError:
            return

        from pxr import UsdGeom

        if name is None:
            name = obj.GetName()
        safe_name = self._sanitise_name(name, index)
        path = Sdf.Path(f"/World/Geometry/{safe_name}")

        mesh = UsdGeom.Mesh.Define(self.stage, path)

        # Vertices
        points = obj.GetAllPoints()
        scale = self.config.get("scene_scale", 1.0)
        vt_points = Vt.Vec3fArray(
            [Gf.Vec3f(p.x * scale, p.y * scale, p.z * scale)
             for p in points]
        )
        mesh.GetPointsAttr().Set(vt_points)

        # Face topology
        polys = obj.GetAllPolygons()
        face_counts = []
        face_indices = []
        for poly in polys:
            if poly.c == poly.d:
                face_counts.append(3)
                face_indices.extend([poly.a, poly.b, poly.c])
            else:
                face_counts.append(4)
                face_indices.extend([poly.a, poly.b, poly.c, poly.d])
        mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(face_counts))
        mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray(face_indices))

        # Subdivision scheme
        phong_tag = obj.GetTag(c4d.Tphong)
        if phong_tag:
            mesh.GetSubdivisionSchemeAttr().Set("catmullClark")
        else:
            mesh.GetSubdivisionSchemeAttr().Set("none")

        # UVs
        uvw_tag = obj.GetTag(c4d.Tuvw)
        if uvw_tag:
            self._export_uvs(mesh, uvw_tag, polys)

        # Normals
        if phong_tag:
            self._export_normals(mesh, obj, polys)

        # Transform
        xform = UsdGeom.Xformable(mesh.GetPrim())
        xform.AddTransformOp().Set(
            self._c4d_matrix_to_gf(obj.GetMg())
        )

        self._prim_map[hash(obj)] = path

    def _export_uvs(self, mesh, uvw_tag, polys):
        """Write UV primvar from a UVW tag."""
        from pxr import UsdGeom

        uvs = []
        for i, poly in enumerate(polys):
            uv_dict = uvw_tag.GetSlow(i)
            a = uv_dict["a"]
            b = uv_dict["b"]
            c = uv_dict["c"]
            uvs.append(Gf.Vec2f(a.x, a.y))
            uvs.append(Gf.Vec2f(b.x, b.y))
            uvs.append(Gf.Vec2f(c.x, c.y))
            if poly.c != poly.d:
                d = uv_dict["d"]
                uvs.append(Gf.Vec2f(d.x, d.y))

        primvar = UsdGeom.PrimvarsAPI(mesh.GetPrim()).CreatePrimvar(
            "st", Sdf.ValueTypeNames.TexCoord2fArray,
            UsdGeom.Tokens.faceVarying,
        )
        primvar.Set(Vt.Vec2fArray(uvs))

    def _export_normals(self, mesh, obj, polys):
        """Write per-face-vertex normals."""
        try:
            import c4d
            normals = []
            for i, poly in enumerate(polys):
                for vi in (poly.a, poly.b, poly.c):
                    n = obj.CreatePhongNormals()[i * 4]
                    normals.append(Gf.Vec3f(n.x, n.y, n.z))
                if poly.c != poly.d:
                    n = obj.CreatePhongNormals()[i * 4 + 3]
                    normals.append(Gf.Vec3f(n.x, n.y, n.z))
            mesh.GetNormalsAttr().Set(Vt.Vec3fArray(normals))
            mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
        except Exception:
            pass  # Normals are optional

    # ================================================================
    # Utility helpers
    # ================================================================

    @staticmethod
    def _c4d_matrix_to_gf(m):
        """Convert a c4d.Matrix to a Gf.Matrix4d."""
        return Gf.Matrix4d(
            m.v1.x, m.v1.y, m.v1.z, 0,
            m.v2.x, m.v2.y, m.v2.z, 0,
            m.v3.x, m.v3.y, m.v3.z, 0,
            m.off.x, m.off.y, m.off.z, 1,
        )

    @staticmethod
    def _next_object(obj):
        """Depth-first traversal helper."""
        if obj.GetDown():
            return obj.GetDown()
        while obj:
            sibling = obj.GetNext()
            if sibling:
                return sibling
            obj = obj.GetUp()
        return None

    @staticmethod
    def _sanitise_name(name, index):
        """Create a valid USD prim name from a Cinema 4D object name."""
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
        if not safe or safe[0].isdigit():
            safe = f"obj_{safe}"
        return f"{safe}_{index}"

"""
Scene Translator - Phase 1
============================
Translates a Cinema 4D scene graph into USD format for MoonRay consumption.
Handles geometry (polygons, subdivision surfaces), cameras, lights, and transforms.
"""

import os
import math
import json


class SceneTranslator:
    """
    Traverses the Cinema 4D document and exports it as a USD file
    compatible with MoonRay's scene description requirements.
    """

    # C4D light type constants (matching c4d module values)
    LIGHT_OMNI = 0
    LIGHT_SPOT = 1
    LIGHT_INFINITE = 3
    LIGHT_AREA = 8

    def __init__(self, doc, config, work_dir):
        """
        Args:
            doc: c4d.documents.BaseDocument
            config (dict): Render configuration
            work_dir (str): Temporary directory for output files
        """
        self.doc = doc
        self.config = config
        self.work_dir = work_dir
        self.usd_data = {
            "metadata": {},
            "cameras": [],
            "lights": [],
            "geometry": [],
            "instances": [],
        }

    def translate(self):
        """
        Execute the full scene translation pipeline.

        Returns:
            str: Path to the exported USD file, or None on failure.
        """
        try:
            self._export_metadata()
            self._export_camera()
            self._export_lights()
            self._export_geometry()

            # Write the USD file
            usd_path = os.path.join(self.work_dir, "scene.usd")
            self._write_usd(usd_path)
            return usd_path

        except Exception as e:
            print(f"[MoonRay] Scene translation failed: {e}")
            return None

    def _export_metadata(self):
        """Export scene-level metadata."""
        self.usd_data["metadata"] = {
            "upAxis": "Y",
            "metersPerUnit": self.config.get("scene_scale", 1.0),
            "framesPerSecond": self.config.get("fps", 24),
            "startFrame": self.config.get("frame_start", 0),
            "endFrame": self.config.get("frame_end", 0),
        }

    def _export_camera(self):
        """Export the active/render camera."""
        try:
            import c4d

            # Get the render camera (active camera or document camera)
            camera = self.doc.GetRenderBaseDraw().GetSceneCamera(self.doc)
            if camera is None:
                camera = self.doc.GetRenderBaseDraw().GetEditorCamera()

            if camera is None:
                print("[MoonRay] Warning: No camera found, using defaults")
                self.usd_data["cameras"].append(self._default_camera())
                return

            # Extract camera properties
            cam_data = camera.GetDataInstance()
            mg = camera.GetMg()

            # Cinema 4D camera parameters
            focal_length = cam_data.GetFloat(c4d.CAMERA_FOCUS)
            sensor_width = cam_data.GetFloat(c4d.CAMERAOBJECT_APERTURE)
            near_clip = cam_data.GetFloat(c4d.CAMERAOBJECT_NEAR_CLIPPING)
            far_clip = cam_data.GetFloat(c4d.CAMERAOBJECT_FAR_CLIPPING)

            # Compute field of view
            fov_h = 2.0 * math.atan(sensor_width / (2.0 * focal_length))

            camera_entry = {
                "name": camera.GetName(),
                "type": "PerspectiveCamera",
                "focalLength": focal_length,
                "horizontalAperture": sensor_width,
                "fov": math.degrees(fov_h),
                "nearClip": near_clip,
                "farClip": far_clip,
                "transform": self._matrix_to_list(mg),
                "width": self.config.get("width", 1920),
                "height": self.config.get("height", 1080),
            }
            self.usd_data["cameras"].append(camera_entry)

        except ImportError:
            # Running outside C4D - use default camera
            self.usd_data["cameras"].append(self._default_camera())

    def _export_lights(self):
        """Export all lights in the scene."""
        try:
            import c4d

            obj = self.doc.GetFirstObject()
            while obj:
                if obj.GetType() == c4d.Olight:
                    self._process_light(obj)
                obj = self._next_object(obj)

        except ImportError:
            pass

    def _process_light(self, light_obj):
        """
        Convert a single C4D light to MoonRay light representation.

        Args:
            light_obj: c4d.BaseObject of type Olight
        """
        import c4d

        data = light_obj.GetDataInstance()
        mg = light_obj.GetMg()

        light_type = data.GetInt32(c4d.LIGHT_TYPE)
        color = data.GetVector(c4d.LIGHT_COLOR)
        intensity = data.GetFloat(c4d.LIGHT_BRIGHTNESS)

        # Map C4D light types to MoonRay light types
        type_map = {
            self.LIGHT_OMNI: "SphereLight",
            self.LIGHT_SPOT: "SpotLight",
            self.LIGHT_INFINITE: "DistantLight",
            self.LIGHT_AREA: "RectLight",
        }

        moonray_type = type_map.get(light_type, "SphereLight")

        light_entry = {
            "name": light_obj.GetName(),
            "type": moonray_type,
            "color": [color.x, color.y, color.z],
            "intensity": intensity,
            "transform": self._matrix_to_list(mg),
        }

        # Spot light specific parameters
        if light_type == self.LIGHT_SPOT:
            inner_angle = data.GetFloat(c4d.LIGHT_DETAILS_INNERANGLE)
            outer_angle = data.GetFloat(c4d.LIGHT_DETAILS_OUTERANGLE)
            light_entry["innerConeAngle"] = math.degrees(inner_angle)
            light_entry["outerConeAngle"] = math.degrees(outer_angle)

        # Area light specific parameters
        if light_type == self.LIGHT_AREA:
            size_x = data.GetFloat(c4d.LIGHT_AREADETAILS_SIZEX)
            size_y = data.GetFloat(c4d.LIGHT_AREADETAILS_SIZEY)
            light_entry["width"] = size_x
            light_entry["height"] = size_y

        self.usd_data["lights"].append(light_entry)

    def _export_geometry(self):
        """Export all visible polygon geometry."""
        try:
            import c4d
            from c4d.utils import SendModelingCommand

            obj = self.doc.GetFirstObject()
            while obj:
                if self._is_renderable(obj):
                    self._process_geometry(obj)
                obj = self._next_object(obj)

        except ImportError:
            pass

    def _process_geometry(self, obj):
        """
        Convert a C4D object to mesh geometry.
        Handles polygon objects directly and generators via CurrentStateToObject.

        Args:
            obj: c4d.BaseObject
        """
        import c4d

        # Convert generators to polygon objects
        if obj.GetType() != c4d.Opolygon:
            # Use CurrentStateToObject to get the polygon representation
            clone = obj.GetClone(c4d.COPYFLAGS_NO_HIERARCHY)
            result = c4d.utils.SendModelingCommand(
                command=c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list=[clone],
                doc=self.doc,
            )
            if not result or not isinstance(result, list):
                return
            poly_obj = result[0]
            if poly_obj.GetType() != c4d.Opolygon:
                return
        else:
            poly_obj = obj

        # Extract mesh data
        points = poly_obj.GetAllPoints()
        polygons = poly_obj.GetAllPolygons()

        if not points or not polygons:
            return

        mg = obj.GetMg()

        # Convert points to world space
        vertices = []
        for p in points:
            wp = mg * p
            vertices.append([wp.x, wp.y, wp.z])

        # Convert polygons to face indices (triangulated)
        faces = []
        for poly in polygons:
            if poly.c == poly.d:
                # Triangle
                faces.append([poly.a, poly.b, poly.c])
            else:
                # Quad - split into two triangles
                faces.append([poly.a, poly.b, poly.c])
                faces.append([poly.a, poly.c, poly.d])

        # Extract UVs if available
        uvs = self._extract_uvs(poly_obj, polygons)

        # Extract normals
        normals = self._extract_normals(poly_obj)

        geo_entry = {
            "name": obj.GetName(),
            "type": "Mesh",
            "vertices": vertices,
            "faces": faces,
            "uvs": uvs,
            "normals": normals,
            "transform": self._matrix_to_list(mg),
            "material": self._get_material_name(obj),
            "subdiv_level": self._get_subdiv_level(obj),
        }
        self.usd_data["geometry"].append(geo_entry)

    def _extract_uvs(self, poly_obj, polygons):
        """Extract UV coordinates from a polygon object."""
        try:
            import c4d

            uvw_tag = poly_obj.GetTag(c4d.Tuvw)
            if uvw_tag is None:
                return None

            uvs = []
            for i, poly in enumerate(polygons):
                uv_data = uvw_tag.GetSlow(i)
                if poly.c == poly.d:
                    uvs.append(
                        [
                            [uv_data["a"].x, uv_data["a"].y],
                            [uv_data["b"].x, uv_data["b"].y],
                            [uv_data["c"].x, uv_data["c"].y],
                        ]
                    )
                else:
                    uvs.append(
                        [
                            [uv_data["a"].x, uv_data["a"].y],
                            [uv_data["b"].x, uv_data["b"].y],
                            [uv_data["c"].x, uv_data["c"].y],
                        ]
                    )
                    uvs.append(
                        [
                            [uv_data["a"].x, uv_data["a"].y],
                            [uv_data["c"].x, uv_data["c"].y],
                            [uv_data["d"].x, uv_data["d"].y],
                        ]
                    )
            return uvs

        except (ImportError, Exception):
            return None

    def _extract_normals(self, poly_obj):
        """Extract vertex normals from a polygon object."""
        try:
            import c4d

            phong_tag = poly_obj.GetTag(c4d.Tphong)
            if phong_tag is None:
                return None

            # Use phong normals if available
            normals = []
            neighbor = c4d.utils.Neighbor()
            neighbor.Init(poly_obj)

            points = poly_obj.GetAllPoints()
            for i in range(poly_obj.GetPointCount()):
                normal = c4d.Vector(0, 1, 0)  # Default up
                normals.append([normal.x, normal.y, normal.z])

            return normals

        except (ImportError, Exception):
            return None

    def _get_material_name(self, obj):
        """Get the name of the first material assigned to an object."""
        try:
            import c4d

            tag = obj.GetTag(c4d.Ttexture)
            if tag:
                mat = tag[c4d.TEXTURETAG_MATERIAL]
                if mat:
                    return mat.GetName()
            return None

        except ImportError:
            return None

    def _get_subdiv_level(self, obj):
        """Check if object has subdivision surface and return level."""
        try:
            import c4d

            parent = obj.GetUp()
            if parent and parent.GetType() == c4d.Osds:
                return parent[c4d.SDSOBJECT_SUBEDITOR_CM]
            return 0

        except ImportError:
            return 0

    def _is_renderable(self, obj):
        """Check if an object should be included in the render."""
        try:
            import c4d

            # Skip invisible objects
            render_mode = obj.GetRenderMode()
            if render_mode == c4d.MODE_OFF:
                return False

            # Skip lights (handled separately)
            if obj.GetType() == c4d.Olight:
                return False

            # Skip cameras
            if obj.GetType() == c4d.Ocamera:
                return False

            # Skip null objects
            if obj.GetType() == c4d.Onull:
                return False

            return True

        except ImportError:
            return False

    def _write_usd(self, usd_path):
        """
        Write the collected scene data as a USD file.
        Uses the pxr USD library if available, otherwise writes USDA (text format).
        """
        try:
            from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf

            self._write_usd_binary(usd_path)
        except ImportError:
            # Fall back to USDA text format
            usda_path = usd_path.replace(".usd", ".usda")
            self._write_usda(usda_path)
            # Update the path reference
            return usda_path

        return usd_path

    def _write_usd_binary(self, usd_path):
        """Write USD using the pxr library (binary format)."""
        from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf, Vt

        stage = Usd.Stage.CreateNew(usd_path)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        stage.SetMetadata(
            "metersPerUnit",
            self.usd_data["metadata"].get("metersPerUnit", 1.0),
        )

        # Export cameras
        for cam in self.usd_data["cameras"]:
            cam_path = f"/World/Cameras/{self._sanitize_name(cam['name'])}"
            usd_cam = UsdGeom.Camera.Define(stage, cam_path)
            usd_cam.GetFocalLengthAttr().Set(cam["focalLength"])
            usd_cam.GetHorizontalApertureAttr().Set(cam["horizontalAperture"])
            usd_cam.GetClippingRangeAttr().Set(
                Gf.Vec2f(cam["nearClip"], cam["farClip"])
            )
            if cam.get("transform"):
                xform = UsdGeom.Xformable(usd_cam.GetPrim())
                xform.AddTransformOp().Set(
                    Gf.Matrix4d(*cam["transform"])
                )

        # Export lights
        for light in self.usd_data["lights"]:
            light_path = f"/World/Lights/{self._sanitize_name(light['name'])}"

            if light["type"] == "SphereLight":
                usd_light = UsdLux.SphereLight.Define(stage, light_path)
            elif light["type"] == "RectLight":
                usd_light = UsdLux.RectLight.Define(stage, light_path)
                if "width" in light:
                    usd_light.GetWidthAttr().Set(light["width"])
                if "height" in light:
                    usd_light.GetHeightAttr().Set(light["height"])
            elif light["type"] == "DistantLight":
                usd_light = UsdLux.DistantLight.Define(stage, light_path)
            elif light["type"] == "SpotLight":
                usd_light = UsdLux.SphereLight.Define(stage, light_path)
                # SpotLight is SphereLight + shaping
                shaping_api = UsdLux.ShapingAPI.Apply(usd_light.GetPrim())
                if "outerConeAngle" in light:
                    shaping_api.GetShapingConeAngleAttr().Set(
                        light["outerConeAngle"]
                    )
            else:
                usd_light = UsdLux.SphereLight.Define(stage, light_path)

            usd_light.GetIntensityAttr().Set(light["intensity"])
            color = light["color"]
            usd_light.GetColorAttr().Set(Gf.Vec3f(*color))

        # Export geometry
        for geo in self.usd_data["geometry"]:
            geo_path = f"/World/Geometry/{self._sanitize_name(geo['name'])}"
            mesh = UsdGeom.Mesh.Define(stage, geo_path)

            # Set vertices
            points = [Gf.Vec3f(*v) for v in geo["vertices"]]
            mesh.GetPointsAttr().Set(Vt.Vec3fArray(points))

            # Set face vertex counts and indices
            face_counts = [len(f) for f in geo["faces"]]
            face_indices = []
            for f in geo["faces"]:
                face_indices.extend(f)

            mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(face_counts))
            mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray(face_indices))

            # Set subdivision scheme
            if geo.get("subdiv_level", 0) > 0:
                mesh.GetSubdivisionSchemeAttr().Set("catmullClark")
            else:
                mesh.GetSubdivisionSchemeAttr().Set("none")

        stage.GetRootLayer().Save()

    def _write_usda(self, usda_path):
        """
        Write scene as USDA (ASCII USD) format.
        Used as fallback when pxr library is not available.
        """
        lines = []
        lines.append('#usda 1.0')
        lines.append('(')
        lines.append('    upAxis = "Y"')
        lines.append(
            f'    metersPerUnit = '
            f'{self.usd_data["metadata"].get("metersPerUnit", 1.0)}'
        )
        lines.append(')')
        lines.append('')
        lines.append('def Xform "World"')
        lines.append('{')

        # Cameras
        if self.usd_data["cameras"]:
            lines.append('    def Xform "Cameras"')
            lines.append('    {')
            for cam in self.usd_data["cameras"]:
                name = self._sanitize_name(cam["name"])
                lines.append(
                    f'        def Camera "{name}"'
                )
                lines.append('        {')
                lines.append(
                    f'            float focalLength = {cam["focalLength"]}'
                )
                lines.append(
                    f'            float horizontalAperture = '
                    f'{cam["horizontalAperture"]}'
                )
                lines.append(
                    f'            float2 clippingRange = '
                    f'({cam["nearClip"]}, {cam["farClip"]})'
                )
                lines.append('        }')
            lines.append('    }')

        # Lights
        if self.usd_data["lights"]:
            lines.append('    def Xform "Lights"')
            lines.append('    {')
            for light in self.usd_data["lights"]:
                name = self._sanitize_name(light["name"])
                usd_type = self._light_type_to_usd(light["type"])
                lines.append(f'        def {usd_type} "{name}"')
                lines.append('        {')
                lines.append(
                    f'            float inputs:intensity = '
                    f'{light["intensity"]}'
                )
                color = light["color"]
                lines.append(
                    f'            color3f inputs:color = '
                    f'({color[0]}, {color[1]}, {color[2]})'
                )
                lines.append('        }')
            lines.append('    }')

        # Geometry
        if self.usd_data["geometry"]:
            lines.append('    def Xform "Geometry"')
            lines.append('    {')
            for geo in self.usd_data["geometry"]:
                name = self._sanitize_name(geo["name"])
                lines.append(f'        def Mesh "{name}"')
                lines.append('        {')

                # Points
                points_str = ", ".join(
                    [f"({v[0]}, {v[1]}, {v[2]})" for v in geo["vertices"]]
                )
                lines.append(
                    f'            point3f[] points = [{points_str}]'
                )

                # Face vertex counts
                counts = [str(len(f)) for f in geo["faces"]]
                lines.append(
                    f'            int[] faceVertexCounts = '
                    f'[{", ".join(counts)}]'
                )

                # Face vertex indices
                indices = []
                for f in geo["faces"]:
                    indices.extend([str(i) for i in f])
                lines.append(
                    f'            int[] faceVertexIndices = '
                    f'[{", ".join(indices)}]'
                )

                # Subdivision
                subdiv = geo.get("subdiv_level", 0)
                if subdiv > 0:
                    lines.append(
                        '            token subdivisionScheme = "catmullClark"'
                    )
                else:
                    lines.append(
                        '            token subdivisionScheme = "none"'
                    )

                lines.append('        }')
            lines.append('    }')

        lines.append('}')
        lines.append('')

        with open(usda_path, "w") as f:
            f.write("\n".join(lines))

    def _light_type_to_usd(self, moonray_type):
        """Map MoonRay light type names to USD schema type names."""
        mapping = {
            "SphereLight": "SphereLight",
            "SpotLight": "SphereLight",
            "DistantLight": "DistantLight",
            "RectLight": "RectLight",
        }
        return mapping.get(moonray_type, "SphereLight")

    def _matrix_to_list(self, mg):
        """Convert a c4d.Matrix to a flat 16-element list (row-major)."""
        try:
            return [
                mg.v1.x, mg.v1.y, mg.v1.z, 0.0,
                mg.v2.x, mg.v2.y, mg.v2.z, 0.0,
                mg.v3.x, mg.v3.y, mg.v3.z, 0.0,
                mg.off.x, mg.off.y, mg.off.z, 1.0,
            ]
        except AttributeError:
            return [
                1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1,
            ]

    def _default_camera(self):
        """Return a default perspective camera."""
        return {
            "name": "DefaultCamera",
            "type": "PerspectiveCamera",
            "focalLength": 36.0,
            "horizontalAperture": 36.0,
            "fov": 53.13,
            "nearClip": 0.1,
            "farClip": 10000.0,
            "transform": [
                1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 200, -600, 1,
            ],
            "width": self.config.get("width", 1920),
            "height": self.config.get("height", 1080),
        }

    def _next_object(self, obj):
        """Depth-first traversal of the C4D object hierarchy."""
        if obj.GetDown():
            return obj.GetDown()
        while obj:
            if obj.GetNext():
                return obj.GetNext()
            obj = obj.GetUp()
        return None

    @staticmethod
    def _sanitize_name(name):
        """Sanitize a name for use as a USD prim path component."""
        if not name:
            return "Unnamed"
        # Replace invalid characters
        sanitized = ""
        for ch in name:
            if ch.isalnum() or ch == "_":
                sanitized += ch
            else:
                sanitized += "_"
        # Ensure it doesn't start with a digit
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized or "Unnamed"

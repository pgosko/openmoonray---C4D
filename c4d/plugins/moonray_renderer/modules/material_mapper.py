"""
Material Mapper - Phase 2
===========================
Maps Cinema 4D materials and shaders to MoonRay's production shader library.
Supports standard C4D materials, node materials, and generates
MaterialX-compatible shader descriptions for MoonRay consumption.
"""

import os
import math


class MaterialMapper:
    """
    Translates Cinema 4D materials into MoonRay shader assignments.
    Generates shader network descriptions compatible with MoonRay's
    DwaBase material system.
    """

    # MoonRay shader types
    SHADER_DWA_BASE = "DwaBaseMaterial"
    SHADER_DWA_METAL = "DwaMetalMaterial"
    SHADER_DWA_GLASS = "DwaGlassMaterial"
    SHADER_DWA_SKIN = "DwaSkinMaterial"
    SHADER_DWA_FABRIC = "DwaFabricMaterial"
    SHADER_DWA_EMISSIVE = "DwaEmissiveMaterial"

    def __init__(self, doc, config, work_dir):
        """
        Args:
            doc: c4d.documents.BaseDocument
            config (dict): Render configuration
            work_dir (str): Temporary directory for texture/shader files
        """
        self.doc = doc
        self.config = config
        self.work_dir = work_dir
        self.materials = {}
        self.texture_dir = os.path.join(work_dir, "textures")
        os.makedirs(self.texture_dir, exist_ok=True)

    def export_materials(self, usd_path):
        """
        Export all materials from the document and create shader assignments.

        Args:
            usd_path (str): Path to the USD scene file (for material binding).
        """
        try:
            import c4d

            mat = self.doc.GetFirstMaterial()
            while mat:
                self._process_material(mat)
                mat = mat.GetNext()

            # Write material definitions
            self._write_material_file()

        except ImportError:
            # Running outside C4D - generate stub materials
            self._write_material_file()

    def _process_material(self, mat):
        """
        Analyze a C4D material and map it to the appropriate MoonRay shader.

        Args:
            mat: c4d.BaseMaterial
        """
        import c4d

        mat_name = mat.GetName()
        mat_data = mat.GetDataInstance()

        # Determine the best MoonRay shader to use based on material properties
        shader_type = self._determine_shader_type(mat)

        material_def = {
            "name": mat_name,
            "shader_type": shader_type,
            "params": {},
            "textures": {},
        }

        # Extract color/diffuse channel
        if mat[c4d.MATERIAL_USE_COLOR]:
            color = mat[c4d.MATERIAL_COLOR_COLOR]
            material_def["params"]["albedo"] = [color.x, color.y, color.z]
            material_def["params"]["diffuse_weight"] = (
                mat[c4d.MATERIAL_COLOR_BRIGHTNESS]
            )

            # Check for texture in color channel
            shader = mat[c4d.MATERIAL_COLOR_SHADER]
            if shader and shader.GetType() == c4d.Xbitmap:
                tex_path = shader[c4d.BITMAPSHADER_FILENAME]
                material_def["textures"]["albedo_map"] = tex_path

        # Extract reflection/specular
        if mat[c4d.MATERIAL_USE_REFLECTION]:
            material_def["params"]["specular_weight"] = 1.0
            # Get roughness from reflection layer
            ref_layers = mat.GetAllReflectionShaders()
            if ref_layers:
                material_def["params"]["roughness"] = self._extract_roughness(
                    mat
                )

        # Extract luminance/emission
        if mat[c4d.MATERIAL_USE_LUMINANCE]:
            lum_color = mat[c4d.MATERIAL_LUMINANCE_COLOR]
            material_def["params"]["emission_color"] = [
                lum_color.x,
                lum_color.y,
                lum_color.z,
            ]
            material_def["params"]["emission_weight"] = (
                mat[c4d.MATERIAL_LUMINANCE_BRIGHTNESS]
            )

        # Extract transparency
        if mat[c4d.MATERIAL_USE_TRANSPARENCY]:
            trans_brightness = mat[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS]
            material_def["params"]["transmission_weight"] = trans_brightness
            refraction = mat[c4d.MATERIAL_TRANSPARENCY_REFRACTION]
            material_def["params"]["ior"] = refraction

        # Extract bump/normal
        if mat[c4d.MATERIAL_USE_BUMP]:
            bump_strength = mat[c4d.MATERIAL_BUMP_STRENGTH]
            material_def["params"]["bump_strength"] = bump_strength
            bump_shader = mat[c4d.MATERIAL_BUMP_SHADER]
            if bump_shader and bump_shader.GetType() == c4d.Xbitmap:
                tex_path = bump_shader[c4d.BITMAPSHADER_FILENAME]
                material_def["textures"]["bump_map"] = tex_path

        # Extract normal map
        if mat[c4d.MATERIAL_USE_NORMAL]:
            normal_shader = mat[c4d.MATERIAL_NORMAL_SHADER]
            if normal_shader and normal_shader.GetType() == c4d.Xbitmap:
                tex_path = normal_shader[c4d.BITMAPSHADER_FILENAME]
                material_def["textures"]["normal_map"] = tex_path

        # Extract displacement
        if mat[c4d.MATERIAL_USE_DISPLACEMENT]:
            disp_strength = mat[c4d.MATERIAL_DISPLACEMENT_STRENGTH]
            material_def["params"]["displacement_height"] = disp_strength
            disp_shader = mat[c4d.MATERIAL_DISPLACEMENT_SHADER]
            if disp_shader and disp_shader.GetType() == c4d.Xbitmap:
                tex_path = disp_shader[c4d.BITMAPSHADER_FILENAME]
                material_def["textures"]["displacement_map"] = tex_path

        # Extract alpha
        if mat[c4d.MATERIAL_USE_ALPHA]:
            alpha_shader = mat[c4d.MATERIAL_ALPHA_SHADER]
            if alpha_shader and alpha_shader.GetType() == c4d.Xbitmap:
                tex_path = alpha_shader[c4d.BITMAPSHADER_FILENAME]
                material_def["textures"]["opacity_map"] = tex_path

        self.materials[mat_name] = material_def

    def _determine_shader_type(self, mat):
        """
        Heuristically determine the best MoonRay shader type for a C4D material.

        Args:
            mat: c4d.BaseMaterial

        Returns:
            str: MoonRay shader type name.
        """
        try:
            import c4d

            # High transparency + high IOR → Glass
            if mat[c4d.MATERIAL_USE_TRANSPARENCY]:
                trans = mat[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS]
                if trans > 0.8:
                    return self.SHADER_DWA_GLASS

            # High luminance → Emissive
            if mat[c4d.MATERIAL_USE_LUMINANCE]:
                lum = mat[c4d.MATERIAL_LUMINANCE_BRIGHTNESS]
                if lum > 0.5:
                    return self.SHADER_DWA_EMISSIVE

            # High metallic reflection → Metal
            if mat[c4d.MATERIAL_USE_REFLECTION]:
                if not mat[c4d.MATERIAL_USE_COLOR]:
                    return self.SHADER_DWA_METAL

            # Default to base material
            return self.SHADER_DWA_BASE

        except (ImportError, Exception):
            return self.SHADER_DWA_BASE

    def _extract_roughness(self, mat):
        """
        Extract roughness value from a C4D material's reflection system.

        Args:
            mat: c4d.BaseMaterial

        Returns:
            float: Roughness value (0.0 = mirror, 1.0 = fully diffuse)
        """
        try:
            import c4d

            # Try to get roughness from the first reflection layer
            layer_count = mat.GetReflectionLayerCount()
            if layer_count > 0:
                layer = mat.GetReflectionLayerIndex(0)
                if layer:
                    layer_id = layer.GetDataID()
                    roughness = mat[
                        layer_id + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS
                    ]
                    if roughness is not None:
                        return roughness

            return 0.3  # Default roughness

        except (ImportError, Exception):
            return 0.3

    def _write_material_file(self):
        """Write material definitions as a JSON file for the render executor."""
        import json

        materials_path = os.path.join(self.work_dir, "materials.json")

        # Convert materials to serializable format
        output = {}
        for name, mat_def in self.materials.items():
            output[name] = {
                "shader_type": mat_def["shader_type"],
                "params": mat_def["params"],
                "textures": mat_def.get("textures", {}),
            }

        with open(materials_path, "w") as f:
            json.dump(output, f, indent=2)

    def generate_rdla_materials(self):
        """
        Generate MoonRay RDLA (scene description) material assignments.
        This produces the native MoonRay shader definitions.

        Returns:
            str: RDLA-formatted material definitions.
        """
        rdla_lines = []

        for name, mat_def in self.materials.items():
            shader_type = mat_def["shader_type"]
            params = mat_def["params"]
            textures = mat_def.get("textures", {})

            rdla_lines.append(f'{shader_type}("{name}") {{')

            # Albedo / base color
            if "albedo" in params:
                color = params["albedo"]
                rdla_lines.append(
                    f'    ["albedo"] = Rgb({color[0]}, {color[1]}, {color[2]}),'
                )

            # Roughness
            if "roughness" in params:
                rdla_lines.append(
                    f'    ["roughness"] = {params["roughness"]},'
                )

            # Specular weight
            if "specular_weight" in params:
                rdla_lines.append(
                    f'    ["specular"] = {params["specular_weight"]},'
                )

            # Transmission
            if "transmission_weight" in params:
                rdla_lines.append(
                    f'    ["transmission"] = '
                    f'{params["transmission_weight"]},'
                )

            # IOR
            if "ior" in params:
                rdla_lines.append(f'    ["ior"] = {params["ior"]},')

            # Emission
            if "emission_color" in params:
                color = params["emission_color"]
                rdla_lines.append(
                    f'    ["emission"] = Rgb('
                    f'{color[0]}, {color[1]}, {color[2]}),'
                )

            # Texture maps
            if "albedo_map" in textures:
                rdla_lines.append(
                    f'    ["albedo map"] = '
                    f'ImageMap("{name}_albedo_map") {{'
                )
                rdla_lines.append(
                    f'        ["texture"] = "{textures["albedo_map"]}",'
                )
                rdla_lines.append("    },")

            if "normal_map" in textures:
                rdla_lines.append(
                    f'    ["input normal map"] = '
                    f'NormalMap("{name}_normal_map") {{'
                )
                rdla_lines.append(
                    f'        ["texture"] = "{textures["normal_map"]}",'
                )
                rdla_lines.append("    },")

            rdla_lines.append("}")
            rdla_lines.append("")

        return "\n".join(rdla_lines)

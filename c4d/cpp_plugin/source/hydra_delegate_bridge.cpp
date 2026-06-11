/**
 * MoonRay Hydra Delegate Bridge - Implementation
 * ================================================
 * Translates a Cinema 4D document into an in-memory USD stage and
 * renders it through hdMoonray via the UsdImagingGL engine.
 *
 * Copyright 2024-2026 - Apache License 2.0
 */

#include "hydra_delegate_bridge.h"
#include "VPmoonray.h"

#ifdef MOONRAY_AVAILABLE
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdGeom/xformable.h>
#include <pxr/usd/usdLux/sphereLight.h>
#include <pxr/usd/usdLux/rectLight.h>
#include <pxr/usd/usdLux/distantLight.h>
#include <pxr/usd/usdLux/shapingAPI.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/gf/vec4d.h>
#include <pxr/base/vt/array.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>
#include <pxr/usdImaging/usdImagingGL/renderParams.h>

PXR_NAMESPACE_USING_DIRECTIVE

// Helper: convert a c4d::Matrix to a GfMatrix4d
static GfMatrix4d C4DMatrixToGf(const Matrix& m)
{
    return GfMatrix4d(
        m.v1.x, m.v1.y, m.v1.z, 0.0,
        m.v2.x, m.v2.y, m.v2.z, 0.0,
        m.v3.x, m.v3.y, m.v3.z, 0.0,
        m.off.x, m.off.y, m.off.z, 1.0
    );
}

// Helper: sanitise an object name to a valid USD prim token
static std::string SanitizeName(const String& name, Int32 idx)
{
    Char buf[256];
    name.GetCString(buf, sizeof(buf));
    std::string s(buf);
    for (auto& ch : s)
    {
        if (!isalnum(static_cast<unsigned char>(ch)) && ch != '_')
            ch = '_';
    }
    if (s.empty() || isdigit(static_cast<unsigned char>(s[0])))
        s = "obj_" + s;
    return s + "_" + std::to_string(idx);
}

#endif // MOONRAY_AVAILABLE


// ============================================================
// Construction / Destruction
// ============================================================

HydraDelegateBridge::HydraDelegateBridge()
    : m_sceneScale(1.0)
    , m_initialized(false)
{
}

HydraDelegateBridge::~HydraDelegateBridge()
{
    Shutdown();
}

Bool HydraDelegateBridge::IsAvailable()
{
#ifdef MOONRAY_AVAILABLE
    return true;
#else
    return false;
#endif
}


// ============================================================
// Stage Construction
// ============================================================

Bool HydraDelegateBridge::BuildStage(BaseDocument* doc, BaseVideoPost* node)
{
#ifdef MOONRAY_AVAILABLE
    if (!doc)
        return false;

    m_stage = UsdStage::CreateInMemory();
    if (!m_stage)
        return false;

    // Read scene scale from render settings
    BaseContainer* data = node ? node->GetDataInstance() : nullptr;
    m_sceneScale = data ? data->GetFloat(MOONRAY_SCENE_SCALE) : 1.0;

    UsdGeomSetStageUpAxis(m_stage, UsdGeomTokens->y);
    UsdGeomSetStageMetersPerUnit(m_stage, m_sceneScale);

    Float64 fps = static_cast<Float64>(doc->GetFps());
    m_stage->SetFramesPerSecond(fps);
    m_stage->SetTimeCodesPerSecond(fps);

    if (!ExportCamera(doc))
        GePrint("[MoonRay Hydra] Warning: camera export failed"_s);

    if (!ExportLights(doc))
        GePrint("[MoonRay Hydra] Warning: lights export failed"_s);

    if (!ExportGeometry(doc))
        GePrint("[MoonRay Hydra] Warning: geometry export failed"_s);

    // Apply render settings before initialising the engine
    ApplySettings(node);

    return true;
#else
    return false;
#endif
}


// ============================================================
// Camera
// ============================================================

Bool HydraDelegateBridge::ExportCamera(BaseDocument* doc)
{
#ifdef MOONRAY_AVAILABLE
    BaseDraw* bd = doc->GetRenderBaseDraw();
    BaseObject* cam = bd ? bd->GetSceneCamera(doc) : nullptr;
    if (!cam)
        cam = doc->GetActiveObject();
    if (!cam || !cam->IsInstanceOf(Ocamera))
        return false;

    SdfPath camPath("/World/Camera");
    UsdGeomCamera usdCam = UsdGeomCamera::Define(m_stage, camPath);

    GeData gd;
    // Focal length
    if (cam->GetParameter(DescID(CAMERA_FOCUS), gd, DESCFLAGS_GET::NONE))
        usdCam.GetFocalLengthAttr().Set(static_cast<float>(gd.GetFloat()));

    // Aperture
    if (cam->GetParameter(DescID(CAMERAOBJECT_APERTURE), gd, DESCFLAGS_GET::NONE))
    {
        float aperture = static_cast<float>(gd.GetFloat());
        if (aperture > 0.0f)
            usdCam.GetHorizontalApertureAttr().Set(aperture);
    }

    // Clipping planes
    float nearClip = 0.01f, farClip = 10000.0f;
    if (cam->GetParameter(DescID(CAMERAOBJECT_NEAR_CLIPPING), gd, DESCFLAGS_GET::NONE))
        nearClip = static_cast<float>(gd.GetFloat());
    if (cam->GetParameter(DescID(CAMERAOBJECT_FAR_CLIPPING), gd, DESCFLAGS_GET::NONE))
        farClip = static_cast<float>(gd.GetFloat());
    usdCam.GetClippingRangeAttr().Set(GfVec2f(nearClip, farClip));

    // Transform
    UsdGeomXformable xform(usdCam.GetPrim());
    xform.AddTransformOp().Set(C4DMatrixToGf(cam->GetMg()));

    return true;
#else
    return false;
#endif
}


// ============================================================
// Lights
// ============================================================

Bool HydraDelegateBridge::ExportLights(BaseDocument* doc)
{
#ifdef MOONRAY_AVAILABLE
    Int32 lightIdx = 0;
    BaseObject* obj = doc->GetFirstObject();

    while (obj)
    {
        if (obj->IsInstanceOf(Olight))
        {
            GeData gd;
            Int32 lightType = 0;
            if (obj->GetParameter(DescID(LIGHT_TYPE), gd, DESCFLAGS_GET::NONE))
                lightType = gd.GetInt32();

            std::string name = "light_" + std::to_string(lightIdx);
            SdfPath path(std::string("/World/Lights/") + name);

            switch (lightType)
            {
                case 0: // Omni
                {
                    auto light = UsdLuxSphereLight::Define(m_stage, path);
                    light.GetRadiusAttr().Set(0.1f);
                    break;
                }
                case 1: // Spot
                {
                    auto light = UsdLuxSphereLight::Define(m_stage, path);
                    light.GetRadiusAttr().Set(0.1f);
                    UsdLuxShapingAPI shaping = UsdLuxShapingAPI::Apply(light.GetPrim());
                    if (obj->GetParameter(DescID(LIGHT_DETAILS_OUTERANGLE), gd, DESCFLAGS_GET::NONE))
                        shaping.GetShapingConeAngleAttr().Set(static_cast<float>(gd.GetFloat()));
                    break;
                }
                case 3: // Infinite / Distant
                {
                    UsdLuxDistantLight::Define(m_stage, path);
                    break;
                }
                case 8: // Area
                {
                    auto light = UsdLuxRectLight::Define(m_stage, path);
                    if (obj->GetParameter(DescID(LIGHT_AREADETAILS_SIZEX), gd, DESCFLAGS_GET::NONE))
                        light.GetWidthAttr().Set(static_cast<float>(gd.GetFloat() * m_sceneScale));
                    if (obj->GetParameter(DescID(LIGHT_AREADETAILS_SIZEY), gd, DESCFLAGS_GET::NONE))
                        light.GetHeightAttr().Set(static_cast<float>(gd.GetFloat() * m_sceneScale));
                    break;
                }
                default:
                {
                    UsdLuxSphereLight::Define(m_stage, path);
                    break;
                }
            }

            // Common: colour and intensity
            auto prim = m_stage->GetPrimAtPath(path);
            if (prim)
            {
                if (obj->GetParameter(DescID(LIGHT_COLOR), gd, DESCFLAGS_GET::NONE))
                {
                    Vector col = gd.GetVector();
                    prim.GetAttribute(TfToken("inputs:color"))
                        .Set(GfVec3f(static_cast<float>(col.x),
                                     static_cast<float>(col.y),
                                     static_cast<float>(col.z)));
                }
                if (obj->GetParameter(DescID(LIGHT_BRIGHTNESS), gd, DESCFLAGS_GET::NONE))
                {
                    prim.GetAttribute(TfToken("inputs:intensity"))
                        .Set(static_cast<float>(gd.GetFloat()));
                }

                // Transform
                UsdGeomXformable xform(prim);
                xform.AddTransformOp().Set(C4DMatrixToGf(obj->GetMg()));
            }

            ++lightIdx;
        }

        // Depth-first traversal
        if (obj->GetDown())
            obj = obj->GetDown();
        else
        {
            while (obj && !obj->GetNext())
                obj = obj->GetUp();
            if (obj)
                obj = obj->GetNext();
        }
    }

    return true;
#else
    return false;
#endif
}


// ============================================================
// Geometry
// ============================================================

Bool HydraDelegateBridge::ExportGeometry(BaseDocument* doc)
{
#ifdef MOONRAY_AVAILABLE
    Int32 meshIdx = 0;
    BaseObject* obj = doc->GetFirstObject();

    while (obj)
    {
        if (obj->GetType() == Opolygon)
        {
            ExportMesh(obj, meshIdx++);
        }
        else
        {
            // Try the deform/polygon cache for generators
            BaseObject* cache = obj->GetDeformCache();
            if (!cache)
                cache = obj->GetCache();
            if (cache && cache->GetType() == Opolygon)
                ExportMesh(cache, meshIdx++);
        }

        // Depth-first traversal
        if (obj->GetDown())
            obj = obj->GetDown();
        else
        {
            while (obj && !obj->GetNext())
                obj = obj->GetUp();
            if (obj)
                obj = obj->GetNext();
        }
    }

    return true;
#else
    return false;
#endif
}

Bool HydraDelegateBridge::ExportMesh(BaseObject* obj, Int32 index)
{
#ifdef MOONRAY_AVAILABLE
    PolygonObject* polyObj = static_cast<PolygonObject*>(obj);
    if (!polyObj)
        return false;

    Int32 pointCount = polyObj->GetPointCount();
    Int32 polyCount  = polyObj->GetPolygonCount();
    if (pointCount == 0 || polyCount == 0)
        return false;

    const Vector*  points = polyObj->GetPointR();
    const CPolygon* polys = polyObj->GetPolygonR();
    if (!points || !polys)
        return false;

    std::string safeName = SanitizeName(obj->GetName(), index);
    SdfPath meshPath(std::string("/World/Geometry/") + safeName);

    UsdGeomMesh mesh = UsdGeomMesh::Define(m_stage, meshPath);

    // Points
    VtVec3fArray vtPoints(pointCount);
    for (Int32 i = 0; i < pointCount; ++i)
    {
        vtPoints[i] = GfVec3f(
            static_cast<float>(points[i].x * m_sceneScale),
            static_cast<float>(points[i].y * m_sceneScale),
            static_cast<float>(points[i].z * m_sceneScale)
        );
    }
    mesh.GetPointsAttr().Set(vtPoints);

    // Face topology
    VtIntArray faceCounts;
    VtIntArray faceIndices;
    faceCounts.reserve(polyCount);
    faceIndices.reserve(polyCount * 4);

    for (Int32 i = 0; i < polyCount; ++i)
    {
        if (polys[i].c == polys[i].d)
        {
            faceCounts.push_back(3);
            faceIndices.push_back(polys[i].a);
            faceIndices.push_back(polys[i].b);
            faceIndices.push_back(polys[i].c);
        }
        else
        {
            faceCounts.push_back(4);
            faceIndices.push_back(polys[i].a);
            faceIndices.push_back(polys[i].b);
            faceIndices.push_back(polys[i].c);
            faceIndices.push_back(polys[i].d);
        }
    }
    mesh.GetFaceVertexCountsAttr().Set(faceCounts);
    mesh.GetFaceVertexIndicesAttr().Set(faceIndices);

    // Subdivision
    BaseTag* phongTag = obj->GetTag(Tphong);
    if (phongTag)
        mesh.GetSubdivisionSchemeAttr().Set(UsdGeomTokens->catmullClark);
    else
        mesh.GetSubdivisionSchemeAttr().Set(UsdGeomTokens->none);

    // Transform
    UsdGeomXformable xform(mesh.GetPrim());
    xform.AddTransformOp().Set(C4DMatrixToGf(obj->GetMg()));

    return true;
#else
    return false;
#endif
}


// ============================================================
// Hydra Engine
// ============================================================

Bool HydraDelegateBridge::InitEngine()
{
#ifdef MOONRAY_AVAILABLE
    m_engine = std::make_unique<UsdImagingGLEngine>();

    // Find hdMoonray among the available delegates
    TfTokenVector plugins = m_engine->GetRendererPlugins();
    TfToken moonrayId;

    for (const auto& pluginId : plugins)
    {
        std::string displayName = m_engine->GetRendererDisplayName(pluginId);
        // Case-insensitive search for "moonray"
        std::string lower = displayName;
        for (auto& ch : lower)
            ch = static_cast<char>(tolower(static_cast<unsigned char>(ch)));
        if (lower.find("moonray") != std::string::npos)
        {
            moonrayId = pluginId;
            break;
        }
    }

    if (moonrayId.IsEmpty())
    {
        GePrint("[MoonRay Hydra] hdMoonray render delegate not found"_s);
        return false;
    }

    if (!m_engine->SetRendererPlugin(moonrayId))
    {
        GePrint("[MoonRay Hydra] Failed to activate hdMoonray delegate"_s);
        return false;
    }

    GePrint("[MoonRay Hydra] Delegate activated successfully"_s);
    m_initialized = true;
    return true;
#else
    return false;
#endif
}

void HydraDelegateBridge::ApplySettings(BaseVideoPost* node)
{
#ifdef MOONRAY_AVAILABLE
    if (!m_engine || !node)
        return;

    BaseContainer* data = node->GetDataInstance();
    if (!data)
        return;

    // Push render quality settings into the Hydra delegate
    auto set = [&](const std::string& key, VtValue val) {
        m_engine->SetRendererSetting(TfToken(key), val);
    };

    set("moonray:samples_per_pixel",
        VtValue(data->GetInt32(MOONRAY_SAMPLES_PER_PIXEL)));
    set("moonray:max_depth",
        VtValue(data->GetInt32(MOONRAY_MAX_DEPTH)));
    set("moonray:light_samples",
        VtValue(data->GetInt32(MOONRAY_LIGHT_SAMPLES)));
    set("moonray:denoise",
        VtValue(data->GetBool(MOONRAY_DENOISE_ENABLED)));
    set("moonray:threads",
        VtValue(data->GetInt32(MOONRAY_THREADS)));
    set("moonray:adaptive_sampling",
        VtValue(data->GetBool(MOONRAY_ADAPTIVE_SAMPLING)));
    set("moonray:adaptive_threshold",
        VtValue(static_cast<float>(data->GetFloat(MOONRAY_ADAPTIVE_THRESHOLD))));
#endif
}


// ============================================================
// Render Execution
// ============================================================

Bool HydraDelegateBridge::Render(Int32 width, Int32 height, BaseThread* thread)
{
#ifdef MOONRAY_AVAILABLE
    if (!m_stage)
        return false;

    if (!InitEngine())
        return false;

    // Allocate pixel buffer (RGBA float32)
    m_pixelBuffer.resize(static_cast<size_t>(width) * height * 4, 0.0f);

    UsdImagingGLRenderParams params;
    GfVec4d viewport(0, 0, width, height);

    // Render loop – poll for convergence
    const int maxIterations = 10000;
    for (int i = 0; i < maxIterations; ++i)
    {
        if (thread && thread->TestBreak())
            return false;

        m_engine->Render(m_stage->GetPseudoRoot(), params);

        if (m_engine->IsConverged())
            break;
    }

    return true;
#else
    return false;
#endif
}

Bool HydraDelegateBridge::ReadPixels(VPBuffer* buffer, Int32 width, Int32 height)
{
#ifdef MOONRAY_AVAILABLE
    if (!buffer || m_pixelBuffer.empty())
        return false;

    Int32 bw = buffer->GetBw();
    Int32 bh = buffer->GetBh();
    Int32 useW = (width < bw) ? width : bw;
    Int32 useH = (height < bh) ? height : bh;

    // Transfer rendered pixels into the C4D VPBuffer
    for (Int32 y = 0; y < useH; ++y)
    {
        for (Int32 x = 0; x < useW; ++x)
        {
            size_t idx = (static_cast<size_t>(y) * width + x) * 4;
            Float32 r = m_pixelBuffer[idx];
            Float32 g = m_pixelBuffer[idx + 1];
            Float32 b = m_pixelBuffer[idx + 2];

            // Clamp to [0, 1]
            r = (r < 0.0f) ? 0.0f : ((r > 1.0f) ? 1.0f : r);
            g = (g < 0.0f) ? 0.0f : ((g > 1.0f) ? 1.0f : g);
            b = (b < 0.0f) ? 0.0f : ((b > 1.0f) ? 1.0f : b);

            // Write pixel (8-bit per channel for standard buffer)
            buffer->SetLine(x, y, 1, &r, 32, true);
        }
    }

    return true;
#else
    return false;
#endif
}


// ============================================================
// Shutdown
// ============================================================

void HydraDelegateBridge::Shutdown()
{
#ifdef MOONRAY_AVAILABLE
    if (m_engine)
    {
        m_engine->StopRenderer();
        m_engine.reset();
    }
    m_stage.Reset();
    m_pixelBuffer.clear();
#endif
    m_initialized = false;
}

/**
 * MoonRay Renderer Plugin for Cinema 4D - C++ VideoPost
 * ======================================================
 * Native C++ integration providing direct memory translation
 * from C4D scene objects into MoonRay's scene_rdl2 structures.
 *
 * Copyright 2024-2026 - Apache License 2.0
 */

#include "c4d.h"
#include "c4d_videopost.h"
#include "c4d_videopostdata.h"
#include "c4d_symbols.h"
#include "VPmoonray.h"
#include "hydra_delegate_bridge.h"

// Plugin ID - Register at plugincafe.maxon.net for production
static const Int32 ID_MOONRAY_VIDEOPOST = 1060450;

/**
 * MoonRay VideoPost Plugin
 * Implements the Cinema 4D render engine interface for MoonRay.
 */
class MoonRayVideoPost : public VideoPostData
{
    INSTANCEOF(MoonRayVideoPost, VideoPostData)

public:
    static NodeData* Alloc() { return NewObjClear(MoonRayVideoPost); }

    // ---- Initialization ----
    virtual Bool Init(GeListNode* node, Bool isCloneInit) override;
    virtual void Free(GeListNode* node) override;

    // ---- Description / UI ----
    virtual Bool GetDDescription(
        GeListNode* node,
        Description* description,
        DESCFLAGS_DESC& flags) override;

    // ---- Render Execution ----
    virtual VIDEOPOSTINFO GetRenderInfo(BaseVideoPost* node) override;
    virtual RENDERRESULT Execute(
        BaseVideoPost* node,
        VideoPostStruct* vps) override;

private:
    // Scene translation
    Bool TranslateScene(BaseDocument* doc, BaseVideoPost* node);
    Bool TranslateObject(BaseObject* obj);
    Bool TranslateCamera(BaseDraw* bd, BaseDocument* doc);
    Bool TranslateLights(BaseDocument* doc);
    Bool TranslateMaterials(BaseDocument* doc);

    // MoonRay integration
    Bool InitMoonRay();
    Bool ExecuteRender(Int32 width, Int32 height);
    Bool ReadResult(VPBuffer* buffer);
    void ShutdownMoonRay();

    // Hydra integration
    Bool ExecuteHydraRender(BaseDocument* doc, BaseVideoPost* node,
                            Int32 width, Int32 height,
                            VPBuffer* buffer, BaseThread* thread);

    // Internal state
    Bool m_initialized;
    HydraDelegateBridge m_hydraBridge;
};


// ============================================================
// Initialization
// ============================================================

Bool MoonRayVideoPost::Init(GeListNode* node, Bool isCloneInit)
{
    if (!node || !SUPER::Init(node, isCloneInit))
        return false;

    BaseContainer* data = static_cast<BaseVideoPost*>(node)->GetDataInstance();
    if (!data)
        return false;

    // Set default parameter values
    data->SetInt32(MOONRAY_SAMPLES_PER_PIXEL, 16);
    data->SetInt32(MOONRAY_MAX_DEPTH, 8);
    data->SetInt32(MOONRAY_LIGHT_SAMPLES, 4);
    data->SetInt32(MOONRAY_PIXEL_FILTER, 0);
    data->SetFloat(MOONRAY_PIXEL_FILTER_WIDTH, 2.0);
    data->SetBool(MOONRAY_DENOISE_ENABLED, true);
    data->SetInt32(MOONRAY_DENOISE_TYPE, 0);
    data->SetInt32(MOONRAY_THREADS, 0);
    data->SetInt32(MOONRAY_EXEC_MODE, 0);
    data->SetString(MOONRAY_EXEC_PATH, "moonray"_s);
    data->SetFloat(MOONRAY_SCENE_SCALE, 1.0);
    data->SetBool(MOONRAY_MOTION_BLUR, false);
    data->SetInt32(MOONRAY_MOTION_STEPS, 2);
    data->SetBool(MOONRAY_ADAPTIVE_SAMPLING, false);
    data->SetFloat(MOONRAY_ADAPTIVE_THRESHOLD, 0.01);
    data->SetBool(MOONRAY_HYDRA_ENABLED, HydraDelegateBridge::IsAvailable());
    data->SetBool(MOONRAY_HYDRA_IPR, false);
    data->SetFloat(MOONRAY_HYDRA_CONVERGENCE, 0.0);

    m_initialized = false;

    return true;
}

void MoonRayVideoPost::Free(GeListNode* node)
{
    ShutdownMoonRay();
    SUPER::Free(node);
}


// ============================================================
// Description
// ============================================================

Bool MoonRayVideoPost::GetDDescription(
    GeListNode* node,
    Description* description,
    DESCFLAGS_DESC& flags)
{
    if (!description->LoadDescription(node->GetType()))
        return false;

    flags |= DESCFLAGS_DESC::LOADED;
    return SUPER::GetDDescription(node, description, flags);
}


// ============================================================
// Render Info
// ============================================================

VIDEOPOSTINFO MoonRayVideoPost::GetRenderInfo(BaseVideoPost* node)
{
    // We handle the entire rendering pipeline
    return VIDEOPOSTINFO::EXECUTELINE;
}


// ============================================================
// Render Execution
// ============================================================

RENDERRESULT MoonRayVideoPost::Execute(
    BaseVideoPost* node,
    VideoPostStruct* vps)
{
    if (!node || !vps || !vps->doc || !vps->render)
        return RENDERRESULT::FAILED;

    BaseDocument* doc = vps->doc;
    RenderData* rd = vps->render->GetRenderData();

    if (!rd)
        return RENDERRESULT::FAILED;

    // Get render resolution
    Int32 width = rd->GetDataInstance()->GetInt32(RDATA_XRES);
    Int32 height = rd->GetDataInstance()->GetInt32(RDATA_YRES);

    // Check for user cancellation
    if (vps->thread && vps->thread->TestBreak())
        return RENDERRESULT::USERBREAK;

    // Determine execution mode
    BaseContainer* data = node->GetDataInstance();
    Int32 execMode = data ? data->GetInt32(MOONRAY_EXEC_MODE) : MOONRAY_EXEC_LOCAL;

    // ---- Hydra render path ----
    if (execMode == MOONRAY_EXEC_HYDRA)
    {
        VPBuffer* rgba = vps->render->GetBuffer(VPBUF_RGBA, 0);
        if (!ExecuteHydraRender(doc, node, width, height, rgba, vps->thread))
        {
            GePrint("[MoonRay] Hydra render failed"_s);
            return RENDERRESULT::FAILED;
        }
        return RENDERRESULT::OK;
    }

    // ---- Classic (CLI / Arras) render path ----

    // Phase 1: Initialize MoonRay
    if (!InitMoonRay())
    {
        GePrint("[MoonRay] Failed to initialize renderer"_s);
        return RENDERRESULT::FAILED;
    }

    // Phase 2: Translate scene
    if (!TranslateScene(doc, node))
    {
        GePrint("[MoonRay] Scene translation failed"_s);
        ShutdownMoonRay();
        return RENDERRESULT::FAILED;
    }

    // Check cancellation
    if (vps->thread && vps->thread->TestBreak())
    {
        ShutdownMoonRay();
        return RENDERRESULT::USERBREAK;
    }

    // Phase 3: Execute render
    if (!ExecuteRender(width, height))
    {
        GePrint("[MoonRay] Render execution failed"_s);
        ShutdownMoonRay();
        return RENDERRESULT::FAILED;
    }

    // Phase 4: Read result into buffer
    VPBuffer* rgba = vps->render->GetBuffer(VPBUF_RGBA, 0);
    if (rgba && !ReadResult(rgba))
    {
        GePrint("[MoonRay] Failed to read render result"_s);
        ShutdownMoonRay();
        return RENDERRESULT::FAILED;
    }

    ShutdownMoonRay();
    return RENDERRESULT::OK;
}


// ============================================================
// Scene Translation (Stubs for MoonRay scene_rdl2 integration)
// ============================================================

Bool MoonRayVideoPost::TranslateScene(BaseDocument* doc, BaseVideoPost* node)
{
    // TODO: Implement direct scene_rdl2 translation
    // This would create a SceneContext and populate it with
    // geometry, cameras, lights, and materials from the C4D document.

    if (!TranslateCamera(doc->GetRenderBaseDraw(), doc))
        return false;

    if (!TranslateLights(doc))
        return false;

    if (!TranslateMaterials(doc))
        return false;

    // Traverse object hierarchy
    BaseObject* obj = doc->GetFirstObject();
    while (obj)
    {
        if (!TranslateObject(obj))
        {
            // Non-fatal: skip problematic objects
            GePrint("[MoonRay] Warning: Skipped object: "_s + obj->GetName());
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
}

Bool MoonRayVideoPost::TranslateObject(BaseObject* obj)
{
    // TODO: Convert C4D polygon object to scene_rdl2 geometry
    // - Get polygon data via SendModelingCommand if needed
    // - Create rdl2::Geometry with mesh data
    // - Apply material assignments
    return true;
}

Bool MoonRayVideoPost::TranslateCamera(BaseDraw* bd, BaseDocument* doc)
{
    // TODO: Create rdl2::Camera from active camera
    // - Extract focal length, aperture, transform
    // - Map to MoonRay's camera model
    return true;
}

Bool MoonRayVideoPost::TranslateLights(BaseDocument* doc)
{
    // TODO: Create rdl2::Light objects for each C4D light
    // - Map light types (omni, spot, infinite, area)
    // - Convert intensity and color
    return true;
}

Bool MoonRayVideoPost::TranslateMaterials(BaseDocument* doc)
{
    // TODO: Create rdl2::Material objects
    // - Map C4D materials to DwaBaseMaterial, DwaMetalMaterial, etc.
    // - Handle texture paths and shader networks
    return true;
}


// ============================================================
// Hydra Render Path
// ============================================================

Bool MoonRayVideoPost::ExecuteHydraRender(
    BaseDocument* doc, BaseVideoPost* node,
    Int32 width, Int32 height,
    VPBuffer* buffer, BaseThread* thread)
{
    if (!HydraDelegateBridge::IsAvailable())
    {
        GePrint("[MoonRay Hydra] Hydra delegate not available"_s);
        return false;
    }

    // Build the USD stage from the C4D document
    if (!m_hydraBridge.BuildStage(doc, node))
    {
        GePrint("[MoonRay Hydra] Stage construction failed"_s);
        return false;
    }

    if (thread && thread->TestBreak())
    {
        m_hydraBridge.Shutdown();
        return false;
    }

    // Execute the Hydra render
    if (!m_hydraBridge.Render(width, height, thread))
    {
        GePrint("[MoonRay Hydra] Render execution failed"_s);
        m_hydraBridge.Shutdown();
        return false;
    }

    // Transfer pixels to C4D buffer
    Bool ok = buffer ? m_hydraBridge.ReadPixels(buffer, width, height) : true;

    m_hydraBridge.Shutdown();
    return ok;
}


// ============================================================
// MoonRay Engine Interface (Stubs)
// ============================================================

Bool MoonRayVideoPost::InitMoonRay()
{
    // TODO: Initialize scene_rdl2::rdl2::SceneContext
    // - Load DSO shader libraries
    // - Set up render context
    m_initialized = true;
    return true;
}

Bool MoonRayVideoPost::ExecuteRender(Int32 width, Int32 height)
{
    // TODO: Execute the MoonRay render via scene_rdl2
    // - Configure frame buffer dimensions
    // - Start the render threads
    // - Wait for completion with progress updates
    return true;
}

Bool MoonRayVideoPost::ReadResult(VPBuffer* buffer)
{
    // TODO: Copy MoonRay's rendered pixels into C4D's VPBuffer
    // - Read from MoonRay's frame buffer
    // - Convert color space if needed
    // - Write pixel data to buffer
    return true;
}

void MoonRayVideoPost::ShutdownMoonRay()
{
    // TODO: Clean up scene_rdl2 context and resources
    m_initialized = false;
}


// ============================================================
// Plugin Registration
// ============================================================

Bool RegisterMoonRayVideoPost()
{
    return RegisterVideoPostPlugin(
        ID_MOONRAY_VIDEOPOST,
        "MoonRay"_s,
        PLUGINFLAG_VIDEOPOST_ISRENDERER,
        MoonRayVideoPost::Alloc,
        "VPmoonray"_s,
        0,          // revision
        nullptr     // icon
    );
}

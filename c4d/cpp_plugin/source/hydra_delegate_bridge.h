/**
 * MoonRay Hydra Delegate Bridge for Cinema 4D
 * =============================================
 * Provides a C++ interface between Cinema 4D's rendering pipeline
 * and MoonRay's Hydra render delegate (hdMoonray).
 *
 * The bridge creates an in-memory USD stage from the Cinema 4D
 * document, instantiates a UsdImagingGLEngine with the hdMoonray
 * delegate, and copies the rendered pixels back into Cinema 4D's
 * frame buffer.
 *
 * Copyright 2024-2026 - Apache License 2.0
 */

#ifndef HYDRA_DELEGATE_BRIDGE_H__
#define HYDRA_DELEGATE_BRIDGE_H__

#include "c4d.h"

#ifdef MOONRAY_AVAILABLE

#include <pxr/pxr.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/xformable.h>
#include <pxr/usd/usdLux/sphereLight.h>
#include <pxr/usd/usdLux/rectLight.h>
#include <pxr/usd/usdLux/distantLight.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/gf/vec4d.h>

PXR_NAMESPACE_USING_DIRECTIVE

#endif // MOONRAY_AVAILABLE

/**
 * Hydra render delegate bridge for Cinema 4D.
 *
 * Manages the lifecycle of:
 *   - An in-memory USD stage built from the Cinema 4D document.
 *   - A UsdImagingGLEngine configured with the hdMoonray delegate.
 *   - Pixel transfer from the Hydra AOV buffer to a C4D VPBuffer.
 */
class HydraDelegateBridge
{
public:
    HydraDelegateBridge();
    ~HydraDelegateBridge();

    /**
     * Check whether the Hydra delegate libraries are available at
     * runtime. Returns false if the plugin was built without
     * MOONRAY_AVAILABLE or if hdMoonray cannot be loaded.
     */
    static Bool IsAvailable();

    /**
     * Build an in-memory USD stage from the Cinema 4D document.
     *
     * @param doc     The active Cinema 4D document.
     * @param node    The VideoPost node (for reading render settings).
     * @return True on success.
     */
    Bool BuildStage(BaseDocument* doc, BaseVideoPost* node);

    /**
     * Execute a blocking Hydra render.
     *
     * @param width   Render width in pixels.
     * @param height  Render height in pixels.
     * @param thread  Thread for cancellation checks (may be nullptr).
     * @return True on success.
     */
    Bool Render(Int32 width, Int32 height, BaseThread* thread);

    /**
     * Copy the rendered pixels into a Cinema 4D VPBuffer.
     *
     * @param buffer  Target buffer (e.g. VPBUF_RGBA).
     * @param width   Buffer width.
     * @param height  Buffer height.
     * @return True on success.
     */
    Bool ReadPixels(VPBuffer* buffer, Int32 width, Int32 height);

    /** Release all Hydra and USD resources. */
    void Shutdown();

private:
    // Scene export helpers
    Bool ExportCamera(BaseDocument* doc);
    Bool ExportLights(BaseDocument* doc);
    Bool ExportGeometry(BaseDocument* doc);
    Bool ExportMesh(BaseObject* obj, Int32 index);

    // Initialise the Hydra engine and select hdMoonray
    Bool InitEngine();

    // Apply render settings from the VideoPost node
    void ApplySettings(BaseVideoPost* node);

#ifdef MOONRAY_AVAILABLE
    // USD / Hydra members
    UsdStageRefPtr                              m_stage;
    std::unique_ptr<UsdImagingGLEngine>         m_engine;
    std::vector<float>                          m_pixelBuffer;
#endif

    Float m_sceneScale;
    Bool  m_initialized;
};

#endif // HYDRA_DELEGATE_BRIDGE_H__

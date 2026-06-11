/**
 * MoonRay VideoPost Description IDs
 * ====================================
 * Parameter IDs for the MoonRay render settings UI.
 */

#ifndef VPMOONRAY_H__
#define VPMOONRAY_H__

enum
{
    // ---- Quality ----
    MOONRAY_SETTINGS_GROUP          = 10000,
    MOONRAY_QUALITY_GROUP           = 10001,
    MOONRAY_SAMPLES_PER_PIXEL       = 10010,
    MOONRAY_MAX_DEPTH               = 10011,
    MOONRAY_LIGHT_SAMPLES           = 10012,
    MOONRAY_PIXEL_FILTER            = 10013,
    MOONRAY_PIXEL_FILTER_WIDTH      = 10014,
    MOONRAY_ADAPTIVE_SAMPLING       = 10015,
    MOONRAY_ADAPTIVE_THRESHOLD      = 10016,

    // ---- Denoising ----
    MOONRAY_DENOISE_GROUP           = 10100,
    MOONRAY_DENOISE_ENABLED         = 10101,
    MOONRAY_DENOISE_TYPE            = 10102,

    // ---- Execution ----
    MOONRAY_EXECUTION_GROUP         = 10200,
    MOONRAY_EXEC_MODE               = 10201,
    MOONRAY_EXEC_PATH               = 10202,
    MOONRAY_THREADS                 = 10203,
    MOONRAY_ARRAS_HOST              = 10204,
    MOONRAY_ARRAS_PORT              = 10205,
    MOONRAY_OUTPUT_FORMAT           = 10206,

    // ---- Scene ----
    MOONRAY_SCENE_GROUP             = 10300,
    MOONRAY_SCENE_SCALE             = 10301,
    MOONRAY_MOTION_BLUR             = 10302,
    MOONRAY_MOTION_STEPS            = 10303,

    // ---- Pixel Filter Types ----
    MOONRAY_FILTER_BOX              = 0,
    MOONRAY_FILTER_GAUSSIAN         = 1,
    MOONRAY_FILTER_MITCHELL         = 2,

    // ---- Denoiser Types ----
    MOONRAY_DENOISE_OIDN            = 0,
    MOONRAY_DENOISE_OPTIX           = 1,

    // ---- Execution Modes ----
    MOONRAY_EXEC_LOCAL              = 0,
    MOONRAY_EXEC_ARRAS              = 1,

    // ---- Output Formats ----
    MOONRAY_OUTPUT_EXR              = 0,
    MOONRAY_OUTPUT_PNG              = 1,
};

#endif // VPMOONRAY_H__

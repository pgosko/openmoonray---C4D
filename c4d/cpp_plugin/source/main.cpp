/**
 * MoonRay Plugin for Cinema 4D - Main Entry Point
 * =================================================
 */

#include "c4d.h"

// Forward declarations
extern Bool RegisterMoonRayVideoPost();

Bool PluginStart()
{
    if (!RegisterMoonRayVideoPost())
        return false;

    GePrint("[MoonRay] Plugin loaded successfully"_s);
    return true;
}

void PluginEnd()
{
    GePrint("[MoonRay] Plugin unloaded"_s);
}

Bool PluginMessage(Int32 id, void* data)
{
    switch (id)
    {
        case C4DPL_INIT_SYS:
            return true;

        case C4DPL_BUILDMENU:
            break;

        case C4DPL_ENDACTIVITY:
            break;
    }

    return true;
}

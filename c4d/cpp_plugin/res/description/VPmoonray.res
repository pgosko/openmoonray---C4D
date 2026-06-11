CONTAINER VPmoonray
{
    NAME VPmoonray;

    GROUP MOONRAY_QUALITY_GROUP
    {
        DEFAULT 1;

        LONG MOONRAY_SAMPLES_PER_PIXEL
        {
            MIN 1;
            MAX 4096;
            STEP 1;
        }
        LONG MOONRAY_MAX_DEPTH
        {
            MIN 1;
            MAX 128;
            STEP 1;
        }
        LONG MOONRAY_LIGHT_SAMPLES
        {
            MIN 1;
            MAX 256;
            STEP 1;
        }
        LONG MOONRAY_PIXEL_FILTER
        {
            CYCLE
            {
                MOONRAY_FILTER_BOX;
                MOONRAY_FILTER_GAUSSIAN;
                MOONRAY_FILTER_MITCHELL;
            }
        }
        REAL MOONRAY_PIXEL_FILTER_WIDTH
        {
            MIN 0.5;
            MAX 8.0;
            STEP 0.1;
            UNIT REAL;
        }
        BOOL MOONRAY_ADAPTIVE_SAMPLING {}
        REAL MOONRAY_ADAPTIVE_THRESHOLD
        {
            MIN 0.001;
            MAX 1.0;
            STEP 0.001;
            UNIT REAL;
        }
    }

    GROUP MOONRAY_DENOISE_GROUP
    {
        DEFAULT 1;

        BOOL MOONRAY_DENOISE_ENABLED {}
        LONG MOONRAY_DENOISE_TYPE
        {
            CYCLE
            {
                MOONRAY_DENOISE_OIDN;
                MOONRAY_DENOISE_OPTIX;
            }
        }
    }

    GROUP MOONRAY_EXECUTION_GROUP
    {
        DEFAULT 1;

        LONG MOONRAY_EXEC_MODE
        {
            CYCLE
            {
                MOONRAY_EXEC_LOCAL;
                MOONRAY_EXEC_ARRAS;
            }
        }
        FILENAME MOONRAY_EXEC_PATH {}
        LONG MOONRAY_THREADS
        {
            MIN 0;
            MAX 256;
            STEP 1;
        }
        STRING MOONRAY_ARRAS_HOST {}
        LONG MOONRAY_ARRAS_PORT
        {
            MIN 1;
            MAX 65535;
        }
        LONG MOONRAY_OUTPUT_FORMAT
        {
            CYCLE
            {
                MOONRAY_OUTPUT_EXR;
                MOONRAY_OUTPUT_PNG;
            }
        }
    }

    GROUP MOONRAY_SCENE_GROUP
    {
        DEFAULT 1;

        REAL MOONRAY_SCENE_SCALE
        {
            MIN 0.001;
            MAX 1000.0;
            STEP 0.01;
            UNIT REAL;
        }
        BOOL MOONRAY_MOTION_BLUR {}
        LONG MOONRAY_MOTION_STEPS
        {
            MIN 2;
            MAX 16;
            STEP 1;
        }
    }
}

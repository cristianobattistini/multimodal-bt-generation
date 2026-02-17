"""
RTX Rendering Configuration

Presets and configuration functions for OmniGibson/Isaac Sim rendering.
"""


# Rendering quality presets
# denoiser_blend: 0.0 = full denoiser (more blur), 1.0 = no denoiser (more noise)
RENDER_PRESETS = {
    "turbo": {
        "samples_per_pixel": 1,
        "denoiser_blend": 0.0,
        "max_bounces": 1,
        "render_mode": "RayTracedLighting",  # Much faster than PathTracing
        "resolution": 512,
        "taa_enabled": True,
    },
    "fast": {
        "samples_per_pixel": 8,
        "denoiser_blend": 0.2,
        "max_bounces": 2,
        "render_mode": "RayTracedLighting",
        "resolution": 512,
        "taa_enabled": True,
    },
    "balanced": {
        "samples_per_pixel": 32,
        "denoiser_blend": 0.09,
        "max_bounces": 4,
        "render_mode": "PathTracing",
        "resolution": 512,
        "taa_enabled": True,
    },
    "high": {
        "samples_per_pixel": 128,
        "denoiser_blend": 0.05,
        "max_bounces": 16,
        "render_mode": "PathTracing",
        "resolution": 512,
        "taa_enabled": True,
    },
    # New preset: Sharp - reduces blur from denoiser, disables TAA
    "sharp": {
        "samples_per_pixel": 64,
        "denoiser_blend": 0.5,  # Less denoising = sharper but more noise
        "max_bounces": 4,
        "render_mode": "PathTracing",
        "resolution": 512,
        "taa_enabled": False,  # Disable TAA to reduce motion blur
    },
    # New preset: Ultra sharp - minimal denoising for maximum detail
    "ultra_sharp": {
        "samples_per_pixel": 128,
        "denoiser_blend": 0.8,  # Almost no denoising
        "max_bounces": 8,
        "render_mode": "PathTracing",
        "resolution": 512,
        "taa_enabled": False,
    },
}


def configure_rtx_rendering(settings, args, is_headless=False, log_fn=print):
    """
    Configure RTX settings for quality rendering with denoising.

    Args:
        settings: carb.settings object from Isaac Sim
        args: Parsed arguments with render_quality, samples_per_pixel, enable_denoiser,
              and optional CLI overrides (spp, denoiser_blend, taa, render_mode, width, height)
        is_headless: Whether running in headless mode
        log_fn: Logging function (default: print)
    """
    preset = RENDER_PRESETS.get(args.render_quality, RENDER_PRESETS["balanced"])

    # CLI overrides with preset fallbacks
    # SPP: check --spp first, then --samples-per-pixel, then preset
    spp = getattr(args, 'spp', None) or getattr(args, 'samples_per_pixel', None) or preset["samples_per_pixel"]

    # Denoiser blend: CLI override or preset
    denoiser_blend = getattr(args, 'denoiser_blend', None)
    if denoiser_blend is None:
        denoiser_blend = preset["denoiser_blend"]

    # TAA: CLI override or preset
    taa_enabled = getattr(args, 'taa', None)
    if taa_enabled is None:
        taa_enabled = preset.get("taa_enabled", True)

    # Render mode: CLI override or preset
    render_mode = getattr(args, 'render_mode', None) or preset.get("render_mode", "PathTracing")

    # Resolution: CLI width/height override or preset
    width = getattr(args, 'width', None) or preset.get("resolution", 512)
    height = getattr(args, 'height', None) or preset.get("resolution", 512)

    max_bounces = preset["max_bounces"]

    # Log all effective values upfront
    log_fn(f"[RTX] Effective settings: spp={spp}, denoiser_blend={denoiser_blend}, "
           f"taa={taa_enabled}, mode={render_mode}, resolution={width}x{height}")

    # Resolution
    if is_headless:
        settings.set("/app/renderer/resolution/width", width)
        settings.set("/app/renderer/resolution/height", height)
    else:
        # In GUI mode, use CLI overrides if provided, else fixed 1280x720
        gui_width = getattr(args, 'width', None) or 1280
        gui_height = getattr(args, 'height', None) or 720
        settings.set("/app/renderer/resolution/width", gui_width)
        settings.set("/app/renderer/resolution/height", gui_height)

    # Render mode - RayTracedLighting is much faster, PathTracing for quality
    settings.set("/rtx/rendermode", render_mode)
    log_fn(f"[RTX] Render mode: {render_mode}")

    # Anti-aliasing (TAA) - can cause blur/ghosting when enabled
    # 0 = off, 1 = FXAA, 2 = TAA, 3 = DLAA
    if taa_enabled:
        settings.set("/rtx/post/aa/op", 2)  # TAA
        log_fn("[RTX] TAA anti-aliasing: enabled")
    else:
        settings.set("/rtx/post/aa/op", 0)  # Disabled for sharper image
        log_fn("[RTX] TAA anti-aliasing: disabled (sharper)")

    # DENOISER - key for removing noise!
    # denoiser_blend: 0.0 = full denoiser (smooth/blur), 1.0 = no denoiser (noise)
    if args.enable_denoiser:
        settings.set("/rtx/pathtracing/optixDenoiser/enabled", True)
        settings.set("/rtx/pathtracing/optixDenoiser/blendFactor", denoiser_blend)
        log_fn(f"[RTX] OptiX denoiser enabled (blend: {denoiser_blend}, higher=sharper)")
    else:
        settings.set("/rtx/pathtracing/optixDenoiser/enabled", False)
        log_fn("[RTX] Denoiser disabled")

    # Samples per pixel (higher = less noise, allows less aggressive denoising)
    settings.set("/rtx/pathtracing/spp", spp)
    settings.set("/rtx/pathtracing/totalSpp", spp)
    log_fn(f"[RTX] Samples per pixel: {spp}")

    # Lighting quality
    settings.set("/rtx/pathtracing/maxBounces", max_bounces)
    settings.set("/rtx/reflections/enabled", True)
    settings.set("/rtx/indirectDiffuse/enabled", True)
    settings.set("/rtx/ambientOcclusion/enabled", True)
    settings.set("/rtx/directLighting/sampledLighting/enabled", True)

    # Firefly filter to reduce bright pixel noise
    settings.set("/rtx/pathtracing/fireflyFilter/maxIntensityPerSample", 10000)
    settings.set("/rtx/pathtracing/fireflyFilter/maxIntensityPerSampleDiffuse", 50000)

    # Sharpening post-process (helps counter denoiser blur)
    # Only for sharp presets
    if "sharp" in args.render_quality:
        settings.set("/rtx/post/sharpen/enabled", True)
        settings.set("/rtx/post/sharpen/intensity", 0.3)
        log_fn("[RTX] Post-process sharpening: enabled (0.3)")

    # Semantic schema for object detection
    settings.set("/rtx/hydra/enableSemanticSchema", True)

    log_fn(f"[RTX] Rendering configured: preset={args.render_quality}, spp={spp}, bounces={max_bounces}")

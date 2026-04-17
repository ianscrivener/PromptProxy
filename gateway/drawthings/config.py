"""FlatBuffer config builder for Draw Things GenerationConfiguration.

Mirrors the TypeScript config.ts — builds a FlatBuffer from a plain dict.
"""

import sys
import random
import flatbuffers


from gateway.drawthings.generated import GenerationConfiguration as GC
from gateway.drawthings.generated import LoRA as LoRAFB
from gateway.drawthings.generated import Control as ControlFB
from gateway.drawthings.generated import SamplerType, SeedMode, ControlMode, ControlInputType

# ── Default config (same as Draw Things app defaults) ──────────────────────

DEFAULT_CONFIG = {
    "preserve_original_after_inpaint": True,
    "batch_count": 1,
    "seed": -1,
    "batch_size": 1,
    "shift": 1.0,
    "model": "z_image_turbo_1.0_i8x.ckpt",
    "height": 512,
    "tiled_diffusion": False,
    "diffusion_tile_height": 1024,
    "diffusion_tile_width": 1024,
    "diffusion_tile_overlap": 128,
    "sampler": SamplerType.SamplerType.DPMPP2MKarras,
    "hires_fix": False,
    "strength": 1.0,
    "steps": 20,
    "tiled_decoding": False,
    "decoding_tile_height": 640,
    "decoding_tile_width": 640,
    "decoding_tile_overlap": 128,
    "loras": [],
    "width": 512,
    "guidance_scale": 4.5,
    "mask_blur": 1.5,
    "seed_mode": SeedMode.SeedMode.ScaleAlike,
    "sharpness": 0.0,
    "clip_skip": 1,
    "controls": [],
    "mask_blur_outset": 0,
    "negative_original_image_height": 512,
    "negative_original_image_width": 512,
    "original_image_height": 512,
    "original_image_width": 512,
    "refiner_start": 0.85,
    "target_image_height": 512,
    "target_image_width": 512,
}


def _round64(v, minimum=64):
    return max(round(v / 64) * 64, minimum)


def _build_lora(builder, lora):
    file_off = builder.CreateString(lora["file"])
    LoRAFB.LoRAStart(builder)
    LoRAFB.LoRAAddFile(builder, file_off)
    LoRAFB.LoRAAddWeight(builder, lora.get("weight", 0.8))
    return LoRAFB.LoRAEnd(builder)


def _build_control(builder, ctrl):
    file_off = builder.CreateString(ctrl["file"])
    tb = ctrl.get("target_blocks", [])
    tb_offsets = [builder.CreateString(s) for s in tb]
    if tb_offsets:
        ControlFB.ControlStartTargetBlocksVector(builder, len(tb_offsets))
        for o in reversed(tb_offsets):
            builder.PrependUOffsetTRelative(o)
        tb_vec = builder.EndVector()
    else:
        tb_vec = None

    ControlFB.ControlStart(builder)
    ControlFB.ControlAddFile(builder, file_off)
    ControlFB.ControlAddWeight(builder, ctrl.get("weight", 1.0))
    ControlFB.ControlAddGuidanceStart(builder, ctrl.get("guidance_start", 0.0))
    ControlFB.ControlAddGuidanceEnd(builder, ctrl.get("guidance_end", 1.0))
    ControlFB.ControlAddNoPrompt(builder, ctrl.get("no_prompt", False))
    ControlFB.ControlAddGlobalAveragePooling(builder, ctrl.get("global_average_pooling", False))
    ControlFB.ControlAddDownSamplingRate(builder, ctrl.get("down_sampling_rate", 1.0))
    ControlFB.ControlAddControlMode(builder, ctrl.get("control_mode", ControlMode.ControlMode.Balanced))
    if tb_vec is not None:
        ControlFB.ControlAddTargetBlocks(builder, tb_vec)
    ControlFB.ControlAddInputOverride(builder, ctrl.get("input_override", ControlInputType.ControlInputType.Inpaint))
    return ControlFB.ControlEnd(builder)


def build_config_buffer(config=None):
    """Build a FlatBuffer-encoded GenerationConfiguration from a config dict.

    Keys use snake_case. Missing keys fall back to DEFAULT_CONFIG.
    Returns bytes suitable for the ImageGenerationRequest.configuration field.
    """
    c = {**DEFAULT_CONFIG, **(config or {})}

    width = _round64(c.get("width") or c.get("start_width") or 512)
    height = _round64(c.get("height") or c.get("start_height") or 512)

    seed = c["seed"]
    if seed is None or seed < 0:
        seed = random.randint(0, 0xFFFFFFFF)

    builder = flatbuffers.Builder(2048)

    # Pre-create strings and nested tables (must happen before Start)
    model_off = builder.CreateString(c.get("model") or "")
    upscaler_value = c.get("upscaler") or ""
    face_restoration_value = c.get("face_restoration") or ""
    upscaler_off = builder.CreateString(upscaler_value) if upscaler_value else None
    face_restoration_off = builder.CreateString(face_restoration_value) if face_restoration_value else None
    refiner_model_off = builder.CreateString(c.get("refiner_model") or "")
    name_off = builder.CreateString(c.get("name") or "")
    clip_l_text_off = builder.CreateString(c.get("clip_l_text") or "")
    open_clip_g_text_off = builder.CreateString(c.get("open_clip_g_text") or "")
    t5_text_off = builder.CreateString(c.get("t5_text") or "")

    # Build LoRA vector
    loras = c.get("loras") or []
    lora_offsets = [_build_lora(builder, l) for l in loras]
    if lora_offsets:
        GC.GenerationConfigurationStartLorasVector(builder, len(lora_offsets))
        for o in reversed(lora_offsets):
            builder.PrependUOffsetTRelative(o)
        loras_vec = builder.EndVector()
    else:
        loras_vec = None

    # Build Controls vector
    controls = c.get("controls") or []
    ctrl_offsets = [_build_control(builder, ct) for ct in controls]
    if ctrl_offsets:
        GC.GenerationConfigurationStartControlsVector(builder, len(ctrl_offsets))
        for o in reversed(ctrl_offsets):
            builder.PrependUOffsetTRelative(o)
        controls_vec = builder.EndVector()
    else:
        controls_vec = None

    # Build main table
    GC.GenerationConfigurationStart(builder)
    GC.GenerationConfigurationAddId(builder, c.get("id", 0))
    GC.GenerationConfigurationAddStartWidth(builder, width // 64)
    GC.GenerationConfigurationAddStartHeight(builder, height // 64)
    GC.GenerationConfigurationAddSeed(builder, seed)
    GC.GenerationConfigurationAddSteps(builder, c.get("steps", 20))
    GC.GenerationConfigurationAddGuidanceScale(builder, c.get("guidance_scale", 4.5))
    GC.GenerationConfigurationAddStrength(builder, c.get("strength", 1.0))
    GC.GenerationConfigurationAddModel(builder, model_off)
    GC.GenerationConfigurationAddSampler(builder, c.get("sampler", 0))
    GC.GenerationConfigurationAddBatchCount(builder, c.get("batch_count", 1))
    GC.GenerationConfigurationAddBatchSize(builder, c.get("batch_size", 1))
    GC.GenerationConfigurationAddHiresFix(builder, c.get("hires_fix", False))
    GC.GenerationConfigurationAddHiresFixStartWidth(builder, _round64(c.get("hires_fix_start_width", 512)) // 64)
    GC.GenerationConfigurationAddHiresFixStartHeight(builder, _round64(c.get("hires_fix_start_height", 512)) // 64)
    GC.GenerationConfigurationAddHiresFixStrength(builder, c.get("hires_fix_strength", 0.7))
    if upscaler_off is not None:
        GC.GenerationConfigurationAddUpscaler(builder, upscaler_off)
    GC.GenerationConfigurationAddImageGuidanceScale(builder, c.get("image_guidance_scale", 1.5))
    GC.GenerationConfigurationAddSeedMode(builder, c.get("seed_mode", 2))
    GC.GenerationConfigurationAddClipSkip(builder, c.get("clip_skip", 1))
    if controls_vec is not None:
        GC.GenerationConfigurationAddControls(builder, controls_vec)
    if loras_vec is not None:
        GC.GenerationConfigurationAddLoras(builder, loras_vec)
    GC.GenerationConfigurationAddMaskBlur(builder, c.get("mask_blur", 1.5))
    if face_restoration_off is not None:
        GC.GenerationConfigurationAddFaceRestoration(builder, face_restoration_off)
    GC.GenerationConfigurationAddClipWeight(builder, c.get("clip_weight", 1.0))
    GC.GenerationConfigurationAddNegativePromptForImagePrior(builder, c.get("negative_prompt_for_image_prior", True))
    GC.GenerationConfigurationAddImagePriorSteps(builder, c.get("image_prior_steps", 5))
    GC.GenerationConfigurationAddRefinerModel(builder, refiner_model_off)
    GC.GenerationConfigurationAddOriginalImageHeight(builder, c.get("original_image_height", height))
    GC.GenerationConfigurationAddOriginalImageWidth(builder, c.get("original_image_width", width))
    GC.GenerationConfigurationAddCropTop(builder, c.get("crop_top", 0))
    GC.GenerationConfigurationAddCropLeft(builder, c.get("crop_left", 0))
    GC.GenerationConfigurationAddTargetImageHeight(builder, c.get("target_image_height", height))
    GC.GenerationConfigurationAddTargetImageWidth(builder, c.get("target_image_width", width))
    GC.GenerationConfigurationAddAestheticScore(builder, c.get("aesthetic_score", 6.0))
    GC.GenerationConfigurationAddNegativeAestheticScore(builder, c.get("negative_aesthetic_score", 2.5))
    GC.GenerationConfigurationAddZeroNegativePrompt(builder, c.get("zero_negative_prompt", False))
    GC.GenerationConfigurationAddRefinerStart(builder, c.get("refiner_start", 0.85))
    GC.GenerationConfigurationAddNegativeOriginalImageHeight(builder, c.get("negative_original_image_height", height))
    GC.GenerationConfigurationAddNegativeOriginalImageWidth(builder, c.get("negative_original_image_width", width))
    GC.GenerationConfigurationAddName(builder, name_off)
    GC.GenerationConfigurationAddFpsId(builder, c.get("fps_id", 5))
    GC.GenerationConfigurationAddMotionBucketId(builder, c.get("motion_bucket_id", 127))
    GC.GenerationConfigurationAddCondAug(builder, c.get("cond_aug", 0.02))
    GC.GenerationConfigurationAddStartFrameCfg(builder, c.get("start_frame_cfg", 1.0))
    GC.GenerationConfigurationAddNumFrames(builder, c.get("num_frames", 14))
    GC.GenerationConfigurationAddMaskBlurOutset(builder, c.get("mask_blur_outset", 0))
    GC.GenerationConfigurationAddSharpness(builder, c.get("sharpness", 0.0))
    GC.GenerationConfigurationAddShift(builder, c.get("shift", 1.0))
    GC.GenerationConfigurationAddStage2Steps(builder, c.get("stage_2_steps", 10))
    GC.GenerationConfigurationAddStage2Cfg(builder, c.get("stage_2_cfg", 1.0))
    GC.GenerationConfigurationAddStage2Shift(builder, c.get("stage_2_shift", 1.0))
    GC.GenerationConfigurationAddTiledDecoding(builder, c.get("tiled_decoding", False))
    GC.GenerationConfigurationAddDecodingTileWidth(builder, _round64(c.get("decoding_tile_width", 512)) // 64)
    GC.GenerationConfigurationAddDecodingTileHeight(builder, _round64(c.get("decoding_tile_height", 512)) // 64)
    GC.GenerationConfigurationAddDecodingTileOverlap(builder, _round64(c.get("decoding_tile_overlap", 512)) // 64)
    GC.GenerationConfigurationAddStochasticSamplingGamma(builder, c.get("stochastic_sampling_gamma", 0.3))
    GC.GenerationConfigurationAddPreserveOriginalAfterInpaint(builder, c.get("preserve_original_after_inpaint", True))
    GC.GenerationConfigurationAddTiledDiffusion(builder, c.get("tiled_diffusion", False))
    GC.GenerationConfigurationAddDiffusionTileWidth(builder, _round64(c.get("diffusion_tile_width", 512)) // 64)
    GC.GenerationConfigurationAddDiffusionTileHeight(builder, _round64(c.get("diffusion_tile_height", 512)) // 64)
    GC.GenerationConfigurationAddDiffusionTileOverlap(builder, _round64(c.get("diffusion_tile_overlap", 512)) // 64)
    GC.GenerationConfigurationAddUpscalerScaleFactor(builder, c.get("upscaler_scale_factor", 0))
    GC.GenerationConfigurationAddT5TextEncoder(builder, c.get("t5_text_encoder", True))
    GC.GenerationConfigurationAddSeparateClipL(builder, c.get("separate_clip_l", False))
    GC.GenerationConfigurationAddClipLText(builder, clip_l_text_off)
    GC.GenerationConfigurationAddSeparateOpenClipG(builder, c.get("separate_open_clip_g", False))
    GC.GenerationConfigurationAddOpenClipGText(builder, open_clip_g_text_off)
    GC.GenerationConfigurationAddSpeedUpWithGuidanceEmbed(builder, c.get("speed_up_with_guidance_embed", True))
    GC.GenerationConfigurationAddGuidanceEmbed(builder, c.get("guidance_embed", 3.5))
    GC.GenerationConfigurationAddResolutionDependentShift(builder, c.get("resolution_dependent_shift", True))

    root = GC.GenerationConfigurationEnd(builder)
    builder.Finish(root)
    return bytes(builder.Output())

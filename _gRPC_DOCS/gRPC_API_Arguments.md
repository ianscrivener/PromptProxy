# gRPC API Arguments

Exact `GenerationConfiguration` arguments accepted by the Draw Things gRPC API, with line numbers in column 1 and matching skill CLI arguments in column 2.

| # | Skill Arg | gRPC Arg |Notes|Default|
| --: | -- | -- | --| -- |
| 1 |  | id |||
| 2 | --width | start_width |||
| 3 | --height | start_height |||
| 4 | --seed | seed ||-1|
| 5 | --steps | steps |||
| 6 | --guidance | guidance_scale |||
| 7 | --strength | strength |*for img2img*||
| 8 | --model | model |||
| 9 | --sampler | sampler | |"UniPC"|
| 10 |  | batch_count | |1|
| 11 |  | batch_size ||1|
| 12 |  | hires_fix |||
| 13 |  | hires_fix_start_width |||
| 14 |  | hires_fix_start_height |||
| 15 |  | hires_fix_strength |||
| 16 | --upscaler | upscaler |||
| 17 |  | image_guidance_scale |||
| 18 |  | seed_mode |||
| 19 | --clip_skip | clip_skip ||1|
| 20 |  | controls |||
| 21 |  | loras |||
| 22 | --mask_blur | mask_blur ||1.5|
| 23 | --facefix / --face-restore | face_restoration |||
| 24 |  | decode_with_attention |||
| 25 |  | hires_fix_decode_with_attention |||
| 26 |  | clip_weight |||
| 27 |  | negative_prompt_for_image_prior |||
| 28 |  | image_prior_steps |||
| 29 |  | refiner_model |||
| 30 |  | original_image_height |||
| 31 |  | original_image_width |||
| 32 |  | crop_top |||
| 33 |  | crop_left |||
| 34 |  | target_image_height |||
| 35 |  | target_image_width |||
| 36 |  | aesthetic_score |||
| 37 |  | negative_aesthetic_score |||
| 38 |  | zero_negative_prompt |||
| 39 |  | refiner_start |||
| 40 |  | negative_original_image_height |||
| 41 |  | negative_original_image_width |||
| 42 |  | name |||
| 43 |  | fps_id |||
| 44 |  | motion_bucket_id |||
| 45 |  | cond_aug |||
| 46 |  | start_frame_cfg |||
| 47 |  | num_frames |||
| 48 |  | mask_blur_outset |||
| 49 | --sharpness | sharpness ||3.5 |
| 50 | --shift | shift ||2.8|
| 51 |  | stage_2_steps |||
| 52 |  | stage_2_cfg |||
| 53 |  | stage_2_shift |||
| 54 |  | tiled_decoding |||
| 55 |  | decoding_tile_width |||
| 56 |  | decoding_tile_height |||
| 57 |  | decoding_tile_overlap |||
| 58 |  | stochastic_sampling_gamma |||
| 59 |  | preserve_original_after_inpaint |||
| 60 |  | tiled_diffusion |||
| 61 |  | diffusion_tile_width |||
| 62 |  | diffusion_tile_height |||
| 63 |  | diffusion_tile_overlap |||
| 64 | --upscale-factor | upscaler_scale_factor |||
| 65 |  | t5_text_encoder |||
| 66 |  | separate_clip_l |||
| 67 |  | clip_l_text |||
| 68 |  | separate_open_clip_g |||
| 69 |  | open_clip_g_text |||
| 70 |  | speed_up_with_guidance_embed |||
| 71 |  | guidance_embed |||
| 72 |  | resolution_dependent_shift |||
| 73 |  | tea_cache_start |||
| 74 |  | tea_cache_end |||
| 75 |  | tea_cache_threshold |||
| 76 |  | tea_cache |||
| 77 |  | separate_t5 |||
| 78 |  | t5_text |||
| 79 |  | tea_cache_max_skip_steps |||
| 80 |  | causal_inference_enabled |||
| 81 |  | causal_inference |||
| 82 |  | causal_inference_pad |||


**Table Rules** 
1. If there is no value, leave the column empty 


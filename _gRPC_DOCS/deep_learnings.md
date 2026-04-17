# Deep Learnings: Draw Things Decode Failures (April 2026)

## Executive Summary
The observed error:

`Draw Things did not return a decodable final image (no image tensors returned)`

was primarily caused by an incompatible sampler/model combination in runtime behavior (not a generic decoder bug):

- `sampler=UniPC`
- model family: `z_image` variants, including `jibmix_zit_v1.0_fp16_f16.ckpt`

In this configuration, the server frequently emitted sampling progress and preview frames but did not emit final `generatedImages` frames (`imageDecoded` stage absent).

## What Was Reproduced

### Failing request pattern
Using the provided request (long prompt, `jibmix_zit_v1.0_fp16_f16.ckpt`, `UniPC`) reproduced failure consistently.

### Minimal reproduction
Even short prompts such as `a photo of a beach` could fail under the same sampler/model pairing.

### Stream-level evidence
Direct gRPC stream inspection showed:

- repeated `currentSignpost=sampling`
- `previewImage` frames present (often)
- `generatedImages` absent in failed runs
- no final `imageDecoded` signpost in failed runs

## Critical Root Cause Learnings

1. Sampler-model compatibility matters operationally
- `UniPC` can be unsupported/unstable for some model variants in practical runtime behavior.
- For JIB/Z-Image-family models, trailing samplers are safer.

2. `previewImage` is not guaranteed to be final RGB output
- Preview payloads can be latent-space tensors (for example, channel count 16).
- Attempting to decode preview payloads as final output with the standard image decoder fails.

3. Server can appear healthy while generation result is incomplete
- gRPC connection, progress signposts, and preview updates may all look normal.
- Final image payload can still be missing.

4. Request-level parameter semantics can silently alter behavior
- Passing `--upscaler None` as a string can be interpreted as a literal model name unless normalized.

## False Leads / Non-Root Issues Encountered

1. Path expansion issue from command file execution
- Executing `$(cat /tmp/command.txt)` preserved literal `~` and failed path resolution.
- Not the decode root cause.

2. Temporary server connectivity interruptions
- At one point, `localhost:7859` returned `Connection refused`.
- This is an availability issue, separate from the sampler compatibility issue.

3. Output filename collision concern
- Addressed separately by forced timestamp naming.
- Not responsible for decode failure.

## Verified Practical Guidance

### Recommended sampler strategy for these models
- Prefer trailing samplers for JIB/Z-Image models.
- Good defaults to try first:
  - `DPMPP2MTrailing`
  - then `DPMPP2MKarras` if needed

### Avoid using `UniPC` as default for JIB/Z-Image
- Treat as opt-in only after successful validation on a specific model/server setup.

### Keep diagnostics in this order
1. Check server availability (`host:port` reachable)
2. Confirm model is present via `list_assets.py --type models`
3. Run a minimal prompt with a known-safe sampler
4. Only then test richer prompts/settings

## Script / Operational Learnings

1. Deployment/setup script should run setup in deployed destination
- Running setup only in source repo can leave deployed skill without `.venv`.

2. `check_env.py` should be diagnostic before setup
- Non-ready from `check_env.py` is expected before first setup.
- Do not treat that pre-setup signal as hard failure.

3. Robust destination cleanup needed
- `shutil.rmtree` can fail on some `.venv` contents; fallback to `rm -rf` improved reliability.

## Current Team Rule to Carry Forward
For JIB/Z-Image-family generation jobs:

- Do not default to `UniPC`.
- Prefer trailing samplers (`DPMPP2MTrailing`) unless explicitly validated otherwise.

## Suggested Future Hardening (Backlog)

1. Model-aware sampler policy
- Build an explicit compatibility map by model `version` metadata (for example: `z_image`, `qwen_image`, `sdxl_base_v0.9`).

2. Better error messaging
- If no `generatedImages` and only preview frames were seen, emit a targeted message:
  - `No final image returned. Try a trailing sampler (e.g., DPMPP2MTrailing).`

3. Telemetry for generation outcomes
- Log signpost sequence and final payload presence to quickly detect sampler incompatibility patterns.

4. Deterministic fallback policy (optional)
- If user requested an incompatible sampler and server returns no final image, optionally retry once with a safe sampler and report retry transparently.

## One-Line Conclusion
This failure class is best treated as a model/sampler runtime compatibility issue first, and a decoding issue second.
# Sampler API and Compatibility Notes

## Summary
This document captures what we verified about sampler discovery and model/sampler compatibility behavior in the Draw Things gRPC integration.

## What the API Provides

1. There is no dedicated Draw Things API endpoint that returns samplers from server runtime metadata.
2. There is no dedicated API endpoint that returns model+sampler compatibility pairs.
3. In this skill, sampler entries are currently constructed locally from enum definitions, not fetched from a server compatibility matrix.

## Where Samplers Come From in the Skill

- Sampler list is defined in `drawthings-agent-skill/src/drawthings/service.py` via `SAMPLER_OPTIONS`.
- Samplers are surfaced through `drawthings-agent-skill/src/drawthings/list_assets.py` (`--type samplers`).
- Enum source is `drawthings-agent-skill/assets/fbs/config.fbs` and generated SamplerType code.

## Why Frontend and Skill Names Can Differ

The frontend may use display aliases that do not exactly match gRPC enum names.

Example:
- gRPC enum includes `DPMPP2MTrailing` (id 15), displayed by the skill as `DPM++ 2M Trailing`.
- There is no separate `UniPCTrailing` enum value in the current schema.
- If UI shows a name like "UniPC Trailing", that is likely a UI alias or grouping label, not a distinct gRPC sampler id.

## Verified Deployed Sampler Output

The deployed skill currently returns 17 samplers (ids 0-16), including:
- `UniPC` (id 5)
- `DPM++ 2M Trailing` (id 15)

## Can We Filter Samplers by Model in One Call?

Not with the current API surface.

- `list_assets --type samplers` does not accept a model filter from server metadata.
- Generation requests do accept a model, but compatibility is effectively discovered at runtime.

## Practical Compatibility Reality

Different models may behave differently with the same sampler. Some combinations may:
- return full final images,
- return only preview frames,
- or fail to return decodable final image payloads.

So compatibility is currently empirical/behavioral, not explicitly declared by API metadata.

## Recommended Approach

1. Maintain a local compatibility cache/map per model version.
2. Probe combinations using small low-cost generation requests.
3. Prefer known-safe sampler defaults for each model family.
4. Provide actionable fallback behavior when no final image is returned.

## Suggested Future Enhancement

Add a skill-level probe utility such as:
- `list_compatible_samplers --model <model_file>`

Implementation idea:
- Try each sampler with a tiny prompt + small resolution + low steps.
- Mark sampler as compatible if at least one final decodable image is returned.
- Cache results per model and environment to avoid repeated probing cost.

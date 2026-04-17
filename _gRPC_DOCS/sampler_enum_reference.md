# Sampler Enum Reference

Canonical sampler enum mapping used by the skill.

Source of truth:
- drawthings-agent-skill/assets/fbs/config.fbs (`enum SamplerType`)
- drawthings-agent-skill/src/drawthings/generated/SamplerType.py

| ID | Enum Name | Display Name | Frontend Label |
| --: | -- | -- | -- |
| 0 | DPMPP2MKarras | DPM++ 2M Karras | DPM++ 2M Karras |
| 1 | EulerA | Euler A | Euler Ancestral |
| 2 | DDIM | DDIM | DDIM |
| 3 | PLMS | PLMS | PLMS |
| 4 | DPMPPSDEKarras | DPM++ SDE Karras | DPM++ SDE Karras |
| 5 | UniPC | UniPC | UniPC |
| 6 | LCM | LCM | LCM |
| 7 | EulerASubstep | Euler A Substep | Euler A Substep |
| 8 | DPMPPSDESubstep | DPM++ SDE Substep | DPM++ SDE Substep |
| 9 | TCD | TCD | TCD |
| 10 | EulerATrailing | Euler A Trailing | Euler A Trailing |
| 11 | DPMPPSDETrailing | DPM++ SDE Trailing | DPM++ SDE Trailing |
| 12 | DPMPP2MAYS | DPM++ 2M AYS | DPM++ 2M AYS |
| 13 | EulerAAYS | Euler A AYS | Euler A AYS |
| 14 | DPMPPSDEAYS | DPM++ SDE AYS | DPM++ SDE AYS |
| 15 | DPMPP2MTrailing | DPM++ 2M Trailing | DPM++ 2M Trailing |
| 16 | DDIMTrailing | DDIM Trailing | DDIM Trailing |
|  |  |  | TCD Trailing (frontend only, no enum value) |
|  |  |  | UniPC Trailing (frontend only, no enum value) |
|  |  |  | UniPC AYS (frontend only, no enum value) |

## Notes

- Frontend-only labels currently observed without enum values: TCD Trailing, UniPC Trailing, UniPC AYS.
- UI labels may differ from enum names (aliases can exist in frontend presentation), for example Euler Ancestral maps to EulerA.
- `list_assets.py --type samplers` is currently generated from this mapping in skill code.

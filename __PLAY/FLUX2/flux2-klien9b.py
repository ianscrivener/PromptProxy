
# Multi-line string. 
PROMPT="""ECU (extreme close-up), eye-level, 85mm lens f/4. Gorgeous 24yo Swedish woman with long wavy curly blonde brown hair, thick and voluminous with natural shinw. Slim face with high cheekbones, almond-shaped pale green eyes with long lashes, slightly upturned nose, and very full natural plump lips. Warm golden-brown skin tone with smooth texture, slightly visible pores, and a dewy natural glow. Body fully facing camera at 0°, head slightly tilted toward camera-right, direct gaze engaging viewer. 

No clothing, bare shoulders with visible collarbone and upper chest, smooth skin texture with natural contours. Studio lighting: soft, diffused key light from camera-left at 30°, creating soft shadows under jawline and nose, with a subtle fill light from camera-right to lift shadows evenly. Catchlights in eyes, soft specular highlights on lips and forehead. 

Background: blurred neutral grey studio backdrop, clean and uncluttered. 8K resolution, sharp focus on eyes and lips, skin texture detail, fabric texture detail (none present), professional quality. Single subject, clean background, anatomically accurate, correct torso length proportions, large full lips with natural plumpness, smooth bare shoulders. Warm lighting balance, natural colour temperature. High detail, cinematic lighting, lifelike rendering, no plastic appearance. Natural facial features with subtle asymmetry, realistic anatomy, deep focus on facial expression and texture. No artificial enhancements. Full visibility of neck and just the tops of the shoulders, Studio quality portrait, high-end photographic realism.
"""


import os
import requests

# FLUX.2 [klein] 9B - Balanced quality/speed (use flux-2-klein-9b for a pinned model)
response = requests.post(
    'https://api.bfl.ai/v1/flux-2-klein-9b-preview',
    headers={
        'accept': 'application/json',
        'x-key': os.environ.get("BFL_API_KEY"),
        'Content-Type': 'application/json',
    },
    json={
        'prompt': PROMPT,
        # 'input_image': 'https://example.com/your-image.jpg',
        # 'input_image_2': 'https://example.com/reference-2.jpg',  # Up to 4 total
    },
).json()

request_id = response["id"]
polling_url = response["polling_url"]


print(f"Request ID: {request_id}")
print(f"Polling URL: {polling_url}")
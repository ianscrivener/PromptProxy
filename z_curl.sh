
# Multi-line string. 
PROMPT=

curl https://ark.ap-southeast.bytepluses.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BYTE_PLUS}" \
  -d '{
    "model": "ep-20260123162415-2wr9p",
    "prompt": "The 1960s, 15th floor of the five-star airport hotel overlooking the airport with planes taking off view of the runway in the distance, stylish 1960s furniture, bright colors, and teak wood panelling above the large kingsize bed on the right side of frame. Lying on the bed naked is a gorgeous 26yo European woman with radiant blonde hair Cascading down messily around her shoulders. She is fully naked, very relaxed, sleepy, leaning back. Looking at the viewer fondly. One hand behind her head. We see her natural gorgeous medium sized breasts. One knee is up, Leg straight forward. To the right is a ruffle bed and some pale blue, light blue clothing scattered on the floor. Classic film grain, sepia undertones mixed with natural colors, 1960s fashion photography style. Lighting only from the large windows. Warm emotive expression, high contrast, sharp focus on face and uniform fabric weave visible. Anatomically correct posture.",
    "size": "4096x4096",
    "watermark": false,
    "max_images": 1,
    "stream": true,
    "response_format": "url"
  }'

echo "Done"
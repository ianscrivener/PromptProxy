"""Image tensor encoding/decoding for Draw Things DTTensor format.

DTTensor layout:
  - 68-byte header (17 x uint32): metadata flags, height, width, channels
  - Payload: float16 pixel data (width x height x channels x 2 bytes)

Response images: float16 -> uint8 via clamp((f16 + 1) * 127)
Request images:  uint8 -> float16 via (u8 / 127) - 1
"""

import struct
from io import BytesIO
import numpy as np
from PIL import Image, ImageOps


COMPRESSED_TENSOR_TYPE = 1012247
CCV_TENSOR_CPU_MEMORY = 0x1
CCV_TENSOR_FORMAT_NHWC = 0x02
CCV_16F = 0x20000


def _decode_encoded_image(data):
    with Image.open(BytesIO(data)) as img:
        return img.copy()


def convert_response_image(tensor_bytes):
    """Decode a DTTensor (from GenerateImage response) into PIL Image.

    Returns a PIL Image in RGB mode.
    Supports both uncompressed and fpzip-compressed DTTensor payloads.
    """
    # Some server paths (notably upscaler output) can return encoded images directly.
    if tensor_bytes.startswith(b"\x89PNG\r\n\x1a\n") or tensor_bytes.startswith(b"\xff\xd8") or tensor_bytes.startswith(b"RIFF"):
        with Image.open(BytesIO(tensor_bytes)) as img:
            return img.copy()

    if len(tensor_bytes) < 68:
        raise ValueError(f"DTTensor payload too small: {len(tensor_bytes)} bytes")

    buf = memoryview(tensor_bytes)
    header = struct.unpack_from("<17I", buf, 0)
    tensor_type = header[0]
    height, width, channels = header[6], header[7], header[8]

    if width <= 0 or height <= 0:
        try:
            return _decode_encoded_image(tensor_bytes)
        except Exception as exc:
            raise ValueError(f"Invalid DTTensor dimensions: width={width}, height={height}") from exc

    if channels not in (1, 3, 4):
        try:
            return _decode_encoded_image(tensor_bytes)
        except Exception as exc:
            raise ValueError(
                f"Unsupported DTTensor channel count: {channels}. Expected 1, 3, or 4."
            ) from exc

    rgb_size = width * height * 3
    rgba_size = width * height * 4
    if len(tensor_bytes) == rgba_size:
        return Image.frombytes("RGBA", (width, height), tensor_bytes).convert("RGB")
    if len(tensor_bytes) == rgb_size:
        return Image.frombytes("RGB", (width, height), tensor_bytes)

    offset = 68

    # Handle compressed DTTensor payloads using fpzip
    if tensor_type == COMPRESSED_TENSOR_TYPE:
        import fpzip
        uncompressed = fpzip.decompress(bytes(buf[offset:]), order="C")
        data = uncompressed.astype(np.float16).tobytes()
    else:
        data = bytes(buf[offset:])

    if len(data) == rgba_size:
        return Image.frombytes("RGBA", (width, height), data).convert("RGB")
    if len(data) == rgb_size:
        return Image.frombytes("RGB", (width, height), data)

    expected = width * height * channels
    required_bytes = expected * np.dtype(np.float16).itemsize
    if len(data) < required_bytes:
        available = len(data) // 2
        try:
            return _decode_encoded_image(tensor_bytes)
        except Exception as exc:
            raise ValueError(
                f"Incomplete DTTensor payload: expected {expected} float16 values, got {available}"
            ) from exc
    f16 = np.frombuffer(data, dtype=np.float16, count=expected)

    # Convert float16 -> uint8: clamp((val + 1) * 127, 0, 255)
    u8 = np.clip((f16.astype(np.float32) + 1.0) * 127.0, 0, 255).astype(np.uint8)

    if channels == 4:
        u8 = u8.reshape((height, width, 4))[:, :, :3]
    elif channels == 3:
        u8 = u8.reshape((height, width, 3))
    elif channels == 1:
        u8 = u8.reshape((height, width))
    else:
        raise ValueError(
            f"Unsupported DTTensor channel count: {channels}. Expected 1, 3, or 4."
        )

    return Image.fromarray(u8, "RGB" if u8.ndim == 3 else "L")


def save_response_image(tensor_bytes, path):
    """Decode a DTTensor and save to a file (PNG, JPEG, etc.)."""
    img = convert_response_image(tensor_bytes)
    img.save(path)
    return path


def convert_image_for_request(img, width=None, height=None):
    """Convert a PIL Image to DTTensor bytes for the gRPC request.

    If width/height are given the image is resized first.
    Returns bytes (68-byte header + float16 payload).
    """
    if width and height:
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        img = ImageOps.fit(img.convert("RGB"), (width, height), method=resample)
    else:
        img = img.convert("RGB")

    arr = np.asarray(img, dtype=np.float32)
    h, w, _ = arr.shape

    # Match sample encode path that is known to work with Draw Things img2img.
    f16 = (arr / 255.0 * 2.0 - 1.0).astype(np.float16)

    image_bytes = bytearray(68 + f16.size * np.dtype(np.float16).itemsize)
    struct.pack_into(
        "<9I",
        image_bytes,
        0,
        0,
        CCV_TENSOR_CPU_MEMORY,
        CCV_TENSOR_FORMAT_NHWC,
        CCV_16F,
        0,
        1,
        h,
        w,
        3,
    )
    image_bytes[68:] = f16.tobytes(order="C")
    return bytes(image_bytes)

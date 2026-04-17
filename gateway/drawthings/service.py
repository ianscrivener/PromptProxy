"""DTService - gRPC client for the Draw Things image generation server."""

import hashlib
import json
import socket

import grpc

from gateway.drawthings.cred import get_credentials
from gateway.drawthings.config import build_config_buffer, DEFAULT_CONFIG
from gateway.drawthings.image_helpers import convert_response_image, convert_image_for_request
from gateway.drawthings.generated.SamplerType import SamplerType
from gateway.drawthings.generated import imageService_pb2 as pb
from gateway.drawthings.generated import imageService_pb2_grpc as pb_grpc


def _sha256(data):
    return hashlib.sha256(data).digest()


def _round64(v, minimum=64):
    return max(round(v / 64) * 64, minimum)


def _parse_signpost(signpost):
    """Extract a progress dict from an ImageGenerationSignpostProto."""
    field = signpost.WhichOneof("signpost")
    if field is None:
        return None
    info = {"stage": field}
    inner = getattr(signpost, field)
    if hasattr(inner, "step"):
        info["step"] = inner.step
    return info


SAMPLER_OPTIONS = [
    {"id": SamplerType.DPMPP2MKarras, "name": "DPM++ 2M Karras", "api_name": "DPMPP2MKarras"},
    {"id": SamplerType.EulerA, "name": "Euler A", "api_name": "EulerA"},
    {"id": SamplerType.DDIM, "name": "DDIM", "api_name": "DDIM"},
    {"id": SamplerType.PLMS, "name": "PLMS", "api_name": "PLMS"},
    {"id": SamplerType.DPMPPSDEKarras, "name": "DPM++ SDE Karras", "api_name": "DPMPPSDEKarras"},
    {"id": SamplerType.UniPC, "name": "UniPC", "api_name": "UniPC"},
    {"id": SamplerType.LCM, "name": "LCM", "api_name": "LCM"},
    {"id": SamplerType.EulerASubstep, "name": "Euler A Substep", "api_name": "EulerASubstep"},
    {"id": SamplerType.DPMPPSDESubstep, "name": "DPM++ SDE Substep", "api_name": "DPMPPSDESubstep"},
    {"id": SamplerType.TCD, "name": "TCD", "api_name": "TCD"},
    {"id": SamplerType.EulerATrailing, "name": "Euler A Trailing", "api_name": "EulerATrailing"},
    {"id": SamplerType.DPMPPSDETrailing, "name": "DPM++ SDE Trailing", "api_name": "DPMPPSDETrailing"},
    {"id": SamplerType.DPMPP2MAYS, "name": "DPM++ 2M AYS", "api_name": "DPMPP2MAYS"},
    {"id": SamplerType.EulerAAYS, "name": "Euler A AYS", "api_name": "EulerAAYS"},
    {"id": SamplerType.DPMPPSDEAYS, "name": "DPM++ SDE AYS", "api_name": "DPMPPSDEAYS"},
    {"id": SamplerType.DPMPP2MTrailing, "name": "DPM++ 2M Trailing", "api_name": "DPMPP2MTrailing"},
    {"id": SamplerType.DDIMTrailing, "name": "DDIM Trailing", "api_name": "DDIMTrailing"},
]


class DTService:
    """High-level client for the Draw Things gRPC API.

    Usage::

        svc = DTService("localhost:7859")
        assets = svc.list_assets()
        images = svc.generate("a cat on a beach", model="flux_qwen_srpo_v1.0_f16.ckpt")
        images[0].save("/tmp/cat.png")
    """

    def __init__(self, address="localhost:7859", use_tls=True, use_compression=False):
        self.address = address
        self.use_tls = use_tls
        self.use_compression = use_compression
        options = [
            ("grpc.max_receive_message_length", -1),
            ("grpc.max_send_message_length", -1),
        ]
        compression = grpc.Compression.Gzip if use_compression else grpc.Compression.NoCompression
        if use_tls:
            creds = get_credentials()
            self.channel = grpc.secure_channel(
                address,
                creds,
                options=options,
                compression=compression,
            )
        else:
            self.channel = grpc.insecure_channel(
                address,
                options=options,
                compression=compression,
            )
        self.stub = pb_grpc.ImageGenerationServiceStub(self.channel)

    # - Echo / list assets -------------------------------------------

    def echo(self, name=None):
        """Call Echo RPC. Returns the raw EchoReply protobuf."""
        req = pb.EchoRequest(name=name or socket.gethostname())
        return self.stub.Echo(req)

    def list_assets(self):
        """Query the server for available assets, samplers, and metadata.

        Returns a dict with keys: models, loras, control_nets, upscalers,
        textual_inversions, samplers.
        Each value is a list of dicts parsed from the override metadata.
        """
        reply = self.echo()
        override = reply.override

        def _decode(buf):
            if not buf:
                return []
            return json.loads(buf.decode("utf-8"))

        return {
            "models": _decode(override.models),
            "loras": _decode(override.loras),
            "control_nets": _decode(override.controlNets),
            "upscalers": _decode(override.upscalers),
            "textual_inversions": _decode(override.textualInversions),
            "samplers": SAMPLER_OPTIONS,
        }

    # - Generate (txt2img) -------------------------------------------

    def generate(self, prompt, negative_prompt="", config=None,
                 image_bytes=None, mask_bytes=None, progress_callback=None,
                 timeout=None, upscaler=None, upscaler_scale_factor=0,
                 face_restoration=None):
        """Generate image(s) from a text prompt.

        Args:
            prompt: The positive prompt.
            negative_prompt: Negative prompt text.
            config: Dict of generation config overrides (snake_case keys).
            image_bytes: Optional source image as DTTensor bytes (for img2img).
            mask_bytes: Optional mask as DTTensor bytes (for inpainting).
            progress_callback: Optional callable(dict) called with progress
                updates as they stream from the server. Each dict has a
                "stage" key (e.g. "sampling", "textEncoded") and optionally
                a "step" key for sampling stages.
            timeout: Optional RPC deadline in seconds. If exceeded, raises
                TimeoutError.

        Returns:
            List of PIL Images.
        """
        c = {**DEFAULT_CONFIG, **(config or {})}
        if upscaler:
            c["upscaler"] = upscaler
        if upscaler_scale_factor and upscaler_scale_factor > 0:
            c["upscaler_scale_factor"] = upscaler_scale_factor
        if face_restoration:
            c["face_restoration"] = face_restoration
        cfg_buf = build_config_buffer(c)

        contents = []
        image_hash = None
        mask_hash = None

        if image_bytes is not None:
            image_hash = _sha256(image_bytes)
            contents.append(image_bytes)
        if mask_bytes is not None:
            mask_hash = _sha256(mask_bytes)
            contents.append(mask_bytes)

        req = pb.ImageGenerationRequest(
            scaleFactor=1,
            user=socket.gethostname(),
            device=pb.LAPTOP,
            configuration=cfg_buf,
            prompt=prompt,
            negativePrompt=negative_prompt,
            image=image_hash,
            mask=mask_hash,
            contents=contents,
            chunked=True,
        )

        response_images = []
        decode_errors = []
        pending_image_chunks = []
        latest_preview_image = None

        def _decode_tensor(raw, label):
            try:
                response_images.append(convert_response_image(raw))
            except Exception as exc:
                decode_errors.append(f"{label}: {exc}")

        try:
            if timeout is None:
                stream = self.stub.GenerateImage(req)
            else:
                stream = self.stub.GenerateImage(req, timeout=timeout)

            for response in stream:
                if progress_callback and response.HasField("currentSignpost"):
                    info = _parse_signpost(response.currentSignpost)
                    if info:
                        progress_callback(info)

                if response.HasField("previewImage") and response.previewImage:
                    latest_preview_image = bytes(response.previewImage)

                if response.generatedImages:
                    chunks = [bytes(img_data) for img_data in response.generatedImages]
                    if response.chunkState == pb.MORE_CHUNKS:
                        pending_image_chunks.extend(chunks)
                    else:
                        if pending_image_chunks:
                            pending_image_chunks.extend(chunks)
                            _decode_tensor(b"".join(pending_image_chunks), "generatedImages")
                            pending_image_chunks = []
                        else:
                            for raw in chunks:
                                _decode_tensor(raw, "generatedImages")

            if pending_image_chunks:
                _decode_tensor(b"".join(pending_image_chunks), "generatedImages")

        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise TimeoutError(
                    f"Draw Things generation timed out after {timeout} seconds"
                ) from exc
            raise

        if not response_images:
            if latest_preview_image is not None:
                _decode_tensor(latest_preview_image, "previewImage")

        if not response_images:
            details = "; ".join(decode_errors[-3:]) if decode_errors else "no image tensors returned"
            raise ValueError(f"Draw Things did not return a decodable final image ({details})")

        return response_images

    # - img2img helper -----------------------------------------------

    def img2img(self, source_image, prompt, negative_prompt="",
                strength=0.6, config=None, progress_callback=None,
                timeout=None, upscaler=None, upscaler_scale_factor=0,
                face_restoration=None):
        """Modify an existing image according to a prompt.

        Args:
            source_image: PIL Image (the source).
            prompt: Text prompt describing desired changes.
            negative_prompt: Negative prompt.
            strength: How much to change (0=none, 1=completely replace).
            config: Additional config overrides.
            progress_callback: Optional callable(dict) for progress updates.
            timeout: Optional RPC deadline in seconds.

        Returns:
            List of PIL Images.
        """
        c = {**(config or {}), "strength": strength}
        width = _round64(c.get("width", source_image.width))
        height = _round64(c.get("height", source_image.height))
        c["width"] = width
        c["height"] = height

        img_bytes = convert_image_for_request(source_image, width=width, height=height)
        return self.generate(
            prompt,
            negative_prompt,
            config=c,
            image_bytes=img_bytes,
            progress_callback=progress_callback,
            timeout=timeout,
            upscaler=upscaler,
            upscaler_scale_factor=upscaler_scale_factor,
            face_restoration=face_restoration,
        )

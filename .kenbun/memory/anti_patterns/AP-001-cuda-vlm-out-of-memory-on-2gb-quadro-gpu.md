# AP-001: CUDA VLM Out-of-Memory on 2GB Quadro GPU

**Logged:** 2026-08-23 07:41
**Reference ID:** `fix_1787464133_e0767eacc0c4`

## The Mistake / Anti-Pattern
Running llama-server with --gpus all and full fp16 mmproj (1.27GB) caused cudaMalloc OOM because Xorg already used ~800MB VRAM.

## The Verified Solution / Protocol
Run UI-TARS multimodal vision encoder on 12-thread Intel i7 CPU with 448x252 Bilinear patch downscaling, achieving sub-5s local inference.

# Grand Challenge Submission
*p10 — Model Training & Benchmarking*

This document covers the full submission lifecycle: container requirements,
local testing, building and uploading the image, interpreting results, and
debugging failed submissions.

---

## How Grand Challenge runs your submission

GC does not run your training code. It runs an inference container:

```
GC infrastructure
  ├── Provides: test WSI at /input/images/breast-cancer-wsi/<filename>.tiff
  ├── Expects:  segmentation mask at /output/images/breast-cancer-segmentation/<filename>.tiff
  └── Runs:     your Docker container, no outbound network, time-limited
```

The container must:
1. Read the input WSI from the fixed input path
2. Run inference (sliding window tiling → model prediction → mask assembly)
3. Write the output mask to the fixed output path, in the correct format

Everything needed for inference — model weights, Python dependencies, all code
— must be inside the image. No downloads at runtime.

---

## Output format

BEETLE expects a TIFF mask where:
- Pixel dimensions match the input WSI at 20× magnification (or the resolution
  specified by the challenge)
- Pixel value = class index (0=other, 1=invasive, 2=non-invasive, 3=necrosis)
- Colour space: greyscale (single channel, uint8)

Verify the exact format requirements in the BEETLE challenge documentation on
Grand Challenge before building the container — format details can change
between challenge phases.

---

## Submission container structure

```
submission/
├── Dockerfile
├── process.py          ← entrypoint: reads input, runs inference, writes output
└── requirements.txt    ← pinned inference-only dependencies (no training libs)
```

`process.py` calls `src/infer.py` with the paths provided by GC's environment
variables. GC sets `INPUT_PATH` and `OUTPUT_PATH` at runtime, or uses fixed
paths — check the BEETLE algorithm template for the exact variable names.

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Non-root user — required for GC submission
RUN useradd -m -u 1000 inference
WORKDIR /opt/inference

# Copy and install dependencies first (layer caching)
COPY submission/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy inference code and model weights
COPY src/ src/
COPY configs/baseline.yaml configs/
COPY runs/<run_id>/best.pt weights/best.pt

COPY submission/process.py .

USER inference
ENTRYPOINT ["python", "process.py"]
```

**Why non-root:** Grand Challenge requires non-root execution for security.
The `USER inference` line before `ENTRYPOINT` is mandatory — submissions
that run as root are rejected at validation.

---

## Local testing

Test the container locally before submitting. Use the `evalutils` test pattern
that Grand Challenge recommends, or a minimal manual test:

```bash
# Build
docker build -t p10-beetle:latest -f submission/Dockerfile .

# Create test input structure (use one of your val WSIs)
mkdir -p /tmp/gc-test/input/images/breast-cancer-wsi
mkdir -p /tmp/gc-test/output/images/breast-cancer-segmentation

cp data/raw/wsis/<test_slide>.tiff \
   /tmp/gc-test/input/images/breast-cancer-wsi/

# Run container with GC-style mounts
docker run --rm \
  -v /tmp/gc-test/input:/input:ro \
  -v /tmp/gc-test/output:/output \
  --network=none \
  p10-beetle:latest

# Check output
ls -la /tmp/gc-test/output/images/breast-cancer-segmentation/
python -c "
from PIL import Image
import numpy as np
mask = np.array(Image.open('/tmp/gc-test/output/images/breast-cancer-segmentation/<test_slide>.tiff'))
print('Shape:', mask.shape)
print('Unique values:', np.unique(mask))
print('Value counts:', {int(v): int((mask == v).sum()) for v in np.unique(mask)})
"
```

The `--network=none` flag simulates GC's network isolation. If `process.py`
tries to make any network call, it will fail here — fix it before submitting.

Expected output: `Unique values: [0 1 2 3]` (or a subset if some classes
aren't present in the test slide).

---

## Building and pushing the image

GC uses its own registry. After registering your algorithm on Grand Challenge:

```bash
# Log in to GC registry (credentials from GC account settings)
docker login grand-challenge.org

# Tag for GC registry
docker tag p10-beetle:latest \
  grand-challenge.org/<your-algorithm-slug>:<version>

# Push
docker push grand-challenge.org/<your-algorithm-slug>:<version>
```

Then trigger a submission from the BEETLE challenge page — select the algorithm
version you just pushed and submit.

---

## Interpreting submission results

GC returns:
- **Pass / Fail** — whether the container ran and produced valid output
- **Dice scores** — overall and per-class (if the challenge provides them)
- **Logs** — stdout/stderr from your container during inference

Common failure modes:

| Status | Likely cause |
|--------|-------------|
| Container failed to start | Missing dependency, import error |
| Output not found | Wrong output path in process.py |
| Output format error | Wrong pixel type (float instead of uint8), wrong channel count |
| Timeout | Inference too slow — reduce patch overlap, optimise tiling loop |
| OOM | GC instance smaller than expected — reduce batch size in infer.py |

Always check the logs first. GC surfaces stdout/stderr from the container —
add logging to `process.py` so you can see what failed.

---

## Inference speed requirements

GC imposes a time limit per slide. The exact limit for BEETLE is specified in
the challenge documentation. Typical limits are 5–15 minutes per slide.

For a 50k×70k WSI at 20× with 512×512 patches and 50% overlap:
- Number of patches: ~(100 × 140) = ~14,000
- At 20ms per patch (A100): ~280 seconds ≈ 5 minutes

GC may use CPU or GPU instances — check the challenge hardware specification.
If running on CPU, inference will be significantly slower. Profile `process.py`
locally on a CPU-only Docker run to estimate wall time:

```bash
docker run --rm \
  --cpus=4 --memory=16g \
  -v /tmp/gc-test/input:/input:ro \
  -v /tmp/gc-test/output:/output \
  --network=none \
  p10-beetle:latest
```

If too slow on CPU: increase stride (reduce patch overlap), use `torch.jit.script`
to compile the model, or reduce model size (switch to EfficientNet-B0 encoder
for the submission build, keeping UNI for validation reporting).

---

## Submission frequency

BEETLE limits the number of submissions per team per day/week (check the
challenge rules). Do not submit every training run — only submit when:
1. A meaningful training change is complete (new encoder, new augmentation)
2. Local val Dice confirms the change is an improvement
3. The container has been locally tested and passes

Each submission uses compute on GC's infrastructure. Submitting broken
containers or incremental changes wastes your submission quota and GC's
resources.

---

## Recording results

After receiving the leaderboard score:
1. Log the result in `docs/results.md` — leaderboard Dice, rank, date, model config
2. Update the p8 registry entry for the submitted run with the GC score
3. Commit the updated `docs/results.md` to git (results are public-safe)

The p8 registry links the leaderboard score to the exact model weights,
config, and training run that produced it.

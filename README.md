# Julia / Mandelbrot — Hi-Precision CUDA Deep Zoom

**Notebook:** `Mandelbrot_Julia_Colab_hi_precision_cuda.ipynb`  
**Profile:** https://github.com/piercegregory-spec

From Scientific American Aug 1985 to ×10^1000 in 2026.

### What it does

This notebook is a full deep-zoom engine, not brute-force float64.

- **Setup (Cell 1):** Auto-detects Colab A100, mounts Drive if `SAVE_TO_DRIVE=True`, installs `gmpy2`, `numba`, `imageio-ffmpeg`. Falls back to CPU if no GPU.
- **Engine (Cell 2):** Perturbation theory
  - One reference orbit `Z_{n+1}=Z_n²+c` computed with as many digits as needed — `gmpy2` on CPU, `bits_for() = halvings + 107` (3,400 bits for 10^-1000)
  - Every pixel only tracks `δz -> 2·Z·δz + δz² + δc` in float64 on GPU via `numba.cuda` (or all CPU cores via `prange`)
  - Floatexp rescaling below ~10^-300: δz is kept as `mantissa × 2^k`
  - Rebasing (Zhuoran 2021): when orbit passes closer to 0 than δz, restarts at reference start — no glitches
  - Destinations Newton-refined to thousands of digits
- **Studio (Cell 3):** Interactive viewer with ipywidgets — click to zoom, Julia twin, ❄ Snap to nearest Misiurewicz point, ‡ Find minibrot in view at any depth, 12-frame contact sheet preview, resumable movie writer.

### Destinations

Pre-loaded `DESTINATIONS`: Seahorse Valley spirals, Elephant Valley trunk, Southern spiral valley, M(4,1) three-armed branch, upper dendrite fork, c=i dendrite, antenna crossroads -1.8393, airplane tripling cascade ×55.247, Feigenbaum doubling ×4.669..., plus deep minibrots found with `minibrot_near()`:

- ×10^120 period 1841 in Seahorse Valley
- ×10^299 period 1209 under the three-armed star  
- ×10^301 period 2900 in Elephant Valley
- ×10^1000 period 16,037 — seahorse abyss, 1,031 digits, ~3M iter/pixel at the end

### Movies

Rendered in 10s pieces to `movies/` or `/content/drive/MyDrive/Mandelbrot_movies/`. Finished pieces get `.done` flags, then concatenated with ffmpeg. Same settings → same hash → same filename, so interrupted runs resume automatically. Designed to survive Colab sleeping.

### Why it's fast (and why naive bandwidth math fails)

The reference orbit `Zr, Zi` is broadcast from L2 cache to all threads at each iteration, not streamed per-pixel from HBM. Real cost is avg iterations actually executed + gmpy2 reference generation, not `px² * max_iter * 16`.

### Run it

Colab: Runtime → Change runtime type → A100 GPU → run cells 1-3.

Local: `pip install -q gmpy2 numba ipywidgets imageio imageio-ffmpeg pillow` + CUDA toolkit. Falls back to CPU automatically.

### Credits

Built for fun over several days and nights. Inspiration from Paul Bourke's classic notes: https://paulbourke.net/fractals/mandelbrot/

Built with VS Code + help from Claude & Gemini.

— Greg Pierce, Pittsburgh, PA

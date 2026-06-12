"""
Central config for paths, hyperparameters, and seeds.

Edit DATA_ROOT only if you run from a different machine (e.g. Colab).
Everything else has sensible defaults from the proposal.
"""
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "DataSet" / "LivDet Datasets" / "Normalized"
TRAIN_DIR = DATA_ROOT / "train"
TEST_DIR = DATA_ROOT / "test"

MANIFEST_DIR = PROJECT_ROOT / "src" / "data" / "manifests"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
RESULTS_DIR = PROJECT_ROOT / "results"

for d in (MANIFEST_DIR, CHECKPOINT_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Reproducibility ─────────────────────────────────────────────────────
SEED = 42

# ── Model defaults ──────────────────────────────────────────────────────
IMAGE_SIZE = 224          # Standard ImageNet input
BATCH_SIZE = 32
NUM_WORKERS = 2           # Windows: keep low. Colab: bump to 4.
NUM_CLASSES = 2           # live=0, spoof=1

# ── Training defaults ───────────────────────────────────────────────────
EPOCHS = 15
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 1e-4
EARLY_STOP_PATIENCE = 4

# ── Augmentation (per proposal §4.4) ────────────────────────────────────
ROTATION_DEG = 20
BRIGHTNESS_JITTER = 0.2
SCALE_MIN = 0.9
SCALE_MAX = 1.1

# ── Split (per proposal §4.4: 70/15/15 stratified) ──────────────────────
VAL_FRACTION = 0.15
TEST_FRACTION_OVERRIDE = None  # We use LivDet's official test split

# ── Quick-test mode ─────────────────────────────────────────────────────
# Set to a small int (e.g. 200) to run a sanity check end-to-end in minutes.
QUICK_SAMPLES = None

# ── Computed defaults ───────────────────────────────────────────────────
LABEL_MAP = {"live": 0, "spoof": 1}
LABEL_NAMES = ["live", "spoof"]


def device_str() -> str:
    """Return 'cuda' if available else 'cpu'. Late-imported to avoid forcing torch."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"

# utils.py
import numpy as np
from PIL import Image

def make_gif(frames, out_path: str, duration: int = 300):
    """
    Salva una GIF animata da una lista di immagini (array o PIL).
    """
    if not frames:
        return
    pil_frames = [Image.fromarray(f) if not isinstance(f, Image.Image) else f for f in frames]
    pil_frames[0].save(out_path, save_all=True, append_images=pil_frames[1:], duration=duration, loop=0)



def _to_1d(x):
    """
    Converte x in un array NumPy monodimensionale.
    Gestisce liste, array con shape arbitraria, scalari.
    """
    return np.asarray(x).reshape(-1)

# utils.py

def to_json_safe(obj):
    """Ricorsivamente converte np.ndarray e np.float32/64 in tipi compatibili con JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_json_safe(x) for x in obj]
    else:
        return obj



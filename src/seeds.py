"""Seed AI/ML packages and category labels for the PyPI dependency network."""

CATEGORIES: dict[str, list[str]] = {
    "deep_learning": [
        "torch", "tensorflow", "keras", "jax", "flax", "pytorch-lightning",
        "torchvision", "torchaudio", "torchtext", "tensorboard",
    ],
    "nlp": [
        "transformers", "tokenizers", "datasets", "sentence-transformers",
        "spacy", "nltk", "gensim", "langchain", "openai", "anthropic",
        "tiktoken", "sentencepiece",
    ],
    "classical_ml": [
        "scikit-learn", "xgboost", "lightgbm", "catboost", "statsmodels",
        "imbalanced-learn",
    ],
    "data": [
        "numpy", "pandas", "scipy", "polars", "pyarrow", "dask",
        "h5py", "zarr",
    ],
    "viz": [
        "matplotlib", "seaborn", "plotly", "bokeh", "altair",
    ],
    "cv": [
        "opencv-python", "Pillow", "scikit-image", "albumentations",
        "ultralytics",
    ],
    "mlops": [
        "mlflow", "wandb", "ray", "optuna", "huggingface-hub",
        "accelerate", "peft", "trl",
    ],
}


def all_seeds() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for pkgs in CATEGORIES.values():
        for p in pkgs:
            if p.lower() not in seen:
                seen.add(p.lower())
                out.append(p)
    return out


def category_of(pkg: str) -> str | None:
    pkg_low = pkg.lower()
    for cat, pkgs in CATEGORIES.items():
        if any(p.lower() == pkg_low for p in pkgs):
            return cat
    return None

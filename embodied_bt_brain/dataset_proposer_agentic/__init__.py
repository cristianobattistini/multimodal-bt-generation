def generate_dataset(*args, **kwargs):
    """
    Lazy entrypoint to avoid importing heavy dependencies (e.g., OpenAI client)
    when using lightweight utilities under this package.
    """
    from .generate_dataset import main as _main
    return _main(*args, **kwargs)

__all__ = ["generate_dataset"]

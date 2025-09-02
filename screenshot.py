import datetime
import pathlib

try:
    import mss
    import mss.tools
except ImportError:
    mss = None  # so code can gracefully warn if missing


def take_screenshot(filename: str | None = None, directory: str | pathlib.Path = ".", monitor: int = 1) -> str:
    """
    Capture a screenshot and save to a file.
    
    Args:
        filename: Optional base filename (without extension). If None, uses timestamp.
        directory: Directory path (default: current dir).
        monitor: Monitor index (1 = primary). Use 0 to capture all monitors.
    
    Returns:
        Path to saved PNG file (as str).
    """
    if mss is None:
        raise ImportError("mss is not installed. Run 'pip install mss'")

    directory = pathlib.Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}"

    out_path = directory / f"{filename}.png"

    with mss.mss() as sct:
        # monitor=0 grabs all screens
        mon = sct.monitors[monitor]
        img = sct.grab(mon)
        mss.tools.to_png(img.rgb, img.size, output=str(out_path))

    return str(out_path)
"""PDF and image output generation - CPU only."""
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import os

# Try to import img2pdf, fallback if not available
try:
    import img2pdf
    HAS_IMG2PDF = True
except ImportError:
    HAS_IMG2PDF = False


def save_as_pdf(image_array: np.ndarray, output_path: str = None) -> str:
    """
    Convert stitched numpy image to PDF.
    Pure CPU operation.

    Args:
        image_array: BGR numpy array
        output_path: Output file path (auto-generated if None)

    Returns:
        Path to saved PDF
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        desktop = os.path.expanduser("~/Desktop")
        output_path = os.path.join(desktop, f"scroll_capture_{timestamp}.pdf")

    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)

    # Convert to PIL Image
    pil_image = Image.fromarray(rgb_image)

    if HAS_IMG2PDF:
        # Use img2pdf for efficient PDF generation
        temp_png = "/tmp/temp_stitched.png"
        pil_image.save(temp_png, "PNG")

        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(temp_png))

        os.remove(temp_png)
    else:
        # Fallback: save as PDF using PIL
        pil_image.save(output_path, "PDF", resolution=100.0)

    return output_path


def save_as_image(image_array: np.ndarray,
                  output_path: str = None,
                  format: str = "PNG") -> str:
    """
    Save stitched image directly.

    Args:
        image_array: BGR numpy array
        output_path: Output file path (auto-generated if None)
        format: Image format (PNG, JPEG, etc.)

    Returns:
        Path to saved image
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        desktop = os.path.expanduser("~/Desktop")
        output_path = os.path.join(desktop, f"scroll_capture_{timestamp}.{format.lower()}")

    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)

    # Convert to PIL Image and save
    pil_image = Image.fromarray(rgb_image)

    # For large images, optimize
    if format.upper() == "PNG":
        pil_image.save(output_path, "PNG", optimize=True)
    elif format.upper() == "JPEG":
        pil_image.save(output_path, "JPEG", quality=95)
    else:
        pil_image.save(output_path, format)

    return output_path


def get_output_path(extension: str = "pdf") -> str:
    """Generate a timestamped output path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    desktop = os.path.expanduser("~/Desktop")
    return os.path.join(desktop, f"scroll_capture_{timestamp}.{extension}")

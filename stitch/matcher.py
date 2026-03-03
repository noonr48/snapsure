"""
Image stitching using NCC template matching - simple and direct: row-by-row pixel comparison.
"""

import cv2
import numpy as np
from typing import List, Optional


def find_overlap(prev_img: np.ndarray, curr_img: np.ndarray,
                 min_overlap: int = 50) -> int:
    """
    Find overlap between two consecutive frames using NCC template matching.
    """
    h1, w1 = prev_img.shape[:2]
    h2, w2 = curr_img.shape[:2]

    # Ensure same width
    if w1 != w2:
        curr_img = cv2.resize(curr_img, (w1, curr_img.shape[0]))

    # Convert to grayscale
    if len(prev_img.shape) == 3:
        prev_gray = cv2.cvtColor(prev_img, cv2.COLOR_BGR2GRAY)
    else:
        prev_gray = prev_img
    if len(curr_img.shape) == 3:
        curr_gray = cv2.cvtColor(curr_img, cv2.COLOR_BGR2GRAY)
    else:
        curr_gray = curr_img

    # Use bottom of prev as template
    template_h = min(300, h1 // 4, h2 // 2)
    template = prev_gray[-template_h:]

    # Search in top of curr
    max_search = min(h2, h1 // 2)
    search_region = curr_gray[:max_search]

    # Template matching
    try:
        result = cv2.matchTemplate(search_region, template, cv2.TM_CCORR_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)


        # Position is where template was found
        overlap = max_loc[1]  # Y position in search region

        # Validate: overlap should be reasonable
        if overlap < min_overlap:
            overlap = min_overlap
        if overlap > h2 - 10:
            overlap = h2 - 10

        # Additional validation: compare pixels directly
        prev_overlap_region = prev_gray[-overlap:]
        curr_overlap_region = curr_gray[:overlap]

        # Calculate mean absolute error
        min_h = min(prev_overlap_region.shape[0], curr_overlap_region.shape[0])
        prev_overlap_region = prev_overlap_region[:min_h]
        curr_overlap_region = curr_overlap_region[:min_h]

        diff = np.mean(np.abs(prev_overlap_region.astype(float) -
                        curr_overlap_region.astype(float)) ** 2)
        similarity = 1.0 - min(1.0, diff / 255.0)

        if similarity > 0.7:
            print(f"  NCC match: overlap={overlap}px (similarity={similarity:.2f})")
            return overlap
        else:
            print(f"  NCC match too weak: overlap={overlap}px (similarity={similarity:.2f})")
            return min_overlap

    except Exception as e:
        print(f"  Template matching error: {e}")

    return min_overlap


def deduplicate_frames(frames: List[np.ndarray]) -> List[np.ndarray]:
    """Pass-through - deduplication handled by stitching overlap detection."""
    return frames


def stitch_frames(frames: List[np.ndarray],
                  min_overlap: int = 50) -> Optional[np.ndarray]:
    """
    Stitch multiple frames into one tall image.
    """
    if not frames:
        return None

    if len(frames) == 1:
        return frames[0].copy()

    print(f"Stitching {len(frames)} frames...")

    result = frames[0].copy()

    for i in range(1, len(frames)):
        curr = frames[i]

        # Ensure same width
        if curr.shape[1] != result.shape[1]:
            curr = cv2.resize(curr, (result.shape[1], curr.shape[0]))

        # Find overlap
        overlap = find_overlap(result, curr, min_overlap)

        if overlap >= curr.shape[0] - 10:
            print(f"  Warning: overlap {overlap} >= frame height {curr.shape[0]}, skipping frame")
            continue

        # Append non-overlapping portion
        new_portion = curr[overlap:]
        result = np.vstack([result, new_portion])

    print(f"Final stitched image: {result.shape[1]}x{result.shape[0]}")
    return result

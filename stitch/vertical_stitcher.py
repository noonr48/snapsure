"""
Simple, robust vertical scrolling stitcher using template matching.
Designed for capturing long scrolling webpages.
"""
import numpy as np
import cv2
from typing import List, Optional, Tuple


def find_vertical_overlap(prev: np.ndarray, curr: np.ndarray,
                         strip_height: int = 300) -> Tuple[int, float]:
    """
    Find the vertical overlap between two consecutive frames.

    Takes a strip from the TOP of curr and searches for it in the BOTTOM of prev.

    Args:
        prev: Previous frame (higher up on screen)
        curr: Current frame (lower down, scrolled further)
        strip_height: Height of strip to match (default 300px)

    Returns:
        (overlap_pixels, confidence_score)
        - overlap_pixels: How many pixels overlap (positive = overlap exists)
        - confidence_score: 0-1, higher is better
    """
    if prev.shape != curr.shape:
        return 0, 0.0

    h, w = prev.shape[:2]

    # Take strip from TOP of current frame (what we just scrolled into view)
    strip_top = curr[:strip_height, :]

    # Search in BOTTOM 80% of previous frame
    search_start = h // 5  # Start from 20% down (avoid top area)
    search_area = prev[search_start:, :]

    # Try template matching
    try:
        result = cv2.matchTemplate(search_area, strip_top, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Calculate overlap: max_loc.y is where strip matches in search_area
        # search_area starts at search_start, so add that offset
        match_y_in_search = max_loc[1]
        match_y_in_full = match_y_in_search + search_start

        # Overlap is how far from bottom the match is
        overlap = h - match_y_in_full

        # Sanity check: overlap should be positive and less than 90% of frame
        if 50 < overlap < h * 0.9:
            return int(overlap), float(max_val)

    except Exception as e:
        print(f"Template matching error: {e}")

    return 0, 0.0


def check_content_exists(result: np.ndarray, new_content: np.ndarray,
                         search_start_ratio: float = 0.5) -> bool:
    """
    Check if new_content already exists in the result image.
    This detects when user scrolls back up or captures duplicate content.

    Searches in the bottom portion of result (search_start_ratio to end).
    """
    if result.shape[1] != new_content.shape[1]:
        return False

    h_result = result.shape[0]
    h_new = new_content.shape[0]

    # Only search the bottom portion of result (most recently added content)
    search_start = int(h_result * search_start_ratio)
    search_area = result[search_start:, :]

    # Take a strip from top of new_content to search for
    strip_height = min(300, h_new)
    strip = new_content[:strip_height, :]

    try:
        result_match = cv2.matchTemplate(search_area, strip, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result_match)

        # If we find a very high confidence match (> 0.85), content already exists
        if max_val > 0.85:
            print(f"  ⚠ Content already exists in result (conf={max_val:.2f}), skipping frame")
            return True
    except:
        pass

    return False


def stitch_frames_vertical(frames: List[np.ndarray],
                           min_overlap: int = 50,
                           min_confidence: float = 0.3) -> Optional[np.ndarray]:
    """
    Stitch frames for vertical scrolling capture.

    Uses simple template matching to find overlaps between consecutive frames.
    Frames are added in order - designed for single-direction scrolling.

    Args:
        frames: List of frames in capture order
        min_overlap: Minimum overlap to consider valid (default 50px)
        min_confidence: Minimum template match confidence (0.0-1.0)

    Returns:
        Stitched image or None if stitching fails
    """
    if not frames:
        print("No frames to stitch!")
        return None

    if len(frames) == 1:
        print("Only 1 frame - nothing to stitch")
        return frames[0].copy()

    print(f"\n=== VERTICAL STITCHER ===")
    print(f"Processing {len(frames)} frames...")

    # Deduplicate with very low threshold (only truly identical frames)
    frames = deduplicate_identical_frames(frames, threshold=1.0)

    if len(frames) < 2:
        print(f"After deduplication: only {len(frames)} frames")
        return frames[0] if frames else None

    # Start with first frame
    result = frames[0].copy()
    current_y = frames[0].shape[0]

    print(f"Starting canvas: {result.shape[1]}x{result.shape[0]}")

    # Add each subsequent frame
    for i in range(1, len(frames)):
        prev = frames[i-1]
        curr = frames[i]

        # Find overlap
        overlap, confidence = find_vertical_overlap(prev, curr)

        print(f"\nFrame {i} -> {i+1}: overlap={overlap}px, conf={confidence:.2f}")

        if overlap > min_overlap and confidence >= min_confidence:
            # Valid overlap found - add only the new part
            new_content = curr[overlap:, :]

            # Check if this content already exists in result (prevents duplicates)
            if check_content_exists(result, new_content):
                continue

            result = np.vstack([result, new_content])
            current_y += new_content.shape[0]
            print(f"  ✓ Added {new_content.shape[0]}px of new content")
        else:
            # No valid overlap - check if it's duplicate content before adding
            if check_content_exists(result, curr):
                continue

            # Not a duplicate, add full frame (might be a gap in scrolling)
            result = np.vstack([result, curr])
            current_y += curr.shape[0]
            print(f"  ⚠ No valid overlap, added full frame ({curr.shape[0]}px)")

        print(f"  Canvas: {result.shape[1]}x{result.shape[0]}")

    print(f"\n✓ Final stitched image: {result.shape[1]}x{result.shape[0]}")
    print(f"  Started: {frames[0].shape[0]}px")
    print(f"  Ended: {result.shape[0]}px")
    print(f"  Growth: {result.shape[0] - frames[0].shape[0]}px ({result.shape[0] / frames[0].shape[0]:.1f}x)")

    return result


def deduplicate_identical_frames(frames: List[np.ndarray],
                                  threshold: float = 1.0) -> List[np.ndarray]:
    """
    Remove only truly identical frames.
    Compare each frame with the LAST KEPT frame.
    """
    if len(frames) <= 2:
        return frames

    print(f"\n=== DEDUPLICATION (threshold={threshold}) ===")

    deduped = [frames[0]]

    for i in range(1, len(frames)):
        prev_kept = deduped[-1]
        curr = frames[i]

        if prev_kept.shape != curr.shape:
            deduped.append(curr)
            continue

        diff = np.mean(np.abs(prev_kept.astype(float) - curr.astype(float)))

        if diff > threshold:
            deduped.append(curr)

    removed = len(frames) - len(deduped)
    print(f"Removed {removed} identical frames")
    print(f"Kept {len(deduped)} unique frames")

    return deduped

"""
Simple, robust vertical stitcher inspired by Fullshot extension principles.
Uses larger overlap regions (200px+) and more forgiving matching.
"""
import numpy as np
import cv2
from typing import List, Optional, Tuple


def find_overlap_multi_strip(prev: np.ndarray, curr: np.ndarray,
                              strip_heights: List[int] = [200, 300, 400]) -> Tuple[int, float]:
    """
    Find overlap using multiple strip sizes for robustness.

    Tries different strip heights and returns the best match.
    Inspired by Fullshot's 200px scroll padding approach.
    """
    if prev.shape != curr.shape:
        return 0, 0.0

    h, w = prev.shape[:2]
    best_overlap = 0
    best_confidence = 0

    # Try multiple strip sizes
    for strip_h in strip_heights:
        if strip_h >= h:
            continue

        # Take strip from TOP of current frame
        strip = curr[:strip_h, :]

        # Search in BOTTOM 60% of previous frame
        search_start = int(h * 0.4)
        search_area = prev[search_start:, :]

        try:
            result = cv2.matchTemplate(search_area, strip, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Calculate overlap in full frame coordinates
            match_y_in_search = max_loc[1]
            match_y_in_full = match_y_in_search + search_start
            overlap = h - match_y_in_full

            # Look for overlaps in the range of 150-700px (reasonable for scrolling)
            if 150 < overlap < h * 0.85 and max_val > best_confidence:
                best_overlap = int(overlap)
                best_confidence = float(max_val)

        except Exception:
            continue

    return best_overlap, best_confidence


def check_for_duplicates(result: np.ndarray, new_content: np.ndarray,
                         threshold: float = 0.85) -> bool:
    """
    Check if new_content already exists in result (prevents back-scrolling duplicates).
    Uses high threshold to avoid false positives.
    """
    if result.shape[1] != new_content.shape[1]:
        return False

    h_result = result.shape[0]
    h_new = new_content.shape[0]

    # Only search bottom 30% of result (most recent content)
    search_start = int(h_result * 0.7)
    if search_start >= h_result:
        return False

    search_area = result[search_start:, :]

    # Use a 150px strip from top of new content
    strip_height = min(150, h_new)
    strip = new_content[:strip_height, :]

    try:
        match_result = cv2.matchTemplate(search_area, strip, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)

        if max_val > threshold:
            return True
    except Exception:
        pass

    return False


def deduplicate_truly_identical(frames: List[np.ndarray], threshold: float = 0.5) -> List[np.ndarray]:
    """
    Remove ONLY truly identical frames (user stopped scrolling).
    Very low threshold - only remove if frames are basically the same.
    """
    if len(frames) <= 2:
        return frames

    print(f"\n=== DEDUPLICATION (threshold={threshold}) ===")

    deduped = [frames[0]]

    for i in range(1, len(frames)):
        last_kept = deduped[-1]
        curr = frames[i]

        if last_kept.shape != curr.shape:
            deduped.append(curr)
            continue

        # Mean absolute difference - only skip if TRULY identical
        diff = np.mean(np.abs(last_kept.astype(float) - curr.astype(float)))

        if diff > threshold:
            deduped.append(curr)

    removed = len(frames) - len(deduped)
    print(f"Removed {removed} identical frames (user paused)")
    print(f"Kept {len(deduped)} frames for stitching")

    return deduped


def stitch_frames_simple(frames: List[np.ndarray]) -> Optional[np.ndarray]:
    """
    Simple vertical stitcher inspired by Fullshot extension.

    Key principles:
    - Look for larger overlaps (150-700px range)
    - Use multiple strip sizes for robustness
    - Skip frames with insufficient overlap (gaps in scrolling)
    - Check for duplicates to prevent back-scrolling issues
    """
    if not frames:
        print("No frames to stitch!")
        return None

    if len(frames) == 1:
        print("Only 1 frame - nothing to stitch")
        return frames[0].copy()

    print(f"\n=== SIMPLE VERTICAL STITCHER ===")
    print(f"Processing {len(frames)} frames...")

    # Remove ONLY truly identical frames (user paused, not scrolling)
    frames = deduplicate_truly_identical(frames, threshold=0.5)

    if len(frames) < 2:
        print(f"After deduplication: only {len(frames)} frames")
        return frames[0] if frames else None

    # Start with first frame
    result = frames[0].copy()
    frames_added = 1

    print(f"\nStarting canvas: {result.shape[1]}x{result.shape[0]}")

    # Add each subsequent frame
    for i in range(1, len(frames)):
        prev = frames[i-1]
        curr = frames[i]

        # Find overlap using multiple strip sizes
        overlap, confidence = find_overlap_multi_strip(prev, curr)

        print(f"\nFrame {i} → {i+1}: overlap={overlap}px, conf={confidence:.2f}")

        # We need:
        # - Overlap in reasonable range: 100-700px (not too small, not entire frame)
        # - Confidence > 0.12 (lowered because faster scrolling = lower match scores)
        if 100 < overlap < prev.shape[0] * 0.85 and confidence > 0.12:
            # Valid overlap - extract and add new content
            new_content = curr[overlap:, :]

            # Check if this content already exists (prevent duplicates)
            if check_for_duplicates(result, new_content):
                print(f"  ⚠ Content already exists, skipped")
                continue

            result = np.vstack([result, new_content])
            frames_added += 1
            print(f"  ✓ Added {new_content.shape[0]}px new content (total: {result.shape[0]}px)")
        else:
            # Insufficient overlap - skip this frame
            print(f"  ⚠ Insufficient overlap, skipped frame")

    print(f"\n=== RESULTS ===")
    print(f"Frames processed: {len(frames)}")
    print(f"Frames added: {frames_added}")
    print(f"Final size: {result.shape[1]}x{result.shape[0]}")
    print(f"Growth: {result.shape[0]} / {frames[0].shape[0]} = {result.shape[0] / frames[0].shape[0]:.1f}x")

    return result

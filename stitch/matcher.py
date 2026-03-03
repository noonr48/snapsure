"""
Feature-based image stitching for screen captures.
Handles bidirectional scrolling using ORB features and graph-based matching.
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple, Dict
from collections import defaultdict


class FeatureStitcher:
    """
    Panorama stitcher using feature detection (ORB/SIFT).
    Handles unordered frames from bidirectional scrolling.
    """

    def __init__(self, feature_type: str = 'orb', min_matches: int = 10):
        self.min_matches = min_matches

        # Initialize feature detector
        if feature_type == 'orb':
            self.detector = cv2.ORB_create(nfeatures=3000)
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        elif feature_type == 'sift':
            self.detector = cv2.SIFT_create()
            self.matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        else:
            self.detector = cv2.ORB_create(nfeatures=3000)
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def extract_features(self, image: np.ndarray):
        """Extract ORB/SIFT features from image."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return self.detector.detectAndCompute(gray, None)

    def find_match(self, features1, features2) -> Optional[Dict]:
        """
        Match features between two images.
        Returns match info including offset for screen captures.
        """
        kp1, des1 = features1
        kp2, des2 = features2

        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            return None

        try:
            matches = self.matcher.knnMatch(des1, des2, k=2)
        except:
            return None

        # Lowe's ratio test
        good_matches = []
        for match in matches:
            if len(match) == 2:
                m, n = match
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        if len(good_matches) < self.min_matches:
            return None

        # Extract matched points
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches])
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches])

        # For screen captures, we expect mostly vertical translation
        # Compute median offset
        offsets = dst_pts - src_pts
        median_offset = np.median(offsets, axis=0)

        # Filter outliers
        inlier_mask = np.all(np.abs(offsets - median_offset) < [50, 100], axis=1)
        inlier_count = np.sum(inlier_mask)

        if inlier_count < self.min_matches // 2:
            return None

        # Refined offset using inliers
        inlier_offsets = offsets[inlier_mask]
        final_offset = np.mean(inlier_offsets, axis=0)

        # Compute confidence based on inlier ratio
        confidence = inlier_count / len(good_matches)

        return {
            'offset': final_offset,  # [x_offset, y_offset]
            'confidence': confidence,
            'inliers': inlier_count,
            'total_matches': len(good_matches)
        }


def find_overlapping_pair(features_list: List, stitcher: FeatureStitcher,
                          exclude_indices: set = None) -> Optional[Tuple[int, int, Dict]]:
    """
    Find the best overlapping pair of images that haven't been stitched yet.
    """
    best_match = None
    best_confidence = 0

    for i in range(len(features_list)):
        if exclude_indices and i in exclude_indices:
            continue
        for j in range(len(features_list)):
            if i == j:
                continue
            if exclude_indices and j in exclude_indices:
                continue

            match = stitcher.find_match(features_list[i], features_list[j])
            if match and match['confidence'] > best_confidence:
                best_confidence = match['confidence']
                best_match = (i, j, match)

    return best_match


def stitch_frames_feature_based(frames: List[np.ndarray],
                                min_matches: int = 15) -> Optional[np.ndarray]:
    """
    Stitch frames using feature-based matching.
    Handles bidirectional scrolling and unordered frames.
    """
    if not frames:
        return None

    if len(frames) == 1:
        return frames[0].copy()

    print(f"[Feature Stitcher] Processing {len(frames)} frames...")

    # Initialize stitcher
    stitcher = FeatureStitcher(feature_type='orb', min_matches=min_matches)

    # Extract features for all frames
    print("[Feature Stitcher] Extracting features...")
    features_list = []
    for i, frame in enumerate(frames):
        kp, des = stitcher.extract_features(frame)
        features_list.append((kp, des))
        print(f"  Frame {i}: {len(kp) if kp is not None else 0} features")

    # Build connectivity: find which frames overlap
    print("[Feature Stitcher] Finding overlaps...")
    overlaps = {}  # (i, j) -> match_info

    for i in range(len(frames)):
        for j in range(len(frames)):
            if i == j:
                continue
            match = stitcher.find_match(features_list[i], features_list[j])
            if match:
                offsets = match['offset']
                print(f"  Frames {i}->{j}: offset=({offsets[0]:.1f}, {offsets[1]:.1f}), conf={match['confidence']:.2f}")
                overlaps[(i, j)] = match

    if not overlaps:
        print("[Feature Stitcher] No overlaps found! Falling back to sequential stitching...")
        return stitch_sequential_fallback(frames)

    # Build panorama starting from the frame with most connections
    print("[Feature Stitcher] Building panorama...")

    # Find frame with most outgoing connections
    connection_count = defaultdict(int)
    for (i, j), match in overlaps.items():
        if match['confidence'] > 0.3:
            connection_count[i] += 1

    if not connection_count:
        print("[Feature Stitcher] No confident connections, using sequential fallback")
        return stitch_sequential_fallback(frames)

    # Start with most connected frame
    start_frame = max(connection_count.keys(), key=lambda k: connection_count[k])
    print(f"[Feature Stitcher] Starting from frame {start_frame}")

    # Build panorama using BFS
    stitched = frames[start_frame].copy()
    stitched_indices = {start_frame}
    frame_positions = {start_frame: (0, 0)}  # frame_id -> (x_offset, y_offset) in panorama

    # Queue of frames to process
    queue = [start_frame]

    while queue:
        current = queue.pop(0)

        # Find frames that overlap with current
        for j in range(len(frames)):
            if j in stitched_indices:
                continue

            match = overlaps.get((current, j))
            if not match or match['confidence'] < 0.2:
                continue

            offset = match['offset']

            # For screen captures, we expect mostly vertical scrolling
            # Positive y_offset means j is below current (scrolled down)
            # Negative y_offset means j is above current (scrolled up)

            y_offset = int(round(offset[1]))
            x_offset = int(round(offset[0]))

            # Get position of current frame in panorama
            curr_x, curr_y = frame_positions[current]

            # Position of new frame
            new_x = curr_x - x_offset
            new_y = curr_y - y_offset

            # Stitch new frame
            h, w = frames[j].shape[:2]
            stitched_h, stitched_w = stitched.shape[:2]

            # Calculate new canvas size
            min_x = min(0, new_x)
            max_x = max(stitched_w, new_x + w)
            min_y = min(0, new_y)
            max_y = max(stitched_h, new_y + h)

            new_w = max_x - min_x
            new_h = max_y - min_y

            # Create new canvas
            new_canvas = np.zeros((new_h, new_w, 3), dtype=np.uint8)

            # Copy existing stitched image
            old_x_offset = -min_x
            old_y_offset = -min_y
            new_canvas[old_y_offset:old_y_offset + stitched_h,
                      old_x_offset:old_x_offset + stitched_w] = stitched

            # Add new frame
            frame_x = new_x - min_x
            frame_y = new_y - min_y

            # Use HARD CUT at overlap boundary - no blending to avoid ghosting
            # The new frame replaces the old content where it overlaps

            # Place new frame (it will overwrite overlap region)
            new_canvas[frame_y:frame_y + h, frame_x:frame_x + w] = frames[j]

            stitched = new_canvas
            stitched_indices.add(j)
            frame_positions[j] = (new_x, new_y)
            queue.append(j)

            print(f"  Added frame {j}: canvas now {stitched.shape[1]}x{stitched.shape[0]}")

    print(f"[Feature Stitcher] Final size: {stitched.shape[1]}x{stitched.shape[0]}")
    return stitched


def stitch_sequential_fallback(frames: List[np.ndarray],
                               min_overlap: int = 30) -> Optional[np.ndarray]:
    """
    Fallback: Sequential stitching assuming frames are in order.
    """
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0].copy()

    print(f"[Sequential Fallback] Stitching {len(frames)} frames...")

    result = frames[0].copy()

    for i in range(1, len(frames)):
        curr = frames[i]

        # Ensure same width
        if curr.shape[1] != result.shape[1]:
            curr = cv2.resize(curr, (result.shape[1], curr.shape[0]))

        # Find vertical overlap using correlation
        h1, h2 = result.shape[0], curr.shape[0]
        max_overlap = min(h1, h2) - 10

        best_overlap = min_overlap
        best_score = 0

        for overlap in range(min_overlap, max_overlap, 5):
            prev_region = result[-overlap:]
            curr_region = curr[:overlap]

            # Normalized correlation
            prev_norm = prev_region.astype(float) - np.mean(prev_region)
            curr_norm = curr_region.astype(float) - np.mean(curr_region)

            std_prev = np.std(prev_region)
            std_curr = np.std(curr_region)

            if std_prev > 0 and std_curr > 0:
                ncc = np.mean(prev_norm * curr_norm) / (std_prev * std_curr)
                if ncc > best_score:
                    best_score = ncc
                    best_overlap = overlap

        print(f"  Frame {i}: overlap={best_overlap}px (score={best_score:.3f})")

        # Add non-overlapping portion
        new_portion = curr[best_overlap:]
        result = np.vstack([result, new_portion])

    print(f"[Sequential Fallback] Final size: {result.shape[1]}x{result.shape[0]}")
    return result


def deduplicate_identical_frames(frames: List[np.ndarray],
                                  threshold: float = 1.0) -> List[np.ndarray]:
    """
    Remove only truly identical frames (very low threshold).
    Compare each frame with the LAST KEPT frame, not the previous frame.
    """
    if len(frames) <= 2:
        return frames

    print(f"=== DEDUPLICATION (threshold={threshold}) ===")

    deduped = [frames[0]]

    for i in range(1, len(frames)):
        # CRITICAL: Compare with LAST KEPT frame, not previous frame in sequence
        prev_kept = deduped[-1]
        curr = frames[i]

        if prev_kept.shape != curr.shape:
            deduped.append(curr)
            continue

        diff = np.mean(np.abs(prev_kept.astype(float) - curr.astype(float)))

        if diff > threshold:  # Only keep if sufficiently different
            deduped.append(curr)

    removed = len(frames) - len(deduped)
    print(f"Deduplication: {len(frames)} -> {len(deduped)} frames (removed {removed})")

    return deduped


def stitch_frames(frames: List[np.ndarray],
                  min_overlap: int = 30) -> Optional[np.ndarray]:
    """
    Main stitching function.
    Uses simple vertical stitching inspired by Fullshot extension principles.
    """
    if not frames:
        return None

    if len(frames) == 1:
        return frames[0].copy()

    print(f"Stitching {len(frames)} frames...")

    # Import and use the simple vertical stitcher
    try:
        from stitch.simple_vertical import stitch_frames_simple
        return stitch_frames_simple(frames)
    except ImportError as e:
        print(f"Error importing simple stitcher: {e}")
        return None

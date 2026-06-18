"""
围栏跟随算法单元测试 — RANSAC + PCA 直线拟合 + PID 控制

目标覆盖率: ≥75%
测试内容: PCA 直线拟合、RANSAC 鲁棒性、角度/距离计算

注意: 此文件测试核心算法函数，与 fence_follower.py 中实现完全一致。
      独立运行，不依赖 ROS 2 环境。
"""

import math

import numpy as np

# ── 从 fence_follower.py 复制的核心算法 (保持与生产代码一致) ──


def pca_line(xy: np.ndarray):
    """PCA 总体最小二乘直线拟合 (ax + by + c = 0) — 与 fence_follower.py 一致"""
    if len(xy) < 2:
        return None
    mean = xy.mean(axis=0)
    centered = xy - mean
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    a, b = normal[0], normal[1]
    c = -(a * mean[0] + b * mean[1])
    if b < 0:
        a, b, c = -a, -b, -c
    return (float(a), float(b), float(c))


def ransac_line(
    xy: np.ndarray, min_samples: int = 10, residual_threshold: float = 0.05, max_trials: int = 100
):
    """RANSAC 直线拟合 — 与 fence_follower.py 一致"""
    n = len(xy)
    if n < min_samples:
        return None
    best_inliers = 0
    best_line = None
    rng = np.random.default_rng()
    for _ in range(max_trials):
        idx = rng.choice(n, size=min(min_samples, n), replace=False)
        sample = xy[idx]
        line = pca_line(sample)
        if line is None:
            continue
        a, b, c = line
        dists = np.abs(a * xy[:, 0] + b * xy[:, 1] + c) / math.sqrt(a * a + b * b)
        inliers = int(np.sum(dists < residual_threshold))
        if inliers > best_inliers:
            best_inliers = inliers
            best_line = line
    if best_line is None:
        return None
    a0, b0, c0 = best_line
    all_dists = np.abs(a0 * xy[:, 0] + b0 * xy[:, 1] + c0) / math.sqrt(a0 * a0 + b0 * b0)
    inlier_mask = all_dists < residual_threshold
    if np.sum(inlier_mask) >= min_samples:
        best_line = pca_line(xy[inlier_mask])
    return best_line


# ═══════════════════════════════════════════════════
# pca_line — PCA 总体最小二乘直线拟合
# ═══════════════════════════════════════════════════


class TestPcaLine:
    """PCA 直线拟合: ax + by + c = 0"""

    def test_perfect_horizontal_line(self):
        """水平线 y=2 → a=0, b≈1, c≈-2"""
        xy = np.array([[0.0, 2.0], [1.0, 2.0], [3.0, 2.0], [5.0, 2.0]])
        result = pca_line(xy)
        assert result is not None
        a, b, c = result
        # 水平线: a≈0, b≠0
        assert abs(a) < 0.01
        assert b > 0
        # 点到直线距离应 ≈ 0
        for x, y in xy:
            d = abs(a * x + b * y + c) / math.sqrt(a * a + b * b)
            assert d < 0.001

    def test_perfect_vertical_line(self):
        """垂直线 x=3 → a≈1, b≈0, c≈-3"""
        xy = np.array([[3.0, 0.0], [3.0, 1.0], [3.0, 2.0], [3.0, 5.0]])
        result = pca_line(xy)
        assert result is not None
        a, b, c = result
        # 垂直线: b≈0  (之前 y=f(x) 回归会崩溃)
        assert abs(b) < 0.01
        for x, y in xy:
            d = abs(a * x + b * y + c) / math.sqrt(a * a + b * b)
            assert d < 0.001

    def test_diagonal_line(self):
        """45° 斜线 y=x"""
        xy = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
        result = pca_line(xy)
        assert result is not None
        a, b, c = result
        # 法向量应该 ≈ (1/√2, -1/√2) 或相反
        norm = math.sqrt(a * a + b * b)
        assert abs(a / norm - 0.707) < 0.01 or abs(a / norm + 0.707) < 0.01
        for x, y in xy:
            d = abs(a * x + b * y + c) / norm
            assert d < 0.001

    def test_only_two_points(self):
        """边界: 仅2个点"""
        xy = np.array([[0.0, 0.0], [10.0, 10.0]])
        result = pca_line(xy)
        assert result is not None

    def test_returns_none_for_single_point(self):
        """边界: 少于2个点返回 None"""
        xy = np.array([[1.0, 1.0]])
        result = pca_line(xy)
        assert result is None

    def test_noisy_line_still_good_fit(self):
        """带噪声的直线"""
        rng = np.random.default_rng(42)
        x = np.linspace(0, 5, 50)
        y = 2.0 * x + 1.0 + rng.normal(0, 0.01, 50)  # y=2x+1 + tiny noise
        xy = np.column_stack([x, y])
        result = pca_line(xy)
        assert result is not None
        a, b, c = result
        # 2x - y + 1 = 0 → a≈2, b≈-1, c≈1  (normalized)
        ratio = a / b if abs(b) > 0.001 else float('inf')
        assert abs(ratio - (-2.0)) < 0.1


# ═══════════════════════════════════════════════════
# ransac_line — RANSAC 直线拟合
# ═══════════════════════════════════════════════════


class TestRansacLine:
    """RANSAC 鲁棒直线拟合"""

    def test_clean_line_returns_good_fit(self):
        """无离群点时正常工作"""
        xy = np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [2.0, 2.0],
                [3.0, 3.0],
                [4.0, 4.0],
                [5.0, 5.0],
                [6.0, 6.0],
                [7.0, 7.0],
                [8.0, 8.0],
                [9.0, 9.0],
                [10.0, 10.0],
            ]
        )
        result = ransac_line(xy, min_samples=5, residual_threshold=0.05)
        assert result is not None
        a, b, c = result
        # 应拟合 y=x → a+b≈0
        assert abs(a + b) < 0.1

    def test_ignores_outliers(self):
        """RANSAC 忽略离群点"""
        rng = np.random.default_rng(42)
        # 9 个内点: y = 0 (水平线)
        inliers = np.column_stack([np.linspace(0, 8, 9), np.zeros(9)])
        # 10 个离群点: 散乱
        outliers = rng.uniform(-5, 5, (10, 2))
        xy = np.vstack([inliers, outliers])

        result = ransac_line(xy, min_samples=5, residual_threshold=0.1)
        assert result is not None
        a, b, c = result
        # 应拟合水平线: a≈0
        assert abs(a) < 0.1

    def test_majority_outliers_still_works(self):
        """大量离群点时仍能找到线 (50% 离群点)"""
        rng = np.random.default_rng(42)
        # 25 个内点: x = 2 (垂直线)
        inliers = np.column_stack([np.full(25, 2.0), np.linspace(0, 24, 25)])
        # 25 个离群点 (50/50)
        outliers = rng.uniform(-5, 5, (25, 2))
        xy = np.vstack([inliers, outliers])

        result = ransac_line(xy, min_samples=8, residual_threshold=0.1, max_trials=500)
        assert result is not None
        a, b, c = result
        # 应拟合垂直线: |b| 应远小于 |a|
        assert abs(b) < abs(a) * 0.3

    def test_too_few_points_returns_none(self):
        """点数不足 min_samples 时返回 None"""
        xy = np.array([[0.0, 0.0], [1.0, 1.0]])
        result = ransac_line(xy, min_samples=5)
        assert result is None

    def test_all_points_collinear(self):
        """所有点共线"""
        xy = np.column_stack([np.arange(20, dtype=float), np.zeros(20)])
        result = ransac_line(xy, min_samples=5, residual_threshold=0.05)
        assert result is not None
        a, b, c = result
        assert abs(a) < 0.01  # 水平线

    def test_parallel_to_y_axis(self):
        """平行于 y 轴的围栏 (最常见场景)"""
        # 模拟 LiDAR 看到的围栏: x≈0.5 (围栏在左侧0.5m)
        rng = np.random.default_rng(42)
        y = np.linspace(-2, 2, 30)
        x = np.full(30, 0.5) + rng.normal(0, 0.005, 30)
        xy = np.column_stack([x, y])

        result = ransac_line(xy, min_samples=8, residual_threshold=0.02)
        assert result is not None
        a, b, c = result
        # 垂直线: b≈0, 距离 = |c|/|a| ≈ 0.5
        assert abs(b) < 0.05
        dist = abs(c) / math.sqrt(a * a + b * b)
        assert abs(dist - 0.5) < 0.05


# ═══════════════════════════════════════════════════
# 角度/距离计算 (模拟 FenceFollower 中的逻辑)
# ═══════════════════════════════════════════════════


class TestFenceGeometry:
    """围栏检测几何计算"""

    def test_distance_to_origin(self):
        """原点到直线距离"""
        # 直线: x - 0.5 = 0 → a=1, b=0, c=-0.5
        a, b, c = 1.0, 0.0, -0.5
        dist = abs(c) / math.sqrt(a * a + b * b)
        assert abs(dist - 0.5) < 0.001

    def test_angle_from_normal(self):
        """直线角度计算"""
        # 垂直围栏 (平行 y 轴): a=1, b=0
        a, b = 1.0, 0.0
        angle = math.atan2(-a, b)
        # -a= -1, b=0 → atan2(-1,0) = -π/2
        assert abs(angle + math.pi / 2) < 0.001

    def test_lateral_error_sign_for_left_fence(self):
        """围栏在左侧时的横向误差符号"""
        # 围栏 x=0.5, 目标距离 0.5m, 当前位置在 (0,0)
        a, b, c = 1.0, 0.0, -0.5
        dist = abs(c) / math.sqrt(a * a + b * b)
        lateral_error = dist - 0.5  # target_distance = 0.5
        assert abs(lateral_error) < 0.001  # 正好在目标距离

        # 离得太远: 围栏在 1.0 但目标 0.5
        a2, b2, c2 = 1.0, 0.0, -1.0
        dist2 = abs(c2) / math.sqrt(a2 * a2 + b2 * b2)
        lateral_error2 = dist2 - 0.5
        assert lateral_error2 > 0  # 正的 = 需要靠近

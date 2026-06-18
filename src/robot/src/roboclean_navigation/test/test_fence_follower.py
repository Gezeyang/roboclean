"""
围栏跟随 v2 单元测试 — 通道中线追踪

目标覆盖率: ≥75%
测试: 角度筛选 / 离群点移除 / 中线计算 / PCA 拟合 / 曲率检测
"""

import math

import numpy as np

# ── 从 fence_follower.py 复制的算法函数 (生产代码一致) ──


def _filter_by_angle(xy: np.ndarray, ang_min: float, ang_max: float) -> np.ndarray:
    """筛选指定角度范围内的点"""
    if len(xy) == 0:
        return np.empty((0, 2))
    angles = np.arctan2(xy[:, 1], xy[:, 0])
    mask = (angles >= ang_min) & (angles <= ang_max)
    return xy[mask]


def _remove_outliers(pts: np.ndarray, outlier_dist: float = 0.15) -> np.ndarray:
    """移除离群点: 距离最近邻超过阈值的孤立点"""
    if len(pts) < 3:
        return pts
    order = np.argsort(pts[:, 1])
    sorted_pts = pts[order]
    diffs = np.abs(np.diff(sorted_pts[:, 0]))
    mask = np.ones(len(sorted_pts), dtype=bool)
    for i in range(1, len(sorted_pts) - 1):
        if diffs[i - 1] > outlier_dist and diffs[i] > outlier_dist:
            mask[i] = False
    return sorted_pts[mask]


def _compute_midline(left: np.ndarray, right: np.ndarray, n_slices: int = 20) -> np.ndarray | None:
    """计算通道中线: 逐切片取左右中点"""
    y_min = max(left[:, 1].min(), right[:, 1].min())
    y_max = min(left[:, 1].max(), right[:, 1].max())
    if y_max - y_min < 0.1:
        return None
    y_edges = np.linspace(y_min, y_max, n_slices + 1)
    pts: list[list[float]] = []
    for i in range(n_slices):
        y_lo, y_hi = y_edges[i], y_edges[i + 1]
        y_mid = (y_lo + y_hi) / 2.0
        left_slice = left[(left[:, 1] >= y_lo) & (left[:, 1] < y_hi)]
        right_slice = right[(right[:, 1] >= y_lo) & (right[:, 1] < y_hi)]
        if len(left_slice) == 0 or len(right_slice) == 0:
            continue
        xl = float(np.median(left_slice[:, 0]))
        xr = float(np.median(right_slice[:, 0]))
        pts.append([(xl + xr) / 2.0, y_mid])
    if len(pts) < 2:
        return None
    return np.array(pts)


def _fit_local_line(pts: np.ndarray) -> tuple[float | None, float | None, float | None]:
    """PCA 拟合 ax+by+c=0"""
    if len(pts) < 2:
        return None, None, None
    mean = pts.mean(axis=0)
    centered = pts - mean
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    a, b = float(normal[0]), float(normal[1])
    c = float(-(a * mean[0] + b * mean[1]))
    if b < 0:
        a, b, c = -a, -b, -c
    return a, b, c


def _compute_curvature_factor(midline: np.ndarray) -> float:
    """曲率 → 降速因子"""
    if len(midline) < 3:
        return 1.0
    pts = midline[: min(5, len(midline))]
    vectors = np.diff(pts, axis=0)
    angles = np.arctan2(vectors[:, 1], vectors[:, 0])
    if len(angles) < 2:
        return 1.0
    angle_change = float(np.abs(np.diff(angles)).mean())
    return max(0.3, 1.0 - angle_change / 0.5)


# ═══════════════════════════════════════════════════
# 角度筛选
# ═══════════════════════════════════════════════════


class TestAngleFilter:
    def test_left_side_filter(self):
        """负角度区域 (-80°~-10°): atan2(y,x) < 0, 即 y<0, x>0 的区域"""
        xy = np.array(
            [
                [1.0, -0.2],  # atan2 ≈ -11° → 在区域内 ✓
                [1.0, -1.0],  # atan2 ≈ -45° → 在区域内 ✓
                [1.0, 0.5],  # atan2 ≈ 27° → 不在区域内
                [0.5, 1.0],  # atan2 ≈ 63° → 不在区域内
            ]
        )
        result = _filter_by_angle(xy, math.radians(-80), math.radians(-10))
        assert len(result) == 2

    def test_right_side_filter(self):
        """正角度区域 (10°~80°): atan2(y,x) > 0, 即 y>0, x>0 的区域"""
        xy = np.array(
            [
                [1.0, 0.5],  # atan2 ≈ 27° → 在区域内 ✓
                [0.5, 1.0],  # atan2 ≈ 63° → 在区域内 ✓
                [1.0, -1.0],  # atan2 ≈ -45° → 不在区域内
            ]
        )
        result = _filter_by_angle(xy, math.radians(10), math.radians(80))
        assert len(result) == 2

    def test_empty_input(self):
        result = _filter_by_angle(np.empty((0, 2)), -1.0, 1.0)
        assert len(result) == 0


# ═══════════════════════════════════════════════════
# 离群点移除
# ═══════════════════════════════════════════════════


class TestOutlierRemoval:
    def test_clean_data_passes_through(self):
        """无离群点: 全部保留"""
        pts = np.column_stack([np.linspace(-0.5, 0.5, 10), np.linspace(0, 9, 10)])
        result = _remove_outliers(pts, outlier_dist=0.3)
        assert len(result) == 10

    def test_isolated_outlier_removed(self):
        """孤立点被移除"""
        pts = np.array(
            [
                [0.0, 0.0],
                [0.0, 1.0],
                [0.0, 2.0],
                [2.0, 3.0],  # ← 离群点
                [0.0, 4.0],
                [0.0, 5.0],
            ]
        )
        result = _remove_outliers(pts, outlier_dist=0.5)
        assert len(result) < 6  # 离群点被移除


# ═══════════════════════════════════════════════════
# 中线计算
# ═══════════════════════════════════════════════════


class TestMidline:
    def test_straight_channel(self):
        """直通道: 左 x=-1.5, 右 x=+1.5 → 中线 x=0"""
        left = np.column_stack([np.full(30, -1.5), np.linspace(0, 5, 30)])
        right = np.column_stack([np.full(30, 1.5), np.linspace(0, 5, 30)])
        midline = _compute_midline(left, right)
        assert midline is not None
        assert len(midline) >= 2
        # 中线 x 坐标应接近 0
        assert abs(midline[:, 0].mean()) < 0.1

    def test_converging_channel(self):
        """逐渐收窄的通道"""
        left = np.column_stack(
            [
                np.linspace(-2.0, -1.0, 20),
                np.linspace(0, 5, 20),
            ]
        )
        right = np.column_stack(
            [
                np.linspace(2.0, 1.0, 20),
                np.linspace(0, 5, 20),
            ]
        )
        midline = _compute_midline(left, right)
        assert midline is not None
        assert len(midline) >= 2
        # 中线 x 应在 [-0.5, 0.5] 之间
        assert abs(midline[-1, 0]) < 0.5

    def test_no_overlap_returns_none(self):
        """无重叠区域 → None"""
        left = np.column_stack([np.full(5, -1.0), np.linspace(0, 2, 5)])
        right = np.column_stack([np.full(5, 1.0), np.linspace(3, 5, 5)])
        midline = _compute_midline(left, right)
        assert midline is None


# ═══════════════════════════════════════════════════
# PCA 局部拟合
# ═══════════════════════════════════════════════════


class TestLocalFit:
    def test_straight_midline(self):
        """x=0 沿 y 轴的线 → a≈1, b≈0, c≈0"""
        pts = np.column_stack([np.zeros(10), np.linspace(0, 5, 10)])
        a, b, c = _fit_local_line(pts)
        assert a is not None
        # 线 x=0 → 1*x + 0*y + 0 = 0, 即 a≈±1, b≈0, c≈0
        assert abs(a) > 0.9  # a 接近 ±1
        assert abs(b) < 0.1  # b 接近 0
        assert abs(c) < 0.1  # c 接近 0 (过原点)

    def test_two_points(self):
        pts = np.array([[0.0, 0.0], [1.0, 1.0]])
        a, b, c = _fit_local_line(pts)
        assert a is not None

    def test_single_point_returns_none(self):
        pts = np.array([[1.0, 1.0]])
        a, b, c = _fit_local_line(pts)
        assert a is None


# ═══════════════════════════════════════════════════
# 曲率降速
# ═══════════════════════════════════════════════════


class TestCurvatureFactor:
    def test_straight_line_full_speed(self):
        """直线 → 全速"""
        midline = np.column_stack([np.zeros(5), np.linspace(0, 4, 5)])
        factor = _compute_curvature_factor(midline)
        assert factor > 0.9

    def test_curve_reduces_speed(self):
        """弯道 → 降速"""
        midline = np.array(
            [
                [0.0, 0.0],
                [0.1, 0.5],
                [0.4, 1.0],
                [0.8, 1.2],
                [1.3, 1.3],
            ]
        )
        factor = _compute_curvature_factor(midline)
        assert factor < 1.0

    def test_short_midline_returns_one(self):
        midline = np.array([[0.0, 0.0], [0.1, 0.5]])
        assert _compute_curvature_factor(midline) == 1.0

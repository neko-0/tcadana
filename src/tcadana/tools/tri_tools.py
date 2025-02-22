import numpy as np
from matplotlib.tri import Triangulation


def crop_triangles(tri, xlim=None, ylim=None):
    """
    Crop a triangulation to a specified rectangular region.

    Parameters
    ----------
    tri : matplotlib.tri.Triangulation
        Input triangulation to be cropped.
    xlim : tuple, optional
        X-axis limits of the cropping region. Defaults to None.
    ylim : tuple, optional
        Y-axis limits of the cropping region. Defaults to None.

    Returns
    -------
    Triangulation
        The cropped triangulation, or None if the entire triangulation is outside the cropping region.
    """
    if xlim is None and ylim is None:
        return tri

    triangles = tri.triangles
    x, y = tri.x, tri.y
    x_min = x[triangles].min(axis=1)
    x_max = x[triangles].max(axis=1)
    y_min = y[triangles].min(axis=1)
    y_max = y[triangles].max(axis=1)

    # assume triangles are initially valid and within the ranges
    mask = np.ones(triangles.shape[0], dtype=bool)
    if xlim is not None:
        mask &= (x_min >= min(xlim)) & (x_max <= max(xlim))
    if ylim is not None:
        mask &= (y_min >= min(ylim)) & (y_max <= max(ylim))

    if not mask.any():
        return None

    return Triangulation(x, y, triangles, mask)


def cutline_2d(tri, field, axis, value, tolerance=1.0):
    diff = np.abs(getattr(tri, axis) - value)
    indices = diff <= max(tolerance, diff.min())
    other_axis = getattr(tri, 'x' if axis == 'y' else 'y')
    return other_axis[indices], field[indices]


def xcutline(tri, field, xcut, tolerance=1.0):
    return cutline_2d(tri, field, 'x', xcut, tolerance)


def ycutline(tri, field, ycut, tolerance=1.0):
    return cutline_2d(tri, field, 'y', ycut, tolerance)

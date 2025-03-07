import logging
from functools import cache

import h5py
import numpy as np
from matplotlib.tri import Triangulation

try:
    import numba as nb

    FOUND_NUMBA = True
except ImportError:
    FOUND_NUMBA = False


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

if FOUND_NUMBA:

    @nb.njit(cache=True, error_model='numpy')
    def extract_triangles_numba(raw_triangles):
        if np.any(raw_triangles[::4] != 2):
            raise ValueError("contains non triangles")
        return raw_triangles.reshape(-1, 4)[:, 1:]


def extract_triangles(raw_triangles):
    # Check if all elements in the region are triangles (type identifier is 2)
    # for a 2D structure, the array is in the form of [2, 275, 278, 276, 2, 276, 283, 281, ...]
    if np.any(raw_triangles[::4] != 2):
        raise ValueError("contains non triangles")

    # Reshape the raw triangles array into a 2D array with shape (n_triangles, 3)
    # where each row represents a triangle and the three columns are the vertex indices
    return raw_triangles.reshape(-1, 4)[:, 1:]


def open_tdr(filename):
    if isinstance(filename, TDRFile):
        return filename
    tdr_file = TDRFile(filename)
    tdr_file.load()
    return tdr_file


class TDRFile:
    __slots__ = (
        "_filename",
        "_file",
        "_region_names",
        "_field_names",
        "geo",
        "vertex",
        "state",
    )

    def __init__(self, filename):
        self._filename = filename
        self._file = None
        self._region_names = None
        self._field_names = None
        self.geo = None
        self.vertex = None
        self.state = None

    def __del__(self):
        self.close()

    def __getitem__(self, key):
        return self._file[key]

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, filename):
        self.close()
        self._filename = filename
        self.load()

    @property
    def file(self):
        if self._file is None:
            self.load()
        return self._file

    @property
    def region_names(self):
        if self._region_names is None:
            self._region_names = set(self.get_region_names())
        return self._region_names

    @property
    def field_names(self):
        if self._field_names is None:
            self._field_names = set(self.get_field_names())
        return self._field_names

    @property
    def dimensions(self):
        """Return the minimum and maximum values for each dimension."""
        dim = lambda x: (self.vertex[x].min(), self.vertex[x].max())
        return {x: dim(x) for x in self.vertex.dtype.names}

    def load(self):
        if self._file:
            return
        self._file = h5py.File(self.filename, "r")
        self.geo = self._file["collection/geometry_0"]
        self.vertex = self.geo["vertex"]
        self.state = self.geo["state_0"]

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None
        self._region_names = None
        self._field_names = None
        self.geo = None
        self.vertex = None
        self.state = None

    def get_region_names(self):
        """Yield names of regions in the geo data."""
        for key in self.geo:
            if key.startswith("region_"):
                yield self.geo[key].attrs["name"].decode("utf-8")

    def get_field_names(self):
        """Yield names of fields in the state data."""
        for dataset in self.state.values():
            yield dataset.attrs["name"].decode("utf-8")

    def get_region_field_names(self, region_name):
        """Yield field names for a given region."""
        region_name_bytes = region_name.encode("UTF-8")
        for dataset in self.state.values():
            region_name = f"region_{dataset.attrs['region']}"
            if self.geo[region_name].attrs["name"] != region_name_bytes:
                continue
            yield dataset.attrs["quantity"].decode("utf-8")

    @cache
    def get_region(self, region_name):
        region_name_bytes = region_name.encode("UTF-8")
        for key, value in self.geo.items():
            if key.startswith("region_"):
                if value.attrs["name"] == region_name_bytes:
                    return int(key.lstrip("region_")), self.geo[key]

        return None

    @cache
    def get_region_field_data(self, region_name, field_name=None):
        """
        Load triangles and vertices from a region in a collection.

        Parameters:
            region_name : str
                The name of the region to load.
            field_name : str or None
                The name of the field to load. If None, only the vertices and triangles
                are returned.

        Returns:
            vertices : numpy.array
                A 2D array of vertices in the region with shape (n, 2) where n is the
                number of vertices.
            triangles : numpy.array
                A 2D array of triangles in the region with shape (m, 3) where m is the
                number of triangles.
            field_values : numpy.array or None
                A 1D array of field values in the region with shape (n) if field_name is
                not None, otherwise None.
        """
        # get region Group key
        region_num, region = self.get_region(region_name)
        if region is None:
            raise KeyError(f"Unable to obtain regionkey for {region_name}")

        # Get the list of elements in the region, which includes type identifiers and vertex indices
        # extract triangles from the elements array
        triangles = extract_triangles(region["elements_0"][:])

        # remove vertices and indices outside of region (so vertex list matches field list)
        # old implementation
        # converter = np.full(len(self.vertex), -1, np.int64)
        # for i, v in enumerate(sorted(set(triangles.flatten()))):
        #     converter[v] = i
        # triangles2 = converter[triangles]
        # vertices = self.vertex[converter >= 0]
        # vertices = np.column_stack((vertices["x"], vertices["y"]))

        # new implementation
        unique_vertices, inverse = np.unique(triangles, return_inverse=True)
        converter = np.full(len(self.vertex), -1)
        converter[unique_vertices] = np.arange(len(unique_vertices))
        triangles = inverse.reshape(triangles.shape)
        vertices = self.vertex[converter >= 0]
        vertices = np.c_[vertices['x'], vertices['y']]

        # add field to returns if field_name is specified
        if field_name is None:
            return vertices, triangles

        fieldkey = None
        field_name_bytes = field_name.encode("UTF-8")
        for key, state_data in self.state.items():
            if "region" not in state_data.attrs:
                continue
            if "quantity" not in state_data.attrs:
                continue
            # check region number
            if state_data.attrs["region"] != region_num:
                continue
            # matching field name field name.
            if state_data.attrs["quantity"] != field_name_bytes:
                continue
            fieldkey = key
            break

        if fieldkey is None:
            logger.warning(f"Unable to match field name {field_name}")
            return vertices, triangles

        return vertices, triangles, self.state[f"{fieldkey}/values"][:]

    def get_region_field_data_dict(self, region_names=None, field_names=None):
        """
        Get triangulation and field data for all regions in a TDR collection.

        Parameters
        ----------
        region_names : list, optional
            The names of the regions to get data for. If `None`, get all regions.

        field_names : list, optional
            The names of the fields to get data for. If `None`, get all fields.

        Returns
        -------
        region_field_data : dict of dicts
            A dictionary where the keys are the region names, and the values are
            dictionaries where the keys are the field names and the values are
            dictionaries with 'tri' and 'field' keys. The 'tri' key has a
            `matplotlib.tri.Triangulation` object, and the 'field' key has the
            corresponding field data.
        """
        if region_names is None:
            region_names = self.region_names
        if field_names is None:
            field_names = self.field_names

        get_data = self.get_region_field_data
        region_field_data = {}
        for region_name in region_names:
            region_field_data[region_name] = {}
            for field_name in field_names:
                try:
                    vertices, triangles, field = get_data(region_name, field_name)
                except ValueError:
                    continue
                region_field_data[region_name][field_name] = {
                    "tri": Triangulation(*vertices.T, triangles),
                    "field": field,
                }

        # remove empty regions and return
        return {
            region_name: field_data
            for region_name, field_data in region_field_data.items()
            if field_data
        }

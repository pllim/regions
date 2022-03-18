# Licensed under a 3-clause BSD style license - see LICENSE.rst

from dataclasses import dataclass
import warnings

from astropy.io import fits
from astropy.table import QTable
import astropy.units as u
from astropy.utils.exceptions import AstropyUserWarning
import numpy as np

from ...core import Region, Regions, SkyRegion
from ...core.registry import RegionsRegistry

__all__ = []


@RegionsRegistry.register(Region, 'serialize', 'fits')
@RegionsRegistry.register(Regions, 'serialize', 'fits')
def _serialize_fits(regions):
    region_data = []
    for region in regions:
        if isinstance(region, SkyRegion):
            warnings.warn('Sky regions cannot be serialized to the FITS '
                          'region format, skipping.', AstropyUserWarning)
        region_data.append(_serialize_region_fits(region))

    fits_table = _make_table(region_data)
    return fits_table


@RegionsRegistry.register(Region, 'write', 'fits')
@RegionsRegistry.register(Regions, 'write', 'fits')
def _write_fits(regions, filename, header=None, overwrite=False):
    """
    Convert a list of `~regions.Region` to a FITS region table and write
    to a file.

    Parameters
    ----------
    regions : list
        A list of `~regions.Region` objects.

    filename : str
        The filename in which the table is to be written.

    header : `~astropy.io.fits.Header`, optional
        The FITS header.

    overwrite : bool, optional
        If True, overwrite the output file if it exists. Raises an
        `OSError` if False and the output file exists. Default is False.
    """
    output = _serialize_fits(regions)
    bin_table = fits.BinTableHDU(data=output, header=header)
    bin_table.writeto(filename, overwrite=overwrite)


@dataclass
class _RegionData:
    """
    Class to hold region data.
    """
    shape: str
    x: np.ndarray
    y: np.ndarray
    r: np.ndarray
    rotang: np.ndarray


def _serialize_region_fits(region):
    # translate region class to FITS shape name
    shape = region.__class__.__name__.lower().replace('pixelregion', '')
    region_map = {'circleannulus': 'annulus',
                  'ellipseannulus': 'elliptannulus',
                  'rectangle': 'rotbox'}
    if shape in region_map:
        shape = region_map[shape]

    shape_params = []
    rotang = None
    for param in region._params:
        value = getattr(region, param)
        if param in ('center', 'vertices'):
            x, y = value.xy
        elif param == 'angle':
            rotang = value
        else:
            shape_params.append(value)

    if not shape_params:
        shape_params = 0
    if rotang is None:
        rotang = u.Quantity(0, 'deg')

    return _RegionData(shape, np.atleast_1d(x), np.atleast_1d(y),
                       np.atleast_1d(shape_params), np.atleast_1d(rotang))


def _make_column(arrays):
    arr_sizes = [arr.size for arr in arrays]
    arr_size = np.max(arr_sizes)

    data = []
    for (arr, size) in zip(arrays, arr_sizes):
        pad_width = arr_size - size
        if pad_width != 0:
            arr = np.pad(arr, (0, pad_width), mode='constant')
        if not isinstance(arr[0], u.Quantity):
            arr <<= u.pix
        data.append(arr)

    data = u.Quantity(data)

    return data


def _make_table(region_data):
    tbl = QTable()
    attrs = ('shape', 'x', 'y', 'r', 'rotang')

    for attr in attrs:
        arrays = [getattr(data, attr) for data in region_data]
        if attr != 'shape':
            arrays = _make_column(arrays)
        tbl[attr.upper()] = arrays
    return tbl

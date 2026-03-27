#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mkgraticule_planet.py

Create planetary graticules for IAU coordinate systems and export them as GeoPackage.

Based on the GDAL sample script mkgraticule.py
https://github.com/OSGeo/gdal/blob/master/swig/python/gdal-utils/osgeo_utils/samples/mkgraticule.py

Requirements
------------
GDAL Python bindings (conda install gdal)

Example
-------
python mkgraticule_planet.py -g 10 10 -r 0.2 0.2 -srs IAU_2015:30100 -e -180 90 180 -90 out.gpkg
"""

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ryodo Hemmi
#
# This software is provided "as is", without warranty of any kind.

__version__ = "0.4.0"

try:
    from osgeo import osr, ogr, gdal
except ImportError:
    import osr
    import ogr
    import gdal

osr.UseExceptions()
ogr.UseExceptions()
gdal.UseExceptions()

import os
import sys
import argparse
import sqlite3
import re
import numpy as np

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter, argparse.MetavarTypeHelpFormatter):
    pass

def get_args():
    parser = argparse.ArgumentParser(formatter_class=CustomFormatter)

    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument("outfile", type=str, help="Set the output filename")

    parser.add_argument(
        "-g",
        "--grid",
        type=float,
        nargs=2,
        metavar=("xstep", "ystep"),
        default=[5, 5],
        help="Set grid size [xstep ystep] in degrees",
    )
    parser.add_argument(
        "-r",
        "--res",
        type=float,
        nargs=2,
        metavar=("xres", "yres"),
        default=[0.1, 0.1],
        help="Set resolution to polygonize grids [xres yres] in degrees",
    )
    parser.add_argument(
        "-m",
        "--major",
        type=float,
        nargs=2,
        metavar=("xmajor", "ymajor"),
        default=None,
        help="Major graticule interval [xmajor ymajor] in degrees.\
            \nIf set, grid_type will be 'major' or 'minor'.\
            \nIf omitted, grid_type is NULL.",
    )
    parser.add_argument(
        "-srs",
        "--srs",
        type=str,
        default="IAU_2015:30100",
        help="Set target spatial reference (IAU code or *.prj file).\
            \nSee https://spatialreference.org/",
    )
    parser.add_argument(
        "-e",
        "--extent",
        type=float,
        nargs=4,
        metavar=("ulx", "uly", "lrx", "lry"),
        default=[-180, 90, 180, -90],
        help="Set a spatial extent of the output file",
    )
    parser.add_argument(
        "-s",
        "--skipfailures",
        action="store_true",
        help="Skip features that fail reprojection (equivalent to GDAL -skipfailures).",
    )

    parser.add_argument(
        "-p",
        "--partial-reprojection",
        action="store_true",
        help="Enable partial reprojection (OGR_ENABLE_PARTIAL_REPROJECTION=TRUE).\
            \nMay output truncated/split geometries near projection domain limits.",
    )

    parser.add_argument(
        "-nde",
        "--no-duplicate-endpoint",
        action="store_true",
        help="Drop the duplicate endpoint meridian when the longitude span is ~360 degrees\
            \n(e.g., keep -180 and drop 180, or keep 0 and drop 360).",
    )

    parser.add_argument(
        "-l",
        "--layer",
        type=str,
        default=None,
        help="Set output layer name explicitly.\
            \nIf not set, use the basename of outfile without extension instead.",
    )
    parser.add_argument(
        "-lo",
        "--lat-orig",
        type=float,
        default=None,
        help="Overwrite latitude of origin / false origin / natural origin in the target projected CRS (degrees).",
    )
    parser.add_argument(
        "-ls",
        "--lat-sp",
        type=float,
        default=None,
        help="Overwrite standard parallel in the target projected CRS.\
            \nFor 2SP projections, this overwrites the 1st standard parallel (degrees).",
    )
    parser.add_argument(
        "-ls2",
        "--lat-sp2",
        type=float,
        default=None,
        help="Overwrite the 2nd standard parallel in the target projected CRS (degrees).",
    )

    args = parser.parse_args()

    xstep, ystep = args.grid
    xres, yres = args.res
    for name, value in (("xstep", xstep), ("ystep", ystep), ("xres", xres), ("yres", yres)):
        if value <= 0:
            parser.error(f"{name} must be > 0 (got {value}).")

    if xstep > 360:
        parser.error(f"xstep must be <= 360 (got {xstep}).")
    if ystep > 180:
        parser.error(f"ystep must be <= 180 (got {ystep}).")

    ulx, uly, lrx, lry = args.extent
    if ulx >= lrx:
        parser.error(f"extent requires ulx < lrx (got ulx={ulx}, lrx={lrx}).")
    if uly <= lry:
        parser.error(f"extent requires uly > lry (got uly={uly}, lry={lry}).")

    for name, value in (("lat-orig", args.lat_orig), ("lat-sp", args.lat_sp), ("lat-sp2", args.lat_sp2)):
        if value is not None and not (-90.0 <= value <= 90.0):
            parser.error(f"{name} must be within [-90, 90] degrees (got {value}).")

    if args.major is not None:
        xmajor, ymajor = args.major
        for name, value in (("xmajor", xmajor), ("ymajor", ymajor)):
            if value <= 0:
                parser.error(f"{name} must be > 0 (got {value}).")

        xr = xmajor / xstep
        yr = ymajor / ystep
        if abs(xr - round(xr)) > 1e-9 or round(xr) < 1:
            parser.error(
                f"xmajor must be a natural-number multiple of xstep (got xmajor={xmajor}, xstep={xstep})."
            )
        if abs(yr - round(yr)) > 1e-9 or round(yr) < 1:
            parser.error(
                f"ymajor must be a natural-number multiple of ystep (got ymajor={ymajor}, ystep={ystep})."
            )

    return args


def progress_bar(i, range_values, strings, progress_bar_width=20):
    total_lines = len(range_values)
    progress = int((i + 1) / total_lines * progress_bar_width)
    percent = (i + 1) / total_lines * 100
    bar = "[" + "#" * progress + " " * (progress_bar_width - progress) + "]"
    sys.stdout.write(f"\r{strings}{bar} {percent:6.2f}%")
    sys.stdout.flush()


def export_wkt2_2019(srs: osr.SpatialReference) -> str:
    """
    Equivalent to: gdalsrsinfo -o wkt2_2019 <CRS>
    (The input CRS here must match the CRS provided via -srs)
    """
    try:
        return srs.ExportToWkt(["format=wkt2_2019"])
    except Exception:
        try:
            return srs.ExportToWkt(["format=wkt2"])
        except Exception:
            return srs.ExportToWkt()

def export_pretty_wkt(srs: osr.SpatialReference) -> str:
    """
    Return a human-readable WKT string for console output.
    Prefer GDAL/OSR's pretty exporter so this works without pyproj.
    """
    try:
        pretty = srs.ExportToPrettyWkt(0)
        if pretty:
            return pretty
    except Exception:
        pass

    wkt = export_wkt2_2019(srs)

    try:
        import pyproj
        return pyproj.CRS.from_wkt(wkt).to_wkt(pretty=True)
    except Exception:
        return wkt


def update_gpkg_spatial_ref_sys_with_wkt2_2019(gpkg_path: str, srs: osr.SpatialReference) -> None:
    """
    Implements the equivalent of:
      gdalsrsinfo -o wkt2_2019 <CRS> > tmp.prj
      sqlite3 <gpkg>:
        ALTER TABLE gpkg_spatial_ref_sys ADD COLUMN definition_12_063 TEXT;
        UPDATE gpkg_spatial_ref_sys
          SET definition_12_063 = readfile(tmp.prj)
          WHERE srs_id = <authority code>;
      rm tmp.prj

    But uses Python sqlite3 with no temp file and no sqlite3 CLI.
    """
    code = srs.GetAuthorityCode(None)
    if code is None:
        print("WARN: target SRS has no authority code; skip gpkg_spatial_ref_sys.definition_12_063 update.")
        return

    try:
        srs_id = int(code)
    except ValueError:
        print(f"WARN: authority code is not an integer ({code}); skip gpkg_spatial_ref_sys.definition_12_063 update.")
        return

    wkt2_2019 = export_wkt2_2019(srs)

    con = sqlite3.connect(gpkg_path)
    try:
        cur = con.cursor()

        cur.execute("PRAGMA table_info(gpkg_spatial_ref_sys);")
        cols = {row[1] for row in cur.fetchall()}
        if "definition_12_063" not in cols:
            cur.execute("ALTER TABLE gpkg_spatial_ref_sys ADD COLUMN definition_12_063 TEXT;")

        cur.execute("SELECT COUNT(1) FROM gpkg_spatial_ref_sys WHERE srs_id = ?;", (srs_id,))
        if cur.fetchone()[0] == 0:
            print(f"WARN: gpkg_spatial_ref_sys has no row with srs_id={srs_id}; skip definition_12_063 update.")
            con.commit()
            return

        cur.execute(
            "UPDATE gpkg_spatial_ref_sys SET definition_12_063 = ? WHERE srs_id = ?;",
            (wkt2_2019, srs_id),
        )
        con.commit()
    finally:
        con.close()


# ----------------------------
# Label helpers
# ----------------------------
_EPS = 1e-12


def _norm_zero(x: float) -> float:
    return 0.0 if abs(x) < _EPS else x


def _deg_text(x: float) -> str:
    """
    Convert a degree value to a compact string (no trailing zeros).
    Examples: 30 -> "30", 7.5 -> "7.5", -0 -> "0"
    """
    x = _norm_zero(float(x))
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


def lat_90_label(lat: float) -> str:
    return f"{_deg_text(lat)}°"


def lat_ns_label(lat: float) -> str:
    lat = _norm_zero(lat)
    if lat > 0:
        return f"{_deg_text(abs(lat))}°N"
    if lat < 0:
        return f"{_deg_text(abs(lat))}°S"
    return "0°"


def lon_180_label(lon: float) -> str:
    return f"{_deg_text(lon)}°"


def lon_ew_label(lon: float) -> str:
    """
    Return longitude labels in the range 180°W .. 180°E,
    regardless of whether input longitudes are given as
    -180..180 or 0..360.
    """
    # Normalize to (-180, 180]
    v = ((float(lon) + 180.0) % 360.0) - 180.0
    v = _norm_zero(v)

    # Prefer +180 over -180 for labeling
    if abs(v + 180.0) < _EPS:
        v = 180.0

    if v > 0:
        return f"{_deg_text(abs(v))}°E"
    if v < 0:
        return f"{_deg_text(abs(v))}°W"
    return "0°"

def lon_360_label(lon: float) -> str:
    v = (float(lon) % 360.0 + 360.0) % 360.0
    v = _norm_zero(v)
    return f"{_deg_text(v)}°"


def lon_360e_label(lon: float) -> str:
    v = (float(lon) % 360.0 + 360.0) % 360.0
    v = _norm_zero(v)
    return f"{_deg_text(v)}°E"


def _is_multiple(val: float, base: float, eps: float = 1e-9) -> bool:
    """
    True if val is (approximately) an integer multiple of base.
    Handles float steps robustly.
    """
    if base is None:
        return False
    base = float(base)
    if abs(base) < eps:
        return False
    k = float(val) / base
    return abs(k - round(k)) < eps


def _quiet_gdal_reprojection_domain_errors():
    def handler(err_class, err_num, msg):
        if "Point outside of projection domain" in msg:
            return
        if "Failed to reproject feature" in msg:
            return
        if "Reprojection failed" in msg:
            return
        if "Full reprojection failed" in msg:
            return

        sys.stderr.write(f"GDAL[{err_class}:{err_num}] {msg}\n")

    return handler

def _list_wkt_parameter_names(wkt: str):
    return re.findall(r'PARAMETER\["([^"]+)"', wkt)


def _replace_wkt_parameter_value(wkt: str, param_names, new_value: float):
    new_value_text = f"{float(new_value):.15g}"

    for param_name in param_names:
        pattern = re.compile(
            r'(PARAMETER\["' + re.escape(param_name) + r'",)([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',
            re.UNICODE,
        )
        if pattern.search(wkt):
            return pattern.sub(r'\1' + new_value_text, wkt, count=1), param_name

    return wkt, None


def _strip_root_authority_from_wkt(wkt: str) -> str:
    return re.sub(r',ID\[[^\]]+\](?=\s*\]\s*$)', '', wkt, count=1)


def _override_projection_latitude_parameters(srs, lat_orig=None, lat_sp=None, lat_sp2=None):
    if lat_orig is None and lat_sp is None and lat_sp2 is None:
        return srs, {}

    try:
        wkt = srs.ExportToWkt(["format=wkt2_2019"])
    except Exception:
        try:
            wkt = srs.ExportToWkt(["format=wkt2"])
        except Exception:
            wkt = srs.ExportToWkt()

    available = _list_wkt_parameter_names(wkt)
    applied = {}

    parameter_specs = [
        (
            "lat_orig",
            lat_orig,
            [
                ("Latitude of false origin", "latitude_of_origin"),
                ("Latitude of natural origin", "latitude_of_origin"),
                ("Latitude of origin", "latitude_of_origin"),
                ("Latitude of true origin", "latitude_of_origin"),
                ("Latitude of center", "latitude_of_center"),
                ("Latitude of projection centre", "latitude_of_center"),
                ("Latitude of projection center", "latitude_of_center"),
            ],
        ),
        (
            "lat_sp",
            lat_sp,
            [
                ("Latitude of 1st standard parallel", "standard_parallel_1"),
                ("Latitude of standard parallel", "standard_parallel_1"),
                ("Standard parallel 1", "standard_parallel_1"),
            ],
        ),
        (
            "lat_sp2",
            lat_sp2,
            [
                ("Latitude of 2nd standard parallel", "standard_parallel_2"),
                ("Standard parallel 2", "standard_parallel_2"),
            ],
        ),
    ]

    srs_new = srs.Clone()
    if hasattr(osr, "OAMS_TRADITIONAL_GIS_ORDER"):
        srs_new.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    for key, value, candidates in parameter_specs:
        if value is None:
            continue

        matched_wkt_name = None
        matched_proj_key = None
        for wkt_name, proj_key in candidates:
            if wkt_name in available:
                matched_wkt_name = wkt_name
                matched_proj_key = proj_key
                break

        if matched_wkt_name is None or matched_proj_key is None:
            raise RuntimeError(
                f"Requested --{key.replace('_', '-')} override, but the target CRS does not expose a compatible parameter. "
                f"Available WKT parameter names: {', '.join(available) if available else 'none'}"
            )

        srs_new.SetNormProjParm(matched_proj_key, float(value))
        applied[key] = matched_wkt_name

    return srs_new, applied


def _srs_id_label(srs: osr.SpatialReference) -> str:
    auth_name = srs.GetAuthorityName(None)
    auth_code = srs.GetAuthorityCode(None)
    if auth_name and auth_code:
        return f"{auth_name}:{auth_code}"

    try:
        name = srs.GetName()
    except Exception:
        name = None

    return name or "custom CRS"

def _get_projection_center_lat_lon(srs: osr.SpatialReference):
    """
    Return (center_lat, center_lon) from common projection parameters, if available.
    """
    lat_keys = [
        "latitude_of_false_origin",
        "latitude_of_origin",
        "latitude_of_center",
        "latitude_of_natural_origin",
    ]
    lon_keys = [
        "longitude_of_false_origin",
        "central_meridian",
        "longitude_of_center",
        "longitude_of_origin",
        "longitude_of_natural_origin",
    ]

    center_lat = None
    center_lon = None

    for key in lat_keys:
        try:
            center_lat = float(srs.GetProjParm(key))
            break
        except Exception:
            pass

    for key in lon_keys:
        try:
            center_lon = float(srs.GetProjParm(key))
            break
        except Exception:
            pass

    return center_lat, center_lon

def _transform_point_safe(ct, x, y):
    """
    Safely transform a single point. Returns (X, Y) in target CRS or None.
    Rejects NaN/Inf coordinates.
    """
    try:
        out = ct.TransformPoint(float(x), float(y))
        X = float(out[0])
        Y = float(out[1])
        if not (np.isfinite(X) and np.isfinite(Y)):
            return None
        return X, Y
    except Exception:
        return None


def _collapsed_target_point(sample_coords, ct, tol=1e-8, min_ok_points=1):
    """
    Check whether a sampled source line collapses to a single point in the target CRS.

    Returns
    -------
    (is_collapsed, target_point)
        is_collapsed : bool
        target_point : (X, Y) in target CRS, or None
    """
    pts = []
    for x, y in sample_coords:
        xy = _transform_point_safe(ct, x, y)
        if xy is not None:
            pts.append(xy)

    if len(pts) < min_ok_points:
        return False, None

    if len(pts) == 1:
        return True, pts[0]

    x0, y0 = pts[0]
    max_dist = 0.0
    for x, y in pts[1:]:
        d = ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5
        if d > max_dist:
            max_dist = d

    if max_dist <= tol:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        X = sum(xs) / len(xs)
        Y = sum(ys) / len(ys)
        if np.isfinite(X) and np.isfinite(Y):
            return True, (X, Y)

    return False, None

def _ensure_point_layer(ds_mem, point_layer, point_layer_name, srs_target):
    """
    Lazily create a companion point layer in the TARGET CRS.
    """
    if point_layer is not None:
        return point_layer

    point_layer = ds_mem.CreateLayer(point_layer_name, geom_type=ogr.wkbPoint, srs=srs_target)
    if point_layer is None:
        raise RuntimeError("Failed to create in-memory point layer.")

    field_defn = ogr.FieldDefn("row_no", ogr.OFTInteger)
    point_layer.CreateField(field_defn)

    field_lat = ogr.FieldDefn("lat", ogr.OFTReal)
    field_lat.SetWidth(10)
    field_lat.SetPrecision(3)
    point_layer.CreateField(field_lat)

    field_lon = ogr.FieldDefn("lon", ogr.OFTReal)
    field_lon.SetWidth(10)
    field_lon.SetPrecision(3)
    point_layer.CreateField(field_lon)
    
    point_layer.CreateField(ogr.FieldDefn("lat_90", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("lat_ns", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("lon_180", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("lon_ew", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("lon_360", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("lon_360e", ogr.OFTString))
    point_layer.CreateField(ogr.FieldDefn("point_role", ogr.OFTString))
    
    return point_layer

def _add_projection_center_point(
    point_layer,
    row,
    center_lat,
    center_lon,
    center_target_xy,
):
    """
    Add a projection-center label point to the companion point layer.
    The point geometry is already in target CRS.
    """
    feat = ogr.Feature(point_layer.GetLayerDefn())

    feat.SetField("row_no", int(row))

    if center_lat is None:
        feat.SetFieldNull("lat")
        feat.SetFieldNull("lat_90")
        feat.SetFieldNull("lat_ns")
    else:
        feat.SetField("lat", float(center_lat))
        feat.SetField("lat_90", lat_90_label(center_lat))
        feat.SetField("lat_ns", lat_ns_label(center_lat))

    if center_lon is None:
        feat.SetFieldNull("lon")
        feat.SetFieldNull("lon_180")
        feat.SetFieldNull("lon_ew")
        feat.SetFieldNull("lon_360")
        feat.SetFieldNull("lon_360e")
    else:
        feat.SetField("lon", float(center_lon))
        feat.SetField("lon_180", lon_180_label(center_lon))
        feat.SetField("lon_ew", lon_ew_label(center_lon))
        feat.SetField("lon_360", lon_360_label(center_lon))
        feat.SetField("lon_360e", lon_360e_label(center_lon))

    feat.SetField("point_role", "center")

    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint(float(center_target_xy[0]), float(center_target_xy[1]))
    pt.FlattenTo2D()
    feat.SetGeometry(pt)

    point_layer.CreateFeature(feat)
    feat = None

def main():
    args = get_args()

    terminal_width = 80
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        pass

    #########################################################################
    # Output format (force GPKG)
    outfile = args.outfile
    if os.path.splitext(outfile)[-1].lower() != ".gpkg":
        outfile += ".gpkg"

    outdir = os.path.dirname(outfile)
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    drv_out = ogr.GetDriverByName("GPKG")
    if drv_out is None:
        raise RuntimeError("OGR driver 'GPKG' is not available in this GDAL build.")

    if os.path.exists(outfile):
        try:
            drv_out.DeleteDataSource(outfile)
        except Exception:
            pass
        if os.path.exists(outfile):
            raise RuntimeError(
                f"Cannot overwrite '{outfile}'. It may be open in QGIS.\n"
                "Close QGIS (or remove the layer) and retry."
            )

    print("=" * terminal_width)

    #########################################################################
    # Spatial reference
    t_srs = args.srs
    t_srs_i = osr.SpatialReference()
    t_srs_i.SetFromUserInput(t_srs)

    # Force traditional GIS axis order (x=lon, y=lat) for manual transformations
    if hasattr(osr, "OAMS_TRADITIONAL_GIS_ORDER"):
        t_srs_i.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    overrides_requested = any(v is not None for v in (args.lat_orig, args.lat_sp, args.lat_sp2))
    applied_overrides = {}
    if overrides_requested:
        if t_srs_i.IsGeographic() == 1:
            raise RuntimeError("--lat-orig/--lat-sp/--lat-sp2 require a projected target CRS.")
        t_srs_i, applied_overrides = _override_projection_latitude_parameters(
            t_srs_i,
            lat_orig=args.lat_orig,
            lat_sp=args.lat_sp,
            lat_sp2=args.lat_sp2,
        )

    if t_srs_i.IsGeographic() == 1:
        projected = False
        proj_type = None
    else:
        projected = True
        proj_type = t_srs_i.GetAttrValue("PROJECTION")
        if proj_type is None:
            proj_type = "Unknown projection"

    # Geographic base CRS used to generate the graticule
    t_srs_geog = t_srs_i.CloneGeogCS()
    if hasattr(osr, "OAMS_TRADITIONAL_GIS_ORDER"):
        t_srs_geog.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    center_lat, center_lon = (None, None)
    if projected:
        center_lat, center_lon = _get_projection_center_lat_lon(t_srs_i)
        if center_lon is None:
            center_lon = 0.0

    #########################################################################
    # Grid / extent
    xstep, ystep = args.grid
    xres, yres = args.res
    ulx, uly, lrx, lry = args.extent

    if args.major is not None:
        xmajor, ymajor = args.major
    else:
        xmajor = ymajor = None

    xmin = min(ulx, lrx)
    xmax = max(ulx, lrx)
    ymin = min(lry, uly)
    ymax = max(lry, uly)

    # Near-global extent check
    global_like = (
        xmin <= -170 and xmax >= 170 and
        ymin <= -80 and ymax >= 80
    )

    # Projection types that are likely to have limited valid domains for near-global extents
    domain_limited_projections = {
        "Stereographic",
        "Polar_Stereographic",
        "Orthographic",
        "Gnomonic",
        "Vertical_Perspective",
        "Azimuthal_Equidistant",
    }
    projection_is_domain_limited = proj_type in domain_limited_projections if projected else False

    # Warn/abort only for domain-limited projected CRS + near-global extent
    if projected and global_like and projection_is_domain_limited:
        if not args.skipfailures:
            msg = (
                "Projected CRS with near-global extent detected.\n"
                "Some projection types (e.g., polar stereographic, orthographic) have limited valid domains, "
                "so global reprojection may fail.\n"
                "Restrict the geographic extent with -e (e.g., \"-e -180 -60 180 -90\").\n"
                "To force output, use -s/--skipfailures. "
                "Combining -s with -p/--partial-reprojection may allow partially valid geometries to be written."
            )
            print("\n" + msg + "\n", file=sys.stderr, flush=True)
            raise RuntimeError(msg)

        if args.skipfailures:
            print(
                "\nWARNING: Projected CRS with near-global extent.\n"
                "Some features may fall outside the projection domain and will be skipped "
                "because -s/--skipfailures is enabled.\n"
                "Consider restricting the extent with -e for a complete graticule in the target region "
                "(e.g., \"-e -180 -60 180 -90\").\n"
                "Alternatively, combining -s with -p/--partial-reprojection may allow partially valid geometries to be written.\n",
                file=sys.stderr,
            )

    # Latitudes / longitudes sequence
    latitudes = np.arange(ymin, ymax + 1e-12, ystep, dtype=float)
    longitudes = np.arange(xmin, xmax + 1e-12, xstep, dtype=float)

    # Optional: remove duplicate endpoint meridian for full 360-degree longitude spans
    if args.no_duplicate_endpoint:
        span = xmax - xmin
        spans_full_360 = abs(span - 360.0) < 1e-9

        if spans_full_360 and longitudes.size > 1:
            # Drop the last endpoint, keep the first.
            # Examples:
            #   -180..180 -> keep -180, drop 180
            #    0..360   -> keep 0,    drop 360
            if abs(longitudes[0] - xmin) < 1e-9 and abs(longitudes[-1] - xmax) < 1e-9:
                longitudes = longitudes[:-1]

    #########################################################################
    # Create Layer in memory
    if args.layer is not None:
        layer_name = args.layer
    else:
        layer_name = os.path.splitext(os.path.basename(outfile))[0]

    point_layer = None
    point_layer_name = f"{layer_name}_points"

    ct_to_target = None
    if projected:
        try:
            ct_to_target = osr.CoordinateTransformation(t_srs_geog, t_srs_i)
        except Exception:
            ct_to_target = None
    
    drv_mem = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
    if drv_mem is None:
        raise RuntimeError("OGR driver 'MEM' is not available in this GDAL build.")

    ds_mem = drv_mem.CreateDataSource("mem")
    if ds_mem is None:
        raise RuntimeError("Failed to create in-memory datasource.")

    layer = ds_mem.CreateLayer(layer_name, geom_type=ogr.wkbLineString, srs=t_srs_geog)
    if layer is None:
        raise RuntimeError("Failed to create in-memory layer.")

    # Print SRS (geographic base)
    print(export_pretty_wkt(t_srs_geog))

    print("=" * terminal_width)

    # Field definition
    field_defn = ogr.FieldDefn("row_no", ogr.OFTInteger)
    layer.CreateField(field_defn)

    field_lat = ogr.FieldDefn("lat", ogr.OFTReal)
    field_lat.SetWidth(10)
    field_lat.SetPrecision(3)
    layer.CreateField(field_lat)

    field_lon = ogr.FieldDefn("lon", ogr.OFTReal)
    field_lon.SetWidth(10)
    field_lon.SetPrecision(3)
    layer.CreateField(field_lon)

    layer.CreateField(ogr.FieldDefn("lat_90", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lat_ns", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_180", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_ew", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_360", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_360e", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("grid_type", ogr.OFTString))

    #########################################################################
    # Create features: latitude lines
    row = 1
    for i, lat in enumerate(latitudes):
        progress_bar(i, latitudes, "Processing Latitudes: ")

        lon_samples = np.arange(xmin, xmax + 1e-12, xres, dtype=float)
        sample_coords = [(float(lon), float(lat)) for lon in lon_samples]

        is_collapsed = False
        collapsed_target_xy = None

        # First, try the generic geometric collapse test
        if projected and ct_to_target is not None:
            is_collapsed, collapsed_target_xy = _collapsed_target_point(sample_coords, ct_to_target)

        # Fallback for true polar singularities:
        # if the target projection center is at a pole and this latitude matches that pole,
        # force a point at the transformed pole location even if all sampled line points failed.
        if (
            not is_collapsed
            and projected
            and center_lat is not None
            and center_lon is not None
            and abs(abs(center_lat) - 90.0) < 1e-9
            and abs(float(lat) - float(center_lat)) < 1e-9
            and ct_to_target is not None
        ):
            pole_xy = _transform_point_safe(ct_to_target, center_lon, center_lat)
            if pole_xy is not None:
                is_collapsed = True
                collapsed_target_xy = pole_xy

        if is_collapsed and collapsed_target_xy is not None:
            point_layer = _ensure_point_layer(ds_mem, point_layer, point_layer_name, t_srs_i)

            pt = ogr.Geometry(ogr.wkbPoint)
            pt.AddPoint(float(collapsed_target_xy[0]), float(collapsed_target_xy[1]))

            feat = ogr.Feature(point_layer.GetLayerDefn())
            feat.SetField("row_no", int(row))
            feat.SetField("lat", float(lat))
            feat.SetFieldNull("lon")

            feat.SetField("lat_90", lat_90_label(lat))
            feat.SetField("lat_ns", lat_ns_label(lat))
            feat.SetFieldNull("lon_180")
            feat.SetFieldNull("lon_ew")
            feat.SetFieldNull("lon_360")
            feat.SetFieldNull("lon_360e")

            feat.SetField("point_role", "collapsed")
            
            pt.FlattenTo2D()
            feat.SetGeometry(pt)
            point_layer.CreateFeature(feat)
            
            feat = None
            row += 1
            continue

        line = ogr.Geometry(ogr.wkbLineString)
        for lon in lon_samples:
            line.AddPoint(float(lon), float(lat))

        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("row_no", int(row))
        feat.SetField("lat", float(lat))
        feat.SetFieldNull("lon")

        feat.SetField("lat_90", lat_90_label(lat))
        feat.SetField("lat_ns", lat_ns_label(lat))
        feat.SetFieldNull("lon_180")
        feat.SetFieldNull("lon_ew")
        feat.SetFieldNull("lon_360")
        feat.SetFieldNull("lon_360e")

        if ymajor is None:
            feat.SetFieldNull("grid_type")
        else:
            feat.SetField("grid_type", "major" if _is_multiple(lat, ymajor) else "minor")

        line.FlattenTo2D()
        feat.SetGeometry(line)
        layer.CreateFeature(feat)
        feat = None
        row += 1

    sys.stdout.write("\n")

    # Create features: longitude lines
    for i, lon in enumerate(longitudes):
        progress_bar(i, longitudes, "Processing Longitudes: ")

        lat_samples = np.arange(ymin, ymax + 1e-12, yres, dtype=float)
        sample_coords = [(float(lon), float(lat)) for lat in lat_samples]

        is_collapsed = False
        collapsed_target_xy = None
        if projected and ct_to_target is not None:
            is_collapsed, collapsed_target_xy = _collapsed_target_point(sample_coords, ct_to_target)

        if is_collapsed and collapsed_target_xy is not None:
            point_layer = _ensure_point_layer(ds_mem, point_layer, point_layer_name, t_srs_i)

            pt = ogr.Geometry(ogr.wkbPoint)
            pt.AddPoint(float(collapsed_target_xy[0]), float(collapsed_target_xy[1]))

            feat = ogr.Feature(point_layer.GetLayerDefn())
            feat.SetField("row_no", int(row))
            feat.SetFieldNull("lat")
            feat.SetField("lon", float(lon))

            feat.SetFieldNull("lat_90")
            feat.SetFieldNull("lat_ns")
            feat.SetField("lon_180", lon_180_label(lon))
            feat.SetField("lon_ew", lon_ew_label(lon))
            feat.SetField("lon_360", lon_360_label(lon))
            feat.SetField("lon_360e", lon_360e_label(lon))
            feat.SetField("point_role", "collapsed")

            pt.FlattenTo2D()
            feat.SetGeometry(pt)
            point_layer.CreateFeature(feat)
            feat = None
            row += 1
            continue

        line = ogr.Geometry(ogr.wkbLineString)
        for lat in lat_samples:
            line.AddPoint(float(lon), float(lat))

        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("row_no", int(row))
        feat.SetFieldNull("lat")
        feat.SetField("lon", float(lon))

        feat.SetFieldNull("lat_90")
        feat.SetFieldNull("lat_ns")
        feat.SetField("lon_180", lon_180_label(lon))
        feat.SetField("lon_ew", lon_ew_label(lon))
        feat.SetField("lon_360", lon_360_label(lon))
        feat.SetField("lon_360e", lon_360e_label(lon))

        if xmajor is None:
            feat.SetFieldNull("grid_type")
        else:
            feat.SetField("grid_type", "major" if _is_multiple(lon, xmajor) else "minor")

        line.FlattenTo2D()
        feat.SetGeometry(line)
        layer.CreateFeature(feat)
        feat = None
        row += 1

    sys.stdout.write("\n")

    # Add a projection-center label point (in target CRS) if available
    if projected and ct_to_target is not None and center_lat is not None and center_lon is not None:
        center_target_xy = _transform_point_safe(ct_to_target, center_lon, center_lat)

        if center_target_xy is not None:
            point_layer = _ensure_point_layer(ds_mem, point_layer, point_layer_name, t_srs_i)

            # Avoid duplicating the exact same point if a collapsed feature already exists there
            duplicate_center = False
            if point_layer.GetFeatureCount() > 0:
                for feat_existing in point_layer:
                    geom_existing = feat_existing.GetGeometryRef()
                    if geom_existing is None:
                        continue
                    x0, y0, _ = geom_existing.GetPoint()
                    if ((x0 - center_target_xy[0]) ** 2 + (y0 - center_target_xy[1]) ** 2) ** 0.5 <= 1e-8:
                        if feat_existing.GetField("point_role") == "center":
                            duplicate_center = True
                            break
                point_layer.ResetReading()

            if not duplicate_center:
                _add_projection_center_point(
                    point_layer=point_layer,
                    row=int(1),
                    center_lat=center_lat,
                    center_lon=center_lon,
                    center_target_xy=center_target_xy,
                )
                row += 1

    #########################################################################
    # Write GeoPackage
    print("=" * terminal_width)
    if projected:
        print(
            f"Reprojection (on export): "
            f"{_srs_id_label(t_srs_geog)} "
            f"=> {('custom CRS' if applied_overrides else _srs_id_label(t_srs_i))}\n"
        )
        if applied_overrides:
            override_parts = []
            if args.lat_orig is not None:
                override_parts.append(f"lat_orig={args.lat_orig}")
            if args.lat_sp is not None:
                override_parts.append(f"lat_sp={args.lat_sp}")
            if args.lat_sp2 is not None:
                override_parts.append(f"lat_sp2={args.lat_sp2}")
            print("Projection parameter overrides: " + ", ".join(override_parts) + "\n")
        print(export_pretty_wkt(t_srs_i))
    else:
        print(
            f"Export (no reprojection): "
            f"{_srs_id_label(t_srs_i)}\n"
        )

    vt_opts = gdal.VectorTranslateOptions(
        format="GPKG",
        layers=[layer_name],   # <- main line layer only
        layerName=layer_name,
        dstSRS=t_srs_i,
        srcSRS=t_srs_geog,
        datasetCreationOptions=[
            "ADD_GPKG_OGR_CONTENTS=NO",
        ],
        layerCreationOptions=[
            "SPATIAL_INDEX=YES",
        ],
        skipFailures=args.skipfailures,
    )

    prev_partial = None
    if args.partial_reprojection:
        prev_partial = gdal.GetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION")
        gdal.SetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION", "TRUE")
        print(
            "NOTE: Partial reprojection enabled (-p/--partial-reprojection). "
            "Geometries may be truncated or split near projection domain limits.",
            file=sys.stderr,
            flush=True,
        )

    if args.skipfailures:
        gdal.PushErrorHandler(_quiet_gdal_reprojection_domain_errors())

    try:
        gdal.VectorTranslate(outfile, ds_mem, options=vt_opts)
    finally:
        if args.skipfailures:
            gdal.PopErrorHandler()

        if args.partial_reprojection:
            if prev_partial is None:
                gdal.SetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION", None)
            else:
                gdal.SetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION", prev_partial)

    # Write companion point layer if present
    if point_layer is not None and point_layer.GetFeatureCount() > 0:
        vt_point_opts = gdal.VectorTranslateOptions(
            format="GPKG",
            accessMode="update",
            layers=[point_layer_name],   # <- point layer only
            layerName=point_layer_name,
            srcSRS=t_srs_i,
            dstSRS=t_srs_i,
            layerCreationOptions=[
                "SPATIAL_INDEX=YES",
            ],
            skipFailures=args.skipfailures,
        )

        if args.skipfailures:
            gdal.PushErrorHandler(_quiet_gdal_reprojection_domain_errors())

        try:
            gdal.VectorTranslate(outfile, ds_mem, options=vt_point_opts)
        finally:
            if args.skipfailures:
                gdal.PopErrorHandler()

    # Post-run note only for domain-limited projected + near-global runs
    if projected and global_like and projection_is_domain_limited:
        if args.skipfailures:
            print(
                "NOTE: Some graticule lines may be missing because they fell outside the projection domain.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "NOTE: Reprojection may fail for near-global extents in some projected CRS. "
                "Use -e to restrict the extent, or -s/--skipfailures.",
                file=sys.stderr,
                flush=True,
            )

    # Add WKT2_2019 into gpkg_spatial_ref_sys.definition_12_063
    if applied_overrides:
        print("WARN: CRS parameter overrides were applied; skip gpkg_spatial_ref_sys.definition_12_063 update.")
    else:
        update_gpkg_spatial_ref_sys_with_wkt2_2019(outfile, t_srs_i)

    print("=" * terminal_width)
    print(f"Output: {outfile}")
    print(f"Lat grids: {len(latitudes)}")
    print(f"Lon grids: {len(longitudes)}")
    print(f"Points: {point_layer.GetFeatureCount() if point_layer is not None else 0}")

    #########################################################################
    # Cleanup
    layer = None
    point_layer = None
    ds_mem = None


if __name__ == "__main__":
    main()

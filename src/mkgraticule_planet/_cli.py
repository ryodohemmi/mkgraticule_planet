#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mkgraticule_planet

Create planetary-scale graticules with multi-format labels for any
GDAL/PROJ-supported CRS — exported as GeoPackage, SpatiaLite, or fitted 3D PLY.

Repository: https://github.com/ryodohemmi/mkgraticule_planet
Citation:   Hemmi, R. (2026). mkgraticule_planet. Zenodo.
            https://doi.org/10.5281/zenodo.18864189

Requirements
------------
GDAL Python bindings (conda install gdal)

Example
-------
python mkgraticule_planet.py -g 10 10 -r 0.2 0.2 -srs IAU_2015:30100 -e -180 90 180 -90 out.gpkg
python mkgraticule_planet.py -g 10 10 -r 0.2 0.2 -srs IAU_2015:30100 -e -180 90 180 -90 out.sqlite
python mkgraticule_planet.py -g 10 10 -r 0.2 0.2 -srs IAU_2015:30100 -f spatialite out.db
python mkgraticule_planet.py -f ply -mesh shape.obj -g 10 10 -r 1 1 out.ply
"""

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Ryodo Hemmi
#
# This software is provided "as is", without warranty of any kind.

__version__ = "1.1.1"

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
import difflib
import sqlite3
import re
import time
import numpy as np

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter, argparse.MetavarTypeHelpFormatter):
    pass

def _parse_color(s):
    parts = s.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Color must be R,G,B, for example 255,255,255")

    try:
        values = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Color values must be integers") from exc

    if any(v < 0 or v > 255 for v in values):
        raise argparse.ArgumentTypeError("Color values must be in 0..255")

    return values

def _is_negative_number_token(s):
    if not s.startswith("-") or s in ("-", "--"):
        return False
    try:
        float(s)
    except ValueError:
        return False
    return True

def _reject_unknown_option_tokens(parser, argv):
    option_strings = set(parser._option_string_actions)
    visible_options = [
        option
        for option, action in parser._option_string_actions.items()
        if action.help is not argparse.SUPPRESS
    ]

    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--":
            break
        if not token.startswith("-") or token == "-" or _is_negative_number_token(token):
            i += 1
            continue

        option = token.split("=", 1)[0] if token.startswith("--") else token
        if option in option_strings:
            action = parser._option_string_actions[option]
            if action.nargs == 0 or token.startswith("--") and "=" in token:
                i += 1
                continue

            nargs = action.nargs if action.nargs is not None else 1
            if isinstance(nargs, int):
                i += 1 + nargs
            else:
                i += 1
            continue

        message = f"unrecognized option: {option}"
        suggestion = difflib.get_close_matches(option, visible_options, n=1, cutoff=0.72)
        if suggestion:
            message += f" (did you mean {suggestion[0]}?)"
        parser.error(message)

def get_args():
    parser = argparse.ArgumentParser(
        formatter_class=CustomFormatter,
        description="Create planetary-scale graticules with multi-format labels for any GDAL/PROJ-supported CRS.",
        epilog="Repository: https://github.com/ryodohemmi/mkgraticule_planet\n"
               "Citation:   Hemmi, R. (2026). mkgraticule_planet. Zenodo.\n"
               "            https://doi.org/10.5281/zenodo.18864189",
    )

    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument("outfile", type=str, help="Set the output filename")
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["gpkg", "spatialite", "ply"],
        default=None,
        help="Output format: 'gpkg' (GeoPackage), 'spatialite' (SpatiaLite SQLite),\n"
             "or 'ply' (3D graticule fitted to an input mesh).\n"
             "Auto-detected from outfile extension if omitted:\n"
             "  .gpkg -> gpkg, .sqlite -> spatialite, .ply -> ply.\n"
             "Defaults to gpkg if extension is ambiguous.",
    )
    ply_group = parser.add_argument_group("PLY fitted 3D graticule options")
    ply_group.add_argument(
        "--input-mesh",
        "-mesh",
        dest="input_mesh",
        type=str,
        default=None,
        help="[PLY only] Input OBJ/mesh shape model. Required when output format is ply.",
    )
    ply_group.add_argument(
        "--mesh",
        dest="input_mesh",
        type=str,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--ray-orig",
        "-rorig",
        dest="origin",
        type=float,
        nargs=3,
        default=(0.0, 0.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="[PLY only] Lat/lon origin in mesh coordinates for ray casting.",
    )
    ply_group.add_argument(
        "--origin",
        dest="origin",
        type=float,
        nargs=3,
        default=argparse.SUPPRESS,
        metavar=("X", "Y", "Z"),
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--ray-scale",
        "-rscale",
        dest="far_scale",
        type=float,
        default=3.0,
        help="[PLY only] Ray start distance as a multiple of the mesh radius.",
    )
    ply_group.add_argument(
        "--far-scale",
        dest="far_scale",
        type=float,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    offset_group = ply_group.add_mutually_exclusive_group()
    offset_group.add_argument(
        "--offset-distance",
        "-odist",
        type=float,
        default=argparse.SUPPRESS,
        help="[PLY only] Absolute outward offset applied to fitted vertices.",
    )
    offset_group.add_argument(
        "--offset-fraction",
        "-ofrac",
        type=float,
        default=argparse.SUPPRESS,
        help="[PLY only] Outward offset as a fraction of the mesh radius.",
    )
    offset_group.add_argument(
        "-ofract",
        dest="offset_fraction",
        type=float,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--ray-batch",
        "-rbatch",
        dest="batch_size",
        type=int,
        default=200000,
        help="[PLY only] Ray-casting batch size.",
    )
    ply_group.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--ray-slow",
        "-rslow",
        dest="allow_slow_raycast",
        action="store_true",
        default=False,
        help="[PLY only] Allow the default trimesh/rtree ray intersector when Embree is unavailable.",
    )
    ply_group.add_argument(
        "--allow-slow-raycast",
        dest="allow_slow_raycast",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--ply-rgb",
        "-prgb",
        dest="color",
        type=_parse_color,
        default=(255, 255, 255),
        help="[PLY only] Color as R,G,B.",
    )
    ply_group.add_argument(
        "--color",
        dest="color",
        type=_parse_color,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--tube-rad",
        "-trad",
        dest="tube_radius",
        type=float,
        default=0.0,
        help="[PLY only] If > 0, write tube mesh instead of edge primitives.",
    )
    ply_group.add_argument(
        "--tube-radius",
        dest="tube_radius",
        type=float,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    ply_group.add_argument(
        "--tube-seg",
        "-tseg",
        dest="tube_segments",
        type=int,
        default=8,
        help="[PLY only] Number of radial segments for tube cross-sections.",
    )
    ply_group.add_argument(
        "--tube-segments",
        dest="tube_segments",
        type=int,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

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
            \nIf not set, defaults to 'grid' (points layer: 'point').",
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

    parser.set_defaults(offset_distance=0.0, offset_fraction=0.0)

    _reject_unknown_option_tokens(parser, sys.argv[1:])
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
    if args.far_scale <= 0:
        parser.error(f"ray-scale must be > 0 (got {args.far_scale}).")
    if args.batch_size <= 0:
        parser.error(f"ray-batch must be > 0 (got {args.batch_size}).")
    if args.tube_radius < 0:
        parser.error(f"tube-rad must be >= 0 (got {args.tube_radius}).")
    if args.tube_segments < 3:
        parser.error(f"tube-seg must be >= 3 (got {args.tube_segments}).")

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

def _indent_wkt(wkt: str) -> str:
    """Add indentation to a single-line WKT2 string.

    Mimics the style produced by PROJ/sf: break after commas that
    precede a keyword (uppercase letter), keep scalar values on the
    same line.
    """
    import re
    out = []
    depth = 0
    i = 0
    n = len(wkt)
    while i < n:
        ch = wkt[i]
        if ch == '[':
            out.append('[')
            depth += 1
            i += 1
        elif ch == ']':
            depth -= 1
            out.append(']')
            i += 1
        elif ch == ',':
            out.append(',')
            i += 1
            # skip spaces
            while i < n and wkt[i] == ' ':
                i += 1
            # break line only if next token is a WKT keyword (uppercase letter)
            if i < n and wkt[i].isupper():
                out.append('\n')
                out.append('    ' * depth)
            else:
                # scalar value follows — keep on same line
                out.append('')
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def export_pretty_wkt(srs: osr.SpatialReference) -> str:
    """
    Return a human-readable WKT2:2019 string for console output.
    """
    wkt = export_wkt2_2019(srs)

    try:
        import pyproj
        return pyproj.CRS.from_wkt(wkt).to_wkt(pretty=True)
    except Exception:
        pass

    # Indent WKT2 without pyproj
    if wkt and ("GEOGCRS[" in wkt or "PROJCRS[" in wkt or "GEODCRS[" in wkt):
        return _indent_wkt(wkt)

    return wkt


_EXT_FORMAT_MAP = {
    ".gpkg": "gpkg",
    ".sqlite": "spatialite",
    ".sqlite3": "spatialite",
    ".spatialite": "spatialite",
    ".ply": "ply",
}

def _resolve_output_format(outfile, fmt_flag):
    """Return (fmt_key, ogr_driver, default_ext, ds_create_opts, is_gpkg)."""
    ext = os.path.splitext(outfile)[-1].lower()

    if fmt_flag is not None:
        fmt = fmt_flag.lower()
    elif ext in _EXT_FORMAT_MAP:
        fmt = _EXT_FORMAT_MAP[ext]
    else:
        fmt = "gpkg"

    if fmt == "spatialite":
        return ("spatialite", "SQLite", ".spatialite", ["SPATIALITE=YES"], False)
    if fmt == "ply":
        return ("ply", None, ".ply", [], False)
    return ("gpkg", "GPKG", ".gpkg", ["ADD_GPKG_OGR_CONTENTS=NO"], True)


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
    if v == 0:
        return "0°"
    return f"{_deg_text(v)}°E"


def lon_360w_label(lon: float) -> str:
    v = ((-float(lon)) % 360.0 + 360.0) % 360.0
    v = _norm_zero(v)
    if v == 0:
        return "0°"
    return f"{_deg_text(v)}°W"


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

    _SENTINEL = float('inf')
    center_lat = None
    center_lon = None

    for key in lat_keys:
        val = srs.GetProjParm(key, _SENTINEL)
        if val != _SENTINEL:
            center_lat = float(val)
            break

    for key in lon_keys:
        val = srs.GetProjParm(key, _SENTINEL)
        if val != _SENTINEL:
            center_lon = float(val)
            break

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

def _sph_to_cart_batch(lat_deg, lon_deg):
    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)

    x = np.cos(lat) * np.cos(lon)
    y = np.cos(lat) * np.sin(lon)
    z = np.sin(lat)

    v = np.column_stack([x, y, z]).astype(np.float64)
    n = np.linalg.norm(v, axis=1)
    return v / n[:, None]


def _load_mesh(path):
    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError("PLY output requires the 'trimesh' Python package.") from exc

    mesh = trimesh.load(path, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError("Input mesh could not be loaded as a single Trimesh.")
    mesh.remove_unreferenced_vertices()
    mesh.process(validate=False)
    return mesh


def _get_mesh_intersector(mesh):
    try:
        from trimesh.ray.ray_pyembree import RayMeshIntersector
        print("[INFO] Using Embree ray intersector: trimesh.ray.ray_pyembree")
        return RayMeshIntersector(mesh), "embree"
    except Exception as exc:
        print("[WARN] Embree intersector is not available.")
        print(f"[WARN] Embree import failed: {exc}")
        try:
            import rtree  # noqa: F401
        except ImportError as rtree_exc:
            raise RuntimeError(
                "Embree is unavailable and the default trimesh ray intersector requires 'rtree'. "
                "For PLY shape-model jobs, install the Embree fast path with 'pip install embreex' "
                "or, on Linux/WSL/macOS conda environments, 'conda install -c conda-forge pyembree'. "
                "Use 'conda install -c conda-forge rtree' only for small fallback jobs."
            ) from rtree_exc
        print("[WARN] Falling back to trimesh default ray intersector. This can be slow and memory-heavy.")
        return mesh.ray, "default"


def _estimate_radius_from_origin(mesh, origin):
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    r = np.linalg.norm(vertices - origin[None, :], axis=1)
    return float(np.max(r))


def _raycast_surface_points(
    intersector,
    directions,
    origin_xyz,
    far_distance,
    offset_distance=0.0,
    batch_size=200000,
):
    n = len(directions)
    points = np.full((n, 3), np.nan, dtype=np.float64)
    hit_mask = np.zeros(n, dtype=bool)

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)

        d = directions[start:end]
        ray_origins = origin_xyz[None, :] + d * far_distance
        ray_dirs = -d

        locations, index_ray, index_tri = intersector.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_dirs,
            multiple_hits=False,
        )

        if len(locations) == 0:
            continue

        global_indices = start + index_ray

        if offset_distance != 0.0:
            locations = locations + directions[global_indices] * offset_distance

        points[global_indices] = locations
        hit_mask[global_indices] = True

    return points, hit_mask


def _make_ply_latitude_specs(grid_step, sample_step, lat_min, lat_max, lon_min, lon_max):
    lat_values = np.arange(lat_min, lat_max + 1e-12, grid_step, dtype=float)
    full_lon_span = abs((lon_max - lon_min) - 360.0) < 1e-9
    if full_lon_span:
        lon_values = np.arange(lon_min, lon_max, sample_step, dtype=float)
    else:
        lon_values = np.arange(lon_min, lon_max + 1e-12, sample_step, dtype=float)

    specs = []
    for lat in lat_values:
        specs.append({
            "kind": "lat",
            "value": float(lat),
            "lat": np.full_like(lon_values, lat, dtype=np.float64),
            "lon": lon_values.copy(),
            "wrap": full_lon_span,
        })

    return specs


def _make_ply_longitude_specs(grid_step, sample_step, lon_min, lon_max, lat_min, lat_max, drop_duplicate_endpoint):
    lon_values = np.arange(lon_min, lon_max + 1e-12, grid_step, dtype=float)
    if drop_duplicate_endpoint and abs((lon_max - lon_min) - 360.0) < 1e-9 and lon_values.size > 1:
        if abs(lon_values[0] - lon_min) < 1e-9 and abs(lon_values[-1] - lon_max) < 1e-9:
            lon_values = lon_values[:-1]

    lat_values = np.arange(lat_min, lat_max + 1e-12, sample_step, dtype=float)

    specs = []
    for lon in lon_values:
        specs.append({
            "kind": "lon",
            "value": float(lon),
            "lat": lat_values.copy(),
            "lon": np.full_like(lat_values, lon, dtype=np.float64),
            "wrap": False,
        })

    return specs


def _build_all_ply_rays(line_specs):
    all_lat = []
    all_lon = []
    ranges = []

    cursor = 0
    for spec in line_specs:
        lat = spec["lat"]
        lon = spec["lon"]
        n = len(lat)

        if n == 0:
            continue

        all_lat.append(lat)
        all_lon.append(lon)
        ranges.append((cursor, cursor + n))
        cursor += n

    if not all_lat:
        return np.empty((0, 3), dtype=np.float64), ranges

    all_lat = np.concatenate(all_lat)
    all_lon = np.concatenate(all_lon)
    directions = _sph_to_cart_batch(all_lat, all_lon)

    return directions, ranges


def _build_ply_polyline_indices(hit_mask, ranges, line_specs):
    polylines = []

    for (start, end), spec in zip(ranges, line_specs):
        indices = np.arange(start, end)
        valid = hit_mask[indices]

        current = []
        for idx, ok in zip(indices, valid):
            if ok:
                current.append(int(idx))
            else:
                if len(current) >= 2:
                    polylines.append(current)
                current = []

        if len(current) >= 2:
            if spec["wrap"] and bool(np.all(valid)):
                current = current + [current[0]]
            polylines.append(current)

    return polylines


def _build_ply_vertices_and_edges(points, hit_mask, ranges, line_specs):
    valid_global = np.where(hit_mask)[0]
    vertices = points[valid_global]

    vertex_index = np.full(len(points), -1, dtype=np.int64)
    vertex_index[valid_global] = np.arange(len(valid_global), dtype=np.int64)

    edges = []
    polylines_global = _build_ply_polyline_indices(hit_mask, ranges, line_specs)

    for line in polylines_global:
        for a, b in zip(line[:-1], line[1:]):
            edges.append((int(vertex_index[a]), int(vertex_index[b])))

    return vertices, edges, polylines_global


def _make_tube_mesh_from_polylines(points, polylines_global, radius, segments=8):
    tube_vertices = []
    tube_faces = []

    def normalize(v):
        n = np.linalg.norm(v)
        if n == 0:
            return v
        return v / n

    for line in polylines_global:
        pts = points[np.asarray(line, dtype=np.int64)]

        valid = np.all(np.isfinite(pts), axis=1)
        pts = pts[valid]
        if len(pts) < 2:
            continue

        closed = np.linalg.norm(pts[0] - pts[-1]) < radius * 1e-3
        if closed:
            pts_work = pts[:-1]
        else:
            pts_work = pts

        if len(pts_work) < 2:
            continue

        n_pts = len(pts_work)

        tangents = np.zeros_like(pts_work)
        for i in range(n_pts):
            if i == 0:
                tangents[i] = normalize(pts_work[1] - pts_work[0])
            elif i == n_pts - 1:
                tangents[i] = normalize(pts_work[-1] - pts_work[-2])
            else:
                tangents[i] = normalize(pts_work[i + 1] - pts_work[i - 1])

        t0 = tangents[0]
        ref = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(t0, ref)) > 0.9:
            ref = np.array([0.0, 1.0, 0.0])

        n0 = normalize(np.cross(t0, ref))
        b0 = normalize(np.cross(t0, n0))

        normals = np.zeros_like(pts_work)
        binormals = np.zeros_like(pts_work)
        normals[0] = n0
        binormals[0] = b0

        for i in range(1, n_pts):
            t = tangents[i]

            nvec = normals[i - 1] - np.dot(normals[i - 1], t) * t
            if np.linalg.norm(nvec) < 1e-12:
                ref = np.array([0.0, 0.0, 1.0])
                if abs(np.dot(t, ref)) > 0.9:
                    ref = np.array([0.0, 1.0, 0.0])
                nvec = np.cross(t, ref)

            nvec = normalize(nvec)
            bvec = normalize(np.cross(t, nvec))

            normals[i] = nvec
            binormals[i] = bvec

        start_index = len(tube_vertices)
        angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)

        for i in range(n_pts):
            center = pts_work[i]
            nvec = normals[i]
            bvec = binormals[i]

            for a in angles:
                p = center + radius * (np.cos(a) * nvec + np.sin(a) * bvec)
                tube_vertices.append(p)

        ring_count = n_pts
        if closed:
            segment_pairs = [(i, (i + 1) % ring_count) for i in range(ring_count)]
        else:
            segment_pairs = [(i, i + 1) for i in range(ring_count - 1)]

        for i, j in segment_pairs:
            for k in range(segments):
                k2 = (k + 1) % segments

                a = start_index + i * segments + k
                b = start_index + i * segments + k2
                c = start_index + j * segments + k2
                d = start_index + j * segments + k

                tube_faces.append((a, b, c))
                tube_faces.append((a, c, d))

        if not closed:
            c0 = len(tube_vertices)
            tube_vertices.append(pts_work[0])
            c1 = len(tube_vertices)
            tube_vertices.append(pts_work[-1])

            for k in range(segments):
                k2 = (k + 1) % segments

                a = start_index + k
                b = start_index + k2
                tube_faces.append((c0, b, a))

                a2 = start_index + (ring_count - 1) * segments + k
                b2 = start_index + (ring_count - 1) * segments + k2
                tube_faces.append((c1, a2, b2))

    return np.asarray(tube_vertices, dtype=np.float64), np.asarray(tube_faces, dtype=np.int64)


def _write_ply_edges(path, vertices, edges, color):
    r, g, b = color

    with open(path, "w", encoding="utf-8") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write("comment fitted latitude-longitude grid generated by ray intersection\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write(f"element edge {len(edges)}\n")
        f.write("property int vertex1\n")
        f.write("property int vertex2\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")

        for v in vertices:
            f.write(f"{v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n")

        for i, j in edges:
            f.write(f"{i} {j} {r} {g} {b}\n")


def _write_ply_mesh(path, vertices, faces, color):
    r, g, b = color

    with open(path, "w", encoding="utf-8") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write("comment fitted latitude-longitude tube mesh generated by ray intersection\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write(f"element face {len(faces)}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")

        for v in vertices:
            f.write(f"{v[0]:.9f} {v[1]:.9f} {v[2]:.9f} {r} {g} {b}\n")

        for a, b_, c in faces:
            f.write(f"3 {a} {b_} {c}\n")


def _guard_slow_ply_raycast(engine_name, args, mesh, sample_count):
    if engine_name == "embree" or args.allow_slow_raycast:
        return

    ray_face_product = int(sample_count) * int(len(mesh.faces))
    max_default_ray_face_product = 50_000_000
    if ray_face_product <= max_default_ray_face_product:
        return

    raise RuntimeError(
        "Embree is unavailable and this PLY job is too large for the default trimesh/rtree ray intersector.\n"
        f"Samples: {sample_count}, mesh faces: {len(mesh.faces)}, samples*faces: {ray_face_product:,}.\n"
        "The fallback can allocate very large candidate arrays on irregular shape models.\n"
        "Install Embree acceleration with 'pip install embreex' or, on Linux/WSL/macOS conda environments, "
        "'conda install -c conda-forge pyembree'.\n"
        "Alternatively reduce sampling density with -r, or pass --ray-slow to force the fallback."
    )


def _write_fitted_latlon_ply(args, outfile):
    if args.input_mesh is None:
        raise RuntimeError("PLY output requires --input-mesh/-mesh.")

    t0 = time.perf_counter()

    xstep, ystep = args.grid
    xres, yres = args.res
    ulx, uly, lrx, lry = args.extent

    lon_min = min(ulx, lrx)
    lon_max = max(ulx, lrx)
    lat_min = min(lry, uly)
    lat_max = max(lry, uly)

    print(f"[INFO] Loading mesh: {args.input_mesh}")
    mesh = _load_mesh(args.input_mesh)

    print(f"[INFO] Mesh vertices: {len(mesh.vertices)}")
    print(f"[INFO] Mesh faces:    {len(mesh.faces)}")

    origin = np.asarray(args.origin, dtype=np.float64)
    max_radius = _estimate_radius_from_origin(mesh, origin)
    far_distance = max_radius * args.far_scale
    offset_distance = args.offset_distance + max_radius * args.offset_fraction

    print(f"[INFO] Lat/lon origin:     {origin}")
    print(f"[INFO] Max radius:         {max_radius:.9g}")
    print(f"[INFO] Ray far distance:   {far_distance:.9g}")
    print(f"[INFO] Offset distance:    {offset_distance:.9g}")

    t1 = time.perf_counter()
    intersector, engine_name = _get_mesh_intersector(mesh)
    t2 = time.perf_counter()

    lat_specs = _make_ply_latitude_specs(
        grid_step=ystep,
        sample_step=xres,
        lat_min=lat_min,
        lat_max=lat_max,
        lon_min=lon_min,
        lon_max=lon_max,
    )
    lon_specs = _make_ply_longitude_specs(
        grid_step=xstep,
        sample_step=yres,
        lon_min=lon_min,
        lon_max=lon_max,
        lat_min=lat_min,
        lat_max=lat_max,
        drop_duplicate_endpoint=args.no_duplicate_endpoint,
    )

    line_specs = lat_specs + lon_specs
    directions, ranges = _build_all_ply_rays(line_specs)
    if len(directions) == 0:
        raise RuntimeError("No PLY ray samples were generated.")

    print(f"[INFO] Latitude lines:  {len(lat_specs)}")
    print(f"[INFO] Longitude lines: {len(lon_specs)}")
    print(f"[INFO] Total samples:   {len(directions)}")
    _guard_slow_ply_raycast(engine_name, args, mesh, len(directions))

    t3 = time.perf_counter()
    points, hit_mask = _raycast_surface_points(
        intersector=intersector,
        directions=directions,
        origin_xyz=origin,
        far_distance=far_distance,
        offset_distance=offset_distance,
        batch_size=args.batch_size,
    )

    n_hit = int(np.count_nonzero(hit_mask))
    n_miss = int(len(hit_mask) - n_hit)

    print(f"[INFO] Ray hits:   {n_hit}")
    print(f"[INFO] Ray misses: {n_miss}")

    t4 = time.perf_counter()
    vertices, edges, polylines_global = _build_ply_vertices_and_edges(
        points=points,
        hit_mask=hit_mask,
        ranges=ranges,
        line_specs=line_specs,
    )

    print(f"[INFO] Polyline vertices: {len(vertices)}")
    print(f"[INFO] Polyline edges:    {len(edges)}")
    print(f"[INFO] Polyline parts:    {len(polylines_global)}")

    if args.tube_radius > 0.0:
        print(f"[INFO] Building tube mesh: radius={args.tube_radius}, segments={args.tube_segments}")
        tube_vertices, tube_faces = _make_tube_mesh_from_polylines(
            points=points,
            polylines_global=polylines_global,
            radius=args.tube_radius,
            segments=args.tube_segments,
        )

        print(f"[INFO] Tube vertices: {len(tube_vertices)}")
        print(f"[INFO] Tube faces:    {len(tube_faces)}")
        _write_ply_mesh(outfile, tube_vertices, tube_faces, args.color)
    else:
        _write_ply_edges(outfile, vertices, edges, args.color)

    t5 = time.perf_counter()

    print(f"[DONE] Wrote: {outfile}")
    print("[TIME] load mesh:        %.3f s" % (t1 - t0))
    print("[TIME] build intersector %.3f s  (%s)" % (t2 - t1, engine_name))
    print("[TIME] build rays:       %.3f s" % (t3 - t2))
    print("[TIME] raycast:          %.3f s" % (t4 - t3))
    print("[TIME] build/write out:  %.3f s" % (t5 - t4))
    print("[TIME] total:            %.3f s" % (t5 - t0))

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
    point_layer.CreateField(ogr.FieldDefn("lon_360w", ogr.OFTString))
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
        feat.SetFieldNull("lon_360w")
    else:
        feat.SetField("lon", float(center_lon))
        feat.SetField("lon_180", lon_180_label(center_lon))
        feat.SetField("lon_ew", lon_ew_label(center_lon))
        feat.SetField("lon_360", lon_360_label(center_lon))
        feat.SetField("lon_360e", lon_360e_label(center_lon))
        feat.SetField("lon_360w", lon_360w_label(center_lon))

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
    # Output format
    outfile = args.outfile
    fmt_key, ogr_driver_name, default_ext, ds_create_opts, is_gpkg = _resolve_output_format(outfile, args.format)

    ext = os.path.splitext(outfile)[-1].lower()
    if ext not in _EXT_FORMAT_MAP:
        outfile += default_ext

    outdir = os.path.dirname(outfile)
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    if fmt_key == "ply":
        _write_fitted_latlon_ply(args, outfile)
        return

    drv_out = ogr.GetDriverByName(ogr_driver_name)
    if drv_out is None:
        raise RuntimeError(f"OGR driver '{ogr_driver_name}' is not available in this GDAL build.")

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
        point_layer_name = f"{layer_name}_point"
    else:
        layer_name = "grid"
        point_layer_name = "point"

    point_layer = None

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
    layer.CreateField(ogr.FieldDefn("lon_360w", ogr.OFTString))
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
            feat.SetFieldNull("lon_360w")

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
        feat.SetFieldNull("lon_360w")

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
            feat.SetField("lon_360w", lon_360w_label(lon))
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
        feat.SetField("lon_360w", lon_360w_label(lon))

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
                is_pole = center_lat is not None and abs(abs(center_lat) - 90) <= 1e-9
                _add_projection_center_point(
                    point_layer=point_layer,
                    row=int(1),
                    center_lat=center_lat,
                    center_lon=None if is_pole else center_lon,
                    center_target_xy=center_target_xy,
                )
                row += 1

    #########################################################################
    # Write output
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
        format=ogr_driver_name,
        layers=[layer_name],   # <- main line layer only
        layerName=layer_name,
        dstSRS=t_srs_i,
        srcSRS=t_srs_geog,
        datasetCreationOptions=ds_create_opts,
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
            format=ogr_driver_name,
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

    # Add WKT2_2019 into gpkg_spatial_ref_sys.definition_12_063 (GPKG only)
    if is_gpkg:
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

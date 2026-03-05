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

__version__ = "0.2.0"

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
import numpy as np


def get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

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
        help="Major graticule interval [xmajor ymajor] in degrees. "
             "If set, grid_type will be 'major' or 'minor'. If omitted, grid_type is NULL.",
    )
    parser.add_argument(
        "-srs",
        "--srs",
        type=str,
        default="IAU_2015:30100",
        help="Set target spatial reference (IAU code or *.prj file). See https://spatialreference.org/",
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
        "-lo",
        "--lato",
        type=float,
        metavar="lato",
        default=None,
        help="Force to override the latitude of origin (center) of the projection specified by -srs",
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
    help="Enable partial reprojection (OGR_ENABLE_PARTIAL_REPROJECTION=TRUE). "
         "May output truncated/split geometries near projection domain limits.",
    )

    parser.add_argument(
    "-ndd",
    "--no-duplicate-dateline",
    action="store_true",
    help="Drop the duplicate dateline meridian when the longitude span is ~360 degrees "
         "(e.g., remove -180 and keep 180). Useful for polar stereographic views.",
    )

    args = parser.parse_args()
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
    # Prefer WKT2:2019; fall back for older GDAL/PROJ builds.
    try:
        return srs.ExportToWkt(["format=wkt2_2019"])
    except Exception:
        try:
            return srs.ExportToWkt(["format=wkt2"])
        except Exception:
            return srs.ExportToWkt()


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

        # Column existence check
        cur.execute("PRAGMA table_info(gpkg_spatial_ref_sys);")
        cols = {row[1] for row in cur.fetchall()}  # row[1] = column name
        if "definition_12_063" not in cols:
            cur.execute("ALTER TABLE gpkg_spatial_ref_sys ADD COLUMN definition_12_063 TEXT;")

        # Confirm row existence (VectorTranslate usually inserts it, but be defensive)
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


def lat_180_label(lat: float) -> str:
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
    lon = _norm_zero(lon)
    if lon > 0:
        return f"{_deg_text(abs(lon))}°E"
    if lon < 0:
        return f"{_deg_text(abs(lon))}°W"
    return "0°"


def lon_360_label(lon: float) -> str:
    # Normalize to [0, 360)
    v = (float(lon) % 360.0 + 360.0) % 360.0
    v = _norm_zero(v)
    return f"{_deg_text(v)}°"


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
        # Suppress noisy reprojection-domain errors when skipFailures is enabled.
        # Still allow other messages through.

        if "Point outside of projection domain" in msg:
            return
        if "Failed to reproject feature" in msg:
            return
        if "Reprojection failed" in msg:
            return
        if "Full reprojection failed" in msg:   # ← これ追加
            return

        # Fall back: print others
        sys.stderr.write(f"GDAL[{err_class}:{err_num}] {msg}\n")

    return handler

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

    if t_srs_i.IsGeographic() == 1:
        projected = False
    else:
        projected = True
        proj_type = t_srs_i.GetAttrValue("PROJECTION")
        if proj_type is None:
            proj_type = "Unknown projection"

    # NOTE: original script creates features in geographic CRS, then reprojects if needed.
    # Keep that behavior: build in geographic for grid logic.
    t_srs_geog = t_srs_i.CloneGeogCS()

    if args.lato is not None and projected:
        # Override latitude of origin for certain IAU planet projections (user-requested behavior).
        # This keeps the rest of the SRS unchanged.
        try:
            t_srs_i.SetProjParm("latitude_of_origin", float(args.lato))
        except Exception as e:
            print(f"WARN: failed to override latitude_of_origin with -lo {args.lato}: {e}")

    #########################################################################
    # Grid / extent
    xstep, ystep = args.grid
    xres, yres = args.res
    ulx, uly, lrx, lry = args.extent

    # major interval (optional)
    if args.major is not None:
        xmajor, ymajor = args.major
    else:
        xmajor = ymajor = None

    # Normalize extent (in case user swaps)
    xmin = min(ulx, lrx)
    xmax = max(ulx, lrx)
    ymin = min(lry, uly)
    ymax = max(lry, uly)

    # Warn if projected CRS + near-global extent
    # Warn/abort if projected CRS + near-global extent
    if projected:
        global_like = (
            xmin <= -170 and xmax >= 170 and
            ymin <= -80 and ymax >= 80
        )
        
        if global_like and not args.skipfailures:
            msg = (
                "Projected CRS with near-global extent detected.\n"
                "Some projections (e.g., polar stereographic) have limited valid domains, "
                "so global reprojection may fail.\n"
                "Restrict the geographic extent with -e (e.g., \"-e -180 -60 180 -90\").\n"
                "To force output, use -s/--skipfailures. "
                "Combining -s with -p/--partial-reprojection may allow partially valid geometries to be written."
            )
            print("\n" + msg + "\n", file=sys.stderr, flush=True)
            raise RuntimeError(msg)
        
        if global_like and args.skipfailures:
            print(
                "\nWARNING: Projected CRS with near-global extent.\n"
                "Some features may fall outside the projection domain and will be skipped "
                "because -s/--skipfailures is enabled.\n"
                "Consider restricting the extent with -e for a complete graticule in the target region (e.g., \"-e -180 -60 180 -90\").\n"
                "Alternatively, combining -s with -p/--partial-reprojection may allow partially valid geometries to be written.\n",
                file=sys.stderr,
            )
    
    # Latitudes / longitudes sequence
    latitudes = np.arange(ymin, ymax + 1e-12, ystep, dtype=float)
    longitudes = np.arange(xmin, xmax + 1e-12, xstep, dtype=float)

    # Optional: remove duplicate dateline (-180 and 180) for near-global extents
    if args.no_duplicate_dateline:
        span = xmax - xmin
        spans_full_360 = abs(span - 360.0) < 1e-9
        has_both_ends = (abs(xmin + 180.0) < 1e-9) and (abs(xmax - 180.0) < 1e-9)

        if spans_full_360 and has_both_ends and longitudes.size > 1:
            # Prefer keeping +180 and dropping -180
            if abs(longitudes[0] + 180.0) < 1e-9:
                longitudes = longitudes[1:]

    #########################################################################
    # Create Layer in memory (avoid temp Shapefile)
    layer_name = os.path.splitext(os.path.basename(outfile))[0]

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
    wkt_string = t_srs_geog.ExportToWkt(["format=wkt2"])
    try:
        import pyproj

        pretty_wkt = pyproj.CRS.from_wkt(wkt_string).to_wkt(pretty=True)
        print(pretty_wkt)
    except ImportError:
        print(wkt_string)

    print("=" * terminal_width)

    # Field definition
    field_defn = ogr.FieldDefn("fid", ogr.OFTInteger)
    layer.CreateField(field_defn)

    field_lat = ogr.FieldDefn("lat", ogr.OFTReal)
    field_lat.SetWidth(10)
    field_lat.SetPrecision(3)
    layer.CreateField(field_lat)

    field_lon = ogr.FieldDefn("lon", ogr.OFTReal)
    field_lon.SetWidth(10)
    field_lon.SetPrecision(3)
    layer.CreateField(field_lon)

    # Label fields (TEXT) - always created by default
    # lat: -90..90 style, and N/S style
    layer.CreateField(ogr.FieldDefn("lat_180", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lat_ns", ogr.OFTString))
    # lon: -180..180 style, E/W style, and 0..360 style
    layer.CreateField(ogr.FieldDefn("lon_180", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_ew", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("lon_360", ogr.OFTString))

    # Major/minor (NULL if --major is not used)
    layer.CreateField(ogr.FieldDefn("grid_type", ogr.OFTString))

    #########################################################################
    # Create features: latitude lines
    fid = 0
    for i, lat in enumerate(latitudes):
        progress_bar(i, latitudes, "Processing Latitudes: ")
        line = ogr.Geometry(ogr.wkbLineString)
        for lon in np.arange(xmin, xmax + 1e-12, xres, dtype=float):
            line.AddPoint(float(lon), float(lat))

        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("fid", int(fid))
        feat.SetField("lat", float(lat))
        feat.SetFieldNull("lon")

        # label fields
        feat.SetField("lat_180", lat_180_label(lat))
        feat.SetField("lat_ns", lat_ns_label(lat))
        feat.SetFieldNull("lon_180")
        feat.SetFieldNull("lon_ew")
        feat.SetFieldNull("lon_360")

        # grid_type
        if ymajor is None:
            feat.SetFieldNull("grid_type")
        else:
            feat.SetField("grid_type", "major" if _is_multiple(lat, ymajor) else "minor")

        line.FlattenTo2D()
        feat.SetGeometry(line)
        layer.CreateFeature(feat)
        feat = None
        fid += 1

    sys.stdout.write("\n")

    # Create features: longitude lines
    for i, lon in enumerate(longitudes):
        progress_bar(i, longitudes, "Processing Longitudes: ")
        line = ogr.Geometry(ogr.wkbLineString)
        for lat in np.arange(ymin, ymax + 1e-12, yres, dtype=float):
            line.AddPoint(float(lon), float(lat))

        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("fid", int(fid))
        feat.SetFieldNull("lat")
        feat.SetField("lon", float(lon))

        # label fields
        feat.SetFieldNull("lat_180")
        feat.SetFieldNull("lat_ns")
        feat.SetField("lon_180", lon_180_label(lon))
        feat.SetField("lon_ew", lon_ew_label(lon))
        feat.SetField("lon_360", lon_360_label(lon))

        # grid_type
        if xmajor is None:
            feat.SetFieldNull("grid_type")
        else:
            feat.SetField("grid_type", "major" if _is_multiple(lon, xmajor) else "minor")

        line.FlattenTo2D()
        feat.SetGeometry(line)
        layer.CreateFeature(feat)
        feat = None
        fid += 1

    sys.stdout.write("\n")

    #########################################################################
    # Write GeoPackage (reproject on export if needed)
    print("=" * terminal_width)
    if projected:
        print(
            f"Reprojection (on export): "
            f"{t_srs_geog.GetAuthorityName(None)}:{t_srs_geog.GetAuthorityCode(None)} "
            f"=> {t_srs_i.GetAuthorityName(None)}:{t_srs_i.GetAuthorityCode(None)}\n"
        )
        wkt_string2 = t_srs_i.ExportToWkt(["format=wkt2"])
        try:
            import pyproj

            pretty_wkt2 = pyproj.CRS.from_wkt(wkt_string2).to_wkt(pretty=True)
            print(pretty_wkt2)
        except ImportError:
            print(wkt_string2)
    else:
        print(
            f"Export (no reprojection): "
            f"{t_srs_i.GetAuthorityName(None)}:{t_srs_i.GetAuthorityCode(None)}\n"
        )

    vt_opts = gdal.VectorTranslateOptions(
        format="GPKG",
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

    # Optional: enable partial reprojection (scoped)
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

    # Optional: suppress noisy domain errors when skipfailures is enabled
    if args.skipfailures:
        gdal.PushErrorHandler(_quiet_gdal_reprojection_domain_errors())

    try:
        gdal.VectorTranslate(outfile, ds_mem, options=vt_opts)
    finally:
        if args.skipfailures:
            gdal.PopErrorHandler()

        # Restore partial reprojection config to previous state
        if args.partial_reprojection:
            if prev_partial is None:
                gdal.SetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION", None)
            else:
                gdal.SetConfigOption("OGR_ENABLE_PARTIAL_REPROJECTION", prev_partial)

    # Post-run note for projected + global-like runs
    if projected and global_like:
        if args.skipfailures:
            print(
                "NOTE: Some graticule lines may be missing because they fell outside the projection domain.",
                file=sys.stderr,
                flush=True,
            )
        else:
            # In your current design, this path should normally be blocked earlier (abort),
            # but keep it harmless if logic changes in the future.
            print(
                "NOTE: Reprojection may fail for near-global extents in some projected CRS. "
                "Use -e to restrict the extent, or -s/--skipfailures.",
                file=sys.stderr,
                flush=True,
            )
    
    # Add WKT2_2019 into gpkg_spatial_ref_sys.definition_12_063 for srs_id (= authority code)
    # IMPORTANT: the CRS input must match -srs, so use t_srs_i here.
    update_gpkg_spatial_ref_sys_with_wkt2_2019(outfile, t_srs_i)

    #########################################################################
    # Cleanup
    layer = None
    ds_mem = None


if __name__ == "__main__":
    main()
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

__version__ = "0.1.0"

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

    # Normalize extent (in case user swaps)
    xmin = min(ulx, lrx)
    xmax = max(ulx, lrx)
    ymin = min(lry, uly)
    ymax = max(lry, uly)

    # Latitudes / longitudes sequence
    latitudes = np.arange(ymin, ymax + 1e-12, ystep, dtype=float)
    longitudes = np.arange(xmin, xmax + 1e-12, xstep, dtype=float)

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

    gdal.VectorTranslate(
        outfile,
        ds_mem,
        format="GPKG",
        layerName=layer_name,
        dstSRS=t_srs_i,  # target CRS (matches -srs)
        srcSRS=t_srs_geog,  # source CRS (geographic base)
        layerCreationOptions=[
            "SPATIAL_INDEX=YES",
        ],
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
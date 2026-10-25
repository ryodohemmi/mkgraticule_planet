"""Integration tests shared by the package, standalone Python and R CLIs."""
from contextlib import closing
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from osgeo import ogr, osr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mkgraticule_planet import _cli

R_COMMAND = json.loads(os.environ["MKGRATICULE_R_COMMAND"]) if os.environ.get("MKGRATICULE_R_COMMAND") else ([shutil.which("Rscript")] if shutil.which("Rscript") else None)
PLY_AVAILABLE = bool(importlib.util.find_spec("trimesh") and importlib.util.find_spec("rtree"))
if os.environ.get("MKGRATICULE_REQUIRE_PLY") == "1" and not PLY_AVAILABLE:
    raise RuntimeError("CI requires trimesh and rtree; PLY tests must not be skipped.")


class SharedCLI:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mkgraticule-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def run_cli(self, *options, success=True):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        result = subprocess.run(self.command + list(map(str, options)), cwd=ROOT,
                                env=env, text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def grid(self, output, *extra, success=True):
        return self.run_cli("-g", 5, 5, "-r", 1, 1, "-e", 0, 10, 10, 0,
                            "-srs", "IAU_2015:30100", *extra, output, success=success)

    def assert_counts(self, output, log, meters=False):
        ds = ogr.Open(str(output))
        self.assertIsNotNone(ds)
        layer = ds.GetLayerByName("grid")
        self.assertIsNotNone(layer)
        count = layer.GetFeatureCount()
        empty = 0
        fields = ("y", "x") if meters else ("lat", "lon")
        directions = dict.fromkeys(fields, 0)
        for feature in layer:
            geometry = feature.GetGeometryRef()
            empty += int(geometry is None or geometry.IsEmpty())
            for field in fields:
                directions[field] += int(feature.GetField(field) is not None)
        points = ds.GetLayerByName("point")
        point_count = points.GetFeatureCount() if points is not None else 0
        self.assertIn(f"Saved line features: {count} (empty: {empty})", log)
        self.assertIn(f"Saved point features: {point_count}", log)
        labels = ("Northing (y)", "Easting (x)") if meters else ("latitude", "longitude")
        for field, label in zip(fields, labels):
            self.assertIn(f"Saved {label} lines: {directions[field]}", log)
        return count, point_count

    def test_geopackage_and_metadata_opt_in(self):
        output = self.work / "grid.gpkg"
        log = self.grid(output, "-m", 10, 10)
        self.assertEqual(self.assert_counts(output, log), (6, 0))
        with closing(sqlite3.connect(output)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master WHERE name='mkgraticule_metadata'").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT DISTINCT grid_type FROM grid ORDER BY grid_type").fetchall(), [("major",), ("minor",)])
            self.assertTrue(con.execute("SELECT lat_ns FROM grid WHERE lat=10").fetchone()[0])
        log = self.grid(output, "--metadata")
        self.assertEqual(self.assert_counts(output, log), (6, 0))
        with closing(sqlite3.connect(output)) as con:
            record = dict(con.execute("SELECT key, value FROM mkgraticule_metadata"))
            self.assertEqual(record["version"], "1.3.1")
            self.assertIn("Moon", record["crs_wkt"])
            self.assertEqual(record["format"], "gpkg")
            self.assertEqual(record["layer"], "grid")
            self.assertEqual(record["grid"], "5 5")
            self.assertEqual(record["res"], "1 1")
            self.assertEqual(record["extent"], "0 10 10 0")
            self.assertEqual(record["major"], "")
            self.assertEqual(record["no_duplicate_endpoint"], "false")
            self.assertTrue({"input_mesh", "origin", "far_scale", "batch_size", "tube_radius", "tube_segments", "color", "dry_run", "yes", "qview"}.isdisjoint(record))
            for key in ("grid", "res", "extent", "command", "created_utc"):
                self.assertTrue(record[key])
        self.assertFalse(list(self.work.glob(".mkgraticule-*")))

    def test_shared_default_settings(self):
        for units, options, extent, grid, resolution, srs in (
            ("degrees", (), (0, 1, 1, 0), "5 5", "0.1 0.1", "IAU_2015:30100"),
            ("meters", ("-u", "meters", "-srs", "IAU_2015:30135"),
             (0, 1000, 1000, 0), "5000 5000", "100 100", "IAU_2015:30135"),
        ):
            with self.subTest(units=units):
                output = self.work / units
                log = self.run_cli("--metadata", "-e", *extent, *options, output)
                saved = output.with_suffix(".gpkg")
                self.assertEqual(self.assert_counts(saved, log, meters=units == "meters"), (2, 0))
                with closing(sqlite3.connect(saved)) as con:
                    record = dict(con.execute("SELECT key, value FROM mkgraticule_metadata"))
                for key, expected in {"grid": grid, "res": resolution, "srs": srs,
                                      "units": units, "format": "gpkg", "layer": "grid",
                                      "major": "", "override_lat_orig": "", "override_lat_sp": "",
                                      "override_lat_sp2": "", "no_duplicate_endpoint": "false"}.items():
                    self.assertEqual(record[key], expected, key)
                ds = ogr.Open(str(saved))
                for feature in ds.GetLayerByName("grid"):
                    self.assertEqual(feature.GetGeometryRef().GetPointCount(), 11)
                ds = None

    def test_reprojection_controls(self):
        output = self.work / "projected.gpkg"
        output.write_bytes(b"original")
        options = ("-srs", "IAU_2015:30165", "-g", 60, 40, "-r", 10, 10,
                   "-e", -180, 80, 180, -80)
        self.run_cli(*options, output, success=False)
        self.assertEqual(output.read_bytes(), b"original")
        nonempty_counts = []
        for flags in (("-s",), ("-s", "-p")):
            log = self.run_cli(*options, *flags, "--metadata", output)
            self.assert_counts(output, log)
            ds = ogr.Open(str(output))
            nonempty = sum(feature.GetGeometryRef() is not None and not feature.GetGeometryRef().IsEmpty()
                           for feature in ds.GetLayerByName("grid"))
            nonempty_counts.append(nonempty)
            self.assertGreater(nonempty, 0)
            self.assertLess(nonempty, 12)
            ds = None
            with closing(sqlite3.connect(output)) as con:
                record = dict(con.execute("SELECT key, value FROM mkgraticule_metadata"))
            self.assertEqual(record["skipfailures"], "true")
            self.assertEqual(record["partial_reprojection"], "true" if "-p" in flags else "false")
        self.assertGreater(nonempty_counts[1], nonempty_counts[0])

    def test_metadata_effective_projection_parameters(self):
        output = self.work / "grid.gpkg"
        crs = "IAU_2015:30175"
        reference = osr.SpatialReference()
        reference.SetFromUserInput(crs)
        defaults = tuple(reference.GetNormProjParm(key) for key in ("latitude_of_origin", "standard_parallel_1", "standard_parallel_2"))
        for overrides, expected in (((), defaults), (("-lo", 5, "-ls", 25, "-ls2", 55), (5, 25, 55))):
            self.grid(output, "--metadata", "-srs", crs, *overrides)
            with closing(sqlite3.connect(output)) as con:
                record = dict(con.execute("SELECT key, value FROM mkgraticule_metadata"))
            for name, value in zip(("latitudeoffalseorigin", "latitudeof1ststandardparallel", "latitudeof2ndstandardparallel"), expected):
                self.assertEqual(float(record["crs_parameter_" + name]), value)
            self.assertEqual(record["override_lat_orig"], "5" if overrides else "")

    def test_size_confirmation_does_not_create_directory(self):
        output = self.work / "nested" / "grid.gpkg"
        self.grid(output, "-r", 0.01, 0.01, success=False)
        self.assertFalse(output.parent.exists())

    def test_spatialite(self):
        output = self.work / "grid.sqlite"
        log = self.grid(output, "--metadata")
        self.assertEqual(self.assert_counts(output, log), (6, 0))
        with closing(sqlite3.connect(output)) as con:
            self.assertEqual(con.execute("SELECT value FROM mkgraticule_metadata WHERE key='version'").fetchone()[0], "1.3.1")

    def test_format_override_default_extension(self):
        for name in ("grid", "grid.db"):
            output = self.work / name
            log = self.grid(output, "-f", "spatialite")
            saved = Path(str(output) + ".spatialite")
            self.assertFalse(output.exists())
            self.assertEqual(self.assert_counts(saved, log), (6, 0))

    def test_invalid_crs_preserves_existing_output(self):
        output = self.work / "grid.gpkg"
        self.grid(output)
        before = output.read_bytes()
        self.grid(output, "-srs", "INVALID:999999", success=False)
        self.assertEqual(output.read_bytes(), before)
        self.assertFalse(list(self.work.glob(".mkgraticule-*")))

    def test_dry_run_does_not_write_or_prompt(self):
        output = self.work / "nested" / "grid.gpkg"
        log = self.grid(output, "--dry-run", "--metadata", "-q", "-r", 0.01, 0.01)
        self.assertIn("Estimated lines:", log)
        self.assertIn("No files were written.", log)
        self.assertFalse(output.parent.exists())
        output = self.work / "grid.gpkg"
        output.write_bytes(b"keep this file")
        log = self.grid(output, "--dry-run")
        self.assertIn("Existing output would be replaced.", log)
        self.assertEqual(output.read_bytes(), b"keep this file")
        self.grid(output, "--dry-run", "-srs", "INVALID:999999", success=False)
        self.assertEqual(output.read_bytes(), b"keep this file")

    def test_endpoint_deduplication(self):
        output = self.work / "grid.gpkg"
        log = self.grid(output, "-e", -180, 10, 180, 0, "-g", 90, 5,
                        "-r", 10, 1, "-nde")
        self.assertEqual(self.assert_counts(output, log), (7, 0))
        # A step that does not reach xmax has no duplicate endpoint to remove.
        log = self.grid(output, "--dry-run", "-e", -180, 10, 180, 0, "-g", 100, 5,
                        "-r", 10, 1, "-nde")
        self.assertIn("Estimated lines: 7", log)
        log = self.grid(output, "-e", -180, 10, 180, 0, "-g", 100, 5,
                        "-r", 10, 1, "-nde")
        self.assertEqual(self.assert_counts(output, log), (7, 0))

    def test_polar_output_counts(self):
        output = self.work / "grid.gpkg"
        log = self.grid(output, "-srs", "IAU_2015:30135", "-e", -180, -80, 180, -90,
                        "-g", 90, 5, "-r", 10, 1, "-nde")
        lines, points = self.assert_counts(output, log)
        self.assertGreater(lines, 0)
        self.assertGreater(points, 0)
        self.assertIn("Saved latitude lines: 2", log)

    def test_meter_grid_and_empty_extent_preserves_output(self):
        output = self.work / "grid.gpkg"
        log = self.run_cli("-u", "meters", "-srs", "IAU_2015:30135", "-e", -100, 100, 100, -100,
                           "-g", 100, 100, "-r", 50, 50, "--metadata", output)
        self.assertEqual(self.assert_counts(output, log, meters=True), (6, 0))
        before = output.read_bytes()
        self.run_cli("-u", "meters", "-srs", "IAU_2015:30135", "-e", 1, 2, 2, 1,
                     "-g", 100, 100, output, success=False)
        self.assertEqual(output.read_bytes(), before)
        self.run_cli("--dry-run", "-u", "meters", "-srs", "IAU_2015:30135", "-e", 1, 2, 2, 1,
                     "-g", 100, 100, output, success=False)

    def test_sqlite_journal_blocks_replacement(self):
        output = self.work / "grid.gpkg"
        self.grid(output)
        before = output.read_bytes()
        journal = Path(str(output) + "-journal")
        journal.write_bytes(b"occupied")
        self.grid(output, success=False)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(journal.read_bytes(), b"occupied")


class PythonPackage(SharedCLI, unittest.TestCase):
    command = [sys.executable, "-m", "mkgraticule_planet"]


class PythonStandalone(SharedCLI, unittest.TestCase):
    command = [sys.executable, str(ROOT / "standalone/mkgraticule_planet.py")]


@unittest.skipUnless(R_COMMAND, "Rscript not found; set MKGRATICULE_R_COMMAND to enable R integration tests")
class RStandalone(SharedCLI, unittest.TestCase):
    command = (R_COMMAND or []) + [str(ROOT / "standalone/mkgraticule_planet.R")]

    def test_without_terminal_information(self):
        output = self.work / "grid.gpkg"
        with patch.dict(os.environ, {"TERM": "", "COLUMNS": ""}):
            log = self.grid(output)
        self.assertEqual(self.assert_counts(output, log), (6, 0))

    def test_write_and_replacement_failure_preserve_output(self):
        output = self.work / "grid.gpkg"
        for setup, message in (
            ('st_write <- function(obj, dsn, ...) { writeLines("partial", dsn); stop("simulated write failure") }',
             "Error in st_write"),
            ('file.rename <- function(from, to) FALSE', "existing output is unchanged. Close applications using it"),
        ):
            output.write_bytes(b"original")
            expression = setup + '; source("standalone/mkgraticule_planet.R")'
            with patch.object(self, "command", R_COMMAND + ["-e", expression]):
                log = self.grid(output, success=False)
            self.assertIn(message, log)
            self.assertEqual(output.read_bytes(), b"original")
            self.assertFalse(list(self.work.glob(".mkgraticule-*")))


class PythonSafety(unittest.TestCase):
    setUp = SharedCLI.setUp
    run_cli = SharedCLI.run_cli
    assert_counts = SharedCLI.assert_counts
    command = PythonPackage.command

    def test_declined_confirmation_does_not_create_directory(self):
        output = self.work / "nested" / "grid.gpkg"
        with patch.object(sys, "argv", ["mkgraticule", "-r", "0.01", "0.01", str(output)]), \
             patch.object(sys.stdin, "isatty", return_value=True), \
             patch.object(_cli, "_ask_yes_no", return_value=False):
            with self.assertRaises(SystemExit) as error:
                _cli.main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(output.parent.exists())

    def test_skipped_reprojection_counts(self):
        output = self.work / "grid.gpkg"
        for flags in (("-s",), ("-s", "-p")):
            log = self.run_cli("-srs", "+proj=ortho +lat_0=0 +lon_0=0 +R=1737400 +units=m +no_defs",
                               "-g", 60, 40, "-r", 10, 10, "-e", -180, 80, 180, -80, *flags, output)
            self.assert_counts(output, log)
            ds = ogr.Open(str(output))
            nonempty = sum(feature.GetGeometryRef() is not None and not feature.GetGeometryRef().IsEmpty()
                           for feature in ds.GetLayerByName("grid"))
            self.assertLess(nonempty, 12)
            ds = None

    def test_standalone_is_identical(self):
        self.assertEqual((ROOT / "src/mkgraticule_planet/_cli.py").read_bytes(),
                         (ROOT / "standalone/mkgraticule_planet.py").read_bytes())

    def test_failure_after_partial_write_preserves_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "grid.gpkg"
            output.write_bytes(b"original")
            def fail(args, staged):
                Path(staged).write_bytes(b"incomplete")
                raise RuntimeError("simulated write failure")
            with patch.object(sys, "argv", ["mkgraticule", str(output)]), patch.object(_cli, "_run", side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, "simulated write failure"):
                    _cli.main()
            self.assertEqual(output.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_replacement_failure_preserves_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "grid.gpkg"
            output.write_bytes(b"original")
            def generate(args, staged):
                Path(staged).write_bytes(b"complete")
            with patch.object(sys, "argv", ["mkgraticule", str(output)]), \
                 patch.object(_cli, "_run", side_effect=generate), \
                 patch.object(_cli, "_inspect_output", return_value=({}, "WKT")), \
                 patch.object(os, "replace", side_effect=PermissionError("locked")):
                with self.assertRaisesRegex(RuntimeError, "existing output is unchanged.*Close applications using it"):
                    _cli.main()
            self.assertEqual(output.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).iterdir()), [output])


class PLYTests:
    setUp = SharedCLI.setUp
    run_cli = SharedCLI.run_cli

    def make_mesh(self):
        mesh = self.work / "octahedron.obj"
        mesh.write_text("v 1 0 0\nv -1 0 0\nv 0 1 0\nv 0 -1 0\nv 0 0 1\nv 0 0 -1\n"
                        "f 1 3 5\nf 3 2 5\nf 2 4 5\nf 4 1 5\n"
                        "f 3 1 6\nf 2 3 6\nf 4 2 6\nf 1 4 6\n")
        return mesh

    def test_ply_output_and_metadata(self):
        mesh = self.make_mesh()
        output = self.work / "grid.ply"
        for tube in (False, True):
            extra = ["-trad", "0.01"] if tube else []
            self.run_cli("-mesh", mesh, "-g", 90, 45, "-r", 30, 20, "-e", -180, 80, 180, -80,
                         "--metadata", *extra, output)
            header, body = output.read_text().split("end_header\n", 1)
            self.assertIn("comment mkgraticule version=\"1.3.1\"", header)
            self.assertIn('comment mkgraticule grid="90 45"', header)
            for key in ("srs", "crs_wkt", "major", "layer", "qview", "yes", "dry_run"):
                self.assertNotIn(f"comment mkgraticule {key}=", header)
            elements = [int(line.split()[2]) for line in header.splitlines() if line.startswith("element ")]
            self.assertTrue(all(count > 0 for count in elements))
            self.assertEqual(sum(elements), len(body.splitlines()))

    def test_ply_dry_run_and_failure_preserve_output(self):
        mesh = self.work / "bad.obj"
        mesh.write_text("not a mesh")
        output = self.work / "grid.ply"
        output.write_bytes(b"original")
        log = self.run_cli("--dry-run", "-mesh", mesh, output)
        self.assertIn("ray casting are not performed", log)
        self.assertEqual(output.read_bytes(), b"original")
        self.run_cli("-mesh", mesh, output, success=False)
        self.assertEqual(output.read_bytes(), b"original")

    def test_ply_surface_offsets_and_batches(self):
        mesh = self.make_mesh()
        output = self.work / "grid.ply"
        for options, offset in (((), 0), (("-odist", "0.1"), 0.1), (("-ofrac", "0.1"), 0.1)):
            self.run_cli("-mesh", mesh, "-g", 90, 45, "-r", 30, 20, "-e", -180, 80, 180, -80,
                         "-rbatch", 7, *options, output)
            header, body = output.read_text().split("end_header\n", 1)
            count = int(next(line.split()[2] for line in header.splitlines() if line.startswith("element vertex ")))
            for row in body.splitlines()[:count]:
                point = [float(value) for value in row.split()[:3]]
                radius = sum(value * value for value in point) ** 0.5
                original = [value * (radius - offset) / radius for value in point]
                self.assertAlmostEqual(sum(abs(value) for value in original), 1, places=5)
            self.assertNotIn("comment mkgraticule", header)

    def test_ply_option_validation_and_no_writes(self):
        mesh = self.make_mesh()
        output = self.work / "grid.ply"
        output.write_bytes(b"original")
        for flags in (("-odist", 0, "-ofrac", 0), ("-tseg", 2), ("-rbatch", 0),
                      ("-prgb", "256,0,0"), ("-rscale", 0), ("-trad", -1), ("-u", "meters")):
            self.run_cli("--dry-run", "-mesh", mesh, *flags, output, success=False)
            self.assertEqual(output.read_bytes(), b"original")

    def test_ply_shifted_origin_and_default_extension(self):
        mesh = self.make_mesh()
        origin = (1.2, -0.4, 0.7)
        lines = []
        for line in mesh.read_text().splitlines():
            if line.startswith("v "):
                point = [float(value) + shift for value, shift in zip(line.split()[1:], origin)]
                line = "v " + " ".join(map(str, point))
            lines.append(line)
        mesh.write_text("\n".join(lines) + "\n")
        output = self.work / "grid"
        self.run_cli("--format", "ply", "--input-mesh", mesh, "--ray-orig", *origin,
                     "-g", 90, 45, "-r", 30, 20, "-e", -180, 80, 180, -80, output)
        saved = Path(str(output) + ".ply")
        self.assertFalse(output.exists())
        header, body = saved.read_text().split("end_header\n", 1)
        count = int(next(line.split()[2] for line in header.splitlines() if line.startswith("element vertex ")))
        for row in body.splitlines()[:count]:
            point = [float(value) - shift for value, shift in zip(row.split()[:3], origin)]
            self.assertAlmostEqual(sum(abs(value) for value in point), 1, places=5)

    def test_ply_closed_lines_endpoint_and_tube_topology(self):
        mesh = self.make_mesh()
        output = self.work / "grid.ply"
        for tube in (False, True):
            for nde in (False, True):
                with self.subTest(tube=tube, nde=nde):
                    flags = (["-trad", "0.01"] if tube else []) + (["-nde"] if nde else [])
                    self.run_cli("-mesh", mesh, "-g", 90, 22, "-r", 37, 11, "-e", 17, 57, 377, 13,
                                 "-prgb", "40,50,60", *flags, output)
                    header, body = output.read_text().split("end_header\n", 1)
                    n = int(next(line.split()[2] for line in header.splitlines() if line.startswith("element vertex ")))
                    rows = [row.split() for row in body.splitlines()]
                    vertices = [tuple(map(float, row[:3])) for row in rows[:n]]
                    self.assertTrue(all(math.isfinite(value) for vertex in vertices for value in vertex))
                    self.assertEqual(n, (408 if nde else 450) if tube else (50 if nde else 55))
                    elements = []
                    for row in rows[n:]:
                        ids = tuple(map(int, row[1:4] if tube else row[:2]))
                        self.assertTrue(all(0 <= index < n for index in ids))
                        self.assertEqual(len(set(ids)), len(ids))
                        elements.append(ids)
                        if not tube:
                            self.assertEqual(list(map(int, row[2:])), [40, 50, 60])
                    if tube:
                        edge_use = {}
                        for a, b, c in elements:
                            for edge in ((a, b), (b, c), (c, a)):
                                key = tuple(sorted(edge))
                                edge_use[key] = edge_use.get(key, 0) + 1
                        self.assertTrue(all(count == 2 for count in edge_use.values()), "Tube surfaces must be closed, including end caps")
                        self.assertTrue(all(list(map(int, row[3:])) == [40, 50, 60] for row in rows[:n]))
                    else:
                        self.assertIn((9, 0), elements, "Full-360 latitude lines must close")


@unittest.skipUnless(PLY_AVAILABLE, "PLY dependencies not installed")
class PythonPLY(PLYTests, unittest.TestCase):
    command = PythonPackage.command


@unittest.skipUnless(R_COMMAND, "Rscript not found")
class RPLY(PLYTests, unittest.TestCase):
    command = (R_COMMAND or []) + [str(ROOT / "standalone/mkgraticule_planet.R")]

    @classmethod
    def setUpClass(cls):
        result = subprocess.run(R_COMMAND + ["-e", "quit(status=if (requireNamespace('Rvcg', quietly=TRUE)) 0 else 1)"],
                                capture_output=True, timeout=60)
        if result.returncode:
            if os.environ.get("MKGRATICULE_REQUIRE_PLY") == "1":
                raise RuntimeError("CI requires Rvcg; R PLY tests must not be skipped.")
            raise unittest.SkipTest("Rvcg is not installed")


if __name__ == "__main__":
    unittest.main()

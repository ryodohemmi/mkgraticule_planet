import importlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_osgeo_modules():
    fake_osr = types.ModuleType("osr")
    fake_ogr = types.ModuleType("ogr")
    fake_gdal = types.ModuleType("gdal")

    class SpatialReference:
        pass

    fake_osr.SpatialReference = SpatialReference
    fake_osr.UseExceptions = lambda: None
    fake_ogr.UseExceptions = lambda: None
    fake_gdal.UseExceptions = lambda: None

    fake_osgeo = types.ModuleType("osgeo")
    fake_osgeo.osr = fake_osr
    fake_osgeo.ogr = fake_ogr
    fake_osgeo.gdal = fake_gdal

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.arange = lambda *args, **kwargs: []

    return {
        "osgeo": fake_osgeo,
        "osgeo.osr": fake_osr,
        "osgeo.ogr": fake_ogr,
        "osgeo.gdal": fake_gdal,
        "numpy": fake_numpy,
    }


class TestCliValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_modules = _install_fake_osgeo_modules()
        cls.module_patcher = mock.patch.dict(sys.modules, cls.fake_modules)
        cls.module_patcher.start()
        cls.mgp = importlib.import_module("mkgraticule_planet")

    @classmethod
    def tearDownClass(cls):
        cls.module_patcher.stop()
        sys.modules.pop("mkgraticule_planet", None)

    def _parse(self, *argv):
        with mock.patch.object(sys, "argv", ["mkgraticule_planet.py", *argv]):
            return self.mgp.get_args()

    def test_valid_default_args(self):
        args = self._parse("out.gpkg")
        self.assertEqual(args.grid, [5, 5])
        self.assertEqual(args.res, [0.1, 0.1])

    def test_grid_step_must_be_positive(self):
        with self.assertRaises(SystemExit):
            self._parse("-g", "0", "10", "out.gpkg")

    def test_res_step_must_be_positive(self):
        with self.assertRaises(SystemExit):
            self._parse("-r", "0.1", "-1", "out.gpkg")

    def test_major_step_must_be_positive(self):
        with self.assertRaises(SystemExit):
            self._parse("-m", "30", "0", "out.gpkg")

    def test_removed_lato_option(self):
        with self.assertRaises(SystemExit):
            self._parse("-lo", "30", "out.gpkg")


if __name__ == "__main__":
    unittest.main()

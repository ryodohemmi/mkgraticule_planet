#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(DBI)
  library(RSQLite)
})

VERSION <- "1.4.0"
args <- commandArgs(trailingOnly = TRUE)

usage <- function(status = 0) {
  cat(paste0(
    "mkgraticule_planet.R\n",
    "Create planetary-scale graticules with multi-format labels for any GDAL/PROJ-supported CRS\n",
    "— exported as GeoPackage, SpatiaLite, or fitted 3D PLY.\n\n",
    "Repository: https://github.com/ryodohemmi/mkgraticule_planet\n",
    "Citation:   Hemmi, R. (2026). mkgraticule_planet. Zenodo.\n",
    "            https://doi.org/10.5281/zenodo.18864189\n\n",
    "Usage:\n",
    "  Rscript mkgraticule_planet.R \\\n",
    "    -srs IAU_2015:30135 \\\n",
    "    -e -180 -80 180 -88 \\\n",
    "    -g 30 2 \\\n",
    "    -r 0.5 0.1 \\\n",
    "    moon_south_graticule.gpkg\n\n",
    "Arguments:\n",
    "  outfile\n",
    "      Set the output filename\n",
    "      If no file extension is given, .gpkg is appended automatically.\n",
    "  -f, --format FORMAT\n",
    "      Output format: 'gpkg', 'spatialite', or 'ply' (requires Rvcg).\n",
    "      Auto-detected from outfile extension if omitted:\n",
    "        .gpkg -> gpkg, .sqlite -> spatialite, .ply -> ply.\n",
    "      Defaults to gpkg if extension is ambiguous.\n",
    "Options:\n",
    "  -h, --help\n",
    "      Show this help message and exit.\n",
    "  -v, --version\n",
    "      Show version and exit.\n",
    "  --dry-run\n",
    "      Validate and show the generation plan without writing files or asking for confirmation.\n",
    "  --metadata\n",
    "      Record generation settings in a SQLite table or PLY comments.\n",
    "  -s, -srs, --srs SRS\n",
    "      Set target spatial reference (IAU/EPSG code, PROJ/WKT string, or .wkt/.prj file).\n",
    "      Required for 2D output; no default. Not required for PLY.\n",
    "      See https://spatialreference.org/\n",
    "  -e, --extent ulx uly lrx lry\n",
    "      Set a spatial extent of the output file\n",
    "      Maps to: lon-min lat-max lon-max lat-min\n",
    "      Requires ulx < lrx and uly > lry.\n",
    "      Default: -180 90 180 -90 (global)\n",
    "      With -u meters, the extent is given in projected CRS meters and is required.\n",
    "      Legacy aliases: --lon-min --lat-max --lon-max --lat-min\n",
    "  -g, --grid xstep ystep\n",
    "      Set grid size [xstep ystep] in degrees (default: 5 5)\n",
    "      With -u meters, the value is in meters and the default is 5000 5000.\n",
    "      xstep = meridian interval, ystep = parallel interval\n",
    "      Legacy aliases: --meridian-step --parallel-step\n",
    "  -r, --res xres yres\n",
    "      Set resolution to polygonize grids [xres yres] in degrees (default: 0.1 0.1)\n",
    "      xres = longitude sampling for parallels\n",
    "      yres = latitude sampling for meridians\n",
    "      With -u meters, the value is in meters and the default is 100 100.\n",
    "      Recommended range: 0.1 (10 with -u meters) <= res <= step/2.\n",
    "      Below the lower bound, or if the estimated output exceeds 100 MB,\n",
    "      the estimated size is shown and a yes/no confirmation is asked.\n",
    "      Legacy aliases: --vertex-step-lon --vertex-step-lat\n",
    "  -m, --major xmajor ymajor\n",
    "      Major graticule interval [xmajor ymajor] in degrees (in meters with -u meters).\n",
    "      If set, grid_type will be 'major' or 'minor'.\n",
    "      If omitted, grid_type is NULL.\n",
    "  -u, --units UNITS\n",
    "      Unit of -g/-r/-m/-e: 'degrees' (default) or 'meters'.\n",
    "      'meters' generates an easting/northing grid directly in the projected CRS\n",
    "      (no reprojection) and requires a projected CRS in meters and -e.\n",
    "  -y, --yes\n",
    "      Answer yes to the output-size confirmation (needed when stdin is not a terminal).\n",
    "  -q, --qview\n",
    "      Quick View: after writing the output, open a window showing the whole grid\n",
    "      (close the window to finish).\n",
    "  -skipf, --skipfailures\n",
    "      Skip features that fail reprojection.\n",
    "  -p, --partial-reprojection\n",
    "      Allow partial reprojection near projection-domain limits.\n",
    "  -nde, --no-duplicate-endpoint\n",
    "      Drop the duplicate endpoint meridian when the longitude span is ~360 degrees\n",
    "      (e.g., keep -180 and drop 180, or keep 0 and drop 360).\n",
    "  -l, --layer NAME\n",
    "      Set output layer name explicitly.\n",
    "      If not set, defaults to 'grid' (points layer: 'point').\n",
    "  -lo, --lat-orig VALUE\n",
    "      Overwrite latitude of origin / false origin / natural origin in the target projected CRS (degrees).\n",
    "  -ls, --lat-sp VALUE\n",
    "      Overwrite standard parallel in the target projected CRS.\n",
    "      For 2SP projections, this overwrites the 1st standard parallel (degrees).\n",
    "  -ls2, --lat-sp2 VALUE\n",
    "      Overwrite the 2nd standard parallel in the target projected CRS (degrees).\n",
    "PLY options (requires Rvcg only when generating PLY):\n",
    "  -mesh, --input-mesh FILE       Input OBJ/mesh shape model (required for PLY).\n",
    "  -rorig, --ray-orig X Y Z       Ray origin (default: 0 0 0).\n",
    "  -rscale, --ray-scale VALUE     Ray start distance / mesh radius (default: 3).\n",
    "  -odist, --offset-distance VAL  Outward offset (default: 0).\n",
    "  -ofrac, --offset-fraction VAL  Offset / mesh radius (default: 0; exclusive with -odist).\n",
    "  -rbatch, --ray-batch N         Ray batch size (default: 200000).\n",
    "  -rslow, --ray-slow             Compatibility flag; Rvcg always uses its native accelerator.\n",
    "  -prgb, --ply-rgb R,G,B         Colour (default: 255,255,255).\n",
    "  -trad, --tube-rad VALUE        Tube radius; 0 writes edges (default: 0).\n",
    "  -tseg, --tube-seg N            Tube radial segments (default: 8).\n"
  ))
  quit(status = status)
}

show_version <- function() {
  cat(sprintf("%s\n", VERSION))
  quit(status = 0)
}

expect_n_values <- function(args, i, n, key) {
  if (i + n > length(args)) {
    stop(sprintf("Missing value(s) for %s", key))
  }
  args[(i + 1):(i + n)]
}

parse_args <- function(args) {
  if (length(args) == 0) usage(1)

  res <- list()
  i <- 1

  while (i <= length(args)) {
    key <- args[i]

    if (key %in% c("-h", "--help")) {
      usage(0)
    }

    if (key %in% c("-v", "--version")) {
      show_version()
    }

    if (key %in% c("--dry-run", "--metadata")) {
      res[[substring(key, 3)]] <- TRUE
      i <- i + 1
      next
    }

    flags <- c("-skipf" = "skipfailures", "--skipfailures" = "skipfailures",
               "-p" = "partial-reprojection", "--partial-reprojection" = "partial-reprojection",
               "-rslow" = "ray-slow", "--ray-slow" = "ray-slow", "--allow-slow-raycast" = "ray-slow")
    if (key %in% names(flags)) {
      res[[flags[[key]]]] <- TRUE
      i <- i + 1
      next
    }
    ply_options <- c("-mesh" = "input-mesh", "--input-mesh" = "input-mesh", "--mesh" = "input-mesh",
                     "-rorig" = "origin", "--ray-orig" = "origin", "--origin" = "origin",
                     "-rscale" = "far-scale", "--ray-scale" = "far-scale", "--far-scale" = "far-scale",
                     "-odist" = "offset-distance", "--offset-distance" = "offset-distance",
                     "-ofrac" = "offset-fraction", "-ofract" = "offset-fraction", "--offset-fraction" = "offset-fraction",
                     "-rbatch" = "batch-size", "--ray-batch" = "batch-size", "--batch-size" = "batch-size",
                     "-prgb" = "color", "--ply-rgb" = "color", "--color" = "color",
                     "-trad" = "tube-radius", "--tube-rad" = "tube-radius", "--tube-radius" = "tube-radius",
                     "-tseg" = "tube-segments", "--tube-seg" = "tube-segments", "--tube-segments" = "tube-segments")
    if (key %in% names(ply_options)) {
      name <- ply_options[[key]]
      n <- if (name == "origin") 3L else 1L
      res[[name]] <- expect_n_values(args, i, n, key)
      i <- i + n + 1L
      next
    }

    if (key %in% c("-e", "--extent")) {
      vals <- expect_n_values(args, i, 4, key)
      ulx <- suppressWarnings(as.numeric(vals[1]))
      uly <- suppressWarnings(as.numeric(vals[2]))
      lrx <- suppressWarnings(as.numeric(vals[3]))
      lry <- suppressWarnings(as.numeric(vals[4]))
      if (is.na(ulx) || is.na(uly) || is.na(lrx) || is.na(lry)) {
        stop("Extent values must be numeric: ulx uly lrx lry")
      }
      if (ulx >= lrx) {
        stop(sprintf("extent requires ulx < lrx (got ulx=%s, lrx=%s).", ulx, lrx))
      }
      if (uly <= lry) {
        stop(sprintf("extent requires uly > lry (got uly=%s, lry=%s).", uly, lry))
      }
      res[["lon-min"]] <- vals[1]
      res[["lat-max"]] <- vals[2]
      res[["lon-max"]] <- vals[3]
      res[["lat-min"]] <- vals[4]
      i <- i + 5
      next
    }

    if (key %in% c("-g", "--grid")) {
      vals <- expect_n_values(args, i, 2, key)
      res[["meridian-step"]] <- vals[1]
      res[["parallel-step"]] <- vals[2]
      i <- i + 3
      next
    }

    if (key %in% c("-r", "--res")) {
      vals <- expect_n_values(args, i, 2, key)
      res[["vertex-step-lon"]] <- vals[1]
      res[["vertex-step-lat"]] <- vals[2]
      i <- i + 3
      next
    }

    if (key %in% c("-m", "--major")) {
      vals <- expect_n_values(args, i, 2, key)
      res[["major-meridian-step"]] <- vals[1]
      res[["major-parallel-step"]] <- vals[2]
      i <- i + 3
      next
    }

    if (key %in% c("-nde", "--no-duplicate-endpoint")) {
      res[["no-duplicate-endpoint"]] <- TRUE
      i <- i + 1
      next
    }

    if (key %in% c("-u", "--units")) {
      vals <- expect_n_values(args, i, 1, key)
      units <- tolower(vals[1])
      if (!units %in% c("degrees", "meters")) {
        stop(sprintf("--units must be 'degrees' or 'meters', got '%s'", vals[1]))
      }
      res[["units"]] <- units
      i <- i + 2
      next
    }

    if (key %in% c("-y", "--yes")) {
      res[["yes"]] <- TRUE
      i <- i + 1
      next
    }

    if (key %in% c("-q", "--qview")) {
      res[["qview"]] <- TRUE
      i <- i + 1
      next
    }

    if (key %in% c("-s", "-srs", "--srs")) {
      if (i == length(args) || startsWith(args[i + 1L], "-")) {
        stop(sprintf("Missing CRS value for %s; specify a CRS code, PROJ/WKT string, or .wkt/.prj file.", key), call. = FALSE)
      }
      vals <- expect_n_values(args, i, 1, key)
      res[["proj-crs"]] <- vals[1]
      i <- i + 2
      next
    }

    if (key %in% c("-f", "--format")) {
      vals <- expect_n_values(args, i, 1, key)
      fmt <- tolower(vals[1])
      if (!fmt %in% c("gpkg", "spatialite", "ply")) {
        stop(sprintf("--format must be 'gpkg', 'spatialite', or 'ply', got '%s'", vals[1]))
      }
      res[["format"]] <- fmt
      i <- i + 2
      next
    }

    if (key %in% c("-l", "--layer")) {
      vals <- expect_n_values(args, i, 1, key)
      res[["layer"]] <- vals[1]
      i <- i + 2
      next
    }

    if (key %in% c("-lo", "--lat-orig")) {
      vals <- expect_n_values(args, i, 1, key)
      res[["lat-orig"]] <- vals[1]
      i <- i + 2
      next
    }

    if (key %in% c("-ls", "--lat-sp")) {
      vals <- expect_n_values(args, i, 1, key)
      res[["lat-sp"]] <- vals[1]
      i <- i + 2
      next
    }

    if (key %in% c("-ls2", "--lat-sp2")) {
      vals <- expect_n_values(args, i, 1, key)
      res[["lat-sp2"]] <- vals[1]
      i <- i + 2
      next
    }

    if (startsWith(key, "--")) {
      name <- sub("^--", "", key)
      if (!name %in% c(
        "lon-min", "lat-max", "lon-max", "lat-min",
        "meridian-step", "parallel-step", "vertex-step-lat", "vertex-step-lon"
      )) {
        stop(sprintf("Unknown option: %s", key))
      }

      vals <- expect_n_values(args, i, 1, key)
      res[[name]] <- vals[1]
      i <- i + 2
      next
    }

    if (startsWith(key, "-")) {
      stop(sprintf("Unknown option: %s", key))
    }

    if (!is.null(res[["outfile"]])) {
      stop(sprintf("Unexpected positional argument: %s", key))
    }
    res[["outfile"]] <- key
    i <- i + 1
  }

  if (is.null(res[["outfile"]])) {
    stop("Missing required argument: outfile", call. = FALSE)
  }

  res
}

get_required <- function(opts, name) {
  if (is.null(opts[[name]])) stop(sprintf("Missing required argument: %s", name))
  opts[[name]]
}

get_optional <- function(opts, name, default) {
  if (is.null(opts[[name]])) default else opts[[name]]
}

to_num <- function(x, name) {
  y <- suppressWarnings(as.numeric(x))
  if (is.na(y)) stop(sprintf("Argument %s must be numeric: %s", name, x))
  y
}

assert_positive <- function(x, name) {
  if (x <= 0) stop(sprintf("Argument %s must be > 0: %s", name, x))
}

normalize_outfile <- function(path) {
  ext <- tools::file_ext(path)
  if (identical(ext, "")) {
    paste0(path, ".gpkg")
  } else {
    path
  }
}

resolve_output_format <- function(outfile, fmt_flag = NULL) {
  ext_map <- c(".gpkg" = "gpkg", ".sqlite" = "spatialite", ".sqlite3" = "spatialite", ".spatialite" = "spatialite", ".ply" = "ply")
  ext <- tolower(tools::file_ext(outfile))
  ext_dot <- if (nzchar(ext)) paste0(".", ext) else ""

  if (!is.null(fmt_flag)) {
    fmt <- fmt_flag
  } else if (ext_dot %in% names(ext_map)) {
    fmt <- ext_map[[ext_dot]]
  } else {
    fmt <- "gpkg"
  }

  if (!ext_dot %in% names(ext_map)) {
    default_ext <- switch(fmt, spatialite = ".spatialite", ply = ".ply", ".gpkg")
    outfile <- paste0(outfile, default_ext)
  }

  list(outfile = outfile, format = fmt, is_gpkg = (fmt == "gpkg"))
}

layer_from_outfile <- function(path) {
  tools::file_path_sans_ext(basename(path))
}

seq_inclusive <- function(from, to, by) {
  seq(from, to + 1e-12, by = by)
}

norm_zero <- function(x, eps = 1e-12) {
  ifelse(abs(x) < eps, 0, x)
}

deg_text <- function(x) {
  x <- norm_zero(as.numeric(x))
  if (abs(x - round(x)) < 1e-9) {
    return(as.character(as.integer(round(x))))
  }
  s <- format(x, scientific = FALSE, trim = TRUE, digits = 15)
  s <- sub("\\.?0+$", "", s)
  if (identical(s, "-0")) s <- "0"
  s
}

lat_90_label <- function(lat) {
  paste0(deg_text(lat), "°")
}

lat_ns_label <- function(lat) {
  lat <- norm_zero(lat)
  if (lat > 0) return(paste0(deg_text(abs(lat)), "°N"))
  if (lat < 0) return(paste0(deg_text(abs(lat)), "°S"))
  "0°"
}

lon_180_label <- function(lon) {
  paste0(deg_text(lon), "°")
}

lon_ew_label <- function(lon) {
  v <- ((as.numeric(lon) + 180) %% 360) - 180
  v <- norm_zero(v)
  if (abs(v + 180) < 1e-12) v <- 180
  if (v > 0) return(paste0(deg_text(abs(v)), "°E"))
  if (v < 0) return(paste0(deg_text(abs(v)), "°W"))
  "0°"
}

lon_360_label <- function(lon) {
  v <- ((as.numeric(lon) %% 360) + 360) %% 360
  v <- norm_zero(v)
  paste0(deg_text(v), "°")
}

lon_360e_label <- function(lon) {
  v <- ((as.numeric(lon) %% 360) + 360) %% 360
  v <- norm_zero(v)
  if (v == 0) return("0°")
  paste0(deg_text(v), "°E")
}

lon_360w_label <- function(lon) {
  v <- ((-as.numeric(lon)) %% 360 + 360) %% 360
  v <- norm_zero(v)
  if (v == 0) return("0°")
  paste0(deg_text(v), "°W")
}

is_multiple <- function(val, base, eps = 1e-9) {
  if (is.null(base) || is.na(base)) return(FALSE)
  base <- as.numeric(base)
  if (!is.finite(base) || abs(base) < eps) return(FALSE)
  k <- as.numeric(val) / base
  abs(k - round(k)) < eps
}

normalize_authority_name <- function(auth, version = NULL) {
  if (!is.null(version) && !is.na(version) && nzchar(version) && auth == "IAU") {
    return(sprintf("IAU_%s", version))
  }
  auth
}

extract_wkt_node <- function(wkt, node_name) {
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) return(NULL)

  m <- regexpr(sprintf("%s\\[", node_name), wkt, perl = TRUE)
  if (m[1] < 1) return(NULL)

  start <- m[1]
  chars <- strsplit(wkt, "", fixed = TRUE)[[1]]
  i <- start + attr(m, "match.length") - 1L
  depth <- 1L
  in_quote <- FALSE

  while (i < length(chars) && depth > 0L) {
    i <- i + 1L
    ch <- chars[i]

    if (ch == '"') {
      in_quote <- !in_quote
    } else if (!in_quote) {
      if (ch == '[') depth <- depth + 1L
      if (ch == ']') depth <- depth - 1L
    }
  }

  if (depth != 0L) return(NULL)
  paste(chars[start:i], collapse = "")
}

extract_last_authority_from_text <- function(txt) {
  if (is.null(txt) || is.na(txt) || !nzchar(txt)) return(NULL)

  # Only the root node's identifier names this CRS, not nested unit/datum IDs.
  chars <- strsplit(txt, "", fixed = TRUE)[[1]]
  direct <- logical(length(chars))
  depth <- 0L
  in_quote <- FALSE
  for (i in seq_along(chars)) {
    ch <- chars[i]
    direct[i] <- depth == 1L && !in_quote
    if (ch == '"') in_quote <- !in_quote
    if (!in_quote) {
      if (ch == "[") depth <- depth + 1L
      if (ch == "]") depth <- depth - 1L
    }
  }

  id_pat <- 'ID\\["([^"]+)",\\s*([0-9]+)(?:\\s*,\\s*([0-9]+))?\\]'
  id_hits <- gregexpr(id_pat, txt, perl = TRUE)
  id_vals <- regmatches(txt, id_hits)[[1]]
  if (length(id_vals)) id_vals <- id_vals[direct[id_hits[[1]]]]
  if (length(id_vals) > 0) {
    last_hit <- id_vals[[length(id_vals)]]
    mm <- regexec(id_pat, last_hit, perl = TRUE)
    parts <- regmatches(last_hit, mm)[[1]]
    auth <- normalize_authority_name(parts[2], if (length(parts) >= 4) parts[4] else NULL)
    return(list(auth = auth, code = parts[3]))
  }

  auth_pat <- 'AUTHORITY\\["([^"]+)",\\s*"?([0-9]+)"?\\]'
  auth_hits <- gregexpr(auth_pat, txt, perl = TRUE)
  auth_vals <- regmatches(txt, auth_hits)[[1]]
  if (length(auth_vals)) auth_vals <- auth_vals[direct[auth_hits[[1]]]]
  if (length(auth_vals) > 0) {
    last_hit <- auth_vals[[length(auth_vals)]]
    mm <- regexec(auth_pat, last_hit, perl = TRUE)
    parts <- regmatches(last_hit, mm)[[1]]
    return(list(auth = parts[2], code = parts[3]))
  }

  NULL
}

extract_outer_authority <- function(srs_code) {
  if (grepl("^[A-Za-z0-9_]+:[0-9]+$", srs_code)) {
    parts <- strsplit(srs_code, ":", fixed = TRUE)[[1]]
    return(list(auth = parts[1], code = parts[2]))
  }

  crs_obj <- st_crs(srs_code)
  wkt <- crs_obj$wkt
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) {
    return(NULL)
  }

  key <- wkt_top_keyword(wkt)
  node_txt <- if (!is.na(key)) extract_wkt_node(wkt, key) else NULL
  if (!is.null(node_txt)) {
    auth <- extract_last_authority_from_text(node_txt)
    if (!is.null(auth)) return(auth)
  }

  extract_last_authority_from_text(wkt)
}

fix_gpkg_crs_wkt <- function(gpkg, srs_code) {
  crs_obj <- st_crs(srs_code)
  auth <- extract_outer_authority(srs_code)

  if (is.null(auth)) {
    warning("target SRS has no authority code; skip gpkg_spatial_ref_sys.definition_12_063 update.")
    return(invisible(NULL))
  }

  srs_id <- suppressWarnings(as.integer(auth$code))
  if (is.na(srs_id)) {
    warning(sprintf("authority code is not an integer (%s); skip gpkg_spatial_ref_sys.definition_12_063 update.", auth$code))
    return(invisible(NULL))
  }

  con <- dbConnect(SQLite(), gpkg)
  on.exit(dbDisconnect(con), add = TRUE)

  cols <- dbGetQuery(con, "PRAGMA table_info(gpkg_spatial_ref_sys);")$name

  if (!"definition_12_063" %in% cols) {
    dbExecute(con, "ALTER TABLE gpkg_spatial_ref_sys ADD COLUMN definition_12_063 TEXT;")
  }
  if (!"epoch" %in% cols) {
    dbExecute(con, "ALTER TABLE gpkg_spatial_ref_sys ADD COLUMN epoch DOUBLE;")
  }
  if (dbGetQuery(con, "SELECT COUNT(*) AS n FROM gpkg_extensions WHERE extension_name = 'gpkg_crs_wkt';")$n[1] == 0) {
    dbExecute(
      con,
      "INSERT INTO gpkg_extensions
       (table_name, column_name, extension_name, definition, scope)
       VALUES
       (NULL, NULL, 'gpkg_crs_wkt',
        'http://www.geopackage.org/spec/#extension_crs_wkt',
        'read-write');"
    )
  }

  exists <- dbGetQuery(con, "SELECT COUNT(*) AS n FROM gpkg_spatial_ref_sys WHERE srs_id = ?;", params = list(srs_id))$n[1]
  if (!isTRUE(exists > 0)) {
    warning(sprintf("gpkg_spatial_ref_sys has no row with srs_id=%s; skip definition_12_063 update.", srs_id))
    return(invisible(NULL))
  }

  dbExecute(
    con,
    "UPDATE gpkg_spatial_ref_sys
     SET definition_12_063 = ?
     WHERE srs_id = ?;",
    params = list(crs_obj$wkt, srs_id)
  )

  invisible(NULL)
}

wkt_top_keyword <- function(wkt) {
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) return(NA_character_)
  m <- regexec('^\\s*([A-Z_]+)\\[', wkt, perl = TRUE)
  parts <- regmatches(wkt, m)[[1]]
  if (length(parts) >= 2) parts[2] else NA_character_
}

is_geographic_input <- function(srs_code) {
  wkt <- st_crs(srs_code)$wkt
  key <- wkt_top_keyword(wkt)
  identical(key, "GEOGCRS") || identical(key, "GEODCRS") || identical(key, "GEOGCS") || identical(key, "GEODETICCRS")
}

extract_base_geographic_authority <- function(wkt) {
  for (node_name in c("BASEGEOGCRS", "BASEGEODCRS", "GEOGCRS", "GEODCRS", "GEOGCS")) {
    node_txt <- extract_wkt_node(wkt, node_name)
    auth <- extract_last_authority_from_text(node_txt)
    if (!is.null(auth)) {
      return(sprintf("%s:%s", auth$auth, auth$code))
    }
  }

  NULL
}

fallback_geographic_crs_from_wkt <- function(wkt) {
  ellipsoid_patterns <- c(
    '(?s)ELLIPSOID\\[[^,]*,\\s*([0-9.]+)\\s*,\\s*([0-9.]+)',
    '(?s)SPHEROID\\[[^,]*,\\s*([0-9.]+)\\s*,\\s*([0-9.]+)'
  )

  a <- invf <- NULL
  for (pat in ellipsoid_patterns) {
    m <- regexec(pat, wkt, perl = TRUE)
    parts <- regmatches(wkt, m)[[1]]
    if (length(parts) >= 3) {
      a <- as.numeric(parts[2])
      invf <- as.numeric(parts[3])
      break
    }
  }

  if (is.null(a) || is.na(a) || is.null(invf) || is.na(invf)) {
    stop("Could not infer geographic base CRS from -srs.")
  }

  b <- if (abs(invf) < 1e-12) a else a * (1 - 1 / invf)

  pm <- 0
  m <- regexec('(?s)PRIMEM\\[[^,]*,\\s*([-0-9.]+)', wkt, perl = TRUE)
  parts <- regmatches(wkt, m)[[1]]
  if (length(parts) >= 2) {
    pm <- suppressWarnings(as.numeric(parts[2]))
    if (is.na(pm)) pm <- 0
  }

  paste(
    "+proj=longlat",
    sprintf("+a=%s", format(a, scientific = FALSE, trim = TRUE, digits = 15)),
    sprintf("+b=%s", format(b, scientific = FALSE, trim = TRUE, digits = 15)),
    sprintf("+pm=%s", format(pm, scientific = FALSE, trim = TRUE, digits = 15)),
    "+no_defs +type=crs"
  )
}

infer_geo_crs_from_srs <- function(srs_code) {
  crs_obj <- st_crs(srs_code)
  if (is.na(crs_obj)) {
    stop(sprintf("Invalid CRS: %s", srs_code))
  }

  if (is_geographic_input(srs_code)) {
    return(srs_code)
  }

  wkt <- crs_obj$wkt
  auth <- extract_base_geographic_authority(wkt)
  if (!is.null(auth)) {
    return(auth)
  }

  fallback_geographic_crs_from_wkt(wkt)
}

make_meridian <- function(lon, lat_min, lat_max, step) {
  lat <- seq_inclusive(lat_min, lat_max, step)
  st_linestring(cbind(rep(lon, length(lat)), lat))
}

make_parallel <- function(lat, lon_min, lon_max, step) {
  lon <- seq_inclusive(lon_min, lon_max, step)
  st_linestring(cbind(lon, rep(lat, length(lon))))
}

terminal_width <- function(default = 80L) {
  cols <- suppressWarnings(as.integer(Sys.getenv("COLUMNS", unset = "")))
  if (is.na(cols) || cols <= 0) {
    # Try tput cols (works on most Unix terminals)
    cols <- tryCatch({
      suppressWarnings(as.integer(system("tput cols 2>/dev/null", intern = TRUE)))
    }, error = function(e) NA_integer_)
  }
  if (length(cols) != 1L || is.na(cols) || cols <= 0) {
    cols <- suppressWarnings(as.integer(getOption("width", default)))
  }
  if (is.na(cols) || cols <= 0) cols <- default
  cols
}

print_separator <- function(width) {
  cat(strrep("=", width), "\n", sep = "")
}

show_wkt <- function(crs_obj) {
  wkt <- crs_obj$wkt
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) {
    cat("<WKT unavailable>\n")
  } else {
    cat(wkt)
    if (!grepl("\\n$", wkt)) cat("\n")
  }
}

authority_label <- function(srs_code) {
  auth <- extract_outer_authority(srs_code)
  if (!is.null(auth)) {
    return(sprintf("%s:%s", auth$auth, auth$code))
  }
  crs_obj <- st_crs(srs_code)
  if (!is.null(crs_obj$input) && !is.na(crs_obj$input) && nzchar(crs_obj$input)) {
    return(crs_obj$input)
  }
  "unknown"
}

progress_bar <- function(i, total, label, progress_bar_width = 20L) {
  if (total <= 0) return(invisible(NULL))
  progress <- floor(i / total * progress_bar_width)
  percent <- i / total * 100
  bar <- paste0(
    "[",
    strrep("#", progress),
    strrep(" ", progress_bar_width - progress),
    "]"
  )
  cat(sprintf("\r%s%s %6.2f%%", label, bar, percent))
  flush.console()
  invisible(NULL)
}

normalize_param_name <- function(x) {
  gsub("[^a-z0-9]", "", tolower(x))
}

extract_wkt_parameters <- function(wkt) {
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) return(list())
  pat <- 'PARAMETER\\["([^"]+)",\\s*([-+0-9.eE]+)'
  hits <- gregexpr(pat, wkt, perl = TRUE)
  vals <- regmatches(wkt, hits)[[1]]
  out <- list()
  if (length(vals) == 0) return(out)
  for (hit in vals) {
    mm <- regexec(pat, hit, perl = TRUE)
    parts <- regmatches(hit, mm)[[1]]
    if (length(parts) >= 3) {
      out[[normalize_param_name(parts[2])]] <- suppressWarnings(as.numeric(parts[3]))
    }
  }
  out
}

get_projection_center_lat_lon <- function(crs_obj) {
  params <- extract_wkt_parameters(crs_obj$wkt)

  lat_keys <- c(
    "latitudeofnaturalorigin",
    "latitudeoforigin",
    "latitudeofprojectioncenter",
    "latitudeoffalseorigin",
    "latitudeofcenter"
  )
  lon_keys <- c(
    "longitudeofnaturalorigin",
    "longitudeoforigin",
    "longitudeofprojectioncenter",
    "longitudeoffalseorigin",
    "longitudeofcenter",
    "centralmeridian",
    "straightverticallongitudefrompole"
  )

  center_lat <- NULL
  center_lon <- NULL

  for (key in lat_keys) {
    if (!is.null(params[[key]]) && is.finite(params[[key]])) {
      center_lat <- as.numeric(params[[key]])
      break
    }
  }
  for (key in lon_keys) {
    if (!is.null(params[[key]]) && is.finite(params[[key]])) {
      center_lon <- as.numeric(params[[key]])
      break
    }
  }

  list(lat = center_lat, lon = center_lon)
}

transform_points_safe <- function(coords, crs_src, crs_dst) {
  coords <- as.matrix(coords)
  if (length(coords) == 0L) {
    return(matrix(numeric(0), ncol = 2))
  }
  storage.mode(coords) <- "double"

  fallback_transform <- function(coords_in) {
    pts <- lapply(seq_len(nrow(coords_in)), function(i) {
      pt <- tryCatch(
        st_sfc(st_point(coords_in[i, 1:2]), crs = crs_src),
        error = function(e) NULL
      )
      if (is.null(pt)) return(NULL)

      out <- tryCatch(
        suppressWarnings(st_transform(pt, crs_dst)),
        error = function(e) NULL
      )
      if (is.null(out) || length(out) < 1 || isTRUE(st_is_empty(out)[1])) return(NULL)

      xy <- tryCatch(st_coordinates(out)[1, c("X", "Y")], error = function(e) NULL)
      if (is.null(xy) || any(!is.finite(xy))) return(NULL)
      as.numeric(xy)
    })
    pts <- pts[!vapply(pts, is.null, logical(1))]
    if (length(pts) == 0L) return(matrix(numeric(0), ncol = 2))
    do.call(rbind, pts)
  }

  sf_project_available <- "sf_project" %in% getNamespaceExports("sf")
  if (sf_project_available) {
    out <- tryCatch(
      sf::sf_project(
        from = crs_src,
        to = crs_dst,
        pts = coords,
        keep = TRUE,
        warn = FALSE,
        authority_compliant = FALSE
      ),
      error = function(e) NULL
    )
    if (!is.null(out)) {
      out <- as.matrix(out)
      if (nrow(out) > 0L) {
        ok <- is.finite(out[, 1]) & is.finite(out[, 2])
        out_ok <- out[ok, , drop = FALSE]
        if (nrow(out_ok) > 0L) {
          return(out_ok)
        }
      }
    }
  }

  fallback_transform(coords)
}

transform_point_safe <- function(x, y, crs_src, crs_dst) {
  out <- transform_points_safe(matrix(c(as.numeric(x), as.numeric(y)), ncol = 2), crs_src, crs_dst)
  if (is.null(out) || nrow(out) < 1) return(NULL)
  c(out[1, 1], out[1, 2])
}

collapsed_target_point <- function(sample_coords, crs_src, crs_dst, tol = 1e-8, min_ok_points = 1L) {
  pts <- transform_points_safe(sample_coords, crs_src, crs_dst)
  if (is.null(pts)) {
    return(list(is_collapsed = FALSE, xy = NULL))
  }
  if (nrow(pts) < min_ok_points) {
    return(list(is_collapsed = FALSE, xy = NULL))
  }
  if (nrow(pts) == 1L) {
    return(list(is_collapsed = TRUE, xy = c(pts[1, 1], pts[1, 2])))
  }

  refx <- pts[1, 1]
  refy <- pts[1, 2]
  d2 <- (pts[, 1] - refx)^2 + (pts[, 2] - refy)^2
  max_dist <- sqrt(max(d2))

  if (max_dist <= tol) {
    xy <- c(mean(pts[, 1]), mean(pts[, 2]))
    if (all(is.finite(xy))) {
      return(list(is_collapsed = TRUE, xy = xy))
    }
  }

  list(is_collapsed = FALSE, xy = NULL)
}

new_parallel_line_row <- function(row, lat, grid_type = NA_character_) {
  data.frame(
    row_no = as.integer(row),
    lat = as.numeric(lat),
    lon = NA_real_,
    lat_90 = lat_90_label(lat),
    lat_ns = lat_ns_label(lat),
    lon_180 = NA_character_,
    lon_ew = NA_character_,
    lon_360 = NA_character_,
    lon_360e = NA_character_,
    lon_360w = NA_character_,
    grid_type = if (is.null(grid_type)) NA_character_ else as.character(grid_type),
    stringsAsFactors = FALSE
  )
}

new_meridian_line_row <- function(row, lon, grid_type = NA_character_) {
  data.frame(
    row_no = as.integer(row),
    lat = NA_real_,
    lon = as.numeric(lon),
    lat_90 = NA_character_,
    lat_ns = NA_character_,
    lon_180 = lon_180_label(lon),
    lon_ew = lon_ew_label(lon),
    lon_360 = lon_360_label(lon),
    lon_360e = lon_360e_label(lon),
    lon_360w = lon_360w_label(lon),
    grid_type = if (is.null(grid_type)) NA_character_ else as.character(grid_type),
    stringsAsFactors = FALSE
  )
}

new_parallel_point_row <- function(row, lat, point_role = "collapsed") {
  data.frame(
    row_no = as.integer(row),
    lat = as.numeric(lat),
    lon = NA_real_,
    lat_90 = lat_90_label(lat),
    lat_ns = lat_ns_label(lat),
    lon_180 = NA_character_,
    lon_ew = NA_character_,
    lon_360 = NA_character_,
    lon_360e = NA_character_,
    lon_360w = NA_character_,
    point_role = point_role,
    stringsAsFactors = FALSE
  )
}

new_meridian_point_row <- function(row, lon, point_role = "collapsed") {
  data.frame(
    row_no = as.integer(row),
    lat = NA_real_,
    lon = as.numeric(lon),
    lat_90 = NA_character_,
    lat_ns = NA_character_,
    lon_180 = lon_180_label(lon),
    lon_ew = lon_ew_label(lon),
    lon_360 = lon_360_label(lon),
    lon_360e = lon_360e_label(lon),
    lon_360w = lon_360w_label(lon),
    point_role = point_role,
    stringsAsFactors = FALSE
  )
}

new_center_point_row <- function(center_lat, center_lon) {
  data.frame(
    row_no = 1L,
    lat = if (is.null(center_lat)) NA_real_ else as.numeric(center_lat),
    lon = if (is.null(center_lon)) NA_real_ else as.numeric(center_lon),
    lat_90 = if (is.null(center_lat)) NA_character_ else lat_90_label(center_lat),
    lat_ns = if (is.null(center_lat)) NA_character_ else lat_ns_label(center_lat),
    lon_180 = if (is.null(center_lon)) NA_character_ else lon_180_label(center_lon),
    lon_ew = if (is.null(center_lon)) NA_character_ else lon_ew_label(center_lon),
    lon_360 = if (is.null(center_lon)) NA_character_ else lon_360_label(center_lon),
    lon_360e = if (is.null(center_lon)) NA_character_ else lon_360e_label(center_lon),
    lon_360w = if (is.null(center_lon)) NA_character_ else lon_360w_label(center_lon),
    point_role = "center",
    stringsAsFactors = FALSE
  )
}

replace_wkt_parameter_value <- function(wkt, param_names, new_value) {
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) {
    return(list(wkt = wkt, matched = NULL))
  }

  value_txt <- format(as.numeric(new_value), scientific = FALSE, trim = TRUE, digits = 15)
  for (param_name in param_names) {
    pat <- sprintf('(PARAMETER\\["\\Q%s\\E",\\s*)([-+]?\\d+(?:\\.\\d+)?(?:[eE][-+]?\\d+)?)', param_name)
    if (grepl(pat, wkt, perl = TRUE)) {
      out <- sub(pat, paste0('\\1', value_txt), wkt, perl = TRUE)
      return(list(wkt = out, matched = param_name))
    }
  }

  list(wkt = wkt, matched = NULL)
}

override_projection_latitude_parameters <- function(crs_obj, lat_orig = NULL, lat_sp = NULL, lat_sp2 = NULL) {
  if (is.null(lat_orig) && is.null(lat_sp) && is.null(lat_sp2)) {
    return(list(crs = crs_obj, applied = list()))
  }

  wkt <- crs_obj$wkt
  if (is.null(wkt) || is.na(wkt) || !nzchar(wkt)) {
    stop('Target CRS has no WKT; cannot apply projection parameter overrides.')
  }

  available <- names(extract_wkt_parameters(wkt))
  applied <- list()

  specs <- list(
    list(
      key = 'lat_orig',
      value = lat_orig,
      candidates = c(
        'Latitude of false origin',
        'Latitude of natural origin',
        'Latitude of origin',
        'Latitude of true origin',
        'Latitude of center',
        'Latitude of projection centre',
        'Latitude of projection center'
      )
    ),
    list(
      key = 'lat_sp',
      value = lat_sp,
      candidates = c(
        'Latitude of 1st standard parallel',
        'Latitude of standard parallel',
        'Standard parallel 1'
      )
    ),
    list(
      key = 'lat_sp2',
      value = lat_sp2,
      candidates = c(
        'Latitude of 2nd standard parallel',
        'Standard parallel 2'
      )
    )
  )

  out_wkt <- wkt
  for (spec in specs) {
    if (is.null(spec$value)) next

    hit <- replace_wkt_parameter_value(out_wkt, spec$candidates, spec$value)
    if (is.null(hit$matched)) {
      stop(sprintf(
        'Requested --%s override, but the target CRS does not expose a compatible parameter. Available WKT parameter names: %s',
        gsub('_', '-', spec$key),
        if (length(available)) paste(available, collapse = ', ') else 'none'
      ))
    }
    out_wkt <- hit$wkt
    applied[[spec$key]] <- hit$matched
  }

  list(crs = st_crs(out_wkt), applied = applied)
}

check_meters_units <- function(crs_obj, projected) {
  if (!projected) {
    stop(paste0(
      "-u meters requires a projected target CRS, but the given CRS is not projected.\n",
      "Use a projected CRS (e.g. polar stereographic) or omit -u to use degrees."
    ))
  }
  unit <- st_crs(crs_obj)$units_gdal
  if (is.null(unit) || is.na(unit) || !tolower(unit) %in% c("metre", "meter")) {
    stop(sprintf(
      "-u meters requires a projected CRS whose linear unit is the metre (got '%s').",
      if (is.null(unit) || is.na(unit)) "unknown" else unit
    ))
  }
  invisible(NULL)
}

# Integer multiples of step inside [vmin, vmax] (grid anchored at 0).
meter_ticks <- function(vmin, vmax, step, eps = 1e-9) {
  k0 <- ceiling(vmin / step - eps)
  k1 <- floor(vmax / step + eps)
  if (k1 < k0) return(numeric(0))
  (k0:k1) * step
}

# Sample positions from vmin to vmax (both included) spaced by res.
meter_samples <- function(vmin, vmax, res) {
  s <- seq(vmin, vmax, by = res)
  if (length(s) > 0L && vmax - s[length(s)] < 1e-9 * max(1, abs(vmax))) {
    s <- s[-length(s)]
  }
  c(s, vmax)
}

RES_FLOOR_DEGREES <- 0.1
RES_FLOOR_METERS <- 10
SIZE_CONFIRM_BYTES <- 100e6
BYTES_PER_VERTEX <- 16  # 2D double coordinates in WKB

# Number of values seq(vmin, vmax + 1e-12, by = step) would yield (without allocating them).
count_samples <- function(vmin, vmax, step) {
  floor((vmax + 1e-12 - vmin) / step) + 1
}

# Lines and vertices the grid would contain. An upper bound; needs no CRS.
estimate_grid <- function(is_meters, xmin, xmax, ymin, ymax, xstep, ystep, xres, yres, nde) {
  if (is_meters) {
    n_x <- max(0, floor(xmax / xstep + 1e-9) - ceiling(xmin / xstep - 1e-9) + 1)
    n_y <- max(0, floor(ymax / ystep + 1e-9) - ceiling(ymin / ystep - 1e-9) + 1)
    per_h <- ceiling((xmax - xmin) / xres) + 1
    per_v <- ceiling((ymax - ymin) / yres) + 1
  } else {
    n_x <- count_samples(xmin, xmax, xstep)
    n_y <- count_samples(ymin, ymax, ystep)
    if (nde && abs((xmax - xmin) - 360) < 1e-9 && n_x > 1 &&
        abs(xmin + (n_x - 1) * xstep - xmax) < 1e-9) n_x <- n_x - 1
    per_h <- count_samples(xmin, xmax, xres)
    per_v <- count_samples(ymin, ymax, yres)
  }
  # n_y horizontal lines run along x (per_h vertices each); n_x vertical lines run along y (per_v each).
  list(lines = n_x + n_y, vertices = n_y * per_h + n_x * per_v)
}

format_size <- function(n) {
  for (u in c("B", "KB", "MB", "GB")) {
    if (n < 1000) return(if (u == "B") sprintf("%.0f B", n) else sprintf("%.1f %s", n, u))
    n <- n / 1000
  }
  sprintf("%.1f TB", n)
}

# Ask until the answer is y/yes or n/no (case-insensitive). End of input counts as no.
ask_yes_no <- function(question) {
  con <- file("stdin")
  open(con)
  on.exit(close(con), add = TRUE)
  repeat {
    cat(question)
    flush.console()
    answer <- readLines(con, n = 1L, warn = FALSE)
    if (length(answer) == 0L) return(FALSE)
    answer <- tolower(trimws(answer))
    if (answer %in% c("y", "yes")) return(TRUE)
    if (answer %in% c("n", "no")) return(FALSE)
    cat("Please answer 'y' (yes) or 'n' (no).\n")
  }
}

# Warn and ask for confirmation when -r is below its recommended lower bound or the output is large.
# Recommended range per axis: floor <= res <= step/2, with floor = 0.1 degrees or 10 m;
# when step/2 is smaller than the floor, the floor is relaxed to step/2.
# Quits with status 1 (before anything is written) unless the user answers yes or -y is given.
confirm_output_size <- function(is_meters, xmin, xmax, ymin, ymax, xstep, ystep, xres, yres, nde, yes) {
  unit <- if (is_meters) "m" else "degrees"
  floor_res <- if (is_meters) RES_FLOOR_METERS else RES_FLOOR_DEGREES
  low <- character(0)
  high <- character(0)
  for (a in list(list("xres", xres, xstep), list("yres", yres, ystep))) {
    lower <- min(floor_res, a[[3]] / 2)
    if (a[[2]] < lower * (1 - 1e-9)) {
      low <- c(low, sprintf("%s=%g is below the recommended lower bound %g %s", a[[1]], a[[2]], lower, unit))
    } else if (a[[2]] > a[[3]] / 2 * (1 + 1e-9)) {
      high <- c(high, sprintf("%s=%g exceeds step/2 (%g %s); lines may look coarse", a[[1]], a[[2]], a[[3]] / 2, unit))
    }
  }

  est <- estimate_grid(is_meters, xmin, xmax, ymin, ymax, xstep, ystep, xres, yres, nde)
  size <- est$vertices * BYTES_PER_VERTEX

  for (msg in high) message(sprintf("NOTE: %s.", msg))

  reasons <- low
  if (size > SIZE_CONFIRM_BYTES) {
    reasons <- c(reasons, sprintf("estimated output size exceeds %s", format_size(SIZE_CONFIRM_BYTES)))
  }
  if (length(reasons) == 0L) return(invisible(NULL))

  message("WARNING: ", paste(reasons, collapse = "; "), ".")
  message(sprintf(
    "  Estimated output: ~%s (%s vertices in %s lines; approximate, geometry only).",
    format_size(size),
    format(est$vertices, big.mark = ",", scientific = FALSE),
    format(est$lines, big.mark = ",", scientific = FALSE)
  ))

  if (yes) {
    message("  Continuing because -y/--yes was given.")
    return(invisible(NULL))
  }
  if (!isatty(stdin())) {
    message(paste0(
      "  Aborted: standard input is not a terminal, so the confirmation cannot be asked.\n",
      "  Re-run interactively, or pass -y/--yes to continue without asking."
    ))
    quit(status = 1)
  }
  if (!ask_yes_no("Continue? [y/N]: ")) {
    message("Aborted: no output was written.")
    quit(status = 1)
  }
  invisible(NULL)
}

open_quick_view_window <- function() {
  sysname <- Sys.info()[["sysname"]]
  if (identical(sysname, "Windows")) {
    grDevices::windows(width = 9, height = 7)
  } else if (identical(sysname, "Darwin")) {
    grDevices::quartz(width = 9, height = 7)
  } else {
    grDevices::x11(width = 9, height = 7)
  }
}

# Quick View (-q/--qview): the output file is already written when this runs,
# so any problem is reported as a warning and does not change the exit status.
quick_view <- function(path, line_layer, point_layer = NULL) {
  tryCatch({
    lines <- st_read(path, layer = line_layer, quiet = TRUE)
    if (nrow(lines) == 0L) {
      message("WARNING: nothing to show in Quick View (no features written).")
      return(invisible(NULL))
    }
    open_quick_view_window()
    gt <- if ("grid_type" %in% names(lines)) lines$grid_type else rep(NA_character_, nrow(lines))
    col <- ifelse(gt %in% "major", "black", ifelse(gt %in% "minor", "grey60", "grey30"))
    lwd <- ifelse(gt %in% "major", 2, 1)
    plot(st_geometry(lines), col = col, lwd = lwd, axes = TRUE, main = basename(path), reset = FALSE)
    if (!is.null(point_layer)) {
      pts <- st_read(path, layer = point_layer, quiet = TRUE)
      if (nrow(pts) > 0L) plot(st_geometry(pts), add = TRUE, pch = 16, col = "red")
    }
    cat("Quick View window opened (close the window to finish).\n")
    while (grDevices::dev.cur() > 1L) Sys.sleep(0.2)
  }, error = function(e) {
    message(sprintf("WARNING: Quick View failed: %s", conditionMessage(e)))
  })
  invisible(NULL)
}

ply_settings <- function(opts) {
  defaults <- list(origin = c(0, 0, 0), "far-scale" = 3, "offset-distance" = 0,
                   "offset-fraction" = 0, "batch-size" = 200000, "tube-radius" = 0, "tube-segments" = 8)
  settings <- lapply(names(defaults), function(k) {
    x <- suppressWarnings(as.numeric(get_optional(opts, k, defaults[[k]])))
    if (any(!is.finite(x))) stop(sprintf("--%s requires finite numeric values.", k))
    x
  })
  names(settings) <- names(defaults)
  if (!is.null(opts[["offset-distance"]]) && !is.null(opts[["offset-fraction"]])) {
    stop("--offset-distance and --offset-fraction are mutually exclusive.")
  }
  if (settings[["far-scale"]] <= 0) stop("--ray-scale must be > 0.")
  if (settings[["batch-size"]] <= 0 || settings[["batch-size"]] != floor(settings[["batch-size"]])) stop("--ray-batch must be a positive integer.")
  if (settings[["tube-radius"]] < 0) stop("--tube-rad must be >= 0.")
  if (settings[["tube-segments"]] < 3 || settings[["tube-segments"]] != floor(settings[["tube-segments"]])) stop("--tube-seg must be an integer >= 3.")
  rgb <- suppressWarnings(as.numeric(strsplit(get_optional(opts, "color", "255,255,255"), ",", fixed = TRUE)[[1]]))
  if (length(rgb) != 3L || any(!is.finite(rgb)) || any(rgb != floor(rgb) | rgb < 0 | rgb > 255)) stop("--ply-rgb requires three integers in 0..255: R,G,B.")
  settings$color <- rgb
  settings$input_mesh <- get_optional(opts, "input-mesh", NULL)
  if (is.null(settings$input_mesh) || !file.exists(settings$input_mesh) || dir.exists(settings$input_mesh)) {
    stop("PLY output requires an existing --input-mesh/-mesh file.")
  }
  settings
}

metadata_values <- function(record) {
  vapply(record, function(x) {
    if (is.logical(x)) return(paste(tolower(as.character(x)), collapse = " "))
    if (is.numeric(x)) return(paste(sprintf("%.15g", x), collapse = " "))
    paste(x, collapse = " ")
  }, character(1))
}

ply_quote <- function(value) {
  escaped <- vapply(utf8ToInt(enc2utf8(value)), function(x) {
    if (x == 34L) return('\\"')
    if (x == 92L) return('\\\\')
    if (x < 32L) return(sprintf("\\u%04x", x))
    intToUtf8(x)
  }, character(1))
  paste0('"', paste(escaped, collapse = ""), '"')
}

cross3 <- function(a, b) c(a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1])
normalize3 <- function(x) {
  n <- sqrt(sum(x * x))
  if (n == 0) x else x / n
}

ply_tubes <- function(points, polylines, radius, segments) {
  vertices <- faces <- vector("list", length(polylines))
  offset <- 0L
  for (part in seq_along(polylines)) {
    pts <- points[polylines[[part]], , drop = FALSE]
    keep <- c(TRUE, sqrt(rowSums((pts[-1, , drop = FALSE] - pts[-nrow(pts), , drop = FALSE])^2)) > radius * 1e-9)
    pts <- pts[keep, , drop = FALSE]
    if (nrow(pts) < 2L) next
    closed <- sqrt(sum((pts[1, ] - pts[nrow(pts), ])^2)) < radius * 1e-3
    if (closed) pts <- pts[-nrow(pts), , drop = FALSE]
    n <- nrow(pts)
    if (n < 2L) next
    tangents <- matrix(0, n, 3)
    tangents[1, ] <- normalize3(pts[2, ] - pts[1, ])
    tangents[n, ] <- normalize3(pts[n, ] - pts[n - 1L, ])
    if (n > 2L) for (i in 2:(n - 1L)) tangents[i, ] <- normalize3(pts[i + 1L, ] - pts[i - 1L, ])
    normals <- binormals <- matrix(0, n, 3)
    ref <- if (abs(tangents[1, 3]) > 0.9) c(0, 1, 0) else c(0, 0, 1)
    normals[1, ] <- normalize3(cross3(tangents[1, ], ref))
    binormals[1, ] <- normalize3(cross3(tangents[1, ], normals[1, ]))
    for (i in 2:n) {
      normal <- normals[i - 1L, ] - sum(normals[i - 1L, ] * tangents[i, ]) * tangents[i, ]
      if (sqrt(sum(normal^2)) < 1e-12) {
        ref <- if (abs(tangents[i, 3]) > 0.9) c(0, 1, 0) else c(0, 0, 1)
        normal <- cross3(tangents[i, ], ref)
      }
      normals[i, ] <- normalize3(normal)
      binormals[i, ] <- normalize3(cross3(tangents[i, ], normals[i, ]))
    }
    angles <- 2 * pi * (0:(segments - 1L)) / segments
    v <- matrix(0, n * segments + if (closed) 0L else 2L, 3)
    for (i in seq_len(n)) {
      ring <- outer(cos(angles), normals[i, ]) + outer(sin(angles), binormals[i, ])
      v[(i - 1L) * segments + seq_len(segments), ] <- sweep(radius * ring, 2, pts[i, ], "+")
    }
    pairs <- if (closed) n else n - 1L
    f <- matrix(0L, pairs * segments * 2L + if (closed) 0L else 2L * segments, 3)
    cursor <- 0L
    k <- 0:(segments - 1L)
    k2 <- (k + 1L) %% segments
    for (i in seq_len(pairs)) {
      j <- if (i == n) 1L else i + 1L
      a <- offset + (i - 1L) * segments + k
      b <- offset + (i - 1L) * segments + k2
      c <- offset + (j - 1L) * segments + k2
      d <- offset + (j - 1L) * segments + k
      f[cursor + seq_len(2L * segments), ] <- rbind(cbind(a, b, c), cbind(a, c, d))
      cursor <- cursor + 2L * segments
    }
    if (!closed) {
      v[n * segments + 1:2, ] <- pts[c(1, n), , drop = FALSE]
      f[cursor + seq_len(2L * segments), ] <- rbind(
        cbind(offset + n * segments, offset + k2, offset + k),
        cbind(offset + n * segments + 1L, offset + (n - 1L) * segments + k, offset + (n - 1L) * segments + k2))
    }
    vertices[[part]] <- v
    faces[[part]] <- f
    offset <- offset + nrow(v)
  }
  list(vertices = do.call(rbind, vertices), elements = do.call(rbind, faces))
}

write_fitted_ply <- function(output, settings, grid, res, extent, nde, metadata = NULL) {
  if (!requireNamespace("Rvcg", quietly = TRUE)) stop("PLY output requires Rvcg: install.packages('Rvcg') or conda install -c conda-forge r-rvcg.")
  mesh <- Rvcg::vcgImport(settings$input_mesh, updateNormals = FALSE, clean = TRUE, silent = TRUE)
  if (is.null(mesh$it) || ncol(mesh$it) == 0L || any(!is.finite(mesh$vb))) stop("Input mesh has no finite triangular surface.")
  origin <- settings$origin
  radius <- max(sqrt(colSums(sweep(mesh$vb[1:3, , drop = FALSE], 1, origin, "-")^2)))
  if (!is.finite(radius) || radius <= 0) stop("Input mesh radius must be positive.")
  far <- radius * settings[["far-scale"]]
  offset <- settings[["offset-distance"]] + radius * settings[["offset-fraction"]]
  full <- abs(extent[3] - extent[1] - 360) < 1e-9
  lats <- seq_inclusive(extent[4], extent[2], grid[2])
  lons <- seq_inclusive(extent[1], extent[3], grid[1])
  if (nde && full && length(lons) > 1L && abs(tail(lons, 1) - extent[3]) < 1e-9) lons <- head(lons, -1)
  lon_samples <- seq_inclusive(extent[1], extent[3], res[1])
  if (full && abs(tail(lon_samples, 1) - extent[3]) < 1e-9) lon_samples <- head(lon_samples, -1)
  lat_samples <- seq_inclusive(extent[4], extent[2], res[2])
  samples <- c(lapply(lats, function(lat) cbind(lat, lon_samples)),
               lapply(lons, function(lon) cbind(lat_samples, lon)))
  sizes <- vapply(samples, nrow, integer(1))
  end <- cumsum(sizes)
  start <- c(1L, head(end, -1L) + 1L)
  angles <- do.call(rbind, samples) * pi / 180
  directions <- cbind(cos(angles[, 1]) * cos(angles[, 2]), cos(angles[, 1]) * sin(angles[, 2]), sin(angles[, 1]))
  points <- matrix(NA_real_, nrow(directions), 3)
  hit <- rep(FALSE, nrow(directions))
  batch <- settings[["batch-size"]]
  cat(sprintf("[INFO] Rvcg ray intersector; %d faces, %d ray samples\n", ncol(mesh$it), nrow(directions)))
  for (first in seq(1, nrow(directions), by = batch)) {
    ids <- first:min(first + batch - 1L, nrow(directions))
    d <- directions[ids, , drop = FALSE]
    rays <- Rvcg::setRays(sweep(d * far, 2, origin, "+"), -d)
    found <- Rvcg::vcgRaySearch(rays, mesh, maxtol = far + radius, mindist = FALSE)
    valid <- found$quality == 1 & colSums(!is.finite(found$vb[1:3, , drop = FALSE])) == 0
    selected <- ids[valid]
    points[selected, ] <- t(found$vb[1:3, valid, drop = FALSE]) + directions[selected, , drop = FALSE] * offset
    hit[selected] <- TRUE
  }
  polylines <- list()
  for (i in seq_along(samples)) {
    ids <- start[i]:end[i]
    groups <- rle(hit[ids])
    ends <- cumsum(groups$lengths)
    begins <- c(1L, head(ends, -1L) + 1L)
    for (j in which(groups$values & groups$lengths >= 2L)) {
      line <- ids[begins[j]:ends[j]]
      if (i <= length(lats) && full && all(hit[ids])) line <- c(line, line[1])
      polylines[[length(polylines) + 1L]] <- line
    }
  }
  if (length(polylines) == 0L) stop("No fitted edges were generated; the existing output is unchanged.")
  tube <- settings[["tube-radius"]] > 0
  if (tube) {
    geometry <- ply_tubes(points, polylines, settings[["tube-radius"]], settings[["tube-segments"]])
    vertices <- geometry$vertices
    elements <- geometry$elements
    if (is.null(elements) || nrow(elements) == 0L) stop("No tube faces were generated.")
  } else {
    vertices <- points[hit, , drop = FALSE]
    vertex_ids <- rep(NA_integer_, length(hit))
    vertex_ids[hit] <- seq_len(sum(hit)) - 1L
    elements <- do.call(rbind, lapply(polylines, function(line) cbind(vertex_ids[head(line, -1)], vertex_ids[tail(line, -1)])))
  }
  con <- file(output, "wt", encoding = "UTF-8")
  on.exit(close(con), add = TRUE)
  writeLines(c("ply", "format ascii 1.0"), con)
  if (!is.null(metadata)) {
    metadata$mesh_radius <- radius
    metadata$ray_engine <- "Rvcg"
    values <- metadata_values(metadata)
    writeLines(paste0("comment mkgraticule ", names(values), "=", vapply(values, ply_quote, character(1))), con)
  }
  writeLines(c(sprintf("element vertex %d", nrow(vertices)), "property float x", "property float y", "property float z"), con)
  if (tube) {
    writeLines(c("property uchar red", "property uchar green", "property uchar blue", sprintf("element face %d", nrow(elements)), "property list uchar int vertex_indices"), con)
  } else {
    writeLines(c(sprintf("element edge %d", nrow(elements)), "property int vertex1", "property int vertex2", "property uchar red", "property uchar green", "property uchar blue"), con)
  }
  writeLines("end_header", con)
  rgb <- settings$color
  for (i in seq_len(nrow(vertices))) {
    text <- sprintf("%.9f %.9f %.9f", vertices[i, 1], vertices[i, 2], vertices[i, 3])
    writeLines(if (tube) paste(text, paste(rgb, collapse = " ")) else text, con)
  }
  for (i in seq_len(nrow(elements))) {
    text <- paste(elements[i, ], collapse = " ")
    writeLines(if (tube) paste("3", text) else paste(text, paste(rgb, collapse = " ")), con)
  }
  cat(sprintf("Saved PLY vertices: %d; %s: %d; ray hits: %d; ray misses: %d\n", nrow(vertices), if (tube) "faces" else "edges", nrow(elements), sum(hit), sum(!hit)))
}

reproject_grid <- function(grid, crs, skip, partial) {
  previous <- Sys.getenv("OGR_ENABLE_PARTIAL_REPROJECTION", unset = NA_character_)
  on.exit(if (is.na(previous)) Sys.unsetenv("OGR_ENABLE_PARTIAL_REPROJECTION") else Sys.setenv(OGR_ENABLE_PARTIAL_REPROJECTION = previous), add = TRUE)
  Sys.setenv(OGR_ENABLE_PARTIAL_REPROJECTION = if (partial) "TRUE" else "FALSE")
  transformed <- tryCatch(suppressWarnings(st_transform(grid, crs, partial = partial)), error = function(e) {
    if (!skip) stop(e)
    geoms <- lapply(st_geometry(grid), function(geom) {
      tryCatch(suppressWarnings(st_transform(st_sfc(geom, crs = st_crs(grid)), crs, partial = partial))[[1]],
               error = function(e) st_linestring())
    })
    st_set_geometry(grid, st_sfc(geoms, crs = crs))
  })
  failed <- st_is_empty(transformed)
  if (any(failed) && !skip) stop("Some grid lines failed reprojection. Restrict -e or use -skipf/--skipfailures, optionally with -p/--partial-reprojection.")
  if (any(failed)) message(sprintf("WARNING: skipped %d grid lines that failed reprojection.", sum(failed)))
  transformed[!failed, , drop = FALSE]
}

main <- function() {
opts <- parse_args(args)

proj_crs  <- get_optional(opts, "proj-crs", NULL)
out_info  <- resolve_output_format(
  get_required(opts, "outfile"),
  get_optional(opts, "format", NULL)
)
output    <- out_info$outfile
if (!identical(out_info$format, "ply") && (is.null(proj_crs) || !nzchar(trimws(proj_crs)))) {
  stop("-s/-srs/--srs is required for 2D output (GeoPackage/SpatiaLite); specify a CRS code, PROJ/WKT string, or .wkt/.prj file (e.g. -srs IAU_2015:30100 for Moon).")
}
is_gpkg   <- out_info$is_gpkg
layer     <- get_optional(opts, "layer", NULL)
if (is.null(layer)) {
  layer <- "grid"
  point_layer <- "point"
} else {
  point_layer <- paste0(layer, "_point")
}
if (isTRUE(opts[["metadata"]]) && identical(layer, "mkgraticule_metadata")) {
  stop("Layer name 'mkgraticule_metadata' is reserved when --metadata is enabled.")
}

lat_min   <- to_num(get_optional(opts, "lat-min", "-90"),  "--lat-min / -e[4]")
lat_max   <- to_num(get_optional(opts, "lat-max",  "90"),  "--lat-max / -e[2]")
lon_min   <- to_num(get_optional(opts, "lon-min", "-180"), "--lon-min / -e[1]")
lon_max   <- to_num(get_optional(opts, "lon-max",  "180"), "--lon-max / -e[3]")
units     <- get_optional(opts, "units", "degrees")
is_meters <- identical(units, "meters")
# Shared defaults match Python: 5 degrees / 0.1 degrees, or 5000 m / 100 m.
mer_step  <- to_num(get_optional(opts, "meridian-step", if (is_meters) "5000" else "5"), "--meridian-step / -g[1]")
par_step  <- to_num(get_optional(opts, "parallel-step", if (is_meters) "5000" else "5"), "--parallel-step / -g[2]")
vstep_lat <- to_num(get_optional(opts, "vertex-step-lat", if (is_meters) "100" else "0.1"), "--vertex-step-lat / -r[2]")
vstep_lon <- to_num(get_optional(opts, "vertex-step-lon", if (is_meters) "100" else "0.1"), "--vertex-step-lon / -r[1]")

assert_positive(mer_step, "--meridian-step / -g[1]")
assert_positive(par_step, "--parallel-step / -g[2]")
assert_positive(vstep_lat, "--vertex-step-lat / -r[2]")
assert_positive(vstep_lon, "--vertex-step-lon / -r[1]")

major_mer_step <- if (!is.null(opts[["major-meridian-step"]])) to_num(opts[["major-meridian-step"]], "--major / -m[1]") else NULL
major_par_step <- if (!is.null(opts[["major-parallel-step"]])) to_num(opts[["major-parallel-step"]], "--major / -m[2]") else NULL
if (!is.null(major_mer_step)) {
  assert_positive(major_mer_step, "--major / -m[1]")
  xr <- major_mer_step / mer_step
  if (abs(xr - round(xr)) > 1e-9 || round(xr) < 1) {
    stop(sprintf("xmajor must be a natural-number multiple of xstep (got xmajor=%s, xstep=%s).", major_mer_step, mer_step))
  }
}
if (!is.null(major_par_step)) {
  assert_positive(major_par_step, "--major / -m[2]")
  yr <- major_par_step / par_step
  if (abs(yr - round(yr)) > 1e-9 || round(yr) < 1) {
    stop(sprintf("ymajor must be a natural-number multiple of ystep (got ymajor=%s, ystep=%s).", major_par_step, par_step))
  }
}

lat_orig <- if (!is.null(opts[["lat-orig"]])) to_num(opts[["lat-orig"]], "--lat-orig / -lo") else NULL
lat_sp   <- if (!is.null(opts[["lat-sp"]])) to_num(opts[["lat-sp"]], "--lat-sp / -ls") else NULL
lat_sp2  <- if (!is.null(opts[["lat-sp2"]])) to_num(opts[["lat-sp2"]], "--lat-sp2 / -ls2") else NULL
for (nm in c("lat_orig", "lat_sp", "lat_sp2")) {
  val <- get(nm)
  if (!is.null(val) && (val < -90 || val > 90)) {
    stop(sprintf("%s must be within [-90, 90] degrees (got %s).", gsub("_", "-", nm), val))
  }
}

skip <- isTRUE(opts[["skipfailures"]])
partial <- isTRUE(opts[["partial-reprojection"]])
if (identical(out_info$format, "ply")) {
  if (is_meters) stop("-u meters is not supported with PLY output.")
  settings <- ply_settings(opts)
  extent <- c(lon_min, lat_max, lon_max, lat_min)
  grid <- c(mer_step, par_step)
  res <- c(vstep_lon, vstep_lat)
  nde <- isTRUE(opts[["no-duplicate-endpoint"]])
  if (isTRUE(opts[["dry-run"]])) {
    cat(sprintf("Dry run: %s\nFormat: ply; units: degrees\nCoordinates: input mesh coordinates (PLY)\n", output))
    cat(sprintf("Input mesh: %s\nGrid: %s; resolution: %s\n", settings$input_mesh, paste(grid, collapse = " "), paste(res, collapse = " ")))
    cat(sprintf("Extent (xmin ymax xmax ymin): %s\n", paste(extent, collapse = " ")))
    cat("PLY size and fitted geometry are not estimated; mesh loading and ray casting are not performed.\n")
    cat(sprintf("Metadata: %s\n", if (isTRUE(opts[["metadata"]])) "enabled" else "disabled"))
    cat(if (file.exists(output)) "Existing output would be replaced.\n" else "A new output would be created.\n")
    cat("No files were written.\n")
    return(invisible(NULL))
  }
  record <- NULL
  if (isTRUE(opts[["metadata"]])) {
    record <- list(version = VERSION, implementation = "R", created_utc = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
                   command = paste(shQuote(args), collapse = " "), outfile = output, format = "ply", units = "degrees",
                   extent = extent, grid = grid, res = res, no_duplicate_endpoint = nde,
                   input_mesh = settings$input_mesh, origin = settings$origin, far_scale = settings[["far-scale"]],
                   offset_distance = settings[["offset-distance"]], offset_fraction = settings[["offset-fraction"]],
                   batch_size = settings[["batch-size"]], color = settings$color,
                   tube_radius = settings[["tube-radius"]], tube_segments = settings[["tube-segments"]])
  }
  if (isTRUE(opts[["qview"]])) message("WARNING: -q/--qview is not supported with PLY output; ignored.")
  if (isTRUE(opts[["ray-slow"]])) message("NOTE: --ray-slow is not needed by the Rvcg accelerator; ignored.")
  outdir <- dirname(output)
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  staging <- tempfile(pattern = ".mkgraticule-", tmpdir = outdir)
  if (!dir.create(staging)) stop("Cannot create staging directory.")
  on.exit(unlink(staging, recursive = TRUE), add = TRUE)
  staged <- file.path(staging, basename(output))
  write_fitted_ply(staged, settings, grid, res, extent, nde, record)
  if (!file.rename(staged, output)) stop(sprintf("Cannot replace '%s'; the existing output is unchanged. Close applications using it and retry.", output))
  cat(sprintf("Output: %s\n", output))
  return(invisible(NULL))
}

geo_crs <- infer_geo_crs_from_srs(proj_crs)
crs_geo  <- st_crs(geo_crs)
crs_proj <- st_crs(proj_crs)
projected <- !is_geographic_input(proj_crs)
if ((!is.null(lat_orig) || !is.null(lat_sp) || !is.null(lat_sp2)) && !projected) {
  stop("--lat-orig/--lat-sp/--lat-sp2 require a projected target CRS.")
}
applied_overrides <- list()
if (projected && (!is.null(lat_orig) || !is.null(lat_sp) || !is.null(lat_sp2))) {
  ov <- override_projection_latitude_parameters(crs_proj, lat_orig = lat_orig, lat_sp = lat_sp, lat_sp2 = lat_sp2)
  crs_proj <- ov$crs
  applied_overrides <- ov$applied
}
qview <- isTRUE(get_optional(opts, "qview", FALSE))
if (is_meters) {
  check_meters_units(crs_proj, projected)
  extent_keys <- c("lon-min", "lat-max", "lon-max", "lat-min")
  if (any(vapply(extent_keys, function(k) is.null(opts[[k]]), logical(1)))) {
    stop("-u meters requires -e/--extent in projected CRS meters (ulx uly lrx lry).")
  }
  if (lon_min >= lon_max) stop(sprintf("extent requires ulx < lrx (got ulx=%s, lrx=%s).", lon_min, lon_max))
  if (lat_max <= lat_min) stop(sprintf("extent requires uly > lry (got uly=%s, lry=%s).", lat_max, lat_min))
}
method <- regmatches(crs_proj$wkt, regexpr('METHOD\\["[^"]+', crs_proj$wkt))
limited <- length(method) > 0L && grepl("stereographic|orthographic|gnomonic|vertical perspective|azimuthal equidistant", method, ignore.case = TRUE)
global_like <- lon_min <= -170 && lon_max >= 170 && lat_min <= -80 && lat_max >= 80
if (!is_meters && projected && limited && global_like) {
  if (!skip) stop("Projected CRS with near-global extent detected. Restrict -e or use -skipf/--skipfailures, optionally with -p/--partial-reprojection.")
  message("WARNING: near-global extent in a limited-domain projection; some features may be missing.")
}
if (!isTRUE(opts[["dry-run"]])) confirm_output_size(
  is_meters, lon_min, lon_max, lat_min, lat_max, mer_step, par_step, vstep_lon, vstep_lat,
  isTRUE(get_optional(opts, "no-duplicate-endpoint", FALSE)),
  isTRUE(get_optional(opts, "yes", FALSE))
)
term_width <- terminal_width()
center <- if (projected) get_projection_center_lat_lon(crs_proj) else list(lat = NULL, lon = NULL)
if (projected && is.null(center$lon)) center$lon <- 0

outdir <- dirname(output)
if (isTRUE(opts[["dry-run"]])) {
  est <- estimate_grid(is_meters, lon_min, lon_max, lat_min, lat_max,
                       mer_step, par_step, vstep_lon, vstep_lat,
                       isTRUE(opts[["no-duplicate-endpoint"]]))
  if (est$lines == 0) stop("No grid line falls inside the extent.")
  cat(sprintf("Dry run: %s\n", output))
  cat(sprintf("Format: %s; units: %s\n", if (is_gpkg) "gpkg" else "spatialite", units))
  show_wkt(crs_proj)
  cat(sprintf("Extent (xmin ymax xmax ymin): %s\n", paste(c(lon_min, lat_max, lon_max, lat_min), collapse = " ")))
  cat(sprintf("Grid: %s; resolution: %s; major: %s\n",
              paste(c(mer_step, par_step), collapse = " "),
              paste(c(vstep_lon, vstep_lat), collapse = " "),
              paste(c(major_mer_step, major_par_step), collapse = " ")))
  cat(sprintf("Estimated lines: %s; vertices: %s\n", est$lines, est$vertices))
  cat(sprintf("Estimated geometry size: %s (approximate, before reprojection)\n", format_size(est$vertices * BYTES_PER_VERTEX)))
  cat(sprintf("Metadata: %s\n", if (isTRUE(opts[["metadata"]])) "enabled" else "disabled"))
  cat(if (file.exists(output)) "Existing output would be replaced.\n" else "A new output would be created.\n")
  cat("No files were written.\n")
  return(invisible(NULL))
}
if (!identical(outdir, ".") && nzchar(outdir)) {
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
}
final_output <- output
staging <- tempfile(pattern = ".mkgraticule-", tmpdir = outdir)
if (!dir.create(staging)) stop("Cannot create staging directory.")
on.exit(unlink(staging, recursive = TRUE), add = TRUE)
output <- file.path(staging, basename(final_output))

finish_output <- function() {
  saved <- st_read(output, layer = layer, quiet = TRUE)
  empty <- sum(st_is_empty(saved))
  if (nrow(saved) == empty) stop("No non-empty grid lines were saved; the existing output is unchanged.")
  point_count <- if (point_layer %in% st_layers(output)$name) {
    nrow(st_read(output, layer = point_layer, quiet = TRUE))
  } else 0L
  if (isTRUE(opts[["metadata"]])) {
    record <- list(
      version = VERSION, implementation = "R",
      created_utc = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
      command = paste(shQuote(args), collapse = " "),
      outfile = final_output, format = if (is_gpkg) "gpkg" else "spatialite",
      srs = proj_crs, crs_wkt = crs_proj$wkt, units = units,
      extent = c(lon_min, lat_max, lon_max, lat_min), grid = c(mer_step, par_step),
      res = c(vstep_lon, vstep_lat), major = c(major_mer_step, major_par_step),
      override_lat_orig = lat_orig, override_lat_sp = lat_sp, override_lat_sp2 = lat_sp2, layer = layer,
      no_duplicate_endpoint = !is_meters && isTRUE(opts[["no-duplicate-endpoint"]])
    )
    params <- extract_wkt_parameters(crs_proj$wkt)
    if (length(params) > 0L) {
      record <- c(record, setNames(params, paste0("crs_parameter_", names(params))))
    }
    if (!is_meters) record <- c(record, list(skipfailures = skip, partial_reprojection = partial))
    values <- metadata_values(record)
    con <- dbConnect(SQLite(), output)
    tryCatch({
      dbExecute(con, "CREATE TABLE mkgraticule_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
      dbAppendTable(con, "mkgraticule_metadata", data.frame(key = names(values), value = unname(values)))
    }, finally = dbDisconnect(con))
  }
  if (any(file.exists(paste0(final_output, c("-wal", "-shm", "-journal"))))) {
    stop("Output has SQLite journal files; close applications using it before retrying.")
  }
  if (!file.rename(output, final_output)) {
    stop(sprintf("Cannot replace '%s'; the existing output is unchanged. Close applications using it and retry.", final_output))
  }
  cat(sprintf("Output: %s\n", final_output))
  if (is_meters) {
    cat(sprintf("Saved Northing (y) lines: %d\n", sum(!is.na(saved$y))))
    cat(sprintf("Saved Easting (x) lines: %d\n", sum(!is.na(saved$x))))
  } else {
    cat(sprintf("Saved latitude lines: %d\n", sum(!is.na(saved$lat))))
    cat(sprintf("Saved longitude lines: %d\n", sum(!is.na(saved$lon))))
  }
  cat(sprintf("Saved line features: %d (empty: %d)\n", nrow(saved), empty))
  cat(sprintf("Saved point features: %d\n", point_count))
  if (qview) quick_view(final_output, layer, if (point_count > 0L) point_layer else NULL)
}

if (identical(units, "meters")) {
  if (isTRUE(get_optional(opts, "no-duplicate-endpoint", FALSE))) {
    message("NOTE: -nde ignored with -u meters (no reprojection is performed).")
  }
  if (skip || partial) message("NOTE: -skipf/-p ignored with -u meters (no reprojection is performed).")

  xs <- meter_ticks(lon_min, lon_max, mer_step)
  ys <- meter_ticks(lat_min, lat_max, par_step)
  if (length(xs) == 0L && length(ys) == 0L) {
    stop(sprintf(
      "No grid line falls inside the extent (x: %s..%s, y: %s..%s) for the grid size (%s, %s) m.",
      lon_min, lon_max, lat_min, lat_max, mer_step, par_step
    ))
  }

  x_samples <- meter_samples(lon_min, lon_max, vstep_lon)
  y_samples <- meter_samples(lat_min, lat_max, vstep_lat)

  print_separator(term_width)
  show_wkt(crs_proj)
  print_separator(term_width)

  line_rows <- vector("list", length(ys) + length(xs))
  line_geoms <- vector("list", length(ys) + length(xs))
  row <- 1L

  for (i in seq_along(ys)) {
    progress_bar(i, length(ys), "Processing Northings: ")
    y <- ys[i]
    line_rows[[row]] <- data.frame(
      row_no = row,
      x = NA_real_,
      y = y,
      grid_type = if (is.null(major_par_step)) NA_character_ else if (is_multiple(y, major_par_step)) "major" else "minor",
      stringsAsFactors = FALSE
    )
    line_geoms[[row]] <- st_linestring(cbind(x_samples, rep(y, length(x_samples))))
    row <- row + 1L
  }
  cat("\n")

  for (i in seq_along(xs)) {
    progress_bar(i, length(xs), "Processing Eastings: ")
    x <- xs[i]
    line_rows[[row]] <- data.frame(
      row_no = row,
      x = x,
      y = NA_real_,
      grid_type = if (is.null(major_mer_step)) NA_character_ else if (is_multiple(x, major_mer_step)) "major" else "minor",
      stringsAsFactors = FALSE
    )
    line_geoms[[row]] <- st_linestring(cbind(rep(x, length(y_samples)), y_samples))
    row <- row + 1L
  }
  cat("\n")

  grid_m <- st_sf(
    do.call(rbind, line_rows),
    geometry = st_sfc(line_geoms, crs = crs_proj)
  )

  print_separator(term_width)
  cat(sprintf("Meter grid (no reprojection): %s\n\n", authority_label(proj_crs)))

  if (is_gpkg) {
    suppressWarnings(st_write(grid_m, output, layer = layer, delete_layer = TRUE, quiet = TRUE))
  } else {
    suppressWarnings(st_write(grid_m, output, layer = layer,
                              driver = "SQLite", dataset_options = "SPATIALITE=YES",
                              layer_options = "SPATIAL_INDEX=YES",
                              delete_layer = TRUE, quiet = TRUE))
  }

  if (is_gpkg) {
    if (length(applied_overrides) > 0L) {
      cat("WARN: CRS parameter overrides were applied; skip gpkg_spatial_ref_sys.definition_12_063 update.\n")
    } else {
      fix_gpkg_crs_wkt(output, proj_crs)
    }
  }

  print_separator(term_width)
  finish_output()
  return(invisible(NULL))
}

meridians <- seq_inclusive(lon_min, lon_max, mer_step)
parallels <- seq_inclusive(lat_min, lat_max, par_step)

if (isTRUE(get_optional(opts, "no-duplicate-endpoint", FALSE))) {
  span <- lon_max - lon_min
  spans_full_360 <- abs(span - 360.0) < 1e-9
  if (spans_full_360 && length(meridians) > 1L) {
    if (abs(meridians[1] - lon_min) < 1e-9 && abs(meridians[length(meridians)] - lon_max) < 1e-9) {
      meridians <- meridians[-length(meridians)]
    }
  }
}

print_separator(term_width)
show_wkt(crs_geo)
print_separator(term_width)

line_rows <- list()
line_geoms <- list()
point_rows <- list()
point_geoms <- list()
row <- 1L

for (i in seq_along(parallels)) {
  progress_bar(i, length(parallels), "Processing Latitudes: ")
  lat <- parallels[i]

  lon_samples <- seq_inclusive(lon_min, lon_max, vstep_lon)
  sample_coords <- cbind(lon_samples, rep(lat, length(lon_samples)))

  is_collapsed <- FALSE
  collapsed_xy <- NULL
  if (projected) {
    collapse <- collapsed_target_point(sample_coords, crs_geo, crs_proj)
    is_collapsed <- isTRUE(collapse$is_collapsed)
    collapsed_xy <- collapse$xy
  }

  if (
    projected && !is_collapsed &&
    !is.null(center$lat) && !is.null(center$lon) &&
    abs(abs(center$lat) - 90) <= 1e-9 &&
    abs(lat - center$lat) <= 1e-9
  ) {
    pole_xy <- transform_point_safe(center$lon, center$lat, crs_geo, crs_proj)
    if (!is.null(pole_xy)) {
      is_collapsed <- TRUE
      collapsed_xy <- pole_xy
    }
  }

  if (projected && is_collapsed && !is.null(collapsed_xy)) {
    point_rows[[length(point_rows) + 1L]] <- new_parallel_point_row(row, lat, "collapsed")
    point_geoms[[length(point_geoms) + 1L]] <- st_point(collapsed_xy)
    row <- row + 1L
    next
  }

  line_rows[[length(line_rows) + 1L]] <- new_parallel_line_row(
    row, lat,
    if (is.null(major_par_step)) NA_character_ else if (is_multiple(lat, major_par_step)) "major" else "minor"
  )
  line_geoms[[length(line_geoms) + 1L]] <- make_parallel(lat, lon_min, lon_max, vstep_lon)
  row <- row + 1L
}
cat("\n")

for (i in seq_along(meridians)) {
  progress_bar(i, length(meridians), "Processing Longitudes: ")
  lon <- meridians[i]

  lat_samples <- seq_inclusive(lat_min, lat_max, vstep_lat)
  sample_coords <- cbind(rep(lon, length(lat_samples)), lat_samples)

  is_collapsed <- FALSE
  collapsed_xy <- NULL
  if (projected) {
    collapse <- collapsed_target_point(sample_coords, crs_geo, crs_proj)
    is_collapsed <- isTRUE(collapse$is_collapsed)
    collapsed_xy <- collapse$xy
  }

  if (projected && is_collapsed && !is.null(collapsed_xy)) {
    point_rows[[length(point_rows) + 1L]] <- new_meridian_point_row(row, lon, "collapsed")
    point_geoms[[length(point_geoms) + 1L]] <- st_point(collapsed_xy)
    row <- row + 1L
    next
  }

  line_rows[[length(line_rows) + 1L]] <- new_meridian_line_row(
    row, lon,
    if (is.null(major_mer_step)) NA_character_ else if (is_multiple(lon, major_mer_step)) "major" else "minor"
  )
  line_geoms[[length(line_geoms) + 1L]] <- make_meridian(lon, lat_min, lat_max, vstep_lat)
  row <- row + 1L
}
cat("\n")

if (projected && !is.null(center$lat) && !is.null(center$lon)) {
  center_xy <- transform_point_safe(center$lon, center$lat, crs_geo, crs_proj)

  if (is.null(center_xy) && length(point_rows) > 0L && length(point_geoms) > 0L) {
    for (j in seq_along(point_rows)) {
      prow <- point_rows[[j]]
      if (!is.null(prow$point_role) && identical(as.character(prow$point_role[[1]]), "collapsed")) {
        plat <- suppressWarnings(as.numeric(prow$lat[[1]]))
        plon <- suppressWarnings(as.numeric(prow$lon[[1]]))
        same_pole_lat <- !is.na(plat) && abs(plat - center$lat) <= 1e-9 && abs(abs(center$lat) - 90) <= 1e-9
        same_center_lon <- !is.na(plon) && abs(plon - center$lon) <= 1e-9
        if (same_pole_lat || same_center_lon) {
          center_xy <- st_coordinates(st_sfc(point_geoms[[j]], crs = crs_proj))[1, c("X", "Y")]
          break
        }
      }
    }
  }

  if (!is.null(center_xy) && all(is.finite(center_xy))) {
    is_pole <- !is.null(center$lat) && abs(abs(center$lat) - 90) <= 1e-9
    center_lon_val <- if (is_pole) NULL else center$lon
    point_rows[[length(point_rows) + 1L]] <- new_center_point_row(center$lat, center_lon_val)
    point_geoms[[length(point_geoms) + 1L]] <- st_point(as.numeric(center_xy))
  }
}

if (length(line_rows) == 0L) {
  stop("No line features were generated.")
}

grat_ll <- st_sf(
  do.call(rbind, line_rows),
  geometry = st_sfc(line_geoms, crs = crs_geo)
)

print_separator(term_width)
if (projected) {
  target_label <- if (length(applied_overrides) > 0L) "custom CRS" else authority_label(proj_crs)
  cat(sprintf(
    "Reprojection (on export): %s => %s\n\n",
    authority_label(geo_crs),
    target_label
  ))
  if (length(applied_overrides) > 0L) {
    override_parts <- character(0)
    if (!is.null(lat_orig)) override_parts <- c(override_parts, sprintf("lat_orig=%s", lat_orig))
    if (!is.null(lat_sp)) override_parts <- c(override_parts, sprintf("lat_sp=%s", lat_sp))
    if (!is.null(lat_sp2)) override_parts <- c(override_parts, sprintf("lat_sp2=%s", lat_sp2))
    cat(sprintf("Projection parameter overrides: %s\n\n", paste(override_parts, collapse = ", ")))
  }
  show_wkt(crs_proj)
  grat_out <- reproject_grid(grat_ll, crs_proj, skip, partial)
} else {
  cat(sprintf("Export (no reprojection): %s\n\n", authority_label(proj_crs)))
  grat_out <- grat_ll
}

if (is_gpkg) {
  suppressWarnings(st_write(grat_out, output, layer = layer, delete_layer = TRUE, quiet = TRUE))
} else {
  suppressWarnings(st_write(grat_out, output, layer = layer,
                            driver = "SQLite", dataset_options = "SPATIALITE=YES",
                            layer_options = "SPATIAL_INDEX=YES",
                            delete_layer = TRUE, quiet = TRUE))
}

point_count <- 0L
if (length(point_rows) > 0L) {
  point_sf <- st_sf(
    do.call(rbind, point_rows),
    geometry = st_sfc(point_geoms, crs = crs_proj)
  )
  point_count <- nrow(point_sf)
  if (is_gpkg) {
    suppressWarnings(st_write(point_sf, output, layer = point_layer, delete_layer = TRUE, quiet = TRUE))
  } else {
    suppressWarnings(st_write(point_sf, output, layer = point_layer,
                              driver = "SQLite",
                              layer_options = "SPATIAL_INDEX=YES",
                              delete_layer = TRUE, quiet = TRUE))
  }
}

if (is_gpkg) {
  if (length(applied_overrides) > 0L) {
    cat("WARN: CRS parameter overrides were applied; skip gpkg_spatial_ref_sys.definition_12_063 update.\n")
  } else {
    fix_gpkg_crs_wkt(output, proj_crs)
  }
}

finish_output()
}

main()

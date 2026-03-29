#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(DBI)
  library(RSQLite)
})

VERSION <- "0.4.3"
args <- commandArgs(trailingOnly = TRUE)

usage <- function(status = 0) {
  cat(paste0(
    "mkgraticule_planet.R\n",
    "Create planetary-scale graticules with multi-format labels for any GDAL/PROJ-supported CRS — exported as QGIS-friendly GeoPackage.\n\n",
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
    "Options:\n",
    "  -h, --help\n",
    "      Show this help message and exit.\n",
    "  -v, --version\n",
    "      Show version and exit.\n",
    "  -srs, --srs SRS\n",
    "      Set target spatial reference (IAU code or *.prj file).\n",
    "      See https://spatialreference.org/\n",
    "  -e, --extent ulx uly lrx lry\n",
    "      Set a spatial extent of the output file\n",
    "      Maps to: lon-min lat-max lon-max lat-min\n",
    "      Requires ulx < lrx and uly > lry.\n",
    "      Default: -180 90 180 -90 (global)\n",
    "      Legacy aliases: --lon-min --lat-max --lon-max --lat-min\n",
    "  -g, --grid xstep ystep\n",
    "      Set grid size [xstep ystep] in degrees\n",
    "      xstep = meridian interval, ystep = parallel interval\n",
    "      Legacy aliases: --meridian-step --parallel-step\n",
    "  -r, --res xres yres\n",
    "      Set resolution to polygonize grids [xres yres] in degrees\n",
    "      xres = longitude sampling for parallels\n",
    "      yres = latitude sampling for meridians\n",
    "      Legacy aliases: --vertex-step-lon --vertex-step-lat\n",
    "  -m, --major xmajor ymajor\n",
    "      Major graticule interval [xmajor ymajor] in degrees.\n",
    "      If set, grid_type will be 'major' or 'minor'.\n",
    "      If omitted, grid_type is NULL.\n",
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
    "      Overwrite the 2nd standard parallel in the target projected CRS (degrees).\n"
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

    if (key %in% c("-srs", "--srs")) {
      vals <- expect_n_values(args, i, 1, key)
      res[["proj-crs"]] <- vals[1]
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
    stop("Missing required argument: outfile")
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
  paste0(deg_text(v), "°E")
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

  id_pat <- 'ID\\["([^"]+)",\\s*([0-9]+)(?:\\s*,\\s*([0-9]+))?\\]'
  id_hits <- gregexpr(id_pat, txt, perl = TRUE)
  id_vals <- regmatches(txt, id_hits)[[1]]
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

opts <- parse_args(args)

proj_crs  <- get_optional(opts, "proj-crs", "IAU_2015:30100")
geo_crs   <- infer_geo_crs_from_srs(proj_crs)
output    <- normalize_outfile(get_required(opts, "outfile"))
layer     <- get_optional(opts, "layer", NULL)
if (is.null(layer)) {
  layer <- "grid"
  point_layer <- "point"
} else {
  point_layer <- paste0(layer, "_point")
}

lat_min   <- to_num(get_optional(opts, "lat-min", "-90"),  "--lat-min / -e[4]")
lat_max   <- to_num(get_optional(opts, "lat-max",  "90"),  "--lat-max / -e[2]")
lon_min   <- to_num(get_optional(opts, "lon-min", "-180"), "--lon-min / -e[1]")
lon_max   <- to_num(get_optional(opts, "lon-max",  "180"), "--lon-max / -e[3]")
mer_step  <- to_num(get_required(opts, "meridian-step"), "--meridian-step / -g[1]")
par_step  <- to_num(get_required(opts, "parallel-step"), "--parallel-step / -g[2]")
vstep_lat <- to_num(get_optional(opts, "vertex-step-lat", "0.1"), "--vertex-step-lat / -r[2]")
vstep_lon <- to_num(get_optional(opts, "vertex-step-lon", "0.5"), "--vertex-step-lon / -r[1]")

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
term_width <- terminal_width()
center <- if (projected) get_projection_center_lat_lon(crs_proj) else list(lat = NULL, lon = NULL)
if (projected && is.null(center$lon)) center$lon <- 0

outdir <- dirname(output)
if (!identical(outdir, ".") && nzchar(outdir)) {
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
}
if (file.exists(output)) {
  unlink(output)
  if (file.exists(output)) {
    stop(sprintf("Cannot overwrite '%s'. It may be open in QGIS.", output))
  }
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
  grat_out <- st_transform(grat_ll, crs_proj)
} else {
  cat(sprintf("Export (no reprojection): %s\n\n", authority_label(proj_crs)))
  grat_out <- grat_ll
}

suppressWarnings(st_write(grat_out, output, layer = layer, delete_layer = TRUE, quiet = TRUE))

point_count <- 0L
if (length(point_rows) > 0L) {
  point_sf <- st_sf(
    do.call(rbind, point_rows),
    geometry = st_sfc(point_geoms, crs = crs_proj)
  )
  point_count <- nrow(point_sf)
  suppressWarnings(st_write(point_sf, output, layer = point_layer, delete_layer = TRUE, quiet = TRUE))
}

if (length(applied_overrides) > 0L) {
  cat("WARN: CRS parameter overrides were applied; skip gpkg_spatial_ref_sys.definition_12_063 update.\n")
} else {
  fix_gpkg_crs_wkt(output, proj_crs)
}

cat(sprintf("Output: %s\n", output))
cat(sprintf("Lat grids: %d\n", length(parallels)))
cat(sprintf("Lon grids: %2d\n", length(meridians)))
cat(sprintf("Points: %d\n", point_count))

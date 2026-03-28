#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Standalone wrapper -- delegates to the installed package."""

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Ryodo Hemmi

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mkgraticule_planet._cli import main

main()

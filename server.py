#!/usr/bin/env python3
"""Atalho para rodar do clone: o código fica no pacote token_usage (`python3 -m token_usage`)."""
import sys

from token_usage.cli import main

main(["serve", *sys.argv[1:]])

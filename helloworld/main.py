"""
Template for aio http service

Here is a long description.
Multi-lined, etc..
"""
import argparse
import sys

from . import SERVICE_NAME


def main():
    parser = argparse.ArgumentParser(
                prog=SERVICE_NAME, description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter,
             )
    args = parser.parse_args()

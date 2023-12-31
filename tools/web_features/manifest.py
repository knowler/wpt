#!/usr/bin/env python3

import argparse
import logging
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Set

from ..manifest.item import SupportFile
from ..manifest.sourcefile import SourceFile
from ..metadata.yaml.load import load_data_to_dict
from ..web_features.web_feature_map import WebFeatureToTestsDirMapper, WebFeaturesMap
from .. import localpaths
from ..metadata.webfeatures.schema import WEB_FEATURES_YML_FILENAME, WebFeaturesFile


logger = logging.getLogger(__name__)

MANIFEST_FILE_NAME = "WEB_FEATURES_MANIFEST.json"

def create_parser() -> argparse.ArgumentParser:
    """
    Creates an argument parser for the script.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Maps tests to web features within a repo root."
    )
    parser.add_argument("--repo-root", type=str,
                        help="The WPT directory. Use this "
                        "option if the script exists outside the repository")
    return parser


def find_all_test_files_in_dir(root_dir: str, rel_dir_path: str) -> List[SourceFile]:
    """
    Finds all test files within a given directory.

    Ignores any SourceFiles that are marked as non_test or the type
    is SupportFile.item_type

    Args:
        root_dir (str): The root directory of the repository.
        rel_dir_path (str): The relative path of the directory to search.

    Returns:
        List[SourceFile]: A list of SourceFile objects representing the found test files.
    """
    rv: List[SourceFile] = []
    full_dir_path = os.path.join(root_dir, rel_dir_path)
    for file in os.listdir(full_dir_path):
        full_path = os.path.join(full_dir_path, file)
        rel_file_path = os.path.relpath(full_path, root_dir)
        source_file = SourceFile(root_dir, rel_file_path, "/")
        if not source_file.name_is_non_test and source_file.type != SupportFile.item_type:
            rv.append(source_file)
    return rv

@dataclass
class CmdConfig():
    """
    Configuration for the command-line options.
    """

    repo_root: str  # The root directory of the WPT repository


def map_tests_to_web_features(
        cmd_cfg: CmdConfig,
        rel_dir_path: str,
        result: WebFeaturesMap,
        visited_dirs: Set[str] = set(),
        prev_inherited_features: List[str] = []) -> None:
    """
    Recursively maps tests to web features within a directory structure.

    Args:
        cmd_cfg (CmdConfig): The configuration for the command-line options.
        rel_dir_path (str): The relative path of the directory to process.
        result (WebFeaturesMap): The object to store the mapping results.
        visited_dirs (Set[str], optional): A set of directories that have already been processed. Defaults to set().
        prev_inherited_features (List[str], optional): A list of inherited web features from parent directories. Defaults to [].
    """
    for current_dir, sub_dirs, _ in os.walk(os.path.join(cmd_cfg.repo_root, rel_dir_path)):
        # Sometimes it will add a . at the beginning. Let's resolve the absolute path to disambiguate.
        current_dir = Path(current_dir).resolve().__str__()

        # Skip if we already visited this directory
        if current_dir in visited_dirs:
            continue
        visited_dirs.add(current_dir)

        # Create a copy that may be built upon or cleared during this iteration.
        inherited_features = prev_inherited_features.copy()

        rel_dir_path = os.path.relpath(current_dir, cmd_cfg.repo_root)

        web_feature_yml_full_path = os.path.join(current_dir, WEB_FEATURES_YML_FILENAME)
        web_feature_file: Optional[WebFeaturesFile] = None
        if os.path.isfile(web_feature_yml_full_path):
            try:
                web_feature_file = WebFeaturesFile(load_data_to_dict(
                    open(web_feature_yml_full_path, "rb")))
            except Exception as e:
                raise e

        WebFeatureToTestsDirMapper(
            find_all_test_files_in_dir(cmd_cfg.repo_root, rel_dir_path),
            web_feature_file
        ).run(result, inherited_features)


        for sub_dir in sub_dirs:
            map_tests_to_web_features(
                cmd_cfg,
                os.path.join(rel_dir_path, sub_dir),
                result,
                visited_dirs,
                inherited_features
            )

def main(venv: Any = None, **kwargs: Any) -> int:

    assert logger is not None

    repo_root = kwargs.get('repo_root') or localpaths.repo_root

    cmd_cfg = CmdConfig(repo_root)
    feature_map = WebFeaturesMap()
    map_tests_to_web_features(cmd_cfg, "", feature_map)
    with open(os.path.join(cmd_cfg.repo_root, MANIFEST_FILE_NAME), "w") as outfile:
        outfile.write(feature_map.to_json())

    return 0

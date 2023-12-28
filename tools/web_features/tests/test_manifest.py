# mypy: allow-untyped-defs

import os
from unittest.mock import ANY, Mock, call, mock_open, patch

from ..manifest import create_parser, find_all_test_files_in_dir, main, map_tests_to_web_features, CmdConfig
from ..web_feature_map import WebFeatureToTestsDirMapper, WebFeaturesMap
from ...metadata.webfeatures.schema import WEB_FEATURES_YML_FILENAME
from ...manifest.sourcefile import SourceFile
from ...manifest.item import SupportFile


@patch("os.listdir")
@patch("tools.web_features.manifest.SourceFile")
def test_find_all_test_files_in_dir(mock_source_file_class, mock_listdir):
    mock_listdir.return_value = ["test1.html", "support.py", "test2.html", "test3.html"]

    def create_source_file_mock(root_dir, rel_file_path, separator):
        source_file = Mock(spec=SourceFile)
        if rel_file_path.endswith("support.py"):
            source_file.name_is_non_test = True
            source_file.type = SupportFile.item_type
        else:
            source_file.name_is_non_test = False
        return source_file

    mock_source_file_class.side_effect = create_source_file_mock

    test_files = find_all_test_files_in_dir("root_dir", "rel_dir_path")

    # Assert calls to the mocked constructor with expected arguments
    mock_source_file_class.assert_has_calls([
        call("root_dir", os.path.join("rel_dir_path", "test1.html"), "/"),
        call("root_dir", os.path.join("rel_dir_path", "support.py"), "/"),
        call("root_dir", os.path.join("rel_dir_path", "test2.html"), "/"),
        call("root_dir", os.path.join("rel_dir_path", "test3.html"), "/"),
    ])
    assert mock_source_file_class.call_count == 4


    # Assert attributes of the resulting test files
    assert all(
        not file.name_is_non_test and file.type != SupportFile.item_type
        for file in test_files
    )

    # Should only have 3 items instead of the original 4
    assert len(test_files) == 3

@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("os.walk")
@patch("os.path.isfile")
@patch("tools.web_features.manifest.load_data_to_dict", return_value={})
@patch("tools.web_features.manifest.find_all_test_files_in_dir")
@patch("tools.web_features.manifest.WebFeaturesFile")
@patch("tools.web_features.manifest.WebFeatureToTestsDirMapper", spec=WebFeatureToTestsDirMapper)
def test_map_tests_to_web_features_recursive(
    mock_mapper,
    mock_web_features_file,
    mock_find_all_test_files_in_dir,
    mock_load_data_to_dict,
    mock_isfile,
    mock_walk,
    mock_file
):
    # Mock a directory structure with subdirectories
    mock_walk.return_value = [
        ("repo_root", ["subdir1", "subdir2"], []),
        (os.path.join("repo_root", "subdir1"), ["subdir1_1", "subdir1_2"], [WEB_FEATURES_YML_FILENAME]),
        (os.path.join("repo_root", "subdir1", "subdir1_1"), [], [WEB_FEATURES_YML_FILENAME]),
        (os.path.join("repo_root", "subdir1", "subdir1_2"), [], []),
        (os.path.join("repo_root", "subdir2"), [], [WEB_FEATURES_YML_FILENAME]),
    ]

    def fake_isfile(path):
        if (path.endswith(os.path.join("repo_root", "subdir1", "WEB_FEATURES.yml")) or
        path.endswith(os.path.join("repo_root", "subdir1", "subdir1_1", "WEB_FEATURES.yml")) or
        path.endswith(os.path.join("repo_root", "subdir2", "WEB_FEATURES.yml"))):
            return True
        return False
    mock_isfile.side_effect = fake_isfile


    expected_root_files = [
        Mock(name="root_test_1"),
    ]

    expected_subdir1_files = [
        Mock(name="subdir1_test_1"),
        Mock(name="subdir1_test_2"),
    ]

    expected_subdir2_files = [
        Mock(name="subdir2_test_1"),
    ]

    expected_subdir1_1_files = [
        Mock(name="subdir1_1_test_1"),
        Mock(name="subdir1_1_test_2"),
    ]

    expected_subdir1_2_files = [
        Mock(name="subdir1_2_test_1"),
        Mock(name="subdir1_2_test_2"),
    ]

    expected_subdir1_web_feature_file = Mock()
    expected_subdir1_1_web_feature_file = Mock()
    expected_subdir2_web_feature_file = Mock()
    mock_web_features_file.side_effect = [
        expected_subdir1_web_feature_file,
        expected_subdir1_1_web_feature_file,
        expected_subdir2_web_feature_file,
    ]

    def fake_find_all_test_files_in_dir(root, rel_path):
        if (root == "repo_root" and rel_path == "."):
            return expected_root_files
        elif (root == "repo_root" and rel_path == "subdir1"):
            return expected_subdir1_files
        elif (root == "repo_root" and rel_path == os.path.join("subdir1", "subdir1_1")):
            return expected_subdir1_1_files
        elif (root == "repo_root" and rel_path == os.path.join("subdir1", "subdir1_2")):
            return expected_subdir1_2_files
        elif (root == "repo_root" and rel_path == "subdir2"):
            return expected_subdir2_files
    mock_find_all_test_files_in_dir.side_effect = fake_find_all_test_files_in_dir
    cmd_cfg = CmdConfig("repo_root")
    result = WebFeaturesMap()

    map_tests_to_web_features(cmd_cfg, "", result)

    assert mock_isfile.call_count == 5
    assert mock_mapper.call_count == 5

    # Check for the constructor calls.
    # In between also assert that the run() call is executed.
    mock_mapper.assert_has_calls([
        call(expected_root_files, None),
        call().run(ANY, []),
        call(expected_subdir1_files, expected_subdir1_web_feature_file),
        call().run(ANY, []),
        call(expected_subdir1_1_files, expected_subdir1_1_web_feature_file),
        call().run(ANY, []),
        call(expected_subdir1_2_files, None),
        call().run(ANY, []),
        call(expected_subdir2_files, expected_subdir2_web_feature_file),
        call().run(ANY, []),
    ])


    # Only five times to the constructor
    assert mock_mapper.call_count == 5

def test_parser_with_repo_root():
    parser = create_parser()
    args = parser.parse_args(["--repo-root", "/path/to/repo"])
    assert args.repo_root == "/path/to/repo"


@patch("builtins.open", new_callable=mock_open)
@patch("tools.web_features.manifest.map_tests_to_web_features")
def test_main(mock_map_tests_to_web_features, mock_file):

    def fake_map_tests_to_web_features(
            cmd_cfg,
            rel_dir_path,
            result,
            visited_dirs = set(),
            prev_inherited_features = []):
        result.add("grid", [Mock(path="grid_test1.js"), Mock(path="grid_test2.js")])
        result.add("avif", [Mock(path="avif_test1.js")])

    mock_map_tests_to_web_features.side_effect = fake_map_tests_to_web_features
    main(repo_root=os.path.join(os.sep, "test_repo_root"))
    mock_map_tests_to_web_features.assert_called_once_with(CmdConfig(os.path.join(os.sep, "test_repo_root")), "", ANY)
    mock_file.assert_called_once_with(os.path.join(os.sep, "test_repo_root", "WEB_FEATURES_MANIFEST.json"), "w")
    mock_file.return_value.write.assert_called_once_with('{"grid": ["grid_test1.js", "grid_test2.js"], "avif": ["avif_test1.js"]}')

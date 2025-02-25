import gc
import json
import pickle
import numpy as np
import fnmatch
import logging
from pathlib import Path

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def filter_db_json_data(json_data, filters):
    """
    Filter QA data dictionary based on arbitrary functions.

    Parameters
    ----------
    json_data : dict
        A dictionary of QA data, where each key represents a test name
        and each value is another dictionary containing all data
        related to that test.
    filters : list of callables
        A list of functions that take a test data dictionary as argument.
        A test is included in the output only if all filters evaluate to True.
    Returns
    -------
    dict
        A filtered dictionary of QA data, where each key represents a test name
        and each value is another dictionary containing all data
        related to that test.
    """
    return {
        test_name: test_data
        for test_name, test_data in json_data.items()
        if all(data_filter(test_data) for data_filter in filters)
    }


def filter_db_json_metadata(json_data, filters):
    """
    Filter QA data dictionary based on metadata key-value pairs.

    Parameters
    ----------
    json_data : dict
        A dictionary of QA data, where each key represents a test name
        and each value is another dictionary containing all data
        related to that test.
    filters : list of tuple
        A list of tuples where each tuple consists of a key and an expected
        value to filter the metadata by. If a key-value pair doesn't match
        or the key doesn't exist, the test is excluded from the filtered data.

    Returns
    -------
    filtered_data : dict
        A dictionary containing only the tests that match the specified
        key-value pairs in their metadata.
    """
    filtered_data = {}
    for test_name, test_data in json_data.items():
        metadata = test_data["Metadata"]
        if all(
            metadata.get(key, None) == expected_value for key, expected_value in filters
        ):
            filtered_data[test_name] = test_data

    return filtered_data


def show_metadata(json_data, metadata_name):
    """Return a set of metadata values for all tests."""
    return {test["Metadata"].get(metadata_name, None) for test in json_data.values()}


def browse_db_json_data(json_file_path, filter_list, metadata_keys, show_values=False):
    """
    Print metadata values for each test in a QA data JSON file.

    Parameters
    ----------
    json_file_path : str
        Path to the QA data JSON file.
    filter_list : list
        List of tuples, where each tuple contains a key and a value
        to filter the data by. If any of the key-value pairs do not
        match, the test is not included in the filtered data.
    metadata_keys : list
        List of keys to include in the metadata printout.

    Returns
    -------
    None
    """
    with open(Path(json_file_path), "r") as file:
        qa_data = json.load(file)

    if filter_list:
        filtered_data = filter_db_json_data_metadata(qa_data, filter_list)
    else:
        filtered_data = qa_data

    if not metadata_keys:
        metadata_keys = list(
            filtered_data[list(filtered_data.keys())[0]]["Metadata"].keys()
        )

    if show_values:
        metadata_values = {
            key: show_metadata(filtered_data, key) for key in metadata_keys
        }
        for key, values in metadata_values.items():
            print(f"'{key}': {values}")
    else:
        allmeta = "\n".join(metadata_keys)
        print(f"List of metadata \n{allmeta}")


def parse_filter_list(filter_list_str):
    """Parse a string of filter key-value pairs into a list of tuples."""
    filter_list = []
    for pair in filter_list_str.split(","):
        key, value = pair.split("=")
        filter_list.append((key.strip(), value.strip()))
    return filter_list


def main():
    """
    example:
        python browse_qa_data.py path/to/data.json --filter "Institute=CNM,DeviceType=MD8" --metadata "Fluence,DeviceType"
    """
    import argparse

    parser = argparse.ArgumentParser(description="Browse QA data JSON file")
    parser.add_argument("json_file_path", help="Path to the QA data JSON file")
    parser.add_argument(
        "--filter", help="Filter key-value pairs (e.g. 'Institute=CNM,DeviceType=MD8')"
    )
    parser.add_argument(
        "--metadata",
        help="Metadata keys to include in the printout (e.g. 'Fluence,DeviceType')",
    )
    parser.add_argument(
        "--show-values", action="store_true", help="Show the values of the metadata"
    )

    args = parser.parse_args()

    if args.filter:
        filter_list = parse_filter_list(args.filter)
    else:
        filter_list = []

    if args.metadata:
        metadata_keys = args.metadata.split(",")
    else:
        metadata_keys = []

    browse_db_json_data(
        args.json_file_path, filter_list, metadata_keys, args.show_values
    )


if __name__ == "__main__":
    main()

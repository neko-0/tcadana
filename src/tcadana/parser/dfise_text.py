import re
import numpy as np

_re_spaces = re.compile(r'[\s\n]+')
_re_info = re.compile(r'Info\s*\{([\s\S]*?)\}')
_re_info_data = re.compile(r'(\w+)\s*=\s*"?([^"\s]+)"?')
_re_version = re.compile(r'version\s*=\s*(\S+)|type\s*=\s*(\S+)')
_re_datasets = re.compile(r'datasets\s*=\s*\[(.*?)\]', re.DOTALL)
_re_functions = re.compile(r'functions\s*=\s*\[(.*?)\]', re.DOTALL)
_re_data = re.compile(r'Data\s*\{([\s\S]*?)(?:\}|$)', re.DOTALL)


def open_dfise_text_file(filename):
    return DFISETextFile(filename)


def _parsing(filename):
    with open(filename) as f:
        stream = _re_spaces.sub(" ", f.read())

        info_data = {}
        info_match = _re_info.search(stream)
        if info_match:
            info = info_match.group(1)
            # Extract version and type
            matches = _re_version.findall(info)
            info_data["version"] = matches[0][0]
            info_data["type"] = matches[1][1]

            # Extract datasets
            match = _re_datasets.search(info)
            if match:
                datasets = match.group(1).split('"')
                datasets = [item.strip() for item in datasets if item.strip()]
                info_data["datasets"] = datasets

            # Extract functions
            match = _re_functions.search(info)
            if match:
                functions = match.group(1).split()
                functions = [item.strip() for item in functions if item.strip()]
                info_data["functions"] = functions

        data_dict = {}
        data_match = _re_data.search(stream)
        if data_match:
            raw_data = np.fromstring(data_match.group(1), dtype=float, sep=" ")
            n = len(raw_data) // len(info_data["datasets"])
            for i, dataset in enumerate(info_data["datasets"]):
                # Extract the data for each dataset, taken every n elements
                chunk = raw_data[i :: len(info_data["datasets"])]
                # Pad the data to make it a multiple of n
                data_dict[dataset] = np.pad(
                    chunk, (0, n - len(chunk)), mode='constant'
                )[:n]

        return info_data, data_dict


class DFISETextFile:

    def __init__(self, filename):
        self._filename = filename
        self.version = None
        self.type = None
        self._flat_datasets = {}
        self.datasets = {}
        # Run parsing
        self._parse()

    def __getitem__(self, key):
        return self.datasets.get(key, self._flat_datasets.get(key))

    def __repr__(self):
        return f"DFISETextFile({self._filename})"

    def _parse(self):
        info_data, data_dict = _parsing(self._filename)
        self.version = info_data["version"]
        self.type = info_data["type"]
        self._flat_datasets = data_dict

        # Grouping datasets
        for name in self._flat_datasets.keys():
            name_split = name.split()
            if len(name_split) == 1:
                self.datasets[name] = self._flat_datasets[name]
            else:
                grp, attr = name_split
                if grp not in self.datasets:
                    self.datasets[grp] = {}
                self.datasets[grp][attr] = self._flat_datasets[name]

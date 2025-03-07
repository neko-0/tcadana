import json
import pickle
from pathlib import Path

import lz4.frame


class SerilizationBase:
    def to_pickle(self, data, name, *args, **kwargs):
        name = Path(name)
        name.parent.mkdir(parents=True, exist_ok=True)
        kwargs.setdefault("protocol", pickle.HIGHEST_PROTOCOL)
        with lz4.frame.open(name, "wb") as f:
            pickle_stream = pickle.dump(data, *args, **kwargs)
            f.write(pickle_stream)

    @staticmethod
    def from_pickle(self, name, *args, **kwargs):
        with lz4.frame.open(name) as f:
            return pickle.load(f, *args, **kwargs)

    def to_json(self, data, name, *args, **kwargs):
        name = Path(name)
        name.parent.mkdir(parents=True, exist_ok=True)
        kwargs.setdefault("indent", 4)
        kwargs.setdefault("separators", (",", ": "))
        with open(name, "w") as f:
            json.dump(data, f, *args, **kwargs)

    def from_json(self, name, *args, **kwargs):
        with open(name) as f:
            return json.load(f, *args, **kwargs)


serial_base = SerilizationBase()
to_pickle = serial_base.to_pickle
from_pickle = serial_base.from_pickle
to_json = serial_base.to_json
from_json = serial_base.from_json

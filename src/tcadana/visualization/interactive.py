import numpy as np
import bokeh
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, Select
from bokeh.transform import linear_cmap
from bokeh.server.server import Server
from bokeh.models import Rect
from bokeh.models import CheckboxGroup
from bokeh.layouts import column, row

from ..parser import open_tdr


class FieldViewer2D:
    def __init__(self, filename):
        self.doc = None

        # TDR structure file and field data
        self.filename = filename
        self.tdr_file = open_tdr(self.filename)
        self.tdr_file.load()
        self.field_names = list(self.tdr_file.field_names)
        self.region_names = list(self.tdr_file.region_names)
        self.plotdata = self.tdr_file.get_region_field_data_dict()

        # Window ranges
        self.x_range_start = None
        self.x_range_end = None
        self.y_range_start = None
        self.y_range_end = None

        self.p = None

        # Toggle for field selection
        self.select = Select(
            title="Field Name", options=self.field_names, value=self.field_names[0]
        )

        # Check boxes for region selection
        self.region_select = CheckboxGroup(
            labels=self.region_names, active=[i for i in range(len(self.region_names))]
        )

        # Toggle for inverting axis
        self.inverted_y = False
        self.invert_y_axis = CheckboxGroup(labels=["Invert Y Axis"], active=[])

    def __call__(self, doc):
        self.doc = doc
        self.update_plot()

    def __del__(self):
        self.tdr_file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.tdr_file.close()

    def update_plot(self):
        field_name = self.select.value

        x_values = []
        y_values = []
        field_values = []
        region_names = []
        for region_name, region_data in self.plotdata.items():
            tri = region_data[field_name]["tri"]
            field = region_data[field_name]["field"]
            x_values.append(tri.x)
            y_values.append(tri.y)
            field_values.append(field)
            region_names.append([region_name] * len(tri.x))

        x_values = np.concatenate(x_values)
        y_values = np.concatenate(y_values)
        field_values = np.concatenate(field_values)
        region_names = np.concatenate(region_names)

        data = {
            "x": x_values,
            "y": y_values,
            "field": field_values,
            "region": region_names,
        }

        source = ColumnDataSource(data=data)

        min_field_value = min(field_values)
        max_field_value = max(field_values)

        if self.x_range_start is None:
            self.x_range_start = min(x_values)
            self.x_range_end = max(x_values)
            self.y_range_start = min(y_values)
            self.y_range_end = max(y_values)

        self.figure = figure(
            title=f"2D Field Plot - {field_name}",
            x_axis_label="x [um]",
            y_axis_label="y [um]",
            x_range=(self.x_range_start, self.x_range_end),
            y_range=(self.y_range_start, self.y_range_end),
            match_aspect=True,
        )

        color_mapper = linear_cmap(
            'field', 'Viridis256', low=min_field_value, high=max_field_value
        )

        self.figure.rect(
            'x',
            'y',
            source=source,
            width=1,
            height=1,
            line_color=None,
            fill_color=color_mapper,
        )

        hover = HoverTool(tooltips=[("Region", "@region"), ("Field Value", "@field")])
        self.figure.add_tools(hover)

        self.select.on_change('value', self.update)
        self.region_select.on_change('active', self.update)
        self.invert_y_axis.on_change('active', self.update)

        self.figure.on_event(bokeh.events.Reset, self.update_range)
        self.figure.on_event(bokeh.events.RangesUpdate, self.update_range)

        self.doc.clear()
        self.doc.add_root(self.figure)
        self.doc.add_root(self.select)

        self.doc.add_root(row(column(self.region_select), column(self.invert_y_axis)))

    def update(self, attr, old, new):
        field_name = self.select.value

        # Get the selected regions
        selected_regions = [
            self.region_names[i]
            for i, label in enumerate(self.region_select.labels)
            if i in self.region_select.active
        ]

        # Filter the data by selected regions
        filtered_data = {}
        for region_name, region_data in self.plotdata.items():
            if region_name in selected_regions:
                filtered_data[region_name] = region_data

        x_values = []
        y_values = []
        field_values = []
        region_names = []
        for region_name, region_data in filtered_data.items():
            tri = region_data[field_name]["tri"]
            field = region_data[field_name]["field"]
            x_values.append(tri.x)
            y_values.append(tri.y)
            field_values.append(field)
            region_names.append([region_name] * len(tri.x))

        if field_values:
            x_values = np.concatenate(x_values)
            y_values = np.concatenate(y_values)
            field_values = np.concatenate(field_values)
            region_names = np.concatenate(region_names)
            min_field_value = min(field_values)
            max_field_value = max(field_values)
        else:
            min_field_value = 0
            max_field_value = 0

        data = {
            "x": x_values,
            "y": y_values,
            "field": field_values,
            "region": region_names,
        }

        source = self.figure.select_one(ColumnDataSource)
        source.data = data

        color_mapper = linear_cmap(
            'field', 'Viridis256', low=min_field_value, high=max_field_value
        )
        for glyph in self.figure.select(Rect):
            glyph.fill_color = color_mapper

        # Keep the same window range
        self.x_range_start = self.figure.x_range.start
        self.x_range_end = self.figure.x_range.end
        self.y_range_start = self.figure.y_range.start
        self.y_range_end = self.figure.y_range.end
        if self.invert_y_axis.active and not self.inverted_y:
            self.figure.y_range.start = self.y_range_end
            self.figure.y_range.end = self.y_range_start
            self.inverted_y = True
        elif not self.invert_y_axis.active and self.inverted_y:
            self.figure.y_range.start = self.y_range_end
            self.figure.y_range.end = self.y_range_start
            self.inverted_y = False

    def update_range(self, event):
        self.x_range_start = self.figure.x_range.start
        self.x_range_end = self.figure.x_range.end
        self.y_range_start = self.figure.y_range.start
        self.y_range_end = self.figure.y_range.end

    def start_server(self):
        server = Server({'/': self}, num_procs=1)
        print(f"Started field viewer server at http://localhost:{server.port}/")
        server.run_until_shutdown()

    def start_server_io_loop(self):
        server = Server({'/': self}, num_procs=1)
        server.io_loop.start()

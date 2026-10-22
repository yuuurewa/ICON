import os
import sys
from datetime import timedelta
from pathlib import Path

from helpers import set_paths, initial_time
from lib.cosmo import ComputedModelData, select_path, model_fileset
from lib.plot import PlotParameter
from lib.map import Map6kmES
from concurrent.futures import ProcessPoolExecutor, as_completed
from constants import *

NAME = "ICON"
resolution = "066"

if os.environ.get('HOSTNAME') == "xfront2" and sys.argv[1]:
    date = sys.argv[1]
else:
    date = "2024071100"
DATA_DIR, IMAGE_DIR, _ = set_paths(NAME, resolution, date)

resolution = float(resolution) / 10

parameters = [("dbz", None), ("h_snow_it", None), ("t2m", None), ("precipitation", None), ("wind_gust", None), ]
levels = [300, 500, 700, 850, 925, 1000]
parameters_agg = ("gust_max", "precip_sum", "h_snow_sum", )

MAP_CONFIGS = [
    (Map6kmES, "ES"),
    # (Map6kmWS, "WS"),
    # (Map6kmUO, "UO"),
]

def do_plot(aggregation_hours, fc_start_minutes, fc_end_minutes, data_step_minutes, map_class, cut):
    model = ComputedModelData(NAME)

    model_time = initial_time(model.time.values)

    plot = PlotParameter(model, resolution, data_step_minutes, aggregation_hours, model_time)

    for lead_time_min in model_fileset(fc_start_minutes, fc_end_minutes, data_step_minutes):
        fc_time = model_time + timedelta(minutes=lead_time_min)
        fc_time = fc_time.strftime("%d.%m.%Y %H UTC")
        lead_time = f"{lead_time_min // 60:03d}"

        with ProcessPoolExecutor(len(parameters)) as executor:
            futures = []

            for parameter, _ in parameters:
                plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
                print(parameter)
                futures.append(executor.submit(getattr(plot, parameter), fc_time, lead_time, cut=cut))

            for level in levels:
                plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
                futures.append(executor.submit(plot.wind_level, fc_time, lead_time, level, cut=cut))

            for key in ['clcl', 'clct']:
                plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
                futures.append(executor.submit(plot.cloud, fc_time, lead_time, key, cut=cut))
    #
            for key in type_cloud['cut']:
                plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
                futures.append(executor.submit(plot.cl_type, fc_time, lead_time, key, cut=cut))

            futures.append(executor.submit(plot.t_level, fc_time, lead_time, 850, cut=cut))

            for future in as_completed(futures):
                future.result()

        plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
        plot.phase(fc_time, lead_time, cut=cut)

    with ProcessPoolExecutor(len(parameters_agg) * 2) as executor:
        futures = []
        for parameter in parameters_agg:
            plot.def_map(map_class(IMAGE_DIR, date, "icon6"))
            print(parameter)
            futures.append(executor.submit(getattr(plot, parameter), hours_step=12, cut=cut))
        for future in as_completed(futures):
            future.result()


def main():
    Path(f"{IMAGE_DIR}").mkdir(parents=True, exist_ok=True)
    select_path(DATA_DIR, "lgfff")

    aggregation_hours = [0, 24, 48]
    fc_start_minutes = 3 * 60
    fc_end_minutes = 48 * 60 + 1
    data_step_minutes = 3 * 60
    for map_class, cut in MAP_CONFIGS:
        print(f"Построение карт: {map_class}, cut={cut}")
        do_plot(aggregation_hours, fc_start_minutes, fc_end_minutes, data_step_minutes, map_class, cut)


if __name__ == '__main__':
    main()



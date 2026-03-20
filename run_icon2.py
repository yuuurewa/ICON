import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from helpers import set_paths, initial_time
from lib.cosmo import ComputedModelData, select_path, model_fileset
from lib.plot import PlotParameter
from lib.map import Map2km
from constants import *

NAME = "ICON"
resolution = "022"

if os.environ.get('HOSTNAME') == "xfront2" and sys.argv[1]:
    date = sys.argv[1]
else:
    date = "2024071100"
DATA_DIR, IMAGE_DIR = set_paths(NAME, resolution, date)

resolution = float(resolution) / 10

parameters = [("stp", None), ("precipitation", None), ("wind_gust", None), ("dbz", None), ("lpi", None), ("t2m", None),
              ("rh2m", None), ("dp2m", None), ("vis", None), ("phase", None),]

levels = [300, 500, 700, 850, 925, 1000]
parameters_agg = ("gust_max", "lpi_max24", "sdi2_max24", "precip_sum", "hail_max")


def do_plot(aggregation_hours, fc_start_minutes, fc_end_minutes, data_step_minutes):
    model = ComputedModelData(NAME)

    model_time = initial_time(model.time.values)

    plot = PlotParameter(model, resolution, data_step_minutes, aggregation_hours, model_time)

    for lead_time_min in model_fileset(fc_start_minutes, fc_end_minutes, data_step_minutes):
        fc_time = model_time + timedelta(minutes=lead_time_min)
        fc_time = fc_time.strftime("%d.%m.%Y %H UTC")
        lead_time = f"{lead_time_min//60:03d}"

        with ProcessPoolExecutor(len(parameters)) as executor:
            futures = []

            for parameter, _ in parameters:
                plot.def_map(Map2km(IMAGE_DIR, date, "cosmo_phenom"))
                print(parameter)
                futures.append(executor.submit(getattr(plot, parameter), fc_time, lead_time))

            for level in levels:
                plot.def_map(Map2km(IMAGE_DIR, date, "cosmo_phenom"))
                futures.append(executor.submit(plot.t_level, fc_time, lead_time, level))
                futures.append(executor.submit(plot.rh_level, fc_time, lead_time, level))
                futures.append(executor.submit(plot.wind_level, fc_time, lead_time, level))
                futures.append(executor.submit(plot.wz_level, fc_time, lead_time, level))

            for key in cl_desc:
                plot.def_map(Map2km(IMAGE_DIR, date, "cosmo_phenom"))
                futures.append(executor.submit(plot.cloud, fc_time, lead_time, key))

            for key in type_cloud:
                plot.def_map(Map2km(IMAGE_DIR, date, "cosmo_phenom"))
                futures.append(executor.submit(plot.cl_type, fc_time, lead_time, key))

            for future in as_completed(futures):
                future.result()

    with ProcessPoolExecutor(len(parameters_agg) + 2) as executor:
        futures = []
        for parameter in parameters_agg:
            plot.def_map(Map2km(IMAGE_DIR, date, "cosmo_phenom"))
            print(parameter)
            futures.append(executor.submit(getattr(plot, parameter)))
            if parameter in ("gust_max", "precip_sum"):
                futures.append(executor.submit(getattr(plot, parameter), hours_step=12))
        for future in as_completed(futures):
            future.result()


def main():
    Path(f"{IMAGE_DIR}").mkdir(parents=True, exist_ok=True)
    select_path(DATA_DIR, "lgfff")

    aggregation_hours = [0, 24, 48]
    fc_start_minutes = 1 * 60
    fc_end_minutes = 48 * 60 + 1
    data_step_minutes = 1 * 60
    do_plot(aggregation_hours, fc_start_minutes, fc_end_minutes, data_step_minutes)


if __name__ == '__main__':
    main()

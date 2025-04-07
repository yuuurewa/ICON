import os
import sys
from datetime import timedelta
from pathlib import Path

from helpers import set_paths, initial_time
from lib.cosmo import ComputedModelData, select_path, model_fileset
from lib.plot import PlotParameter
from lib.map import Map2km

NAME = "ICON"
resolution = "022"

date = "2024071100"
DATA_DIR = ""
IMAGE_DIR = ""

resolution = float(resolution) / 10
aggregation_hours = [0, 24, 48]
fc_start_minutes = 1 * 60
fc_end_minutes = 48 * 60 + 1
data_step_minutes = 1 * 60


def main():
    Path(f"{IMAGE_DIR}").mkdir(parents=True, exist_ok=True)
    select_path(DATA_DIR, "lgfff")
    map = Map2km(IMAGE_DIR, date, "cosmo_phenom")
    model = ComputedModelData(NAME)
    model_time = initial_time(model.time.values)
    plot = PlotParameter(model, resolution, data_step_minutes, aggregation_hours, model_time)
    plot.def_map(map)
    for lead_time_min in model_fileset(fc_start_minutes, fc_end_minutes, data_step_minutes):
        fc_time = model_time + timedelta(minutes=lead_time_min)
        fc_time = fc_time.strftime("%d/%m/%Y %H(UTC)")
        lead_time = f"{lead_time_min//60:02d}"
        plot.stp(fc_time, lead_time)
        # plot.dbz(fc_time, lead_time)
        # plot.precipitation(fc_time, lead_time)
        # plot.wind_gust(fc_time, lead_time)
        # plot.lpi(fc_time, lead_time)
    # plot.gust_max()
    # plot.lpi_max24()
    # plot.sdi2_max24()
    # # plot.hail_max24()
    # plot.precip_sum()
    # plot.precip_sum(hours_step=12)
    # plot.gust_max(hours_step=12)
    # @# plot.stp_max24()


if __name__ == '__main__':
    main()




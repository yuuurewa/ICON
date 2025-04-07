from datetime import datetime, timedelta
from typing import List

import numpy
import xarray as xr

from constants import *
from helpers import initial_time
from lib.cosmo import ComputedModelData, model_fileset, select_grib_file
from lib.map import BasePlot


class PlotParameter:
    def __init__(
        self,
        model: ComputedModelData,
        resolution: float,
        data_step_min: int,
        aggregation_hours: List[int],
        model_time: datetime,
    ) -> None:
        self.model = model
        self.lats = model.lats.values
        self.lons = model.lons.values
        self.resolution = resolution
        self.data_step_min = data_step_min
        self.aggregation_hours = aggregation_hours
        self.half_aggregation_hours = list(range(aggregation_hours[0], aggregation_hours[-1] + 1, 12))
        self.model_time = model_time
        self.title = f'\nCOSMO-Ru{str(resolution)[0]}Sib ({model.name}) от {model_time.strftime("%d/%m/%Y %H(UTC)")}'
        self.plot_map: BasePlot = BasePlot("", "", "")
        self.mesh_grid()

    def mesh_grid(self):
        if len(self.lons.shape) == 1:
            self.lons, self.lats = numpy.meshgrid(self.lons, self.lats)

    def def_map(self, plot_map: BasePlot):
        self.plot_map = plot_map

    def lpi_max24(self, hours_step=24) -> None:
        description = "макс. молниевый потенциал"

        title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Max молн за 24ч, Дж/м2"
        self._plot_max(name="lpi_max", data_step_minutes=10, cbar=cbar,
                       bounds=lpi_bounds, title=title, cmap_list=lpi_cmap, hours_step=hours_step)

    def sdi2_max24(self, hours_step=24) -> None:
        description = "индекс суперячейки"

        title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = "SDI_2 за 24 часа, 1/с"
        self._plot_max(name="sdi_2", data_step_minutes=60, cbar=cbar,
                       bounds=sdi_bounds, title=title, threshold=sdi_threshold, cm="seismic", hours_step=hours_step)

    def hail_max(self, hours_step=24) -> None:
        description = "макс. град"

        title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = f"Max диам. града за {hours_step} час(а), мм"
        self._plot_max(name="dhail_avg", data_step_minutes=5, cbar=cbar,
                       bounds=hail_bounds, title=title, cmap_list=hail_cmap, hours_step=hours_step)

    def gust_max(self, hours_step: int=24) -> None:
        description = "макс. возможные порывы ветра"

        title = f"{description} за {hours_step} часа(ов){self.title}"
        cbar = cbar_full[self.resolution]
        if self.resolution == 6.6:
            step = 180
        else:
            step = 60
        cbar["label"] = f"макс. порывы ветра за {hours_step} ч., м/с"
        self._plot_max(name="vmax_10m", data_step_minutes=step, cbar=cbar,
                       bounds=gust_bounds, title=title, cmap_list=gust_cmap, hours_step=hours_step)

    def stp_max24(self, hours_step=24) -> None:
        description = "макс. STP"

        title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        if self.resolution == 6.6:
            step = 180
        else:
            step = 60
        cbar["label"] = "макс. STP за 24 часа, 1"
        self._plot_max(name="stp", data_step_minutes=step, cbar=cbar,
                       bounds=stp_levels, title=title, cmap_list=gust_cmap[1:], extend='max', hours_step=hours_step)

    def precip_sum(self, hours_step: int = 24) -> None:
        description = "осадки"

        title = f"{description} за {hours_step} часа(ов){self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = f"Осадки за {hours_step} ч., мм"
        if hours_step == 24:
            hours = self.aggregation_hours
        else:
            hours = self.half_aggregation_hours
        start_hour = hours[0]
        end_hours = hours[1:]
        bounds = [int(v * 3) if v > 1 else v for v in prec_bounds]
        tot_prec_previous = np.zeros(self.lats.shape)
        for end_hour in end_hours:
            for _ in model_fileset(start_hour * 60, end_hour * 60, hours_step * 60):
                tot_prec_previous = self.model.tot_prec.values
            for lead_time_minutes in model_fileset(end_hour * 60, end_hour * 60 + 1, 60):
                tot_prec = self.model.tot_prec.values - tot_prec_previous
                tot_prec_previous = self.model.tot_prec.values
                model_time = initial_time(self.model.time.values)
                fc_time = model_time + timedelta(minutes=lead_time_minutes)
                fc_time = fc_time.strftime("%d/%m/%Y %H(UTC)")
                title_fc = f"{fc_time}, {title} +({start_hour}-{end_hour})ч"
                self.plot_map.create(title_fc)
                c = self.plot_map.draw_contourf(tot_prec, self.lats, self.lons, bounds,
                                           cmap_list=prec_cmap, extend='max')
                self.plot_map.draw_colorbar(c, cbar, bounds)
                if hours_step == 24:
                    self.plot_map.save(f"{self.model.name}_{self.resolution}_SUM_tot_prec_{end_hour+1:03d}")
                else:
                    self.plot_map.save(f"{self.model.name}_{self.resolution}_SUM_tot_prec_{end_hour:03d}")
                start_hour = end_hour

    def _plot_max(self, *, name: str, data_step_minutes: int, cbar: dict, bounds: tuple, title: str,
                  threshold: float = None, hours_step: int = 24, **kwargs) -> None:
        da = xr.DataArray()
        if hours_step == 24:
            hours = self.aggregation_hours
        else:
            hours = self.half_aggregation_hours
        start_hours = hours[:-1]
        end_hours = hours[1:]
        for j, start_hour in enumerate(start_hours):
            for i, lead_time_minutes in enumerate(
                    model_fileset(start_hour * 60, end_hours[j] * 60 + 1, data_step_minutes)):
                parameter = getattr(self.model, name).array
                lead_time_hours = lead_time_minutes / 60
                if lead_time_hours == end_hours[j]:
                    da = xr.concat([da, parameter], "time")
                    fc_time = self.model_time + timedelta(minutes=lead_time_minutes)
                    fc_time = fc_time.strftime("%d/%m/%Y %H(UTC)")
                    title_fc = f"{fc_time}, {title} +({start_hour}-{int(lead_time_hours)})ч"
                    self.plot_map.create(title_fc)
                    if threshold:
                        min_values = np.where(np.abs(da.min(dim="time").values) >= threshold, da.min(dim="time"),
                                              np.nan)
                        self.plot_map.draw_contourf(min_values, self.lats, self.lons, bounds, **kwargs)
                        max_values = np.where(np.abs(da.max(dim="time").values) >= threshold, da.max(dim="time"),
                                              np.nan)
                        c = self.plot_map.draw_contourf(max_values, self.lats, self.lons, bounds, **kwargs)
                    else:
                        a = abs(self.lats - 55.2) + abs(self.lons - 88.6)
                        values = da.max(dim="time")
                        c = self.plot_map.draw_contourf(values, self.lats, self.lons, bounds, **kwargs)
                    self.plot_map.draw_colorbar(c, cbar, bounds)
                    if hours_step == 24:
                        self.plot_map.save(f"{self.model.name}_{self.resolution}_MAX_{name}_{int(lead_time_hours)+1:03d}")
                    else:
                        self.plot_map.save(f"{self.model.name}_{self.resolution}_MAX_{name}_{int(lead_time_hours):03d}")
                    da = xr.DataArray()

                if lead_time_hours == start_hours[j]:
                    da = parameter

                elif lead_time_hours != end_hours[j]:
                    da = xr.concat([da, parameter], "time")

    def stp(self, fc_time, lead_time) -> None:
        description = "индекс суперячейки, Significant Tornado Parameter"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        stp = self.plot_map.draw_contour(self.model.stp, self.lats, self.lons, stp_levels, gust_cmap[2:])

        if self.resolution == 2.2:
            sdi2 = self.plot_map.draw_contourf(self.model.sdi_2.values, self.lats, self.lons, sdi_bounds, cm="seismic",
                                           opacity=0.9)
            cbar = cbar_h_left
            cbar["label"] = "SDI_2, 1/с"
            self.plot_map.draw_colorbar(sdi2, cbar, sdi_bounds)
        cbar = cbar_h_right
        cbar["label"] = "STP, 1"

        if len(stp.levels) > 1:
            self.plot_map.draw_colorbar(stp, cbar, stp_levels)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_stp_{lead_time}")

    def scp(self, fc_time, lead_time) -> None:
        description = "SuperCell Composite Parameter"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        scp = self.plot_map.draw_contourf(self.model.scp, self.lats, self.lons, scp_levels, cmap_list=gust_cmap)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "SCP, 1"
        self.plot_map.draw_colorbar(scp, cbar, scp_levels)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_scp_{lead_time}")

    def precipitation(self, fc_time, lead_time) -> None:
        scale = self.data_step_min / 60
        description = f"осадки за {int(scale)}ч. и облачность, PMSL"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        precip_bounds = [v * scale for v in prec_bounds]
        self.plot_map.create(title)
        pmsl, lons, lats = self.model.pmsl.smoothed_values()
        self.plot_map.draw_contour(pmsl / 100, lats, lons, pmsl_levels, 'navy')
        clcm = self.plot_map.draw_contourf(self.model.clcm.values, self.lats, self.lons, cloud_levels, cm="Blues", opacity=0.5)

        lead_time_min = int(lead_time) * 60
        previous_lead_time = lead_time_min - self.data_step_min
        next_lead_time = lead_time_min + self.data_step_min
        if previous_lead_time > 0:
            for _ in model_fileset(previous_lead_time, lead_time_min, self.data_step_min):
                previous_prec = self.model.tot_prec.values
            for _ in model_fileset(lead_time_min, next_lead_time, self.data_step_min):
                prec = self.model.tot_prec.values - previous_prec
        else:
            prec = self.model.tot_prec.values

        critical_values = np.where(prec >= 0.1, prec, np.nan)
        if np.count_nonzero(~np.isnan(critical_values)) > 20:
            prec = self.plot_map.draw_contourf(prec, self.lats, self.lons, precip_bounds, cmap_list=prec_cmap,
                                           extend='max')

            cbar = cbar_h_right
            cbar["label"] = f"Осадки за {int(scale)}ч., мм"
            self.plot_map.draw_colorbar(prec, cbar, precip_bounds)
            cbar = cbar_h_left
            cbar["label"] = "Облачность ср. яруса, %"
            self.plot_map.draw_colorbar(clcm, cbar, cloud_levels)
        else:
            cbar = cbar_h_left
            cbar["label"] = "Облачность ср. яруса, %"
            self.plot_map.draw_colorbar(clcm, cbar, cloud_levels)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_tot_prec_{lead_time}")

    def dbz(self, fc_time, lead_time) -> None:
        description = "макс. радиолокационная отражаемость"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        if self.resolution == 2.2:
            dbz_max = self.model.dbz(lead_time)
        else:
            dbz_max = self.model.dbz_ctmax.values
        dbz = self.plot_map.draw_contourf(dbz_max, self.lats, self.lons, dbz_bounds, cmap_list=dbz_cmap, extend='max')
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Max отражаемость, dbZ (за 1 час)"
        self.plot_map.draw_colorbar(dbz, cbar, dbz_bounds)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_dbz_ctmax_{lead_time}")

    def wind_gust(self, fc_time, lead_time) -> None:
        description = "ветер и порывы на 10м, PMSL"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        pmsl, lons, lats = self.model.pmsl.smoothed_values()
        self.plot_map.draw_contour(pmsl / 100, lats, lons, pmsl_levels, 'navy')
        vmax = self.plot_map.draw_contourf(self.model.vmax_10m.values, self.lats, self.lons, gust_bounds,
                                       cmap_list=gust_cmap)
        self.plot_map.draw_barbs(self.model.u_10m.values, self.model.v_10m.values, self.lats, self.lons)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Порыв ветра, м/с"
        self.plot_map.draw_colorbar(vmax, cbar, gust_bounds)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_wind_gust_{lead_time}")

    def lpi(self, fc_time, lead_time) -> None:
        description = "макс. молниевый потенциал"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        lpi_max = self.model.lpi(lead_time)
        lpi = self.plot_map.draw_contourf(lpi_max, self.lats, self.lons, lpi_bounds, cmap_list=lpi_cmap)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Max молн, Дж/м2 (за 1 час)"
        self.plot_map.draw_colorbar(lpi, cbar, lpi_bounds)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_lpi_max_{lead_time}")

    def t2m(self, fc_time, lead_time) -> None:
        description = "температура воздуха"

        title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(title)
        if self.model.name == "ICON":
            t, lons, lats = self.model.t_2m_grb2.smoothed_values(10)
        else:
            t, lons, lats = self.model.t_2m.smoothed_values(10)
        self.plot_map.draw_contour(t - 273.15, lats, lons, t_levels[::2], 'black', linewidth=0.2)
        t2m = self.plot_map.draw_contourf(t - 273.15, lats, lons, t_levels, cm="nipy_spectral")
        cbar = cbar_full[self.resolution]
        cbar["label"] = "T,°C"
        self.plot_map.draw_colorbar(t2m, cbar, t_levels)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_t2m_{lead_time}")


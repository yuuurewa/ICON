from datetime import datetime, timedelta
from typing import List

import numpy
import xarray as xr
import cartopy.crs as ccrs

from constants import *
from helpers import initial_time
from lib.cosmo import ComputedModelData, model_fileset, select_grib_file
from lib.map import BasePlot
from scipy.ndimage import gaussian_filter
from math import floor, ceil
import matplotlib.pyplot as plt

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
        self.text_left = f'COSMO-Ru{str(resolution)[0]}Sib ({model.name})'
        self.text_right = f'От {model_time.strftime("%d.%m.%Y %H UTC")}'
        self.plot_map: BasePlot = BasePlot("", "", "")
        self.mesh_grid()

    def mesh_grid(self):
        if len(self.lons.shape) == 1:
            self.lons, self.lats = numpy.meshgrid(self.lons, self.lats)

    def def_map(self, plot_map: BasePlot):
        self.plot_map = plot_map

    def auto_levels(self, data, *, target_levels: int = 12):
        arr = np.asarray(data)
        dmin = np.nanmin(arr)
        dmax = np.nanmax(arr)
        if np.isclose(dmin, dmax):
            return np.linspace(dmin, dmax + 1, 3)
        rng = dmax - dmin
        raw = rng / target_levels
        exp = 10 ** np.floor(np.log10(raw))
        frac = raw / exp
        step = (
            1 * exp if frac < 1.5 else
            2 * exp if frac < 3 else
            5 * exp if frac < 7 else
            10 * exp
        )
        start = np.floor(dmin / step) * step
        end = np.ceil(dmax / step) * step
        return np.arange(start, end + step, step)

    def lpi_max24(self, hours_step=24) -> None:
        description = f"Макс. молниевый потенциал ({hours_step} ч)"

        # title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Max молн за 24ч, Дж/м2"
        self._plot_max(name="lpi_max", data_step_minutes=10, cbar=cbar,
                       bounds=lpi_bounds, description=description, cmap_list=lpi_cmap, hours_step=hours_step)

    def sdi2_max24(self, hours_step=24) -> None:
        description = f"Индекс суперячейки (SDI) ({hours_step} ч)"

        # title = f"{}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = "SDI_2 за 24 часа, 1/с"
        self._plot_max(name="sdi_2", data_step_minutes=60, cbar=cbar,
                       bounds=sdi_bounds, description=description, threshold=sdi_threshold, cm="seismic", hours_step=hours_step)

    def hail_max(self, hours_step=24) -> None:
        description = f"Макс. град ({hours_step} ч)"

        # title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        cbar["label"] = f"Max диам. града за {hours_step} час(а), мм"
        self._plot_max(name="dhail_avg", data_step_minutes=5, cbar=cbar,
                       bounds=hail_bounds, description=description, cmap_list=hail_cmap, hours_step=hours_step)

    def gust_max(self, hours_step: int=24) -> None:
        description = f"Максимальные порывы ветра ({hours_step} ч)"

        # title = f"{description} за {hours_step} часа(ов){self.title}"
        cbar = cbar_full[self.resolution]
        if self.resolution == 6.6:
            step = 180
        else:
            step = 60
        cbar["label"] = f"макс. порывы ветра за {hours_step} ч., м/с"
        self._plot_max(name="vmax_10m", data_step_minutes=step, cbar=cbar,
                       bounds=gust_bounds, description=description, cmap_list=gust_cmap, hours_step=hours_step)

    def stp_max24(self, hours_step=24) -> None:
        description = "макс. STP"

        # title = f"{description}{self.title}"
        cbar = cbar_full[self.resolution]
        if self.resolution == 6.6:
            step = 180
        else:
            step = 60
        cbar["label"] = "макс. STP за 24 часа, 1"
        self._plot_max(name="stp", data_step_minutes=step, cbar=cbar,
                       bounds=stp_levels, description=description, cmap_list=gust_cmap[1:], extend='max', hours_step=hours_step)

    def precip_sum(self, hours_step: int = 24) -> None:
        description = f"Осадки ({hours_step} ч)"

        # title = f"{description} за {hours_step} часа(ов){self.title}"
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
                #model_time = initial_time(self.model.time.values)
                fc_time = self.model_time + timedelta(minutes=lead_time_minutes)
                fc_time = fc_time.strftime("%d.%m.%Y %H UTC")
                # title_fc = f"{fc_time}, {title} +({start_hour}-{end_hour})ч"
                lead_time = f"({start_hour}-{end_hour})"
                self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
                c = self.plot_map.draw_contourf(tot_prec, self.lats, self.lons, bounds,
                                           cmap_list=prec_cmap, extend='max')
                self.plot_map.draw_colorbar(c, cbar, bounds)
                if hours_step == 24:
                    self.plot_map.save(f"{self.model.name}_{self.resolution}_SUM_tot_prec_{end_hour+1:03d}")
                else:
                    self.plot_map.save(f"{self.model.name}_{self.resolution}_SUM_tot_prec_{end_hour:03d}")
                start_hour = end_hour

    def _plot_max(self, *, name: str, data_step_minutes: int, cbar: dict, bounds: tuple, description: str,
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
                    fc_time = fc_time.strftime("%d.%m.%Y %H UTC")
                    lead_time = f"({start_hour}-{int(lead_time_hours)})"
                    # title_fc = f"{fc_time}, {title} +({start_hour}-{int(lead_time_hours)})ч"
                    self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
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
        description = "Индекс суперъячейки (SDI), параметр значимых торнадо (STP)"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
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

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        scp = self.plot_map.draw_contourf(self.model.scp, self.lats, self.lons, scp_levels, cmap_list=gust_cmap)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "SCP, 1"
        self.plot_map.draw_colorbar(scp, cbar, scp_levels)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_scp_{lead_time}")

    def precipitation(self, fc_time, lead_time) -> None:
        scale = self.data_step_min / 60
        description = f"Осадки ({int(scale)}ч), облачность среднего яруса (%), давление на уровне моря"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        precip_bounds = [v * scale for v in prec_bounds]
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        clcm = self.plot_map.draw_contourf(self.model.clcm.values, self.lats, self.lons, cloud_levels, cm="Blues",
                                           opacity=0.5)
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
        description = "Макс. радиолокационная отражаемость"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
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
        description = "Ветер и порывы ветра, давление на уровне моря"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        vmax = self.plot_map.draw_contourf(self.model.vmax_10m.values, self.lats, self.lons, gust_bounds,
                                       cmap_list=gust_cmap)
        self.plot_map.draw_barbs(self.model.u_10m.values, self.model.v_10m.values, self.lats, self.lons)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Порыв ветра, м/с"
        self.plot_map.draw_colorbar(vmax, cbar, gust_bounds)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_wind_gust_{lead_time}")

    def lpi(self, fc_time, lead_time) -> None:
        description = "Макс. молниевый потенциал"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        lpi_max = self.model.lpi(lead_time)
        lpi = self.plot_map.draw_contourf(lpi_max, self.lats, self.lons, lpi_bounds, cmap_list=lpi_cmap)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Max молн, Дж/м2 (за 1 час)"
        self.plot_map.draw_colorbar(lpi, cbar, lpi_bounds)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_lpi_max_{lead_time}")

    def t2m(self, fc_time, lead_time) -> None:
        description = "Температура воздуха"

        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
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

    def rh2m(self, fc_time, lead_time) -> None:
        description = "Относительная влажность (2 м)"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        rh = gaussian_filter(self.model.rh_2m.values, sigma=6)
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        cr = self.plot_map.draw_contourf(rh, self.lats, self.lons, levels_rh, cm=plt.cm.summer_r, extend=None)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Отн. влажность (%)"
        self.plot_map.draw_colorbar(cr, cbar, levels_rh)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_rh2m_{lead_time}")

    def t_level(self, fc_time, lead_time, level: int) -> None:
        description = f"Температура на уровне {level} гПа"
        fc_time_dt = datetime.strptime(fc_time, "%d.%m.%Y %H %Z")
        month = fc_time_dt.month
        season = "warm" if 4 <= month <= 9 else "cold"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        t = gaussian_filter(self.model.t_lvl(level).values, sigma=5)
        fi = gaussian_filter(self.model.fi_lvl(level).values, sigma=5)
        t_cels = t - 273.15
        fi_dam = fi / 9.80665 / 10
        res = self.resolution  # 6.6 или 2.2
        t_min, t_max = level_temp.get((season, res, level), (floor(np.nanmin(t_cels)), ceil(np.nanmax(t_cels))))
        levels_t = np.arange(t_min, t_max + 0.1, 2)
        cmap = plt.get_cmap("nipy_spectral", 34)
        colors = [cmap(i) for i in range(cmap.N)]
        ct = self.plot_map.draw_contourf(t_cels, self.lats, self.lons, levels_t, cmap_list=colors)
        cf = self.plot_map.draw_contour(fi_dam, self.lats, self.lons, fi_levels[level], 'saddlebrown', linewidth=1)
        for label in cf.labelTexts:
            label.set_fontsize(8.5)
            label.set_bbox(dict(facecolor='white', edgecolor='none', pad=1))
        cbar = cbar_full[self.resolution]
        cbar["label"] = f"Температура на уровне {level} гПа,°C"
        self.plot_map.draw_colorbar(ct, cbar, levels_t)
        handles = [plt.Line2D([0], [0], color='saddlebrown', lw=2, label='Геопотенциальная высота (дам)')]
        self.plot_map.ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(-0.008, 1.05), fontsize=9,
                                frameon=True)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_t{level}_{lead_time}")
    def rh_level(self, fc_time, lead_time, level: int) -> None:
        description = f"Относительная влажность на уровне {level} гПа"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        rh = gaussian_filter(self.model.rh_lvl(level).values, sigma=5)
        fi = gaussian_filter(self.model.fi_lvl(level).values, sigma=5)
        fi_dam = fi / 9.80665 / 10
        crh = self.plot_map.draw_contourf(rh, self.lats, self.lons, levels_rh, cm=plt.cm.summer_r, extend=None)
        cf = self.plot_map.draw_contour(fi_dam, self.lats, self.lons, fi_levels[level], 'saddlebrown')
        for label in cf.labelTexts:
            label.set_fontsize(8.5)
            label.set_bbox(dict(facecolor='white', edgecolor='none', pad=1))
        cbar = cbar_full[self.resolution]
        cbar["label"] = f"Отн. влажность на уровне {level} гПа (%)"
        self.plot_map.draw_colorbar(crh, cbar, levels_rh)
        handles = [plt.Line2D([0], [0], color='saddlebrown', lw=2, label='Геопотенциальная высота (дам)')]
        self.plot_map.ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(-0.008, 1.05), fontsize=9, frameon=True)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_relhum{level}_{lead_time}")

    def wind_level(self, fc_time, lead_time, level: int) -> None:
        description = f"Ветер на уровне {level} гПа"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        if level==300:
            self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        else:
            self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution, right_pos=0.92)

        u = self.model.u_lvl(level)
        v = self.model.v_lvl(level)
        fi = gaussian_filter(self.model.fi_lvl(level).values, sigma=5)
        fi_dam = fi / 9.80665 / 10
        wind_speed = np.sqrt(u.values ** 2 + v.values ** 2)
        if level==300:
            if self.resolution == 2.2:
                barb = self.plot_map.draw_contourf(wind_speed, u.lats, u.lons, wind_h300_levels,
                                                   cmap_list=wind_h300_cmap, extend='max')
            else:
                lons_2d, lats_2d = np.meshgrid(u.lons, u.lats)
                barb = self.plot_map.draw_contourf(wind_speed, lats_2d, lons_2d, wind_h300_levels,
                                               cmap_list=wind_h300_cmap, extend='max')
            cbar = cbar_full[self.resolution]
            cbar["label"] = f"Скорость ветра (м/с)"
            self.plot_map.draw_colorbar(barb, cbar, wind_h300_levels)
        cf = self.plot_map.draw_contour(fi_dam, self.lats, self.lons, fi_levels[level], 'saddlebrown')
        if self.resolution == 2.2:
            self.plot_map.draw_barbs(u.values, v.values, self.lats, self.lons)
        else:
            self.plot_map.draw_barbs(u.values[::3], v.values[::3], self.lats[::3], self.lons[::3])
        handles = [plt.Line2D([0], [0], color='saddlebrown', lw=2, label='Геопотенциальная высота (дам)')]
        self.plot_map.ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(-0.008, 1.05), fontsize=9, frameon=True)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_wind{level}_{lead_time}")

    def wz_level(self, fc_time, lead_time, level: int):
        description = f"Вертикальная скорость на уровне {level} гПа"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        w = gaussian_filter(self.model.w_lvl(level).values, sigma=5)
        fi = gaussian_filter(self.model.fi_lvl(level).values, sigma=5)
        fi_dam = fi / 9.80665 / 10
        w_levels = self.auto_levels(w)
        cw = self.plot_map.draw_contourf(w, self.lats, self.lons, w_levels, cm="seismic", extend=None)
        cf = self.plot_map.draw_contour(fi_dam, self.lats, self.lons, fi_levels[level], 'saddlebrown')
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Вертикальная скорость (м/с)"
        self.plot_map.draw_colorbar(cw, cbar, w_levels)
        handles = [plt.Line2D([0], [0], color='saddlebrown', lw=2, label='Геопотенциальная высота (дам)')]
        self.plot_map.ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(-0.008, 1.06), fontsize=9, frameon=True)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_wz{level}_{lead_time}")

    def vis(self, fc_time, lead_time) -> None:
        description = "Приземная видимость"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        vis = gaussian_filter(self.model.vis.values, sigma=6)
        vis[vis > 10001.0] = np.nan
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        cv = self.plot_map.draw_contourf(vis, self.lats, self.lons, levels_vis, cmap_list=vis_colors, extend=None)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Видимость (м)"
        self.plot_map.draw_colorbar(cv, cbar, levels_vis)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_vis_{lead_time}")

    def cloud(self, fc_time, lead_time, level: str) -> None:
        if level=='clcl' or level=='clcm' or level=='clch':
            description = f"Облачность {cl_desc[level]} яруса (%)"
        elif level=='clct':
            description = cl_desc[level]
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        cl_da = self.model.get_cloud(level)
        cl = gaussian_filter(cl_da.values, sigma=6)
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        cv = self.plot_map.draw_contourf(cl, self.lats, self.lons, cl_lvl, cmap_list=plt.cm.gist_yarg, extend=None)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Облачность (%)"
        self.plot_map.draw_colorbar(cv, cbar, cl_lvl)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_{level}_{lead_time}")

    def cl_type(self, fc_time, lead_time, type: str) -> None:
        if type=='hbas_con':
            description = f"Нижняя граница конвективной облачности"
        elif type=='htop_con':
            description = f"Верхняя граница конвективной облачности"
        elif type=='ceiling':
            description = f"Высота нижней границы общей облачности"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        type_cl = getattr(self.model, type)
        cloud_cover = type_cl.values - self.model.hsurf.values
        cloud_cover[cloud_cover > 12001.0] = np.nan
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        if type=='htop_con':
            cc = self.plot_map.draw_contourf(cloud_cover, self.lats, self.lons, levels_cl_cov,
                                             cmap_list=cl_cov_colors[::-1], extend=None)
        else:
            cc = self.plot_map.draw_contourf(cloud_cover, self.lats, self.lons, levels_cl_cov, cmap_list=cl_cov_colors,
                                             extend=None)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Высота (м)"
        self.plot_map.draw_colorbar(cc, cbar, levels_cl_cov)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_{type}_{lead_time}")

    def dp2m(self, fc_time, lead_time) -> None:
        description = "Дефицит точки росы (2 м)"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution)
        t = gaussian_filter(self.model.t_2m_grb2.values, sigma=6)
        td = gaussian_filter(self.model.td_2m.values, sigma=6)
        d = t - td
        levels_d = np.arange(floor(d.min()), ceil(d.max()) + 0.1, 4)
        cmap = plt.get_cmap("summer", 256)
        colors = [cmap(i) for i in range(cmap.N)]
        sigma = 15 if self.resolution == 2.2 else 6
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy')
        cd = self.plot_map.draw_contourf(d, self.lats, self.lons, levels_d, cmap_list=colors, extend=None)
        cbar = cbar_full[self.resolution]
        cbar["label"] = "Дефицит точки росы"
        self.plot_map.draw_colorbar(cd, cbar, levels_d)
        self.plot_map.save(f"{self.model.name}_{self.resolution}_dew_point_{lead_time}")

    def phase(self, fc_time, lead_time) -> None:
        description = f"Фаза и интенсивность осадков ({int(self.data_step_min / 60)} ч)"
        # title = f"{fc_time}, {description}{self.title} +{lead_time}"
        self.plot_map.create(self.text_left, self.text_right, description, fc_time, lead_time, self.resolution, right_pos=1.085)
        rain_con = self.model.rain_con
        rain_gsp = self.model.rain_gsp
        snow_con = self.model.snow_con
        snow_gsp = self.model.snow_gsp
        rain = rain_con.values + rain_gsp.values
        snow = snow_con.values + snow_gsp.values
        total = rain + snow
        p_rain = rain / (total + 1e-6)
        p_snow = snow / (total + 1e-6)
        is_rain = rain > 0
        is_snow = snow > 0
        is_mixed = is_rain & is_snow
        rain_only = np.where(is_rain & ~is_snow, rain, np.nan)
        snow_only = np.where(is_snow & ~is_rain, snow, np.nan)
        mixed = np.full_like(total, np.nan)
        mixed_mask = is_mixed & (p_rain >= 0.1) & (p_snow >= 0.1)
        rain_mask = is_mixed & (p_snow < 0.1)
        snow_mask = is_mixed & (p_rain < 0.1)
        mixed[mixed_mask] = total[mixed_mask]
        rain_only[rain_mask] = total[rain_mask]
        snow_only[snow_mask] = total[snow_mask]
        if self.resolution == 2.2:
            sigma = 15
            lons, lats = rain_gsp.lons.values, rain_gsp.lats.values
        else:
            sigma = 6
            lons, lats = np.meshgrid(rain_gsp.lons.values, rain_gsp.lats.values)
        pmsl_sm = gaussian_filter(self.model.pmsl.values, sigma)
        pmsl = pmsl_sm / 100
        pm = self.plot_map.draw_contour(pmsl, self.lats, self.lons, pmsl_levels[self.resolution], 'navy', zorder=20)
        cr = self.plot_map.draw_contourf(rain_only, lats, lons, phase_levels, cmap_list=cmap_phase['rain'], extend='max', zorder=10)
        cs = self.plot_map.draw_contourf(snow_only, lats, lons, phase_levels, cmap_list=cmap_phase['snow'], extend='max', zorder=10)
        cm = self.plot_map.draw_contourf(mixed, lats, lons, phase_levels, cmap_list=cmap_phase['mixed'], extend='max', zorder=10)
        cfs = {'rain': cr, 'snow': cs, 'mixed': cm}

        for label in pm.labelTexts:
            label.set_zorder(30)

        x0 = 0.86  # стартовая позиция первой полосы
        cbar_width = 0.02  # ширина каждой полосы
        cbar_height = 0.65  # высота полос
        cbar_y = 0.17  # нижняя граница полос
        cbar_pad = 0.06  # расстояние между полосами

        for i, key in enumerate(['rain', 'snow', 'mixed']):
            cbar_cfg = {
                "cax": [
                    x0 + i * (cbar_width + cbar_pad),
                    cbar_y,
                    cbar_width,
                    cbar_height
                ],
                "orientation": "vertical",
                "label": phase_labels[key]
            }

            self.plot_map.draw_colorbar(
                c=cfs[key],
                cbar=cbar_cfg,
                levels=phase_levels
            )

        self.plot_map.save(f"{self.model.name}_{self.resolution}_phase_{lead_time}")
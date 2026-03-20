import os
from typing import Tuple, Iterable

import metpy.calc
import numpy
import numpy as np
import numpy.ma as ma
import xarray
from funcy import retry
from scipy.ndimage import zoom
from wrf import interplevel
import metpy.calc as mpcalc
from metpy.units import units
import wrf

path = ""
filename = ""
fileprefix = ""


def select_path(name: str, prefix: str) -> None:
    global path
    global fileprefix
    path = name
    fileprefix = prefix


def select_grib_file(name: str) -> None:
    global filename
    filename = os.path.join(path, name)


def model_fileset(start_min, stop_min, step_min) -> Iterable[int]:
    day_hours = 24 * 60
    for i in range(start_min, stop_min, step_min):
        days = i // day_hours
        hours = (i - days * day_hours) // 60
        minutes = i - (days * day_hours + hours * 60)

        select_grib_file(f"{fileprefix}{days:02d}{hours:02d}{minutes:02d}00")
        print(f"{days:02d}{hours:02d}{minutes:02d}")
        yield i


class BaseData:
    def __init__(self):
        global filename
        if not filename:
            select_grib_file(f"{fileprefix}00000000")

    @property
    def lats(self) -> xarray.DataArray:
        ds = self._get_ds("s", {"typeOfLevel": "surface"}, name=f"{fileprefix}00000000")
        return ds["latitude"]

    @property
    def lons(self) -> xarray.DataArray:
        ds = self._get_ds("s", {"typeOfLevel": "surface"}, name=f"{fileprefix}00000000")
        return ds["longitude"]

    @property
    def hhl(self) -> xarray.DataArray:
        if fileprefix == "lfff":
            ds = self._get_ds("c", {"typeOfLevel": "hybrid"}, name=f"{fileprefix}00000000")
        else:
            ds = self._get_ds("c", {"typeOfLevel": "generalVertical"}, name=f"{fileprefix}00000000")
        return ds["HHL"]

    @property
    def hsurf(self) -> xarray.DataArray:
        ds = self._get_ds("c", {"typeOfLevel": "surface"}, name=f"{fileprefix}00000000")
        return ds["HSURF"]

    @property
    def h_agl(self) -> xarray.DataArray:
        height = self.hhl - self.hsurf
        h_coord = height["hybrid"]
        t_stag = height[:-1]
        t_stag["hybrid"] = h_coord[:-1]
        b_stag = height[1:]
        b_stag["hybrid"] = h_coord[:-1]
        half_height = b_stag + (t_stag - b_stag) / 2
        return half_height[::-1, :, :]

    @property
    def hfl(self) -> xarray.DataArray:
        height = self.hhl
        try:
            h_coord = height["hybrid"]
            level_type = "hybrid"
        except KeyError:
            h_coord = height["generalVertical"]
            level_type = "generalVertical"
        t_stag = height[:-1]
        t_stag[level_type] = h_coord[:-1]
        b_stag = height[1:]
        b_stag[level_type] = h_coord[:-1]
        half_height = b_stag + (t_stag - b_stag) / 2
        return half_height

    @retry(9, errors=(FileNotFoundError, EOFError), timeout=lambda a: 3 ** a)
    def _get_ds(self, suffix, filter_keys, *, name="") -> xarray.Dataset:
        global filename
        global path
        if fileprefix == "lgfff":
            suffix += ".grb"
            if filter_keys.get("typeOfLevel") == "generalVerticalLayer":
                suffix = ".grb"
        if name:
            open_file = os.path.join(path, name)
        else:
            open_file = filename
        print(f"{open_file}{suffix}")
        return xarray.open_dataset(
            f"{open_file}{suffix}", engine='cfgrib', chunks=None, cache=True,
            backend_kwargs={
                'filter_by_keys': filter_keys,
                'indexpath': '',
                'encode_cf': ("time", "geography", "vertical")
            }
        )


class ModelParam(BaseData):
    def __init__(
        self,
        suffix,
        *,
        param: str = "",
        param_name: str = 'unknown',
        level_type: str = "",
        short_name: str = "",
        step_type: str = "",
        level: int = None,
    ):
        super().__init__()
        self._suffix = suffix
        self._param = param
        self._param_name = param_name
        self._level_type = level_type
        self._level = level
        self._step_type = step_type
        self._short_name = short_name

    def _get_array(self) -> xarray.DataArray:
        filter_keys = {}
        if self._param:
            filter_keys = {'param': self._param}
        if self._level_type:
            filter_keys['typeOfLevel'] = self._level_type
        if self._level:
            filter_keys['level'] = self._level
        if self._step_type:
            filter_keys['stepType'] = self._step_type
        if self._short_name:
            filter_keys['shortName'] = self._short_name
        da = self._get_ds(self._suffix, filter_keys)
        return da[self._param_name]

    def read_from_current_file(self) -> xarray.DataArray:
        """
        Читает параметр из УЖЕ выбранного filename.
        НИЧЕГО не переключает.
        """
        filter_keys = {}
        if self._param:
            filter_keys = {'param': self._param}
        if self._level_type:
            filter_keys['typeOfLevel'] = self._level_type
        if self._level:
            filter_keys['level'] = self._level
        if self._step_type:
            filter_keys['stepType'] = self._step_type
        if self._short_name:
            filter_keys['shortName'] = self._short_name

        ds = self._get_ds(self._suffix, filter_keys)
        return ds[self._param_name]

    @property
    def values(self) -> numpy.ndarray:
        return self._get_array().values

    @property
    def array(self) -> xarray.DataArray:
        return self._get_array()

    @property
    def agl_values(self) -> numpy.ndarray:
        ag_levels = (11, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000)
        array = self._get_array()
        i_array = interplevel(array[::-1, :, :], self.h_agl, ag_levels)

        return i_array.values

    def smoothed_values(self, smooth_value: int = 15) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        array = self._get_array()
        y_max, x_max,  = array.shape
        if y_max % smooth_value == 0 and x_max % smooth_value == 0:
            array_zoom = array
        else:
            y_zoom = self._calc_shape(y_max, smooth_value)
            x_zoom = self._calc_shape(x_max, smooth_value)
            array_zoom = array[:y_zoom, :x_zoom]
        shape = array_zoom.shape
        transform = array_zoom.values.reshape(shape[0] // smooth_value, smooth_value, shape[1] // smooth_value, smooth_value)
        values = zoom(transform.mean(axis=(1, 3)), smooth_value)
        lons = array_zoom.longitude.values
        lats = array_zoom.latitude.values
        if len(lons.shape) == 1:
            lons, lats = numpy.meshgrid(lons, lats)
        return values, lons, lats

    def _calc_shape(self, shape: int, factor: int) -> int:
        return ((shape // factor) - 1) * factor


class ModelData(BaseData):
    def __init__(self):
        super().__init__()

    @property
    def time(self) -> ModelParam:
        return ModelParam("s", level_type="surface", param_name="time")

    @property
    def vabsmx_10m(self) -> ModelParam:
        return ModelParam("s", param='216.201')

    @property
    def u(self) -> ModelParam:
        return ModelParam("sw", level_type="generalVerticalLayer", param_name="U", short_name="U")

    @property
    def u_h_levels(self) -> ModelParam:
        return ModelParam("z", level_type="heightAboveSea", param_name="U", short_name="U")

    @property
    def v_h_levels(self) -> ModelParam:
        return ModelParam("z", level_type="heightAboveSea", param_name="V", short_name="V")

    @property
    def v(self) -> ModelParam:
        return ModelParam("sw", level_type="generalVerticalLayer", param_name="V", short_name="V")

    @property
    def capeml(self) -> ModelParam:
        return ModelParam("sw", level_type="atmML", param_name="CAPE_ML")

    @property
    def capemu(self) -> ModelParam:
        return ModelParam("sw", level_type="atmMU", param_name="CAPE_MU")

    @property
    def cinml(self) -> ModelParam:
        return ModelParam("sw", level_type="atmML", param_name="CIN_ML")

    @property
    def lclml(self) -> ModelParam:
        return ModelParam("sw", level_type="unknown", param_name="LCL_ML")

    @property
    def pmsl(self) -> ModelParam:
        return ModelParam("s", level_type="meanSea", param_name="PMSL")

    @property
    def tot_prec(self) -> ModelParam:
        return ModelParam("s", level_type="surface", param_name="TOT_PREC")

    @property
    def dbz_ctmax(self) -> ModelParam:
        return ModelParam("dbz", level_type="entireAtmosphere", param_name="DBZ_CTMAX")

    @property
    def dbz_ctmax2(self) -> ModelParam:
        return ModelParam("dbz", level_type="entireAtmosphere", param_name="DBZ_CTMAX")

    @property
    def lpi_max(self) -> ModelParam:
        return ModelParam("dbz", level_type="surface", param_name="LPI_MAX")

    @property
    def sdi_2(self) -> ModelParam:
        return ModelParam("sw", level_type="surface", param_name="SDI_2")

    @property
    def dhail_avg(self) -> ModelParam:
        return ModelParam("hail", level_type="surface", param_name="unknown")

    @property
    def vmax_10m(self) -> ModelParam:
        return ModelParam("sw", level_type="heightAboveGround", param_name="VMAX_10M", level=10)

    @property
    def u_10m(self) -> ModelParam:
        return ModelParam("s", level_type="heightAboveGround", param_name="U_10M", level=10)

    @property
    def v_10m(self) -> ModelParam:
        return ModelParam("s", level_type="heightAboveGround", param_name="V_10M", level=10)

    @property
    def sp_10m(self) -> ModelParam:
        return ModelParam("dbz", level_type="heightAboveGround", param_name="SP_10M", level=10)

    @property
    def t_2m(self) -> ModelParam:
        return ModelParam("s", param='11.2', param_name="T_2M")

    @property
    def t_2m_grb2(self) -> ModelParam:
        return ModelParam("s", level_type="heightAboveGround", param_name="T_2M", level=2)

    @property
    def td_2m(self) -> ModelParam:
        return ModelParam("s", level_type="heightAboveGround", param_name="TD_2M", level=2)

    @property
    def rh_2m(self) -> ModelParam:
        return ModelParam("s", level_type="heightAboveGround", param_name="RELHUM_2M", level=2)

    # @property
    # def w(self) -> ModelParam:
    #     return ModelParam("", param="40.2", param_name="W")
    #
    # @property
    # def qv_cosmo(self) -> ModelParam:
    #     return ModelParam("", param="51.2", param_name="QV")

    # @property
    # def w_so(self) -> ModelParam:
    #     return ModelParam("", param="198.201", param_name="unknown")
    #
    # @property
    # def qv_icon(self) -> ModelParam:
    #     return ModelParam("", level_type="generalVerticalLayer", param_name="QV", short_name="QV")
    #
    # @property
    # def t(self) -> ModelParam:
    #     return ModelParam("", level_type="generalVerticalLayer", param_name="T", short_name="T")
    #
    # @property
    # def p(self) -> ModelParam:
    #     return ModelParam("", level_type="generalVerticalLayer", param_name="P", short_name="P")

    @property
    def ps(self) -> ModelParam:
        return ModelParam("s", level_type="surface", param_name="PS")

    @property
    def rain_gsp(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="RAIN_GSP")

    @property
    def rain_con(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="RAIN_CON")

    @property
    def snow_gsp(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="SNOW_GSP")

    @property
    def snow_con(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="SNOW_CON")

    def t_lvl(self, level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="T")

    def fi_lvl(self,  level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="FI")

    def rh_lvl(self,  level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="RELHUM")

    def u_lvl(self,  level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="U")

    def v_lvl(self,  level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="V")

    def w_lvl(self,  level: int) -> ModelParam:
        return ModelParam("pl", level_type="isobaricInhPa", level=level, param_name="W")

    @property
    def vis(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="VIS")

    @property
    def clcl(self) -> ModelParam:
        return ModelParam("s", level_type="isobaricLayer", level=800, param_name="CLCL")

    @property
    def clcm(self) -> ModelParam:
        return ModelParam("s", level_type="isobaricLayer", level=400, param_name="CLCM")

    @property
    def clch(self) -> ModelParam:
        return ModelParam("s", level_type="isobaricLayer", level=0, param_name="CLCH")

    @property
    def clct(self) -> ModelParam:
        return ModelParam("s", level_type="surface", level=0, param_name="CLCT")

    @property
    def hbas_con(self) -> ModelParam:
        return ModelParam("s", level=0, param_name="HBAS_CON", short_name="HBAS_CON")

    @property
    def htop_con(self) -> ModelParam:
        return ModelParam("s", level=0, param_name="HTOP_CON", short_name="HTOP_CON")

    @property
    def ceiling(self) -> ModelParam:
        return ModelParam("s", level=0, param_name="CEILING", short_name="CEILING")

    def all_required_params(self) -> list:
        """
        Возвращает список всех ModelParam, которые нужно загрузить.
        Включает параметры на разных уровнях и поверхностные параметры.
        """
        levels = [500, 700, 850]  # уровни для t_lvl, u_lvl, v_lvl
        params = []

        for lvl in levels:
            params.append(self.t_lvl(lvl))
            params.append(self.u_lvl(lvl))
            params.append(self.v_lvl(lvl))

        params.extend([self.t_2m_grb2, self.td_2m, self.u_10m, self.v_10m,
        # #     self.tot_prec,
            self.pmsl,
        ])

        return params

    def nearest(self, lat: float, lon: float, lats: np.ndarray,lons: np.ndarray) -> Tuple[int, int]:
        dist_sq = (lats - lat) ** 2 + (lons - lon) ** 2
        idx = dist_sq.argmin()
        y, x = np.unravel_index(idx, lats.shape)
        return y, x

    def load_all_modeldata_files(self, lat: float, lon: float, hours: int = 48):
        """
        Загружает значения параметров в одной точке (lat, lon)
        на диапазон часов прогноза.
        """
        data_cache = {}

        y_idx = x_idx = None
        coords_initialized = False

        for h in range(0, hours + 1):
            file_h = f"{fileprefix}{h // 24:02d}{h % 24:02d}0000"

            try:
                select_grib_file(file_h)
            except Exception as e:
                print(f"Файл {file_h} не найден:", e)
                continue

            for param in self.all_required_params():
                try:
                    da = param.read_from_current_file()
                    if da is None:
                        continue

                    # 🔹 координаты определяем ОДИН РАЗ
                    if not coords_initialized:
                        y_idx, x_idx = self.nearest(lat, lon, da.latitude.values, da.longitude.values)
                        coords_initialized = True

                    # 🔹 сразу берём одно значение
                    value = da.isel(y=y_idx, x=x_idx).values.item()

                    param_name = getattr(param, "_param_name", None)
                    level = getattr(param, "_level", None)

                    # 🔹 формируем ключ
                    if param_name in {"T", "U", "V"} and level is not None:
                        key = f"{param_name}{level}"
                    else:
                        key = param_name

                    if key not in data_cache:
                        data_cache[key] = []

                    data_cache[key].append(value)

                except Exception as e:
                    print("Ошибка при чтении", param, e)

        # превращаем списки в numpy-массивы
        for key in data_cache:
            data_cache[key] = np.array(data_cache[key])

        return data_cache


class ComputedModelData(ModelData):
    def __init__(self, name):
        super().__init__()
        self.name = name

    @property
    def stp(self) -> numpy.ndarray:
        # if self.name == "ICON":
        #     shear, srh = self._calc_effective_bwd_srh()
        #     return (self.capeml.values / 1500) * ((2000 - self.lclml.values) / 1000) \
        #         * (srh / 150) * (shear / 20) * ((250 + self.cinml.values) / 200)

        shear, srh1km, srh3km = self._calc_shear()
        return (self.capeml.values / 1500) * ((2000 - self.lclml.values) / 1000) \
               * (srh1km / 100) * (shear / 20) * ((250 + self.cinml.values) / 200)

    @property
    def scp(self) -> numpy.ndarray:
        shear, srh1km, srh3km = self._calc_shear()
        capeml = self.capeml.values
        brn = (capeml / (0.5 * numpy.square(shear)))
        return (self.capemu.values / 1000) * (srh3km / 100) * (brn / 40)

    def _calc_shear(self) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        """
        levels = 11,500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500,6000
        """
        if self.name == "ICON":
            u = self.u_h_levels.values
            v = self.v_h_levels.values
        else:
            u = self.u.agl_values
            v = self.v.agl_values

        u_shear = u[12, :, :] - u[0, :, :]
        v_shear = v[12, :, :] - v[0, :, :]
        shear = numpy.sqrt(numpy.square(u_shear) + numpy.square(v_shear))
        u_motion = numpy.mean(u, axis=0) + (7.5 / shear) * v_shear
        v_motion = numpy.mean(v, axis=0) - (7.5 / shear) * u_shear
        srh_3km = numpy.zeros(u_motion.shape)
        srh_1km = numpy.zeros(u_motion.shape)
        for i in range(1, 7):
            srh_3km += (u[i] - u_motion) * (v[i - 1] - v_motion) \
                       - (u[i - 1] - u_motion) * (v[i] - v_motion)
            if i <= 2:
                srh_1km += (u[i] - u_motion) * (v[i - 1] - v_motion) \
                           - (u[i - 1] - u_motion) * (v[i] - v_motion)
        return shear, srh_1km, srh_3km

    def _calc_effective_bwd_srh(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        effective inflow layer: CAPE >= 100 J/kg and CIN >= -250 J/kg
        """
        p = self.p.values
        t = self.t.values
        qv = self.qv_icon.values
        height = self.hfl.values
        terrain = self.hsurf.values
        psfc = self.ps.values
        u = self.u.values
        v = self.v.values

        cape, cin = wrf.cape_3d(self._to_hpa(p), t, qv, height, terrain, self._to_hpa(psfc), ter_follow=True)

        effective_layer_condition = ~((cape >= 100) & (cin >= -250))

        effective_p = ma.masked_where(effective_layer_condition, p)
        top_level = numpy.argmin(effective_p, axis=0)
        bottom_level = numpy.argmax(effective_p, axis=0)

        j, k = np.indices(top_level.shape)
        u_top = u[top_level, j, k]
        v_top = v[top_level, j, k]
        u_bottom = u[bottom_level, j, k]
        v_bottom = v[bottom_level, j, k]

        u_shear = u_top - u_bottom
        v_shear = v_top - v_bottom
        ebwd = numpy.sqrt(numpy.square(u_shear) + numpy.square(v_shear))
        ebwd = np.clip(ebwd, None, 30)
        ebwd = np.where(ebwd < 12.5, 0, ebwd)

        effective_u = ma.masked_where(effective_layer_condition, u)
        effective_v = ma.masked_where(effective_layer_condition, v)

        p_difference = p[top_level, j, k] - p[bottom_level, j, k]
        u_weighted = numpy.trapz(effective_u, x=effective_p, axis=0) / p_difference
        v_weighted = numpy.trapz(effective_v, x=effective_p, axis=0) / p_difference

        u_rdev = (7.5 / ebwd) * v_shear
        v_rdev = (7.5 / ebwd) * u_shear

        u_motion = u_weighted + u_rdev
        v_motion = v_weighted - v_rdev

        esrh = numpy.zeros(u_motion.shape)
        for i in range(effective_u.shape[0] - 1):
            esrh += (u_weighted[i] - u_motion) * (v_weighted[i + 1] - v_motion) \
                    - (u_weighted[i + 1] - u_motion) * (v_weighted[i] - v_motion)

        return ebwd, esrh

    def _to_hpa(self, values: np.ndarray) -> np.ndarray:
        return values / 100

    def dbz(self, lead_time) -> numpy.ndarray:
        return self._concatenate_values(lead_time, 'dbz_ctmax2').values

    def lpi(self, lead_time) -> numpy.ndarray:
        return self._concatenate_values(lead_time, 'lpi_max').values

    def max_wind(self, lead_time) -> xarray.DataArray:
        return self._concatenate_values(lead_time, 'sp_10m')

    def _concatenate_values(self, lead_time, parameter, step_minutes=10):
        global filename
        base_name = filename
        start_hour = int(lead_time) - 1
        end_hour = int(lead_time)
        values = getattr(self, parameter).array
        for _ in model_fileset(start_hour * 60 + step_minutes, end_hour * 60, step_minutes):
            values = xarray.concat([values, getattr(self, parameter).array], "time")
        select_grib_file(base_name)
        return values.max(dim="time")

    def get_cloud(self, level: str):
        short = level.upper()
        if short == 'CLCT':
            ds = self._get_ds("s",{'shortName': 'CLCT', 'typeOfLevel': 'surface'})
            return ds['CLCT']
        layer_map = {'CLCL': 800, 'CLCM': 400, 'CLCH': 0}
        ds = self._get_ds("s", {'shortName': short, 'typeOfLevel': 'isobaricLayer',
                                  'level': layer_map[short]})
        return ds[short]
from eccodes import codes_grib_new_from_file, codes_get, codes_get_double_element, codes_release
import os
import numpy as np
import matplotlib.pyplot as plt
from lib.cosmo import ModelData, select_path
from helpers import set_paths
from datetime import datetime, timedelta
import locale
from collections import defaultdict
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.ticker import FixedLocator
import json
import time
from multiprocessing import Pool, cpu_count
import sys
from transliterate import translit

locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")

# ============ КОНСТАНТЫ ============
S_MAP = {"totprec": 0, "ws10": 5, "vmax10": 11, "pmsl": 10, "htop_con": 2, "hbas_con": 1, "td2m": 9, "u10": 3,
         "v10": 4, "t2m": 8, "snow_gsp": 7, "snow_con": 6}
PL_MAP = {"T925": 3, "T850": 2, "U500": 4, "V500": 8, "U700": 5, "V700": 9, "U850": 6, "V850": 10}
Z_MAP = {"U500m": 0, "V500m": 1}
C_MAP = {"HSURF": 0}
CCL_ID, H_ID, LAYERS = 260257, 3008, 65
W, H = 3507, 2481


def detect_grid_type(path):
    test_file = f"{path}/lgfff00000000m.grb"
    with open(test_file, "rb") as f:
        gid = codes_grib_new_from_file(f)
        if gid is not None:
            try:
                npoints = codes_get(gid, "numberOfPoints")
                grid_type = codes_get(gid, "gridType")
                codes_release(gid)

                if npoints == 301500 and grid_type == "rotated_ll":
                    return "ICON_2.2"
                elif npoints == 1127061 and grid_type == "regular_ll":
                    return "ICON_6.6"
                else:
                    print(f"Неизвестная сетка: npoints={npoints}, gridType={grid_type}")
                    return "unknown"
            except:
                codes_release(gid)
                return "unknown"
    return "unknown"


def get_filename(path, prefix, suffix, hour, day=0):
    return os.path.join(path, f"{prefix}{day:02d}{hour:02d}0000{suffix}.grb")


def get_point_index(model, lat, lon):
    if hasattr(model.lats, 'values'):
        lats = model.lats.values
        lons = model.lons.values
    else:
        lats = model.lats
        lons = model.lons

    if lats.ndim == 2:
        lats_2d = lats
        lons_2d = lons
        nx = lats.shape[1]
    else:
        lats_2d, lons_2d = np.meshgrid(lats, lons, indexing='ij')
        if hasattr(model, 'Nx'):
            nx = model.Nx
        else:
            nx = len(lons)

    dist = (lats_2d - lat) ** 2 + (lons_2d - lon) ** 2
    y, x = np.unravel_index(np.argmin(dist), dist.shape)
    idx = y * nx + x
    return y, x, idx, nx


def get_start_date(path):
    with open(f"{path}/lgfff00000000m.grb", "rb") as f:
        gid = codes_grib_new_from_file(f)
        y, m, d, h = codes_get(gid, "year"), codes_get(gid, "month"), codes_get(gid, "day"), codes_get(gid,
                                                                                                       "dataTime") // 100
        codes_release(gid)
    return datetime(y, m, d, h)


def read_file_point(grib_file, msg_map, idx):
    result, wanted = {}, set(msg_map.values())
    msg_to_name = {v: k for k, v in msg_map.items()}
    with open(grib_file, "rb") as f:
        msg_no = 0
        while wanted:
            gid = codes_grib_new_from_file(f)
            if gid is None: break
            try:
                if msg_no in wanted:
                    result[msg_to_name[msg_no]] = codes_get_double_element(gid, "values", idx)
                    wanted.remove(msg_no)
            finally:
                codes_release(gid)
            msg_no += 1
    return result


def load_series(path, prefix, suffix, msg_map, idx, nx, hours=49, is_prec=False, y=None, x=None, ny=None):
    hours_list = range(hours)
    num_files = hours

    if is_prec:
        series = []
        for idx_time, h in enumerate(hours_list):
            fname = get_filename(path, prefix, suffix, h % 24, h // 24)
            window = np.full((3, 3), np.nan, dtype=np.float32)
            with open(fname, "rb") as f:
                msg_no = 0
                while True:
                    gid = codes_grib_new_from_file(f)
                    if gid is None: break
                    try:
                        if msg_no == msg_map["totprec"]:
                            for dy in (-1, 0, 1):
                                for dx in (-1, 0, 1):
                                    idx2 = (y + dy) * nx + (x + dx)
                                    window[dy + 1, dx + 1] = codes_get_double_element(gid, "values", idx2)
                            break
                    finally:
                        codes_release(gid)
                    msg_no += 1
            series.append(window)
        return np.array(series, dtype=np.float32)

    elif msg_map == "ccl_h":
        ccl_all = np.empty((num_files, LAYERS), dtype=np.float32)
        h_all = np.empty((num_files, LAYERS), dtype=np.float32)
        for idx_time, h in enumerate(hours_list):
            fname = get_filename(path, prefix, suffix, h % 24, h // 24)
            ccl = np.full(LAYERS, np.nan, dtype=np.float32)
            h_vals = np.full(LAYERS, np.nan, dtype=np.float32)
            with open(fname, "rb") as f:
                while True:
                    gid = codes_grib_new_from_file(f)
                    if gid is None: break
                    try:
                        pid, level = codes_get(gid, "paramId"), codes_get(gid, "topLevel") - 1
                        if level < LAYERS and pid in (CCL_ID, H_ID):
                            val = codes_get_double_element(gid, "values", idx)
                            if pid == CCL_ID:
                                ccl[level] = val
                            else:
                                h_vals[level] = val
                    finally:
                        codes_release(gid)
            ccl_all[idx_time] = ccl
            h_all[idx_time] = h_vals
        return ccl_all, h_all

    else:
        data = {name: np.empty(num_files, dtype=np.float32) for name in msg_map}
        for idx_time, h in enumerate(hours_list):
            fname = get_filename(path, prefix, suffix, h % 24, h // 24)
            point = read_file_point(fname, msg_map, idx)
            for name, val in point.items():
                data[name][idx_time] = val
        return data


def cloud_to_score(cloud):
    score = np.full_like(cloud, 10, dtype=int)
    score[np.isnan(cloud)] = 10
    bins = [0, 5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 101]
    for i in range(10):
        score[(cloud >= bins[i]) & (cloud < bins[i + 1])] = i
    return score


def get_color(score):
    return ["#FFFFFF", "#DCEEFF", "#DCEEFF", "#DCEEFF", "#A4CEFF", "#A4CEFF",
            "#5F9EF5", "#5F9EF5", "#2E6FD1", "#2E6FD1", "#003D99"][int(score)] if not np.isnan(score) else "#FFFFFF"


def clean_cloud(arr):
    arr = np.array(arr, dtype=float)
    arr[(arr < 0) | (arr > 12000.001)] = np.nan
    return arr


def compute_tprec(series):
    tprec = np.zeros_like(series)
    tprec[0] = series[0]
    for i in range(1, len(series)):
        tprec[i] = series[i] - series[i - 1]
    return tprec


def px(x, y, w, h):
    return [
        x / W,
        y / H,
        w / W,
        h / H
    ]


def setup_axes(fig):
    pos = {
        "header": (274, 2322, 3016, 158),
        "wind": (274, 1908, 3014, 416),
        "temp": (274, 1608, 3014, 300),
        "cloud": (274, 1111, 3014, 416),
        "vngo": (274, 1041, 3014, 70),
        "press": (274, 671, 3014, 370),
        "wind10m": (274, 580, 3014, 92),
        "ground": (274, 210, 3014, 370),
        "legend": (274, 110, 3014, 140),
    }
    axes = {}
    for name, p in pos.items():
        ax = fig.add_axes(px(*p))
        if name == 'header':
            ax.axis("off")
        elif name == 'legend':
            ax.set_yticks([])
        axes[name] = ax
    return axes


def setup_header(ax, start_date, grid_type, station_name, header_coords):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(plt.Rectangle((0, 0.01), 0.999, 1, fill=False, linewidth=1))
    ax.plot([0.25, 0.25], [0.5, 1], 'k', lw=1)
    ax.plot([0.75, 0.75], [0.5, 1], 'k', lw=1)
    ax.plot([0, 1], [0.5, 0.5], 'k', lw=1)
    ax.text(0.125, 0.75, f"{header_coords}", ha="center", va="center")
    ax.text(0.5, 0.75, station_name, ha="center", va="center")

    # Выбор названия сетки
    if grid_type == "ICON_2.2":
        grid_name = "ICON 2.2 км"
    else:
        grid_name = "ICON 6.6 км"
    ax.text(0.875, 0.75, grid_name, ha="center", va="center")

    ax.text(0.5, 0.25, f"{start_date.strftime('%d %B %Y')} {start_date.hour:02d} UTC", ha="center", va="center")


def setup_common_axes(axes_list, start_date, ticks_3h):
    labels = [dt.strftime("%d %B") if dt.hour == 0 else str(dt.hour)
              for dt in [start_date + timedelta(hours=int(t)) for t in ticks_3h]]
    ticks_24h = np.arange((24 - start_date.hour) % 24, 49, 24)
    for ax in axes_list:
        ax.set_xlim(-0.5, 48.5)
        ax.set_xticks(ticks_3h)
        ax.set_xticklabels(labels, fontsize=8)
        ax.grid(which='major', axis='x', linestyle='--', linewidth=0.5, alpha=0.5, color='k')
        for x in ticks_24h:
            ax.axvline(x=x, color='black', linestyle='--', linewidth=1, alpha=0.7, zorder=10)


def draw_meteogram(path, lat, lon, station_name, header_coords, output_dir=None, grid_type=None):
    if grid_type is None:
        grid_type = detect_grid_type(path)

    if grid_type == "unknown":
        print(f"Не удалось определить тип сетки для {path}, пропускаем")
        return

    select_path(path, "lgfff")
    model = ModelData()
    y, x, idx, nx = get_point_index(model, lat, lon)
    start_date = get_start_date(path)
    season = "warm" if 4 <= start_date.month <= 9 else "cold"

    series_s = load_series(path, "lgfff", "m", S_MAP, idx, nx,)
    series_pl = load_series(path, "lgfff", "p", PL_MAP, idx, nx)
    series_z = load_series(path, "lgfff", "h", Z_MAP, idx, nx)

    if hasattr(model.lats, 'values'):
        ny = model.lats.values.shape[0] if model.lats.values.ndim == 2 else len(model.lats.values)
    else:
        ny = model.lats.shape[0] if model.lats.ndim == 2 else len(model.lats)

    prec_series = load_series(path, "lgfff", "m", S_MAP, idx, nx, is_prec=True, y=y, x=x, ny=ny)
    hsurf = read_file_point(f"{path}/lgfff00000000c.grb", C_MAP, idx)["HSURF"]
    ccl_profile, h_profile = load_series(path, "lgfff", "clc", "ccl_h", idx, nx)


    time = np.arange(49)
    ticks_3h = np.arange(0, 49, 3)

    fig = plt.figure(figsize=(11.69, 8.27), dpi=300)
    axes = setup_axes(fig)
    setup_header(axes['header'], start_date, grid_type, station_name, header_coords)

    # ===== ВЕТЕР =====
    levels = {"500m": 0, "850": 1, "700": 2, "500": 3}
    ax = axes['wind']

    for level in levels:
        u = series_z["U500m"] if level == "500m" else series_pl[f"U{level}"]
        v = series_z["V500m"] if level == "500m" else series_pl[f"V{level}"]
        ax.barbs(time, np.full_like(time, levels[level]), 1.94384 * u, 1.94384 * v, length=5, linewidth=0.7)

    ax.set(xlim=(-0.5, 48.5), ylim=(-0.5, max(levels.values()) + 0.8), xticks=ticks_3h, xticklabels=[])
    ax.set_yticks(list(levels.values()))
    ax.set_yticklabels(['500 м', '850 гПа', '700 гПа', '500 гПа'], fontsize=8)
    ax.tick_params(axis='y', labelsize=8)

    ax_wind_right = ax.twinx()
    ax_wind_right.set_ylim(ax.get_ylim())
    ax_wind_right.set_yticks(ax.get_yticks())
    ax_wind_right.set_yticklabels(ax.get_yticklabels())
    ax_wind_right.tick_params(axis='y', labelsize=8)

    # ===== ТЕМПЕРАТУРА =====
    ax = axes['temp']
    ax.plot(time, series_s["t2m"] - 273, 'r')
    ax.plot(time, series_pl["T925"] - 273, color='orangered', linestyle='-.')
    ax.plot(time, series_pl["T850"] - 273, color='darkorange', linestyle=(0, (10, 5)))
    ax.set(xlim=(-0.5, 48.5), xticks=ticks_3h, xticklabels=[], ylim=(-40, 20) if season == 'cold' else (-30, 40))
    ax.tick_params(axis='y', labelsize=8)
    ax.grid(which='major', axis='y', linestyle='--', linewidth=0.5, alpha=0.5)
    ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.7)
    ax.set_xticks(np.arange(0, 49, 1), minor=True)

    ax_temp_right = ax.twinx()
    ax_temp_right.set_ylim(ax.get_ylim())
    ax_temp_right.tick_params(axis='y', labelsize=8)

    # ===== ОБЛАЧНОСТЬ =====
    ax = axes['cloud']

    # for y_pos in range(2, 11, 2):
    #     ax.axhline(y=y_pos, color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
    ax.set(xlim=(-0.5, 48.5), ylim=(0, 12), xticklabels=[])
    ax.tick_params(axis='y', labelsize=8)

    if grid_type == 'ICON_2.2':
        width = 1
        dx = 0
    else:
        width = 0.5
        dx = -0.25

    for t in range(ccl_profile.shape[0]):
        for z0 in range(12):
            vals = ccl_profile[t][(h_profile[t] / 1000 > z0) & (h_profile[t] / 1000 <= z0 + 1)]
            vals = vals[vals >= 5]
            if len(vals):
                ax.bar(t + dx, 1.0, bottom=z0, width=width,
                       color=get_color(cloud_to_score(vals.mean())), edgecolor="none", zorder=0)

    if grid_type == "ICON_6.6":
        hbas_con = clean_cloud(series_s["hbas_con"]) - hsurf
        htop_con = clean_cloud(series_s["htop_con"]) - hsurf
        hbas_con_km = hbas_con / 1000
        htop_con_km = htop_con / 1000
        ax.bar(time + 0.25, (htop_con_km - hbas_con_km),
               bottom=hbas_con_km, width=width, facecolor='none', alpha=0.6,
               edgecolor='darkorange', linewidth=1, hatch='\\\\\\\\')

    ax_cloud_right = ax.twinx()
    ax_cloud_right.set_ylim(ax.get_ylim())
    ax_cloud_right.tick_params(axis='y', labelsize=8)
    ax = axes["vngo"]

    lowest_height = np.full(len(time), np.nan)

    for hour in range(len(time)):

        mask = (
                (h_profile[hour] > 0) &
                (h_profile[hour] <= 1000) &
                np.isfinite(h_profile[hour]) &
                np.isfinite(ccl_profile[hour]) &
                (ccl_profile[hour] >= 5)
        )

        idx = np.where(mask)[0]

        if len(idx):
            lowest_idx = idx[np.argmin(h_profile[hour, idx])]
            lowest_height[hour] = h_profile[hour, lowest_idx]

    for i, height in enumerate(lowest_height):
        if np.isfinite(height):
            ax.text(
                i,
                0.5,
                str(int(round(height))),
                fontsize=7,
                ha="center",
                va="center",
                rotation=45
            )

    ax.set(
        xlim=(-.5, 48.5),
        ylim=(0, 1),
        xticks=ticks_3h,
        xticklabels=[],
        yticks=[]
    )
    # ===== ДАВЛЕНИЕ =====
    ax = axes['press']
    ax.plot(time, series_s["pmsl"] / 100, 'k', linewidth=1.7)
    ax.barbs(time, np.full_like(time, 995), 1.94384 * series_s["u10"], 1.94384 * series_s["v10"], length=5,
             linewidth=0.7)
    major_ticks = np.arange(985, 1041, 10)
    ax.set(xlim=(-0.5, 48.5), ylim=(985, 1045), xticklabels=[], yticks=major_ticks,
           yticklabels=[str(t) for t in major_ticks])
    ax.yaxis.set_minor_locator(FixedLocator(np.arange(990, 1041, 10)))
    ax.tick_params(axis='y', which='major', length=6)
    ax.tick_params(axis='y', which='minor', length=3)
    ax.tick_params(axis='y', labelsize=8)
    ax.grid(which='major', axis='y', linestyle='--', linewidth=0.5, alpha=0.5)

    ax_press_right = ax.twinx()
    ax_press_right.set_ylim(985, 1045)
    ax_press_right.set_yticks(major_ticks)
    ax_press_right.set_yticklabels([str(t) for t in major_ticks])
    ax_press_right.yaxis.set_minor_locator(FixedLocator(np.arange(990, 1041, 10)))
    ax_press_right.tick_params(axis='y', which='major', length=6)
    ax_press_right.tick_params(axis='y', which='minor', length=3)
    ax_press_right.tick_params(axis='y', labelsize=8)

    # ===== ВЕТЕР 10М =====
    ax = axes['wind10m']
    ws10, vmax10 = np.round(series_s["ws10"]).astype(int), np.round(series_s["vmax10"]).astype(int)
    for i, (w, g) in enumerate(zip(ws10, vmax10)):
        ax.text(i, 0.65, str(w), fontsize=7, ha='center')
        ax.text(i, 0.15, str(g), fontsize=7, ha='center')
    ax.set(xlim=(-0.5, 48.5), xticks=ticks_3h, xticklabels=[], ylim=(0, 1), yticks=[])
    ax.axhline(y=0.5, color='k', linestyle='-', linewidth=0.5)

    # ===== ПРИЗЕМНЫЙ СЛОЙ =====
    ax = axes['ground']

    ax.set_ylim(0, 20)  # было 20, стало 15
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)

    tprec = compute_tprec(series_s["totprec"])
    tprec_plot = np.where(np.round(tprec, 1) < 0.1, np.nan, tprec)
    tprec_clipped = np.clip(tprec_plot, None, 15)  # None = нет минимума

    bars = ax.bar(time, tprec_clipped, width=1, color="green", alpha=0.8,
                  edgecolor='k', linewidth=0.5, zorder=3)

    snow = compute_tprec(series_s["snow_gsp"] + series_s["snow_con"])
    snow = np.where(np.round(snow, 1) < 0.1, np.nan, snow)
    snow_clipped = np.clip(snow, None, 15)

    ax.bar(time, snow_clipped, width=1, color="blue", alpha=0.8, zorder=4)

    for prec_bar, prec_val in zip(bars, tprec_plot):
        if not np.isnan(prec_val):
            ax.text(prec_bar.get_x() + prec_bar.get_width() / 2, 18, f"{prec_val:.1f}",
                    ha="center", va="bottom", fontsize=6.5, color="black", style='italic')

    ax1 = ax.twinx()

    t2m = series_s["t2m"] - 273
    td2m = series_s["td2m"] - 273

    ax1.plot(time, t2m, "r", zorder=10)
    ax1.plot(time, td2m, "g--", zorder=5)

    ax1.set(xlim=(-0.5, 48.5), xticks=ticks_3h, xticklabels=[],
            ylim=(-40, 20) if season == 'cold' else (-30, 40))

    ax1.tick_params(axis="y", labelsize=8, left=True, right=True, labelleft=True, labelright=True)
    ax1.yaxis.set_ticks_position("both")

    ax1.grid(which="major", axis="y", linestyle="--", linewidth=0.5, alpha=0.5)

    dates = [start_date + timedelta(hours=i) for i in range(len(t2m))]
    days = defaultdict(list)

    for i, dt in enumerate(dates):
        days[dt.date()].append((i, dt.hour))

    for values in days.values():
        for period, color, offset in [([i for i, h in values if 0 <= h < 12], 'red', 3),
                                      ([i for i, h in values if 12 <= h < 24], 'blue', -3)]:
            if len(period) >= 2:
                idx_val = period[np.argmax(t2m[period])] if color == 'red' else period[np.argmin(t2m[period])]
                dx = 0.5 if idx_val == period[0] else (-0.5 if idx_val == period[-1] else 0)
                x_pos = idx_val + dx
                ax1.text(x_pos, t2m[idx_val] + offset, f"{t2m[idx_val]:.1f}",
                        ha="center", va="bottom" if color == 'red' else "top",
                        fontsize=8, color=color,
                        bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                                  edgecolor=color, alpha=0.5, linewidth=1), zorder=7)

    # ===== ЛЕГЕНДА =====
    ax = axes['legend']
    tprec_ser = np.where(np.round(compute_tprec(prec_series), 1) < 0.1, np.nan, compute_tprec(prec_series))
    cmap_prec = ListedColormap(['#aaF5aa', '#4FE74F', '#12B512', '#005A00'])
    norm_prec = BoundaryNorm([0.1, 1, 5, 15, 50], cmap_prec.N)
    size = 1
    cell = size / 3

    for h in range(tprec_ser.shape[0]):
        x0 = h - 0.5
        x1 = h + 0.5
        ax.imshow(tprec_ser[h], cmap=cmap_prec, norm=norm_prec, interpolation="none", origin="upper",
                  extent=[x0, x1, size, 0])

    ax.set_xlim(-0.5, 48.5)
    ax.set_xticks(ticks_3h)

    for h in range(tprec_ser.shape[0]):
        x0 = h - 0.5
        x1 = h + 0.5
        for i in range(4):
            ax.axvline(x0 + i * cell, color="black", linewidth=0.5, alpha=0.5)
            ax.hlines(y=i * cell, xmin=x0, xmax=x1, color="black", linewidth=0.2, alpha=0.5)

    ax.set_xticks(np.arange(0, 49, 1), minor=True)

    # ===== ФИНАЛЬНАЯ НАСТРОЙКА =====
    setup_common_axes([axes['cloud'], axes['ground'], axes['wind'], axes['temp'], axes['press'], axes['legend']],
                      start_date, ticks_3h)
    axes['legend'].xaxis.grid(False)
    for name in ['wind', 'ground', 'cloud', 'press', 'wind10m']:
        axes[name].tick_params(bottom=False, top=False, labelbottom=False)
    fig.text(1, 0, "©СибНИГМИ", ha="right", va="bottom", fontsize=10, zorder=60)

    # Сохраняем
    os.makedirs(output_dir, exist_ok=True)
    safe_name = translit(station_name, 'ru', reversed=True)
    safe_name = safe_name.replace(' ', '_').replace('(', '').replace(')', '')
    output_name = f"M_{grid_type}_{safe_name}.png"
    output_path = os.path.join(output_dir, output_name)
    plt.savefig(output_path, dpi=100)
    plt.close(fig)


GRID_RESOLUTION = {
    "ICON_2.2": "022",
    "ICON_6.6": "066",
}


def process_task(task):
    station, grid_name, DATA_DIR, M_DIR = task

    draw_meteogram(
        path=DATA_DIR,
        lat=station['lat'],
        lon=station['lon'],
        station_name=station['Название'],
        header_coords=station.get('Координаты', None),
        output_dir=M_DIR,
        grid_type=grid_name
    )


def run_from_config(path, conf_file='config_with_grids.json'):
    start_time = time.time()
    config_file = os.path.join(path, conf_file)

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    stations = config['stations']

    if os.environ.get('HOSTNAME') == "xfront2" and len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = "2024071100"

    tasks = []

    for station in stations:
        for grid_name in station.get('grids', []):

            resolution = GRID_RESOLUTION.get(grid_name)

            if resolution is None:
                continue

            DATA_DIR, _, M_DIR = set_paths("ICON", resolution, date)
            tasks.append((station, grid_name, DATA_DIR, M_DIR))

    total = len(tasks)
    print(f"\n{'=' * 60}")
    print(f"Начинаем генерацию {total} метеограмм")
    print(f"Используется ядер: {min(cpu_count(), len(tasks))}")
    print(f"{'=' * 60}\n")

    with Pool(processes=min(cpu_count(), total)) as pool:
        for i, _ in enumerate(pool.imap_unordered(process_task, tasks), 1):
            if i % max(1, total // 10) == 0 or i == total:
                elapsed = time.time() - start_time
                percent = i / total * 100
                eta = (elapsed / i) * (total - i) if i > 0 else 0
                print(f"\rПрогресс: {i}/{total} ({percent:.1f}%) | Прошло: {elapsed:.1f}с | Осталось: ~{eta:.1f}с",
                      end="", flush=True)

    total_time = time.time() - start_time
    print(f"\n\n{'=' * 60}")
    print(f"Готово! Сгенерировано {total} метеограмм")
    print(f"⏱️ Общее время: {total_time:.1f}с ({total_time / 60:.1f} мин)")
    print(f"📊 Среднее время на метеограмму: {total_time / total:.1f}с")
    print(f"{'=' * 60}")


# ============ ТОЧКА ВХОДА ============
if __name__ == "__main__":
    # Вариант 1: Запуск из конфигурационного файла
    from pathlib import Path

    path = Path(__file__).resolve().parent
    run_from_config(path)

    # Вариант 2: Запуск для одной станции (для отладки)
    #draw_meteogram('/home/vika/icon1707', 52.766, 87.826, 'Таштагол', 'Учебная')
    # draw_meteogram('/home/vika/icon071718kz', 54.973, 82.891, 'Новосибирск', 'Учебная')



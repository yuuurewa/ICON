import ftplib
import queue
import threading
import time
import os

import cartopy.crs as crs
import cartopy.feature as cf
import matplotlib.colors as mpl_colors
import matplotlib.pyplot as plt
from cartopy.io.shapereader import Reader
from matplotlib.cm import get_cmap
import matplotlib
matplotlib.use('agg')
from PIL import Image
from pathlib import Path

from constants import *


plt.rc('font', family='sans-serif')
plt.rc('font', serif='Helvetica Neue')


class BasePlot:
    _ftp_queue = queue.Queue()
    _ftp_thread = None
    _ftp_lock = threading.Lock()
    _ftp_stop = False

    FTP_HOST = "192.168.9.9"

    FTP_PASSWORDS = {
        "cosmo_phenom": "atyjvtys",
        "cosmo_lhn": "gjh5GHF54f",
        "icon2": "Kmq2026A!0",
        "icon6": "QzAXb@2026",
    }
    def __init__(self, path: str, date: str, ftp_user: str) -> None:
        self.path = path
        self.date = date
        self.ftp_user = ftp_user

    def create(self, text_left, text_right, description, fc_time, lead_time, resolution: float, right_pos=None):
        self.fig, self.ax = plt.subplots(figsize=self.figsize, dpi=200)
        self.fig.subplots_adjust(right=0.85)  # оставляем 15% справа для colorbar
        self.ax.axis('off')
        self.transform = crs.PlateCarree()

        self.ax = plt.axes(projection=self.proj)
        if resolution == 6.6:
            self.ax.set_extent(self.extent)
        self.ax.tick_params(right=False)

        shp_path = Path(__file__).resolve().parent.parent/"Adm_bound"/"Administrative_boundaries.shp"

        states = cf.ShapelyFeature(
            Reader(str(shp_path)).geometries(),
                                   self.transform, edgecolor='black', facecolor='none')
        self.ax.add_feature(states, linewidth=.5)

        for feature in [cf.RIVERS, cf.LAKES]:
            self.add_cfeature(feature)
        gl = self.ax.gridlines(draw_labels=True)
        gl.top_labels = False
        gl.right_labels = False

        # Add city point
        plt.rcParams.update({'font.size': 10})
        for c in self.cities:
            if c['lon'] < 84:
                alignment = 'right'
            else:
                alignment = 'left'
            self.ax.plot(c['lon'], c['lat'], marker='o', color='red', markersize=3, alpha=1,
                     transform=self.transform, zorder=40)  # transform=crs.Geodetic())
            self.ax.text(c['lon'], c['lat'] + 0.2, c['name'],
                     horizontalalignment=alignment,
                     transform=self.transform, zorder=50)  # transform=crs.Geodetic())

        for spine in self.ax.spines.values():
            spine.set_linewidth(1.5)
            spine.set_color('black')

        # self.ax.set_title(title, y=1.05)
        # Верхняя центральная часть (две строки разным шрифтом)
        if resolution == 2.2:
            f_height = 0.95
            s_height = 0.91
        else:
            f_height = 0.93
            s_height = 0.89

        if right_pos == None:
            right_pos = 0.97
        else:
            right_pos = right_pos

        if isinstance(self, Map6kmES):
            s_height = 0.895
            self.fig.text(0.5, f_height, description, ha='center', va='top', fontsize=14)
            self.fig.text(0.5, s_height, fc_time, ha='center', va='top', fontsize=12)
            self.fig.text(0.05, f_height, text_left, ha='left', va='top', fontsize=11)
            self.fig.text(right_pos, f_height, f'{text_right} +{lead_time}', ha='right', va='top', fontsize=11)
        else:
            self.fig.text(0.5, f_height, description, ha='center', va='top', fontsize=13)
            self.fig.text(0.5, s_height, fc_time, ha='center', va='top', fontsize=12)
            self.fig.text(0.05, f_height, text_left, ha='left', va='top', fontsize=10)
            self.fig.text(right_pos, f_height, f'{text_right} +{lead_time}', ha='right', va='top', fontsize=10)

    def add_cfeature(self, feature):
        self.ax.add_feature(feature, alpha=0.7, edgecolor='royalblue', linewidth=1.5)

    def draw_contourf(self, geom, lats, lons, levels, *, cm=None, cmap_list=None, extend='both', opacity=0.7, **kwargs):
        if cmap_list is not None:
            # если cmap_list — объект colormap (LinearSegmentedColormap), используем напрямую
            if isinstance(cmap_list, mpl_colors.Colormap):
                cmap = cmap_list
            else:
                # иначе создаём ListedColormap
                if extend == 'both':
                    cmap = mpl_colors.ListedColormap(cmap_list[1:-1])
                    cmap.set_under(cmap_list[0])
                    cmap.set_over(cmap_list[-1])
                elif extend == 'max':
                    cmap = mpl_colors.ListedColormap(cmap_list[:-1])
                    cmap.set_over(cmap_list[-1])
                else:
                    cmap = mpl_colors.ListedColormap(cmap_list)
        else:
            # если cmap передан как объект или строка
            cmap = cm if isinstance(cm, mpl_colors.Colormap) else get_cmap(cm)

        norm = mpl_colors.BoundaryNorm(levels, cmap.N)
        return self.ax.contourf(lons, lats, geom, 0, cmap=cmap, norm=norm, alpha=opacity, levels=levels,
                                transform=self.transform,
                                transform_first=True,
                                extend=extend)

    def draw_colorbar(self, c, cbar, levels, extend=None):
        ticks = np.array(levels, dtype=float).copy()
        if "cax" in cbar.keys():
            colorbar_ax = self.fig.add_axes(cbar["cax"])

            colorbar = self.fig.colorbar(c, cax=colorbar_ax, orientation=cbar["orientation"],
                                    ticks=ticks, extend=extend)  # , extend='both')
        else:
            colorbar = self.fig.colorbar(c, ax=self.ax, orientation=cbar["orientation"], ticks=ticks, extend=extend)

        colorbar.set_label(cbar["label"])
        colorbar.ax.tick_params(labelsize=9)

        return colorbar

    def draw_contour(self, geom, lats, lons, levels, color, linewidth=1, linestyles='solid', clabel=True, **kwargs):
        c = self.ax.contour(
            lons, lats, geom, 0,
            colors=color,
            linewidths=linewidth,
            linestyles=linestyles,
            negative_linestyles=linestyles, antialiased=True,
            levels=levels,
            alpha=0.7,
            transform=self.transform,
            transform_first=True
        )
        if clabel:
            labels = self.ax.clabel(c, c.levels, fmt="%d", inline=True, fontsize=8.5)
            for label in labels:
                label.set_bbox(dict(facecolor='white', edgecolor='none', pad=1))
        return c

    def draw_barbs(self, u, v, lats, lons, scale):
        self.ax.barbs(lons[::scale, ::scale], lats[::scale, ::scale], u[::scale, ::scale], v[::scale, ::scale],
                  transform=self.transform, rounding=False, barb_increments=dict(half=2, full=5, flag=24),
                  length=4, sizes=dict(emptybarb=0.05, spacing=0.2, height=0.7), alpha=0.35, linewidth=0.7, color='k')

    def draw_scatter(self, size, lats, lons):
        size = np.where(size > 0.001, size.values, np.nan)
        if np.count_nonzero(~np.isnan(size)) > 10:
            self.ax.scatter(lons, lats, s=size * 1000, c="white", marker='o',
                        linewidths=1, edgecolors="black", transform=self.transform)

    def _chdir(self, ftp, dir):
        if self._directory_exists(ftp, dir) is False:
            ftp.mkd(dir)
        ftp.cwd(dir)

    def _directory_exists(self, ftp, dir):
        filelist = []
        ftp.retrlines('LIST', filelist.append)
        for f in filelist:
            if f.split()[-1] == dir and f.upper().startswith('D'):
                return True
        return False

    def _ftp_send(self, filename, name):
        p = {
            "cosmo_phenom": "atyjvtys",
            "cosmo_lhn": "gjh5GHF54f",
            "icon2": "Kmq2026A!0",
            "icon6": "QzAXb@2026",
        }
        session = ftplib.FTP('192.168.9.9', self.ftp_user, p[self.ftp_user])
        file = open(filename, 'rb')
        self._chdir(session, self.date)
        session.storbinary(f'STOR {name}', file)  # send the file
        file.close()
        session.quit()

    def save(self, name, type=None, image_type=None, upload_ftp=True):
        if type == 'm':
            name = f"{name}.png"
            filename = os.path.join(self.path, name)
            self.fig.savefig(filename, format="png", dpi=200,
                pil_kwargs={
                    "quality": 85,
                    "optimize": True,
                    "progressive": True
                })
        else:
            name = f"{name}hour.jpg"
            filename = os.path.join(self.path, name)
            self.ax.text(1, 0, "©СибНИГМИ", transform=self.ax.transAxes, ha="right", va="bottom", fontsize=11,
                         zorder=60)
            # if image_type == "tiff":
            #     self.fig.savefig('{}.tiff'.format(filename), dpi=650, format="tiff", pil_kwargs={"compression": "tiff_lzw"})
            # else:
            self.fig.savefig(filename, format="jpg", dpi=200, bbox_inches='tight',
                pil_kwargs={
                    "quality": 85,
                    "optimize": True,
                    "progressive": True
                })
            #self.fig.savefig(filename, dpi=300, bbox_inches='tight')

        plt.cla()
        # plt.clf()
        plt.close()


        if upload_ftp and os.environ.get('HOSTNAME') == "xfront2":
            try:
                self._ftp_send(filename, name)
            except Exception as e:
                print("FTP transfer failed")
                print(e)

        return filename

    @classmethod
    def _ftp_worker(cls):
        while True:
            task = cls._ftp_queue.get()
            try:
                if task is None:
                    return

                filename, name, ftp_user, remote_dir = task
                password = cls.FTP_PASSWORDS.get(ftp_user)

                if password is None:
                    print(f"FTP: неизвестный пользователь {ftp_user}")
                    continue

                for attempt in range(1, 6):
                    ftp = None
                    try:
                        ftp = ftplib.FTP(timeout=60)
                        ftp.connect(cls.FTP_HOST)
                        ftp.login(ftp_user, password)
                        ftp.set_pasv(True)

                        cls._ftp_makedirs(ftp, remote_dir)

                        if cls._ftp_is_up_to_date(ftp, filename, name):
                            print(f"FTP: актуальный файл, пропуск {name}")
                            break

                        with open(filename, "rb") as file:
                            ftp.storbinary(f"STOR {name}", file)

                        print(f"FTP: отправлен {name}")
                        break

                    except Exception as exc:
                        print(
                            f"FTP: ошибка отправки {name}, "
                            f"попытка {attempt}/5: {exc}"
                        )

                        if attempt == 5:
                            print(f"FTP: окончательная ошибка для {name}")
                        else:
                            time.sleep(3 * (1.5 ** (attempt - 1)))

                    finally:
                        if ftp is not None:
                            try:
                                ftp.quit()
                            except Exception:
                                ftp.close()

            finally:
                cls._ftp_queue.task_done()

    @staticmethod
    def _ftp_makedirs(ftp, remote_dir):
        path = remote_dir.replace("\\", "/")
        current = "/" if path.startswith("/") else ""

        for part in path.strip("/").split("/"):
            if not part:
                continue

            current = (
                current.rstrip("/") + "/" + part
                if current
                else part
            )

            try:
                ftp.cwd(current)
            except ftplib.error_perm:
                try:
                    ftp.mkd(current)
                except ftplib.error_perm:
                    pass

                ftp.cwd(current)

    @staticmethod
    def _ftp_is_up_to_date(ftp, filename, name):
        try:
            response = ftp.sendcmd(f"MDTM {name}")

            if not response.startswith("213 "):
                return False

            remote_time = time.strptime(
                response[4:18], "%Y%m%d%H%M%S"
            )
            remote_timestamp = time.mktime(remote_time) - time.timezone

            return remote_timestamp >= os.path.getmtime(filename)

        except Exception:
            return False

    @classmethod
    def queue_ftp_upload(cls, filename, ftp_user, remote_dir):
        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)

        with cls._ftp_lock:
            if cls._ftp_thread is None or not cls._ftp_thread.is_alive():
                cls._ftp_thread = threading.Thread(
                    target=cls._ftp_worker,
                    daemon=False,
                )
                cls._ftp_thread.start()

        cls._ftp_queue.put((
            filename,
            os.path.basename(filename),
            ftp_user,
            remote_dir,
        ))

    @classmethod
    def wait_ftp_uploads(cls):
        with cls._ftp_lock:
            thread = cls._ftp_thread

            if thread is None:
                return

            cls._ftp_queue.join()
            cls._ftp_queue.put(None)

        thread.join()

        with cls._ftp_lock:
            cls._ftp_thread = None


class Map2km(BasePlot):

    extent = (71, 93, 50, 58)
    cent_lat = 57
    cent_lon = 70
    figsize = (14, 9)
    proj = crs.NearsidePerspective(central_latitude=cent_lat, central_longitude=cent_lon)
    cities = (
        {"name": "Кемерово", "lat": 55.35, "lon": 86.09},
        {"name": "Новосибирск", "lat": 55.02, "lon": 82.94},
        {"name": "Барабинск", "lat": 55.34, "lon": 78.3},
        {"name": "Татарск", "lat": 55.19, "lon": 75.96},
        {"name": "Карасук", "lat": 53.73, "lon": 78},
        {"name": "Кыштовка", "lat": 56.55, "lon": 76.58},
        {"name": "Омск", "lat": 54.58, "lon": 73.23},
        {"name": "Томск", "lat": 56.48, "lon": 84.96},
        {"name": "Красноярск", "lat": 56.008, "lon": 92.87},
        {"name": "Абакан", "lat": 53.720, "lon": 91.442},
        {"name": "Новокузнецк", "lat": 53.75, "lon": 87.13},
        {"name": "Барнаул", "lat": 53.34, "lon": 83.77},
        {"name": "Горно-Алтайск", "lat": 51.95, "lon": 85.95},
        {"name": "Онгудай", "lat": 50.75, "lon": 86.13},
        {"name": "Кош-Агач", "lat": 50.0, "lon": 88.66},
        {"name": "Камень-на-Оби", "lat": 53.79, "lon": 81.35},
        {"name": "Бийск", "lat": 52.53, "lon": 85.21},
        {"name": "Юрга", "lat": 55.7, "lon": 84.93},
        {"name": "Таштагол", "lat": 52.75, "lon": 87.85},
        {"name": "Мариинск", "lat": 56.2, "lon": 87.76},
        {"name": "Рубцовск", "lat": 51.52, "lon": 81.22},
        {"name": "Усть-Каменогорск", "lat": 49.95, "lon": 82.6},

    )


class Kushva(BasePlot):

    extent = (50, 68, 51, 61)
    cent_lat = 56.2
    cent_lon = 60.3
    figsize = (14, 9)
    proj = crs.NearsidePerspective(central_latitude=cent_lat, central_longitude=cent_lon)
    cities = (
         {"name": "Челябинск", "lat": 55.159, "lon": 61.402},
         {"name": "Екатеринбург", "lat": 56.838, "lon": 60.597},
         {"name": "Курган", "lat": 55.444, "lon": 65.316},
         {"name": "Тюмень", "lat": 57.153, "lon": 65.534},
         {"name": "Уфа", "lat": 54.62, "lon": 55.81},
         {"name": "Кушва", "lat": 58.28, "lon": 59.74},
#         {"name": "Норильск", "lat": 69.349, "lon": 88.201},
#         {"name": "Тура", "lat": 64.276, "lon": 100.198},
#         {"name": "Красноярск", "lat": 56.008, "lon": 92.87},
#         {"name": "Абакан", "lat": 53.720, "lon": 91.442},
#         {"name": "Кызыл", "lat": 51.719, "lon": 94.437},
#         {"name": "Иркутск", "lat": 52.286, "lon": 104.280},
#         {"name": "Чита", "lat": 52.034, "lon": 113.499},
#         {"name": "Якутск", "lat": 62.027, "lon": 129.704},
#         {"name": "Барнаул", "lat": 53.21, "lon": 83.47},
#         {"name": "Горно-Алтайск", "lat": 51.57, "lon": 85.58},
#         {"name": "Кемерово", "lat": 55.2, "lon": 86.04},
#         {"name": "Новосибирск", "lat": 55.02, "lon": 82.8},
#         {"name": "Омск", "lat": 54.58, "lon": 73.23},
#         {"name": "Томск", "lat": 56.29, "lon": 84.57}
     )


class Map6kmKz(BasePlot):

    extent = (51, 127, 42, 71)
    proj = crs.Miller(central_longitude=78)
    cent_lat = 80
    cent_lon = 78
    # proj = crs.NearsidePerspective(central_latitude=cent_lat, central_longitude=cent_lon)
    figsize = (14, 9)
    cities = (
        {"name": "Челябинск", "lat": 55.159, "lon": 61.402},
        {"name": "Екатеринбург", "lat": 56.838, "lon": 60.597},
        {"name": "Курган", "lat": 55.444, "lon": 65.316},
        {"name": "Тюмень", "lat": 57.153, "lon": 65.534},
        {"name": "Салехард", "lat": 66.549, "lon": 66.6083},
        {"name": "Ханты-Мансийск", "lat": 61.002, "lon": 69.018},
        {"name": "Норильск", "lat": 69.349, "lon": 88.201},
        {"name": "Тура", "lat": 64.276, "lon": 100.198},
        {"name": "Красноярск", "lat": 56.008, "lon": 92.87},
        {"name": "Абакан", "lat": 53.720, "lon": 91.442},
        {"name": "Кызыл", "lat": 51.719, "lon": 94.437},
        {"name": "Иркутск", "lat": 52.286, "lon": 104.280},
        {"name": "Чита", "lat": 52.034, "lon": 113.499},
        # {"name": "Якутск", "lat": 62.027, "lon": 129.704},
        {"name": "Барнаул", "lat": 53.21, "lon": 83.47},
        {"name": "Горно-Алтайск", "lat": 51.57, "lon": 85.58},
        {"name": "Кемерово", "lat": 55.2, "lon": 86.04},
        {"name": "Новосибирск", "lat": 55.02, "lon": 82.8},
        {"name": "Омск", "lat": 54.58, "lon": 73.23},
        {"name": "Томск", "lat": 56.29, "lon": 84.57},
        {"name": "Астана", "lat": 51.13, "lon": 71.43},
        {"name": "Улан-Батор", "lat": 47.92, "lon": 106.92},
    )


class Map6kmES(BasePlot):

    extent = (90, 122, 40, 74.5)
    proj = crs.Miller(central_longitude=78)
    cent_lat = 80
    cent_lon = 78
    # proj = crs.NearsidePerspective(central_latitude=cent_lat, central_longitude=cent_lon)
    figsize = (12, 16)
    cities = (
        {"name": "Тура", "lat": 64.276, "lon": 100.198},
        {"name": "Красноярск", "lat": 56.008, "lon": 92.87},
        {"name": "Абакан", "lat": 53.720, "lon": 91.442},
        {"name": "Кызыл", "lat": 51.719, "lon": 94.437},
        {"name": "Иркутск", "lat": 52.286, "lon": 104.280},
        {"name": "Чита", "lat": 52.034, "lon": 113.499},
        {"name": "Улан-Батор", "lat": 47.92, "lon": 106.92},
    )


# class Map6kmWS(BasePlot):
#
#     extent = (70, 108, 40, 74)
#     proj = crs.Miller(central_longitude=78)
#     cent_lat = 80
#     cent_lon = 78
#     # proj = crs.NearsidePerspective(central_latitude=cent_lat, central_longitude=cent_lon)
#     figsize = (14, 9)
#     cities = (
#         {"name": "Норильск", "lat": 69.349, "lon": 88.201},
#         {"name": "Тура", "lat": 64.276, "lon": 100.198},
#         {"name": "Красноярск", "lat": 56.008, "lon": 92.87},
#         {"name": "Абакан", "lat": 53.720, "lon": 91.442},
#         {"name": "Кызыл", "lat": 51.719, "lon": 94.437},
#         {"name": "Иркутск", "lat": 52.286, "lon": 104.280},
#         {"name": "Барнаул", "lat": 53.21, "lon": 83.47},
#         {"name": "Горно-Алтайск", "lat": 51.57, "lon": 85.58},
#         {"name": "Кемерово", "lat": 55.2, "lon": 86.04},
#         {"name": "Новосибирск", "lat": 55.02, "lon": 82.8},
#         {"name": "Омск", "lat": 54.58, "lon": 73.23},
#         {"name": "Томск", "lat": 56.29, "lon": 84.57},
#         {"name": "Астана", "lat": 51.13, "lon": 71.43},
#         {"name": "Улан-Батор", "lat": 47.92, "lon": 106.92},
#     )
import numpy as np

pmsl_levels = {2.2: np.arange(900., 1100., 2.), 6.6: np.arange(900., 1100., 5.)}
t_levels = np.arange(-45., 35., 2.)
level_temp = {
    ("warm", 6.6, 1000): (0, 35),
    ("warm", 6.6, 925): (-5, 30),
    ("warm", 6.6, 850): (-5, 25),
    ("warm", 6.6, 700): (-20, 0),
    ("warm", 6.6, 500): (-55, -10),
    ("warm", 6.6, 300): (-65, -40),

    ("warm", 2.2, 1000): (5, 30),
    ("warm", 2.2, 925): (0, 25),
    ("warm", 2.2, 850): (0, 20),
    ("warm", 2.2, 700): (-15, 0),
    ("warm", 2.2, 500): (-50, -10),
    ("warm", 2.2, 300): (-65, -40),

    ("cold", 6.6, 1000): (-40, 5),
    ("cold", 6.6, 925): (-40, 10),
    ("cold", 6.6, 850): (-40, 0),
    ("cold", 6.6, 700): (-50, -10),
    ("cold", 6.6, 500): (-60, -20),
    ("cold", 6.6, 300): (-70, -45),

    ("cold", 2.2, 1000): (-40, 5),
    ("cold", 2.2, 925): (-40, 5),
    ("cold", 2.2, 850): (-40, -5),
    ("cold", 2.2, 700): (-50, -15),
    ("cold", 2.2, 500): (-60, -25),
    ("cold", 2.2, 300): (-70, -50),
}

fi_levels = {300: np.arange(800, 1000, 4), 500: np.arange(450, 650, 4), 700: np.arange(200, 400, 4),
             850: np.arange(100, 200, 4), 925: np.arange(0, 100, 4), 1000: np.arange(-100, 100, 4)}

levels_rh = np.arange(0, 101, 10)

cloud_levels = np.arange(10, 100., 10.)
dcloud_levels = np.arange(100, 5000., 1000.)
stp_levels = (0.1, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 7, 10)
scp_levels = np.arange(1, 11., 1)

gust_cmap = (
            'white', '#E0F3FC', '#9EDBF7', '#00DD00', '#A1E72E', '#FFFF98', '#FAE95C', '#FDB061', '#F46D41', '#D63C4E',
            '#772584', '#4376B5', '#BBB6B1', 'black'
        )
cl_desc = {'clcl': 'нижнего', 'clcm': 'среднего', 'clch': 'верхнего', 'clct': 'Общая облачность (%)'}
cl_lvl = [0, 10, 30, 50, 70, 90, 100]
type_cloud = ['hbas_con', 'htop_con', 'ceiling']
levels_cl_cov = np.concatenate([np.arange(0, 1500, 150), np.arange(1500, 12001, 1500)])
cl_cov_colors = [
    "#980a0a",  # 150
    "#660033",  # 300
    "#194b94",  # 450
    "#2c78a0",  # 600
    "#489f91",  # 750
    "#75c475",  # 900
    "#a6e480",  # 1050
    "#f7c065",  # 1200
    "#f7ce5a",  # 1350
    "#f7da4f",  # 1500
    "#f7e343",  # 3000
    "#f7ea38",  # 4500
    "#e0d977",  # 6000
    "#cabe88",  # 7500
    "#b5b1a6",  # 9000
    "#a3a3a3",  # 10500
    "#c7c7c7"   # 12000
]

phase_levels = [0.001, 0.1, 1, 2, 5, 10, 15, 25]
cmap_phase = {'rain': ['#99ff99', '#66ff66', '#33cc33', '#009900','#007700', '#005500', '#003300', '#001a00'],
         'snow': ['#99d6ff', '#66c2ff', '#3399ff', '#007acc', '#0066b3', '#004c99', '#003366', '#001933'],
         'mixed': ['#d9b3ff', '#c080ff', '#a64dff', '#8c1aff', '#7300e6', '#5900b3', '#400080', '#1a0040']}
phase_labels = {
    'rain':  'Дождь, мм',
    'snow':  'Снег, мм',
    'mixed': 'Смешанные, мм'
}
wind_h300_cmap = (
    '#E6E6E6', '#99e6ff', '#33c2ff', '#90EE90', '#FFFF98', '#FAE95C', '#FDB061', '#F46D41', '#D63C4E',
    '#2E5D99', '#bd33a4', '#8B4513', 'black'
)
wind_h300_levels = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
levels_vis = np.concatenate([np.arange(0, 1500, 150), np.arange(1500, 10001, 2125)])
vis_colors = [
    '#7F0000',  # 0–150
    '#A50000',  # 150–300
    '#C91400',  # 300–450
    '#E83800',  # 450–600
    '#FF6600',  # 600–750
    '#FF8C00',  # 750–900
    '#FFA500',  # 900–1050
    '#FFC04D',  # 1050–1200
    '#FFE6A0',  # 1200–1500
    '#4B4B4B',  # 1500–2000
    '#808080',  # 2000–4000
    '#A9A9A9',  # 4000–6000
    '#C0C0C0',  # 6000–8000
    '#E6E6E6'   # 8000–10000
]
gust_bounds = (7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35, 37.5)

dbz_cmap = (
            "#cccccc", "#78899A", "#88CFFA", "#04e9e7", "#019ff4", "#0300f4", "#02fd02",
            "#01c501", "#008e00", "#fdf802", "#e5bc00", "#fd9500", "#fd0000", "#d40000",
            "#bc0000", "#f800fd", "#9854c6",
            "#8C3C2B"
        )
dbz_bounds = (-50, -20, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70)
prec_bounds = [0.001, 0.1, 1, 2, 5, 10, 15, 25]
prec_cmap = ('#aaF5aa', '#97F58D', '#4FE74F', '#12B512', '#005A00', '#FFC139', '#FF6000', '#E20C00',
                            'darkred')

# sdi_threshold = 0.0031
sdi_threshold = 0.001
hail_cmap = ('white', '#C0EFFF', '#99DC2B', '#FEE18C', '#D63C4E', '#772584', "black")
hail_bounds = (1, 5, 10, 20, 30, 40)
lpi_cmap = ('white', 'greenyellow', 'yellowgreen', 'khaki', 'yellow', 'gold', 'orange', 'darkorange', 'darkred')
lpi_bounds = (1, 5, 10, 20, 50, 100, 200)
sdi_bounds = (-0.009, -0.003, -0.001, -0.0003, 0.0003, 0.001, 0.003, 0.009)

# cbar_h_left = {"cax": [0.1, 0.06, 0.35, 0.03], "orientation": "horizontal", "label": ""}
# cbar_h_right = {"cax": [0.5, 0.06, 0.35, 0.03], "orientation": "horizontal", "label": ""}
cbar_h_left = {"cax": [0.88, 0.14, 0.02, 0.35], "orientation": "vertical", "label": ""}
cbar_h_right = {"cax": [0.88, 0.5, 0.02, 0.35], "orientation": "vertical", "label": ""}
cbar_full = {
    # 6.6: {"cax": [0.1, 0.06, 0.8, 0.03], "orientation": "horizontal", "label": ""},
    # 2.2: {"cax": [0.1, 0.06, 0.8, 0.03], "orientation": "horizontal", "label": ""},
    2.2: {"cax": [0.88, 0.15, 0.02, 0.7], "orientation": "vertical", "label": ""},
    6.6: {"cax": [0.88, 0.15, 0.02, 0.7], "orientation": "vertical", "label": ""}
}


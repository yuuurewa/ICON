import numpy as np

pmsl_levels = np.arange(900., 1100., 3.)
t_levels = np.arange(-45., 35., 2.)
cloud_levels = np.arange(10, 100., 10.)
dcloud_levels = np.arange(100, 5000., 1000.)
stp_levels = (0.1, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 7, 10)
scp_levels = np.arange(1, 11., 1)

gust_cmap = (
            'white', '#E0F3FC', '#9EDBF7', '#00DD00', '#A1E72E', '#FFFF98', '#FAE95C', '#FDB061', '#F46D41', '#D63C4E',
            '#772584', '#4376B5', '#BBB6B1', 'black'
        )
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
cbar_h_left = {"cax": [0.9, 0.12, 0.02, 0.35], "orientation": "vertical", "label": ""}
cbar_h_right = {"cax": [0.9, 0.52, 0.02, 0.35], "orientation": "vertical", "label": ""}
cbar_full = {
    # 6.6: {"cax": [0.1, 0.06, 0.8, 0.03], "orientation": "horizontal", "label": ""},
    # 2.2: {"cax": [0.1, 0.06, 0.8, 0.03], "orientation": "horizontal", "label": ""},
    2.2: {"cax": [0.9, 0.15, 0.02, 0.7], "orientation": "vertical", "label": ""},
    6.6: {"cax": [0.9, 0.15, 0.02, 0.7], "orientation": "vertical", "label": ""}
}
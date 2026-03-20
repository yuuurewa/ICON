import os
import numpy
from datetime import datetime
from typing import Tuple

MODEL = ""


def set_paths(model: str, resolution: str, datestring: str) -> Tuple[str, str]:
    if model == "COSMO":
        if os.environ.get('HOSTNAME') == "xfront2":
            DATA_DIR = f"/RHM-Lustre2.1/RHM-M/users/cosmo/grivin/COSMO_SIB/OUTPUT/OUT{resolution}.{datestring}/CM_out_{datestring}"
            IMAGE_DIR = f"/RHM-Lustre2.1/RHM-M/users/cosmo/grivin/COSMO_SIB/OUTPUT/OUT{resolution}.{datestring}/maps"
        else:
            # DATA_DIR = f'/mnt/grivin/tmp/COSMO_SIB/OUTPUT/Konstantinovka/OUT{resolution}.{datestring}/CM_out_{datestring}'
            DATA_DIR = f'/mnt/grivin/COSMO_SIB/OUTPUT/OUT{resolution}.{datestring}/CM_out_{datestring}'
            IMAGE_DIR = f'maps/{datestring}/{resolution}'

    elif model == "COSMO_LHN":
        if os.environ.get('HOSTNAME') == "xfront2":
            DATA_DIR = f"/RHM-Lustre2.1/RHM-M/users/cosmo/grivin/COSMO_SIB/OUTPUT/OUT_LHN{resolution}.{datestring}/CM_out_{datestring}"
            IMAGE_DIR = f"/RHM-Lustre2.1/RHM-M/users/cosmo/grivin/COSMO_SIB/OUTPUT/OUT_LHN{resolution}.{datestring}/maps"
        else:
            # DATA_DIR = f'/mnt/grivin/tmp/COSMO_SIB/OUTPUT/Konstantinovka/OUT{resolution}.{datestring}/CM_out_{datestring}'
            DATA_DIR = f'/mnt/grivin/COSMO_SIB/OUTPUT/OUT{resolution}.{datestring}/CM_out_{datestring}'
            IMAGE_DIR = f'maps/{datestring}/{resolution}'

    elif model == "ICON":
        dom_folder = {"022": "RuSib2", "066": "RuSib6Kz"}
        if os.environ.get('HOSTNAME') == "xfront2":
            DATA_DIR = f'/RHM-Lustre2.1/RHM-NSK/users/sibnigmi/icon1/ICON-kOper/OUTPUT-2024.07/{datestring}/{dom_folder[resolution]}/LLGRID'
            IMAGE_DIR = f'/RHM-Lustre2.1/RHM-NSK/users/sibnigmi/icon1/ICON-kOper/OUTPUT-2024.07/{datestring}/{dom_folder[resolution]}/maps'
        else:
            # DATA_DIR = f'/mnt/icon1/ICON-kOper/OUTPUT-2024.07/{datestring}/{dom_folder[resolution]}/LLGRID'
            DATA_DIR = f'/mnt/icon1/RSCH_ICON/OUTPUT-oper/{datestring}/{dom_folder[resolution]}/LLGRID'
            IMAGE_DIR = f'maps/ICON/{datestring}/{resolution}'

    else:
        print("unknown model")
        raise NotImplementedError
    return DATA_DIR, IMAGE_DIR,


def initial_time(time: numpy.datetime64) -> datetime:
    return datetime.utcfromtimestamp(time.tolist()/1e9)

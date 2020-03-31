"""

Similar to clean_for_recovery, but this script does not delete anything.
It looks for detections in the entire data release and returns a list of detections that need to be re-run because they are:
1) missing (no entry in the report db)
2) have no imaging (empty Aperture table in the Elixer HDF5)
3) have no neighborhood map (no entry in the *_nei.db)
4) have no mini png (no entry in the *_mini.db)

"""


import numpy as np
import tables
import glob
import os
from hetdex_api.config import HDRconfig
import sqlite3
#from hetdex_api import sqlite_utils as sql

#todo: make configurable (which hdr version)
cfg = HDRconfig(survey="hdr2")

check_nei = False
check_mini = False
check_imaging = False


i = input("Check for no imaging (y/n)?")
if len(i) > 0 and i.upper() == "Y":
    check_imaging = True

i = input("Check for nei.png (y/n)?")
if len(i) > 0 and i.upper() == "Y":
    check_nei = True

i = input("Check for mini.png (y/n)?")
if len(i) > 0 and i.upper() == "Y":
    check_mini = True


print("Reading detecth5 file ...")
hetdex_h5 = tables.open_file(cfg.detecth5,"r")
dtb = hetdex_h5.root.Detections
alldets = dtb.read(field="detectid")
hetdex_h5.close()

print("Reading elixerh5 file ...")
#elixer_h5 = tables.open_file(cfg.elixerh5,"r") #"elixer_merged_cat.h5","r")
elixer_h5 = tables.open_file("/data/03261/polonius/hdr2/detect/elixer.h5","r")
dtb = elixer_h5.root.Detections
apt = elixer_h5.root.Aperture

ct_no_imaging = 0
ct_no_png = 0
ct_no_nei = 0
ct_no_mini = 0

missing = []
# no_nei = []
# no_mini = []
# no_imaging = []

all_rpts = []
all_nei = []
all_mini = []

#todo: open the various sqlite dbs and get the list of all detectids they have
#todo: make file locations automatic
#todo: add some error control
db_path = "/data/03261/polonius/hdr2/detect/image_db/"
#main reports
SQL_QUERY = "SELECT detectid from report;"

dbs = sorted(glob.glob(os.path.join(db_path,"elixer_reports_2*[0-9].db")))
for db in dbs:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    dets = cursor.fetchall()
    cursor.close()
    conn.close()
    all_rpts.extend([x[0] for x in dets])

dbs = sorted(glob.glob(os.path.join(db_path,"elixer_reports_2*nei.db")))
for db in dbs:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    dets = cursor.fetchall()
    cursor.close()
    conn.close()
    all_nei.extend([x[0] for x in dets])

dbs = sorted(glob.glob(os.path.join(db_path,"elixer_reports_2*mini.db")))
for db in dbs:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(SQL_QUERY)
    dets = cursor.fetchall()
    cursor.close()
    conn.close()
    all_mini.extend([x[0] for x in dets])

#this is slow enough, that the prints don't make an impact
#and they are a good progress indicator
for d in alldets:

    #check if exists
    if not (d in all_rpts):
        #does not exist
        print(f"{d} missing report: png ({ct_no_png}), nei ({ct_no_nei}), mini ({ct_no_mini}), img ({ct_no_imaging})")
        missing.append(d)
        ct_no_png += 1
        continue #already added so no need to check further

    if check_nei:
        if not (d in all_nei):
            # does not exist
            print(f"{d} missing neighborhood: png ({ct_no_png}), nei ({ct_no_nei}), mini ({ct_no_mini}), img ({ct_no_imaging})")
            missing.append(d)
            ct_no_nei += 1
            continue  # already added so no need to check further

    if check_mini:
        if not (d in all_mini):
            # does not exist
            print(f"{d} missing mini: png ({ct_no_png}), nei ({ct_no_nei}), mini ({ct_no_mini}), img ({ct_no_imaging})")
            missing.append(d)
            ct_no_mini += 1
            continue  # already added so no need to check further

    #most involved, so do this one last (since one of the above checks may have
    #already marked this one to be rerun)
    if check_imaging:
        rows = apt.read_where("detectid==d",field="detectid")
        if rows.size==0:
            print(f"{d} missing imaging: png ({ct_no_png}), nei ({ct_no_nei}), mini ({ct_no_mini}), img ({ct_no_imaging})")
            missing.append(d)
            ct_no_imaging += 1

elixer_h5.close()

print(f"{len(missing)} to be re-run")
print(f"{ct_no_png} no png")
print(f"{ct_no_nei} no nei")
print(f"{ct_no_mini} no mini")
print(f"{ct_no_imaging} no imaging")
np.savetxt("dets.rerun",missing,fmt="%d")


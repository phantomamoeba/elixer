from __future__ import print_function
#keep it simple for now. Put base class and all children in here.
#Later, create a proper package

#PATHS MUST END WITH /

#CANDELS_EGS_Stefanon_2016_BASE_PATH = "/work/03564/stevenf/maverick/EGS/"
CANDELS_EGS_Stefanon_2016_BASE_PATH = "/home/dustin/code/python/voltron/data/EGS/"
CANDELS_EGS_Stefanon_2016_CAT = CANDELS_EGS_Stefanon_2016_BASE_PATH+"/photometry/CANDELS.EGS.F160W.v1_1.photom.cat"
CANDELS_EGS_Stefanon_2016_IMAGES_PATH = CANDELS_EGS_Stefanon_2016_BASE_PATH + "images/"
CANDELS_EGS_Stefanon_2016_PHOTOZ_CAT = CANDELS_EGS_Stefanon_2016_BASE_PATH + "photoz/zcat_EGS_v2.0.cat"
CANDELS_EGS_Stefanon_2016_PHOTOZ_ZPDF_PATH = CANDELS_EGS_Stefanon_2016_BASE_PATH + "photoz/zPDF/"




import matplotlib
matplotlib.use('agg')

import pandas as pd
import global_config
import science_image
import numpy as np
import copy
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.gridspec as gridspec
#from astropy.io import ascii #note: this works, but pandas is much faster


log = global_config.logging.getLogger('Cat_logger')
log.setLevel(global_config.logging.DEBUG)

pd.options.mode.chained_assignment = None  #turn off warning about setting the distance field

#base class for catalogs (essentially an interface class)
#all Catalogs classes must implement:


def get_catalog_list():
    #build list of all catalogs below
    cats = list()
    cats.append(CANDELS_EGS_Stefanon_2016())

  #  cats.append(CANDELS_EGS_Stefanon_2016())
  #  cats[1].Name = "Duplicate CANDELS"
    return cats



__metaclass__ = type
class Catalog:
    MainCatalog = None
    Name = "Generic Catalog (Base)"
    df = None  # pandas dataframe ... all instances share the same frame
    df_photoz = None
    #tbl = None # astropy.io.table
    RA_min = None
    RA_max = None
    Dec_min = None
    Dec_max = None
    status = -1

    def __init__(self):
        self.pages = None #list of bid entries (rows in the pdf)

    @property
    def ok(self):
        return (self.status == 0)

    @property
    def name(self):
        return (self.Name)

    @classmethod
    def position_in_cat(cls, ra, dec, error = 0.0):  # error assumed to be small and this is approximate anyway
        """Simple check for ra and dec within a rectangle defined by the min/max of RA,DEC for the catalog.
        RA and Dec in decimal degrees.
        """
        if cls.ok:
            try:
                result = (ra >= (cls.RA_min - error)) and (ra <= (cls.RA_max + error))\
                         and (dec >= (cls.Dec_min - error)) and (dec <= (cls.Dec_max + error))
            except:
                result = False
        else:
            result = False
        return result

    @classmethod
    def get_dict(cls,id,cols):
        """returns a (nested) dictionary of desired cols for a single row from the full dataframe
            form {col_name : {id : value}}
        """
        try:
            bid_dict = cls.df.loc[id,cols].to_dict()
        except:
            log.error("Exception attempting to build dictionary for id %d" %id)
            return None
        return bid_dict

    def clear_pages(self):
        if self.pages is None:
            self.pages = []
        elif len(self.pages) > 0:
            del self.pages[:]

    def add_bid_entry(self, entry):
        if self.pages is None:
            self.clear_pages()
        self.pages.append(entry)


#specific implementation of The CANDELS-EGS Multi-wavelength catalog Stefanon et al., 2016
#CandlesEgsStefanon2016

class CANDELS_EGS_Stefanon_2016(Catalog):
#RA,Dec in decimal degrees

#photometry catalog
#  1 ID #  2 IAU_designation  #  3 RA  #  4 DEC #  5 RA_Lotz2008 (RA in AEGIS ACS astrometric system)  #  6 DEC_Lotz2008 (DEC in AEGIS ACS astrometric system)
#  7 FLAGS #  8 CLASS_STAR #  9 CFHT_U_FLUX  # 10 CFHT_U_FLUXERR # 11 CFHT_g_FLUX # 12 CFHT_g_FLUXERR # 13 CFHT_r_FLUX
# 14 CFHT_r_FLUXERR  # 15 CFHT_i_FLUX # 16 CFHT_i_FLUXERR # 17 CFHT_z_FLUX # 18 CFHT_z_FLUXERR # 19 ACS_F606W_FLUX
# 20 ACS_F606W_FLUXERR # 21 ACS_F814W_FLUX # 22 ACS_F814W_FLUXERR # 23 WFC3_F125W_FLUX # 24 WFC3_F125W_FLUXERR
# 25 WFC3_F140W_FLUX # 26 WFC3_F140W_FLUXERR # 27 WFC3_F160W_FLUX # 28 WFC3_F160W_FLUXERR # 29 WIRCAM_J_FLUX
# 30 WIRCAM_J_FLUXERR  # 31 WIRCAM_H_FLUX # 32 WIRCAM_H_FLUXERR # 33 WIRCAM_K_FLUX # 34 WIRCAM_K_FLUXERR
# 35 NEWFIRM_J1_FLUX # 36 NEWFIRM_J1_FLUXERR # 37 NEWFIRM_J2_FLUX # 38 NEWFIRM_J2_FLUXERR # 39 NEWFIRM_J3_FLUX # 40 NEWFIRM_J3_FLUXERR
# 41 NEWFIRM_H1_FLUX # 42 NEWFIRM_H1_FLUXERR # 43 NEWFIRM_H2_FLUX # 44 NEWFIRM_H2_FLUXERR # 45 NEWFIRM_K_FLUX# 46 NEWFIRM_K_FLUXERR
# 47 IRAC_CH1_FLUX # 48 IRAC_CH1_FLUXERR # 49 IRAC_CH2_FLUX # 50 IRAC_CH2_FLUXERR # 51 IRAC_CH3_FLUX # 52 IRAC_CH3_FLUXERR # 53 IRAC_CH4_FLUX
# 54 IRAC_CH4_FLUXERR # 55 ACS_F606W_V08_FLUX # 56 ACS_F606W_V08_FLUXERR # 57 ACS_F814W_V08_FLUX # 58 ACS_F814W_V08_FLUXERR
# 59 WFC3_F125W_V08_FLUX # 60 WFC3_F125W_V08_FLUXERR # 61 WFC3_F160W_V08_FLUX # 62 WFC3_F160W_V08_FLUXERR
# 63 IRAC_CH3_V08_FLUX # 64 IRAC_CH3_V08_FLUXERR # 65 IRAC_CH4_V08_FLUX # 66 IRAC_CH4_V08_FLUXERR # 67 DEEP_SPEC_Z

    #class variables
    MainCatalog = CANDELS_EGS_Stefanon_2016_CAT
    Name = "CANDELS_EGS_Stefanon_2016"
    WCS_Manual = True
    BidCols = ["ID","IAU_designation","RA","DEC",
               "CFHT_U_FLUX","CFHT_U_FLUXERR",
               "IRAC_CH1_FLUX","IRAC_CH1_FLUXERR","IRAC_CH2_FLUX","IRAC_CH2_FLUXERR",
               "ACS_F606W_FLUX","ACS_F606W_FLUXERR",
               "ACS_F814W_FLUX","ACS_F814W_FLUXERR",
               "WFC3_F125W_FLUX","WFC3_F125W_FLUXERR",
               "WFC3_F140W_FLUX","WFC3_F140W_FLUXERR",
               "WC3_F160W_FLUX","WFC3_F160W_FLUXERR",
               "DEEP_SPEC_Z"]  #NOTE: there are no F105W values

    CatalogImages = [
                {'path':CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name':'egs_all_acs_wfc_f606w_060mas_v1.1_drz.fits',
                 'filter':'f606w',
                 'instrument':'ACS WFC',
                 'cols':["ACS_F606W_FLUX","ACS_F606W_FLUXERR"],
                 'labels':["Flux","Err"]
                },
                {'path':CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name':'egs_all_acs_wfc_f814w_060mas_v1.1_drz.fits',
                 'filter':'f814w',
                 'instrument':'ACS WFC',
                 'cols':["ACS_F814W_FLUX","ACS_F814W_FLUXERR"],
                 'labels':["Flux","Err"]
                },
                {'path':CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name':'egs_all_wfc3_ir_f105w_060mas_v1.5_drz.fits',
                 'filter':'f105w',
                 'instrument':'WFC3',
                 'cols':[],
                 'labels':[]
                },
                {'path':CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name':'egs_all_wfc3_ir_f125w_060mas_v1.1_drz.fits',
                 'filter':'f125w',
                 'instrument':'WFC3',
                 'cols':["WFC3_F125W_FLUX","WFC3_F125W_FLUXERR"],
                 'labels':["Flux","Err"]
                },
                {'path':CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name':'egs_all_wfc3_ir_f140w_060mas_v1.1_drz.fits',
                 'filter':'f140w',
                 'instrument':'WFC3',
                 'cols':["WFC3_F140W_FLUX","WFC3_F140W_FLUXERR"],
                 'labels':["Flux","Err"]
                },
                {'path': CANDELS_EGS_Stefanon_2016_IMAGES_PATH,
                 'name': 'egs_all_wfc3_ir_f160w_060mas_v1.1_drz.fits',
                 'filter': 'f160w',
                 'instrument': 'WFC3',
                 'cols':["WFC3_F160W_FLUX","WFC3_F160W_FLUXERR"],
                 'labels':["Flux","Err"]
                }
               ]

# 1 file # 2 ID (CANDELS.EGS.F160W.v1b_1.photom.cat) # 3 RA (CANDELS.EGS.F160W.v1b_1.photom.cat) # 4 DEC (CANDELS.EGS.F160W.v1b_1.photom.cat)
# 5 z_best # 6 z_best_type # 7 z_spec # 8 z_spec_ref # 9 z_grism # 10 mFDa4_z_peak # 11 mFDa4_z_weight # 12 mFDa4_z683_low
# 13 mFDa4_z683_high # 14 mFDa4_z954_low # 15 mFDa4_z954_high # 16 HB4_z_peak # 17 HB4_z_weight # 18 HB4_z683_low
# 19 HB4_z683_high # 20 HB4_z954_low # 21 HB4_z954_high # 22 Finkelstein_z_peak # 23 Finkelstein_z_weight
# 24 Finkelstein_z683_low # 25 Finkelstein_z683_high # 26 Finkelstein_z954_low # 27 Finkelstein_z954_high
# 28 Fontana_z_peak # 29 Fontana_z_weight # 30 Fontana_z683_low # 31 Fontana_z683_high # 32 Fontana_z954_low
# 33 Fontana_z954_high # 34 Pforr_z_peak # 35 Pforr_z_weight # 36 Pforr_z683_low # 37 Pforr_z683_high
# 38 Pforr_z954_low # 39 Pforr_z954_high # 40 Salvato_z_peak # 41 Salvato_z_weight # 42 Salvato_z683_low
# 43 Salvato_z683_high # 44 Salvato_z954_low # 45 Salvato_z954_high # 46 Wiklind_z_peak # 47 Wiklind_z_weight
# 48 Wiklind_z683_low  # 49 Wiklind_z683_high # 50 Wiklind_z954_low # 51 Wiklind_z954_high # 52 Wuyts_z_peak
# 53 Wuyts_z_weight  # 54 Wuyts_z683_low # 55 Wuyts_z683_high # 56 Wuyts_z954_low # 57 Wuyts_z954_high

    PhotoZCatalog = CANDELS_EGS_Stefanon_2016_PHOTOZ_CAT
    SupportFilesLocation = CANDELS_EGS_Stefanon_2016_PHOTOZ_ZPDF_PATH

    def __init__(self):
        super(CANDELS_EGS_Stefanon_2016, self).__init__()

        self.dataframe_of_bid_targets = None
        self.dataframe_of_bid_targets_photoz = None
        #self.table_of_bid_targets = None
        self.num_targets = 0

        self.read_main_catalog()
        self.read_photoz_catalog()

        self.master_cutout= None


    @classmethod
    def read_main_catalog(cls):
        if cls.df is not None:
            log.debug("Already built df")
        else:
            try:
                print("Reading main catalog for ", cls.Name)
                cls.df = cls.read_catalog(cls.MainCatalog,cls.Name)
                cls.status = 0
                cls.RA_min = cls.df['RA'].min()
                cls.RA_max = cls.df['RA'].max()
                cls.Dec_min = cls.df['DEC'].min()
                cls.Dec_max = cls.df['DEC'].max()

                log.debug(cls.Name + " Coordinate Range: RA: %f to %f , Dec: %f to %f" % (cls.RA_min, cls.RA_max,
                                                                                          cls.Dec_min, cls.Dec_max))
            except:
                print("Failed")
                cls.status = -1

            if cls.df is None:
                cls.status = -1
        return

    @classmethod
    def read_photoz_catalog(cls):
        if cls.df_photoz is not None:
            log.debug("Already built df_photoz")
        else:
            try:
                print("Reading photoz catalog for ", cls.Name)
                cls.df_photoz = cls.read_catalog(cls.PhotoZCatalog,cls.Name)
            except:
                print("Failed")

        return


    @classmethod
    def read_catalog(cls,catalog_loc,name):

        log.debug("Building " + name + " dataframe...")
        idx = []
        header = []
        skip = 0
        try:
            f = open(catalog_loc, mode='r')
        except:
            log.error(name + " Exception attempting to open catalog file: " + catalog_loc, exc_info=True)
            return None


        line = f.readline()
        while '#' in line:
            skip += 1
            toks = line.split()
            if (len(toks) > 2) and toks[1].isdigit():   #format:   # <id number> <column name>
                idx.append(toks[1])
                header.append(toks[2])
            line = f.readline()

        f.close()

        try:
            df = pd.read_csv(catalog_loc, names=header,
                delim_whitespace=True, header=None, index_col=None, skiprows=skip)
        except:
            log.error(name + " Exception attempting to build pandas dataframe",exc_info=True)
            return None

        return df

    @classmethod
    def coordinate_range(cls,echo=False):
        if echo:
            msg = "RA (%f, %f)" % (cls.RA_min, cls.RA_max) + "Dec(%f, %f)" % (cls.Dec_min, cls.Dec_max)
            print( msg )
        log.debug(cls.Name + " Simple Coordinate Box: " + msg )
        return (cls.RA_min, cls.RA_max, cls.Dec_min, cls.Dec_max)


    def sort_bid_targets_by_likelihood(self,ra,dec):
        #right now, just by euclidean distance (ra,dec are of target)
        self.dataframe_of_bid_targets['distance'] = np.sqrt((self.dataframe_of_bid_targets['RA'] - ra)**2 +
                                                            (self.dataframe_of_bid_targets['DEC'] - dec)**2)
        self.dataframe_of_bid_targets = self.dataframe_of_bid_targets.sort_values(by='distance', ascending=True)

    def build_list_of_bid_targets(self,ra,dec,error):
        '''ra and dec in decimal degress. error in arcsec.
        returns a pandas dataframe'''

        #todo: explicity delete dataframes if they exist (these are copies of the master dataframes)
        self.dataframe_of_bid_targets = None
        self.dataframe_of_bid_targets_photoz = None
        self.num_targets = 0

        ra_min = float(ra - error)
        ra_max = float(ra + error)
        dec_min = float(dec - error)
        dec_max = float(dec + error)

        try:
            self.dataframe_of_bid_targets = self.df[(self.df['RA'] > ra_min) & (self.df['RA'] < ra_max) &
                                                (self.df['DEC'] > dec_min) & (self.df['DEC'] < dec_max)]

            self.dataframe_of_bid_targets_photoz = \
                self.df_photoz[(self.df_photoz['RA'] > ra_min) & (self.df_photoz['RA'] < ra_max) &
                               (self.df_photoz['DEC'] > dec_min) & (self.df_photoz['DEC'] < dec_max)]
        except:
            log.error(self.Name + " Exception in build_list_of_bid_targets",exc_info=True)

        if self.dataframe_of_bid_targets is not None:
            self.num_targets = self.dataframe_of_bid_targets.iloc[:, 0].count()
            self.sort_bid_targets_by_likelihood(ra,dec)

            log.debug(self.Name + " searching for objects in [%f - %f, %f - %f] " %(ra_min,ra_max,dec_min,dec_max) +
                  ". Found = %d" % (self.num_targets ))

        return self.num_targets, self.dataframe_of_bid_targets, self.dataframe_of_bid_targets_photoz


    def get_bid_dict(self,id,cols):
        """returns a (nested) dictionary of desired cols for a single row from the full bid dataframe
        form {col_name : {id : value}} where id is 1-based
        """
        try:
            bid_dict = self.dataframe_of_bid_targets.loc[id,cols].to_dict()
            log.debug(str(bid_dict))
        except:
            log.error("Exception attempting to build dictionary for %s : id %d" % (self.name, id),exc_info=True)
            return None
        return bid_dict

    #todo: refactor and move most of this to the base class
    #column names are catalog specific, but could map catalog specific names to generic ones and produce a dictionary?
    def build_bid_target_reports(self,target_ra, target_dec, error):

        #display the exact (target) location
        entry = self.build_exact_target_location_figure(target_ra,target_dec,error)

        if entry is not None:
            self.add_bid_entry(entry)

        ras = self.dataframe_of_bid_targets.loc[:, ['RA']].values
        decs = self.dataframe_of_bid_targets.loc[:, ['DEC']].values

        number = 0
        #display each bid target
        for r,d in zip(ras,decs):
            number+=1
            try:
                df = self.dataframe_of_bid_targets.loc[(self.dataframe_of_bid_targets['RA'] == r[0]) &
                                                   (self.dataframe_of_bid_targets['DEC'] == d[0])]

                idnum = df['ID'].values[0] #to matchup in photoz catalog
            except:
                log.error("Exception attempting to find object in dataframe_of_bid_targets", exc_info=True)
                continue #this must be here, so skip to next ra,dec

            try:
                #note cannot dirctly use RA,DEC as the recorded precission is different (could do a rounded match)
                #but the idnums match up, so just use that
                df_photoz = self.dataframe_of_bid_targets_photoz.loc[self.dataframe_of_bid_targets_photoz['ID'] == idnum ]

                if len(df_photoz) == 0:
                    log.debug("No conterpart found in photoz catalog; RA=%f , Dec =%f" %(r[0],d[0] ))
                    df_photoz = None
            except:
                log.error("Exception attempting to find object in dataframe_of_bid_targets",exc_info=True)
                df_photoz = None

            print("Building report for bid target %d in %s" % (number,self.Name))
            entry = self.build_bid_target_figure(r[0],d[0],error=error,df=df,df_photoz=df_photoz,
                                                 target_ra=target_ra,target_dec=target_dec)
            self.add_bid_entry(entry)

        return self.pages

    def build_exact_target_location_figure(self, ra, dec, error):
        '''Builds the figure (page) the exact target location. Contains just the filter images ...
        
        Returns the matplotlib figure. Due to limitations of matplotlib pdf generation, each figure = 1 page'''

        # note: error is essentially a radius, but this is done as a box, with the 0,0 position in lower-left
        #not the middle, so need the total length of each side to be twice translated error or 2*2*errorS
        window = error*4
        rows = 2
        cols = len(self.CatalogImages)

        fig_sz_x = cols * 3
        fig_sz_y = rows * 3

        fig = plt.figure(figsize=(fig_sz_x, fig_sz_y))

        gs = gridspec.GridSpec(rows, cols, wspace=0.25, hspace=0.5)
        #reminder gridspec indexing is 0 based; matplotlib.subplot is 1-based

        title = "Target Location\n\nRA = %f    Dec = %f\n\n" % (ra, dec)
        #ax = plt.subplot(rows, cols, 1)
        plt.subplot(gs[0,0])
        plt.text(0, 0.5, title, size=16, ha='left',va='bottom')
        plt.gca().set_frame_on(False)
        plt.gca().axis('off')

        font = FontProperties()
        font.set_family('monospace')

        if self.master_cutout is not None:
            del(self.master_cutout)
            self.master_cutout = None

        index = -1
        for i in self.CatalogImages:  # i is a dictionary
            index += 1
            sci = science_image.science_image(wcs_manual=self.WCS_Manual, image_location=i['path'] + i['name'])

            # sci.load_image(wcs_manual=True)
            cutout = sci.get_cutout(ra, dec, error, window=window)  # 8 arcsec
            ext = int(sci.window / 2) #extent is from the 0,0 center, so window/2

            if cutout is not None: #construct master cutout
                if self.master_cutout is None:
                    self.master_cutout = copy.deepcopy(cutout)
                else:
                    self.master_cutout.data = np.add(self.master_cutout.data, cutout.data)

                #plt.subplot(rows, cols, index)
                plt.subplot(gs[rows-1, index])
                # plt.axis('equal')
                plt.imshow(cutout.data, origin='lower', interpolation='nearest', cmap=plt.get_cmap('gray_r'),
                           vmin=sci.vmin, vmax=sci.vmax, extent=[-ext, ext, -ext, ext])
                plt.title(i['instrument'] + " " + i['filter'])

                plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
                                                  angle=0.0, color='red', fill=False))


        #plot the master cutout
        plt.subplot( gs[0, cols-1])
        vmin,vmax = science_image.science_image().get_vrange(self.master_cutout.data)
        plt.imshow(self.master_cutout.data, origin='lower', interpolation='nearest', cmap=plt.get_cmap('gray_r'),
                   vmin=vmin, vmax=vmax, extent=[-ext, ext, -ext, ext])
        plt.title("Master Cutout -- Stacked")
        plt.plot(0,0, "r+")
        plt.gca().add_patch(plt.Rectangle( (-error,-error), width=error*2, height=error*2,
                angle=0.0, color='red', fill=False ))

        # complete the entry
        plt.close()
        return fig



    def build_bid_target_figure(self,ra,dec,error,df=None,df_photoz=None,target_ra=None,target_dec=None):
        '''Builds the entry (e.g. like a row) for one bid target. Includes the target info (name, loc, Z, etc),
        photometry images, Z_PDF, etc
        
        Returns the matplotlib figure. Due to limitations of matplotlib pdf generateion, each figure = 1 page'''

        # note: error is essentially a radius, but this is done as a box, with the 0,0 position in lower-left
        # not the middle, so need the total length of each side to be twice translated error or 2*2*errorS
        window = error * 2
        photoz_file = None
        z_best = None
        z_best_type = None  # s = spectral , p = photometric?
        #z_spec = None
        #z_spec_ref = None

        rows = 2
        cols = len(self.CatalogImages)

        if df_photoz is not None:
            photoz_file = df_photoz['file'].values[0]
            z_best = df_photoz['z_best'].values[0]
            z_best_type = df_photoz['z_best_type'].values[0] #s = spectral , p = photometric?
            #z_spec = df_photoz['z_spec'].values[0]
            #z_spec_ref = df_photoz['z_spec_ref'].values[0]
            #rows = rows + 1

        fig_sz_x = cols*3
        fig_sz_y = rows*3

        gs = gridspec.GridSpec(rows, cols, wspace=0.25, hspace=0.5)

        fig = plt.figure(figsize=(fig_sz_x,fig_sz_y))

        if df is not None:
            title = "%s\n\nRA = %f    Dec = %f\nSeparation = %f\"" \
                    % (df['IAU_designation'].values[0], df['RA'].values[0], df['DEC'].values[0],
                       df['distance'].values[0] * 3600)
            z = df['DEEP_SPEC_Z'].values[0]
            if z >= 0.0:
                title = title + "\nDEEP SPEC Z = %f" % z
            elif z_best_type is not None:
                if (z_best_type.lower() == 'p'):
                    title = title + "\nPhoto Z = %f" % z_best
                elif (z_best_type.lower() == 's'):
                    title = title + "\nSpec Z = %f" % z_best
        else:
            title = "RA=%f    Dec=%f" % (ra, dec)


        #plt.subplot(rows,cols,1)
        plt.subplot(gs[0, 0])
        plt.text(0,0.50,title,size=16,ha='left',va='bottom')
        plt.gca().set_frame_on(False)
        plt.gca().axis('off')

        font = FontProperties()
        font.set_family('monospace')

        index = -1
        #iterate over all filter images
        for i in self.CatalogImages: # i is a dictionary
            index+= 1 #for subplot ... is 1 based
            sci = science_image.science_image(wcs_manual= self.WCS_Manual,image_location=i['path']+i['name'])

            #sci.load_image(wcs_manual=True)
            cutout = sci.get_cutout(ra, dec, error, window=window) #8 arcsec
            ext = int(sci.window / 2)

            #df should have exactly one entry, so need just the column values
            if (0):
                if df is not None:
                    title = "%s\nRA = %f    Dec = %f\nSeparation = %f\""  \
                                   % (df['IAU_designation'].values[0], df['RA'].values[0], df['DEC'].values[0],
                                     df['distance'].values[0]*3600)
                    z = df['DEEP_SPEC_Z'].values[0]
                    if z >= 0.0:
                        title = title + "\nDEEP SPEC Z = %f" %z
                    elif z_best_type is not None:
                        if (z_best_type.lower() == 'p'):
                            title = title + "\nPhoto Z = %f" % z_best
                        elif (z_best_type.lower() == 's'):
                            title = title + "\nSpec Z = %f" % z_best
                    plt.suptitle(title)
                else:
                    plt.suptitle("RA=%f    Dec=%f" %(ra,dec))

            if cutout is not None:
                #plt.subplot(rows,cols,index)
                plt.subplot(gs[1, index])
                #plt.axis('equal')
                plt.imshow(cutout.data, origin='lower', interpolation='nearest', cmap=plt.get_cmap('gray_r'),
                           vmin=sci.vmin, vmax=sci.vmax, extent= [-ext,ext,-ext,ext])
                plt.title(i['instrument']+" "+i['filter'])

                #add (+) to mark location of Target RA,DEC
                if cutout and (target_ra is not None) and (target_dec is not None):
                    px, py = sci.get_pixel_position(target_ra, target_dec, cutout)
                    x,y = sci.get_pixel_position(ra, dec, cutout)
                    plt.plot((px-x)*sci.get_pixel_size(),(py-y)*sci.get_pixel_size(),"r+")
                    plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
                                                  angle=0.0, color='yellow', fill=False,linewidth=5.0,zorder=1))

                #iterate over all fields for this image and print values
                if df is not None:
                    s = ""
                    for f,l in zip(i['cols'],i['labels']):
                        #print (f)
                        v = df[f].values[0]
                        s = s + "%-8s = %.5f\n" %(l,v)

                    plt.xlabel(s,multialignment='left',fontproperties=font)


        #add photo_z plot
        # if the z_best_type is 'p' call it photo-Z, if s call it 'spec-Z'
        # alwasy read in file for "file" and plot column 1 (z as x) vs column 9 (pseudo-probability)
        #get 'file'
        # z_best  # 6 z_best_type # 7 z_spec # 8 z_spec_ref
        if df_photoz is not None:
            z_cat = self.read_catalog(self.SupportFilesLocation+photoz_file,"z_cat")
            if z_cat is not None:
                x = z_cat['z'].values
                y = z_cat['mFDa4'].values
                #y = y/y.max()
                #plt.subplot(rows, cols, index)
                plt.subplot(gs[0, 3])
                plt.plot(x,y)
                plt.title("Z PDF")
                #plt.xticks(np.arange(0.0, 10.1, 1.0))
                plt.gca().yaxis.set_visible(False)
                plt.xlabel("Z")
                #plt.axis('equal')


        #master cutout (0,0 is the observered (exact) target RA, DEC)
        if self.master_cutout.data is not None:
            window=error*4
            ext = error*2
            plt.subplot(gs[0, cols - 1])
            vmin, vmax = science_image.science_image().get_vrange(self.master_cutout.data)
            plt.imshow(self.master_cutout.data, origin='lower', interpolation='nearest',
                       cmap=plt.get_cmap('gray_r'),
                       vmin=vmin, vmax=vmax, extent=[-ext, ext, -ext, ext])
            plt.title("Master Cutout -- Stacked")

            #mark the bid target location on the master cutout
            if  (target_ra is not None) and (target_dec is not None):
                px, py = sci.get_pixel_position(target_ra, target_dec, self.master_cutout)
                x, y   = sci.get_pixel_position(ra, dec, self.master_cutout)
                plt.plot(0, 0, "r+")

                plt.gca().add_patch(plt.Circle(((x-px) * sci.get_pixel_size(), (y-py) * sci.get_pixel_size())
                                               , radius=0.5, color='yellow', fill=False))
                plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
                                                  angle=0.0, color='red', fill=False))

                x = (x-px) * sci.get_pixel_size() - error
                y = (y-py) * sci.get_pixel_size() - error
                plt.gca().add_patch(plt.Rectangle((x, y), width=error * 2, height=error * 2,
                                                  angle=0.0, color='yellow', fill=False))

        plt.close()
        return fig

#######################################
#end class CANDELS_EGS_Stefanon_2016
#######################################



class dummy_cat(Catalog):
#RA,Dec in decimal degrees

    #class variables
    MainCatalog = "nowhere"
    Name = "Dummy Cat"


    def __init__(self):
    #    super(dummy_cat, self).__init__()
        self.dataframe_of_bid_targets = None
        self.read_catalog()

    @classmethod
    def read_catalog(cls):
        pass

    @classmethod
    def coordinate_range(cls,echo=False):
        if echo:
            msg = "RA (%f, %f)" % (cls.RA_min, cls.RA_max) + "Dec(%f, %f)" % (cls.Dec_min, cls.Dec_max)
            print( msg )
        log.debug(cls.Name + " Simple Coordinate Box: " + msg )
        return (cls.RA_min, cls.RA_max, cls.Dec_min, cls.Dec_max)

    def build_list_of_bid_targets(self,ra,dec,error):
       return 0,None





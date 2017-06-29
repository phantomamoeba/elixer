from __future__ import print_function

import global_config as G
import os.path as op

STACK_COSMOS_BASE_PATH = G.STACK_COSMOS_BASE_PATH
STACK_COSMOS_IMAGE = op.join(G.STACK_COSMOS_BASE_PATH,"COSMOS_g_sci.fits")
STACK_COSMOS_CAT = op.join(G.STACK_COSMOS_CAT_PATH,"cat_g.fits")


import matplotlib
matplotlib.use('agg')

import pandas as pd
import science_image
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.gridspec as gridspec
import astropy.io.fits as fits
from astropy.table import Table


log = G.logging.getLogger('Cat_logger')
log.setLevel(G.logging.DEBUG)

pd.options.mode.chained_assignment = None  #turn off warning about setting the distance field

import cat_base

class SHELA(cat_base.Catalog):
    # class variables
    SHELA_BASE_PATH = G.SHELA_BASE_PATH
    SHELA_IMAGE_PATH = G.SHELA_BASE_PATH

    Filters = ['u','g','r','i','z']
    Tiles = ['3','4','5','6']
    Img_ext = 'psfsci.fits'
    Cat_ext = 'dualgcat.fits'

    #SHELA_CAT = op.join(G.SHELA_CAT_PATH, "B3_g_dualgcat.fits")
    #SHELA_IMAGE = op.join(SHELA_IMAGE_PATH, "B3_g_psfsci.fits")

    MainCatalog = "SHELA" #while there is no main catalog, this needs to be not None
    Name = "SHELA"
    # if multiple images, the composite broadest range (filled in by hand)
    Image_Coord_Range = {'RA_min': 14.09, 'RA_max': 25.31, 'Dec_min': -1.35, 'Dec_max': 1.34}
    #approximate
    Tile_Coord_Range = {'3': {'RA_min': 14.09, 'RA_max': 16.91, 'Dec_min': -1.35, 'Dec_max': 1.34},
                        '4': {'RA_min': 16.90, 'RA_max': 19.71, 'Dec_min': -1.35, 'Dec_max': 1.34},
                        '5': {'RA_min': 19.70, 'RA_max': 22.52, 'Dec_min': -1.35, 'Dec_max': 1.34},
                        '6': {'RA_min': 22.51, 'RA_max': 25.31, 'Dec_min': -1.35, 'Dec_max': 1.34},
                        }


    Cat_Coord_Range = {'RA_min': None, 'RA_max': None, 'Dec_min': None, 'Dec_max': None}

    WCS_Manual = False

    AstroTable = None

# ColDefs(
#     name = 'NUMBER'; format = '1J'; disp = 'I10'
#     name = 'FLUXERR_ISO'; format = '1E'; unit = 'count'; disp = 'G12.7'
#     name = 'MAG_APER'; format = '25E'; unit = 'mag'; disp = 'F8.4'
#     name = 'MAGERR_APER'; format = '25E'; unit = 'mag'; disp = 'F8.4'
#     name = 'FLUX_AUTO'; format = '1E'; unit = 'count'; disp = 'G12.7'
#     name = 'FLUXERR_AUTO'; format = '1E'; unit = 'count'; disp = 'G12.7'
#     name = 'MAG_AUTO'; format = '1E'; unit = 'mag'; disp = 'F8.4'
#     name = 'MAGERR_AUTO'; format = '1E'; unit = 'mag'; disp = 'F8.4'
#     name = 'KRON_RADIUS'; format = '1E'; disp = 'F5.2'
#     name = 'THRESHOLD'; format = '1E'; unit = 'count'; disp = 'G12.7'
#     name = 'X_IMAGE'; format = '1E'; unit = 'pixel'; disp = 'F11.4'
#     name = 'Y_IMAGE'; format = '1E'; unit = 'pixel'; disp = 'F11.4'
#     name = 'ALPHA_J2000'; format = '1D'; unit = 'deg'; disp = 'F11.7'
#     name = 'DELTA_J2000'; format = '1D'; unit = 'deg'; disp = 'F11.7'
#     name = 'A_WORLD'; format = '1E'; unit = 'deg'; disp = 'G12.7'
#     name = 'B_WORLD'; format = '1E'; unit = 'deg'; disp = 'G12.7'
#     name = 'FLUX_RADIUS'; format = '1E'; unit = 'pixel'; disp = 'F10.3'
#     name = 'THETA_J2000'; format = '1E'; unit = 'deg'; disp = 'F6.2'
#     name = 'FWHM_IMAGE'; format = '1E'; unit = 'pixel'; disp = 'F8.2'
#     name = 'FWHM_WORLD'; format = '1E'; unit = 'deg'; disp = 'G12.7'
#     name = 'FLAGS'; format = '1I'; disp = 'I3'
#     name = 'IMAFLAGS_ISO'; format = '1J'; disp = 'I9'
#     name = 'NIMAFLAGS_ISO'; format = '1J'; disp = 'I9'
#     name = 'CLASS_STAR'; format = '1E'; disp = 'F6.3'
# )


    #NUMBER is NOT unique across Tiles (as expected)
    #NUMBER is NOT unique within a Tile either (bummer)
    #so ... it is essentially useless, just an index-1
    #plus they have different entries per filter, so must match by exact RA, DEC? are they consistent??

    BidCols = ['NUMBER',  # int32
               'FLUXERR_ISO',  # ct float32
               'MAG_APER',  # [25] mag float32
               'MAGERR_APER',  # [25] mag float32
               'FLUX_AUTO',  # ct float32
               'FLUXERR_AUTO',  # ct float32
               'MAG_AUTO',  # mag float32
               'MAGERR_AUTO',  # mag float32
               'KRON-RADIUS', #
               'THRESHOLD', # ct float32
               'X_IMAGE',  # pix float32
               'Y_IMAGE',  # pix float32
               'ALPHA_J2000',  # deg float64
               'DELTA_J2000',  # deg float64
               'A_WORLD',  # deg float32
               'B_WORLD',  # deg float32
               'FLUX_RADIUS',  # pix float32
               'THETA_J2000',  #
               'FWHM_IMAGE',  # pix float32
               'FWHM_WORLD',  # deg float32
               'FLAGS',  # int16
               'IMAFLAGS_ISO',  # int32
               'NIMAFLAGS_ISO',  # int32
               'CLASS_STAR']  # float32

    CatalogImages = [] #built in constructor

    def __init__(self):
        super(SHELA, self).__init__()

        self.dataframe_of_bid_targets = None
        self.dataframe_of_bid_targets_unique = None
        self.dataframe_of_bid_targets_photoz = None
        self.num_targets = 0
        self.master_cutout = None
        self.build_catalog_of_images()


    @classmethod
    def read_catalog(cls, catalog_loc=None, name=None):
        "This catalog is in a fits file"

        #ignore catalog_loc and name. Must use class defined.
        #build each tile and filter and concatenate into a single pandas dataframe

        df_master = pd.DataFrame()

        for t in cls.Tiles:
            for f in cls.Filters:
                cat_name = 'B'+t+'_'+f+'_'+cls.Cat_ext
                log.debug("Building " + cls.Name + " " + cat_name + " dataframe...")

                cat_loc = op.join(cls.SHELA_BASE_PATH,cat_name)

                try:
                    table = Table.read(cat_loc)
                except:
                    log.error(name + " Exception attempting to open catalog file: " + catalog_loc, exc_info=True)
                    return None

                # convert into a pandas dataframe ... cannot convert directly to pandas because of the [25] lists
                # so build a pandas df with just the few columns we need for searching
                # then pull data from full astro table as needed

                try:
                    lookup_table = Table([table['NUMBER'], table['ALPHA_J2000'], table['DELTA_J2000']])
                    df = lookup_table.to_pandas()
                    old_names = ['NUMBER', 'ALPHA_J2000', 'DELTA_J2000']
                    new_names = ['ID', 'RA', 'DEC']
                    df.rename(columns=dict(zip(old_names, new_names)), inplace=True)
                    df['TILE'] = t
                    df['FILTER'] = f

                    df_master = pd.concat([df_master,df])

                   # cls.AstroTable = table
                except:
                    log.error(name + " Exception attempting to build pandas dataframe", exc_info=True)
                    return None

        return df_master

    def build_catalog_of_images(self):
        for t in self.Tiles:
            for f in self.Filters:
                self.CatalogImages.append(
                    {'path': self.SHELA_IMAGE_PATH,
                     'name': 'B'+t+'_'+f+'_'+self.Img_ext,
                     'tile': t,
                     'filter': f,
                     'instrument': "",
                     'cols': [],
                     'labels': [],
                     'image': None
                     })

    def find_target_tile(self,ra,dec):
        #assumed to have already confirmed this target is at least in coordinate range of this catalog
        tile = None
        for t in self.Tiles:
            for f in ['g']: #self.Filters:
                #can we assume the filters all have the same coord range?
                #see if can get a cutout?
                img_name = 'B' + t + '_' + f + '_' + self.Img_ext
                try:
                    image = science_image.science_image(wcs_manual=self.WCS_Manual,
                            image_location=op.join(self.SHELA_IMAGE_PATH, img_name))
                    if image.contains_position(ra,dec):
                        tile = t
                except:
                    pass

                if tile is not None:
                    break

        return tile

    def build_list_of_bid_targets(self, ra, dec, error):
        '''ra and dec in decimal degrees. error in arcsec.
        returns a pandas dataframe'''

        if self.df is None:
            self.read_main_catalog()

        error_in_deg = np.float64(error) / 3600.0

        self.dataframe_of_bid_targets = None
        self.dataframe_of_bid_targets_photoz = None
        self.num_targets = 0

        ra_min = np.float64(ra - error_in_deg)
        ra_max = np.float64(ra + error_in_deg)
        dec_min = np.float64(dec - error_in_deg)
        dec_max = np.float64(dec + error_in_deg)

        log.info(self.Name + " searching for bid targets in range: RA [%f +/- %f], Dec [%f +/- %f] ..."
                 % (ra, error_in_deg, dec, error_in_deg))

        try:
            self.dataframe_of_bid_targets = \
                self.df[(self.df['RA'] >= ra_min) & (self.df['RA'] <= ra_max) &
                        (self.df['DEC'] >= dec_min) & (self.df['DEC'] <= dec_max)].copy()
            #may contain duplicates (across tiles)
            #remove duplicates (assuming same RA,DEC between tiles has same data)
            #so, different tiles that have the same ra,dec and filter get dropped (keep only 1)
            #but if the filter is different, it is kept

            #this could be done at construction time, but given the smaller subset I think
            #this is faster here
            self.dataframe_of_bid_targets = self.dataframe_of_bid_targets.drop_duplicates(
                subset=['RA','DEC','FILTER'])


            #relying on auto garbage collection here ...
            self.dataframe_of_bid_targets_unique = self.dataframe_of_bid_targets.copy()
            self.dataframe_of_bid_targets_unique = \
                self.dataframe_of_bid_targets_unique.drop_duplicates(subset=['RA','DEC'])
            self.num_targets = self.dataframe_of_bid_targets_unique.iloc[:,0].count()

        except:
            log.error(self.Name + " Exception in build_list_of_bid_targets", exc_info=True)

        if self.dataframe_of_bid_targets is not None:
            #self.num_targets = self.dataframe_of_bid_targets.iloc[:, 0].count()
            self.sort_bid_targets_by_likelihood(ra, dec)

            log.info(self.Name + " searching for objects in [%f - %f, %f - %f] " % (ra_min, ra_max, dec_min, dec_max) +
                     ". Found = %d" % (self.num_targets))

        return self.num_targets, self.dataframe_of_bid_targets, None


    def build_bid_target_reports(self, target_ra, target_dec, error, num_hits=0, section_title="", base_count=0,
                                 target_w=0, fiber_locs=None,target_flux=None):
        self.clear_pages()
        self.build_list_of_bid_targets(target_ra, target_dec, error)

        #need unique ra and decs only


        ras = self.dataframe_of_bid_targets_unique.loc[:, ['RA']].values
        decs = self.dataframe_of_bid_targets_unique.loc[:, ['DEC']].values

        # display the exact (target) location
        entry = self.build_exact_target_location_figure(target_ra, target_dec, error, section_title=section_title,
                                                        target_w=target_w, fiber_locs=fiber_locs,target_flux=target_flux)

        if entry is not None:
            self.add_bid_entry(entry)

        number = 0
        # display each bid target
        for r, d in zip(ras, decs):
            number += 1
            try:
                df = self.dataframe_of_bid_targets.loc[(self.dataframe_of_bid_targets['RA'] == r[0]) &
                                                       (self.dataframe_of_bid_targets['DEC'] == d[0])]
            except:
                log.error("Exception attempting to find object in dataframe_of_bid_targets", exc_info=True)
                continue  # this must be here, so skip to next ra,dec


            print("Building report for bid target %d in %s" % (base_count + number, self.Name))
            entry = self.build_bid_target_figure(r[0], d[0], error=error, df=df, df_photoz=None,
                                                 target_ra=target_ra, target_dec=target_dec,
                                                 section_title=section_title,
                                                 bid_number=number, target_w=target_w,of_number=num_hits-base_count,
                                                 target_flux=target_flux)
            if entry is not None:
                self.add_bid_entry(entry)

        return self.pages

    def build_exact_target_location_figure(self, ra, dec, error, section_title="", target_w=0, fiber_locs=None,
                                           target_flux=None):
        # todo: weight master cutout by exposure time ... see cat_candles_egs ...
        '''Builds the figure (page) the exact target location. Contains just the filter images ...

        Returns the matplotlib figure. Due to limitations of matplotlib pdf generation, each figure = 1 page'''

        # note: error is essentially a radius, but this is done as a box, with the 0,0 position in lower-left
        # not the middle, so need the total length of each side to be twice translated error or 2*2*errorS
        window = error * 4


        rows = 2
        cols = len(self.Filters)

        fig_sz_x = cols * 3
        fig_sz_y = rows * 3

        fig = plt.figure(figsize=(fig_sz_x, fig_sz_y))

        gs = gridspec.GridSpec(rows, cols, wspace=0.25, hspace=0.5)
        # reminder gridspec indexing is 0 based; matplotlib.subplot is 1-based

        font = FontProperties()
        font.set_family('monospace')
        font.set_size(12)

        title = "Catalog: %s\n" % self.Name + section_title + "\nPossible Matches = %d (within %g\")\n" \
                                                              "RA = %f    Dec = %f\n" % (
                                                                  len(self.dataframe_of_bid_targets), error, ra, dec)
        if target_w > 0:
            title = title + "Wavelength = %g $\AA$\n" % target_w
        else:
            title = title + "\n"
        plt.subplot(gs[0, 0])
        plt.text(0, 0.3, title, ha='left', va='bottom', fontproperties=font)
        plt.gca().set_frame_on(False)
        plt.gca().axis('off')

        if self.master_cutout is not None:
            del (self.master_cutout)
            self.master_cutout = None


        #for a given Tile, iterate over all filters
        tile = self.find_target_tile(ra,dec)

        if tile is None:
            #problem
            print("+++++ No appropriate tile found in SHELA for RA,DEC = [%f,%f]" %(ra,dec))
            log.error("No appropriate tile found in SHELA for RA,DEC = [%f,%f]" %(ra,dec))
            return None

        index = -1
        for f in self.Filters:
            index += 1

            i = self.CatalogImages[
                next(i for (i,d) in enumerate(self.CatalogImages)
                     if ((d['filter'] == f) and (d['tile'] == tile)))]

            if i is None:
                continue

            if i['image'] is None:
                i['image'] = science_image.science_image(wcs_manual=self.WCS_Manual,
                                                         image_location=op.join(i['path'], i['name']))
            sci = i['image']

            # sci.load_image(wcs_manual=True)
            cutout = sci.get_cutout(ra, dec, error, window=window)
            ext = sci.window / 2.  # extent is from the 0,0 center, so window/2

            if cutout is not None:  # construct master cutout
                # master cutout needs a copy of the data since it is going to be modified  (stacked)
                # repeat the cutout call, but get a copy
                if self.master_cutout is None:
                    self.master_cutout = sci.get_cutout(ra, dec, error, window=window, copy=True)
                else:
                    self.master_cutout.data = np.add(self.master_cutout.data, cutout.data)

                plt.subplot(gs[rows - 1, index])
                plt.imshow(cutout.data, origin='lower', interpolation='none', cmap=plt.get_cmap('gray_r'),
                           vmin=sci.vmin, vmax=sci.vmax, extent=[-ext, ext, -ext, ext])
                plt.title(i['instrument'] + " " + i['filter'])

                #plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
                #                                  angle=0.0, color='red', fill=False))

                self.add_north_box(plt, sci, cutout, error, 0, 0, theta=None)

        if self.master_cutout is None:
            # cannot continue
            print("No catalog image available in %s" % self.Name)
            return None

        # plot the master cutout
        empty_sci = science_image.science_image()
        plt.subplot(gs[0, cols - 1])
        vmin, vmax = empty_sci.get_vrange(self.master_cutout.data)
        plt.imshow(self.master_cutout.data, origin='lower', interpolation='none', cmap=plt.get_cmap('gray_r'),
                   vmin=vmin, vmax=vmax, extent=[-ext, ext, -ext, ext])
        plt.title("Master Cutout (Stacked)")
        plt.xlabel("arcsecs")
        # only show this lable if there is not going to be an adjacent fiber plot
        if (fiber_locs is None) or (len(fiber_locs) == 0):
            plt.ylabel("arcsecs")
        plt.plot(0, 0, "r+")
        #plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
        #                                  angle=0.0, color='red', fill=False))

        self.add_north_box(plt, empty_sci, self.master_cutout, error, 0, 0, theta=None)

        # plot the fiber cutout
        if (fiber_locs is not None) and (len(fiber_locs) > 0):
            plt.subplot(gs[0, cols - 2])

            plt.title("Fiber Positions")
            plt.xlabel("arcsecs")
            plt.ylabel("arcsecs")

            plt.plot(0, 0, "r+")

            xmin = float('inf')
            xmax = float('-inf')
            ymin = float('inf')
            ymax = float('-inf')

            x, y = empty_sci.get_position(ra, dec, self.master_cutout)  # zero (absolute) position

            self.add_north_box(plt, empty_sci, self.master_cutout, error, 0, 0, theta=None)

            for r, d, c, i in fiber_locs:
                # print("+++++ Cutout RA,DEC,ID,COLOR", r,d,i,c)
                # fiber absolute position ... need relative position to plot (so fiber - zero pos)
                fx, fy = empty_sci.get_position(r, d, self.master_cutout)

                xmin = min(xmin, fx - x)
                xmax = max(xmax, fx - x)
                ymin = min(ymin, fy - y)
                ymax = max(ymax, fy - y)

                plt.gca().add_patch(plt.Circle(((fx - x), (fy - y)), radius=G.Fiber_Radius, color=c, fill=False))
                plt.text((fx - x), (fy - y), str(i), ha='center', va='center', fontsize='x-small', color=c)

            ext_base = max(abs(xmin), abs(xmax), abs(ymin), abs(ymax))
            # larger of the spread of the fibers or the maximum width (in non-rotated x-y plane) of the error window
            ext = ext_base + G.Fiber_Radius

            # need a new cutout since we rescalled the ext (and window) size
            cutout = empty_sci.get_cutout(ra, dec, error, window=ext * 2, image=self.master_cutout)
            vmin, vmax = empty_sci.get_vrange(cutout.data)

            self.add_north_arrow(plt, sci, cutout, theta=None)

            plt.imshow(cutout.data, origin='lower', interpolation='none', cmap=plt.get_cmap('gray_r'),
                       vmin=vmin, vmax=vmax, extent=[-ext, ext, -ext, ext])

        # complete the entry
        plt.close()
        return fig

    def build_bid_target_figure(self, ra, dec, error, df=None, df_photoz=None, target_ra=None, target_dec=None,
                                section_title="", bid_number=1, target_w=0, of_number=0,target_flux=None):
        '''Builds the entry (e.g. like a row) for one bid target. Includes the target info (name, loc, Z, etc),
        photometry images, Z_PDF, etc

        Returns the matplotlib figure. Due to limitations of matplotlib pdf generateion, each figure = 1 page'''

        # note: error is essentially a radius, but this is done as a box, with the 0,0 position in lower-left
        # not the middle, so need the total length of each side to be twice translated error or 2*2*errorS
        window = error * 2.
        photoz_file = None
        z_best = None
        z_best_type = None  # s = spectral , p = photometric?
        # z_spec = None
        # z_spec_ref = None

        rows = 2
        cols = len(self.Filters)

        fig_sz_x = cols * 3
        fig_sz_y = rows * 3

        gs = gridspec.GridSpec(rows, cols, wspace=0.25, hspace=0.5)

        font = FontProperties()
        font.set_family('monospace')
        font.set_size(12)

        fig = plt.figure(figsize=(fig_sz_x, fig_sz_y))

        spec_z = 0.0

        if df is not None:
           # title = "%s\nPossible Match #%d\n\nRA = %f    Dec = %f\nSeparation  = %g\"" \
           #         % (section_title, bid_number, df['RA'].values[0], df['DEC'].values[0],
           #         df['distance'].values[0] * 3600)

            title = "%s  Possible Match #%d" % (section_title, bid_number)
            if of_number > 0:
                title = title + " of %d" % of_number

            title = title + "\nRA = %f    Dec = %f\nSeparation  = %g\"" \
                    % (df['RA'].values[0], df['DEC'].values[0],df['distance'].values[0] * 3600)
        else:
            title = "%s\nRA=%f    Dec=%f" % (section_title, ra, dec)

        plt.subplot(gs[0, 0])
        plt.text(0, 0.20, title, ha='left', va='bottom', fontproperties=font)
        plt.gca().set_frame_on(False)
        plt.gca().axis('off')

        # for a given Tile, iterate over all filters
        tile = self.find_target_tile(ra, dec)

        if tile is None:
            # problem
            print("+++++ No appropriate tile found in SHELA for RA,DEC = [%f,%f]" % (ra, dec))
            log.error("No appropriate tile found in SHELA for RA,DEC = [%f,%f]" % (ra, dec))
            return None

        index = -1
        for f in self.Filters:
            index += 1

            i = self.CatalogImages[
                next(i for (i, d) in enumerate(self.CatalogImages)
                     if ((d['filter'] == f) and (d['tile'] == tile)))]

            if i is None:
                continue

            if i['image'] is None:
                i['image'] = science_image.science_image(wcs_manual=self.WCS_Manual,
                                                         image_location=op.join(i['path'], i['name']))
            sci = i['image']

            cutout = sci.get_cutout(ra, dec, error, window=window)
            ext = sci.window / 2.

            if cutout is not None:
                plt.subplot(gs[1, index])

                plt.imshow(cutout.data, origin='lower', interpolation='none', cmap=plt.get_cmap('gray_r'),
                           vmin=sci.vmin, vmax=sci.vmax, extent=[-ext, ext, -ext, ext])
                plt.title(i['instrument'] + " " + i['filter'])

                # add (+) to mark location of Target RA,DEC
                # we are centered on ra,dec and target_ra, target_dec belong to the HETDEX detect
                if cutout and (target_ra is not None) and (target_dec is not None):
                    px, py = sci.get_position(target_ra, target_dec, cutout)
                    x, y = sci.get_position(ra, dec, cutout)

                    plt.plot((px - x), (py - y), "r+")

                    self.add_north_arrow(plt, sci, cutout, theta=None)

                    #plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2., height=error * 2.,
                    #                                  angle=0.0, color='yellow', fill=False, linewidth=5.0, zorder=1))
                    # set the diameter of the cirle to half the error (radius error/4)
                    plt.gca().add_patch(plt.Circle((0, 0), radius=error / 4.0, color='yellow', fill=False))

                # iterate over all filters for this image and print values
                font.set_size(10)
                if df is not None:
                    s = ""
                    for f, l in zip(i['cols'], i['labels']):
                        # print (f)
                        v = df[f].values[0]
                        s = s + "%-8s = %.5f\n" % (l, v)

                    plt.xlabel(s, multialignment='left', fontproperties=font)

        # add photo_z plot
        # if the z_best_type is 'p' call it photo-Z, if s call it 'spec-Z'
        # alwasy read in file for "file" and plot column 1 (z as x) vs column 9 (pseudo-probability)
        # get 'file'
        # z_best  # 6 z_best_type # 7 z_spec # 8 z_spec_ref
        if df_photoz is not None:
            z_cat = self.read_catalog(op.join(self.SupportFilesLocation, photoz_file), "z_cat")
            if z_cat is not None:
                x = z_cat['z'].values
                y = z_cat['mFDa4'].values
                plt.subplot(gs[0, 3])
                plt.plot(x, y, zorder=1)

                if spec_z > 0:
                    plt.axvline(x=spec_z, color='gold', linestyle='solid', linewidth=3, zorder=0)

                if target_w > 0:
                    la_z = target_w / G.LyA_rest - 1.0
                    oii_z = target_w / G.OII_rest - 1.0
                    plt.axvline(x=la_z, color='r', linestyle='--', zorder=2)
                    if (oii_z > 0):
                        plt.axvline(x=oii_z, color='g', linestyle='--', zorder=2)

                plt.title("Photo Z PDF")
                plt.gca().yaxis.set_visible(False)
                plt.xlabel("Z")

        empty_sci = science_image.science_image()
        # master cutout (0,0 is the observered (exact) target RA, DEC)
        if self.master_cutout is not None:
            # window=error*4
            ext = error * 2.
            plt.subplot(gs[0, cols - 1])
            vmin, vmax = empty_sci.get_vrange(self.master_cutout.data)
            plt.imshow(self.master_cutout.data, origin='lower', interpolation='none',
                       cmap=plt.get_cmap('gray_r'),
                       vmin=vmin, vmax=vmax, extent=[-ext, ext, -ext, ext])
            plt.title("Master Cutout (Stacked)")
            plt.xlabel("arcsecs")
            plt.ylabel("arcsecs")

            # mark the bid target location on the master cutout
            if (target_ra is not None) and (target_dec is not None):
                px, py = empty_sci.get_position(target_ra, target_dec, self.master_cutout)
                x, y = empty_sci.get_position(ra, dec, self.master_cutout)
                plt.plot(0, 0, "r+")

                # set the diameter of the cirle to half the error (radius error/4)
                plt.gca().add_patch(plt.Circle(((x - px), (y - py)), radius=error / 4.0, color='yellow', fill=False))
                #plt.gca().add_patch(plt.Rectangle((-error, -error), width=error * 2, height=error * 2,
                #                                  angle=0.0, color='red', fill=False))

                self.add_north_box(plt, empty_sci, self.master_cutout, error, 0, 0, theta=None)

                x = (x - px) - error
                y = (y - py) - error
                plt.gca().add_patch(plt.Rectangle((x, y), width=error * 2, height=error * 2,
                                                  angle=0.0, color='yellow', fill=False))

        plt.close()
        return fig

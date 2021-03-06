try:
    from elixer import global_config as G
    from elixer import line_prob
    from elixer import mcmc_gauss
    from elixer import spectrum_utilities as SU
except:
    import global_config as G
    import line_prob
    import mcmc_gauss
    import spectrum_utilities as SU

import matplotlib
#matplotlib.use('agg')

import matplotlib.pyplot as plt
#from matplotlib.font_manager import FontProperties
#import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import io
#from scipy.stats import gmean
#from scipy import signal
#from scipy.integrate import simps
from scipy.stats import skew, kurtosis,chisquare
from scipy.optimize import curve_fit
from scipy.signal import medfilt
import astropy.stats.biweight as biweight
import copy

import os.path as op
from speclite import filters as speclite_filters
from astropy import units as units

#log = G.logging.getLogger('spectrum_logger')
#log.setLevel(G.logging.DEBUG)
log = G.Global_Logger('spectrum_logger')
log.setlevel(G.LOG_LEVEL)

#these are for the older peak finder (based on direction change)
MIN_FWHM = 2.0 #AA (must xlat to pixels) (really too small to be realistic, but is a floor)
MAX_FWHM = 40.0 #big LyA are around 15-16; booming can get into the 20s, real lines can be larger,
                # but tend to be not what we are looking for
                # and these are more likly continuum between two abosrpotion features that is mistaken for a line
                #AGN seen with almost 25AA with CIV and NV around 35AA
MAX_NORMAL_FWHM = 20.0 #above this, need some extra info to accept
MIN_HUGE_FWHM_SNR = 19.0 #if the FWHM is above the MAX_NORMAL_FWHM, then then SNR needs to be above this value
                        #would say "20.0 AA" but want some room for error
MIN_ELI_SNR = 3.0 #bare minium SNR to even remotely consider a signal as real
MIN_ELI_SIGMA = 1.0 #bare minium (expect this to be more like 2+)
MIN_HEIGHT = 10
MIN_DELTA_HEIGHT = 2 #to be a peak, must be at least this high above next adjacent point to the left
DEFAULT_BACKGROUND = 6.0
DEFAULT_BACKGROUND_WIDTH = 100.0 #pixels
DEFAULT_MIN_WIDTH_FROM_CENTER_FOR_BACKGROUND = 10.0 #pixels


GAUSS_FIT_MAX_SIGMA = 17.0 #maximum width (pixels) for fit gaussian to signal (greater than this, is really not a fit)
GAUSS_FIT_MIN_SIGMA = 1.0 #roughly 1/2 pixel where pixel = 1.9AA (#note: "GOOD_MIN_SIGMA" below provides post
                          # check and is more strict) ... allowed to fit a more narrow sigma, but will be rejected later
                          # as not a good signal .... should these actually be the same??
GAUSS_FIT_AA_RANGE = 40.0 #AA to either side of the line center to include in the gaussian fit attempt
                          #a bit of an art here; too wide and the general noise and continuum kills the fit (too wide)
                          #too narrow and fit hard to find if the line center is off by more than about 2 AA
                          #40 seems (based on testing) to be about right (50 leaves too many clear, but weak signals behind)
GAUSS_FIT_PIX_ERROR = 4.0 #error (freedom) in pixels (usually  wavebins): have to allow at least 2 pixels of error
                          # (if aa/pix is small, _AA_ERROR takes over)
GAUSS_FIT_AA_ERROR = 1.0 #error (freedom) in line center in AA, still considered to be okay
GAUSS_SNR_SIGMA = 5.0 #check at least these pixels (pix*sigma) to either side of the fit line for SNR
                      # (larger of this or GAUSS_SNR_NUM_AA) *note: also capped to a max of 40AA or so (the size of the
                      # 'cutout' of the signal (i.e. GAUSS_FIT_AA_RANGE)
GAUSS_SNR_NUM_AA = 5.0 #check at least this num of AA to either side (2x +1 total) of the fit line for SNR in gaussian fit
                       # (larger of this or GAUSS_SNR_SIGMA


#copied from manual run of 100,000 noise spectra (see exp_prob.py)
#if change the noise model or SNR or line_flux algorithm or "EmissionLineInfo::is_good", need to recompute these
#as MDF
PROB_NOISE_LINE_SCORE = \
[  2.5,   3.5,   4.5,   5.5,   6.5,   7.5,   8.5,   9.5,  10.5,
        11.5,  12.5,  13.5,  14.5,  15.5]

#PROB_NOISE_GIVEN_SCORE = np.zeros(len(PROB_NOISE_LINE_SCORE))#\
PROB_NOISE_GIVEN_SCORE =  \
[        3.77800000e-01,   2.69600000e-01,   1.66400000e-01,
         9.05000000e-02,   4.69000000e-02,   2.28000000e-02,
         1.07000000e-02,   7.30000000e-03,   3.30000000e-03,
         2.30000000e-03,   1.00000000e-03,   5.00000000e-04,
         5.00000000e-04,   2.00000000e-04]

PROB_NOISE_TRUNCATED = 0.0002 #all bins after the end of the list get this value
PROB_NOISE_MIN_SCORE = 2.0 #min score that makes it to the bin list


#beyond an okay fit (see GAUSS_FIT_xxx above) is this a "good" signal
GOOD_BROADLINE_SIGMA = 6.0 #getting broad
LIMIT_BROAD_SIGMA = 7.0 #above this the emission line must specifically allow "broad"
GOOD_BROADLINE_SNR = 11.0 # upshot ... protect against neighboring "noise" that fits a broad line ...
                          # if big sigma, better have big SNR
GOOD_BROADLINE_RAW_SNR = 4.0 # litteraly signal/noise (flux values / error values +/- 3 sigma from peak)
GOOD_MIN_LINE_SNR = 4.0
GOOD_MIN_LINE_SCORE = 3.0 #lines are added to solution only if 'GOOD' (meaning, minimally more likely real than noise)
#does not have to be the same as PROB_NOISE_MIN_SCORE, but that generally makes sense
GOOD_BROADLINE_MIN_LINE_SCORE = 20.0 #if we have a special broad-line match, the score MUST be higher to accept
GOOD_FULL_SNR = 9.0 #ignore SBR is SNR is above this
#GOOD_MIN_SNR = 5.0 #bare-minimum; if you change the SNR ranges just above, this will also need to change
GOOD_MIN_SBR = 6.0 #signal to "background" noise (looks at peak height vs surrounding peaks) (only for "weak" signals0
GOOD_MIN_SIGMA = 1.35 #very narrow, but due to measurement error, could be possible (should be around 2 at a minimum, but with error ...)
#1.8 #in AA or FWHM ~ 4.2 (really too narrow, but allowing for some error)
#GOOD_MIN_EW_OBS = 1.5 #not sure this is a good choice ... really should depend on the physics of the line and
                      # not be absolute
#GOOD_MIN_EW_REST = 1.0 #ditto here

#GOOD_MIN_LINE_FLUX = 5.0e-18 #todo: this should be the HETDEX flux limit (but that depends on exposure time and wavelength)
#combined in the score

#GOOD_MAX_DX0_MUTL .... ALL in ANGSTROMS
MAX_LYA_VEL_OFFSET = 500.0 #km/s
NOMINAL_MAX_OFFSET_AA =8.0 # 2.75  #using 2.75AA as 1/2 resolution for HETDEX at 5.5AA
                           # ... maybe 3.0 to give a little wiggle room for fit?
GOOD_MAX_DX0_MULT_LYA = [-8.0,NOMINAL_MAX_OFFSET_AA] #can have a sizeable velocity offset for LyA (actaully depends on z, so this is a default)
#assumes a max velocity offset of 500km/s at 4500AA ==> 4500 * 500/c = 7.5AA
GOOD_MAX_DX0_MULT_OTHER = [-1.*NOMINAL_MAX_OFFSET_AA,NOMINAL_MAX_OFFSET_AA] #all others are symmetric and smaller

GOOD_MAX_DX0_MULT = GOOD_MAX_DX0_MULT_OTHER#[-1.75,1.75] #3.8 (AA)
                    # #maximum error (domain freedom) in fitting to line center in AA
                    #since this is based on the fit of the extra line AND the line center error of the central line
                    #this is a compound error (assume +/- 2 AA since ~ 1.9AA/pix for each so at most 4 AA here)?
#GOOD_MIN_H_CONT_RATIO = 1.33 #height of the peak must be at least 33% above the continuum fit level


#todo: impose line ratios?
#todo:  that is, if line_x is assumed and line_y is assumed, can only be valid if line_x/line_y ~ ratio??
#todo:  i.e. [OIII(5007)] / [OIII(4959)] ~ 3.0 (2.993 +/- 0.014 ... at least in AGN)

ABSORPTION_LINE_SCORE_SCALE_FACTOR = 0.5 #treat absorption lines as 50% of the equivalent emission line score


#FLUX conversion are pretty much defunct, but kept here as a last ditch conversion if all else fails
FLUX_CONVERSION_measured_w = [3000., 3500., 3540., 3640., 3740., 3840., 3940., 4040., 4140., 4240., 4340., 4440., 4540., 4640., 4740., 4840.,
     4940., 5040., 5140.,
     5240., 5340., 5440., 5500., 6000.]
FLUX_CONVERSION_measured_f = [1.12687e-18, 1.12687e-18, 9.05871e-19, 6.06978e-19, 4.78406e-19, 4.14478e-19, 3.461e-19, 2.77439e-19, 2.50407e-19,
     2.41462e-19, 2.24238e-19, 2.0274e-19, 1.93557e-19, 1.82048e-19, 1.81218e-19, 1.8103e-19, 1.81251e-19,
     1.80744e-19, 1.85613e-19, 1.78978e-19, 1.82547e-19, 1.85056e-19, 2.00788e-19, 2.00788e-19]

FLUX_CONVERSION_w_grid = np.arange(3000.0, 6000.0, 1.0)
FLUX_CONVERSION_f_grid = np.interp(FLUX_CONVERSION_w_grid, FLUX_CONVERSION_measured_w, FLUX_CONVERSION_measured_f)

FLUX_CONVERSION_DICT = dict(zip(FLUX_CONVERSION_w_grid,FLUX_CONVERSION_f_grid))


def conf_interval(num_samples,sd,conf=0.95):
    """
    mean +/- error  ... this is the +/- error part as 95% (or other) confidence interval (assuming normal distro)

    :param num_samples:
    :param sd: standard deviation
    :param conf:
    :return:
    """

    if num_samples < 30:
        return None

    #todo: put in other values
    if conf == 0.68:
        t = 1.0
    elif conf == 0.95:
        t = 1.96
    elif conf == 0.99:
        t = 2.576
    else:
        log.debug("todo: need to handle other confidence intervals: ", conf)
        return None

    return t * sd / np.sqrt(num_samples)


def get_sdss_gmag(flux_density, wave, flux_err=None, num_mc=G.MC_PLAE_SAMPLE_SIZE, confidence=G.MC_PLAE_CONF_INTVL):
    """

    :param flux_density: erg/s/cm2/AA  (*** reminder, HETDEX sumspec usually a flux erg/s/cm2 NOT flux denisty)
    :param wave: in AA
    :param flux_err: error array for flux_density (if None, then no error is computed)
    :param num_mc: number of MC samples to run
    :param confidence:  confidence interval to report
    :return: AB mag in g-band and continuum estimate (erg/s/cm2/AA)
            if flux_err is specified then also returns error on mag and error on the flux (continuum)
    """

    try:
        mag = None
        cont = None
        mag_err = None
        cont_err = None
        if flux_err is None:
            no_error = True

        # num_mc = G.MC_PLAE_SAMPLE_SIZE #good enough for this (just use the same as the MC for the PLAE/POII
        # confidence = G.MC_PLAE_CONF_INTVL

        filter_name = 'sdss2010-g'
        sdss_filter = speclite_filters.load_filters(filter_name)
        # not quite correct ... but can't find the actual f_iso freq. and f_iso lambda != f_iso freq, but
        # we should not be terribly far off (and there are larger sources of error here anyway since this is
        # padded HETDEX data passed through an SDSS-g filter (approximately)
        #iso_f = 3e18 / sdss_filter.effective_wavelengths[0].value
        iso_lam = sdss_filter.effective_wavelengths[0].value

        #sanity check flux_density
        sel = np.where(abs(flux_density) > 1e-5) #remember, these are e-17, so that is enormous
        if np.any(sel):
            msg = "Warning! Absurd flux density values: [%f,%f] (normal expected values e-15 to e-19 range)" %(min(flux_density[sel]),max(flux_density[sel]))
            print(msg)
            log.warning(msg)
            flux_density[sel] = 0.0

        #if flux_err is specified, assume it is Gaussian and sample, repeatedly building up spectra
        if flux_err is not None:
            try:
                mag_list = []
                cont_list = []
                for i in range(num_mc):
                    flux_sample = np.random.normal(flux_density, flux_err)

                    flux, wlen = sdss_filter.pad_spectrum(
                        flux_sample * (units.erg / units.s / units.cm ** 2 / units.Angstrom), wave * units.Angstrom)
                    mag = sdss_filter.get_ab_magnitudes(flux, wlen)[0][0]
                    #cont = 3631.0 * 10 ** (-0.4 * mag) * 1e-23 * iso_f / (wlen[-1] - wlen[0]).value  # (5549.26 - 3782.54) #that is the approximate bandpass

                    cont = 3631.0 * 10 ** (-0.4 * mag) * 1e-23 * 3e18 / (iso_lam * iso_lam)

                    mag_list.append(mag)
                    cont_list.append(cont)

                mag_list = np.array(mag_list)
                cont_list = np.array(cont_list)

                #clean the nans
                mag_list  = mag_list[~np.isnan(mag_list)]
                cont_list = cont_list[~np.isnan(cont_list)]

                loc = biweight.biweight_location(mag_list)  # the "average"
                scale = biweight.biweight_scale(mag_list)
                ci = conf_interval(len(mag_list), scale * np.sqrt(num_mc), conf=confidence)
                mag = loc
                mag_err = ci

                loc = biweight.biweight_location(cont_list)  # the "average"
                scale = biweight.biweight_scale(cont_list)
                ci = conf_interval(len(cont_list), scale * np.sqrt(num_mc), conf=confidence)
                cont = loc
                cont_err = ci

                no_error = False
            except:
                log.info("Exception in spectrum::get_sdss_gmag()",exc_info=True)
                no_error = True

        if no_error: #if we cannot compute the error, the just call once (no MC sampling)
            flux, wlen = sdss_filter.pad_spectrum(flux_density* (units.erg / units.s /units.cm**2/units.Angstrom),wave* units.Angstrom)
            mag = sdss_filter.get_ab_magnitudes(flux , wlen )[0][0]
            #cont = 3631.0 * 10**(-0.4*mag) * 1e-23 * iso_f / (wlen[-1] - wlen[0]).value
            cont = 3631.0 * 10 ** (-0.4 * mag) * 1e-23 * 3e18 / (iso_lam * iso_lam)#(5549.26 - 3782.54) #that is the approximate bandpass
            mag_err = None
            cont_err = None
    except:
        log.warning("Exception! in spectrum::get_sdss_gmag.",exc_info=True)

    if flux_err is not None: #even if this failed, the caller expects the extra two returns
        return mag, cont, mag_err, cont_err
    else:
        return mag, cont



def get_hetdex_gmag(flux_density, wave, flux_density_err=None):
    """
    Similar to get_sdss_gmag, but this uses ONLY the HETDEX spectrum and its errors

    Simple mean over spectrum ... should use something else? Median or Biweight?

    :param flux_density: erg/s/cm2/AA  (*** reminder, HETDEX sumspec usually a flux erg/s/cm2 NOT flux denisty)
    :param wave: in AA
    :param flux_err: error array for flux_density (if None, then no error is computed)
    :return: AB mag in g-band and continuum estimate (erg/s/cm2/AA)
            if flux_err is specified then also returns error on mag and error on the flux (continuum)
    """

    try:

        f_lam_iso = 4500.0  # middle of the range #not really the "true" f_lam_iso, but prob. intrudces small error compared to others
        mag = None
        cont = None
        mag_err = None
        cont_err = None
        if (flux_density_err is None) or (len(flux_density_err) == 0):
            flux_density_err = np.zeros(len(wave))

        #sanity check flux_density
        sel = np.where(abs(flux_density) > 1e-5) #remember, these are e-17, so that is enormous
        if np.any(sel):
            msg = "Warning! Absurd flux density values: [%f,%f] (normal expected values e-15 to e-19 range)" %(min(flux_density[sel]),max(flux_density[sel]))
            print(msg)
            log.warning(msg)
            flux_density[sel] = 0.0


        #trim off the ends (only use 3600-5400)
        idx_3600,*_ = SU.getnearpos(wave,3600.)
        idx_5400,*_ = SU.getnearpos(wave,5400.)

        fluxbins = np.array(flux_density[idx_3600:idx_5400+1]) * G.FLUX_WAVEBIN_WIDTH
        fluxerrs = np.array(flux_density_err[idx_3600:idx_5400+1]) * G.FLUX_WAVEBIN_WIDTH
        integrated_flux = np.sum(fluxbins)
        integrated_errs = np.sqrt(np.sum(fluxerrs*fluxerrs))

        #This already been thoughput adjusted? (Yes? I think)
        #so there is no need to adjust for transmission
        # remeber to add one more bin (bin 2 - bin 1 != 1 bin it is 2 bins, not 1 as both bins are included)
        band_flux_density = integrated_flux/(wave[idx_5400]-wave[idx_3600]+G.FLUX_WAVEBIN_WIDTH)
        band_flux_density_err = integrated_errs/(wave[idx_5400]-wave[idx_3600]+G.FLUX_WAVEBIN_WIDTH)


        if band_flux_density > 0:
            mag = -2.5*np.log10(SU.cgs2ujy(band_flux_density,f_lam_iso) / 1e6 / 3631.)
            mag_bright = -2.5 * np.log10(SU.cgs2ujy(band_flux_density+band_flux_density_err, f_lam_iso) / 1e6 / 3631.)
            mag_faint = -2.5 * np.log10(SU.cgs2ujy(band_flux_density-band_flux_density_err, f_lam_iso) / 1e6 / 3631.)
            if np.isnan(mag_faint):
                log.debug("Warning. HETDEX full spectrum mag estimate is invalid on the faint end.")
                mag_err = mag - mag_bright
            else:
                mag_err = 0.5 * (mag_faint-mag_bright) #not symmetric, but this is roughly close enough
        else:
            log.info(f"HETDEX full width gmag, continuum estimate ({band_flux_density:0.3g}) below flux limit. Setting mag to None.")
            return None, band_flux_density, None, band_flux_density_err


        #todo: technically, should remove the emission lines to better fit actual contiuum, rather than just use band_flux_density
        # but I think this is okay and appropriate and matches the other uses as the "band-pass" continuum
        return mag, band_flux_density, mag_err, band_flux_density_err

    except:
        log.warning("Exception! in spectrum::get_hetdex_gmag.",exc_info=True)
        return None, None, None, None


def fit_line(wavelengths,values,errors=None):
#super simple line fit ... very basic
#rescale x so that we start at x = 0
    coeff = np.polyfit(wavelengths,values,deg=1)

    #flip the array so [0] = 0th, [1] = 1st ...
    coeff = np.flip(coeff,0)

    if False: #just for debug
        fig = plt.figure(figsize=(8, 2), frameon=False)
        line_plot = plt.axes()
        line_plot.plot(wavelengths, values, c='b')

        x_vals = np.array(line_plot.get_xlim())
        y_vals = coeff[0] + coeff[1] * x_vals
        line_plot.plot(x_vals, y_vals, '--',c='r')

        fig.tight_layout()
        fig.savefig("line.png")
        fig.clear()
        plt.close()
        # end plotting
    return coeff


def invert_spectrum(wavelengths,values):
    # subtracting from the maximum value inverts the slope also, and keeps the overall shape intact
    # subtracting from the line fit slope flattens out the slope (leveling out the continuum) and changes the overall shape
    #
    #coeff = fit_line(wavelengths,values)
    #inverted = coeff[1]*wavelengths+coeff[0] - values

    mx = np.max(values)
    inverted = mx - values

    if False: #for debugging
        if not 'coeff' in locals():
            coeff = [mx, 0]

        fig = plt.figure(figsize=(8, 2), frameon=False)
        line_plot = plt.axes()
        line_plot.plot(wavelengths, values, c='g',alpha=0.5)
        x_vals = np.array(line_plot.get_xlim())
        y_vals = coeff[0] + coeff[1] * x_vals
        line_plot.plot(x_vals, y_vals, '--', c='b')

        line_plot.plot(wavelengths, inverted, c='r' ,lw=0.5)
        fig.tight_layout()
        fig.savefig("inverted.png")
        fig.clear()
        plt.close()


    return inverted


def norm_values(values,values_units):
    '''
    Basically, make spectra values either counts or cgs x10^-18 (whose magnitdues are pretty close to counts) and the
    old logic and parameters can stay the same
    :param values:
    :param values_units:
    :return:
    '''

    #return values, values_units
    if values is not None:
        values = np.array(values)

    if values_units == 0: #counts
        return values, values_units
    elif values_units == 1:
        return values * 1e18, -18
    elif values_units == -17:
        return values * 10.0, -18
    elif values_units == -18:
        return values, values_units
    else:
        log.warning("!!! Problem. Unexpected values_units = %s" % str(values_units))
        return values, values_units


def flux_conversion(w): #electrons to ergs at wavelenght w
    if w is None:
        return 0.0
    w = round(w)

    if w in FLUX_CONVERSION_DICT.keys():
        return FLUX_CONVERSION_DICT[w]
    else:
        log.error("ERROR! Unable to find FLUX CONVERSION entry for %f" %w)
        return 0.0


def pix_to_aa(pix):
    #constant for now since interpolating to 1 AA per pix
    #e.g. pix * 1.0
    return float(pix)

def getnearpos(array,value):
    idx = (np.abs(array-value)).argmin()
    return idx


def gaussian(x,x0,sigma,a=1.0,y=0.0):
    if (x is None) or (x0 is None) or (sigma is None):
        return None
    #return a * np.exp(-np.power((x - x0) / sigma, 2.) / 2.)
    #return a * (np.exp(-np.power((x - x0) / sigma, 2.) / 2.))  + y

    #have the / np.sqrt(...) part so the basic shape is normalized to 1 ... that way the 'a' becomes the area
    return a * (np.exp(-np.power((x - x0) / sigma, 2.) / 2.) / np.sqrt(2 * np.pi * sigma ** 2)) + y
    #return a * (np.exp(-np.power((x - x0) / sigma, 2.) / 2.)) + y




def gaussian_unc(x, mu, mu_u, sigma, sigma_u, A, A_u, y, y_u ):

    def df_dmu(x,mu,sigma,A):
        return A * (x - mu)/(np.sqrt(2.*np.pi)*sigma**3)*np.exp(-np.power((x - mu) / sigma, 2.) / 2.)

    def df_dsigma(x,mu,sigma,A):
        return A / (np.sqrt(2.*np.pi)*sigma**2) * (((x-mu)/sigma)**2 -1) * np.exp(-np.power((x - mu) / sigma, 2.) / 2.)

    def df_dA(x,mu,sigma):
        return 1./ (np.sqrt(2.*np.pi)*sigma)*np.exp(-np.power((x - mu) / sigma, 2.) / 2.)

    def df_dy():
        return 1

    try:
        f = gaussian(x,mu,sigma,A,y)

        variance = (mu_u**2) * (df_dmu(x,mu,sigma,A)**2) + (sigma_u**2) * (df_dsigma(x,mu,sigma,A)**2) + \
                   (A_u**2) * (df_dA(x,mu,sigma)**2) + (y_u**2) * (df_dy()**2)
    except:
        log.warning("Exception in spectrum::gaussian_unc: ", exc_info=True)
        f = None
        variance = 0


    return f, np.sqrt(variance)
#
#
#
# DEFUNCT: moved to spectrum_utilities.py
# def rms(data, fit,cw_pix=None,hw_pix=None,norm=True):
#     """
#
#     :param data: (raw) data
#     :param fit:  fitted data (on the same scale)
#     :param cw_pix: (nearest) pixel (index) of the central peak (could be +/- 1 pix (bin)
#     :param hw_pix: half-width (in pixels from the cw_pix) overwhich to calculate rmse (i.e. cw_pix +/- hw_pix)
#     :param norm: T/F whether or not to divide by the peak of the raw data
#     :return:
#     """
#     #sanity check
#     if (data is None) or (fit is None) or (len(data) != len(fit)) or any(np.isnan(data)) or any(np.isnan(fit)):
#         return -999
#
#     if norm:
#         mx = max(data)
#         if mx < 0:
#             return -999
#     else:
#         mx = 1.0
#
#     d = np.array(data)/mx
#     f = np.array(fit)/mx
#
#     if ((cw_pix is not None) and (hw_pix is not None)):
#         left = cw_pix - hw_pix
#         right = cw_pix + hw_pix
#
#         #due to rounding of pixels (bins) from the caller (the central index +/- 2 and the half-width to either side +/- 2)
#         # either left or right can be off by a max total of 4 pix
#         rounding_error = 4
#         if -1*rounding_error <= left < 0:
#             left = 0
#
#         if len(data) < right <= (len(data) +rounding_error):
#             right = len(data)
#
#         if (left < 0) or (right > len(data)):
#             log.warning("Invalid range supplied for rms. Data len = %d. Central Idx = %d , Half-width= %d"
#                       % (len(data),cw_pix,hw_pix))
#             return -999
#
#         d = d[left:right+1]
#         f = f[left:right+1]
#
#     return np.sqrt(((f - d) ** 2).mean())
#

#def fit_gaussian(x,y):
#    yfit = None
#    parm = None
#    pcov = None
#    try:
#        parm, pcov = curve_fit(gaussian, x, y,bounds=((-np.inf,0,-np.inf),(np.inf,np.inf,np.inf)))
#        yfit = gaussian(x,parm[0],parm[1],parm[2])
#    except:
#        log.error("Exception fitting gaussian.",exc_info=True)
#
#    return yfit,parm,pcov


class EmissionLineInfo:
    """
    mostly a container, could have pretty well just used a dictionary
    """
    def __init__(self):

        #unless noted, these are without units
        self.fit_a = None #expected in counts or in x10^-18 cgs [notice!!! -18 not -17]
        self.fit_a_err = 0.
        self.fit_x0 = None #central peak (x) position in AA
        self.fit_x0_err = 0.
        self.fit_dx0 = None #difference in fit_x0 and the target wavelength in AA, like bias: target-fit
        self.fit_sigma = 0.0
        self.fit_sigma_err = 0.0
        self.fit_y = None #y offset for the fit (essentially, the continuum estimate)
        self.fit_y_err = 0.0
        self.fit_h = None #max of the fit (the peak) #relative height
        self.fit_rh = None #fraction of fit height / raw peak height
        self.fit_rmse = -999
        self.fit_chi2 = None
        self.fit_norm_rmse = -999
        self.fit_bin_dx = 1.0 #default to 1.0 for no effect (bin-width of flux bins if flux instead of flux/dx)

        self.y_unc = None
        self.a_unc = None

        self.fit_line_flux = None #has units applied
        self.fit_line_flux_err = 0.0 #has units applied
        self.fit_continuum = None #has units applied
        self.fit_continuum_err = 0.0 #has units applied

        self.fit_wave = []
        self.fit_vals = []

        self.pix_size = None
        self.sn_pix = 0 #total number of pixels used to calcualte the SN (kind of like a width in pixels)

        #!! Important: raw_wave, etc is NOT of the same scale or length of fit_wave, etc
        self.raw_wave = []
        self.raw_vals = []
        self.raw_errs = []
        self.raw_h =  None
        self.raw_x0 = None

        self.line_flux = -999. #the line flux
        self.line_flux_err = 0. #the line flux
        self.cont = -999.
        self.cont_err = 0.

        self.snr = 0.0
        self.sbr = 0.0
        self.eqw_obs = -999
        self.fwhm = -999
        self.score = None
        self.raw_score = None

        self.line_score = None
        self.prob_noise = 1.0

        #MCMC errors and info
        # 3-tuples [0] = fit, [1] = fit +16%,  [2] = fit - 16% (i.e. ~ +/- 1 sd ... the interior 66%)
        self.mcmc_x0 = None #aka mu
        self.mcmc_sigma = None
        self.mcmc_a = None #area
        self.mcmc_y = None
        self.mcmc_ew_obs = None #calcuated value (using error propogation from mcmc_a and mcmc_y)
        self.mcmc_snr = -1
        self.mcmc_dx = 1.0 #default to 1.0 so mult or div have no effect
        self.mcmc_line_flux = None #actual line_flux not amplitude (not the same if y data is flux instead of flux/dx)
        self.mcmc_continuum = None #ditto for continuum
        self.mcmc_line_flux_tuple = None #3-tuple version of mcmc_a / mcmc_dx
        self.mcmc_continuum_tuple = None #3-tuple version of mcmc_y / mcmc_dx
        self.mcmc_chi2 = None


        self.broadfit = False #set to TRUE if a broadfit conditions were applied to the fit
        self.absorber = False #set to True if this is an absorption line

        self.mcmc_plot_buffer = None
        self.gauss_plot_buffer = None

        self.noise_estimate = None
        self.noise_estimate_wave = None
        self.unique = None #is this peak unique, alone in its immediate vacinity


    def unc_str(self,tuple):
        s = ""
        try:
            flux = ("%0.2g" % tuple[0]).split('e')
            unc = ("%0.2g" % (0.5 * (abs(tuple[1]) + abs(tuple[2])))).split('e')

            if len(flux) == 2:
                fcoef = float(flux[0])
                fexp = float(flux[1])
            else:
                fcoef = flux
                fexp = 0

            if len(unc) == 2:
                ucoef = float(unc[0])
                uexp = float(unc[1])
            else:
                ucoef = unc
                uexp = 0

            s = '%0.2f($\pm$%0.2f)e%d' % (fcoef, ucoef * 10 ** (uexp - fexp), fexp)
        except:
            log.warning("Exception in EmissionLineInfo::flux_unc()", exc_info=True)

        return s

    @property
    def flux_unc(self):
        #return a string with flux uncertainties in place
        return self.unc_str(self.mcmc_line_flux_tuple)

    @property
    def cont_unc(self):
        #return a string with flux uncertainties in place
        return self.unc_str(self.mcmc_continuum_tuple)


    @property
    def eqw_lya_unc(self):
        #return a string with flux uncertainties in place
        s = ""
        try:
           # ew = np.array(self.mcmc_ew_obs)/(self.fit_x0 / G.LyA_rest) #reminder this is 1+z
           # s  =  "%0.2g($\pm$%0.2g)" %(ew[0],(0.5 * (abs(ew[1]) + abs(ew[2]))))

            #more traditional way
            ew = self.mcmc_line_flux / self.mcmc_continuum /(self.fit_x0 / G.LyA_rest)
            a_unc = 0.5 * (abs(self.mcmc_line_flux_tuple[1])+abs(self.mcmc_line_flux_tuple[2]))
            y_unc = 0.5 * (abs(self.mcmc_continuum_tuple[1])+abs(self.mcmc_continuum_tuple[2]))

            #wrong!! missing the abs(ew) and the ratios inside are flipped
            #ew_unc = np.sqrt((self.mcmc_a[0]/a_unc)**2 + (self.mcmc_y[0]/y_unc)**2)

            ew_unc = abs(ew) * np.sqrt((a_unc/self.mcmc_line_flux)**2 + (y_unc/self.mcmc_continuum)**2)

            s = "%0.2g($\pm$%0.2g)" % (ew, ew_unc)


        except:
            log.warning("Exception in eqw_lya_unc",exc_info=True)

        return s

    def raw_snr(self):
        """
        return the SNR (litterly as the flux values / noise values) over the 3sigma with of the line
        :return:
        """
        snr = 0.0
        try:
            idx = getnearpos(self.raw_wave,self.fit_x0) #single value version of getnearpos
            width = int(self.fit_sigma * 3.0)
            left = max(0,idx-width)
            right = max(len(self.raw_wave)-1,idx+width)

            signal = np.nansum(self.raw_vals[left::right+1])
            error = np.nansum(self.raw_errs[left::right+1])

            snr = signal/error
        except:
            log.info("Exception in EmissionLineInfo::raw_snr",exc_info=True)

        return snr

    def build(self,values_units=0,allow_broad=False, broadfit=1):
        """

        :param values_units:
        :param allow_broad:  can be broad (really big sigma)
        :param broadfit:  was fit using the broad adjustment (median filter)
        :return:
        """
        if self.snr > MIN_ELI_SNR and self.fit_sigma > MIN_ELI_SIGMA:
            if self.fit_sigma is not None:
                self.fwhm = 2.355 * self.fit_sigma  # e.g. 2*sqrt(2*ln(2))* sigma

            unit = 1.0
            if self.fit_x0 is not None:

                if values_units != 0:
                    if values_units == 1:
                        unit = 1.0
                    elif values_units == -17:
                        unit = 1.0e-17
                    elif values_units == -18:
                        unit = 1.0e-18
                    else:
                        unit = 1.0
                        log.warning(("!!! Problem. Unexpected values units in EmissionLineInfo::build(): %s") % str(values_units))

                    #need these unadjusted since they inform the MCMC fit
                    # self.fit_a *= unit
                    # self.fit_y *= unit
                    # self.fit_h *= unit

                    self.line_flux = self.fit_a / self.fit_bin_dx * unit
                    self.line_flux_err = self.fit_a_err / self.fit_bin_dx * unit
                    self.fit_line_flux = self.line_flux
                    self.cont = self.fit_y * unit
                    self.cont_err = self.fit_y_err * unit
                    self.fit_continuum = self.cont

                    #fix fit_h
                    # if (self.fit_h > 1.0) and (values_units < 0):
                    #     self.fit_h *= unit

                else: #very old deals with counts instead of flux
                    if (self.fit_a is not None):
                        #todo: HERE ... do not attempt to convert if this is already FLUX !!!
                        #todo: AND ... need to know units of flux (if passed from signal_score are in x10^-18 not -17
                        self.line_flux = self.fit_a / self.fit_bin_dx * flux_conversion(self.fit_x0)  # cgs units
                        self.fit_line_flux = self.line_flux
                        self.line_flux_err = self.fit_a_err / self.fit_bin_dx * flux_conversion(self.fit_x0)

                    if (self.fit_y is not None) and (self.fit_y > G.CONTINUUM_FLOOR_COUNTS):
                        self.cont = self.fit_y * flux_conversion(self.fit_x0)
                        self.cont_err = self.fit_y_err * flux_conversion(self.fit_x0)
                    else:
                        self.cont = G.CONTINUUM_FLOOR_COUNTS * flux_conversion(self.fit_x0)
                    self.fit_continuum = self.cont


            if self.line_flux and self.cont:
                self.eqw_obs = self.line_flux / self.cont

            #line_flux is now in erg/s/... the 1e17 scales up to reasonable numbers (easier to deal with)
            #we are technically penalizing a for large variance, but really this is only to weed out
            #low and wide fits that are probably not reliable

            #and penalize for large deviation from the highest point and the line (gauss) mean (center) (1.9 ~ pixel size)
            #self.line_score = self.snr * self.line_flux * 1e17 / (2.5 * self.fit_sigma * (1. + abs(self.fit_dx0/1.9)))

            #penalize for few pixels (translated to angstroms ... anything less than 21 AA total)
            #penalize for too narrow sigma (anything less than 1 pixel

            #the 10.0 is just to rescale ... could make 1e17 -> 1e16, but I prefer to read it this way

            above_noise = self.peak_sigma_above_noise()
            #this can fail to behave as expected for large galaxies (where much/all of IFU is covered)
            #since all the lines are represented in many fibers, that appears to be "noise"
            if above_noise is None:
                above_noise = 1.0
            else:
                above_noise = min(above_noise / G.MULTILINE_SCORE_NORM_ABOVE_NOISE, G.MULTILINE_SCORE_ABOVE_NOISE_MAX_BONUS)
                # cap at 3x (so above 9x noise, we no longer graduate)
                # that way, some hot pixel that spikes at 100x noise does not automatically get "real"
                # but will still be throttled down due to failures with other criteria

            unique_mul = 1.0 #normal
            if (self.unique == False) and (self.fwhm < 6.5):
                #resolution is around 5.5, so if this is less than about 7AA, it could be noise?
                unique_mul = 0.5 #knock it down (it is mixed in with others)
                #else it is broad enough that we don't care about possible nearby lines as noise

            #def unique_peak(spec, wave, cwave, fwhm, width=10.0, frac=0.9):
            if GOOD_MAX_DX0_MULT[0] < self.fit_dx0 < GOOD_MAX_DX0_MULT[1]:
                adjusted_dx0_error = 0.0
            else:
                adjusted_dx0_error = self.fit_dx0

            if allow_broad:
                max_fwhm = MAX_FWHM * 1.5
            else:
                max_fwhm = MAX_FWHM

            if (self.fwhm is None) or (self.fwhm < max_fwhm):
                #this MIN_HUGE_FWHM_SNR is based on the usual 2AA bins ... if this is broadfit, need to return to the
                # usual SNR definition
                if (self.fwhm > MAX_NORMAL_FWHM) and \
                        ((self.snr *np.sqrt(broadfit) < MIN_HUGE_FWHM_SNR) and (self.raw_snr() < GOOD_BROADLINE_RAW_SNR)):
                    log.debug(f"Huge fwhm {self.fwhm} with relatively poor SNR {self.snr} < required SNR {MIN_HUGE_FWHM_SNR} and "
                              f"{self.raw_snr()} < {GOOD_BROADLINE_RAW_SNR}. "
                              "Probably bad fit or merged lines. Rejecting score.")
                    self.line_score = 0
                else:
                    self.line_score = self.snr * above_noise * unique_mul * self.line_flux * 1e17 * \
                              min(self.fit_sigma/self.pix_size,1.0) * \
                              min((self.pix_size * self.sn_pix)/21.0,1.0) / \
                              (10.0 * (1. + abs(adjusted_dx0_error / self.pix_size)) )
            else:
                log.debug(f"Huge fwhm {self.fwhm}, Probably bad fit or merged lines. Rejecting score.")
                self.line_score = 0

            if self.absorber:
                if G.MAX_SCORE_ABSORPTION_LINES: #if not scoring absorption, should never actually get here ... this is a safety
                    # as hand-wavy correction, reduce the score as an absorber
                    # to do this correctly, need to NOT invert the values and treat as a proper absorption line
                    #   and calucate a true flux and width down from continuum
                    new_score = min(G.MAX_SCORE_ABSORPTION_LINES, self.line_score * ABSORPTION_LINE_SCORE_SCALE_FACTOR)
                    log.info("Rescalling line_score for absorption line: %f to %f" %(self.line_score,new_score))
                    self.line_score = new_score
                else:
                    log.info("Zeroing line_score for absorption line.")
                    self.line_score = 0.0
            #
            # !!! if you change this calculation, you need to re-calibrate the prob(Noise) (re-run exp_prob.py)
            # !!! and update the Solution cut criteria in global_config.py (MULTILINE_MIN_SOLUTION_SCORE, etc) and
            # !!!    in hetdex.py (DetObj::multiline_solution_score)
            # !!! and update GOOD_MIN_LINE_SCORE and PROB_NOISE_MIN_SCORE
            # !!! It is a little ciruclar as MIN scores are dependent on the results of the exp_prob.py run
            #

            self.prob_noise = self.get_prob_noise()
        else:
            self.fwhm = -999
            self.cont = -999
            self.line_flux = -999
            self.line_score = 0


    # def calc_line_score(self):
    #
    #     return   self.snr * self.line_flux * 1e17 * \
    #              min(self.fit_sigma / self.pix_size, 1.0) * \
    #              min((self.pix_size * self.sn_pix) / 21.0, 1) / \
    #              (10.0 * (1. + abs(self.fit_dx0 / self.pix_size)))

    def get_prob_noise(self):
        MDF = False

        try:
            if (self.line_score is None) or (self.line_score < PROB_NOISE_MIN_SCORE):
                return 0.98 # really not, but we will cap it
            #if we are off the end of the scores, set to a fixed probability
            elif self.line_score > max(PROB_NOISE_LINE_SCORE) + (PROB_NOISE_LINE_SCORE[1]-PROB_NOISE_LINE_SCORE[0]):
                return PROB_NOISE_TRUNCATED #set this as the minium
            else:

                if MDF:
                    prob = 0.0
                    assumed_error_frac = 0.5
                    score_bin_width = PROB_NOISE_LINE_SCORE[1] - PROB_NOISE_LINE_SCORE[0]
                    #treat the arrays as MDF and use an error in LineFlux as a range over which to sum
                    min_score_bin = round(float(max(0, self.line_score*(1.0 - assumed_error_frac))) / score_bin_width)\
                                    * score_bin_width
                    max_score_bin = round(float( self.line_score*(1.0+assumed_error_frac)) / score_bin_width)\
                                    * score_bin_width

                    min_score_idx = np.where(PROB_NOISE_LINE_SCORE == min_score_bin)[0][0]
                    max_score_idx = np.where(PROB_NOISE_LINE_SCORE == max_score_bin)[0][0]

                    for i in range(min_score_idx, max_score_idx + 1):
                        prob += PROB_NOISE_GIVEN_SCORE[i]

                    return prob
                else:
                    return PROB_NOISE_GIVEN_SCORE[getnearpos(PROB_NOISE_LINE_SCORE,self.line_score)]
        except:
            return 1.0


    def peak_sigma_above_noise(self):
        s = None

        if (self.noise_estimate is not None) and (len(self.noise_estimate) > 0):
            try:
                noise_idx = getnearpos(self.noise_estimate_wave, self.fit_x0)
                raw_idx = getnearpos(self.raw_wave, self.fit_x0)
                s = self.raw_vals[raw_idx] / self.noise_estimate[noise_idx]
            except:
                pass

        return s

    def is_good(self,z=0.0,allow_broad=False):
        #(self.score > 0) and  #until score can be recalibrated, don't use it here
        #(self.sbr > 1.0) #not working the way I want. don't use it
        result = False

        def ratty(snr,sigma): #a bit redundant vs similar check under self.build()
            if (sigma > GOOD_BROADLINE_SIGMA) and ((snr < GOOD_BROADLINE_SNR) and (self.raw_snr() < GOOD_BROADLINE_RAW_SNR)):
                log.debug("Ratty fit on emission line.")
                return True
            else:
                return False

        if not (allow_broad or self.broadfit) and (self.fit_sigma >= LIMIT_BROAD_SIGMA):
            return False
        elif (self.fit_sigma > GOOD_BROADLINE_SIGMA) and (self.line_score < GOOD_BROADLINE_MIN_LINE_SCORE):
            result = False
        # minimum to be possibly good
        elif (self.line_score >= GOOD_MIN_LINE_SCORE) and (self.fit_sigma >= GOOD_MIN_SIGMA):
        #if(self.snr >= GOOD_MIN_LINE_SNR) and (self.fit_sigma >= GOOD_MIN_SIGMA):
            if not ratty(self.snr,self.fit_sigma):
                s = self.peak_sigma_above_noise()
                if (s is None) or (s > G.MULTILINE_MIN_GOOD_ABOVE_NOISE):
                    result = True
                else:
                    if (self.snr > GOOD_FULL_SNR) or (self.sbr > GOOD_MIN_SBR):
                        result = True

            #note: GOOD_MAX_DX0_MULT enforced in signal_score

        # if ((self.snr > GOOD_FULL_SNR) or ((self.snr > GOOD_MIN_SNR) and (self.sbr > GOOD_MIN_SBR))) and \
        #    (self.fit_sigma > GOOD_MIN_SIGMA) and \
        #    (self.line_flux > GOOD_MIN_LINE_FLUX) and \
        #    (self.fit_h/self.cont > GOOD_MIN_H_CONT_RATIO) and \
        #    (abs(self.fit_dx0) < GOOD_MAX_DX0):
        #         result = True

            #if self.eqw_obs/(1.+z) > GOOD_MIN_EW_REST:
            #    result =  True

        return result
 #end EmissionLineInfo Class



#really should change this to use kwargs
def signal_score(wavelengths,values,errors,central,central_z = 0.0, spectrum=None,values_units=0, sbr=None,
                 min_sigma=GAUSS_FIT_MIN_SIGMA,show_plot=False,plot_id=None,plot_path=None,do_mcmc=False,absorber=False,
                 force_score=False,values_dx=G.FLUX_WAVEBIN_WIDTH,allow_broad=False,broadfit=1):
    """

    :param wavelengths:
    :param values:
    :param errors:
    :param central:
    :param central_z:
    :param spectrum:
    :param values_units:
    :param sbr:
    :param min_sigma:
    :param show_plot:
    :param plot_id:
    :param plot_path:
    :param do_mcmc:
    :param absorber:
    :param force_score:
    :param values_dx:
    :param allow_broad:
    :param broadfit: (median filter size used to smooth for a broadfit) 1 = no filter (or a bin of 1 which is no filter)
    :return:
    """

    #values_dx is the bin width for the values if multiplied out (s|t) values are flux and not flux/dx
    #   by default, Karl's data is on a 2.0 AA bin width

    #error on the wavelength of the possible line depends on the redshift and its error and the wavelength itself
    #i.e. wavelength error = wavelength / (1+z + error)  - wavelength / (1+z - error)
    # want that by 1/2 (so +/- error from center ... note: not quite symmetric, but close enough over small delta)
    # and want in pixels so divide by pix_size
    #todo: note error itself should be a function of z ... otherwise, error is constant and as z increases, the
    #todo:   pix_error then decreases
    #however, this error is ON TOP of the wavelength measurement error, assumed to be +/- 1 pixel?
    def pix_error(z,wavelength,error=0.001, pix_size= 2.0):
        """
        NOTICE ALWAYS RETURNING ZERO RIGHT NOW
        :param z:
        :param wavelength:
        :param error:
        :param pix_size:
        :return:  error in measurement IN PIXELS (not AA)
        """
        return 0.0

        try:
            e =  0.5 * wavelength * (2. * error / ((1.+z)**2 - error**2)) / pix_size
        except:
            e = 0.0
            log.warning("Invalid pix_error in spectrum::signal_score",exc_info=True)

        return e


    if (wavelengths is None) or (values is None) or (len(wavelengths)==0) or (len(values)==0):
        log.warning("Zero length (or None) spectrum passed to spectrum::signal_score().")
        return None


    accept_fit = False
    #if values_are_flux:
    #    # assumed then to be in cgs units of x10^-17 as per typical HETDEX values
    #    # !!!! reminder, do NOT do values *= 10.0  ... that is an in place operation and overwrites the original
    #    values = values * 10.0  # put in units of 10^-18 so they pretty much match up with counts

    err_units = values_units #assumed to be in the same units
    values, values_units = norm_values(values,values_units)
    if errors is not None and (len(errors) == len(values)):
        errors, err_units = norm_values(errors,err_units)
       # errors /= 10.0 #todo: something weird here with the latest update ... seem to be off by 10.0

    #sbr signal to background ratio
    pix_size = abs(wavelengths[1] - wavelengths[0])  # aa per pix

    #if near a peak we already found, nudge to align
    if isinstance(spectrum,Spectrum):
        w = spectrum.is_near_a_peak(central,pix_size)
        if w:
            central = w

    # want +/- 20 angstroms in pixel units (maybe should be 50 AA?
    wave_side = int(round(GAUSS_FIT_AA_RANGE / pix_size))  # pixels
    #1.5 seems to be good multiplier ... 2.0 is a bit too much;
    # 1.0 is not bad, but occasionally miss something by just a bit

    fit_range_AA = max(GAUSS_FIT_PIX_ERROR * pix_size, GAUSS_FIT_AA_ERROR)
    #fit_range_AA = GAUSS_FIT_PIX_ERROR * pix_size #1.0  # peak must fit to within +/- fit_range AA
                                  # this allows room to fit, but will enforce +/- pix_size after
    #num_of_sigma = 3.0  # number of sigma to include on either side of the central peak to estimate noise

    len_array = len(wavelengths)
    idx = getnearpos(wavelengths,central)
    min_idx = max(0,idx-wave_side)
    max_idx = min(len_array,idx+wave_side)
    wave_x = wavelengths[min_idx:max_idx+1]
    wave_counts = values[min_idx:max_idx+1]
    if (errors is not None) and (len(errors) == len(wavelengths)):
        wave_errors = errors[min_idx:max_idx+1]
        #replace any 0 with 1
        wave_errors[np.where(wave_errors == 0)] = 1
        wave_err_sigma = 1. / (wave_errors * wave_errors) #double checked and this is correct (assuming errors is +/- as expected)
        #as a reminder, if the errors are all the same, then it does not matter what they are, it reduces to the standard
        #arithmetic mean :  Sum 1 to N (x_n**2, sigma_n**2) / (Sum 1 to N (1/sigma_n**2) ==> 1/N * Sum(x_n**2)
        # since sigma_n (as a constant) divides out
    else:
        wave_errors = None
        wave_err_sigma = None

    if False: #do I want to use a more narrow range for the gaussian fit? still uses the wider range for RMSE
        min_idx = max(0, idx - wave_side/2)
        max_idx = min(len_array, idx + wave_side/2)
        narrow_wave_x = wavelengths[min_idx:max_idx+1]
        narrow_wave_counts = values[min_idx:max_idx + 1]
        if (wave_errors is not None):
            narrow_wave_errors = wave_errors[min_idx:max_idx + 1]
            narrow_wave_err_sigma =  wave_err_sigma[min_idx:max_idx + 1]
        else:
            narrow_wave_err_sigma = None
            narrow_wave_errors = None
    else:
        narrow_wave_x = wave_x
        narrow_wave_counts = wave_counts
        narrow_wave_errors = wave_errors
        narrow_wave_err_sigma = wave_err_sigma

    #blunt very negative values
    #wave_counts = np.clip(wave_counts,0.0,np.inf)

    xfit = np.linspace(wave_x[0], wave_x[-1], 1000) #range over which to plot the gaussian equation
    peak_pos = getnearpos(wavelengths, central)

    try:
        # find the highest point in the raw data inside the range we are allowing for the line center fit
        dpix = int(round(fit_range_AA / pix_size))
        raw_peak = max(values[peak_pos-dpix:peak_pos+dpix+1])
        if raw_peak <= 0:
            log.warning("Spectrum::signal_score invalid raw peak %f" %raw_peak)
            return None
    except:
        #this can fail if on very edge, but if so, we would not use it anyway
        log.debug("Raw Peak value failure for wavelength (%f) at index (%d). Cannot fit to gaussian. " %(central,peak_pos))
        return None

    fit_peak = None

    eli = EmissionLineInfo()
    eli.absorber = absorber
    eli.pix_size = pix_size
    eli.fit_bin_dx = values_dx
    num_sn_pix = 0

    bad_curve_fit = False
    if allow_broad:
        max_fit_sigma = GAUSS_FIT_MAX_SIGMA *1.5 + 1.0 # allow a model fit bigger than what is actually acceptable
    else:                                              # so can throw out reall poor broad fits
        max_fit_sigma = GAUSS_FIT_MAX_SIGMA + 1.0

    #use ONLY narrow fit
    try:

        # parm[0] = central point (x in the call), parm[1] = sigma, parm[2] = 'a' multiplier (happens to also be area)
        # parm[3] = y offset (e.g. the "continuum" level)
        #get the gaussian for the more central part, but use that to get noise from wider range
        #sigma lower limit at 0.5 (could make more like pixel_size / 4.0 or so, but probabaly should not depend on that
        # the minimum size is in angstroms anyway, not pixels, and < 0.5 is awfully narrow to be real)
        # instrument resolution ~ 1.9AA/pix (dispersion around 2.2?)

        #if narrow_wave_err_sigma is None:
        #    print("**** NO UNCERTAINTIES ****")
        #   log.warning("**** NO UNCERTAINTIES ****")


        parm, pcov = curve_fit(gaussian, np.float64(narrow_wave_x), np.float64(narrow_wave_counts),
                                p0=(central,1.5,1.0,0.0),
                                bounds=((central-fit_range_AA, 1.0, 0.0, -100.0),
                                        (central+fit_range_AA, max_fit_sigma, 1e5, 1e4)),
                                #sigma=1./(narrow_wave_errors*narrow_wave_errors)
                                sigma=narrow_wave_err_sigma#, #handles the 1./(err*err)
                               #note: if sigma == None, then curve_fit uses array of all 1.0
                               #method='trf'
                               )

        perr = np.sqrt(np.diag(pcov)) #1-sigma level errors on the fitted parameters
        #e.g. flux = a = parm[2]   +/- perr[2]*num_of_sigma_confidence
        #where num_of_sigma_confidence ~ at a 5 sigma confidence, then *5 ... at 3 sigma, *3

        try:
            if not np.any(pcov): #all zeros ... something wrong
                log.info("Something very wrong with curve_fit")
                bad_curve_fit = True
                do_mcmc = True
        except:
            pass

        #gaussian(x, x0, sigma, a=1.0, y=0.0):
        eli.fit_vals = gaussian(xfit, parm[0], parm[1], parm[2], parm[3])
        eli.fit_wave = xfit.copy()
        eli.raw_vals = wave_counts[:]
        eli.raw_wave = wave_x[:]
        if wave_errors is not None:
            eli.raw_errs = wave_errors[:]

        if spectrum is not None:
            try:
                #noise estimate from Spetrcum is from HDF5 and is in 10^-17 units
                if spectrum.noise_estimate is not None:
                    if values_units == -18:
                        m = 10.0
                    else:
                        m = 1.0

                    eli.noise_estimate = spectrum.noise_estimate[:] * m
                if spectrum.noise_estimate_wave is not None:
                    eli.noise_estimate_wave = spectrum.noise_estimate_wave[:]
            except:
                pass

        #matches up with the raw data scale so can do RMSE
        rms_wave = gaussian(wave_x, parm[0], parm[1], parm[2], parm[3])

        eli.fit_x0 = parm[0]
        eli.fit_x0_err = perr[0]
        eli.fit_dx0 = central - eli.fit_x0
        scaled_fit_h = max(eli.fit_vals)
        eli.fit_h = scaled_fit_h
        eli.fit_rh = eli.fit_h / raw_peak
        eli.fit_sigma = parm[1] #units of AA not pixels
        eli.fit_sigma_err = perr[1]
        eli.fit_a = parm[2] #this is an AREA so there are 2 powers of 10.0 in it (hx10 * wx10) if in e-18 units
        eli.fit_a_err = perr[2]
        eli.fit_y = parm[3]
        eli.fit_y_err = perr[3]

        if (values_dx is not None) and (values_dx > 0):
            eli.fit_bin_dx = values_dx
            eli.fit_line_flux = eli.fit_a / eli.fit_bin_dx
            eli.fit_line_flux_err = eli.fit_a_err/eli.fit_bin_dx #assumes no error in fit_bin_dx (and that is true)
            eli.fit_continuum = eli.fit_y / eli.fit_bin_dx
            eli.fit_continuum_err = eli.fit_y_err / eli.fit_bin_dx
        else:
            eli.fit_line_flux = eli.fit_a
            eli.fit_line_flux_err = eli.fit_a_err
            eli.fit_continuum = eli.fit_y
            eli.fit_continuum_err = eli.fit_y_err


        raw_idx = getnearpos(eli.raw_wave, eli.fit_x0)
        if raw_idx < 3:
            raw_idx = 3

        if raw_idx > len(eli.raw_vals)-4:
            raw_idx = len(eli.raw_vals)-4
        #if still out of range, will throw a trapped exception ... we can't use this data anyway
        eli.raw_h = max(eli.raw_vals[raw_idx - 3:raw_idx + 4])
        eli.raw_x0 = eli.raw_wave[getnearpos(eli.raw_vals, eli.raw_h)]

        fit_peak = max(eli.fit_vals)

        if ( abs(fit_peak - raw_peak) > (raw_peak * 0.25) ):
        #if (abs(raw_peak - fit_peak) / raw_peak > 0.2):  # didn't capture the peak ... bad, don't calculate anything else
            #log.warning("Failed to capture peak")
            log.debug("Failed to capture peak: raw = %f , fit = %f, frac = %0.2f" % (raw_peak, fit_peak,
                                                                                 abs(raw_peak - fit_peak) / raw_peak))
        else:
            #check the dx0

            p_err = pix_error(central_z,eli.fit_x0,pix_size=pix_size)

            #old ... here GOOD_MAX_DXO_MULT was in pixel multiples
            #if (abs(eli.fit_dx0) > (GOOD_MAX_DX0_MULT * pix_size + p_err)):
            #    log.debug("Failed to capture peak: dx0 = %f, pix_size = %f, wavelength = %f, pix_z_err = %f"
            #              % (eli.fit_dx0,pix_size, eli.fit_x0,p_err))


            #GOOD_MAX_DX0_MULT[0] is the negative direction, [1] is the positive direction
            #but fit_dx0 is defined as the expected position - fit position, so a positive fit_dx0 has the fit position
            # short (left) of the expected position, which corresponds to the negative offset allowance
            if (eli.fit_dx0 > (GOOD_MAX_DX0_MULT[1] + p_err * pix_size)) or \
               (eli.fit_dx0 < (GOOD_MAX_DX0_MULT[0] + p_err * pix_size)):
                log.debug("Failed to capture peak: dx0 = %f, pix_size = %f, wavelength = %f, pix_z_err = %f"
                          % (eli.fit_dx0,pix_size, eli.fit_x0,p_err))


            else:
                accept_fit = True
                log.debug("Success: captured peak: raw = %f , fit = %f, frac = %0.2f"
                          % (raw_peak, fit_peak, abs(raw_peak - fit_peak) / raw_peak))

                #num_sn_pix = int(round(max(GAUSS_SNR_SIGMA * eli.fit_sigma, GAUSS_SNR_NUM_AA)/pix_size)) #half-width in AA
                num_sn_pix = int(round(max(GAUSS_SNR_SIGMA * eli.fit_sigma, GAUSS_SNR_NUM_AA))) #don't divi by pix_size
                    #at this point, the pixel units or width don't matter ... everything is per pixel
                num_sn_pix = int(round(min(num_sn_pix,len(wave_counts)/2 - 1))) #don't go larger than the actual array

                # if (2 * sigma * 2.355) > (len(narrow_wave_counts)):
                #     # could be very skewed and broad, so don't center on the emission peak, but center on the array
                #     cw_idx = len(narrow_wave_counts) // 2
                # else:
                cw_idx = getnearpos(wave_x, eli.fit_x0 )

                #?rms just under the part of the plot with signal (not the entire fit part) so, maybe just a few AA or pix
                eli.fit_norm_rmse = SU.rms(wave_counts, rms_wave, cw_pix=cw_idx, hw_pix=num_sn_pix,
                             norm=True)
                eli.fit_rmse = SU.rms(wave_counts, rms_wave, cw_pix=cw_idx, hw_pix=num_sn_pix,
                             norm=False)

                #test (though, essentially the curve_fit is a least-squarest fit (which is
                # really just a chi2 fit, (technically IF the model data is Gaussian)), so
                # since we got here from a that fit, this chi2 would have to be small (otherwise
                # the fit would have failed .. and this is the "best" of those fits)
                #chi2, _ = SU.chi_sqr(wave_counts,rms_wave,error=wave_errors,c=1.0,dof=3)
                #scipy_chi2,scipy_pval = chisquare(wave_counts,rms_wave)

                #*2 +1 because the rmse is figures as +/- the "num_sn_pix" from the center pixel (so total width is *2 + 1)
                num_sn_pix = num_sn_pix * 2 + 1 #need full width later (still an integer)

                eli.sn_pix = num_sn_pix
    except Exception as ex:
        try: #bug? in Python3 ... after 3.4 message attribute is lost?
            if ex.message.find("Optimal parameters not found") > -1:
                log.debug("Could not fit gaussian near %f" % central,exc_info=False)
            else:
                log.error("Could not fit gaussian near %f" % central, exc_info=True)
        except:
            try:
                if ex.args[0].find("Optimal parameters not found") > -1:
                    log.debug("Could not fit gaussian near %f" % central, exc_info=False)
            except:
                log.error("Could not fit gaussian near %f" % central, exc_info=True)
        return None

    #if there is a large anchor sigma (the sigma of the "main" line), then the max_sigma can be allowed to go higher
    if allow_broad:
        max_sigma = GAUSS_FIT_MAX_SIGMA * 1.5
    else:
        max_sigma = GAUSS_FIT_MAX_SIGMA

    if (eli.fit_rmse > 0) and (eli.fit_sigma >= min_sigma) and ( 0 < (eli.fit_sigma-eli.fit_sigma_err) <= max_sigma) and \
        (eli.fit_a_err < eli.fit_a ):

        #this snr makes sense IF we assume the noise is distributed as a gaussian (which is reasonable)
        #then we'd be looking at something like 1/N * Sum (sigma_i **2) ... BUT , there are so few pixels
        #  typically around 10 and there really should be at least 30  to approximate the gaussian shape

        eli.snr = eli.fit_a/(np.sqrt(num_sn_pix)*eli.fit_rmse)/np.sqrt(broadfit)
        eli.unique = unique_peak(values,wavelengths,eli.fit_x0,eli.fit_sigma*2.355)

        if not eli.unique and ((eli.fit_a_err / eli.fit_a) > 0.5) and (eli.fit_sigma > GAUSS_FIT_MAX_SIGMA):
            accept_fit = False
            snr = 0.0
            eli.snr = 0.0
            eli.line_score = 0.0
            eli.line_flux = 0.0
        # elif (eli.fit_a_err / eli.fit_a > 0.5):
        #     #error on the area is just to great to trust, regardless of the fit height
        #     accept_fit = False
        #     snr = 0.0
        #     eli.snr = 0.0
        #     eli.line_score = 0.0
        #     eli.line_flux = 0.0
        #     log.debug(f"Fit rejected: fit_a_err/fit_a {eli.fit_a_err / eli.fit_a} > 0.5")
        elif (eli.fit_a_err / eli.fit_a > 0.34) and ((eli.fit_y > 0) and (eli.fit_h/eli.fit_y < 1.66)):
            #error on the area is just to great to trust along with very low peak height (and these are already broad)
            accept_fit = False
            snr = 0.0
            eli.snr = 0.0
            eli.line_score = 0.0
            eli.line_flux = 0.0
            log.debug(f"Fit rejected: fit_a_err/fit_a {eli.fit_a_err / eli.fit_a} > 0.34 and fit_h/fit_y {eli.fit_h/eli.fit_y} < 1.66")
        else:
            eli.build(values_units=values_units,allow_broad=allow_broad,broadfit=broadfit)
            #eli.snr = max(eli.fit_vals) / (np.sqrt(num_sn_pix) * eli.fit_rmse)
            snr = eli.snr
    else:
        accept_fit = False
        snr = 0.0
        eli.snr = 0.0
        eli.line_score = 0.0
        eli.line_flux = 0.0

    log.debug("SNR (fit rmse)  at %0.2f (fiducial = %0.2f) = %0.2f"%(eli.fit_x0,central,snr))
    #log.debug("SNR (vs fibers) at %0.2f (fiducial = %0.2f) = %0.2f"%(eli.fit_x0,central,eli.peak_sigma_above_noise()))

    title = ""

    #todo: re-calibrate to use SNR instead of SBR ??
    sbr = snr
    if sbr is None:
        sbr = est_peak_strength(wavelengths,values,central,values_units)
        if sbr is None:
            #done, no reason to continue
            log.warning("Could not determine SBR at wavelength = %f. Will use SNR." %central)
            sbr = snr

    score = sbr
    eli.sbr = sbr
    sk = -999
    ku = -999
    si = -999
    dx0 = -999 #in AA
    rh = -999
    mx_norm = max(wave_counts)/100.0

    fit_wave = eli.fit_vals
    error = eli.fit_norm_rmse

    #fit around designated emis line
    if (fit_wave is not None):
        sk = skew(fit_wave)
        ku = kurtosis(fit_wave) # remember, 0 is tail width for Normal Dist. ( ku < 0 == thinner tails)
        si = eli.fit_sigma  #*1.9 #scale to angstroms
        dx0 = eli.fit_dx0 #*1.9

        #si and ku are correlated at this scale, for emission lines ... fat si <==> small ku

        height_pix = raw_peak
        height_fit = scaled_fit_h

        if height_pix > 0:
            rh = height_fit/height_pix
        else:
            log.debug("Minimum peak height (%f) too small. Score zeroed." % (height_pix))
            dqs_raw = 0.0
            score = 0.0
            rh = 0.0

        #todo: for lower S/N, sigma (width) can be less and still get bonus if fibers have larger separation

        #new_score:
        if (0.75 < rh < 1.25) and (error < 0.2): # 1 bad pixel in each fiber is okay, but no more

            #central peak position
            #2020-03-09 turn off ... being off in dx0 is handled elsewhere and there are valid physical reasons this can be so
            # if abs(dx0) > pix_size:# 1.9:  #+/- one pixel (in AA)  from center
            #     val = (abs(dx0) - pix_size)** 2
            #     score -= val
            #     log.debug("Penalty for excessive error in X0: %f" % (val))
            #

            #sigma scoring
            if si < 2.0: # and ku < 2.0: #narrow and not huge tails
                val = mx_norm*np.sqrt(2.0 - si)
                score -= val
                log.debug("Penalty for low sigma: %f" % (val))
                #note: si always > 0.0 and rarely < 1.0
            elif si < 2.5:
                pass #zero zone
            elif si < 10.0:
                val = np.sqrt(si-2.5)
                score += val
                log.debug("Bonus for large sigma: %f" % (val))
            elif si < 15.0:
                pass #unexpected, but lets not penalize just yet
            elif not allow_broad: #very wrong (could be a broadline hit)
                if si > (5*min_sigma): #if a large min_sigma is passed in, this can be allowed to be larger w/o penalty
                    val = np.sqrt(si-15.0)
                    score -= val
                    log.debug("Penalty for excessive sigma: %f" % (val))


            #only check the skew for smaller sigma
            #skew scoring

            #2020-03-09 turn off ... noise can be high enough that this is not a valid test
            #plus this gets applied to ALL lines, not just LyA, so this is not a valid check in most cases
            # if si < 2.5:
            #     if sk < -0.5: #skew wrong directionn
            #         val = min(1.0,mx_norm*min(0.5,abs(sk)-0.5))
            #         score -= val
            #         log.debug("Penalty for low sigma and negative skew: %f" % (val))
            #     if (sk > 2.0): #skewed a bit red, a bit peaky, with outlier influence
            #         val = min(0.5,sk-2.0)
            #         score += val
            #         log.debug("Bonus for low sigma and positive skew: %f" % (val))

            base_msg = "Fit dX0 = %g(AA), RH = %0.2f, rms = %0.2f, Sigma = %g(AA), Skew = %g , Kurtosis = %g "\
                   % (dx0, rh, error, si, sk, ku)
            log.debug(base_msg)
        elif rh > 0.0:
            #todo: based on rh and error give a penalty?? maybe scaled by maximum pixel value? (++val = ++penalty)

            if (error > 0.3) and (0.75 < rh < 1.25): #really bad rms, but we did capture the peak
                val = mx_norm*(error - 0.3)
                score -= val
                log.debug("Penalty for excessively bad rms: %f" % (val))
            elif rh < 0.6: #way under shooting peak (should be a wide sigma) (peak with shoulders?)
                val = mx_norm * (0.6 - rh)
                score -= val
                log.debug("Penalty for excessive undershoot peak: %f" % (val))
            elif rh > 1.4: #way over shooting peak (super peaky ... prob. hot pixel?)
                val = mx_norm * (rh - 1.4)
                score -= val
                log.debug("Penalty for excessively overshoot peak: %f" % (val))
        else:
            log.debug("Too many bad pixels or failure to fit peak or overall bad fit. ")
            score = 0.0
    else:
        log.debug("Unable to fit gaussian. ")
        score = 0.0

    mcmc = None
    if do_mcmc:
        mcmc = mcmc_gauss.MCMC_Gauss()
        mcmc.initial_mu = eli.fit_x0

        if bad_curve_fit:
            mcmc.initial_sigma = 1.0
            mcmc.initial_A = raw_peak * 2.35 * mcmc.initial_sigma  # / adjust
        else:
            mcmc.initial_sigma = eli.fit_sigma
            mcmc.initial_A = eli.fit_a  # / adjust
        mcmc.initial_y = eli.fit_y  # / adjust
        mcmc.initial_peak = raw_peak  # / adjust
        mcmc.data_x = narrow_wave_x
        mcmc.data_y = narrow_wave_counts # / adjust
        mcmc.err_y = narrow_wave_errors  # not the 1./err*err .... that is done in the mcmc likelihood function

        # if using the scipy::curve_fit, 50-100 burn-in and ~1000 main run is plenty
        # if other input (like Karl's) ... the method is different and we are farther off ... takes longer to converge
        #   but still converges close to the scipy::curve_fit
        mcmc.burn_in = 250
        mcmc.main_run = 1000
        mcmc.run_mcmc()

        # 3-tuple [0] = fit, [1] = fit +16%,  [2] = fit - 16%
        eli.mcmc_x0 = mcmc.mcmc_mu
        eli.mcmc_sigma = mcmc.mcmc_sigma
        eli.mcmc_snr = mcmc.mcmc_snr

        if mcmc.mcmc_A is not None:
            eli.mcmc_a = np.array(mcmc.mcmc_A)
            if (values_dx is not None) and (values_dx > 0):
                eli.mcmc_dx = values_dx
                eli.mcmc_line_flux = eli.mcmc_a[0]/values_dx
                eli.mcmc_line_flux_tuple =  np.array(mcmc.mcmc_A)/values_dx
        else:
            eli.mcmc_a = np.array((0.,0.,0.))
            eli.mcmc_line_flux = eli.mcmc_a[0]

        if mcmc.mcmc_y is not None:
            eli.mcmc_y = np.array(mcmc.mcmc_y)
            if (values_dx is not None) and (values_dx > 0):
                eli.mcmc_dx = values_dx
                eli.mcmc_continuum = eli.mcmc_y[0]
                eli.mcmc_continuum_tuple = np.array(mcmc.mcmc_y)
        else:
            eli.mcmc_y = np.array((0.,0.,0.))
            eli.mcmc_continuum = eli.mcmc_y[0]

        if values_units < 0:
            eli.mcmc_a *= 10**values_units
            eli.mcmc_y *= 10**values_units
            eli.mcmc_continuum  *= 10**values_units
            eli.mcmc_line_flux *= 10**values_units
            try:
                eli.mcmc_line_flux_tuple *= 10 ** values_units
                eli.mcmc_continuum_tuple *= 10 ** values_units
            except:
                log.error("*** Exception!", exc_info=True)

            #no ... this is wrong ... its all good now
        # if values_units == -18:  # converted from e-17, but this is an area so there are 2 factors
        #     eli.mcmc_a = tuple(np.array(eli.mcmc_a ) / [10., 1., 1.])

        # calc EW and error with approximate symmetric error on area and continuum
        if eli.mcmc_y[0] != 0 and eli.mcmc_a[0] != 0:
            ew = eli.mcmc_a[0] / eli.mcmc_y[0]
            ew_err = ew * np.sqrt((mcmc.approx_symmetric_error(eli.mcmc_a) / eli.mcmc_a[0]) ** 2 +
                                  (mcmc.approx_symmetric_error(eli.mcmc_y) / eli.mcmc_y[0]) ** 2)
        else:
            ew = eli.mcmc_a[0]
            ew_err = mcmc.approx_symmetric_error(eli.mcmc_a)


        eli.mcmc_ew_obs = [ew, ew_err, ew_err]
        log.debug("MCMC Peak height = %f" % (max(narrow_wave_counts)))
        log.debug("MCMC calculated EW_obs for main line = %0.3g +/- %0.3g" % (ew, ew_err))


    if show_plot or G.DEBUG_SHOW_GAUSS_PLOTS:# or eli.snr > 40.0:
        if error is None:
            error = -1

        g = eli.is_good(z=central_z,allow_broad=allow_broad)
        a = accept_fit

        # title += "%0.2f z_guess=%0.4f A(%d) G(%d)\n" \
        #          "Score = %0.2f (%0.1f), SBR = %0.2f (%0.1f), SNR = %0.2f (%0.1f) wpix = %d\n" \
        #          "Peak = %0.2g, Line(A) = %0.2g, Cont = %0.2g, EqW_Obs=%0.2f\n"\
        #          "dX0 = %0.2f, RH = %0.2f, RMS = %0.2f (%0.2f) \n"\
        #          "Sigma = %0.2f, Skew = %0.2f, Kurtosis = %0.2f"\
        #           % (eli.fit_x0,central_z,a,g,score, signal_calc_scaled_score(score),sbr,
        #              signal_calc_scaled_score(sbr),snr,signal_calc_scaled_score(snr),num_sn_pix,
        #              eli.fit_h,eli.line_flux, eli.cont,eli.eqw_obs,
        #              dx0, rh, error,eli.fit_rmse, si, sk, ku)

        if eli.absorber:
            line_type = "[Absorption]"
        else:
            line_type = ""

        title += "%0.2f z_guess=%0.4f A(%d) G(%d) %s\n" \
                 "Line Score = %0.2f , SNR = %0.2f (%0.1f) , wpix = %d, LineFlux = %0.2g\n" \
                 "Peak = %0.2g, Area = %0.2g, Y = %0.2g, EqW_Obs=%0.2f\n"\
                 "dX0 = %0.2f, RH = %0.2f, RMS = %0.2f (%0.2f) \n"\
                 "Sigma = %0.2f, Skew = %0.2f, Kurtosis = %0.2f"\
                  % (eli.fit_x0,central_z,a,g,line_type,eli.line_score,
                     snr,signal_calc_scaled_score(snr),num_sn_pix,eli.fit_line_flux,
                     eli.fit_h,eli.fit_a, eli.fit_y,eli.eqw_obs,
                     dx0, rh, error,eli.fit_rmse, si, sk, ku)

        fig = plt.figure()
        gauss_plot = plt.axes()

        gauss_plot.plot(wave_x,wave_counts,c='k')

        try:
            gauss_plot.axvline(x=central,c='k',linestyle="--")
            gauss_plot.axvline(x=central+fit_range_AA, c='r', linestyle="--")
            gauss_plot.axvline(x=central-fit_range_AA, c='r', linestyle="--")
            if num_sn_pix > 0:
                half_sn = (num_sn_pix - 1) / 2. * pix_size

                gauss_plot.axvline(x=central + half_sn, c='g')
                gauss_plot.axvline(x=central - half_sn, c='g')
        except:
            log.debug("Cannot plot central line fit boundaries.",exc_info=True)

        if fit_wave is not None:
            gauss_plot.plot(xfit, fit_wave, c='b',zorder=99,lw=1)
            gauss_plot.grid(True)
        #     ymin = min(min(fit_wave),min(wave_counts))
        #     ymax = max(max(fit_wave),max(wave_counts))
        # else:
        #     ymin = min(wave_counts)
        #     ymax = max(wave_counts)

        if mcmc is not None:
            try:

              #  y,y_unc = gaussian_unc(narrow_wave_x, mcmc.mcmc_mu[0], mcmc.approx_symmetric_error(mcmc.mcmc_mu),
              #                         mcmc.mcmc_sigma[0], mcmc.approx_symmetric_error(mcmc.mcmc_sigma),
              #                         mcmc.mcmc_A[0], mcmc.approx_symmetric_error(mcmc.mcmc_A),
              #                         mcmc.mcmc_y[0], mcmc.approx_symmetric_error(mcmc.mcmc_y))
              #
              #  gauss_plot.errorbar(narrow_wave_x,y,yerr=[y_unc,y_unc],fmt="--o",alpha=0.5,color='green')

                y, y_unc = gaussian_unc(xfit, mcmc.mcmc_mu[0], mcmc.approx_symmetric_error(mcmc.mcmc_mu),
                                        mcmc.mcmc_sigma[0], mcmc.approx_symmetric_error(mcmc.mcmc_sigma),
                                        mcmc.mcmc_A[0], mcmc.approx_symmetric_error(mcmc.mcmc_A),
                                        mcmc.mcmc_y[0], mcmc.approx_symmetric_error(mcmc.mcmc_y))


                gauss_plot.fill_between(xfit,y+y_unc,y-y_unc,alpha=0.4,color='g')
                gauss_plot.plot(xfit, y, c='g', lw=1,alpha=1)#,zorder=1)

                #gauss_plot.plot(xfit,gaussian(xfit,mcmc.mcmc_mu[0], mcmc.mcmc_sigma[0],mcmc.mcmc_A[0],mcmc.mcmc_y[0]),
                #            c='b', lw=10,alpha=0.2,zorder=1)
            except:
                log.warning("Exception in spectrum::signal_score() trying to plot mcmc output." ,exc_info=True)


        gauss_plot.set_ylabel("Flux [unsp] ")
        gauss_plot.set_xlabel("Wavelength [$\AA$] ")

        # ymin, ymax = gauss_plot.get_ylim()
        #
        # ymin *= 1.1
        # ymax *= 1.1
        #
        # if abs(ymin) < 1.0: ymin = -1.0
        # if abs(ymax) < 1.0: ymax = 1.0

       # gauss_plot.set_ylim((ymin,ymax))
        gauss_plot.set_xlim( (np.floor(wave_x[0]),np.ceil(wave_x[-1])) )
        gauss_plot.set_title(title)
        stat = ""
        if a:
            stat += "a"
        if g:
            stat += "g"

        if plot_id is not None:
            plot_id = "_" + str(plot_id) + "_"
        else:
            plot_id = "_"
        png = "gauss" + plot_id + str(central)+ "_" + stat + ".png"

        if plot_path is not None:
            png = op.join(plot_path,png)

        log.info('Writing: ' + png)
        #print('Writing: ' + png)
        fig.tight_layout()
        fig.savefig(png)

        if eli is not None:
            eli.gauss_plot_buffer = io.BytesIO()
            plt.savefig(eli.gauss_plot_buffer, format='png', dpi=300)

        fig.clear()
        plt.close()

        if mcmc is not None:
            png = "mcmc" + plot_id + str(central) + "_" + stat + ".png"
            if plot_path is not None:
                png = op.join(plot_path, png)
            buf = mcmc.visualize(png)

            if eli is not None:
                eli.mcmc_plot_buffer = buf

        # end plotting

    if accept_fit:
        eli.raw_score = score
        eli.score = signal_calc_scaled_score(score)
        log.debug(f"Fit not rejected. eli score: {eli.score} line score: {eli.line_score}")
        return eli
    else:
        log.debug("Fit rejected")
        return None




def run_mcmc(eli,wavelengths,values,errors,central,values_units,values_dx=G.FLUX_WAVEBIN_WIDTH):

    #values_dx is the bin width for the values if multiplied out (s|t) values are flux and not flux/dx
    #   by default, Karl's data is on a 2.0 AA bin width

    err_units = values_units  # assumed to be in the same units
    values, values_units = norm_values(values, values_units)
    if errors is not None and (len(errors) == len(values)):
        errors, err_units = norm_values(errors, err_units)

    pix_size = abs(wavelengths[1] - wavelengths[0])  # aa per pix
    wave_side = int(round(GAUSS_FIT_AA_RANGE / pix_size))  # pixels
    fit_range_AA = max(GAUSS_FIT_PIX_ERROR * pix_size, GAUSS_FIT_AA_ERROR)

    len_array = len(wavelengths)
    idx = getnearpos(wavelengths, central)
    min_idx = max(0, idx - wave_side)
    max_idx = min(len_array, idx + wave_side)
    wave_x = wavelengths[min_idx:max_idx + 1]
    wave_counts = values[min_idx:max_idx + 1]
    if (errors is not None) and (len(errors) == len(wavelengths)):
        wave_errors = errors[min_idx:max_idx + 1]
        # replace any 0 with 1
        wave_errors[np.where(wave_errors == 0)] = 1
    else:
        wave_errors = None

    narrow_wave_x = wave_x
    narrow_wave_counts = wave_counts
    narrow_wave_errors = wave_errors

    fit_range_AA = max(GAUSS_FIT_PIX_ERROR * pix_size, GAUSS_FIT_AA_ERROR)
    peak_pos = getnearpos(wavelengths, central)

    try:
        # find the highest point in the raw data inside the range we are allowing for the line center fit
        dpix = int(round(fit_range_AA / pix_size))
        raw_peak = max(values[peak_pos - dpix:peak_pos + dpix + 1])
        if raw_peak <= 0:
            log.warning("Spectrum::run_mcmc invalid raw peak %f" % raw_peak)
            return eli
    except:
        # this can fail if on very edge, but if so, we would not use it anyway
        log.debug(
            "Raw Peak value failure for wavelength (%f) at index (%d). Cannot fit to gaussian. " % (central, peak_pos))
        return eli


    mcmc = mcmc_gauss.MCMC_Gauss()
    mcmc.initial_mu = eli.fit_x0
    mcmc.initial_sigma = eli.fit_sigma
    mcmc.initial_A = eli.fit_a  # / adjust
    mcmc.initial_y = eli.fit_y  # / adjust
    mcmc.initial_peak = raw_peak  # / adjust
    mcmc.data_x = narrow_wave_x
    mcmc.data_y = narrow_wave_counts  # / adjust
    mcmc.err_y = narrow_wave_errors  # not the 1./err*err .... that is done in the mcmc likelihood function

    # if using the scipy::curve_fit, 50-100 burn-in and ~1000 main run is plenty
    # if other input (like Karl's) ... the method is different and we are farther off ... takes longer to converge
    #   but still converges close to the scipy::curve_fit
    mcmc.burn_in = 250
    mcmc.main_run = 1000

    try:
        mcmc.run_mcmc()
    except:
        log.warning("Exception in spectrum.py calling mcmc.run_mcmc()", exc_info=True)
        return eli

    # 3-tuple [0] = fit, [1] = fit +16%,  [2] = fit - 16%
    eli.mcmc_x0 = mcmc.mcmc_mu
    eli.mcmc_sigma = mcmc.mcmc_sigma
    eli.mcmc_snr = mcmc.mcmc_snr

    if mcmc.mcmc_A is not None:
        eli.mcmc_a = np.array(mcmc.mcmc_A)
        if (values_dx is not None) and (values_dx > 0):
            eli.mcmc_dx = values_dx
            eli.mcmc_line_flux = eli.mcmc_a[0] / eli.mcmc_dx
            eli.mcmc_line_flux_tuple =  np.array(mcmc.mcmc_A)/values_dx
    else:
        eli.mcmc_a = np.array((0., 0., 0.))
        eli.mcmc_line_flux = eli.mcmc_a[0]

    if mcmc.mcmc_y is not None:
        eli.mcmc_y = np.array(mcmc.mcmc_y)
        if (values_dx is not None) and (values_dx > 0):
            eli.mcmc_dx = values_dx
            eli.mcmc_continuum = eli.mcmc_y[0]
            eli.mcmc_continumm_tuple =  np.array(mcmc.mcmc_y)
    else:
        eli.mcmc_y = np.array((0., 0., 0.))
        eli.mcmc_continuum = eli.mcmc_y[0]

    if values_units < 0:
        eli.mcmc_a *= 10 ** values_units
        eli.mcmc_y *= 10 ** values_units
        eli.mcmc_continuum *= 10 ** values_units
        eli.mcmc_line_flux *= 10 ** values_units
        try:
            eli.mcmc_line_flux_tuple *= 10 ** values_units
            eli.mcmc_continuum_tuple *= 10 ** values_units
        except:
            log.error("*** Exception!",exc_info=True)

    # calc EW and error with approximate symmetric error on area and continuum
    if eli.mcmc_y[0] != 0 and eli.mcmc_a[0] != 0:
        ew = eli.mcmc_a[0] / eli.mcmc_y[0]
        ew_err = ew * np.sqrt((mcmc.approx_symmetric_error(eli.mcmc_a) / eli.mcmc_a[0]) ** 2 +
                              (mcmc.approx_symmetric_error(eli.mcmc_y) / eli.mcmc_y[0]) ** 2)
    else:
        ew = eli.mcmc_a[0]
        ew_err = mcmc.approx_symmetric_error(eli.mcmc_a)

    eli.mcmc_ew_obs = [ew, ew_err, ew_err]
    log.debug("MCMC Peak height = %f" % (max(narrow_wave_counts)))
    log.debug("MCMC calculated EW_obs for main line = %0.3g +/- %0.3g" % (ew, ew_err))



    return eli


def signal_calc_scaled_score(raw):
    # 5 point scale
    # A+ = 5.0
    # A  = 4.0
    # B+ = 3.5
    # B  = 3.0
    # C+ = 2.5
    # C  = 2.0
    # D+ = 1.5
    # D  = 1.0
    # F  = 0

    a_p = 14.0
    a__ = 12.5
    a_m = 11.0
    b_p = 8.0
    b__ = 7.0
    c_p = 6.0
    c__ = 5.0
    d_p = 4.0
    d__ = 3.0
    f__ = 2.0

    if raw is None:
        return 0.0
    else:
        hold = False

    if   raw > a_p : score = 5.0  #A+
    elif raw > a__ : score = 4.5 + 0.5*(raw-a__)/(a_p-a__) #A
    elif raw > a_m : score = 4.0 + 0.5*(raw-a_m)/(a__-a_m) #A-
    elif raw > b_p : score = 3.5 + 0.5*(raw-b_p)/(a_m-b_p) #B+ AB
    elif raw > b__ : score = 3.0 + 0.5*(raw-b__)/(b_p-b__) #B
    elif raw > c_p : score = 2.5 + 0.5*(raw-c_p)/(b__-c_p) #C+ BC
    elif raw > c__ : score = 2.0 + 0.5*(raw-c__)/(c_p-c__) #C
    elif raw > d_p : score = 1.5 + 0.5*(raw-d_p)/(c__-d_p) #D+ CD
    elif raw > d__ : score = 1.0 + 0.5*(raw-d__)/(d_p-d__) #D
    elif raw > f__ : score = 0.5 + 0.5*(raw-f__)/(d__-f__) #F
    elif raw > 0.0 : score =  0.5*raw/f__
    else: score = 0.0

    score = round(score,1)

    return score


# def est_ew_obs(fwhm=None,peak=None, wavelengths=None, values=None, central=None,values_units=0):
#
#     try:
#         if (wavelengths is not None) and (values is not None) and (central is not None):
#             fwhm =  est_fwhm(wavelengths,values,central,values_units)
#             if peak is None:
#                 peak = values[getnearpos(wavelengths, central)]
#
#         if (fwhm is not None) and (peak is not None):
#             return pix_to_aa(fwhm)*peak
#         else:
#             return None
#     except:
#         log.error("Error in spectrum::est_ew",exc_info=True)
#         return None
#
# def est_ew_rest():
#     #need to know z
#     pass
#
#


def est_fwhm(wavelengths,values,central,values_units=0):

    num_pix = len(wavelengths)
    idx = getnearpos(wavelengths, central)

    values, values_units = norm_values(values,values_units)

    background,zero = est_background(wavelengths,values,central,values_units)

    if zero is None:
        zero = 0.0

    hm = (values[idx] - zero) / 2.0

    #hm = float((pv - zero) / 2.0)
    pix_width = 0

    # for centroid (though only down to fwhm)
    sum_pos_val = wavelengths[idx] * values[idx]
    sum_pos = wavelengths[idx]
    sum_val = values[idx]

    # check left
    pix_idx = idx - 1

    try:
        while (pix_idx >= 0) and ((values[pix_idx] - zero) >= hm) \
                and ((values[pix_idx] -zero) < values[idx]):
            sum_pos += wavelengths[pix_idx]
            sum_pos_val += wavelengths[pix_idx] * values[pix_idx]
            sum_val += values[pix_idx]
            pix_width += 1
            pix_idx -= 1

    except:
        pass

    # check right
    pix_idx = idx + 1

    try:
        while (pix_idx < num_pix) and ((values[pix_idx]-zero) >= hm) \
                and ((values[pix_idx] - zero) < values[idx]):
            sum_pos += wavelengths[pix_idx]
            sum_pos_val += wavelengths[pix_idx] * values[pix_idx]
            sum_val += values[pix_idx]
            pix_width += 1
            pix_idx += 1
    except:
        pass

    #print("FWHM = %f at %f" %(pix_width, central))

    return pix_width

def est_background(wavelengths,values,central,values_units = 0,dw=DEFAULT_BACKGROUND_WIDTH,xw=10.0,peaks=None,valleys=None):
    """
    mean of surrounding (simple) peaks, excluding any obvious lines (above 3x std) - the zero

    :param wavelengths: [array] position (wavelength) coordinates of spectra
    :param values: [array] values of the spectra
    :param central: central wavelength aboout which to estimate noise
    :param dw: width about the central wavelength over which to estimate noise
    :param xw: width from the central wavelength to begin the dw window
               that is, average over all peaks between (c-xw-dw) and (c-xw) AND (c+xw) and (c+xw+dw)
               like a 1d annulus
    :param px: optional peak coordinates (wavelengths)
    :param pv: optional peak values (counts)
    :return: background, zero
    """

    values, values_units = norm_values(values, values_units)

    xw = max(DEFAULT_MIN_WIDTH_FROM_CENTER_FOR_BACKGROUND,xw)

    outlier_x = 3.0
    background = DEFAULT_BACKGROUND
    wavelengths = np.array(wavelengths)
    values = np.array(values)
    zero = None

    if dw > len(wavelengths)/2.0:
        return None, None

    try:
        # peaks, vallyes are 3D arrays = [index in original array, wavelength, value]
        if peaks is None or valleys is None:
            peaks, valleys = simple_peaks(wavelengths,values,values_units=values_units)

        if peaks is None or len(peaks) < 1:
            log.debug("No peaks returned. spectrum::est_background(...). Values range (%f,%f)" %(min(values),max(values)))
            return background, zero

        #get all the peak values that are in our background sample range
        peak_v = peaks[:,2]
        peak_w = peaks[:,1]

        peak_v = peak_v[((peak_w >= (central - xw - dw)) & (peak_w <= (central - xw))) |
                   ((peak_w >= (central + xw)) & (peak_w <= (central + xw + dw)))]

        # get all the valley values that are in our background sample range
        valley_v = valleys[:, 2]
        valley_w = valleys[:, 1]

        valley_v = valley_v[((valley_w >= (central - xw - dw)) & (valley_w <= (central - xw))) |
                        ((valley_w >= (central + xw)) & (valley_w <= (central + xw + dw)))]

        #remove outliers (under assumption that extreme outliers are signals or errors)
        if (len(peak_v) > 3) and (len(valley_v) > 3):
            peak_v = peak_v[abs(peak_v - np.mean(peak_v)) < abs(outlier_x * np.std(peak_v))]
            valley_v = valley_v[abs(valley_v-np.mean(valley_v)) < abs(outlier_x * np.std(valley_v))]
        else:
            background, zero = est_background(wavelengths, values, central, values_units,
                                              dw * 2, xw, peaks=None, valleys=None)
            return background, zero

        #zero point is the total average
        zero = np.mean(np.append(peak_v,valley_v))

        if len(peak_v) > 2:
            peak_background = np.mean(peak_v) - zero
            #peak_background = np.std(peak_v)**2
        else:
            background, zero = est_background(wavelengths,values,central,values_units,dw*2,xw,peaks=None,valleys=None)
            return background, zero

       # since looking for emission, not absorption, don't care about the valley background
       # if len(valley_v) > 2: #expected to be negavive
       #     valley_background = np.mean(valley_v) - zero
       #     #valley_background = np.std(valley_v) ** 2
       # else:
       #     valley_background = DEFAULT_BACKGROUND

        background = peak_background

    except:
        log.error("Exception estimating background: ", exc_info=True)

    return background, zero


#todo: detect and estimate contiuum (? as SNR or mean value? over some range(s) of wavelength?)
# ie. might have contiuum over just part of the spectra
def est_continuum(wavengths,values,central):
    pass

#todo: actual signal
def est_signal(wavelengths,values,central,xw=None,zero=0.0):
    pass

#todo: actual noise, not just the local background
def est_noise():
    pass


def unique_peak(spec,wave,cwave,fwhm,width=10.0,frac=0.9):
    """
    Is the peak at cwave relatively unique (is it the highest within some range
    :param spec:
    :param wave:
    :param cwave:
    :param fwhm:
    :param width: number of angstroms to look to either side of the peak (and sd)
    :param frac: fraction of peak value to compare
    :return:
    """

    try:
        peak_val = max(spec[list(SU.getnearpos(wave,cwave))]) #could be +/-1 to either side (depending on binning), so use all returns
        blue_stop, *_ = SU.getnearpos(wave,cwave-fwhm)
        red_start, *_ = SU.getnearpos(wave,cwave+fwhm)

        blue_start,*_ = SU.getnearpos(wave,cwave-fwhm - width)
        red_stop, *_ = SU.getnearpos(wave,cwave+fwhm + width)

        region = np.concatenate((spec[blue_start:blue_stop+1],spec[red_start:red_stop+1]))
        hits = np.where(region > (frac * peak_val))[0]

        if len(hits) < 3: #1 or 2 hits could be a barely resolved doublet (or at least adjacent lines)
            return True
        else:
            log.debug(f"Peak {cwave} appears to be in noise.")
            return False


    except:
        log.debug("Exception in spectrum::unique_peak.",exc_info=True)
        return False



def est_peak_strength(wavelengths,values,central,values_units=0,dw=DEFAULT_BACKGROUND_WIDTH,peaks=None,valleys=None):
    """

    :param wavelengths:
    :param values:
    :param central:
    :param dw:
    :param xw:
    :param px:
    :param pv:
    :return:
    """
    values, values_units = norm_values(values, values_units)

    sbr = None #Signal to Background Ratio  (similar to SNR)
    xw = est_fwhm(wavelengths,values,central,values_units)

    background,zero = est_background(wavelengths,values,central,values_units,dw,xw,peaks,valleys)

    if background is not None:
        # signal = nearest values (pv) to central ?? or average of a few near the central wavelength
        #signal = est_signal(wavelengths,values,central,xw,zero)

        peak_pos = getnearpos(wavelengths, central)
        try:
            peak_str = max(values[peak_pos - 1:peak_pos + 2]) - zero
        except:
            # this can fail if on very edge, but if so, we would not use it anyway
            log.debug("Raw Peak value failure for wavelength (%f) at index (%d). Cannot calculate SBR. "
                     % (central, peak_pos))
            return 0

        #signal = ((np.sqrt(signal)-zero)/2.0)**2

        if peak_str is not None:
           # sbr = (signal-background)/(background)
           sbr = peak_str/background

    return sbr


#todo: update to deal with flux instead of counts
#def simple_peaks(x,v,h=MIN_HEIGHT,delta_v=2.0,values_units=0):
def simple_peaks(x, v, h=None, delta_v=None, values_units=0):
    """

    :param x:
    :param v:
    :return:  #3 arrays: index of peaks, coordinate (wavelength) of peaks, values of peaks
              2 3D arrays: index, wavelength, value for (1) peaks and (2) valleys
    """

    maxtab = []
    mintab = []

    if h is None:
        h = np.mean(v)*0.8 #assume the mean to be roughly like the continuum level ... make min height with some slop

    if delta_v is None:
        delta_v = 0.2*h

    if x is None:
        x = np.arange(len(v))

    v, values_units = norm_values(v, values_units)

    v = np.asarray(v)
    num_pix = len(v)

    if num_pix != len(x):
        log.warning('simple_peaks: Input vectors v and x must have same length')
        return None,None

    minv, maxv = np.Inf, -np.Inf
    minpos, maxpos = np.NaN, np.NaN

    lookformax = True

    for i in np.arange(len(v)):
        thisv = v[i]
        if thisv > maxv:
            maxv = thisv
            maxpos = x[i]
            maxidx = i
        if thisv < minv:
            minv = thisv
            minpos = x[i]
            minidx = i
        if lookformax:
            if (thisv >= h) and (thisv < maxv - delta_v):
                #i-1 since we are now on the right side of the peak and want the index associated with max
                maxtab.append((maxidx,maxpos, maxv))
                minv = thisv
                minpos = x[i]
                lookformax = False
        else:
            if thisv > minv + delta_v:
                mintab.append((minidx,minpos, minv))
                maxv = thisv
                maxpos = x[i]
                lookformax = True

    #return np.array(maxtab)[:, 0], np.array(maxtab)[:, 1], np.array(maxtab)[:, 2]
    return np.array(maxtab), np.array(mintab)




def sn_peakdet_no_fit(wave,spec,spec_err,dx=3,rx=2,dv=2.0,dvmx=3.0):
    """

    :param wave: x-values (wavelength)
    :param spec: v-values (spectrum values)
    :param spec_err: error on v (treat as 'noise')
    :param dx: minimum number of x-bins to trigger a possible line detection
    :param rx: like dx but just for rise and fall
    :param dv:  minimum height in value (in s/n, not native values) to trigger counting of bins
    :param dvmx: at least one point though must be >= to this in S/N
    :return:
    """

    try:
        if not (len(wave) == len(spec) == len(spec_err)):
            log.debug("Bad call to sn_peakdet(). Lengths of arrays do not match")
            return []

        x = np.array(wave)
        v = np.array(spec)
        e = np.array(spec_err)
        sn = v/e
        hvi = np.where(sn > dv)[0] #hvi high v indicies (where > dv)

        if len(hvi) < 1:
            log.debug(f"sn_peak - no bins above minimum snr {dv}")
            return []

        pos = [] #positions to search (indicies into original wave array)
        run = [hvi[0],]
        rise = [hvi[0],] #assume start with a rise
        fall = []

        #two ways to trigger a peak:
        #several bins in a row above the SNR cut, then one below
        #or many bins in a row, that rise then fall with lengths of rise and fall above the dx length
        for h in hvi:
            if (h-1) == run[-1]: #the are adjacent in the original arrays
                #what about sharp drops in value? like multiple peaks above continuum?
                if v[h] >= v[run[-1]]: #rising
                    rise.append(h)
                    if len(rise) >= rx:
                        rise_trigger = True
                        fall = []
                else: #falling
                    fall.append(h)
                    if len(fall) >= rx: #assume the end of a line and trigger a new run
                        fall_trigger = True
                        rise = []
                if rise_trigger and fall_trigger: #call this a peak, start a new run
                    if len(run) >= dx and np.any(sn[run] >= dvmx):
                        mx = np.argmax(v[run])  # find largest value in the original arrays from these indicies
                        pos.append(mx + run[0])  # append that position to pos
                    run = [h]  # start a new run
                    rise = [h]
                    fall = []
                    fall_trigger = False
                    rise_trigger = False
                else:
                    run.append(h)

            else: #not adjacent, are there enough in run to append?
                if len(run) >= dx and np.any(sn[run] >= dvmx):
                    mx = np.argmax(v[run]) #find largest value in the original arrays from these indicies
                    pos.append(mx+run[0]) #append that position to pos
                run = [h] #start a new run
                rise = [h]
                fall = []
                fall_trigger = False
                rise_trigger = False
    except:
        log.error("Exception in sn_peakdet",exc_info=True)
        return []

    return pos


def sn_peakdet(wave,spec,spec_err,dx=3,rx=2,dv=2.0,dvmx=3.0,values_units=0,
            enforce_good=True,min_sigma=GAUSS_FIT_MIN_SIGMA,absorber=False,do_mcmc=False):
    """

    :param wave: x-values (wavelength)
    :param spec: v-values (spectrum values)
    :param spec_err: error on v (treat as 'noise')
    :param dx: minimum number of x-bins to trigger a possible line detection
    :param rx: like dx but just for rise and fall
    :param dv:  minimum height in value (in s/n, not native values) to trigger counting of bins
    :param dvmx: at least one point though must be >= to this in S/N
    :param values_units:
    :param enforce_good:
    :param min_sigma:
    :param absorber:
    :return:
    """

    eli_list = []

    try:
        if not (len(wave) == len(spec) == len(spec_err)):
            log.debug("Bad call to sn_peakdet(). Lengths of arrays do not match")
            return []

        x = np.array(wave)
        v = np.array(spec)
        e = np.array(spec_err)
        sn = v/e
        hvi = np.where(sn > dv)[0] #hvi high v indicies (where > dv)

        if len(hvi) < 1:
            log.debug(f"sn_peak - no bins above minimum snr {dv}")
            return []

        pos = [] #positions to search (indicies into original wave array)
        run = [hvi[0],]
        rise = [hvi[0],] #assume start with a rise
        fall = []

        #two ways to trigger a peak:
        #several bins in a row above the SNR cut, then one below
        #or many bins in a row, that rise then fall with lengths of rise and fall above the dx length
        for h in hvi:
            if (h-1) == run[-1]: #the are adjacent in the original arrays
                #what about sharp drops in value? like multiple peaks above continuum?
                if v[h] >= v[run[-1]]: #rising
                    rise.append(h)
                    if len(rise) >= rx:
                        rise_trigger = True
                        fall = []
                else: #falling
                    fall.append(h)
                    if len(fall) >= rx: #assume the end of a line and trigger a new run
                        fall_trigger = True
                        rise = []
                if rise_trigger and fall_trigger: #call this a peak, start a new run
                    if len(run) >= dx and np.any(sn[run] >= dvmx):
                        mx = np.argmax(v[run])  # find largest value in the original arrays from these indicies
                        pos.append(mx + run[0])  # append that position to pos
                    run = [h]  # start a new run
                    rise = [h]
                    fall = []
                    fall_trigger = False
                    rise_trigger = False
                else:
                    run.append(h)

            else: #not adjacent, are there enough in run to append?
                if len(run) >= dx and np.any(sn[run] >= dvmx):
                    mx = np.argmax(v[run]) #find largest value in the original arrays from these indicies
                    pos.append(mx+run[0]) #append that position to pos
                run = [h] #start a new run
                rise = [h]
                fall = []
                fall_trigger = False
                rise_trigger = False

        #now pos has the indicies in the original arrays of the highest values in runs of high S/N bins
        for p in pos:
            try:
                eli = signal_score(wave, spec, spec_err, wave[p], values_units=values_units, min_sigma=min_sigma,
                               absorber=absorber,do_mcmc=do_mcmc)

                # if (eli is not None) and (eli.score > 0) and (eli.snr > 7.0) and (eli.fit_sigma > 1.6) and (eli.eqw_obs > 5.0):
                if (eli is not None) and ((not enforce_good) or eli.is_good()):
                    #extra check for broadlines the score must be higher than usual
                    #if (min_sigma < 4.0) or ((min_sigma >= 4.0) and (eli.line_score > 25.0)):
                    eli_list.append(eli)
            except:
                log.error("Exception calling signal_score in sn_peakdet",exc_info=True)

    except:
        log.error("Exception in sn_peakdet",exc_info=True)
        return []

    return combine_lines(eli_list)

def peakdet(x,v,err=None,dw=MIN_FWHM,h=MIN_HEIGHT,dh=MIN_DELTA_HEIGHT,zero=0.0,values_units=0,
            enforce_good=True,min_sigma=GAUSS_FIT_MIN_SIGMA,absorber=False):

    """

    :param x:
    :param v:
    :param dw:
    :param h:
    :param dh:
    :param zero:
    :return: array of [ pi, px, pv, pix_width, centroid_pos, eli.score, eli.snr]
    """

    #peakind = signal.find_peaks_cwt(v, [2,3,4,5],min_snr=4.0) #indexes of peaks

    #emis = zip(peakind,x[peakind],v[peakind])
    #emistab.append((pi, px, pv, pix_width, centroid))
    #return emis



    #dh (formerly, delta)
    #dw (minimum width (as a fwhm) for a peak, else is noise and is ignored) IN PIXELS
    # todo: think about jagged peaks (e.g. a wide peak with many subpeaks)
    #zero is the count level zero (nominally zero, but with noise might raise or lower)
    """
    Converted from MATLAB script at http://billauer.co.il/peakdet.html


    function [maxtab, mintab]=peakdet(v, delta, x)
    %PEAKDET Detect peaks in a vector
    %        [MAXTAB, MINTAB] = PEAKDET(V, DELTA) finds the local
    %        maxima and minima ("peaks") in the vector V.
    %        MAXTAB and MINTAB consists of two columns. Column 1
    %        contains indices in V, and column 2 the found values.
    %
    %        With [MAXTAB, MINTAB] = PEAKDET(V, DELTA, X) the indices
    %        in MAXTAB and MINTAB are replaced with the corresponding
    %        X-values.
    %
    %        A point is considered a maximum peak if it has the maximal
    %        value, and was preceded (to the left) by a value lower by
    %        DELTA.

    % Eli Billauer, 3.4.05 (Explicitly not copyrighted).
    % This function is released to the public domain; Any use is allowed.

    """

    if (v is None) or (len(v) < 3):
        return [] #cannot execute


    maxtab = []
    mintab = []
    emistab = []
    eli_list = []
    delta = dh

    eli_list = sn_peakdet(x,v,err,values_units=values_units,enforce_good=enforce_good,min_sigma=min_sigma,
                          absorber=absorber)


    if True:
        try:
            #repeat with median filter and kick up the minimum sigma for a broadfit
            medfilter_eli_list = sn_peakdet(x,medfilt(v,5),medfilt(err,5),values_units=values_units,
                                            enforce_good=enforce_good,min_sigma=GOOD_BROADLINE_SIGMA,absorber=absorber)

            for m in medfilter_eli_list:
                m.broadfit = True

            if medfilter_eli_list and len(medfilter_eli_list) > 0:
                eli_list += medfilter_eli_list
        except:
            log.debug("Exception in peakdet with median filter",exc_info=True)

    if x is None:
        x = np.arange(len(v))

    pix_size = abs(x[1] - x[0])  # aa per pix
    if pix_size == 0:
        log.error("Unexpected pixel_size in spectrum::peakdet(). Wavelength step is zero.")
        return []
    # want +/- 20 angstroms
    wave_side = int(round(20.0 / pix_size))  # pixels

    dw = int(dw / pix_size) #want round down (i.e. 2.9 -> 2) so this is fine

    v = np.asarray(v)
    num_pix = len(v)

    if num_pix != len(x):
        log.warning('peakdet: Input vectors v and x must have same length')
        return []

    if not np.isscalar(dh):
        log.warning('peakdet: Input argument delta must be a scalar')
        return []

    if dh <= 0:
        log.warning('peakdet: Input argument delta must be positive')
        return []


    v_0 = copy.copy(v)# v[:] #slicing copies if list, but not if array
    x_0 = copy.copy(x)#x[:]
    values_units_0 = values_units

    #if values_are_flux:
    #    v = v * 10.0

    #don't need to normalize errors for peakdet ... will be handled in signal_score
    v,values_units = norm_values(v,values_units)

    #smooth v and rescale x,
    #the peak positions are unchanged but some of the jitter is smoothed out
    #v = v[:-2] + v[1:-1] + v[2:]
    v = v[:-4] + v[1:-3] + v[2:-2] + v[3:-1] + v[4:]
    #v = v[:-6] + v[1:-5] + v[2:-4] + v[3:-3] + v[4:-2] + v[5:-1] + v[6:]
    v /= 5.0
    x = x[2:-2]

    minv, maxv = np.Inf, -np.Inf
    minpos, maxpos = np.NaN, np.NaN

    lookformax = True

    for i in np.arange(len(v)):
        thisv = v[i]
        if thisv > maxv:
            maxv = thisv
            maxpos = x[i]
            maxidx = i
        if thisv < minv:
            minv = thisv
            minpos = x[i]
            minidx = i
        if lookformax:
            if (thisv >= h) and (thisv < maxv - delta):
                #i-1 since we are now on the right side of the peak and want the index associated with max
                maxtab.append((maxidx,maxpos, maxv))
                minv = thisv
                minpos = x[i]
                lookformax = False
        else:
            if thisv > minv + delta:
                mintab.append((minidx,minpos, minv))
                maxv = thisv
                maxpos = x[i]
                lookformax = True


    if len(maxtab) < 1:
        log.warning("No peaks found with given conditions: mininum:  fwhm = %f, height = %f, delta height = %f" \
                %(dw,h,dh))
        return eli_list

    #make an array, slice out the 3rd column
    #gm = gmean(np.array(maxtab)[:,2])
    peaks = np.array(maxtab)[:, 2]
    gm = np.mean(peaks)
    std = np.std(peaks)


    ################
    #DEBUG
    ################

    if False:
        so = Spectrum()
        eli = []
        for p in maxtab:
            e = EmissionLineInfo()
            e.raw_x0 = p[1] #xposition p[0] is the index
            e.raw_h = v_0[p[0]+2] #v_0[getnearpos(x_0,p[1])]
            eli.append(e)

        so.build_full_width_spectrum(wavelengths=x_0, counts=v_0, errors=None, central_wavelength=0,
                                      show_skylines=False, show_peaks=True, name="peaks",
                                      dw=MIN_FWHM, h=MIN_HEIGHT, dh=MIN_DELTA_HEIGHT, zero=0.0,peaks=eli,annotate=False)



    #now, throw out anything waaaaay above the mean (toss out the outliers and recompute mean)
    if False:
        sub = peaks[np.where(abs(peaks - gm) < (3.0*std))[0]]
        if len(sub) < 3:
            sub = peaks
        gm = np.mean(sub)

    for pi,px,pv in maxtab:
        #check fwhm (assume 0 is the continuum level)

        #minium height above the mean of the peaks (w/o outliers)
        if False:
            if (pv < 1.333 * gm):
                continue

        hm = float((pv - zero) / 2.0)
        pix_width = 0

        #for centroid (though only down to fwhm)
        sum_pos_val = x[pi] * v[pi]
        sum_pos = x[pi]
        sum_val = v[pi]

        #check left
        pix_idx = pi -1

        try:
            while (pix_idx >=0) and (v[pix_idx] >= hm):
                sum_pos += x[pix_idx]
                sum_pos_val += x[pix_idx] * v[pix_idx]
                sum_val += v[pix_idx]
                pix_width += 1
                pix_idx -= 1

        except:
            pass

        #check right
        pix_idx = pi + 1

        try:
            while (pix_idx < num_pix) and (v[pix_idx] >= hm):
                sum_pos += x[pix_idx]
                sum_pos_val += x[pix_idx] * v[pix_idx]
                sum_val += v[pix_idx]
                pix_width += 1
                pix_idx += 1
        except:
            pass

        #check local region around centroid
        centroid_pos = sum_pos_val / sum_val #centroid is an index

        #what is the average value in the vacinity of the peak (exlcuding the area under the peak)
        #should be 20 AA not 20 pix
        side_pix = max(wave_side,pix_width)
        left = max(0,(pi - pix_width)-side_pix)
        sub_left = v[left:(pi - pix_width)]
   #     gm_left = np.mean(v[left:(pi - pix_width)])

        right = min(num_pix,pi+pix_width+side_pix+1)
        sub_right = v[(pi + pix_width):right]
   #     gm_right = np.mean(v[(pi + pix_width):right])

        #minimum height above the local gm_average
        #note: can be a problem for adjacent peaks?
        # if False:
        #     if pv < (2.0 * np.mean(np.concatenate((sub_left,sub_right)))):
        #         continue

        #check vs minimum width
        if not (pix_width < dw):
            #see if too close to prior peak (these are in increasing wavelength order)
            already_found = np.array([e.fit_x0 for e in eli_list])

            if np.any(abs(already_found-px) < 2.0):
                pass #skip and move on
            else:
                eli = signal_score(x_0, v_0, err, px,values_units=values_units_0,min_sigma=min_sigma,absorber=absorber)

                #if (eli is not None) and (eli.score > 0) and (eli.snr > 7.0) and (eli.fit_sigma > 1.6) and (eli.eqw_obs > 5.0):
                if (eli is not None) and ((not enforce_good) or eli.is_good()):
                    eli_list.append(eli)
                    log.debug("*** old peakdet added new ELI")
                    if len(emistab) > 0:
                        if (px - emistab[-1][1]) > 6.0:
                            emistab.append((pi, px, pv,pix_width,centroid_pos,eli.eqw_obs,eli.snr))
                        else: #too close ... keep the higher peak
                            if pv > emistab[-1][2]:
                                emistab.pop()
                                emistab.append((pi, px, pv, pix_width, centroid_pos,eli.eqw_obs,eli.snr))
                    else:
                        emistab.append((pi, px, pv, pix_width, centroid_pos,eli.eqw_obs,eli.snr))


    #return np.array(maxtab), np.array(mintab)
    #print("DEBUG ... peak count = %d" %(len(emistab)))
    #for i in range(len(emistab)):
    #    print(emistab[i][1],emistab[i][2], emistab[i][5])
    #return emistab

    ################
    #DEBUG
    ################
    # if False:
    #     so = Spectrum()
    #     eli = []
    #     for p in eli_list:
    #         e = EmissionLineInfo()
    #         e.raw_x0 = p.raw_x0
    #         e.raw_h = p.raw_h / 10.0
    #         eli.append(e)
    #     so.build_full_width_spectrum(wavelengths=x_0, counts=v_0, errors=None, central_wavelength=0,
    #                                  show_skylines=False, show_peaks=True, name="peaks_trimmed",
    #                                  dw=MIN_FWHM, h=MIN_HEIGHT, dh=MIN_DELTA_HEIGHT, zero=0.0, peaks=eli,
    #                                  annotate=False)

    return combine_lines(eli_list)



def combine_lines(eli_list,sep=4.0):
    """

    :param eli_list:
    :param sep: max peak separation in AA (for peakdet values, true duplicates are very close, sub AA close)
    :return:
    """

    def is_dup(wave1,wave2,sep):
        if abs(wave1-wave2) < sep:
            return True
        else:
            return False

    keep_list = []
    for e in eli_list:
        add = True
        for i in range(len(keep_list)):
            if abs(e.fit_x0 - keep_list[i].fit_x0) < sep:
                add = False
                #keep the larger score
                if e.line_score > keep_list[i].fit_x0:
                    keep_list[i] = copy.deepcopy(e)
        if add:
            keep_list.append(copy.deepcopy(e))

    return keep_list



class EmissionLine():
    def __init__(self,name,w_rest,plot_color,solution=True,display=True,z=0,score=0.0,rank=0,
                 min_fwhm=999.0,min_obs_wave=9999.0,max_obs_wave=9999.0,broad=False):
        self.name = name
        self.w_rest = w_rest
        self.w_obs = w_rest * (1.0 + z)
        self.z = z
        self.color = plot_color
        self.solution = solution #True = can consider this as the target lines (as a single line solution
        self.display = display #True = plot label on full 1D plot
        self.rank = rank #indicator of the rank in solutions (from 1 to x, with 1 being high, like LyA)
                       #roughly corresponds to expected line strength (1= high, 4= low)
                       #the base idea is that if the emission line center is a "low" rank, but there are high ranks
                       #in the wavelength range that are not found, the line may not be real
        self.min_fwhm = min_fwhm #FWHM in AA, if solution is FALSE but measured FWHM is above this value, can still be considered
                          #as a single line solution (ie. CIII, CIV, MgII ... really broad in AGN and could be alone)
        self.min_obs_wave = min_obs_wave    #if solution is FALSE, but observed wave between these values, can still be a solution
        self.max_obs_wave = max_obs_wave



        #can be filled in later if a specific instance is created and a model fit to it
        self.score = score
        self.snr = None
        self.sbr = None
        self.flux = None
        self.flux_err = 0.0
        self.eqw_obs = None
        self.eqw_rest = None
        self.sigma = None #gaussian fit sigma
        self.sigma_err = 0.0

        #a bit redundant with EmissionLineInfo
        self.line_score = 0.0
        self.prob_noise = 1.0
        self.fit_dx0 = None #from EmissionLineInfo, but we want this for a later comparison of all other lines in the solution

        self.absorber = False #true if an abosrption line
        if G.ALLOW_BROADLINE_FIT:
            self.broad = broad #this can be a potentially very broad line (i.e. may be with an AGN)
        else:
            self.broad = False

    def redshift(self,z):
        self.z = z
        self.w_obs = self.w_rest * (1.0 + z)
        return self.w_obs




class Classifier_Solution:
    def __init__(self,w=0.0):
        self.score = 0.0
        self.frac_score = 0.0
        self.scale_score = -1.0 #right now, not computed until the end, in hetdex.py multiline_solution_score()
        self.z = 0.0
        self.central_rest = w
        self.name = ""
        self.color = None
        self.emission_line = None

        self.prob_noise = 1.0
        self.lines = [] #list of EmissionLine
        self.rejected_lines = [] #list of EmissionLines that were scored as okay, but rejected for other reasons

        #self.unmatched_lines = [] #not bothering to track the specific lines after computing score & count
        self.unmatched_lines_score = 0
        self.unmatched_lines_count = 0

    @property
    def prob_real(self):
        #return min(1-self.prob_noise,0.999) * min(1.0, max(0.67,self.score/G.MULTILINE_MIN_SOLUTION_SCORE))
        return min(1 - self.prob_noise, 0.999) * min(1.0, float(len(self.lines))/(G.MIN_ADDL_EMIS_LINES_FOR_CLASSIFY))# + 1.0))


    def calc_score(self):
        self.score = 0.0
        self.prob_noise = 1.0

        for l in self.lines:
            self.score += l.line_score  # score for this solution
            self.prob_noise *= l.prob_noise

        n = len(np.where([l.absorber == False for l in self.lines])[0])

        if n >= G.MIN_ADDL_EMIS_LINES_FOR_CLASSIFY:
            bonus = 0.5 * (n ** 2 - n) * G.ADDL_LINE_SCORE_BONUS  # could be negative
            self.score += bonus

        return self.score


class PanaceaSpectrum:
    """
    identification, etc from Panacea
    the operable unit
    now from HDF5
    """

    def __init__(self):
        #address
        self.amp = None
        self.ifuid = None
        self.ifuslot = None
        self.specid = None
        self.fibnum = None

        #when
        self.expnum = None
        self.obsind = None


        #coords
        self.ra = None
        self.dec = None
        self.fpx = None
        self.fpy = None
        self.ifux = None
        self.ifuy = None

        #data
        self.spectrum = None
        self.error1Dfib = None
        self.wavelength = None
        self.sky_subtracted = None

        #calibration
        self.fiber_to_fiber = None
        self.trace = None
        self.twi_spectrum = None

#end class PanaceaSpectrum


class Spectrum:
    """
    helper functions for spectra
    actual spectra data is kept in fiber.py
    """

    def __init__(self):
        #reminder ... colors don't really matter (are not used) if solution is not True)
        #try to keep the name in 4 characters
        w = 4

        self.emission_lines = [
            #extras for HW
            # EmissionLine("H$\\alpha$".ljust(w), 6562.8, "blue"),
            # EmissionLine("NaII".ljust(w),6549.0,"lightcoral",solution=True, display=True),
            # EmissionLine("NaII".ljust(w),6583.0,"lightcoral",solution=True, display=True),
            # EmissionLine("Pa$\\beta$".ljust(w),12818.0,"lightcoral",solution=True, display=True),
            # EmissionLine("Pa$\\alpha$".ljust(w),18751.0,"lightcoral",solution=True, display=True),

            #solution == can be a single line solution .... if False, only counts as a possible solution if
            # there is at least one corroborating line
            # see (among others) https://ned.ipac.caltech.edu/level5/Netzer/Netzer2_1.html

            EmissionLine("Ly$\\alpha$".ljust(w), G.LyA_rest, 'red',rank=1,broad=True),

            EmissionLine("OII".ljust(w), G.OII_rest, 'green',rank=2),
            EmissionLine("OIII".ljust(w), 4959, "lime",rank=2),#4960.295 (vacuum) 4958.911 (air)
            EmissionLine("OIII".ljust(w), 5007, "lime",rank=1), #5008.240 (vacuum) 5006.843 (air)
            #EmissionLine("OIV".ljust(w), 1400, "lime", solution=False, display=True, rank=4),  # or 1393-1403 also OIV]
            # (alone after LyA falls off red end, no max wave)
            EmissionLine("OVI".ljust(w), 1035, "lime",solution=False,display=True,rank=3,
                         min_fwhm=12.0,min_obs_wave=4861.0-20.,max_obs_wave=5540.0+20.),

            # big in AGN (never alone in our range)
            EmissionLine("CIV".ljust(w), 1549, "blueviolet",solution=True,display=True,rank=3,broad=True),
            # big in AGN (alone before CIV enters from blue and after MgII exits to red) [HeII too unreliable to set max_obs_wave]
            EmissionLine("CIII".ljust(w), 1909, "purple",solution=False,display=True,rank=3,broad=True,
                         min_fwhm=12.0,min_obs_wave=3751.0-20.0,max_obs_wave=4313.0+20.0),
            #big in AGN (too weak to be alone)
            EmissionLine("CII".ljust(w),  2326, "purple",solution=False,display=True,rank=4,broad=True),  # in AGN

            #big in AGN (alone before CIII enters from the blue )  this MgII is a doublet, 2795, 2802 ... can sometimes
            #  see the doublet in the HETDEX spectrum
            # What about when combined with OII 3277 (MgII maybe broad, but OII is not?)
            EmissionLine("MgII".ljust(w), 2799, "magenta",solution=True,display=True,rank=3,broad=True,
                         min_fwhm=12.0,min_obs_wave=3500.0-20.0, max_obs_wave=5131.0+20.0),

            #thse H_x lines are never alone (OIII or OII are always present)
            EmissionLine("H$\\beta$".ljust(w), 4861, "blue",solution=True,rank=3), #4862.68 (vacuum) 4861.363 (air)
            EmissionLine("H$\\gamma$".ljust(w), 4340, "royalblue",solution=True,rank=3),

            EmissionLine("H$\\delta$".ljust(w), 4101, "royalblue", solution=False,display=False,rank=4),
            EmissionLine("H$\\epsilon$/CaII".ljust(w), 3970, "royalblue", solution=False,display=False,rank=4), #very close to CaII(3970)
            EmissionLine("H$\\zeta$".ljust(w), 3889, "royalblue", solution=False,display=False,rank=5),
            EmissionLine("H$\\eta$".ljust(w), 3835, "royalblue", solution=False,display=False,rank=5),

            # big in AGN, but never alone in our range
            EmissionLine("NV".ljust(w), 1241, "teal", solution=False,display=True,rank=3),

            EmissionLine("SiII".ljust(w), 1260, "gray", solution=False,display=True,rank=4),
            EmissionLine("SiIV".ljust(w), 1400, "gray", solution=False, display=True, rank=4), #or 1393-1403 also OIV]

            #big in AGN, but never alone in our range
            EmissionLine("HeII".ljust(w), 1640, "orange", solution=False,display=True,rank=3),

            EmissionLine("NeIII".ljust(w), 3869, "deeppink", solution=False,display=False,rank=4),
            EmissionLine("NeIII".ljust(w), 3967, "deeppink", solution=False,display=False,rank=4),  #very close to CaII(3970)
            EmissionLine("NeV".ljust(w), 3347, "deeppink", solution=False,display=False,rank=4),
            EmissionLine("NeVI".ljust(w), 3427, "deeppink", solution=False, display=False,rank=4),

            EmissionLine("NaI".ljust(w),4980,"lightcoral",solution=False, display=False,rank=4),  #4978.5 + 4982.8
            EmissionLine("NaI".ljust(w),5153,"lightcoral",solution=False, display=False,rank=4),  #5148.8 + 5153.4

            #stars
            EmissionLine("CaII".ljust(w), 3935, "skyblue", solution=False, display=False,rank=4)

            #merged CaII(3970) with H\$epsilon$(3970)
            #EmissionLine("CaII".ljust(w), 3970, "skyblue", solution=False, display=False)  #very close to NeIII(3967)
           ]

        self.wavelengths = []
        self.values = [] #could be fluxes or counts or something else ... right now needs to be counts
        self.errors = []
        self.values_units = 0

        self.noise_estimate = None
        self.noise_estimate_wave = None

        # very basic info, fit line to entire spectrum to see if there is a general slope
        #useful in identifying stars (kind of like a color U-V (ish))
        self.spectrum_linear_coeff = None #index = power so [0] = onstant, [1] = 1st .... e.g. mx+b where m=[1], b=[0]
        self.spectrum_slope = None
        self.spectrum_slope_err = None

        self.central = None
        self.estflux = None
        self.estflux_unc = None
        self.estcont = None
        self.estcont_unc = None
        self.eqw_obs = None
        self.eqw_obs_unc = None
        self.fwhm = None
        self.fwhm_unc = None


        self.central_eli = None

        self.solutions = []
        self.unmatched_solution_count = 0
        self.unmatched_solution_score = 0
        self.all_found_lines = None #EmissionLineInfo objs (want None here ... if no lines, then peakdet returns [])
        self.all_found_absorbs = None
        self.classification_label = "" #string of possible classification applied (i.e. "AGN", "low-z","star", "meteor", etc)
        self.meteor_strength = 0 #qualitative strength of meteor classification

        self.addl_fluxes = []
        self.addl_wavelengths = []
        self.addl_fluxerrs = []
        self.p_lae = None
        self.p_oii = None
        self.p_lae_oii_ratio = None
        self.p_lae_oii_ratio_range = None #[ratio, max ratio, min ratio]

        self.identifier = None #optional string to help identify in the log
        self.plot_dir = None

        #from HDF5

    def add_classification_label(self,label="",prepend=False,replace=False):
        try:
            if replace or self.classification_label is None:
                self.classification_label = label
            else:
                toks = self.classification_label.split(",")
                if label not in toks:
                    if prepend:
                        self.classification_label = label + "," + self.classification_label
                    else:
                        self.classification_label += label + ","
        except:
            log.warning("Unexpected exception",exc_info=True)

    def scale_consistency_score_to_solution_score_factor(self,consistency_score):
        """
        take the score from the various solution_consistent_with_xxx and
        scale it to appropriate use for the solution scoring

        :param consistency_score:
        :return:
        """
        #todo: figure out what this should be;
        #todo: set a true upper limit (2-3x or so)

        upper_limit = 3.0
        if consistency_score < 0:
            #already negative so, a -1 --> 1/2, -2 --> 1/3 and so on
            consistency_score = -1./(consistency_score-1.)
        else:
            consistency_score += 1.0

        return min(max(consistency_score, 0.0), upper_limit)

    # # actually impemented in hetdex.py DetObj.check_for_meteor() as it is more convenient to do so there
    # # were the individual exposures and fibers are readily available
    # def solution_consistent_with_meteor(self, solution):
    #     """
    #
    #     if there is (positive) consistency (lines match and ratios match) you get a boost
    #     if there is no consistency (that is, the lines don't match up) you get no change
    #     if there is anti-consistency (the lines match up but are inconsistent by ratio, you can get a score decrease)
    #
    #
    #     :param solution:
    #     :return: +1 point for each pair of lines that are consistent (or -1 for ones that are anti-consistent)
    #     """
    #
    #     # check the lines, are they consistent with low z OII galaxy?
    #     try:
    #         pass
    #     except:
    #         log.info("Exception in Spectrum::solution_consistent_with_meteor", exc_info=True)
    #         return 0
    #
    #     return 0

    #todo:
    def solution_consistent_with_star(self,solution):
        """

        if there is (positive) consistency (lines match and ratios match) you get a boost
        if there is no consistency (that is, the lines don't match up) you get no change
        if there is anti-consistency (the lines match up but are inconsistent by ratio, you can get a score decrease)


        :param solution:
        :return: +1 point for each pair of lines that are consistent (or -1 for ones that are anti-consistent)
        """

        # check the lines, are they consistent with low z OII galaxy?
        try:
            pass
        except:
            log.info("Exception in Spectrum::solution_consistent_with_star", exc_info=True)
            return 0

        return 0



    def solution_consistent_with_low_z(self,solution):
        """

        if there is (positive) consistency (lines match and ratios match) you get a boost
        if there is no consistency (that is, the lines don't match up) you get no change
        if there is anti-consistency (the lines match up but are inconsistent by ratio, you can get a score decrease)


        :param solution:
        :return: +1 point for each pair of lines that are consistent (or -1 for ones that are anti-consistent)
        """

        # check the lines, are they consistent with low z OII galaxy?
        try:
            #compared to OII (3272) EW: so line ew / OII EW; a value of 0 means no info
            #               OII      NeV  NeIV H_eta   -NeIII-   H_zeta  CaII  H_eps  H_del  H_gam H_beta   -NaI-     -OIII-
            #rest_waves = [G.OII_rest,3347,3427,3835,  3869,3967, 3889,   3935, 3970,  4101,  4340, 4861,  4980,5153, 4959,5007]
            #                       OII       H_eta  H_zeta H_eps H_del  H_gam H_beta   -OIII-
            rest_waves = np.array([G.OII_rest, 3835,  3889,  3970, 4101,  4340, 4861,  4959, 5007])
            #                         0         1      2      3     4     5     6      7     8
            obs_waves  = rest_waves * (1. + solution.z)

            #OIII 4960 / OIII 5007 ~ 1/3
            #using as rough reference https://watermark.silverchair.com/stt151.pdf (MNRAS 430, 35103536 (2013))

            # note that H_beta and OIII can be more intense than OII
            # pretty loose since the Hx lines can really be large compared to OII in very metal poor objects
            #                                      CaII
            #             OII   H_eta      H_zeta  H_eps  H_del H_gam  H_beta  -OIII-
            min_ratios = [1,     0.01,      0.05,  0.05,  0.1, 0.15,   0.4,    0.1, 0.3]
            max_ratios = [1,     0.06,      0.20,  1.20,  0.5, 1.50,   3.3,    6.5, 20.0]

            #required match matrix ... if line (x) is found and line(y) is in range, it MUST be found too
            #this is in order of the lines in rest_waves
            match_matrix =[[1,0,0,0,0,0,0,0,0],  #0 [OII]
                           [0,1,1,1,1,1,1,0,0],  #1 H_eta
                           [0,0,1,1,1,1,1,0,0],  #2 H_zeta
                           [0,0,0,1,1,1,1,0,0],  #3 H_epsilon
                           [0,0,0,0,1,1,1,0,0],  #4 H_delta
                           [0,0,0,0,0,1,1,0,0],  #5 H_gamma
                           [0,0,0,0,0,0,1,0,0],  #6 H_beta
                           [0,0,0,0,0,0,0,1,1],  #7 OIII 4959
                           [0,0,0,0,0,0,0,0,1]]  #8 OIII 5007
            match_matrix = np.array(match_matrix)

            #row/column (is mininum, where lines are smallest compared to LyA)
            # the inverse is still the minimum just the inverted ratio)
            min_ratio_matrix = \
            [ [1.00, None, None, None, None, None, None, None, None],  #OII
              [None, 1.00, None, None, None, None, None, None, None],  #H_eta
              [None, None, 1.00, None, None, None, None, None, None],  #H_zeta
              [None, None, None, 1.00, None, None, None, None, None],  #H_eps
              [None, None, None, None, 1.00, None, None, None, None],  #H_del
              [None, None, None, None, None, 1.00, None, None, None],  #H_gamma
              [None, None, None, None, None, None, 1.00, None, None],  #H_beta
              [None, None, None, None, None, None, None, 1.00, 0.33],  #OIII 4959
              [None, None, None, None, None, None, None, 3.00, 1.00]]  #OIII 5007
             # OII   H_eta H_zet H_eps H_del H_gam H_bet  OIII OIII

            max_ratio_matrix = \
            [ [1.00, None, None, None, None, None, None, None, None],  #OII
              [None, 1.00, None, None, None, None, None, None, None],  #H_eta
              [None, None, 1.00, None, None, None, None, None, None],  #H_zeta
              [None, None, None, 1.00, None, None, None, None, None],  #H_eps
              [None, None, None, None, 1.00, None, None, None, None],  #H_del
              [None, None, None, None, None, 1.00, None, None, None],  #H_gamma
              [None, None, None, None, None, None, 1.00, None, None],  #H_beta
              [None, None, None, None, None, None, None, 1.00, 0.33],  #OIII 4959
              [None, None, None, None, None, None, None, 3.00, 1.00]]  #OIII 5007
             # OII   H_eta H_zet H_eps H_del H_gam H_bet  OIII OIII

            sel = np.where(np.array([l.absorber for l in solution.lines]) == False)[0]
            sol_lines = np.array(solution.lines)[sel]
            line_waves = [solution.central_rest] + [l.w_rest for l in sol_lines]
            #line_ew = [self.eqw_obs / (1 + solution.z)] + [l.eqw_rest for l in sol_lines]
            #line_flux is maybe more reliable ... the continuum estimates for line_ew can go wrong and give horrible results
            line_flux = [self.estflux] + [l.flux for l in sol_lines]
            line_flux_err = [self.estflux_unc] + [l.flux_err for l in sol_lines]
            line_fwhm = [self.fwhm] + [l.sigma * 2.355 for l in sol_lines]
            line_fwhm_err = [self.fwhm_unc] + [l.sigma_err * 2.355 for l in sol_lines]

            overlap, rest_idx, line_idx = np.intersect1d(rest_waves, line_waves, return_indices=True)


            central_fwhm =  self.fwhm
            central_fwhm_err = self.fwhm_unc
            #todo: get samples and see if there is a correlation with slope
            #slope = self.spectrum_slope
            #slope_err = self.spectrum_slope_err

            if len(overlap) < 1:
                #todo: any fwhm that would imply low-z? more narrow?
                return 0

            #check the match_matrix
            missing = []
            in_range = np.where((obs_waves > 3500.) & (obs_waves < 5500.))[0]
            for i in range(len(overlap)):
                if np.sum(match_matrix[rest_idx[i]]) > 1:
                    #at least one other line must be found (IF the obs_wave is in the HETDEX range)
                    sel = np.intersect1d(in_range,np.where(match_matrix[rest_idx[i]])[0])
                    missing = np.union1d(missing,np.setdiff1d(sel,rest_idx)).astype(int)

            score = -1 * len(missing)

            if score < 0:
                log.info(f"LzG consistency failure. Initial Score = {score}. "
                         f"Missing expected lines {[z for z in zip(rest_waves[missing],obs_waves[missing])]}. ")
            # compare all pairs of lines

            if len(overlap) < 2:  # done (0 or 1) if only 1 line, can't go any farther with comparison
                #todo: any fwhm that would imply low-z? more narrow?
                return score


            for i in range(len(overlap)):
                for j in range(i+1,len(overlap)):
                    if (line_flux[line_idx[i]] != 0):
                        if (min_ratios[rest_idx[i]] != 0) and (min_ratios[rest_idx[j]] != 0) and \
                           (max_ratios[rest_idx[i]] != 0) and (max_ratios[rest_idx[j]] != 0):

                            ratio = line_flux[line_idx[j]] / line_flux[line_idx[i]]
                            ratio_err = abs(ratio) * np.sqrt((line_flux_err[line_idx[j]] /line_flux[line_idx[j]]) ** 2 +
                                                             (line_flux_err[line_idx[i]] / line_flux[line_idx[i]]) ** 2)
                            # try the matrices first (if they are zero, they are not populated yet
                            # so fall back to the list)
                            min_ratio = min_ratio_matrix[rest_idx[j]][rest_idx[i]]
                            max_ratio = max_ratio_matrix[rest_idx[j]][rest_idx[i]]

                            if (min_ratio is None) or (max_ratio is None):
                                min_ratio = min_ratios[rest_idx[j]] / min_ratios[rest_idx[i]]
                                max_ratio = max_ratios[rest_idx[j]] / max_ratios[rest_idx[i]]

                            if min_ratio > max_ratio: #order is backward, so flip
                                min_ratio, max_ratio = max_ratio, min_ratio

                            if min_ratio <= (ratio+ratio_err) and (ratio-ratio_err) <= max_ratio:
                                #now check fwhm is compatible
                                fwhm_i = line_fwhm[line_idx[i]]
                                fwhm_j = line_fwhm[line_idx[j]]

                                #none of the low-z lines can be super broad
                                if (fwhm_i > (LIMIT_BROAD_SIGMA * 2.355)) or (fwhm_j > (LIMIT_BROAD_SIGMA * 2.355)):
                                    score -=1
                                    log.debug(f"Ratio mis-match (-1) for solution = {solution.central_rest}: "
                                              f"FWHM {fwhm_j:0.2f}, {fwhm_i:0.2f} exceed max allowed {2.355 *LIMIT_BROAD_SIGMA} ")
                                    continue

                                avg_fwhm = 0.5* (fwhm_i + fwhm_j)
                                diff_fwhm = abs(fwhm_i - fwhm_j)
                                if avg_fwhm > 0 and diff_fwhm/avg_fwhm < 0.5:
                                    score += 1
                                    log.debug(f"Ratio match (+1) for solution = {solution.central_rest}: "
                                              f"rest {overlap[j]} to {overlap[i]}: "
                                              f"{min_ratio:0.2f} < {ratio:0.2f} +/- {ratio_err:0.2f} < {max_ratio:0.2f} "
                                              f"FWHM {fwhm_j}, {fwhm_i}")

                                    if rest_waves[rest_idx[j]] == 3727 and rest_waves[rest_idx[i]] == 5007:
                                        if 1/ratio > 5.0:
                                            self.add_classification_label("o32")
                                    elif rest_waves[rest_idx[j]] == 5007 and rest_waves[rest_idx[i]] == 3727:
                                        if ratio > 5.0:
                                            self.add_classification_label("o32")

                                else:
                                    log.debug(f"FWHM no match (0) for solution = {solution.central_rest}: "
                                              f"rest {overlap[j]} to {overlap[i]}: FWHM {fwhm_j}, {fwhm_i}, "
                                              f"ratios {min_ratio:0.2f} < {ratio:0.2f} +/- {ratio_err:0.2f} < {max_ratio:0.2f}")
                            else:
                                if ratio < min_ratio:
                                    frac = (min_ratio - ratio) / min_ratio
                                else:
                                    frac = (ratio - max_ratio) / max_ratio

                                if 0.5 < frac < 250.0: #if more than 250 more likely there is something wrong
                                    score -= 1
                                    log.debug(
                                        f"Ratio mismatch (-1) for solution = {solution.central_rest}: "
                                        f"rest {overlap[j]} to {overlap[i]}: "
                                        f"{min_ratio:0.2f} !< {ratio:0.2f} +/- {ratio_err:0.2f} !< {max_ratio:0.2f} ")
                                # else:
                                #     log.debug(
                                #         f"Ratio no match (0) for solution = {solution.central_rest}: "
                                #         f"rest {overlap[j]} to {overlap[i]}:  {min_ratio} !< {ratio} !< {max_ratio}")

            # todo: sther stuff??
            # if score > 0:
            #     self.add_classification_label("LzG") #Low-z Galaxy
            return score

        except:
            log.info("Exception in Spectrum::solution_consistent_with_low_z", exc_info=True)
            return 0

        return 0

    def solution_consistent_with_agn(self,solution):
        """
        REALLY AGN or higher z (should not actually include MgII)

        if there is (positive) consistency (lines match and ratios match) you get a boost
        if there is no consistency (that is, the lines don't match up) you get no change
        if there is anti-consistency (the lines match up but are inconsistent by ratio, you can get a score decrease)


        :param solution:
        :return: +1 point for each pair of lines that are consistent (or -1 for ones that are anti-consistent)
        """

        #
        # note: MgII alone (as broad line) not necessarily AGN ... can be from outflows?
        #

        #check the lines, are they consistent with AGN?
        try: #todo: for MgII, OII can also be present
            rest_waves = np.array([G.LyA_rest,1549.,1909.,2326.,2799.,1241.,1260.,1400.,1640.,1035., G.OII_rest])
            #aka                     LyA,      CIV, CIII, CII,   MgII,  NV,  SiII, SiIV, HeII, OVI,  OII
            obs_waves = rest_waves * (1. + solution.z)

            # compared to LyA EW: so line ew/ LyA EW; a value of 0 means no info
            #todo: need info/citation on this
            #todo: might have to make a matrix if can't reliably compare to LyA
            #todo:   e.g. if can only say like NV < MgII or CIV > CIII, etc

            # using as a very rough guide: https://ned.ipac.caltech.edu/level5/Netzer/Netzer2_1.html
            # and manual HETDEX spectra
            #            #LyA, CIV,  CIII, CII,  MgII,  NV,     SiII, SiIV,  HeII,  OVI   OII
            min_ratios = [1.0, 0.07, 0.02, 0.01,  0.05, 0.05,  0.00, 0.03,   0.01,  0.03, 0.01]
            max_ratios = [1.0, 0.70, 0.30, 0.10,  0.40, 0.40,  0.00, 0.20,   0.20,  0.40, 9.99]
            #            *** apparently NV can be huge .. bigger than CIV even see 2101164104
            #            *** OII entries just to pass logic below (only appears on our range for some MgII)


            #required match matrix ... if line (x) is found and line(y) is in range, it MUST be found too
            #this is in order of the lines in rest_waves
            #in ALL cases, LyA better be found IF it is in range (so making it a 2 ... need 2 other matched lines to overcome missing LyA)
            match_matrix =[[1,0,0,0,0,0,0,0,0,0,0],  #0 LyA
                           [1,1,0,0,0,0,0,0,0,0,0],  #1 CIV
                           [1,0,1,0,0,0,0,0,0,0,0],  #2 CIII
                           [1,0,0,1,0,0,0,0,0,0,0],  #3 CII
                           [1,0,0,0,1,0,0,0,0,0,0],  #4 MgII
                           [1,0,0,0,0,1,0,0,0,0,0],  #5 NV
                           [1,0,0,0,0,0,1,0,0,0,0],  #6 SiII
                           [1,0,0,0,0,0,0,1,0,0,0],  #7 SiIV
                           [1,0,0,0,0,0,0,0,1,0,0],  #8 HeII
                           [1,0,0,0,0,0,0,0,0,1,0],  #9 OVI
                           [0,0,0,0,1,0,0,0,0,0,1] ] #10 OII (just with MgII)
                         #  0 1 2 3 4 5 6 7 8 9 10

            match_matrix = np.array(match_matrix)

            match_matrix_weights = np.array([3,1,1,0.5,1,1,0.5,0.5,1,1])

            #todo: 2 matrices (min and max ratios) so can put each line vs other line
            # like the match_matrix in the low-z galaxy check (but with floats) as row/column
            # INCOMPLETE ... not in USE YET

            #row/column (is mininum, where lines are smallest compared to LyA)
            # the inverse is still the minimum just the inverted ratio)
            min_ratio_matrix = \
            [ [1.00, None, None, None, None, None, None, None, None, None, None],  #LyA
              [None, 1.00, None, None, None, None, 4.00, None, 6.66, None, None],  #CIV
              [None, None, 1.00, None, None, None, None, None, None, None, None],  #CIII
              [None, None, None, 1.00, None, None, None, None, None, None, None],  #CII
              [None, None, None, None, 1.00, None, None, None, None, None, 20.0],  #MgII
              [None, None, None, None, None, 1.00, None, None, None, None, None],  #NV
              [None, 0.25, None, None, None, None, 1.00, None, None, None, None],  #SiII
              [None, None, None, None, None, None, None, 1.00, None, None, None],  #SiIV
              [None, 0.15, None, None, None, None, None, None, 1.00, None, None],  #HeII
              [None, None, None, None, None, None, None, None, None, 1.00, None],  #OVI
              [None, None, None, None, 0.05, None, None, None, None, None, 1.00 ]] #OII
             # LyA   CIV   CIII  CII   MgII   NV   SiII  SiVI  HeII   OVI  OII

            #row/column (is maximum ... where lines are the largest compared to LyA)
            max_ratio_matrix = \
            [ [1.00, None, None, None, None, None, None, None, None, None, None],  #LyA
              [None, 1.00, None, None, None, None, 0.10, None, 1.43, None, None],  #CIV
              [None, None, 1.00, None, None, None, None, None, None, None, None],  #CIII
              [None, None, None, 1.00, None, None, None, None, None, None, None],  #CII
              [None, None, None, None, 1.00, None, None, None, None, None, 2.00],  #MgII
              [None, None, None, None, None, 1.00, None, None, None, None, None],  #NV
              [None, 10.0, None, None, None, None, 1.00, None, None, None, None],  #SiII
              [None, None, None, None, None, None, None, 1.00, None, None, None],  #SiIV
              [None, 0.70, None, None, None, None, None, None, 1.00, None, None],  #HeII
              [None, None, None, None, None, None, None, None, None, 1.00, None],  #OVI
              [None, None, None, None, 0.50, None, None, None, None, None, 1.00] ] #OII
             # LyA    CIV  CIII   CII  MgII   NV   SiII  SiVI  HeII   OVI  OII

            sel = np.where(np.array([l.absorber for l in solution.lines])==False)[0]
            sol_lines = np.array(solution.lines)[sel]
            line_waves = [solution.central_rest] + [l.w_rest for l in sol_lines]
            #line_ew = [self.eqw_obs/(1+solution.z)] + [l.eqw_rest for l in sol_lines]
            # line_flux is maybe more reliable ... the continuum estimates for line_ew can go wrong and give horrible results
            line_flux = [self.estflux] + [l.flux for l in sol_lines]
            line_flux_err = [self.estflux_unc] + [l.flux_err for l in sol_lines]
            line_fwhm = [self.fwhm] + [l.sigma * 2.355 for l in sol_lines]
            line_fwhm_err = [self.fwhm_unc] + [l.sigma_err * 2.355 for l in sol_lines]
            line_broad = [solution.emission_line.broad] + [l.broad for l in sol_lines] #can they be broad

            overlap, rest_idx, line_idx = np.intersect1d(rest_waves,line_waves,return_indices=True)

            central_fwhm =  self.fwhm
            central_fwhm_err = self.fwhm_unc
            #todo: get samples and see if there is a correlation with slope
            #slope = self.spectrum_slope
            #slope_err = self.spectrum_slope_err

            score = 0

            # check the match_matrix
            missing = []
            in_range = np.where((obs_waves > 3500.) & (obs_waves < 5500.))[0]
            for i in range(len(overlap)):
                if np.sum(match_matrix[rest_idx[i]]) > 1:
                    # at least one other line must be found (IF the obs_wave is in the HETDEX range)
                    sel = np.intersect1d(in_range, np.where(match_matrix[rest_idx[i]])[0])
                    missing = np.union1d(missing, np.setdiff1d(sel, rest_idx)).astype(int)

            # score = -1 * len(missing)
            score = -1 * np.sum(match_matrix_weights[missing])

            if score < 0:
                log.info(f"AGN consistency failure. Initial Score = {score}. "
                         f"Missing expected lines {[z for z in zip(rest_waves[missing], obs_waves[missing])]}. ")

            if len(overlap) < 2: #done (0 or 1) if only 1 line, can't go any farther with comparision
                #for FWHM nudge to AGN, the one line MUST at least be on the list of AGN lines
                if (score > 0) and (len(overlap) > 0) and (central_fwhm - central_fwhm_err > 12.0) and \
                    ((self.spectrum_slope + self.spectrum_slope_err) < 0.02 )      and \
                    ((self.spectrum_slope - self.spectrum_slope_err) > -0.02 ):
                    #the slope is just a guess ... trying to separate out most stars
                    #self.add_classification_label("AGN")
                    try:
                        if (np.mean([line_fwhm[i] for i in line_idx]) > 12.0) and\
                                len(np.intersect1d(overlap,np.array([G.LyA_rest,1549.,1909.,2799.])) > 0):
                            #allowed singles: LyA, MgII, CIV, CIII (and really not CIV by itself in our range)
                            return 0.25  # still give a little boost to AGN classification?
                    except:
                        pass

                    return 0
                else:
                    return 0


            #compare all pairs of lines
            #
            # REMINDER: line_idx[i] indexes based on the overlap (should see only with line_xxx[] lists)
            #           rest_idx[i] indexes based on the fixed list of rest_wavelengths (maps overlap to rest)
            for i in range(len(overlap)):
                for j in range(i+1,len(overlap)):
                    if (line_flux[line_idx[i]] != 0):
                        if (min_ratios[rest_idx[i]] != 0) and (min_ratios[rest_idx[j]] != 0) and \
                           (max_ratios[rest_idx[i]] != 0) and (max_ratios[rest_idx[j]] != 0):

                            ratio = line_flux[line_idx[j]] / line_flux[line_idx[i]]
                            ratio_err = abs(ratio) * np.sqrt((line_flux_err[line_idx[j]] /line_flux[line_idx[j]]) ** 2 +
                                                             (line_flux_err[line_idx[i]] / line_flux[line_idx[i]]) ** 2)

                            #try the matrices first (if they are zero, they are not populated yet
                            # so fall back to the list)
                            min_ratio = min_ratio_matrix[rest_idx[j]][rest_idx[i]]
                            max_ratio = max_ratio_matrix[rest_idx[j]][rest_idx[i]]

                            if (min_ratio is None) or (max_ratio is None):
                                min_ratio = min_ratios[rest_idx[j]]/min_ratios[rest_idx[i]]
                                max_ratio = max_ratios[rest_idx[j]] / max_ratios[rest_idx[i]]

                            if min_ratio > max_ratio: #order is backward, so flip
                                min_ratio, max_ratio = max_ratio, min_ratio

                            if min_ratio <= (ratio+ratio_err) and (ratio-ratio_err) <= max_ratio:
                                #now check fwhm is compatible
                                #todo: consider using the fwhm error (is the difference consistent with zero? or
                                # maybe is the ratio consistent with less than 50% difference? or
                                # maybe if both are greater than 12 or 14AA, just call them equivalent
                                fwhm_i = line_fwhm[line_idx[i]]
                                fwhm_j = line_fwhm[line_idx[j]]
                                avg_fwhm = 0.5* (fwhm_i + fwhm_j)
                                diff_fwhm = abs(fwhm_i - fwhm_j)

                                if (line_broad[line_idx[i]] == line_broad[line_idx[j]]):
                                    adjust = 1.0  # they should be similar (both broad or narrow)
                                elif (line_broad[line_idx[j]]):
                                    adjust = 2.0  #
                                elif (line_broad[line_idx[i]]):
                                    adjust = 0.5  #

                                if avg_fwhm > 0 and adjust*diff_fwhm/avg_fwhm < 0.5:
                                    score += 1
                                    log.debug(f"Ratio match (+1) for solution = {solution.central_rest}: "
                                              f"rest {overlap[j]} to {overlap[i]}: "
                                              f"{min_ratio:0.2f} < {ratio:0.2f} +/- {ratio_err:0.2f} < {max_ratio:0.2f} "
                                              f"FWHM {fwhm_j}, {fwhm_i}")
                                else:
                                    log.debug(f"FWHM no match (0) for solution = {solution.central_rest}: "
                                              f"rest {overlap[j]} to {overlap[i]}: FWHM {fwhm_j}, {fwhm_i}: "
                                              f"ratios: {min_ratio:0.2f} < {ratio:0.2f} +/- {ratio_err:0.2f} < {max_ratio:0.2f}")

                            else:
                                if ratio < min_ratio:
                                    frac = (min_ratio-ratio)/min_ratio
                                else:
                                    frac = (ratio - max_ratio)/max_ratio

                                if frac > 0.5:
                                    score -= 1
                                    log.debug(f"Ratio mismatch (-1) for solution = {solution.central_rest}: "
                                              f"rest {overlap[j]} to {overlap[i]}: "
                                              f"{min_ratio:0.2f} !< {ratio:0.2f} +/- {ratio_err:0.2f} !< {max_ratio:0.2f} ")


            #todo: sther stuff
            # like spectral slope?
            #if score > 0:
            #    self.add_classification_label("AGN")
            return score

        except:
            log.info("Exception in Spectrum::solution_consistent_with_agn",exc_info=True)
            return 0

    def top_hat_filter(self,w_rest,w_obs, wx, hat_width=None, negative=False):
        #optimal seems to be around 1 to < 2 resolutions (e.g. HETDEX ~ 6AA) ... 6 is good, 12 is a bit
        #unstable ... or as rougly 3x pixel pix_size


        #build up an array with tophat filters at emission line positions
        #based on the rest and observed (shifted and streched based on the redshift)
        # wx is the array of wavelengths (e.g the x coords)
        # hat width in angstroms
        try:
            w_rest = np.float(w_rest)
            w_obs = np.float(w_obs)
            num_hats = 0

            if negative:
                filter = np.full(np.shape(wx), -1.0)
            else:
                filter = np.zeros(np.shape(wx))

            pix_size = np.float(wx[1]-wx[0]) #assume to be evenly spaced


            if hat_width is None:
                hat_width = 3.0*pix_size

            half_hat = int(np.ceil(hat_width/pix_size)/2.0) #hat is split evenly on either side of center pix
            z = w_obs/w_rest -1.0

            #for each line in self.emission_lines that is in range, add a top_hat filter to filter
            for e in self.emission_lines:
                w = e.redshift(z)

                #set center pixel and half-hat on either side to 1.0
                if (w > wx[0]) and (w < wx[-1]):
                    num_hats += 1
                    idx = getnearpos(wx,w)
                    filter[idx-half_hat:idx+half_hat+1] = 1.0
        except:
            log.warning("Unable to build top hat filter.", exc_info=True)
            return None

        return filter, num_hats


    def set_spectra(self,wavelengths, values, errors, central, values_units = 0, estflux=None, estflux_unc=None,
                    eqw_obs=None, eqw_obs_unc=None, fit_min_sigma=GAUSS_FIT_MIN_SIGMA,estcont=None,estcont_unc=None,
                    fwhm=None,fwhm_unc=None):
        self.wavelengths = []
        self.values = []
        self.errors = []

        self.all_found_lines = None
        self.all_found_absorbs = None
        self.solutions = None
        self.central_eli = None

        if self.noise_estimate is None or len(self.noise_estimate) == 0:
            self.noise_estimate = errors[:]
            self.noise_estimate_wave = wavelengths[:]

        if central is None:
            self.wavelengths = wavelengths
            self.values = values
            self.errors = errors
            self.values_units = values_units
            self.central = central
            return

        if fwhm is not None:
            self.fwhm = fwhm
            if fwhm_unc is not None:
                self.fwhm_unc = fwhm_unc #might be None
            else:
                self.fwhm_unc = 0

        #scan for lines
        try:
            self.all_found_lines = peakdet(wavelengths, values, errors, values_units=values_units, enforce_good=True)
        except:
            log.warning("Exception in spectum::set_spectra()",exc_info=True)

        #run MCMC on this one ... the main line
        try:

            if self.identifier is None and self.plot_dir is None:
                show_plot = False #intermediate call, not the final
            else:
                show_plot = G.DEBUG_SHOW_GAUSS_PLOTS

            try:
                allow_broad = (self.fwhm + self.fwhm_unc) > (GOOD_BROADLINE_SIGMA * 2.355)
            except:
                allow_broad = False

            eli = signal_score(wavelengths=wavelengths, values=values, errors=errors,central=central,spectrum=self,
                               values_units=values_units, sbr=None, min_sigma=fit_min_sigma,
                               show_plot=show_plot,plot_id=self.identifier,
                               plot_path=self.plot_dir,do_mcmc=True,allow_broad=allow_broad)
        except:
            log.error("Exception in spectrum::set_spectra calling signal_score().",exc_info=True)
            eli = None

        if eli:
            if (estflux is None) or (eqw_obs is None) or (estflux == -1) or (eqw_obs <= 0.0):
                #basically ... if I did not get this from Karl, use my own measure
                if (eli.mcmc_a is not None) and (eli.mcmc_y is not None):
                    a_unc = 0.5 * (abs(eli.mcmc_a[1]) + abs(eli.mcmc_a[2])) / eli.mcmc_dx
                    y_unc = 0.5 * (abs(eli.mcmc_y[1]) + abs(eli.mcmc_y[2])) / eli.mcmc_dx

                    estflux = eli.mcmc_line_flux
                    estflux_unc = a_unc

                    estcont = eli.mcmc_continuum
                    estcont_unc = y_unc

                    eqw_obs = abs(estflux / eli.mcmc_continuum)
                    eqw_obs_unc = abs(eqw_obs) * np.sqrt((a_unc / estflux) ** 2 + (y_unc / eli.mcmc_continuum) ** 2)
                else: #not from mcmc, so we have no error
                    estflux = eli.line_flux
                    estflux_unc = 0.0
                    eqw_obs = eli.eqw_obs
                    eqw_obs_unc = 0.0

            if (fwhm is None):
                self.fwhm = eli.fwhm
                self.fwhm_unc = 0. #right now, not actually calc the uncertainty

            #if (self.snr is None) or (self.snr == 0):
            #    self.snr = eli.snr

            self.central_eli = copy.deepcopy(eli)

            # get very basic info (line fit)
            # coeff = fit_line(wavelengths, values, errors)  # flipped order ... coeff[0] = 0th, coeff[1]=1st
            # self.spectrum_linear_coeff = coeff

            # also get the overall slope
            self.spectrum_slope, self.spectrum_slope_err = SU.simple_fit_slope(wavelengths, values, errors)

            log.info("%s Spectrum basic slope: %g +/- %g"
                     %(self.identifier,self.spectrum_slope,self.spectrum_slope_err))
            #todo: maybe also a basic parabola? (if we capture an overall peak? like for a star black body peak?
        else:
            log.warning("Warning! Did not successfully compute signal_score on main emission line.")

        self.wavelengths = wavelengths
        self.values = values
        self.errors = errors
        self.values_units = values_units
        self.central = central
        self.estflux = estflux
        self.estflux_unc = estflux_unc
        self.eqw_obs = eqw_obs
        self.eqw_obs_unc = eqw_obs_unc
        self.estcont = estcont
        self.estcont_unc = estcont_unc


        #also get the overall slope
        self.spectrum_slope, self.spectrum_slope_err = SU.simple_fit_slope(wavelengths, values, errors)
        #if self.snr is None:
        #    self.snr = 0


    def find_central_wavelength(self,wavelengths = None,values = None, errors=None,values_units=0):
        central = 0.0
        update_self = False
        if (wavelengths is None) or (values is None):
            wavelengths = self.wavelengths
            values = self.values
            values_units = self.values_units
            update_self = True

        #find the peaks and use the largest
        #for now, largest means highest value

        # if values_are_flux:
        #     #!!!!! do not do values *= 10.0 (will overwrite)
        #     # assumes fluxes in e-17 .... making e-18 ~= counts so logic can stay the same
        #     values = values * 10.0

        values,values_units = norm_values(values,values_units)

        #does not need errors for this purpose
        peaks = peakdet(wavelengths,values,errors,values_units=values_units,enforce_good=False) #as of 2018-06-11 these are EmissionLineInfo objects
        max_score = -np.inf
        if peaks is None:
            log.info("No viable emission lines found.")
            return 0.0

        #find the largest flux
        for p in peaks:
            #  0   1   2   3          4
            # pi, px, pv, pix_width, centroid_pos
            #if p[2] > max_v:
            #    max_v = p[2]
            #    central = p[4]
            if p.line_score > max_score:
                max_score = p.line_score
                central = p.fit_x0

        if update_self:
            self.central = central

        log.info("Central wavelength = %f" %central)

        return central

    def classify(self,wavelengths = None,values = None, errors=None, central = None, values_units=0,known_z=None):
        #for now, just with additional lines
        #todo: later add in continuum
        #todo: later add in bayseian stuff
        if not G.CLASSIFY_WITH_OTHER_LINES:
            return []

        self.solutions = []
        if (wavelengths is not None) and (values is not None) and (central is not None):
            self.set_spectra(wavelengths,values,errors,central,values_units=values_units)
        else:
            wavelengths = self.wavelengths
            values = self.values
            central = self.central
            errors=self.errors
            values_units = self.values_units

        #if central wavelength not provided, find the peaks and use the largest
        #for now, largest means highest value
        if (central is None) or (central == 0.0):
            try:
                if G.CONTINUUM_RULES:
                    central = wavelengths[np.argmax(values)]
                    self.central = central
                else:
                    central = self.find_central_wavelength(wavelengths,values,errors,values_units=values_units)
            except:
                pass

        if (central is None) or (central == 0.0):
            log.warning("Cannot classify. No central wavelength specified or found.")
            return []

        solutions = self.classify_with_additional_lines(wavelengths,values,errors,central,values_units,known_z=known_z)
        self.solutions = solutions

        #set the unmatched solution (i.e. the solution score IF all the extra lines were unmatched, not
        #the unmatched score for the best solution) #instead, find the LyA solution and check it specifically
        try:
            self.unmatched_solution_count, self.unmatched_solution_score = self.unmatched_lines_score(Classifier_Solution(self.central))
            log.debug(f"Unmatched solution line count {self.unmatched_solution_count} and score {self.unmatched_solution_score}")
        except:
            log.debug("Exception computing unmatched solution count and score",exc_info=True)

        #get the LAE and OII solutions and send to Bayesian to check p_LAE/p_OII
        self.addl_fluxes = []
        self.addl_wavelengths = []
        self.addl_fluxerrs = []
        for s in solutions:
            if (abs(s.central_rest - G.LyA_rest) < 2.0) or \
               (abs(s.central_rest - G.OII_rest) < 2.0): #LAE or OII

                for l in s.lines:
                    if l.flux > 0:
                        self.addl_fluxes.append(l.flux)
                        self.addl_wavelengths.append((l.w_obs))
                        #todo: get real error (don't have that unless I run mcmc and right now, only running on main line)
                        self.addl_fluxerrs.append(0.0)
                       # self.addl_fluxerrs.append(l.flux*.3)

        #if len(addl_fluxes) > 0:
        self.get_bayes_probabilities(addl_wavelengths=self.addl_wavelengths,addl_fluxes=self.addl_fluxes,
                                     addl_errors=self.addl_fluxerrs)
        #self.get_bayes_probabilities(addl_fluxes=None, addl_wavelengths=None)

        return solutions


    def is_near_a_peak(self,w,aa=4.0): #is the provided wavelength near one of the found peaks (+/- few AA or pixels)

        wavelength = 0.0
        if (self.all_found_lines is None):
            self.all_found_lines = peakdet(self.wavelengths, self.values, self.errors,values_units=self.values_units)

        if self.all_found_lines is None:
            return 0.0

        for f in self.all_found_lines:
            if abs(f.fit_x0 - w) < aa:
                wavelength = f.fit_x0
                break

        return wavelength

    def unmatched_lines_score(self,solution,aa=4.0):
        """
        Return the lines and summed line scores for unmatched lines associated with a solution
        :param solutions:
        :param aa:
        :return:
        """

        try:
            if (self.all_found_lines is None):
                self.all_found_lines = peakdet(self.wavelengths, self.values, self.errors,values_units=self.values_units)

            if self.all_found_lines is None or len(self.all_found_lines)==0:
                return 0,0

            unmatched_score_list = np.array([x.line_score for x in self.all_found_lines if 3550.0 < x.fit_x0 < 5500.0 ])
            unmatched_wave_list = np.array([x.fit_x0 for x in self.all_found_lines if 3550.0 < x.fit_x0 < 5500.0])
            solution_wave_list = np.array([solution.central_rest * (1.+solution.z)] + [x.w_obs for x in solution.lines])

            for line in solution_wave_list:
                idx = np.where(abs(unmatched_wave_list-line) <= aa)[0]
                if idx is not None and len(idx) > 0: #should usually be just 0 or 1
                    #remove from unmatched_list as these are now matched
                    idx = idx[::-1]
                    for i in idx:
                        unmatched_wave_list = np.delete(unmatched_wave_list,i)
                        unmatched_score_list = np.delete(unmatched_score_list,i)

            #now check based on line FWHM (broad lines found differently could be off in peak position, but overlap)
            for i in range(len(unmatched_wave_list)-1,-1,-1):
                for line in solution.lines:
                    if abs(line.w_obs - unmatched_wave_list[i]) < (2*line.sigma):
                        unmatched_wave_list = np.delete(unmatched_wave_list,i)
                        unmatched_score_list = np.delete(unmatched_score_list,i)
                        break

            #what is left over
            if len(unmatched_score_list) > 0:
                log.debug("Unmatched lines: (wave,score): " + str([(w,s) for w,s in zip(unmatched_wave_list,unmatched_score_list)]))
            return len(unmatched_score_list), np.nansum(unmatched_score_list)
        except:
            log.debug("Exception in spectrum::unmatched_lines_score",exc_info=True)
            return 0,0

    def is_near_absorber(self,w,aa=4.0):#pix_size=1.9): #is the provided wavelength near one of the found peaks (+/- few AA or pixels)

        if not (G.DISPLAY_ABSORPTION_LINES or G.MAX_SCORE_ABSORPTION_LINES):
            return 0

        wavelength = 0.0
        if (self.all_found_absorbs is None):
            self.all_found_absorbs = peakdet(self.wavelengths, invert_spectrum(self.wavelengths,self.values),
                                             self.errors, values_units=self.values_units,absorber=True)
            self.clean_absorbers()

        if self.all_found_absorbs is None:
            return 0.0

        for f in self.all_found_absorbs:
            if abs(f.fit_x0 - w) < aa:
                wavelength = f.fit_x0
                break

        return wavelength


    def clean_absorbers(self):
        #the intent is to not mark a "partial trough next to a peak as an absorption feature
        #but this does not really do the job
        #really should properly fit an absorption profile and not use this cheap, flip the spectra approach
        return
        if self.all_found_absorbs is not None:
            for i in range(len(self.all_found_absorbs)-1,-1,-1):
                if self.is_near_a_peak(self.all_found_absorbs[i].fit_x0,aa=10.0):
                    del self.all_found_absorbs[i]



    def classify_with_additional_lines(self,wavelengths = None,values = None,errors=None,central = None,
                                       values_units=0,known_z=None):
        """
        using the main line
        for each possible classification of the main line
            for each possible additional line
                if in the range of the spectrum
                    fit a line (?gaussian ... like the score?) to the exact spot of the additional line
                        (allow the position to shift a little)
                    get the score and S/N (? how best to get S/N? ... look only nearby?)
                    if score is okay and S/N is at least some minium (say, 2)
                        add to weighted solution (say, score*S/N)
                    (if score or S/N not okay, skip and move to the next one ... no penalties)

        best weighted solution wins
        ?what about close solutions? maybe something where we return the best weight / (sum of all weights)?
        or (best weight - 2nd best) / best ?

        what to return?
            with a clear winner:
                redshift of primary line (z)
                rest wavelength of primary line (e.g. effectively, the line identification) [though with z is redundant]
                list of additional lines found (rest wavelengths?)
                    and their scores or strengths?

        should return all scores? all possible solutions? maybe a class called classification_solution?

        """

        if (values is None) or (wavelengths is None) or (central is None):
            values = self.values
            wavelengths = self.wavelengths
            errors = self.errors
            central = self.central
            values_units = self.values_units

        if (self.all_found_lines is None):
            self.all_found_lines = peakdet(wavelengths,values,errors, values_units=values_units)
            if G.DISPLAY_ABSORPTION_LINES or G.MAX_SCORE_ABSORPTION_LINES:
                self.all_found_absorbs = peakdet(wavelengths, invert_spectrum(wavelengths,values),errors,
                                                 values_units=values_units,absorber=True)
                self.clean_absorbers()


        solutions = []

        if G.CONTINUUM_RULES:
            return solutions

        per_line_total_score = 0.0 #sum of all scores (use to represent each solution as fraction of total score)


        #for each self.emission_line
        #   run down the list of remianing self.emission_lines and calculate score for each
        #   make a copy of each emission_line, set the score, save to the self.lines list []
        #
        #sort solutions by score

        max_w = max(wavelengths)
        min_w = min(wavelengths)

        for e in self.emission_lines:
            #!!! consider e.solution to mean it cannot be a lone solution (that is, the line without other lines)
            #if not e.solution: #changed!!! this line cannot be the ONLY line, but can be the main line if there are others
            #    continue

            central_z = central/e.w_rest - 1.0
            if (central_z) < 0.0:
                if central_z > G.NEGATIVE_Z_ERROR: #assume really z=0 and this is wavelength error
                    central_z = 0.0
                else:
                    continue #impossible, can't have a negative z

            if known_z is not None:
                if abs(central_z-known_z) > 0.05:
                    log.info(f"Known z {known_z:0.2f} invalidates solution for {e.name} at z = {central_z:0.2f}")
                    continue
            elif (self.fwhm) and (self.fwhm_unc) and (((self.fwhm-self.fwhm_unc)/2.355 > LIMIT_BROAD_SIGMA) and not e.broad):
                log.info(f"FWHM ({self.fwhm},+/- {self.fwhm_unc}) too broad for {e.name}. Solution disallowed.")
                continue
            else:
                #normal rules apply only allow major lines or lines marked as allowing a solution

                #2020-09-08 DD take out the check for rank 4; extra comparisons later make this no longer necessary
                #to filter out noisy matches
                # if e.rank > 4:  # above rank 4, don't even consider as a main line (but it can still be a supporting line)
                #    continue

                try:
                    if not (e.solution) and (e.min_obs_wave < central < e.max_obs_wave) and (self.fwhm >= e.min_fwhm):
                        e.solution = True  # this change applies only to THIS instance of a spectrum, so it is safe
                except:  # could be a weird issue
                    if self.fwhm is not None:
                        log.debug("Unexpected exception in specturm::classify_with_additional_lines", exc_info=True)
                    # else: #likely because we could not get a fit at that position

            if e.w_rest == G.LyA_rest:
                #assuming a maximum expected velocity offset, we can allow the additional lines to be
                #asymmetrically less redshifted than LyA
                GOOD_MAX_DX0_MULT = [MAX_LYA_VEL_OFFSET / 3.0e5 * central  ,GOOD_MAX_DX0_MULT_LYA[1]]
            else:
                GOOD_MAX_DX0_MULT = GOOD_MAX_DX0_MULT_OTHER

            sol = Classifier_Solution()
            sol.z = central_z
            sol.central_rest = e.w_rest
            sol.name = e.name
            sol.color = e.color
            sol.emission_line = copy.deepcopy(e)
            sol.emission_line.w_obs = sol.emission_line.w_rest*(1.0 + sol.z)
            sol.emission_line.solution = True
            sol.prob_noise = 1.0

            for a in self.emission_lines:
                if e == a:
                    continue

                a_central = a.w_rest*(sol.z+1.0)
                if (a_central > max_w) or (a_central < min_w) or (abs(a_central-central) < 5.0):
                    continue

                log.debug("Testing line solution. Anchor line (%s, %0.1f) at %0.1f, target line (%s, %0.1f) at %0.1f."
                          %(e.name,e.w_rest,e.w_rest*(1.+central_z),a.name,a.w_rest,a_central))

                eli = signal_score(wavelengths=wavelengths, values=values, errors=errors, central=a_central,
                                   central_z = central_z, values_units=values_units, spectrum=self,
                                   show_plot=False, do_mcmc=False,
                                   allow_broad= (a.broad and e.broad))

                if eli and a.broad and e.broad and (eli.fit_sigma < eli.fit_sigma_err) and \
                    ((eli.fit_sigma + eli.fit_sigma_err) > GOOD_BROADLINE_SIGMA):
                        #try again with medfilter fit
                        eli = signal_score(wavelengths=wavelengths, values=medfilt(values, 5), errors=medfilt(errors, 5),
                            central=a_central, central_z = central_z, values_units=values_units, spectrum=self,
                            show_plot=False, do_mcmc=False, allow_broad= (a.broad and e.broad))
                elif eli is None and a.broad and e.broad:
                    #are they in the same family? OII, OIII, OIV :  CIV, CIII, CII : H_beta, ....
                    samefamily = False
                    if (e.name[0] == 'O') and (a.name[0] == 'O'):
                        samefamily = True
                    elif (e.name[0:2] == 'CI') and (a.name[0:2] == 'CI'):
                        samefamily = True
                    elif (e.name[0:2] == 'H$') and (a.name[0:2] == 'H$'):
                        samefamily = True

                    if not samefamily or (samefamily and (self.central_eli and self.central_eli.fit_sigma and self.central_eli.fit_sigma > 5.0)):
                        eli = signal_score(wavelengths=wavelengths, values=medfilt(values, 5), errors=medfilt(errors, 5),
                                       central=a_central, central_z=central_z, values_units=values_units, spectrum=self,
                                       show_plot=False, do_mcmc=False, allow_broad=(a.broad and e.broad),broadfit=5)

                #try as absorber
                if G.MAX_SCORE_ABSORPTION_LINES and eli is None and self.is_near_absorber(a_central):
                    eli = signal_score(wavelengths=wavelengths, values=invert_spectrum(wavelengths,values), errors=errors, central=a_central,
                                       central_z=central_z, values_units=values_units, spectrum=self,
                                       show_plot=False, do_mcmc=False,absorber=True)


                good = False
                if (eli is not None) and eli.is_good(z=sol.z,allow_broad=(e.broad and a.broad)):
                    good = True

                #specifically check for 5007 and 4959 as nasty LAE contaminatant
                if eli and not good:
                    try:
                        if (np.isclose(a.w_rest,4959,atol=1.0) and np.isclose(e.w_rest,5007,atol=1.0)):
                            ratio = self.central_eli.fit_a / eli.fit_a
                            ratio_err = abs(ratio) * np.sqrt( (eli.fit_a_err / eli.fit_a) ** 2 +
                                                    (self.central_eli.fit_a_err / self.central_eli.fit_a) ** 2)

                            if (ratio - ratio_err) < 3 < (ratio + ratio_err):
                                good = True

                        elif (np.isclose(a.w_rest,5007,atol=1.0) and np.isclose(e.w_rest,4959,atol=1.0)):
                            ratio = eli.fit_a / self.central_eli.fit_a
                            ratio_err = abs(ratio) * np.sqrt( (eli.fit_a_err / eli.fit_a) ** 2 +
                                                    (self.central_eli.fit_a_err / self.central_eli.fit_a) ** 2)

                            if (ratio - ratio_err) < 3 < (ratio + ratio_err):
                                good = True
                    except:
                        pass

                if good:
                    #if this line is too close to another, keep the one with the better score
                    add_to_sol = True

                    # BASIC FWHM check (by rank)
                    # higher ranks are stronger lines and must have similar or greater fwhm (or sigma)
                    #rank 1 is highest, 4 lowest; a is the line being tested, e is the solution anchor line
                    if a.rank < e.rank:

                        try: #todo: something similar in the specific consistency checks? (not sure here anyway since fwhm is related to lineflux)
                            #maybe fit_h is a better, more independent factor?
                            #but needs to be height above continuum, so now we are looking at EqW
                            #and we're just going in circles. Emprically, line_flux seems to work better than the others
                            # adjust = eli.line_flux / self.central_eli.line_flux
                            # #adjust = (eli.fit_h-eli.fit_y) / (self.central_eli.fit_h - self.central_eli.fit_y)
                            # adjust = min(adjust,1.0/adjust)

                            if (a.broad == e.broad):
                                adjust = 1.0 #they should be similar (both broad or narrow)
                            elif (a.broad):
                                adjust = 3.0 #the central line can be more narrow
                            elif (e.broad):
                                adjust = 0.33 #the central line can be more broad

                            fwhm_comp = adjust * 2.0 * (eli.fit_sigma - self.central_eli.fit_sigma)  / \
                                        (eli.fit_sigma + self.central_eli.fit_sigma)

                            if -0.5 < fwhm_comp  < 0.5:
                                    # delta sigma is okay, the higher rank is larger sigma (negative result) or within 50%
                                pass
                            else:
                                log.debug(f"Sigma sanity check failed {self.identifier}. Disallowing {a.name} at sigma {eli.fit_sigma:0.2f} "
                                          f" vs anchor sigma {self.central_eli.fit_sigma:0.2f}")
                                add_to_sol = False
                                # this line should not be part of the solution
                        except:
                            pass


                    #check the main line first
                    if abs(central - eli.fit_x0) < 5.0:
                        # the new line is not as good so just skip it
                        log.debug("Emission line (%s) at (%f) close to or overlapping primary line (%f). Rejecting."
                                 % (self.identifier, eli.fit_x0,central))
                        add_to_sol = False

                    else:
                        for i in range(len(sol.lines)):
                            if abs(sol.lines[i].w_obs - eli.fit_x0) < 10.0:

                                #keep the emission line over the absorption line, regardless of score, if that is the case
                                if sol.lines[i].absorber != eli.absorber:
                                    if eli.absorber:
                                        log.debug("Emission line too close to absorption line (%s). Removing %s(%01.f) "
                                                 "from solution in favor of %s(%0.1f)"
                                            % (self.identifier, a.name, a.w_rest, sol.lines[i].name, sol.lines[i].w_rest))

                                        add_to_sol = False
                                    else:
                                        log.debug("Emission line too close to absorption line (%s). Removing %s(%01.f) "
                                                 "from solution in favor of %s(%0.1f)"
                                            % (self.identifier, sol.lines[i].name, sol.lines[i].w_rest, a.name, a.w_rest))
                                        # remove this solution
                                        per_line_total_score -= sol.lines[i].line_score
                                        sol.score -= sol.lines[i].line_score
                                        sol.prob_noise /= sol.lines[i].prob_noise
                                        del sol.lines[i]
                                else: #they are are of the same type, so keep the better score
                                    if sol.lines[i].line_score < eli.line_score:
                                        log.debug("Lines too close (%s). Removing %s(%01.f) from solution in favor of %s(%0.1f)"
                                                 % (self.identifier,sol.lines[i].name, sol.lines[i].w_rest,a.name, a.w_rest))
                                        #remove this solution
                                        per_line_total_score -= sol.lines[i].line_score
                                        sol.score -= sol.lines[i].line_score
                                        sol.prob_noise /= sol.lines[i].prob_noise
                                        del sol.lines[i]
                                        break
                                    else:
                                        #the new line is not as good so just skip it
                                        log.debug("Lines too close (%s). Removing %s(%01.f) from solution in favor of %s(%0.1f)"
                                                 % (self.identifier,a.name, a.w_rest,sol.lines[i].name, sol.lines[i].w_rest))
                                        add_to_sol = False
                                        break

                    #now, before we add, if we have not run MCMC on the feature, do so now
                    if G.MIN_MCMC_SNR > 0:
                        if add_to_sol:
                            if eli.mcmc_x0 is None:
                                eli = run_mcmc(eli,wavelengths,values,errors,a_central,values_units)

                            #and now validate the MCMC SNR (reminder:  MCMC SNR is line flux (e.g. Area) / (1sigma uncertainty)
                            if eli.mcmc_snr is None:
                                add_to_sol = False
                                log.debug("Line (at %f) rejected due to missing MCMC SNR" %(a_central))
                            elif eli.mcmc_snr < G.MIN_MCMC_SNR:
                                add_to_sol = False
                                log.debug("Line (at %f) rejected due to poor MCMC SNR (%f)" % (a_central,eli.mcmc_snr))
                            #todo: should we recalculate the score with the MCMC data (flux, SNR, etc)??
                            #todo: or, at this point, is this a binary condition ... the line is there, or not
                            #todo: .... still with multiple solutions possible, we must meet the minimum and then the best
                            #todo:      score (clear winner) wins


                    if add_to_sol:
                        l = copy.deepcopy(a)
                        l.w_obs = l.w_rest * (1.0 + sol.z)
                        l.z = sol.z
                        l.score = eli.score
                        l.snr = eli.snr
                        l.sbr = eli.sbr
                        l.eqw_obs = eli.eqw_obs
                        l.eqw_rest = l.eqw_obs / (1.0 + l.z)
                        l.flux = eli.line_flux
                        l.flux_err = eli.line_flux_err
                        l.sigma = eli.fit_sigma
                        l.sigma_err = eli.fit_sigma_err
                        l.line_score = eli.line_score
                        l.prob_noise = eli.prob_noise
                        l.absorber = eli.absorber
                        l.fit_dx0 = eli.fit_dx0

                        per_line_total_score += eli.line_score  # cumulative score for ALL solutions
                        sol.score += eli.line_score  # score for this solution
                        sol.prob_noise *= eli.prob_noise

                        sol.lines.append(l)
                        if l.absorber:
                            line_type = "absorption"
                        else:
                            line_type = "emission"
                        log.info("Accepting %s line (%s): %s(%0.1f at %01.f) snr = %0.1f  MCMC_snr = %0.1f  "
                                 "line_flux = %0.1g  sigma = %0.1f  line_score = %0.1f  p(noise) = %g"
                                 %(line_type, self.identifier,l.name,l.w_rest,l.w_obs,l.snr, eli.mcmc_snr, l.flux,
                                  l.sigma, l.line_score,l.prob_noise))
                else: #is not good
                    log.debug("Line rejected (failed is_good).")

            #now apply penalty for unmatched lines?
            try:
                sol.unmatched_lines_count, sol.unmatched_lines_score = self.unmatched_lines_score(sol)

                if sol.unmatched_lines_count > G.MAX_OK_UNMATCHED_LINES and sol.unmatched_lines_score > G.MAX_OK_UNMATCHED_LINES_SCORE:
                    log.info(f"Solution ({sol.name} {sol.central_rest:0.2f} at {sol.central_rest * (1+sol.z)}) penalized for excessive unmatched lines. Old score: {sol.score:0.2f}, "
                             f"Penalty {sol.unmatched_lines_score:0.2f} on {sol.unmatched_lines_count} lines")
                    sol.score -= sol.unmatched_lines_score
            except:
                log.info("Exception adjusting solution score for unmatched lines",exc_info=True)

            if sol.score > 0.0:
                # check if not a solution, has at least one other line

                allow_solution = False

                if (sol.lines is not None) and (len(sol.lines) > 1): #anything with 2 or more lines is "allowed"
                    allow_solution = True
                elif (e.solution): #only 1 line
                    allow_solution = True
                #need fwhm and obs line range
                elif (self.fwhm is not None) and (self.fwhm >= e.min_fwhm): #can be None if no good fit
                    allow_solution = True
                #technically, this condition should not trigger as if we are in the single line range, there IS NO SECOND LINE
                elif (e.min_obs_wave < central < e.max_obs_wave) :
                    #only 1 line and not a 1 line solution, except in certain configurations
                    allow_solution = True
                else:
                    allow_solution = False

                if allow_solution or (known_z is not None):
                    # log.info("Solution p(noise) (%f) from %d additional lines" % (sol.prob_noise, len(sol.lines) - 1))
                    # bonus for each extra line over the minimum

                    # sol.lines does NOT include the main line (just the extra lines)
                    n = len(np.where([l.absorber == False for l in sol.lines])[0])
                    #          n = len(sol.lines) + 1 #+1 for the main line
                    if n >= G.MIN_ADDL_EMIS_LINES_FOR_CLASSIFY:
                        bonus = 0.5 * (n ** 2 - n) * G.ADDL_LINE_SCORE_BONUS  # could be negative
                        # print("+++++ %s n(%d) bonus(%g)"  %(self.identifier,n,bonus))
                        sol.score += bonus
                        per_line_total_score += bonus
                    solutions.append(sol)
                else:
                    log.debug("Line (%s, %0.1f) not allowed as single line solution." % (sol.name, sol.central_rest))

        #end for e in emission lines

        #clean up invalid solutions (multiple lines with very different systematic velocity offsets)
        if True:
            for s in solutions:
                all_dx0 = [l.fit_dx0 for l in s.lines]
                all_score = [l.line_score for l in s.lines]
                rescore = False
                #enforce similar all_dx0
                while len(all_dx0) > 1:
                    #todo: no ... throw out the line farthest from the average and recompute ....
                    if max(all_dx0) - min(all_dx0) > G.SPEC_MAX_OFFSET_SPREAD: #differ by more than 2 AA
                        #throw out lowest score? or greatest dx0?
                        i = np.argmin(all_score)
                        log.info("Removing lowest score from solution %s (%s at %0.1f) due to extremes in fit_dx0 (%f,%f)."
                                 " Line (%s) Score (%f)"
                                 %(self.identifier,s.emission_line.name,s.central_rest,min(all_dx0),max(all_dx0),
                                   s.lines[i].name, s.lines[i].score))

                        s.rejected_lines.append(copy.deepcopy(s.lines[i]))
                        del all_dx0[i]
                        del all_score[i]
                        del s.lines[i]
                        rescore = True
                    else:
                        break

                if rescore:
                    #remove this solution?
                    old_score = s.score
                    per_line_total_score -= s.score

                    s.calc_score()
                    per_line_total_score += s.score

                    # HAVE to REAPPLY
                    # now apply penalty for unmatched lines?
                    try:
                        s.unmatched_lines_count, s.unmatched_lines_score = self.unmatched_lines_score(s)

                        if s.unmatched_lines_count > G.MAX_OK_UNMATCHED_LINES and s.unmatched_lines_score > G.MAX_OK_UNMATCHED_LINES_SCORE:
                            log.info("Re-apply unmatched lines after rescoring....")
                            log.info(
                                f"Solution ({s.name} {s.central_rest:0.2f} at {s.central_rest * (1 + s.z)}) penalized for excessive unmatched lines. Old score: {s.score:0.2f}, "
                                f"Penalty {s.unmatched_lines_score:0.2f} on {s.unmatched_lines_count} lines")
                            s.score -= s.unmatched_lines_score
                    except:
                        log.info("Exception adjusting solution score for unmatched lines", exc_info=True)


                    log.info("Solution:  %s (%s at %0.1f) rescored due to extremes in fit_dx0. Old score (%f) New Score (%f)"
                             %(self.identifier,s.emission_line.name,s.central_rest,old_score,s.score))


        #todo: check line ratios, AGN consistency, etc here?
        #at least 3 func calls
        #consistent_with_AGN (returns some scoring that is only used to boost AGN consistent solutions)
        #consistent_with_oii_galaxy()
        #consistent_with_star
        #??consistent with meteor #this may need to be elsewhere and probably involves check individual exposures
        #                          #since it would only show up in one exposure

        if G.MULTILINE_USE_CONSISTENCY_CHECKS:# and (self.central_eli is not None):
            if self.central_eli is None:
                #could  not fit the central line, so no solution is valid if it relies on the central
                #(can still be valid if there are mulitple other lines)
                central_eli = EmissionLineInfo()
                central_eli.line_score = 0.0
            else:
                central_eli = self.central_eli

            for s in solutions:

                if (central_eli.line_score == 0):
                    if (s is not None) and (s.lines is not None) and (len(s.lines) > 1):
                        pass #still okay there are 2+ other lines
                    else:
                        log.info(f"Solution {s.name} rejected. No central fit and few lines. Zeroing score.")
                        s.score = 0.0
                        s.scale_score = 0.0
                        s.frac_score = 0.0
                        continue

                # the pair of lines being checked are 4959 and 5007 (or the solution contains those pair of lines)
                try:
                    if (np.isclose(s.central_rest,4959,atol=1.0) or np.isclose(s.central_rest,5007,atol=1.0)) and \
                        np.any([(np.isclose(x.w_rest,4959,atol=1.0) or np.isclose(x.w_rest,5007,atol=1.0)) and abs(x.fit_dx0) < 2.0 for x in s.lines]):
                        oiii_lines = True
                    else:
                        oiii_lines = False
                except:
                    oiii_lines = False

                # even if weak, go ahead and check for inconsistency (ie. if 4595 present but 5007 is not, then that
                # solution does not make sense), but only allow a positive boost to the scoring IF the base solution
                # is not weak or IF this is a possible OIII 4595+5007 combination (which is well constrained)
                if s.score < G.MULTILINE_MIN_SOLUTION_SCORE and not oiii_lines:
                    no_plus_boost = True
                else:
                    no_plus_boost = False

                #todo: iterate over all types of objects
                #if there is no consistency (that is, the lines don't match up) you get no change
                #if there is anti-consistency (the lines match up but are inconsistent by ratio, you can get a score decrease)

                #AGN
                boost = self.scale_consistency_score_to_solution_score_factor(self.solution_consistent_with_agn(s))

                if boost != 1.0:
                    log.info(f"Solution: {s.name} score {s.score} to be modified by x{boost} for consistency with AGN")

                    #for the labeling, need to check vs the TOTAL score (so include the primary line)
                    if ( (s.score + central_eli.line_score) > G.MULTILINE_FULL_SOLUTION_SCORE) and (boost > 1.0) and \
                            (no_plus_boost is False):
                        #check BEFORE the boost
                        #however, only apply the label if at least one line is broad
                        line_fwhm = np.array([central_eli.fit_sigma*2.355] + [l.sigma * 2.355 for l in s.lines])
                        line_fwhm_err = np.array([central_eli.fit_sigma_err*2.355] + [l.sigma_err * 2.355 for l in s.lines])
                        if max(line_fwhm+line_fwhm_err) > 14.0 and s.emission_line.w_rest != 2799:
                            self.add_classification_label("agn")
                        else:
                            log.info(f"Solution: {s.name} 'agn' label omitted, but boost applied.")

                    per_line_total_score -= s.score
                    s.score = boost * s.score
                    per_line_total_score += s.score


                # low-z galaxy
                boost = self.scale_consistency_score_to_solution_score_factor(self.solution_consistent_with_low_z(s))

                if boost != 1.0:
                    log.info(f"Solution: {s.name} score {s.score} to be modified by x{boost} for consistency with low-z galaxy")

                    if ((s.score + central_eli.line_score) > G.MULTILINE_FULL_SOLUTION_SCORE) and \
                            (boost > 1.0) and (no_plus_boost is False):  # check BEFORE the boost
                        self.add_classification_label("lzg") #Low-z Galaxy

                    per_line_total_score -= s.score
                    s.score =  boost * s.score
                    if s.score < G.MULTILINE_MIN_SOLUTION_SCORE and oiii_lines:
                        log.info(f"Solution: {s.name} score {s.score} raised to minimum {G.MULTILINE_MIN_SOLUTION_SCORE} for 4959+5007")
                        s.score = G.MULTILINE_MIN_SOLUTION_SCORE
                        s.prob_noise = min(s.prob_noise,0.5/boost)

                    per_line_total_score += s.score
        else: #still check for invalid solutions (no valid central emission line)
            if self.central_eli is None:
                for s in solutions:
                    if (s is not None) and (s.lines is not None) and (len(s.lines) > 1):
                        pass #still okay there are 2+ other lines
                    else:
                        log.info(f"Solution {s.name} rejected. No central fit and few lines. Zeroing score.")
                        s.score = 0.0
                        s.scale_score = 0.0
                        s.frac_score = 0.0
                        continue
        #remove and zeroed scores
        try:
            if solutions is not None and len(solutions)>0:
                for i in range(len(solutions)-1,-1,-1):
                    if solutions[i].score <= 0:
                        del solutions[i]
                    elif solutions[i].emission_line.rank > 3 and min([x.rank for x in solutions[i].lines]) > 3:
                        del solutions[i]
        except:
            log.debug("Exception clearing solutions",exc_info=True)



        per_solution_total_score = np.nansum([s.score for s in solutions])

        for s in solutions:
            s.frac_score = s.score/per_solution_total_score
            s.scale_score = s.prob_real * G.MULTILINE_WEIGHT_PROB_REAL + \
                          min(1.0, s.score / G.MULTILINE_FULL_SOLUTION_SCORE) *  G.MULTILINE_WEIGHT_SOLUTION_SCORE + \
                          s.frac_score * G.MULTILINE_WEIGHT_FRAC_SCORE

        #sort by score
        solutions.sort(key=lambda x: x.scale_score, reverse=True)

        #check for display vs non-display (aka primary emission line solution)
        if len(solutions) > 1:
            if (solutions[0].frac_score / solutions[1].frac_score) < 2.0:
                if (solutions[0].emission_line.display is False) and (solutions[1].emission_line.display is True):
                    #flip them
                    log.debug("Flipping top solutions to favor display line over non-display line")
                    temp_sol = solutions[0]
                    solutions[0] = solutions[1]
                    solutions[1] = temp_sol

        for s in solutions:
            ll =""
            for l in s.lines:
                ll += " %s(%0.1f at %0.1f)," %(l.name,l.w_rest,l.w_obs)
            msg = "Possible Solution %s (%0.3f): %s (%0.1f at %0.1f), Frac = %0.2f, Score = %0.1f (%0.3f), z = %0.5f, +lines=%d %s"\
                    % (self.identifier, s.prob_real,s.emission_line.name,s.central_rest,s.central_rest*(1.0+s.z), s.frac_score,
                       s.score,s.scale_score,s.z, len(s.lines),ll )
            log.info(msg)
            #
            if G.DEBUG_SHOW_GAUSS_PLOTS:
                print(msg)

        return solutions


    def get_bayes_probabilities(self,addl_wavelengths=None,addl_fluxes=None,addl_errors=None):
        # todo: feed in addl_fluxes from the additonal line solutions (or build specifically)?
        # todo: make use of errors

        #care only about the LAE and OII solutions:
        #todo: find the LyA and OII options in the solution list and use to fill in addl_fluxes?

        # self.p_lae_oii_ratio, self.p_lae, self.p_oii, plae_errors = line_prob.prob_LAE(wl_obs=self.central,
        #                                                    lineFlux=self.estflux,
        #                                                    lineFlux_err=self.estflux_unc,
        #                                                    ew_obs=self.eqw_obs,
        #                                                    ew_obs_err=self.eqw_obs_unc,
        #                                                    c_obs=None, which_color=None,
        #                                                    addl_wavelengths=addl_wavelengths,
        #                                                    addl_fluxes=addl_fluxes,
        #                                                    addl_errors=addl_errors,
        #                                                    sky_area=None,
        #                                                    cosmo=None, lae_priors=None,
        #                                                    ew_case=None, W_0=None,
        #                                                    z_OII=None, sigma=None, estimate_error=True)


        self.p_lae_oii_ratio, self.p_lae, self.p_oii, plae_errors = line_prob.mc_prob_LAE(wl_obs=self.central,
                                                           lineFlux=self.estflux,
                                                           lineFlux_err=self.estflux_unc,
                                                           continuum=self.estcont,
                                                           continuum_err=self.estcont_unc,
                                                           c_obs=None, which_color=None,
                                                           addl_wavelengths=addl_wavelengths,
                                                           addl_fluxes=addl_fluxes,
                                                           addl_errors=addl_errors,
                                                           sky_area=None,
                                                           cosmo=None, lae_priors=None,
                                                           ew_case=None, W_0=None,
                                                           z_OII=None, sigma=None)

        try:
            if plae_errors:
                self.p_lae_oii_ratio_range = plae_errors['ratio']
        except:
            pass
        # if (self.p_lae is not None) and (self.p_lae > 0.0):
        #     if (self.p_oii is not None) and (self.p_oii > 0.0):
        #         self.p_lae_oii_ratio = self.p_lae /self.p_oii
        #     else:
        #         self.p_lae_oii_ratio = float('inf')
        # else:
        #     self.p_lae_oii_ratio = 0.0
        #
        # self.p_lae_oii_ratio = min(line_prob.MAX_PLAE_POII,self.p_lae_oii_ratio) #cap to MAX

    def build_full_width_spectrum(self,wavelengths = None,  counts = None, errors = None, central_wavelength = None,
                                  values_units = 0, show_skylines=True, show_peaks = True, name=None,
                                  dw=MIN_FWHM,h=MIN_HEIGHT,dh=MIN_DELTA_HEIGHT,zero=0.0,peaks=None,annotate=True,
                                  figure=None,show_line_names=True):


        use_internal = False
        if (counts is None) or (wavelengths is None) or (central_wavelength is None):
            counts = self.values
            #if self.values_are_flux: #!!! need a copy here ... DO NOT counts *= 10.0
            #    counts = counts * 10.0 #flux assumed to be cgs x10^-17 ... by 10x to x10^-18 become very similar to counts in scale

            counts, values_units = norm_values(counts,self.values_units)
            wavelengths = self.wavelengths
            central_wavelength = self.central
            use_internal = True

        if len(counts)==0:
            #not empty but still wrong
            log.error("Spectrum::build_full_width_spectrum. No spectrum to plot.")
            return None

        # fig = plt.figure(figsize=(5, 6.25), frameon=False)
        if figure is None:
            fig = plt.figure(figsize=(G.ANNULUS_FIGURE_SZ_X, 2), frameon=False)
            plt.subplots_adjust(left=0.05, right=0.95, top=1.0, bottom=0.0)
        else:
            fig = figure


        if show_line_names:
            dy = 1.0 / 5.0  # + 1 skip for legend, + 2 for double height spectra + 2 for double height labels
            specplot = plt.axes([0.05, 0.20, 0.90, 0.40])
        else:
            dy = 0.0
            specplot = plt.axes([0.05, 0.1, 0.9, 0.8]) #left,bottom,width, height in fraction of 1.0

        # this is the 1D averaged spectrum
        #textplot = plt.axes([0.025, .6, 0.95, dy * 2])
        #specplot = plt.axes([0.05, 0.20, 0.90, 0.40])
        #specplot = plt.axes([0.025, 0.20, 0.95, 0.40])

        # they should all be the same length
        # yes, want round and int ... so we get nearest pixel inside the range)
        left = wavelengths[0]
        right = wavelengths[-1]

        try:
            mn = np.min(counts)
            mn = max(mn, -20)  # negative flux makes no sense (excepting for some noise error)
            mx = np.max(counts)
            ran = mx - mn
            specplot.plot(wavelengths, counts,lw=0.5,c='b')

            specplot.axis([left, right, mn - ran / 20, mx + ran / 20])
            yl, yh = specplot.get_ylim()

            specplot.locator_params(axis='y', tight=True, nbins=4)


            if show_peaks:
                #emistab.append((pi, px, pv,pix_width,centroid))
                if peaks is None:
                    if (self.all_found_lines is not None):
                        peaks = self.all_found_lines
                    else:
                        peaks = peakdet(wavelengths,counts,errors, dw,h,dh,zero,values_units=values_units) #as of 2018-06-11 these are EmissionLineInfo objects
                        self.all_found_lines = peaks
                        if G.DISPLAY_ABSORPTION_LINES or G.MAX_SCORE_ABSORPTION_LINES:
                            self.all_found_absorbs = peakdet(wavelengths, invert_spectrum(wavelengths,counts), errors,
                                                             values_units=values_units,absorber=True)
                            self.clean_absorbers()


                #scores = []
                #for p in peaks:
                #    scores.append(signal_score(wavelengths, counts, p[1]))

                #for i in range(len(scores)):
                #    print(peaks[i][0],peaks[i][1], peaks[i][2], peaks[i][3], peaks[i][4], scores[i])

                if (peaks is not None) and (len(peaks) > 0):
                    # specplot.scatter(np.array(peaks)[:, 1], np.array(peaks)[:, 2], facecolors='none', edgecolors='r',
                    #                  zorder=99)
                    #
                    # for i in range(len(peaks)):
                    #     h = peaks[i][2]
                    #     specplot.annotate("%0.1f"%peaks[i][5],xy=(peaks[i][1],h),xytext=(peaks[i][1],h),fontsize=6,zorder=99)
                    #
                    #     log.debug("Peak at: %g , Score = %g , SNR = %g" %(peaks[i][1],peaks[i][5], peaks[i][6]))

                    #                 0   1   2  3           4            5          6
                    #emistab.append((pi, px, pv, pix_width, centroid_pos,eli.eqw_obs,eli.snr))

                    x = [p.raw_x0 for p in peaks]
                    y = [p.raw_h for p in peaks] #np.array(peaks)[:, 2]

                    specplot.scatter(x, y, facecolors='none', edgecolors='r',zorder=99)

                    if annotate:
                        for i in range(len(peaks)):
                            h = peaks[i].raw_h
                            specplot.annotate("%0.1f"%peaks[i].eqw_obs,xy=(peaks[i].fit_x0,h),xytext=(peaks[i].fit_x0,h),
                                              fontsize=6,zorder=99)

                            log.debug("Peak at %g , Score = %g , SNR = %g" %(peaks[i].fit_x0,peaks[i].eqw_obs, peaks[i].snr))


            #textplot = plt.axes([0.025, .6, 0.95, dy * 2])
            textplot = plt.axes([0.05, .6, 0.90, dy * 2])
            textplot.set_xticks([])
            textplot.set_yticks([])
            textplot.axis(specplot.axis())
            textplot.axis('off')

            if central_wavelength > 0:
                wavemin = specplot.axis()[0]
                wavemax = specplot.axis()[1]
                legend = []
                name_waves = []
                obs_waves = []

                rec = plt.Rectangle((central_wavelength - 20.0, yl), 2 * 20.0, yh - yl, fill=True, lw=0.5, color='y', zorder=1)
                specplot.add_patch(rec)

                if show_line_names:

                    if use_internal and (len(self.solutions) > 0):

                        e = self.solutions[0].emission_line

                        z = self.solutions[0].z

                        #plot the central (main) line
                        y_pos = textplot.axis()[2]
                        textplot.text(e.w_obs, y_pos, e.name + " {", rotation=-90, ha='center', va='bottom',
                                      fontsize=12, color=e.color)  # use the e color for this family

                        #plot the additional lines
                        for f in self.solutions[0].lines:
                            if f.score > 0:
                                y_pos = textplot.axis()[2]
                                textplot.text(f.w_obs, y_pos, f.name + " {", rotation=-90, ha='center', va='bottom',
                                              fontsize=12, color=e.color)  # use the e color for this family


                        #todo: show the fractional score?
                        #todo: show the next highest possibility?
                        legend.append(mpatches.Patch(color=e.color,
                                                     label="%s, z=%0.5f, Score = %0.1f (%0.2f)" %(e.name,self.solutions[0].z,
                                                                                self.solutions[0].score,
                                                                                self.solutions[0].frac_score)))
                        name_waves.append(e.name)


                    else:
                        for e in self.emission_lines:
                            if not e.solution:
                                continue

                            z = central_wavelength / e.w_rest - 1.0

                            if (z < 0):
                                continue

                            count = 0
                            for f in self.emission_lines:
                                if (f == e) or not (wavemin <= f.redshift(z) <= wavemax):
                                    continue

                                count += 1
                                y_pos = textplot.axis()[2]
                                for w in obs_waves:
                                    if abs(f.w_obs - w) < 20:  # too close, shift one vertically
                                        y_pos = (textplot.axis()[3] - textplot.axis()[2]) / 2.0 + textplot.axis()[2]
                                        break

                                obs_waves.append(f.w_obs)
                                textplot.text(f.w_obs, y_pos, f.name + " {", rotation=-90, ha='center', va='bottom',
                                              fontsize=12, color=e.color)  # use the e color for this family

                            if (count > 0) and not (e.name in name_waves):
                                legend.append(mpatches.Patch(color=e.color, label=e.name))
                                name_waves.append(e.name)

                    # make a legend ... this won't work as is ... need multiple colors
                    skipplot = plt.axes([.025,0.0, 0.95, dy])
                    skipplot.set_xticks([])
                    skipplot.set_yticks([])
                    skipplot.axis(specplot.axis())
                    skipplot.axis('off')
                    skipplot.legend(handles=legend, loc='center', ncol=len(legend), frameon=False,
                                    fontsize='small', borderaxespad=0)

        except:
            log.warning("Unable to build full width spec plot.", exc_info=True)

        if show_skylines:
            try:
                yl, yh = specplot.get_ylim()

                central_w = 3545
                half_width = 10
                rec = plt.Rectangle((central_w - half_width, yl), 2 * half_width, yh - yl, fill=True, lw=1,
                                    color='gray', alpha=0.5, zorder=1)
                specplot.add_patch(rec)

                central_w = 5462
                half_width = 5
                rec = plt.Rectangle((central_w - half_width, yl), 2 * half_width, yh - yl, fill=True, lw=1,
                                    color='gray', alpha=0.5, zorder=1)
                specplot.add_patch(rec)
            except:
                log.warning("Unable add skylines.", exc_info=True)

        if name is not None:
            try:
                #plt.tight_layout(w_pad=1.1)
                plt.savefig(name+".png", format='png', dpi=300)
            except:
                log.warning("Unable save plot to file.", exc_info=True)


        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300)

        plt.close(fig)
        return buf



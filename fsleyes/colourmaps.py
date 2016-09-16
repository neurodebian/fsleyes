#!/usr/bin/env python
#
# colourmaps.py - Manage colour maps and lookup tables for overlay rendering.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module manages the colour maps and lookup tables available for overlay
rendering in *FSLeyes*.


The :func:`init` function must be called before any colour maps or lookup
tables can be accessed. When :func:`init` is called, it searches in the
``fsleyes/colourmaps/`` and ``fsleyes/luts/`` directories, and attempts to
load all files within which have the suffix ``.cmap`` or ``.lut``
respectively.

.. note:: Only the :func:`scanColourMaps` and :func:`scanLookupTables`
          functions may be called before :func:`init` is called.


-----------
Colour maps
-----------


A ``.cmap`` file defines a colour map which may be used to display a range of
intensity values - see the :attr:`.VolumeOpts.cmap` property for an example. A
``.cmap`` file must contain a list of RGB colours, one per line, with each
colour specified by three space-separated floating point values in the range
``0.0 - 1.0``, for example::


        1.000000 0.260217 0.000000
        0.000000 0.687239 1.000000
        0.738949 0.000000 1.000000


This list of RGB values is used to create a :class:`.ListedColormap` object,
which is then registered with the :mod:`matplotlib.cm` module (using the file
name prefix as the colour map name), and thus made available for rendering
purposes.


If a file named ``order.txt`` exists in the ``fsleyes/colourmaps/`` directory,
it is assumed to contain a list of colour map names, and colour map
identifiers, defining the order in which the colour maps should be displayed
to the user. Any colour maps which are not listed in the ``order.txt`` file
will be appended to the end of the list, and their name will be derived from
the file name.


The following functions are available for managing and accessing colour maps:

.. autosummary::
   :nosignatures:

   scanColourMaps
   getColourMaps
   getColourMap
   getColourMapLabel
   registerColourMap
   installColourMap
   isColourMapRegistered
   isColourMapInstalled


-------------
Lookup tables
-------------


A ``.lut`` file defines a lookup table which may be used to display images
wherein each voxel has a discrete integer label. Each of the possible voxel
values such an image has an associated colour and name. Each line in a
``.lut`` file must specify the label value, RGB colour, and associated name.
The first column (where columns are space-separated) defines the label value,
the second to fourth columns specify the RGB values, and all remaining columns
give the label name. For example::


        1  0.00000 0.93333 0.00000 Frontal Pole
        2  0.62745 0.32157 0.17647 Insular Cortex
        3  1.00000 0.85490 0.72549 Superior Frontal Gyrus


This list of label, colour, and name mappings is used to create a
:class:`LookupTable` instance, which can be used to access the colours and
names associated with each label value.

.. note:: The labels specified in a ``.lut`` file must be in ascending order.


Once created, ``LookupTable`` instances may be modified - labels can be
added/removed, and the name/colour of existing labels can be modified.  The
:func:`.installLookupTable` method will install a new lookup table, or save
any changes made to an existing one.


The following functions are available to access and manage
:class:`LookupTable` instances:

.. autosummary::
   :nosignatures:

   scanLookupTables
   getLookupTables
   registerLookupTable
   installLookupTable
   isLookupTableRegistered
   isLookupTableInstalled


-------------
Miscellaneous
-------------


Some utility functions are also kept in this module, related to calculating
the relationship between a data display range and brightness/contrast scales,
and generating/manipulating colours.:

.. autosummary::
   :nosignatures:

   displayRangeToBricon
   briconToDisplayRange
   applyBricon
   randomColour
   randomBrightColour
   randomDarkColour
"""


import logging
import glob
import bisect
import colorsys
import random
import os.path as op

from collections import OrderedDict

import          six
import numpy as np

import                       props
import                       fsleyes
import fsl.utils.notifier as notifier


log = logging.getLogger(__name__)


def getCmapDir():
    """Returns the directory in which all colour map files are stored."""
    return op.join(fsleyes.assetDir, 'assets', 'colourmaps')


def getLutDir():
    """Returns the directory in which all lookup table files are stored. """
    return op.join(fsleyes.assetDir, 'assets', 'luts')


_cmaps = None
"""An ``OrderedDict`` which contains all registered colour maps as
``{key : _Map}`` mappings.
"""


_luts = None
"""An ``OrderedDict`` which contains all registered lookup tables as
``{key : _Map}`` mappings.
"""


def scanColourMaps():
    """Scans the colour maps directory, and returns a list containing the
    names of all colour maps contained within. This function may be called
    before :func:`init`.
    """
    cmapFiles = glob.glob(op.join(getCmapDir(), '*cmap'))
    return [op.splitext(op.basename(f))[0] for f in cmapFiles]


def scanLookupTables():
    """Scans the lookup tables directory, and returns a list containing the
    names of all lookup tables contained within. This function may be called
    before :func:`init`.
    """
    lutFiles = glob.glob(op.join(getLutDir(), '*lut'))
    return [op.splitext(op.basename(f))[0] for f in lutFiles] 


def init():
    """This function must be called before any of the other functions in this
    module can be used.

    It initialises the colour map and lookup table registers, loading all
    colour map and lookup table files that exist.
    """

    global _cmaps
    global _luts

    registers = []

    if _cmaps is None:
        _cmaps = OrderedDict()
        registers.append((_cmaps, getCmapDir(), 'cmap'))

    if _luts is None:
        _luts = OrderedDict()
        registers.append((_luts, getLutDir(), 'lut'))

    if len(registers) == 0:
        return

    for register, rdir, suffix in registers:

        # Build up a list of key -> name mappings,
        # from the order.txt file, and any other
        # colour map/lookup table  files in the
        # cmap/lut directory
        allmaps   = OrderedDict()
        orderFile = op.join(rdir, 'order.txt')

        if op.exists(orderFile):
            with open(orderFile, 'rt') as f:
                lines = f.read().split('\n')

                for line in lines:
                    if line.strip() == '':
                        continue
                    
                    # The order.txt file is assumed to
                    # contain one row per cmap/lut,
                    # where the first word is the key
                    # (the cmap/lut file name prefix),
                    # and the remainder of the line is
                    # the cmap/lut name
                    key, name = line.split(' ', 1)

                    allmaps[key.strip()] = name.strip()

        # Search through all cmap/lut files that exist -
        # any which were not specified in order.txt
        # are added to the end of the list, and their
        # name is just set to the file name prefix
        for mapFile in sorted(glob.glob(op.join(rdir, '*.{}'.format(suffix)))):

            name = op.basename(mapFile).split('.')[0]

            if name not in allmaps:
                allmaps[name] = name

        # Now load all of the cmaps/luts
        for key, name in allmaps.items():
            mapFile = op.join(rdir, '{}.{}'.format(key, suffix))

            try:
                kwargs = {'key' : key, 'name' : name}
                
                if   suffix == 'cmap': registerColourMap(  mapFile, **kwargs)
                elif suffix == 'lut':  registerLookupTable(mapFile, **kwargs)
                
                register[key].installed    = True
                register[key].mapObj.saved = True

            except Exception as e:
                log.warn('Error processing custom {} '
                         'file {}: {}'.format(suffix, mapFile, str(e)),
                         exc_info=True)


def registerColourMap(cmapFile,
                      overlayList=None,
                      displayCtx=None,
                      key=None,
                      name=None):
    """Loads RGB data from the given file, and registers
    it as a :mod:`matplotlib` :class:`~matplotlib.colors.ListedColormap`
    instance.

    .. note:: If the ``overlayList`` and ``displayContext`` arguments are
              provided, the ``cmap`` property of all :class:`.VolumeOpts`
              instances are updated to support the new colour map.

    :arg cmapFile:    Name of a file containing RGB values

    :arg overlayList: A :class:`.OverlayList` instance which contains all
                      overlays that are being displayed (can be ``None``).
    
    :arg displayCtx:  A :class:`.DisplayContext` instance describing how
                      the overlays in ``overlayList`` are being displayed.
                      Must be provided if ``overlayList`` is provided.

    :arg key:         Name to give the colour map. If ``None``, defaults
                      to the file name prefix.

    :arg name:        Display name for the colour map. If ``None``, defaults
                      to the ``name``. 
    """

    import matplotlib.cm     as mplcm
    import matplotlib.colors as colors
    
    if key         is None: key         = op.basename(cmapFile).split('.')[0]
    if name        is None: name        = key
    if overlayList is None: overlayList = []

    data = np.loadtxt(cmapFile)
    cmap = colors.ListedColormap(data, key)

    log.debug('Loading and registering custom '
              'colour map: {}'.format(cmapFile))

    mplcm.register_cmap(key, cmap)

    _cmaps[key] = _Map(key, name, cmap, None, False)

    log.debug('Patching DisplayOpts instances and class '
              'to support new colour map {}'.format(key))

    import fsleyes.displaycontext as fsldisplay
    
    # A list of all DisplayOpts colour map properties
    # 
    # TODO Any new DisplayOpts sub-types which have a 
    #      colour map will need to be patched here
    cmapProps = []
    cmapProps.append((fsldisplay.VolumeOpts, 'cmap'))
    cmapProps.append((fsldisplay.VolumeOpts, 'negativeCmap'))
    cmapProps.append((fsldisplay.VectorOpts, 'cmap'))

    # Update the colour map properties
    # for any existing instances 
    for overlay in overlayList:
        opts = displayCtx.getOpts(overlay)

        for cls, propName in cmapProps:
            if isinstance(opts, cls):
                prop = opts.getProp(propName)
                prop.addColourMap(key, opts)

    # and for all future overlays
    for cls, propName in cmapProps:
        
        prop = cls.getProp(propName)
        prop.addColourMap(key)
                

def registerLookupTable(lut,
                        overlayList=None,
                        displayCtx=None,
                        key=None,
                        name=None):
    """Registers the given ``LookupTable`` instance (if ``lut`` is a string,
    it is assumed to be the name of a ``.lut`` file, which is loaded).

    .. note:: If the ``overlayList`` and ``displayContext`` arguments are
              provided, the ``lut`` property of all :class:`.LabelOpts`
              instances are updated to support the new lookup table.

    :arg lut:         A :class:`LookupTable` instance, or the name of a
                      ``.lut`` file.

    :arg overlayList: A :class:`.OverlayList` instance which contains all
                      overlays that are being displayed (can be ``None``).
    
    :arg displayCtx:  A :class:`.DisplayContext` instance describing how
                      the overlays in ``overlayList`` are being displayed.
                      Must be provided if ``overlayList`` is provided. 
    
    :arg key:         Name to give the lookup table. If ``None``, defaults
                      to the file name prefix.
    
    :arg name:        Display name for the lookup table. If ``None``, defaults
                      to the ``name``. 
    """

    if isinstance(lut, six.string_types): lutFile = lut
    else:                                 lutFile = None

    if overlayList is None:
        overlayList = []

    # lut may be either a file name
    # or a LookupTable instance
    if lutFile is not None:

        if key  is None: key  = op.basename(lutFile).split('.')[0]
        if name is None: name = key

        log.debug('Loading and registering custom '
                  'lookup table: {}'.format(lutFile)) 
        
        lut = LookupTable(key, name, lutFile)
    else:
        if key  is None: key  = lut.name
        if name is None: name = key

        lut.key  = key
        lut.name = name

    # Even though the lut may have been loaded from
    # a file, it has not necessarily been installed
    lut.saved = False
            
    _luts[key] = _Map(key, name, lut, None, False)

    log.debug('Patching LabelOpts classes to support '
              'new LookupTable {}'.format(key))

    import fsleyes.displaycontext as fsldisplay

    # Update the lut property for
    # any existing label overlays
    for overlay in overlayList:
        opts = displayCtx.getOpts(overlay)

        if not isinstance(opts, fsldisplay.LabelOpts):
            continue

        lutChoice = opts.getProp('lut')
        lutChoice.addChoice(lut,
                            alternate=list(set((lut.name, key))),
                            instance=opts)

    # and for any future label overlays
    fsldisplay.LabelOpts.lut.addChoice(
        lut,
        alternate=list(set((lut.name, key))))
    
    return lut


def getLookupTables():
    """Returns a list containing all available lookup tables."""
    return [_luts[lutName].mapObj for lutName in _luts.keys()]


def getLookupTable(lutName):
    """Returns the :class:`LookupTable` instance of the specified name."""
    return _caseInsensitiveLookup(_luts, lutName).mapObj

        
def getColourMaps():
    """Returns a list containing the names of all available colour maps."""
    return list(_cmaps.keys())


def getColourMap(cmapName):
    """Returns the colour map instance of the specified name."""
    return _caseInsensitiveLookup(_cmaps, cmapName).mapObj


def getColourMapLabel(cmapName):
    """Returns a label/display name for the specified colour map. """
    return _caseInsensitiveLookup(_cmaps, cmapName).name


def isColourMapRegistered(cmapName):
    """Returns ``True`` if the specified colourmap is registered, ``False``
    otherwise. 
    """ 
    return cmapName in _cmaps


def isLookupTableRegistered(lutName):
    """Returns ``True`` if the specified lookup table is registered, ``False``
    otherwise. 
    """ 
    return lutName in _luts


def isColourMapInstalled(cmapName):
    """Returns ``True`` if the specified colourmap is installed, ``False``
    otherwise.  A :exc:`KeyError` is raised if the colourmap is not registered.
    """
    return _cmaps[cmapName].installed


def isLookupTableInstalled(lutName):
    """Returns ``True`` if the specified loolup table is installed, ``False``
    otherwise.  A :exc:`KeyError` is raised if the lookup tabler is not
    registered.
    """
    return _luts[lutName].installed 


def installColourMap(cmapName):
    """Attempts to install a previously registered colourmap into the
    ``fsleyes/colourmaps`` directory.
    """

    # keyerror if not registered
    cmap = _cmaps[cmapName]

    if cmap.mapFile is not None:
        destFile = cmap.mapFile
    else:
        destFile = op.join(
            getCmapDir(),
            '{}.cmap'.format(cmapName.lower().replace(' ', '_')))

    log.debug('Installing colour map {} to {}'.format(cmapName, destFile))

    # I think the colors attribute is only
    # available on ListedColormap instances ...
    data = cmap.mapObj.colors
    np.savetxt(destFile, data, '%0.6f')
    
    cmap.installed = True


def installLookupTable(lutName):
    """Attempts to install/save a previously registered lookup table into
    the ``fsleyes/luts`` directory.
    """
    
    # keyerror if not registered
    lut = _luts[lutName]

    if lut.mapFile is not None:
        destFile = lut.mapFile
    else:
        destFile = op.join(
            getLutDir(),
            '{}.lut'.format(lutName.lower().replace(' ', '_')))

    log.debug('Installing lookup table {} to {}'.format(lutName, destFile))

    lut.mapObj.save(destFile)

    lut.mapFile   = destFile
    lut.installed = True
    

###############
# Miscellaneous
###############


def _briconToScaleOffset(brightness, contrast, drange):
    """Used by the :func:`briconToDisplayRange` and the :func:`applyBricon`
    functions.

    Calculates a scale and offset which can be used to transform a display
    range of the given size so that the given brightness/contrast settings
    are applied.

    :arg brightness: Brightness, between 0.0 and 1.0.
    :arg contrast:   Contrast, between 0.0 and 1.0.
    :arg drange:     Data range.
    """
    
    # The brightness is applied as a linear offset,
    # with 0.5 equivalent to an offset of 0.0.                
    offset = (brightness * 2 - 1) * drange

    # If the contrast lies between 0.0 and 0.5, it is
    # applied to the colour as a linear scaling factor.
    if contrast <= 0.5:
        scale = contrast * 2

    # If the contrast lies between 0.5 and 1, it
    # is applied as an exponential scaling factor,
    # so lower values (closer to 0.5) have less of
    # an effect than higher values (closer to 1.0).
    else:
        scale = 20 * contrast ** 4 - 0.25

    return scale, offset
    

def briconToDisplayRange(dataRange, brightness, contrast):
    """Converts the given brightness/contrast values to a display range,
    given the data range.

    :arg dataRange:  The full range of the data being displayed, a
                     (min, max) tuple.
    
    :arg brightness: A brightness value between 0 and 1.
    
    :arg contrast:   A contrast value between 0 and 1.
    """

    # Turn the given bricon values into
    # values between 1 and 0 (inverted)
    brightness = 1.0 - brightness
    contrast   = 1.0 - contrast

    dmin, dmax = dataRange
    drange     = dmax - dmin
    dmid       = dmin + 0.5 * drange

    scale, offset = _briconToScaleOffset(brightness, contrast, drange)

    # Calculate the new display range, keeping it
    # centered in the middle of the data range
    # (but offset according to the brightness)
    dlo = (dmid + offset) - 0.5 * drange * scale 
    dhi = (dmid + offset) + 0.5 * drange * scale

    return dlo, dhi


def displayRangeToBricon(dataRange, displayRange):
    """Converts the given brightness/contrast values to a display range,
    given the data range.

    :arg dataRange:    The full range of the data being displayed, a
                       (min, max) tuple.
    
    :arg displayRange: A (min, max) tuple containing the display range.
    """    

    dmin, dmax = dataRange
    dlo,  dhi  = displayRange
    drange     = dmax - dmin
    dmid       = dmin + 0.5 * drange

    if drange == 0:
        return 0, 0

    # These are inversions of the equations in
    # the _briconToScaleOffset function above,
    # which calculate the display ranges from
    # the bricon offset/scale
    offset = dlo + 0.5 * (dhi - dlo) - dmid
    scale  = (dhi - dlo) / drange

    brightness = 0.5 * (offset / drange + 1)

    if scale <= 1: contrast = scale / 2.0
    else:          contrast = ((scale + 0.25)  / 20.0) ** 0.25

    brightness = 1.0 - brightness
    contrast   = 1.0 - contrast

    return brightness, contrast


def applyBricon(rgb, brightness, contrast):
    """Applies the given ``brightness`` and ``contrast`` levels to
    the given ``rgb`` colour(s).

    Passing in ``0.5`` for both the ``brightness``  and ``contrast`` will
    result in the colour being returned unchanged.

    :arg rgb:        A sequence of three or four floating point numbers in 
                     the range ``[0, 1]`` specifying an RGB(A) value, or a
                     :mod:`numpy` array of shape ``(n, 3)`` or ``(n, 4)``
                     specifying ``n`` colours. If alpha values are passed
                     in, they are returned unchanged.

    :arg brightness: A brightness level in the range ``[0, 1]``.

    :arg contrast:   A contrast level in the range ``[0, 1]``.
    """
    rgb       = np.array(rgb)
    oneColour = len(rgb.shape) == 1
    rgb       = rgb.reshape(-1, rgb.shape[-1])

    scale, offset = _briconToScaleOffset(brightness, contrast, 1)

    # The contrast factor scales the existing colour
    # range, but keeps the new range centred at 0.5.
    rgb[:, :3] += offset
  
    rgb[:, :3]  = np.clip(rgb[:, :3], 0.0, 1.0)
    rgb[:, :3]  = (rgb[:, :3] - 0.5) * scale + 0.5
    
    rgb[:, :3]  = np.clip(rgb[:, :3], 0.0, 1.0)

    if oneColour: return rgb[0]
    else:         return rgb


def randomColour():
    """Generates a random RGB colour. """
    values = [randomColour.random.random() for i in range(3)]
    return np.array(values)

# The randomColour function uses a generator
# with a fixed seed for reproducibility
randomColour.random = random.Random(x=1)


def randomBrightColour():
    """Generates a random saturated RGB colour. """
    colour                  = randomColour()
    colour[colour.argmax()] = 1
    colour[colour.argmin()] = 0

    randomColour.random.shuffle(colour)

    return colour


def randomDarkColour():
    """Generates a random saturated and darkened RGB colour."""

    return applyBricon(randomBrightColour(), 0.35, 0.5)


def complementaryColour(rgb):
    """Generate a colour which can be used as a complement/opposite
    to the given colour.

    If the given ``rgb`` sequence contains four values, the fourth
    value (e.g. alpha) is returned unchanged.
    """

    if len(rgb) >= 4:
        a   = rgb[3:]
        rgb = rgb[:3]
    else:
        a   = []

    h, l, s = colorsys.rgb_to_hls(*rgb)

    # My ad-hoc complementary colour calculation:
    # create a new colour with the opposite hue
    # and opposite lightness, but the same saturation.
    nh = 1.0 - h
    nl = 1.0 - l
    ns = s

    # If the two colours have similar lightness
    # (according to some arbitrary threshold),
    # force the new one to have a different
    # lightness
    if abs(nl - l) < 0.3:
        if l > 0.5: nl = 0.0
        else:       nl = 1.0

    nr, ng, nb = colorsys.hls_to_rgb(nh, nl, ns)

    return [nr, ng, nb] + a


def _caseInsensitiveLookup(d, k, default=None):
    """Performs a case-insensitive lookup on the dictionary ``d``,
    with the key ``k``.

    This function is used to allow case-insensitive retrieval of colour maps
    and lookup tables.
    """

    v = d.get(k, None)

    if v is not None:
        return v

    keys  = d.keys()
    lKeys = map(str.lower, keys)

    try:
        idx = lKeys.index(k.lower())
    except:
        if default is not None: return default
        else:                   raise  KeyError(k)

    return d[keys[idx]]


class _Map(object):
    """A little class for storing details on registered colour maps and lookup
    tables. This class is only used internally.
    """

    
    def __init__(self, key, name, mapObj, mapFile, installed):
        """Create a ``_Map``.
        
        :arg key:         The identifier name of the colour map/lookup table,
                          which must be passed to the :func:`getColourMap` and
                          :func:`getLookupTable` functions to look up this
                          map object.

        :arg name:        The display name of the colour map/lookup table.

        :arg mapObj:      The colourmap/lut object, either a
                          :class:`matplotlib.colors..Colormap`, or a
                          :class:`LookupTable` instance.

        :arg mapFile:     The file from which this map was loaded,
                          or ``None`` if this cmap/lookup table only
                          exists in memory, or is a built in :mod:`matplotlib`
                          colourmap.

        :arg installed: ``True`` if this is a built in :mod:`matplotlib`
                          colourmap or is installed in the
                          ``fsleyes/colourmaps/`` or ``fsleyes/luts/``
                          directory, ``False`` otherwise.
        """
        self.key       = key
        self.name      = name
        self.mapObj    = mapObj
        self.mapFile   = mapFile
        self.installed = installed

        
    def __str__(self):
        """Returns a string representation of this ``_Map``. """
        if self.mapFile is not None: return self.mapFile
        else:                        return self.key

        
    def __repr__(self):
        """Returns a string representation of this ``_Map``. """
        return self.__str__()


class LutLabel(props.HasProperties):
    """This class represents a mapping from a value to a colour and name.
    ``LutLabel`` instances are created and managed by :class:`LookupTable`
    instances.

    Listeners may be registered on the :attr:`name`, :attr:`colour`, and
    :attr:`enabled` properties to be notified when they change.
    """

    name = props.String(default='Label')
    """The display name for this label. Internally (for comparison), the
    :meth:`internalName` is used, which is simply this name, converted to
    lower case.
    """

    colour = props.Colour(default=(0, 0, 0))
    """The colour for this label. """


    enabled = props.Boolean(default=True)
    """Whether this label is currently enabled or disabled. """

    
    def __init__(self,
                 value,
                 name=None,
                 colour=None,
                 enabled=None):
        """Create a ``LutLabel``.

        :arg value:   The label value.
        :arg name:    The label name.
        :arg colour:  The label colour.
        :arg enabled: Whether the label is enabled/disabled.
        """

        if value is None:
            raise ValueError('LutLabel value cannot be None')

        if name is None:
            name = LutLabel.getConstraint('name', 'default')

        if colour is None:
            colour  = LutLabel.getConstraint('colour', 'default')

        if enabled is None:
            enabled = LutLabel.getConstraint('enabled', 'default')
        
        self.__value = value
        self.name    = name
        self.colour  = colour
        self.enabled = enabled


    @property
    def value(self):
        """Returns the value of this ``LutLabel``. """ 
        return self.__value


    @property
    def internalName(self):
        """Returns the *internal* name of this ``LutLabel``, which is just
        its :attr:`name`, converted to lower-case. This is used by 
        :meth:`__eq__` and :meth:`__hash__`, and by the
        :class:`LookupTable` class.
        """
        return self.name.lower()


    def __eq__(self, other):
        """Equality operator - returns ``True`` if this ``LutLabel``
        has the same  value as the given one.
        """
        
        return self.value == other.value


    def __lt__(self, other):
        """Less-than operator - compares two ``LutLabel`` instances
        based on their value.
        """ 
        return self.value < other.value

    
    def __hash__(self):
        """The hash of a ``LutLabel`` is a combination of its
        value, name, and colour, but not its enabled state.
        """
        return (hash(self.value)        ^
                hash(self.internalName) ^
                hash(self.colour))

    
    def __str__(self):
        """Returns a string representation of this ``LutLabel``."""
        return '{}: {} / {} ({})'.format(self.value,
                                         self.internalName,
                                         self.colour,
                                         self.enabled)


    def __repr__(self):
        """Returns a string representation of this ``LutLabel``."""
        return self.__str__()
    

class LookupTable(notifier.Notifier):
    """A ``LookupTable`` encapsulates a list of label values and associated
    colours and names, defining a lookup table to be used for colouring label
    images.


    A label value typically corresponds to an anatomical region (as in
    e.g. atlas images), or a classification (as in e.g. white/grey matter/csf
    segmentations).


    The label values, and their associated names/colours, in a ``LookupTable``
    are stored in ``LutLabel`` instances, ordered by their value in ascending
    order. These are accessible by label value via the :meth:`get` method, by
    index, by directly indexing the ``LookupTable`` instance, or by name, via
    the :meth:`getByName` method.  New label values can be added via the
    :meth:`insert` and :meth:`new` methods. Label values can be removed via
    the meth:`delete` method.


    *Notifications*


    The ``LookupTable`` class implements the :class:`.Notifier` interface.
    If you need to be notified when a ``LookupTable`` changes, you may
    register to be notified on the following topics:


    ==========  ====================================================
    *Topic*     *Meaning*
    ``label``   The properties of a :class:`.LutLabel` have changed.
    ``saved``   The saved state of this ``LookupTable`` has changed.
    ``added``   A new ``LutLabel`` has been added.
    ``removed`` A ``LutLabel`` has been removed.
    =========== ====================================================
    """

    
    def __init__(self, key, name, lutFile=None):
        """Create a ``LookupTable``.

        :arg key:     The identifier for this ``LookupTable``.

        :arg name:    The display name for this ``LookupTable``.

        :arg lutFile: A file to load lookup table label values, names, and
                      colours from. If ``None``, this ``LookupTable`` will
                      be empty - labels can be added with the :meth:`new` or
                      :meth:`insert` methods.
        """

        self.key      = key
        self.name     = name
        self.__labels = []
        self.__saved  = False

        self.__name   = 'LookupTable({})_{}'.format(self.name, id(self))

        if lutFile is not None:
            self.__load(lutFile)


    def __str__(self):
        """Returns the name of this ``LookupTable``. """
        return self.name

    
    def __repr__(self):
        """Returns the name of this ``LookupTable``. """
        return self.name 
        

    def __len__(self):
        """Returns the number of labels in this ``LookupTable``. """
        return len(self.__labels)


    def __getitem__(self, i):
        """Access the ``LutLabel`` at index ``i``. Use the :meth:`get` method
        to determine the index of a ``LutLabel`` from its value.
        """
        return self.__labels[i]


    def max(self):
        """Returns the maximum current label value in this ``LookupTable``. """
        
        if len(self.__labels) == 0: return 0
        else:                       return self.__labels[-1].value


    @property
    def saved(self):
        """Returns ``True`` if this ``LookupTable`` is registered and saved,
        ``False`` if it is not registered, or has been modified.
        """
        return self.__saved


    @saved.setter
    def saved(self, val):
        """Change the saved state of this ``LookupTable``, and trigger
        notification on the ``saved`` topic. This property should not
        be set outside of this module.
        """
        self.__saved = val
        self.notify(topic='saved')


    def index(self, value):
        """Returns the index in this ``LookupTable`` of the ``LutLabel`` with
        the specified value. Raises a :exc:`ValueError` if no ``LutLabel``
        with this value is present.
        """
        return self.__labels.index(LutLabel(value))


    def get(self, value):
        """Returns the :class:`LutLabel` instance associated with the given
        ``value``, or ``None`` if there is no label.
        """
        try:               return self.__labels[self.index(value)]
        except ValueError: return None


    def getByName(self, name):
        """Returns the :class:`LutLabel` instance associated with the given
        ``name``, or ``None`` if there is no ``LutLabel``. The name comparison
        is case-insensitive.
        """
        name = name.lower()
        
        for i, ll in enumerate(self.__labels):
            if ll.internalName == name:
                return ll
            
        return None


    def new(self, name=None, colour=None, enabled=None):
        """Add a new :class:`LutLabel` with value ``max() + 1``, and add it
        to this ``LookupTable``.
        """
        return self.insert(self.max() + 1, name, colour, enabled)


    def insert(self, value, name=None, colour=None, enabled=None):
        """Create a new :class:`LutLabel` associated with the given
        ``value`` and insert it into this ``LookupTable``. Internally, the
        labels are stored in ascending (by value) order.

        :returns: The newly created ``LutLabel`` instance.
        """
        if not isinstance(value, six.integer_types) or \
           value < 0 or value > 65535:
            raise ValueError('Lookup table values must be '
                             '16 bit unsigned integers.')

        if self.get(value) is not None:
            raise ValueError('Value {} is already in '
                             'lookup table'.format(value))

        label = LutLabel(value, name, colour, enabled)
        label.addGlobalListener(self.__name, self.__labelChanged)

        bisect.insort(self.__labels, label)

        self.saved = False
        self.notify(topic='added', value=label)

        return label


    def delete(self, value):
        """Removes the label with the given value from the lookup table.

        Raises a :exc:`ValueError` if no label with the given value is
        present.
        """

        idx   = self.index(value)
        label = self.__labels.pop(idx)

        label.removeGlobalListener(self.__name)
        
        self.notify(topic='removed', value=label)
        self.saved = False


    def save(self, lutFile):
        """Saves this ``LookupTable`` instance to the specified ``lutFile``.
        """

        with open(lutFile, 'wt') as f:
            for label in self:
                value  = label.value
                colour = label.colour
                name   = label.name

                tkns   = [value, colour[0], colour[1], colour[2], name]
                line   = ' '.join(map(str, tkns))

                f.write('{}\n'.format(line))

        self.saved = True

        
    def __load(self, lutFile):
        """Called by :meth:`__init__`. Loads a ``LookupTable`` specification
        from the given file.
        """

        # Calling insert() to add new labels is very
        # slow, because the labels are inserted in
        # ascending order. But because we require
        # .lut files to be sorted, we can create the
        # lookup table much faster.
        def parseLabel(line):
            tkns = line.split()

            label = int(     tkns[0])
            r     = float(   tkns[1])
            g     = float(   tkns[2])
            b     = float(   tkns[3])
            lName = ' '.join(tkns[4:])

            return LutLabel(label, lName, (r, g, b), True)

        with open(lutFile, 'rt') as f:

            last   = 0
            lines  = [l.strip() for l in f.readlines()]
            labels = []

            for line in lines:

                if line == '':
                    continue

                label = parseLabel(line)
                lval  = label.value

                if lval <= last:
                    raise ValueError('{} file is not in ascending '
                                     'order!'.format(lutFile))

                labels.append(label)
                last = lval

            self.__labels = labels
            self.saved    = True

            for label in labels:
                label.addGlobalListener(self.__name, self.__labelChanged)


    def __labelChanged(self, label, *a, **kwa):
        """Called when the properties of any ``LutLabel`` change. Triggers
        notification on the ``label`` topic.
        """
        self.saved = False
        self.notify(topic='label', value=label)

#!/usr/bin/env python
#
# overlaydisplaywidgets.py - Contents of the OverlayDisplayPanel.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module is used by the :class:`.OverlayDisplayPanel`. It contains
definitions of all the settings that are displayed on the
``OverlayDisplayPanel`` for each overlay type.

It also contains functions which create customised widgets, for scenarios
where a widget does not directly map to a :class:`.Display` or
:class:`.DisplayOpts` property.


``_initPropertyList_[DisplayOptsType]``
``_init3DPropertyList_[DisplayOptsType]``
``_initWidgetSpec_[DisplayOptsType]``
``_init3DWidgetSpec_[DisplayOptsType]``
"""


import os.path as op
import            sys
import            copy
import            functools

import            wx

import fsl.utils.async                    as async
from   fsl.utils.platform import platform as fslplatform
import fsleyes_props                      as props
import fsleyes_widgets.utils.typedict     as td
import fsleyes.strings                    as strings
import fsleyes.colourmaps                 as fslcm
import fsleyes.actions.loadcolourmap      as loadcmap
import fsleyes.actions.loadvertexdata     as loadvdata


_PROPERTIES      = td.TypeDict()
_3D_PROPERTIES   = td.TypeDict()
_WIDGET_SPECS    = td.TypeDict()
_3D_WIDGET_SPECS = td.TypeDict()




def _merge_dicts(d1, d2):
    d3 = d1.copy()
    d3.update(d2)
    return d3


def getPropertyList(target, threedee=False):

    plist = _getThing(target, '_initPropertyList_', _PROPERTIES, threedee)

    if plist is None:
        return []

    return functools.reduce(lambda a, b: a + b, plist)


def get3DPropertyList(target):

    plist = _getThing(target, '_init3DPropertyList_', _3D_PROPERTIES)

    if plist is None:
        return []

    return functools.reduce(lambda a, b: a + b, plist)


def getWidgetSpecs(target, threedee=False):

    sdicts = _getThing(target, '_initWidgetSpec_', _WIDGET_SPECS, threedee)

    if sdicts is None:
        return {}

    return functools.reduce(_merge_dicts, sdicts)


def get3DWidgetSpecs(target):

    sdicts = _getThing(target, '_init3DWidgetSpec_', _3D_WIDGET_SPECS)

    if sdicts is None:
        return {}

    return functools.reduce(_merge_dicts, sdicts)


def _getThing(target, prefix, thingDict, *args, **kwargs):

    def _makeKey(t):
        return (t, str(args), str(kwargs))

    tkey = _makeKey(target)

    if thingDict.get(tkey, None, exact=True) is None:

        keys, funcs = _getInitFuncs(prefix, target)

        for key, func in zip(keys, funcs):
            key = _makeKey(key)
            thingDict[key] = func(*args, **kwargs)

    return thingDict.get(tkey, None, allhits=True)


def _getInitFuncs(prefix, target):

    if isinstance(target, type): ttype = target
    else:                        ttype = type(target)

    key   = ttype.__name__
    bases = ttype.__bases__

    thismod  = sys.modules[__name__]
    initFunc = '{}{}'.format(prefix, key)
    initFunc = getattr(thismod, initFunc, None)

    if initFunc is None:
        return [], []

    keys      = [key]
    initFuncs = [initFunc]

    for base in bases:
        bkeys, bfuncs = _getInitFuncs(prefix, base)

        keys     .extend(bkeys)
        initFuncs.extend(bfuncs)

    return keys, initFuncs


def _initPropertyList_Display(threedee):
    return ['name',
            'overlayType',
            'enabled',
            'alpha',
            'brightness',
            'contrast']


def _initPropertyList_VolumeOpts(threedee):
    return ['volume',
            'interpolation',
            'custom_cmap',
            'cmapResolution',
            'interpolateCmaps',
            'invert',
            'invertClipping',
            'linkLowRanges',
            'linkHighRanges',
            'displayRange',
            'clippingRange',
            'clipImage',
            'custom_overrideDataRange']


def _init3DPropertyList_VolumeOpts():
    return ['blendFactor',
            'resolution',
            'numSteps',
            'dithering',
            'custom_clipPlanes']


def _initPropertyList_MaskOpts(threedee):
    return ['volume',
            'colour',
            'invert',
            'threshold']


def _initPropertyList_VectorOpts(threedee):
    return ['colourImage',
            'modulateImage',
            'clipImage',
            'cmap',
            'clippingRange',
            'modulateRange',
            'xColour',
            'yColour',
            'zColour',
            'suppressX',
            'suppressY',
            'suppressZ',
            'suppressMode']


def _initPropertyList_RGBVectorOpts(threedee):
    return ['interpolation']


def _initPropertyList_LineVectorOpts(threedee):
    return ['directed',
            'unitLength',
            'orientFlip',
            'lineWidth',
            'lengthScale']


def _initPropertyList_TensorOpts(threedee):
    return ['lighting',
            'orientFlip',
            'tensorResolution',
            'tensorScale']


def _initPropertyList_MeshOpts(threedee):
    plist = ['refImage',
             'coordSpace',
             'outline',
             'outlineWidth',
             'colour',
             'custom_vertexData',
             'vertexDataIndex',
             'custom_lut',
             'custom_cmap',
             'cmapResolution',
             'interpolateCmaps',
             'invert',
             'invertClipping',
             'discardClipped',
             'linkLowRanges',
             'linkHighRanges',
             'displayRange',
             'clippingRange']

    # Remove outline
    # options for 3D
    if threedee:
        plist.pop(3)
        plist.pop(2)

    return plist


def _init3DPropertyList_MeshOpts():
    return ['wireframe']


def _initPropertyList_GiftiOpts(threedee):
    return []


def _init3DPropertyList_GiftiOpts():
    return []


def _initPropertyList_LabelOpts(threedee):
    return ['lut',
            'outline',
            'outlineWidth',
            'volume']


def _initPropertyList_SHOpts(threedee):
    return ['shResolution',
            'shOrder',
            'orientFlip',
            'lighting',
            'size',
            'radiusThreshold',
            'colourMode']


def _initWidgetSpec_Display(threedee):
    return {
        'name'        : props.Widget('name'),
        'overlayType' : props.Widget(
            'overlayType',
            labels=strings.choices['Display.overlayType']),
        'enabled'     : props.Widget('enabled'),
        'alpha'       : props.Widget('alpha',      showLimits=False),
        'brightness'  : props.Widget('brightness', showLimits=False),
        'contrast'    : props.Widget('contrast',   showLimits=False),
    }


def _initWidgetSpec_ColourMapOpts(threedee):
    return {
        'custom_cmap'              : _ColourMapOpts_ColourMapWidget,
        'custom_overrideDataRange' : _VolumeOpts_OverrideDataRangeWidget,
        'cmap'              : props.Widget(
            'cmap',
            labels=fslcm.getColourMapLabel),
        'useNegativeCmap' : props.Widget('useNegativeCmap'),
        'negativeCmap'    : props.Widget(
            'negativeCmap',
            labels=fslcm.getColourMapLabel,
            dependencies=['useNegativeCmap'],
            enabledWhen=lambda i, unc : unc),
        'cmapResolution'  : props.Widget(
            'cmapResolution',
            slider=True,
            spin=True,
            showLimits=False),
        'interpolateCmaps' : props.Widget('interpolateCmaps'),
        'invert'           : props.Widget('invert'),
        'invertClipping'   : props.Widget('invertClipping'),
        'linkLowRanges'    : props.Widget('linkLowRanges'),
        'linkHighRanges'   : props.Widget('linkHighRanges'),
        'displayRange'     : props.Widget(
            'displayRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['ColourMapOpts.displayRange.min'],
                    strings.choices['ColourMapOpts.displayRange.max']]),
        'clippingRange'  : props.Widget(
            'clippingRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['ColourMapOpts.displayRange.min'],
                    strings.choices['ColourMapOpts.displayRange.max']]),
    }


def _initWidgetSpec_VolumeOpts(threedee):

    def imageName(img):
        if img is None: return 'None'
        else:           return img.name

    return {
        'volume'         : props.Widget(
            'volume',
            showLimits=False,
            enabledWhen=lambda o: o.overlay.is4DImage()),
        'interpolation'  : props.Widget(
            'interpolation',
            labels=strings.choices['VolumeOpts.interpolation']),
        'clipImage'      : props.Widget(
            'clipImage',
            labels=imageName),
        'custom_overrideDataRange' : _VolumeOpts_OverrideDataRangeWidget,
        'enableOverrideDataRange'  : props.Widget(
            'enableOverrideDataRange'),
        'overrideDataRange' : props.Widget(
            'overrideDataRange',
            showLimits=False,
            spin=True,
            slider=False,
            dependencies=['enableOverrideDataRange'],
            enabledWhen=lambda vo, en: en),
    }


def _init3DWidgetSpec_VolumeOpts():

    return {
        'dithering'         : props.Widget('dithering',
                                           showLimits=False),
        'numSteps'          : props.Widget('numSteps',
                                           showLimits=False),
        'blendFactor'       : props.Widget('blendFactor',
                                           showLimits=False),
        'resolution'        : props.Widget('resolution',
                                           showLimits=False),
        'numClipPlanes'     : props.Widget('numClipPlanes',
                                           slider=False,
                                           showLimits=False),
        'showClipPlanes'    : props.Widget('showClipPlanes'),
        'clipPosition'      : props.Widget('clipPosition',
                                           showLimits=False),
        'clipAzimuth'       : props.Widget('clipAzimuth',
                                           showLimits=False),
        'clipInclination'   : props.Widget('clipInclination',
                                           showLimits=False),
        'custom_clipPlanes' : _VolumeOpts_3DClipPlanes,
    }


def _initWidgetSpec_MaskOpts(threedee):
    return {
        'volume'     : props.Widget(
            'volume',
            showLimits=False,
            enabledWhen=lambda o: o.overlay.is4DImage()),
        'colour'     : props.Widget('colour'),
        'invert'     : props.Widget('invert'),
        'threshold'  : props.Widget('threshold', showLimits=False),
    }


def _initWidgetSpec_LabelOpts(threedee):
    return {
        'lut'          : props.Widget('lut', labels=lambda l: l.name),
        'outline'      : props.Widget('outline'),
        'outlineWidth' : props.Widget('outlineWidth', showLimits=False),
        'volume'       : props.Widget(
            'volume',
            showLimits=False,
            enabledWhen=lambda o: o.overlay.is4DImage()),
    }


def _initWidgetSpec_VectorOpts(threedee):
    def imageName(img):
        if img is None: return 'None'
        else:           return img.name

    return {
        'colourImage'   : props.Widget(
            'colourImage',
            labels=imageName),
        'modulateImage' : props.Widget(
            'modulateImage',
            labels=imageName,
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'clipImage'     : props.Widget('clipImage', labels=imageName),
        'cmap'          : props.Widget(
            'cmap',
            labels=fslcm.getColourMapLabel,
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is not None),
        'clippingRange' : props.Widget(
            'clippingRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['VectorOpts.clippingRange.min'],
                    strings.choices['VectorOpts.clippingRange.max']],
            dependencies=['clipImage'],
            enabledWhen=lambda o, ci: ci is not None),
        'modulateRange' : props.Widget(
            'modulateRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['VectorOpts.modulateRange.min'],
                    strings.choices['VectorOpts.modulateRange.max']],
            dependencies=['colourImage', 'modulateImage'],
            enabledWhen=lambda o, ci, mi: ci is None and mi is not None),
        'xColour'       : props.Widget(
            'xColour',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'yColour'       : props.Widget(
            'yColour',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'zColour'       : props.Widget(
            'zColour',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'suppressX'     : props.Widget(
            'suppressX',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'suppressY'     : props.Widget(
            'suppressY',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'suppressZ'     : props.Widget(
            'suppressZ',
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'suppressMode'  : props.Widget(
            'suppressMode',
            dependencies=['colourImage'],
            labels=strings.choices['VectorOpts.suppressMode'],
            enabledWhen=lambda o, ci: ci is None),
    }


def _initWidgetSpec_RGBVectorOpts(threedee):
    return {
        'interpolation' : props.Widget(
            'interpolation',
            labels=strings.choices['VolumeOpts.interpolation'])
    }


def _initWidgetSpec_LineVectorOpts(threedee):
    return {
        'directed'    : props.Widget('directed'),
        'unitLength'  : props.Widget('unitLength'),
        'orientFlip'  : props.Widget('orientFlip'),
        'lineWidth'   : props.Widget('lineWidth',   showLimits=False),
        'lengthScale' : props.Widget('lengthScale', showLimits=False),
    }


def _initWidgetSpec_TensorOpts(threedee):
    return {
        'lighting'         : props.Widget('lighting'),
        'orientFlip'       : props.Widget('orientFlip'),
        'tensorResolution' : props.Widget(
            'tensorResolution',
            showLimits=False,
            spin=False,
            labels=[strings.choices['TensorOpts.tensorResolution.min'],
                    strings.choices['TensorOpts.tensorResolution.max']]),
        'tensorScale'      : props.Widget(
            'tensorScale',
            showLimits=False,
            spin=False),
    }

def _initWidgetSpec_SHOpts(threedee):
    return {
        'shResolution'    : props.Widget(
            'shResolution',
            spin=False,
            showLimits=False),
        'shOrder'    : props.Widget('shOrder'),
        'orientFlip' : props.Widget('orientFlip'),
        'lighting'   : props.Widget('lighting'),
        'size'       : props.Widget(
            'size',
            spin=False,
            showLimits=False),
        'radiusThreshold' : props.Widget(
            'radiusThreshold',
            spin=False,
            showLimits=False),
        'colourMode'      : props.Widget(
            'colourMode',
            labels=strings.choices['SHOpts.colourMode'],
            dependencies=['colourImage'],
            enabledWhen=lambda o, ci: ci is None),
        'cmap' : props.Widget(
            'cmap',
            labels=fslcm.getColourMapLabel,
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is not None or cm == 'radius'),
        'xColour'         : props.Widget(
            'xColour',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'yColour'         : props.Widget(
            'yColour',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'zColour'         : props.Widget(
            'zColour',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'suppressX'         : props.Widget(
            'suppressX',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'suppressY'         : props.Widget(
            'suppressY',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'suppressZ'         : props.Widget(
            'suppressZ',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
        'suppressMode'         : props.Widget(
            'suppressMode',
            dependencies=['colourImage', 'colourMode'],
            enabledWhen=lambda o, ci, cm: ci is None and cm == 'direction'),
    }



def _initWidgetSpec_MeshOpts(threedee):

    def imageName(img):
        if img is None: return 'None'
        else:           return img.name

    def vertexDataName(vdata):
        if vdata is None: return 'None'
        else:             return op.basename(vdata)

    def colourEnabledWhen(opts, vdata, useLut):
        return (vdata is not None) and (not useLut)

    colourKwargs = {
        'dependencies' : ['vertexData', 'useLut'],
        'enabledWhen'  : colourEnabledWhen
    }

    return {
        'outline'      : props.Widget(
            'outline',
            dependencies=['vertexData'],
            enabledWhen=lambda o, v: v is None),
        'outlineWidth' : props.Widget(
            'outlineWidth',
            showLimits=False,
            dependencies=['outline', 'vertexData'],
            enabledWhen=lambda op, o, v: o or v is not None),
        'refImage'     : props.Widget('refImage', labels=imageName),
        'coordSpace'   : props.Widget(
            'coordSpace',
            enabledWhen=lambda o, ri: ri != 'none',
            labels=strings.choices['MeshOpts.coordSpace'],
            dependencies=['refImage']),
        'colour'       : props.Widget('colour'),
        'custom_vertexData' : _MeshOpts_VertexDataWidget,
        'vertexData'   : props.Widget(
            'vertexData',
            labels=vertexDataName),
        'vertexDataIndex' : props.Widget(
            'vertexDataIndex',
            showLimits=False,
            dependencies=['vertexData'],
            enabledWhen=lambda o, vd: vd is not None),
        'useLut' : props.Widget(
            'useLut',
            dependencies=['vertexData'],
            enabledWhen=lambda o, vd: vd is not None),
        'custom_lut' : _MeshOpts_LutWidget,
        'lut'    : props.Widget(
            'lut',
            labels=lambda l: l.name,
            dependencies=['vertexData'],
            enabledWhen=lambda o, vd: vd is not None),

        # We override the ColourMapOpts definitions
        # for custom enabledWhen behaviour.
        'cmap'           : props.Widget(
            'cmap',
            labels=fslcm.getColourMapLabel,
            **colourKwargs),

        'useNegativeCmap' : props.Widget(
            'useNegativeCmap',
            **colourKwargs),
        'negativeCmap'    : props.Widget(
            'negativeCmap',
            labels=fslcm.getColourMapLabel,
            **colourKwargs),
        'cmapResolution'  : props.Widget(
            'cmapResolution',
            slider=True,
            spin=True,
            showLimits=False,
            **colourKwargs),
        'interpolateCmaps' : props.Widget(
            'interpolateCmaps',
            **colourKwargs),
        'invert'           : props.Widget(
            'invert',
            **colourKwargs),
        'invertClipping'   : props.Widget(
            'invertClipping',
            **colourKwargs),
        'linkLowRanges'    : props.Widget(
            'linkLowRanges',
            **colourKwargs),
        'linkHighRanges' : props.Widget(
            'linkHighRanges',
            **colourKwargs),
        'displayRange'   : props.Widget(
            'displayRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['ColourMapOpts.displayRange.min'],
                    strings.choices['ColourMapOpts.displayRange.max']],
            **colourKwargs),
        'clippingRange'  : props.Widget(
            'clippingRange',
            showLimits=False,
            slider=True,
            labels=[strings.choices['ColourMapOpts.displayRange.min'],
                    strings.choices['ColourMapOpts.displayRange.max']],
            dependencies=['vertexData'],
            enabledWhen=lambda o, vd: vd is not None),
        'discardClipped' : props.Widget(
            'discardClipped',
            **colourKwargs),
    }


def _init3DWidgetSpec_MeshOpts():
    return {
        'wireframe' : props.Widget('wireframe'),
    }


def _initWidgetSpec_GiftiOpts(threedee):
    return {}
def _init3DWidgetSpec_GiftiOpts():
    return {}


def _ColourMapOpts_ColourMapWidget(
        target,
        parent,
        panel,
        overlayList,
        displayCtx,
        threedee):
    """Builds a panel which contains widgets for controlling the
    :attr:`.ColourMapOpts.cmap`, :attr:`.ColourMapOpts.negativeCmap`, and
    :attr:`.ColourMapOpts.useNegativeCmap`.

    :returns: A ``wx.Sizer`` containing all of the widgets, and a list
              containing the extra widgets that were added.
    """

    # Button to load a new
    # colour map from file
    loadAction = loadcmap.LoadColourMapAction(overlayList, displayCtx)

    loadButton = wx.Button(parent)
    loadButton.SetLabel(strings.labels[panel, 'loadCmap'])

    loadAction.bindToWidget(panel, wx.EVT_BUTTON, loadButton)

    cmap       = getWidgetSpecs(target, threedee)['cmap']
    negCmap    = getWidgetSpecs(target, threedee)['negativeCmap']
    useNegCmap = getWidgetSpecs(target, threedee)['useNegativeCmap']

    cmap       = props.buildGUI(parent, target, cmap)
    negCmap    = props.buildGUI(parent, target, negCmap)
    useNegCmap = props.buildGUI(parent, target, useNegCmap)

    useNegCmap.SetLabel(strings.properties[target, 'useNegativeCmap'])

    sizer = wx.FlexGridSizer(2, 2, 0, 0)
    sizer.AddGrowableCol(0)

    sizer.Add(cmap,       flag=wx.EXPAND)
    sizer.Add(loadButton, flag=wx.EXPAND)
    sizer.Add(negCmap,    flag=wx.EXPAND)
    sizer.Add(useNegCmap, flag=wx.EXPAND)

    return sizer, [cmap, negCmap, useNegCmap]


def _VolumeOpts_OverrideDataRangeWidget(
        target,
        parent,
        panel,
        overlayList,
        displayCtx,
        threedee):
    """Builds a panel which contains widgets for enabling and adjusting
    the :attr:`.VolumeOpts.overrideDataRange`.

    :returns: a ``wx.Sizer`` containing all of the widgets.
    """

    # Override data range widget
    enable   = getWidgetSpecs(target, threedee)['enableOverrideDataRange']
    ovrRange = getWidgetSpecs(target, threedee)['overrideDataRange']

    enable   = props.buildGUI(parent, target, enable)
    ovrRange = props.buildGUI(parent, target, ovrRange)

    sizer = wx.BoxSizer(wx.HORIZONTAL)

    sizer.Add(enable,   flag=wx.EXPAND)
    sizer.Add(ovrRange, flag=wx.EXPAND, proportion=1)

    return sizer, [enable, ovrRange]


def _VolumeOpts_3DClipPlanes(
        target,
        parent,
        panel,
        overlayList,
        displayCtx,
        threedee):
    """Generates widget specifications for the ``VolumeOpts`` 3D settings.
    A different number of widgets are shown depending on the value of the
    :attr:`.VolumeOpts.numClipPlanes` setting.
    """

    # Whenever numClipPlanes changes, we
    # need to refresh the clip plane widgets.
    # Easiest way to do this is to tell the
    # OverlayDisplayPanel to re-create the 3D
    # settings section.
    #
    # TODO what is the lifespan of this listener?
    def numClipPlanesChanged(*a):
        if fslplatform.isWidgetAlive(panel) and \
           fslplatform.isWidgetAlive(parent):
            async.idle(panel.updateWidgets, target, '3d')

    name = '{}_{}_VolumeOpts_3DClipPlanes'.format(
        target.name, id(panel))

    target.addListener('numClipPlanes',
                       name,
                       numClipPlanesChanged,
                       overwrite=True,
                       weak=False)

    numPlaneSpec = get3DWidgetSpecs(target)['numClipPlanes']
    showPlanes   = get3DWidgetSpecs(target)['showClipPlanes']
    position     = get3DWidgetSpecs(target)['clipPosition']
    azimuth      = get3DWidgetSpecs(target)['clipAzimuth']
    inclination  = get3DWidgetSpecs(target)['clipInclination']

    numPlanes = target.numClipPlanes

    if numPlanes == 0:
        return [numPlaneSpec, showPlanes], None

    positions    = [copy.deepcopy(position)    for i in range(numPlanes)]
    azimuths     = [copy.deepcopy(azimuth)     for i in range(numPlanes)]
    inclinations = [copy.deepcopy(inclination) for i in range(numPlanes)]

    specs = [numPlaneSpec, showPlanes]

    for i in range(numPlanes):

        positions[i]   .index = i
        azimuths[i]    .index = i
        inclinations[i].index = i

        label = strings.labels[panel, 'clipPlane#'].format(i + 1)
        label = props.Label(label=label)

        specs.extend((label, positions[i], azimuths[i], inclinations[i]))

    return specs, None


def _MeshOpts_VertexDataWidget(
        target,
        parent,
        panel,
        overlayList,
        displayCtx,
        threedee):
    """Builds a panel which contains a widget for controlling the
    :attr:`.MeshOpts.vertexData` property, and also has a button
    which opens a file dialog, allowing the user to select other
    data.
    """

    loadAction = loadvdata.LoadVertexDataAction(overlayList, displayCtx)
    loadButton = wx.Button(parent)
    loadButton.SetLabel(strings.labels[panel, 'loadVertexData'])

    loadAction.bindToWidget(panel, wx.EVT_BUTTON, loadButton)

    sizer = wx.BoxSizer(wx.HORIZONTAL)

    vdata = getWidgetSpecs(target, threedee)['vertexData']
    vdata = props.buildGUI(parent, target, vdata)

    sizer.Add(vdata,      flag=wx.EXPAND, proportion=1)
    sizer.Add(loadButton, flag=wx.EXPAND)

    return sizer, [vdata]


def _MeshOpts_LutWidget(
        target,
        parent,
        panel,
        overlayList,
        displayCtx,
        threedee):
    """Builds a panel which contains the provided :attr:`.MeshOpts.lut`
    widget, and also a widget for :attr:`.MeshOpts.useLut`.
    """

    # enable lut widget
    lut    = getWidgetSpecs(target, threedee)['lut']
    enable = getWidgetSpecs(target, threedee)['useLut']

    lut    = props.buildGUI(parent, target, lut)
    enable = props.buildGUI(parent, target, enable)

    sizer = wx.BoxSizer(wx.HORIZONTAL)

    sizer.Add(enable, flag=wx.EXPAND)
    sizer.Add(lut,    flag=wx.EXPAND, proportion=1)

    return sizer, [enable, lut]
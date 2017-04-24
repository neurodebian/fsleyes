#!/usr/bin/env python
#
# overlayinfopanel.py - The OverlayInfoPanel class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the ``OverlayInfoPanel`` class, a *FSLeyes control*
panel which displays information about the currently selected overlay.
"""


import logging
import collections
import string

import wx

import numpy as np

import fsl.data.image                 as fslimage
import fsl.data.constants             as constants
import fsleyes_widgets.utils.typedict as td

import fsleyes.panel                  as fslpanel
import fsleyes.strings                as strings


USE_HTML2 = False
"""Toggle this flag to switch between the simple wx.html renderer,
and the webkit-backed wx.html2 renderer. Webkit is not necessarily
present on all systems, and there's no neat way to dynamically
test whether wx.html2 will work. So I'm sticking with wx.html for
now.
"""


if USE_HTML2: import wx.html2 as wxhtml
else:         import wx.html  as wxhtml


log = logging.getLogger(__name__)


# The wx.html2.WebView.SetPage method differs from
# the wx.html.HtmlWindow.SetPage method - it requires
# two parameters. Here we're sub-classing the
# HtmlWindow method so that it also accepts two
# parameters, but ignores the second.
#
# The sub-class also forces links to be opened
# in the system browser, as opposed to in the
# same window.
if not USE_HTML2:

    class HtmlWindow(wxhtml.HtmlWindow):

        def __init__(self, *args, **kwargs):
            wxhtml.HtmlWindow.__init__(self, *args, **kwargs)

            self.Bind(wxhtml.EVT_HTML_LINK_CLICKED, self.__onLink)

            # wx.html.HtmlWindow defaults
            # to a slightly bigger font size
            self.SetStandardFonts(self.GetFont().GetPointSize())

        def __onLink(self, ev):
            wx.LaunchDefaultBrowser(ev.GetLinkInfo().GetHref())
            
        def SetPage(self, html, url=None):
            wxhtml.HtmlWindow.SetPage(self, html)


def terminateString(s):
    """Given an ASCII string (or a ``numpy`` array containing one),
    returns that string as a python string, correctly null-terminated,
    and with non-printable characters removed.


    .. note:: This function is used to sanitise some NIFTI header fields.
              The default Python behaviour for converting a sequence of
              bytes to a string is to strip all termination characters
              (bytes with value of ``0x00``) from the end of the
              sequence.

    
              This behaviour does not handle the case where a sequence
              of bytes which did contain a long string is subsequently
              overwritten with a shorter string - the short string will
              be terminated, but that termination character will be
              followed by the remainder of the original string.
    """

    try:    s = str(s).partition(b'\0')[0]
    except: s = str(s)

    return ''.join([c for c in s if c in string.printable])


class OverlayInfoPanel(fslpanel.FSLeyesPanel):
    """An ``OverlayInfoPanel`` is a :class:`.FSLeyesPanel` which displays
    information about the currently selected overlay in a
    ``wx.html.HtmlWindow``. The currently selected overlay is defined by the
    :attr:`.DisplayContext.selectedOverlay` property. An ``OverlayInfoPanel``
    looks something like the following:

    .. image:: images/overlayinfopanel.png
       :scale: 50%
       :align: center

    Slightly different information is shown depending on the overlay type,
    and is generated by the following methods:

    ====================== =============================
    :class:`.Image`        :meth:`__getImageInfo`
    :class:`.FEATImage`    :meth:`__getFEATImageInfo`
    :class:`.MelodicImage` :meth:`__getMelodicImageInfo`
    :class:`.DTIFitTensor` :meth:`__getDTIFitTensorInfo`
    :class:`.TriangleMesh` :meth:`__getTriangleMeshInfo`
    :class:`.GiftiSurface` :meth:`__getGiftiSurfaceInfo`
    ====================== =============================
    """


    def __init__(self, parent, overlayList, displayCtx, frame):
        """Create an ``OverlayInfoPanel``.

        :arg parent:      The :mod:`wx` parent object.
        :arg overlayList: The :class:`.OverlayList` instance.
        :arg displayCtx:  The :class:`.DisplayContext` instance.
        :arg frame:       The :class:`.FSLeyesFrame` instance.
        """

        fslpanel.FSLeyesPanel.__init__(
            self, parent, overlayList, displayCtx, frame)

        if USE_HTML2: self.__info = wxhtml.WebView.New(self)
        else:         self.__info = HtmlWindow(        self)
        
        self.__sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__sizer.Add(self.__info, flag=wx.EXPAND, proportion=1)
        
        self.SetSizer(self.__sizer)

        displayCtx .addListener('selectedOverlay',
                                self._name,
                                self.__selectedOverlayChanged) 
        overlayList.addListener('overlays',
                                self._name,
                                self.__selectedOverlayChanged)

        self.__currentOverlay = None
        self.__currentDisplay = None
        self.__currentOpts    = None
        self.__selectedOverlayChanged()

        self.SetMinSize((350, 500))
        self.Layout()

        
    def destroy(self):
        """Must be called when this ``OverlayInfoPanel`` is no longer
        needed. Removes some property listeners, and calls the
        :meth:`.FSLeyesPanel.destroy` method.
        """
        
        self._displayCtx .removeListener('selectedOverlay', self._name)
        self._overlayList.removeListener('overlays',        self._name)

        if self.__currentDisplay is not None:
            self.__currentDisplay.removeListener('name', self._name)

        self.__currentOverlay = None
        self.__currentDisplay = None

        fslpanel.FSLeyesPanel.destroy(self)

        
    def __selectedOverlayChanged(self, *a):
        """Called when the :class:`.OverlayList` or
        :attr:`.DisplayContext.selectedOverlay` changes. Refreshes the
        information shown on this ``OverlayInfoPanel``.
        """

        overlay = self._displayCtx.getSelectedOverlay()

        # Overlay list is empty
        if overlay is None:
            self.__info.SetPage('', '')
            self.__info.Refresh()
            return
        
        self.__deregisterOverlay()
        
        if overlay is not None:
            self.__registerOverlay(overlay)

        self.__updateInformation()


    _optProps = td.TypeDict({
        'Image'        : ['transform'],
        'TriangleMesh' : ['refImage', 'coordSpace'],
        'DTIFitTensor' : ['transform'],
    })
    """This dictionary contains a list of :class:`.DisplayOpts` properties
    that, when changed, should result in the information being refreshed.
    It is used by the :meth:`__registerOverlay` and :meth:`__deregisterOverlay`
    methods.
    """
    

    def __registerOverlay(self, overlay):
        """Registers property listeners with the given overlay so the
        information can be refreshed when necessary.
        """

        display = self._displayCtx.getDisplay(overlay)
        opts    = display.getDisplayOpts()

        self.__currentOverlay = overlay
        self.__currentDisplay = display
        self.__currentOpts    = opts

        display.addListener('name',
                            self._name,
                            self.__overlayNameChanged)
        display.addListener('overlayType',
                            self._name,
                            self.__overlayTypeChanged)

        for propName in OverlayInfoPanel._optProps.get(overlay, []):
            opts.addListener(propName, self._name, self.__overlayOptsChanged) 

    
    def __deregisterOverlay(self):
        """De-registers property listeners from the overlay that was
        previously registered via :meth:`__registerOverlay`.
        """ 

        if self.__currentOverlay is None:
            return

        overlay = self.__currentOverlay
        display = self.__currentDisplay
        opts    = self.__currentOpts

        self.__currentOverlay = None
        self.__currentDisplay = None
        self.__currentOpts    = None

        display.removeListener('name',        self._name)
        display.removeListener('overlayType', self._name)

        for propName in OverlayInfoPanel._optProps[overlay]:
            opts.removeListener(propName, self._name)

        
    def __overlayTypeChanged(self, *a):
        """Called when the :attr:`.Display.overlayType` for the current
        overlay changes. Re-registers with the ``Display`` and
        ``DisplayOpts`` instances associated with the overlay.
        """
        self.__selectedOverlayChanged() 
        
        
    def __overlayNameChanged(self, *a):
        """Called when the :attr:`.Display.name` for the current overlay
        changes. Updates the information display.
        """
        self.__updateInformation()

        
    def __overlayOptsChanged(self, *a):
        """Called when any :class:`.DisplayOpts` properties for the current
        overlay change. Updates the information display. The properties that
        trigger a refresh are  defined in the :attr:`_optProps` dictionary.
        """
        self.__updateInformation() 


    def __updateInformation(self):
        """Refreshes the information shown on this ``OverlayInfoPanel``.
        Called by the :meth:`__selectedOverlayChanged` and
        :meth:`__overlayNameChanged` methods.
        """

        overlay   = self.__currentOverlay
        display   = self.__currentDisplay
        infoFunc  = '_{}__get{}Info'.format(type(self)   .__name__,
                                            type(overlay).__name__)
        infoFunc  = getattr(self, infoFunc, None)

        # Overlay is none, or the overlay 
        # type is not supported
        if infoFunc is None:
            self.__info.SetPage('', '')
            self.__info.Refresh()
            return

        info = infoFunc(overlay, display)

        self.__info.SetPage(self.__formatOverlayInfo(info), '')
        self.__info.Refresh()


    def __getImageInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.Image` overlay.

        :arg overlay: A :class:`.Image` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``Image``.
        """

        img     = overlay.nibImage
        hdr     = overlay.header
        isNifti = overlay.niftiVersion >= 1
        opts    = display.getDisplayOpts()

        if isNifti: title = strings.labels[self, overlay]
        else:       title = strings.labels[self, 'Analyze']
        
        info = OverlayInfo('{} - {}'.format(display.name, title))
        
        generalSect = strings.labels[self,          'general']
        dimSect     = strings.labels[self, overlay, 'dimensions']
        xformSect   = strings.labels[self, overlay, 'transform']
        orientSect  = strings.labels[self, overlay, 'orient']

        info.addSection(generalSect)
        info.addSection(dimSect)
        info.addSection(xformSect)
        info.addSection(orientSect)

        displaySpace = strings.labels[self,
                                      overlay,
                                      'displaySpace',
                                      opts.transform]
        
        if opts.transform == 'custom':
            dsImg = self._displayCtx.displaySpace
            if isinstance(dsImg, fslimage.Nifti):
                dsDisplay    = self._displayCtx.getDisplay(dsImg)
                displaySpace = displaySpace.format(dsDisplay.name)
            else:
                log.warn('{} transform ({}) seems to be out '
                         'of date (display space: {})'.format(
                             overlay,
                             opts.transform,
                             self._displayCtx.displaySpace))

        dataType = strings.nifti.get(('datatype', int(hdr['datatype'])),
                                     'Unknown')
 
        info.addInfo(strings.labels[self, 'niftiVersion'],
                     strings.nifti['version.{}'.format(overlay.niftiVersion)],
                     section=generalSect)
        info.addInfo(strings.labels[self, 'dataSource'],
                     overlay.dataSource,
                     section=generalSect)
        info.addInfo(strings.nifti['datatype'],
                     dataType,
                     section=generalSect)
        info.addInfo(strings.nifti['descrip'],
                     terminateString(hdr['descrip']),
                     section=generalSect)

        if isNifti:
            intent = strings.nifti.get(
                ('intent_code', int(hdr['intent_code'])),
                'Unknown')
        
            info.addInfo(strings.nifti['intent_code'],
                         intent,
                         section=generalSect)
            info.addInfo(strings.nifti['intent_name'],
                         terminateString(hdr['intent_name']),
                         section=generalSect)
            
        info.addInfo(strings.nifti['aux_file'],
                     terminateString(hdr['aux_file']),
                     section=generalSect) 

        info.addInfo(strings.labels[self, 'overlayType'],
                     strings.choices[display, 'overlayType'][
                         display.overlayType],
                     section=generalSect)
        info.addInfo(strings.labels[self, 'displaySpace'],
                     displaySpace,
                     section=generalSect)
        
        info.addInfo(strings.nifti['dimensions'],
                     '{}D'.format(len(overlay.shape)),
                     section=dimSect)

        for i in range(len(overlay.shape)):
            info.addInfo(strings.nifti['dim{}'.format(i + 1)],
                         str(overlay.shape[i]),
                         section=dimSect)

        # NIFTI images can specify different units.
        if isNifti:
            voxUnits  = overlay.xyzUnits
            timeUnits = overlay.timeUnits

        # Assume mm / seconds for ANALYZE images
        # We are using nifti xyzt_unit code values
        # here
        else:
            voxUnits, timeUnits = 2, 8

        # Convert the unit codes into labels
        voxUnits  = strings.nifti.get(('xyz_unit', voxUnits),  'INVALID CODE')
        timeUnits = strings.nifti.get(('t_unit',   timeUnits), 'INVALID CODE')

        for i in range(len(overlay.shape)):
            
            pixdim = hdr['pixdim'][i + 1]

            if   i  < 3: pixdim = '{:0.4g} {}'.format(pixdim, voxUnits)
            elif i == 3: pixdim = '{:0.4g} {}'.format(pixdim, timeUnits)
                
            info.addInfo(
                strings.nifti['pixdim{}'.format(i + 1)],
                pixdim,
                section=dimSect)

        # For NIFTI images, we show both
        # the sform and qform matrices,
        # in addition to the effective
        # transformation
        if isNifti:
            
            qformCode = int(hdr['qform_code'])
            sformCode = int(hdr['sform_code'])

            info.addInfo(strings.nifti['transform'],
                         self.__formatArray(overlay.voxToWorldMat),
                         section=xformSect)

            info.addInfo(strings.nifti['sform_code'],
                         strings.anatomy['Nifti', 'space', sformCode],
                         section=xformSect)
            info.addInfo(strings.nifti['qform_code'],
                         strings.anatomy['Nifti', 'space', qformCode],
                         section=xformSect)

            if sformCode != constants.NIFTI_XFORM_UNKNOWN:
                info.addInfo(strings.nifti['sform'],
                             self.__formatArray(img.get_sform()),
                             section=xformSect)

            if qformCode != constants.NIFTI_XFORM_UNKNOWN:
                info.addInfo(strings.nifti['qform'],
                             self.__formatArray(img.get_qform()),
                             section=xformSect)

        # For ANALYZE images, we show 
        # the scale/offset matrix
        else:
            info.addInfo(strings.nifti['affine'],
                         self.__formatArray(hdr.get_best_affine()),
                         section=xformSect) 

        if overlay.getXFormCode() == constants.NIFTI_XFORM_UNKNOWN:
            storageOrder = 'unknown'
        elif overlay.isNeurological(): storageOrder = 'neuro'
        else:                          storageOrder = 'radio'
        storageOrder = strings.nifti['storageOrder.{}'.format(storageOrder)]

        info.addInfo(strings.nifti['storageOrder'],
                     storageOrder,
                     section=orientSect)

        for i in range(3):
            xform  = opts.getTransform('voxel', 'world')
            orient = overlay.getOrientation(i, xform)
            orient = '{} - {}'.format(
                strings.anatomy['Nifti', 'lowlong',  orient],
                strings.anatomy['Nifti', 'highlong', orient])
            info.addInfo(strings.nifti['voxOrient.{}'.format(i)],
                         orient,
                         section=orientSect)

        for i in range(3):
            xform  = np.eye(4)
            orient = overlay.getOrientation(i, xform)
            orient = '{} - {}'.format(
                strings.anatomy['Nifti', 'lowlong',  orient],
                strings.anatomy['Nifti', 'highlong', orient])
            info.addInfo(strings.nifti['worldOrient.{}'.format(i)],
                         orient,
                         section=orientSect)

        return info


    def __getFEATImageInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.FEATImage` overlay.

        :arg overlay: A :class:`.FEATImage` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``FEATImage``.
        """

        info = self.__getImageInfo(overlay, display)

        featInfo = [
            ('analysisName',   overlay.getAnalysisName()),
            ('analysisDir',    overlay.getFEATDir()),
            ('numPoints',      overlay.numPoints()),
            ('numEVs',         overlay.numEVs()),
            ('numContrasts',   overlay.numContrasts())]

        topLevel = overlay.getTopLevelAnalysisDir()
        report   = overlay.getReportFile()

        if topLevel is not None:
            featInfo.insert(2, ('partOfAnalysis', topLevel))
            
        if report is not None:
            report = '<a href="file://{}">{}</a>'.format(report, report)
            featInfo.insert(2, ('report', report)) 

        secName = strings.labels[self, overlay, 'featInfo']
        info.addSection(secName)

        for k, v in featInfo:
            info.addInfo(strings.feat[k], v, section=secName)

        return info


    def __getMelodicImageInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.MelodicImage` overlay.

        :arg overlay: A :class:`.MelodicImage` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``MelodicImage``.
        """

        info = self.__getImageInfo(overlay, display)

        melInfo = [
            ('dataFile',       overlay.getDataFile()),
            ('analysisDir',    overlay.getMelodicDir()),
            ('tr',             overlay.tr),
            ('numComponents',  overlay.numComponents())]

        topLevel = overlay.getTopLevelAnalysisDir()
        report   = overlay.getReportFile()
        
        if topLevel is not None:
            melInfo.insert(2, ('partOfAnalysis', topLevel))

        if report is not None:
            report = '<a href="file://{}">{}</a>'.format(report, report)
            melInfo.insert(2, ('report', report)) 

        secName = strings.labels[self, overlay, 'melodicInfo']
        info.addSection(secName)

        for k, v in melInfo:
            info.addInfo(strings.melodic[k], v, section=secName)

        return info

    
    def __getTriangleMeshInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.TriangleMesh` overlay.

        :arg overlay: A :class:`.TriangleMesh` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``TriangleMesh``.
        """ 

        opts   = display.getDisplayOpts()
        refImg = opts.refImage

        modelInfo = [
            ('numVertices',  overlay.vertices.shape[0]),
            ('numTriangles', overlay.indices .shape[0]),
        ]

        if refImg is None:
            modelInfo.append(
                ('displaySpace', strings.labels[
                    self, overlay, 'coordSpace', 'display']))
        else:
            
            refOpts      = self._displayCtx.getOpts(refImg)
            dsImg        = self._displayCtx.displaySpace
            displaySpace = strings.labels[
                self, refImg, 'displaySpace', refOpts.transform]
            coordSpace   = strings.labels[
                self, overlay,
                'coordSpace', opts.coordSpace].format(refImg.name)

            if refOpts.transform == 'custom':
                dsDisplay    = self._displayCtx.getDisplay(dsImg)
                displaySpace = displaySpace.format(dsDisplay.name)

            modelInfo.append(('refImage',     refImg.dataSource))
            modelInfo.append(('coordSpace',   coordSpace))
            modelInfo.append(('displaySpace', displaySpace))

        info = OverlayInfo('{} - {}'.format(
            display.name,
            strings.labels[self, overlay]))
        
        info.addInfo(strings.labels[self, 'dataSource'], overlay.dataSource)

        for name, value in modelInfo:
            info.addInfo(strings.labels[self, overlay, name], value) 

        return info


    def __getGiftiSurfaceInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.GiftiSurface` overlay.

        :arg overlay: A :class:`.GiftiSurface` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``DTIFitTensor``. 
        """

        info       = self.__getTriangleMeshInfo(overlay, display)
        info.title = strings.labels[self, overlay]

        return info


    def __getDTIFitTensorInfo(self, overlay, display):
        """Creates and returns an :class:`OverlayInfo` object containing
        information about the given :class:`.DTIFitTensor` overlay.

        :arg overlay: A :class:`.DTIFitTensor` instance.
        :arg display: The :class:`.Display` instance assocated with the
                      ``DTIFitTensor``. 
        """
        info = self.__getImageInfo(overlay.L1(), display)

        generalSect = strings.labels[self, 'general']
        dataSource  = strings.labels[self, 'dataSource']

        info.title = strings.labels[self, overlay]
        info.sections[generalSect][dataSource] = overlay.dataSource

        tensorInfo = [
            ('v1', overlay.V1().dataSource),
            ('v2', overlay.V2().dataSource),
            ('v3', overlay.V3().dataSource),
            ('l1', overlay.L1().dataSource),
            ('l2', overlay.L2().dataSource),
            ('l3', overlay.L3().dataSource),
        ]

        section = strings.labels[self, overlay, 'tensorInfo']

        info.addSection(section)
        
        for name, val in tensorInfo:
            info.addInfo(strings.tensor[name], val, section)

        return info


    def __formatArray(self, array):
        """Creates and returns a string containing a HTML table which
        formats the data in the given ``numpy.array``.
        """

        lines = []

        lines.append('<table border="0" style="font-size: small;">')

        for rowi in range(array.shape[0]):

            lines.append('<tr>')

            for coli in range(array.shape[1]):
                lines.append('<td>{:0.4g}</td>'.format(array[rowi, coli]))
            lines.append('</tr>')

        lines.append('</table>')
            
        return ''.join(lines)


    def __formatOverlayInfo(self, info):
        """Creates and returns a string containing some HTML which formats
        the information in the given ``OverlayInfo`` instance.
        """
        lines = []

        lines.append('<html>')
        lines.append('<body style="font-family: '
                     'sans-serif; font-size: small;">')
        lines.append('<h2>{}</h2>'.format(info.title))

        sections = []

        if len(info.info) > 0:
            sections.append((None, info.info.items()))
        
        for secName, secInf in info.sections.items():
            sections.append((secName, secInf.items()))

        for i, (secName, secInf) in enumerate(sections):

            lines.append('<div style="float:left; margin: 5px; '
                         'background-color: #f0f0f0;">')

            if secName is not None:
                lines.append('<h3>{}</h3>'.format(secName))

            lines.append('<table border="0" style="font-size: small;">')

            for i, (infName, infData) in enumerate(secInf):

                if i % 2: bgColour = '#f0f0f0'
                else:     bgColour = '#cdcdff'

                lines.append('<tr bgcolor="{}">'
                             '<td><b>{}</b></td>'
                             '<td>{}</td></tr>'.format(
                                 bgColour,
                                 infName,
                                 infData))

            lines.append('</table>')
            lines.append('</div>')


        lines.append('</body></html>')

        return '\n'.join(lines)


class OverlayInfo(object):
    """A little class which encapsulates human-readable information about
    one overlay. ``OverlayInfo`` objects are created and returned by the
    ``OverlayInfoPanel.__get*Info`` methods.

    The information stored in an ``OverlayInfo`` instance is organised into
    *sections*. Within each section, information is organised into key-value
    pairs. The order in which both ``OverlayInfo`` sections, and information,
    is ultimately output, is the order in which the sections/information are
    added, via the :meth:`addSection` and :meth:`addInfo` methods.
    """

    def __init__(self, title):
        """Create an ``OverlayInfo`` instance.

        :arg title: The ``OverlaytInfo`` title.
        """
        
        self.title    = title
        self.info     = collections.OrderedDict()
        self.sections = collections.OrderedDict()

        
    def addSection(self, section):
        """Add a section to this ``OverlayInfo`` instance.

        :arg section: The section name.
        """
        self.sections[section] = collections.OrderedDict()

        
    def addInfo(self, name, info, section=None):
        """Add some information to this ``OverlayInfo`` instance.

        :arg name:    The information name.
        :arg info:    The information value.
        :arg section: Section to place the information in.
        """ 
        if section is None: self.info[             name] = info
        else:               self.sections[section][name] = info

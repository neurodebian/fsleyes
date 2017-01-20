#!/usr/bin/env python
#
# canvaspanel.py - Base class for all panels that display overlay data.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`CanvasPanel` class, which is the base
class for all panels which display overlays using ``OpenGL``.
"""


import os
import os.path as op
import logging

import wx

import numpy            as np
import matplotlib.image as mplimg

import props

import fsl.utils.dialog                            as fsldlg
import fsl.utils.async                             as async
import fsl.utils.status                            as status
import fsl.utils.settings                          as fslsettings
from   fsl.utils.platform  import platform         as fslplatform
import fsl.data.image                              as fslimage
import fsleyes.parseargs                           as parseargs
import fsleyes.strings                             as strings
import fsleyes.actions                             as actions
import fsleyes.colourmaps                          as colourmaps
import fsleyes.displaycontext                      as displayctx
import fsleyes.controls.overlaylistpanel           as overlaylistpanel
import fsleyes.controls.overlayinfopanel           as overlayinfopanel
import fsleyes.controls.atlaspanel                 as atlaspanel
import fsleyes.controls.overlaydisplaytoolbar      as overlaydisplaytoolbar
import fsleyes.controls.overlaydisplaypanel        as overlaydisplaypanel
import fsleyes.controls.canvassettingspanel        as canvassettingspanel
import fsleyes.controls.locationpanel              as locationpanel
import fsleyes.controls.clusterpanel               as clusterpanel
import fsleyes.controls.lookuptablepanel           as lookuptablepanel
import fsleyes.controls.melodicclassificationpanel as melclasspanel
from . import                                         colourbarpanel
from . import                                         viewpanel


log = logging.getLogger(__name__)


class CanvasPanel(viewpanel.ViewPanel):
    """The ``CanvasPanel`` class is a :class:`.ViewPanel` which is the base
    class for all panels which display overlays using ``OpenGL``
    (e.g. the :class:`.OrthoPanel` and the :class:`.LightBoxPanel`). A
    ``CanvasPanel`` instance uses a :class:`.SceneOpts` instance to control
    much of its functionality. The ``SceneOpts`` instance used by a
    ``CanvasPanel`` can be accessed via the :meth:`getSceneOptions` method.

    
    The ``CanvasPanel`` class contains settings and functionality common to
    all sub-classes, including *movie mode* (see :attr:`movieMode`), the
    ability to show a colour bar (a :class:`.ColourBarPanel`; see
    :attr:`.SceneOpts.showColourBar`), and a number of actions.

    
    **Sub-class implementations**

    
    Sub-classes of the ``CanvasPanel`` must do the following:
    
      1. Add their content to the panel that is accessible via the
         :meth:`getContentPanel` method (see the note on
         :ref:`adding content <canvaspanel-adding-content>`).
    
      2. Override the :meth:`getGLCanvases` method.

      3. Call the :meth:`centrePanelLayout` method in their ``__init__``
         method.

      4. Override the :meth:`centrePanelLayout` method if any custom layout is
         necessary.
    
    
    **Actions**


    The following actions are available through a ``CanvasPanel`` (see
    the :mod:`.actions` module). They toggle a range of
    :mod:`control <.controls>` panels:

    .. autosummary::
       :nosignatures:
    
       screenshot
       showCommandLineArgs
       toggleMovieMode
       toggleDisplaySync
       toggleOverlayList
       toggleOverlayInfo
       toggleAtlasPanel
       toggleDisplayToolBar
       toggleDisplayPanel
       toggleCanvasSettingsPanel
       toggleLocationPanel
       toggleClusterPanel
       toggleLookupTablePanel
       toggleClassificationPanel


    .. _canvaspanel-adding-content:

    
    **Adding content**

    
    To support colour bar and screenshot functionality, the ``CanvasPanel``
    uses a hierarchy of ``wx.Panel`` instances, depicted in the following
    containment hierarchy diagram:
    
    .. graphviz::

       digraph canvasPanel {

         graph [size=""];

         node [style="filled",
               shape="box",
               fillcolor="#ddffdd",
               fontname="sans"];
     
         rankdir="BT";
    
         1 [label="CanvasPanel"];
         2 [label="Centre panel"];
         3 [label="Custom content (for complex layouts)"];
         4 [label="Container panel"];
         5 [label="ColourBarPanel"];
         6 [label="Content panel"];
         7 [label="Content added by sub-classes"];

         2 -> 1;
         3 -> 2;
         4 -> 2;
         5 -> 4;
         6 -> 4;
         7 -> 6;
       }

    
    As depicted in the diagram, sub-classes need to add their content to the
    *content panel*. This panel is accessible via the :meth:`getContentPanel`
    method. 

    
    The *centre panel* is what gets passed to the
    :meth:`.ViewPanel.setCentrePanel` method, and is accessible via the
    :meth:`getCentrePanel` method, if necessary. The *container panel* is
    also available, via the :meth:`getContainerPanel`. Everything in the
    container panel will appear in screenshots (see the :meth:`screenshot`
    method).

    
    The :meth:`centrePanelLayout` method lays out the centre panel, using the
    :meth:`layoutContainerPanel` method to lay out the colour bar and the
    content panel. The ``centrePanelLayout`` method simply adds the canvas
    container directly to the centre panel. Sub-classes which have more
    advanced layout requirements (e.g.  the :class:`.LightBoxPanel` needs a
    scrollbar) may override the :meth:`centrePanelLayout` method to implement
    their own layout.  These sub-class implementations must:

      1. Call the :meth:`layoutContainerPanel` method.

      2. Add the container panel (accessed via :meth:`getContainerPanel`)
         to the centre panel (accessed via :meth:`getCentrePanel`).

      3. Add any other custom content to the centre panel.
    """

    
    syncLocation = props.Boolean(default=True)
    """If ``True`` (the default), the :attr:`.DisplayContext.location` for 
    this ``CanvasPanel`` is linked to the master ``DisplayContext`` location.
    """

    
    syncOverlayOrder = props.Boolean(default=True)
    """If ``True`` (the default), the :attr:`.DisplayContext.overlayOrder`
    for this ``CanvasPanel`` is linked to the master ``DisplayContext``
    overlay order.
    """    

    
    syncOverlayDisplay = props.Boolean(default=True)
    """If ``True`` (the default), the properties of the :class:`.Display` 
    and :class:`.DisplayOpts` instances for every overlay, as managed
    by the :attr:`.DisplayContext` for this ``CanvasPanel``, are linked to
    the properties of all ``Display`` and ``DisplayOpts`` instances managed
    by the master ``DisplayContext`` instance.
    """

    
    movieMode = props.Boolean(default=False)
    """If ``True``, and the currently selected overlay (see
    :attr:`.DisplayContext.selectedOverlay`) is a :class:`.Image` instance
    with its display managed by a :class:`.VolumeOpts` instance, the displayed
    volume is changed periodically, according to the :attr:`movieRate`
    property.

    The update is performed on the main application thread via
    ``wx.CallLater``.
    """

    
    movieRate = props.Int(minval=10, maxval=1000, default=750, clamped=True)
    """The movie update rate in milliseconds. The value of this property is
    inverted so that a high value corresponds to a fast rate, which makes
    more sense when displayed as an option to the user.
    """

    
    movieAxis = props.Choice((0, 1, 2, 3), default=3)
    """Axis along which the movie should be played, relative to the
    currently selected :class:`.Image`.
    """
    

    def __init__(self, parent, overlayList, displayCtx, frame, sceneOpts):
        """Create a ``CanvasPanel``.

        :arg parent:       The :mod:`wx` parent object.
        
        :arg overlayList:  The :class:`.OverlayList` instance.
        
        :arg displayCtx:   The :class:`.DisplayContext` instance.
        
        :arg sceneOpts:    A :class:`.SceneOpts` instance for this
                           ``CanvasPanel`` - must be created by
                           sub-classes.
        """

        viewpanel.ViewPanel.__init__(
            self, parent, overlayList, displayCtx, frame)

        self.__opts = sceneOpts

        # Use this name for listener registration,
        # in case subclasses use the FSLeyesPanel._name
        self.__name = 'CanvasPanel_{}'.format(self._name)
        
        # Bind the sync* properties of this
        # CanvasPanel to the corresponding
        # properties on the DisplayContext
        # instance. 
        if displayCtx.getParent() is not None:
            self.bindProps('syncLocation',
                           displayCtx,
                           displayCtx.getSyncPropertyName('location'))
            self.bindProps('syncOverlayOrder',
                           displayCtx,
                           displayCtx.getSyncPropertyName('overlayOrder'))
            self.bindProps('syncOverlayDisplay', displayCtx) 
            
        # If the displayCtx instance does not
        # have a parent, this means that it is
        # a top level instance
        else:
            self.disableProperty('syncLocation')
            self.disableProperty('syncOverlayOrder')
            self.disableProperty('syncOverlayDisplay')

        self.__centrePanel    = wx.Panel(self)
        self.__containerPanel = wx.Panel(self.__centrePanel)
        self.__contentPanel   = wx.Panel(self.__containerPanel)

        self.toggleMovieMode  .bindProps('toggled', self, 'movieMode')
        self.toggleDisplaySync.bindProps('toggled', self, 'syncOverlayDisplay')

        self.setCentrePanel(self.__centrePanel)

        # the __movieModeChanged method is called
        # when movieMode changes, but also when
        # the movie axis, overlay list, or selected
        # overlay changes. This is because, if movie
        # mode is on, but no overlay, or an
        # incompatible overlay, is selected, the
        # movie loop stops. So it needs to be
        # re-started if/when a compatible overlay is
        # selected.
        self.__movieRunning = False
        self             .addListener('movieMode',
                                      self.__name,
                                      self.__movieModeChanged)
        self             .addListener('movieAxis',
                                      self.__name,
                                      self.__movieModeChanged) 
        self._overlayList.addListener('overlays',
                                      self.__name,
                                      self.__movieModeChanged)
        self._displayCtx .addListener('selectedOverlay',
                                      self.__name,
                                      self.__movieModeChanged) 

        # Canvas/colour bar layout is managed in
        # the layoutColourBarAndCanvas method
        self.__colourBar = None

        self.__opts.addListener('colourBarLocation',
                                self.__name,
                                self.__colourBarPropsChanged)
        self.__opts.addListener('showColourBar',
                                self.__name,
                                self.__colourBarPropsChanged)


    def destroy(self):
        """Makes sure that any remaining control panels are destroyed
        cleanly, and calls :meth:`.ViewPanel.destroy`.
        """

        if self.__colourBar is not None:
            self.__colourBar.destroy()

        self             .removeListener('movieMode',         self.__name)
        self             .removeListener('movieAxis',         self.__name)
        self._overlayList.removeListener('overlays',          self.__name)
        self._displayCtx .removeListener('selectedOverlay',   self.__name)
        self.__opts      .removeListener('colourBarLocation', self.__name)
        self.__opts      .removeListener('showColourBar',     self.__name)
            
        viewpanel.ViewPanel.destroy(self)


    @actions.action
    def screenshot(self):
        """Takes a screenshot of the currently displayed scene on this
        ``CanvasPanel``. See the :func:`_screenshot` function.
        """
        _screenshot(self._overlayList, self._displayCtx, self)


    @actions.action
    def showCommandLineArgs(self):
        """Shows the command line arguments which can be used to re-create
        the currently displayed scene. See the :func:`_showCommandLineArgs`
        function.
        """
        _showCommandLineArgs(self._overlayList, self._displayCtx, self)


    @actions.toggleAction
    def toggleMovieMode(self):
        """Toggles the value of :attr:`movieMode`. """
        # The state of this action gets bound to 
        # the movieMode attribute in __init__ 
        pass


    @actions.toggleAction
    def toggleDisplaySync(self):
        """Toggles the value of :attr:`syncOverlayDisplay`. """
        # The state of this action gets bound to 
        # the syncOverlayDisplay attribute in __init__ 
        pass 

        
    @actions.toggleControlAction(overlaylistpanel.OverlayListPanel)
    def toggleOverlayList(self):
        """Toggles an :class:`.OverlayListPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """
        self.togglePanel(overlaylistpanel.OverlayListPanel, location=wx.BOTTOM)

    
    @actions.toggleControlAction(overlayinfopanel.OverlayInfoPanel)
    def toggleOverlayInfo(self, floatPane=False):
        """Toggles an :class:`.OverlayInfoPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """        
        self.togglePanel(overlayinfopanel.OverlayInfoPanel,
                         location=wx.RIGHT,
                         floatPane=floatPane)
    

    @actions.toggleControlAction(atlaspanel.AtlasPanel)
    def toggleAtlasPanel(self):
        """Toggles an :class:`.AtlasPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """
        self.togglePanel(atlaspanel.AtlasPanel, location=wx.BOTTOM) 


    @actions.toggleControlAction(overlaydisplaytoolbar.OverlayDisplayToolBar)
    def toggleDisplayToolBar(self):
        """Toggles an :class:`.OverlayDisplayToolBar`. See
        :meth:`.ViewPanel.togglePanel`.
        """ 
        self.togglePanel(overlaydisplaytoolbar.OverlayDisplayToolBar,
                         viewPanel=self)

        
    @actions.toggleControlAction(overlaydisplaypanel.OverlayDisplayPanel)
    def toggleDisplayPanel(self, floatPane=False):
        """Toggles an :class:`.OverlayDisplayPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """
        self.togglePanel(overlaydisplaypanel.OverlayDisplayPanel,
                         floatPane=floatPane,
                         location=wx.LEFT) 
        

    @actions.toggleControlAction(canvassettingspanel.CanvasSettingsPanel)
    def toggleCanvasSettingsPanel(self, floatPane=False):
        """Toggles a :class:`.CanvasSettingsPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """
        self.togglePanel(canvassettingspanel.CanvasSettingsPanel,
                         canvasPanel=self, 
                         floatPane=floatPane,
                         location=wx.LEFT) 

        
    @actions.toggleControlAction(locationpanel.LocationPanel)
    def toggleLocationPanel(self):
        """Toggles a :class:`.LocationPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """
        self.togglePanel(locationpanel.LocationPanel, location=wx.BOTTOM) 


    @actions.toggleControlAction(clusterpanel.ClusterPanel)
    def toggleClusterPanel(self):
        """Toggles a :class:`.ClusterPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """ 
        self.togglePanel(clusterpanel.ClusterPanel, location=wx.TOP) 


    @actions.toggleControlAction(lookuptablepanel.LookupTablePanel)
    def toggleLookupTablePanel(self):
        """Toggles a :class:`.LookupTablePanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """ 
        self.togglePanel(lookuptablepanel.LookupTablePanel, location=wx.RIGHT)

    @actions.toggleControlAction(melclasspanel.MelodicClassificationPanel)
    def toggleClassificationPanel(self):
        """Toggles a :class:`.MelodicClassificationPanel`. See
        :meth:`.ViewPanel.togglePanel`.
        """ 
        self.togglePanel(melclasspanel.MelodicClassificationPanel,
                         location=wx.RIGHT,
                         canvasPanel=self)


    def getSceneOptions(self):
        """Returns the :class:`.SceneOpts` instance used by this
        ``CanvasPanel``.
        """
        return self.__opts
                
        
    def getCentrePanel(self):
        """Returns the ``wx.Panel`` which is passed to
        :meth:`.ViewPanel.setCentrePanel`. See the note on
        :ref:`adding content <canvaspanel-adding-content>`.
        """
        return self.__centrePanel

    
    def getContentPanel(self):
        """Returns the ``wx.Panel`` to which sub-classes must add their content.
        See the note on :ref:`adding content <canvaspanel-adding-content>`.
        """
        return self.__contentPanel 


    def getContainerPanel(self):
        """Returns the ``wx.Panel`` which contains the
        :class:`.ColourBarPanel` if it is being displayed, and the content
        panel. See the note on
        :ref:`adding content <canvaspanel-adding-content>`.
        """
        return self.__containerPanel


    def getGLCanvases(self):
        """This method must be overridden by subclasses, and must return a
        list containing all :class:`.SliceCanvas` instances which are being
        displayed.
        """
        raise NotImplementedError(
            'getGLCanvases has not been implemented '
            'by {}'.format(type(self).__name__))


    def getColourBarCanvas(self):
        """If a colour bar is being displayed, this method returns
        the :class:`.ColourBarCanvas` instance which is used by the
        :class:`.ColourBarPanel` to render the colour bar.
        
        Otherwise, ``None`` is returned.
        """
        if self.__colourBar is not None:
            return self.__colourBar.getCanvas()
        return None


    def centrePanelLayout(self):
        """Lays out the centre panel. This method may be overridden by
        sub-classes which need more advanced layout logic. See the note on
        :ref:`adding content <canvaspanel-adding-content>`
        """

        self.layoutContainerPanel()

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.__containerPanel, flag=wx.EXPAND, proportion=1)
        self.__centrePanel.SetSizer(sizer)
        
        self.PostSizeEvent()
        
    
    def layoutContainerPanel(self):
        """Creates a ``wx.Sizer``, and uses it to lay out the colour bar panel
        and canvas panel. The sizer object is returned.

        This method is used by the default :meth:`centrePanelLayout` method,
        and is available for custom sub-class implementations to use.
        """

        if not self.__opts.showColourBar:

            if self.__colourBar is not None:
                self.__opts.unbindProps('colourBarLabelSide',
                                        self.__colourBar,
                                        'labelSide')
                self.__colourBar.destroy()
                self.__colourBar.Destroy()
                self.__colourBar = None

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(self.__contentPanel, flag=wx.EXPAND, proportion=1)
            self.__containerPanel.SetSizer(sizer)
            return

        if self.__colourBar is None:
            self.__colourBar = colourbarpanel.ColourBarPanel(
                self.__containerPanel,
                self.getOverlayList(),
                self.getDisplayContext(),
                self.getFrame())
            
            bg = self.getSceneOptions().bgColour
            fg = colourmaps.complementaryColour(bg) 
            self.__colourBar.getCanvas().textColour = fg

        self.__opts.bindProps('colourBarLabelSide',
                              self.__colourBar,
                              'labelSide') 
            
        if   self.__opts.colourBarLocation in ('top', 'bottom'):
            self.__colourBar.orientation = 'horizontal'
        elif self.__opts.colourBarLocation in ('left', 'right'):
            self.__colourBar.orientation = 'vertical'
        
        if self.__opts.colourBarLocation in ('top', 'bottom'):
            sizer = wx.BoxSizer(wx.VERTICAL)
        else:
            sizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.__opts.colourBarLocation in ('top', 'left'):
            sizer.Add(self.__colourBar,    flag=wx.EXPAND)
            sizer.Add(self.__contentPanel, flag=wx.EXPAND, proportion=1)
        else:
            sizer.Add(self.__contentPanel, flag=wx.EXPAND, proportion=1)
            sizer.Add(self.__colourBar,    flag=wx.EXPAND)

        self.__containerPanel.SetSizer(sizer)


    def __colourBarPropsChanged(self, *a):
        """Called when any colour bar display properties are changed (see
        :class:`.SceneOpts`). Calls :meth:`canvasPanelLayout`.
        """
        self.centrePanelLayout()


    def __movieModeChanged(self, *a):
        """Called when the :attr:`movieMode` property changes. If it has been
        enabled, calls :meth:`__movieUpdate`, to start the movie loop.
        """

        # The fsl.utils.async idle loop timeout
        # defaults to 200 milliseconds, which can
        # cause delays in frame updates. So when
        # movie mode is on, we bump up the rate.
        def startMovie():
            async.setIdleTimeout(10)
            if not self.__movieLoop(startLoop=True):
                async.setIdleTimeout(None)

        # The __movieModeChanged method is called
        # on the props event queue. Here we make
        # sure that __movieLoop() is called *off*
        # the props event queue, by calling it from
        # the idle loop.
        if self.movieMode: async.idle(startMovie)
        else:              async.setIdleTimeout(None)


    def __movieLoop(self, startLoop=False):
        """Manages the triggering of the next movie frame. This method is
        called by :meth:`__movieModeChanged` when :attr:`movieMode` changes
        and when the selected overlay changes, and also by
        :meth:`__syncMovieUpdate` and :meth:`__unsyncMovieUpdate` while
        the movie loop is running, to trigger the next frame.

        :arg startLoop: This is set to ``True`` when called from
                        :meth:`__movieModeChanged`. If ``True``, and the movie
                        loop is already running, this method does nothing.

        """

        # Movie loop is already running, nothing to do.
        if startLoop and self.__movieRunning:
            return True

        # Attempt to show the next frame -
        # __movieFrame returns True if the
        # movie is continuing, False if it
        # has ended.
        self.__movieRunning = self.__movieFrame()

        return self.__movieRunning



    def __movieFrame(self):
        """Called by :meth:`__movieLoop`.

        If the currently selected overlay (see
        :attr:`.DisplayContext.selectedOverlay`) is a 4D :class:`.Image` being
        displayed as a ``volume`` (see the :class:`.VolumeOpts` class), the
        :attr:`.NiftiOpts.volume` property is incremented and all
        GL canvases in this ``CanvasPanel`` are refreshed.

        :returns: ``True`` if the movie loop was started, ``False`` otherwise.
        """

        if self.destroyed():   return False
        if not self.movieMode: return False

        overlay  = self._displayCtx.getSelectedOverlay()
        canvases = self.getGLCanvases()

        if overlay is None:
            return False

        opts = self._displayCtx.getOpts(overlay)
        axis = self.movieAxis
        
        if not isinstance(overlay, fslimage.Nifti) or \
           len(overlay.shape) <= axis              or \
           not isinstance(opts, displayctx.VolumeOpts):
            return False

        # We want the canvas refreshes to be
        # synchronised. So we 'freeze' them
        # while changing the image volume, and
        # then refresh them all afterwards.
        for c in canvases:
            c.FreezeDraw()
            c.FreezeSwapBuffers()

        limit = overlay.shape[axis]

        # This method has been called off the props
        # event queue (see __movieModeChanged).
        # Therefore, all listeners on the opts.volume
        # or DisplayContext.location  properties
        # should be called immediately, in these
        # assignments.
        #
        # When the movie axis == 3 (time), this means
        # that image texture refreshes should be
        # triggered and, after the opts.volume
        # assignment, all affected GLObjects should
        # return ready() == False.
        if axis == 3:
            if opts.volume >= limit - 1: opts.volume  = 0
            else:                        opts.volume += 1
            
        else:
            voxel = opts.getVoxel()
            if voxel[axis] >= limit - 1: voxel[axis]  = 0
            else:                        voxel[axis] += 1

            self._displayCtx.location = opts.transformCoords(
                voxel, 'voxel', 'display')

        # Now we get refs to *all* GLObjects managed
        # by every canvas - we have to wait until
        # they are all ready to be drawn before we
        # can refresh the canvases.  Note that this
        # is only necessary when the movie axis == 3
        globjs = [c.getGLObject(o)
                  for c in canvases
                  for o in self._overlayList]
        globjs = [g for g in globjs if g is not None]

        def allReady():
            return all([g.ready() for g in globjs])

        # Figure out the movie rate - the
        # number of seconds to wait until
        # triggering the next frame.
        rate    = self.movieRate
        rateMin = self.getConstraint('movieRate', 'minval')
        rateMax = self.getConstraint('movieRate', 'maxval')
        rate    = (rateMin + (rateMax - rate)) / 1000.0

        # The canvas refreshes are performed by the
        # __syncMovieUpdate or __unsyncMovieUpdate
        # methods. Gallium seems to have a problem
        # with separate renders/buffer swaps, so we
        # have to use a shitty unsynchronised update
        # routine.
        useSync = 'gallium' not in fslplatform.glRenderer.lower()

        if useSync: update = self.__syncMovieUpdate
        else:       update = self.__unsyncMovieUpdate

        # Refresh the canvases when all
        # GLObjects are ready to be drawn.
        async.idleWhen(update, allReady, canvases, rate, pollTime=rate / 10) 

        return True


    def __unsyncMovieUpdate(self, canvases, rate):
        """Called by :meth:`__movieUpdate`. Updates all canvases in an
        unsynchronised manner.

        Ideally all canvases should be drawn off-screen (i.e. rendered to the
        back buffer), and then all refreshed together (back and front buffers
        swapped). Unfortunately some OpenGL drivers seem to have trouble with
        this approach, and require drawing and front/back buffer swaps to be
        done at the same time. This method is used for those drivers.

        :arg canvases: List of canvases to update. It is assumed that
                       ``FreezeDraw`` and ``FreezeSwapBuffers`` has been 
                       called on every canvas.
        :arg rate:     Delay to trigger the next movie update.
        """

        for c in canvases:
            c.ThawDraw()
            c.ThawSwapBuffers()
            c.Refresh()

        async.idle(self.__movieLoop, after=rate)


    def __syncMovieUpdate(self, canvases, rate):
        """Updates all canvases in a synchronised manner. All canvases are
        refreshed, and then the front/back buffers are swapped on each of
        them.
        
        :arg canvases: List of canvases to update. It is assumed that
                       ``FreezeDraw`` and ``FreezeSwapBuffers`` has been 
                       called on every canvas.
        :arg rate:     Delay to trigger the next movie update. 
        """

        for c in canvases:
            c.ThawDraw()
            c.Refresh()

        for c in canvases:
            c.ThawSwapBuffers()
            c.SwapBuffers()

        async.idle(self.__movieLoop, after=rate)


def _showCommandLineArgs(overlayList, displayCtx, canvas):
    """Called by the :meth:`CanvasPanel.showCommandLineArgs` method.

    Generates command line arguments which can be used to re-create the
    scene shown on the given :class:`CanvasPanel`, and displays them
    to the user with a :class:`.TextEditDialog`.

    :arg overlayList: A :class:`.OverlayList` .
    :arg displayCtx:  A :class:`.DisplayContext` instance.
    :arg canvas:      A :class:`CanvasPanel` instance.
    """

    args = _genCommandLineArgs(overlayList, displayCtx, canvas)
    dlg  = fsldlg.TextEditDialog(
        canvas,
        title=strings.messages[  canvas, 'showCommandLineArgs', 'title'],
        message=strings.messages[canvas, 'showCommandLineArgs', 'message'],
        text=' '.join(args),
        icon=wx.ICON_INFORMATION,
        style=(fsldlg.TED_OK        |
               fsldlg.TED_READONLY  |
               fsldlg.TED_MULTILINE |
               fsldlg.TED_COPY      |
               fsldlg.TED_COPY_MESSAGE))

    dlg.CentreOnParent()
    dlg.ShowModal()


def _genCommandLineArgs(overlayList, displayCtx, canvas):
    """Called by the :func:`_showCommandLineArgs` function. Generates
    command line arguments which can be used to re-create the scene
    currently shown on the given :class:`CanvasPanel`.

    :arg overlayList: A :class:`.OverlayList` .
    :arg displayCtx:  A :class:`.DisplayContext` instance.
    :arg canvas:      A :class:`CanvasPanel` instance.

    :returns:         A list of command line arguments.
    """

    argv = []

    # Add scene options
    sceneOpts = canvas.getSceneOptions()
    argv += parseargs.generateSceneArgs(
        overlayList,
        displayCtx,
        sceneOpts,
        exclude=['performance'])

    # Add ortho specific options, if it's 
    # an orthopanel we're dealing with
    if isinstance(sceneOpts, displayctx.OrthoOpts):

        xcanvas = canvas.getXCanvas()
        ycanvas = canvas.getYCanvas()
        zcanvas = canvas.getZCanvas()

        # Get the canvas centres in the
        # display coordinate system
        xc = xcanvas.getDisplayCentre()
        yc = ycanvas.getDisplayCentre()
        zc = zcanvas.getDisplayCentre()

        # The getDisplayCentre method only
        # returns horizontal/vertical values,
        # so we have to make the positions 3D.
        loc = displayCtx.location.xyz
        xc  = [loc[0], xc[ 0], xc[ 1]]
        yc  = [yc[ 0], loc[1], yc[ 1]]
        zc  = [zc[ 0], zc[ 1], loc[2]]

        # Transform the centres into the world
        # coordinate system of the first overlay.
        if len(overlayList) > 0:
            opts   = displayCtx.getOpts(overlayList[0])
            refimg = opts.getReferenceImage()
            
            if refimg is not None:
                xc, yc, zc = opts.transformCoords(
                    [xc, yc, zc], 'display', 'world')
                
            # And turn back into 2D (horizontal/
            # vertical) positions
            xc = xc[1], xc[2]
            yc = yc[0], yc[2]
            zc = zc[0], zc[1]

        argv += ['--{}'.format(parseargs.ARGUMENTS[sceneOpts, 'xcentre'][1])]
        argv += ['{:0.8f}'.format(c) for c in xc]
        argv += ['--{}'.format(parseargs.ARGUMENTS[sceneOpts, 'ycentre'][1])]
        argv += ['{:0.8f}'.format(c) for c in yc]
        argv += ['--{}'.format(parseargs.ARGUMENTS[sceneOpts, 'zcentre'][1])]
        argv += ['{:0.8f}'.format(c) for c in zc]

    # Add display options for each overlay
    for overlay in overlayList:

        fname   = overlay.dataSource
        ovlArgv = parseargs.generateOverlayArgs(overlay, displayCtx)
        argv   += [fname] + ovlArgv

    return argv


def _screenshot(overlayList, displayCtx, canvasPanel):
    """Called by the :meth:`CanvasPanel.screenshot` method. Grabs a
    screenshot of the current scene on the given :class:`.CanvasPanel`,
    and saves it to a file specified by the user.

    :arg overlayList: A :class:`.OverlayList` .
    :arg displayCtx:  A :class:`.DisplayContext` instance.
    :arg canvas:      A :class:`CanvasPanel` instance. 
    """

    # Ask the user where they want 
    # the screenshot to be saved
    fromDir = fslsettings.read('canvasPanelScreenshotLastDir',
                               default=os.getcwd())
    
    dlg = wx.FileDialog(
        canvasPanel,
        message=strings.messages['CanvasPanel.screenshot'],
        defaultDir=fromDir,
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

    if dlg.ShowModal() != wx.ID_OK:
        return

    filename = dlg.GetPath()

    # Make the dialog go away before
    # the screenshot gets taken
    dlg.Close()
    dlg.Destroy()
    wx.Yield()

    def doScreenshot():

        # The typical way to get a screen grab of a wx
        # Window is to use a wx.WindowDC, and a wx.MemoryDC,
        # and to 'blit' a region from the window DC into
        # the memory DC.
        #
        # This is precisely what we're doing here, but
        # the process is complicated by the fact that,
        # under OSX, the contents of wx.glcanvas.GLCanvas
        # instances are not captured by WindowDCs.
        #
        # So I'm grabbing a screenshot of the canvas
        # panel in the standard wxWidgets way, and then
        # manually patching in bitmaps of each GLCanvas
        # that is displayed in the canvas panel.

        # Get all the wx GLCanvas instances
        # which are displayed in the panel,
        # including the colour bar canvas
        glCanvases = canvasPanel.getGLCanvases()
        glCanvases.append(canvasPanel.getColourBarCanvas())

        # The canvas panel container is the
        # direct parent of the colour bar
        # canvas, and an ancestor of the
        # other GL canvases
        parent                  = canvasPanel.getContainerPanel()
        totalWidth, totalHeight = parent.GetClientSize().Get()
        absPosx,    absPosy     = parent.GetScreenPosition()
        windowDC                = wx.WindowDC(parent)
        memoryDC                = wx.MemoryDC()
        bmp                     = wx.EmptyBitmap(totalWidth, totalHeight)

        # Copy the contents of the canvas
        # container to the bitmap
        memoryDC.SelectObject(bmp)
        memoryDC.Blit(
            0,
            0,
            totalWidth,
            totalHeight,
            windowDC,
            0,
            0)
        memoryDC.SelectObject(wx.NullBitmap)

        # Make a H*W*4 bitmap array, and copy
        # the container screen grab into it.
        # We initialise the bitmap to the
        # current background colour, due to
        # some sizing issues that will be
        # revealed below.
        opts     = canvasPanel.getSceneOptions()
        bgColour = np.array(opts.bgColour) * 255
        
        data          = np.zeros((totalHeight, totalWidth, 4), dtype=np.uint8)
        data[:, :, :] = bgColour
 
        rgb  = bmp.ConvertToImage().GetData()
        rgb  = np.fromstring(rgb, dtype=np.uint8)

        log.debug('Creating bitmap {} * {} for {} screenshot'.format(
            totalWidth, totalHeight, type(canvasPanel).__name__))
        
        data[:, :, :3] = rgb.reshape(totalHeight, totalWidth, 3)

        # Patch in bitmaps for every GL canvas
        for glCanvas in glCanvases:

            # If the colour bar is not displayed,
            # the colour bar canvas will be None
            if glCanvas is None:
                continue

            # Hidden wx objects will
            # still return a size
            if not glCanvas.IsShown():
                continue

            width, height = glCanvas.GetClientSize().Get()
            posx, posy    = glCanvas.GetScreenPosition()

            posx -= absPosx
            posy -= absPosy

            log.debug('Canvas {} position: ({}, {}); size: ({}, {})'.format( 
                type(glCanvas).__name__, posx, posy, width, height)) 

            xstart = posx
            ystart = posy
            xend   = xstart + width
            yend   = ystart + height

            bmp = glCanvas.getBitmap()

            # Under OSX, there seems to be a size/position
            # miscalculation  somewhere, such that if the last
            # canvas is on the hard edge of the parent, the
            # canvas size spills over the parent size by a
            # couple of pixels. If this occurs, I re-size the
            # final bitmap accordingly.
            #
            # n.b. This is why I initialise the bitmap array
            #      to the canvas panel background colour.
            if xend > totalWidth:
                
                oldWidth    = totalWidth
                totalWidth  = xend
                newData     = np.zeros((totalHeight, totalWidth, 4),
                                       dtype=np.uint8)
                
                newData[:, :, :]         = bgColour
                newData[:, :oldWidth, :] = data
                data                     = newData

                log.debug('Adjusted bitmap width: {} -> {}'.format(
                    oldWidth, totalWidth))
                
            if yend > totalHeight:
                
                oldHeight   = totalHeight
                totalHeight = yend
                newData     = np.zeros((totalHeight, totalWidth, 4),
                                       dtype=np.uint8)
                
                newData[:, :, :]          = bgColour
                newData[:oldHeight, :, :] = data
                data                      = newData

                log.debug('Adjusted bitmap height: {} -> {}'.format(
                    oldHeight, totalHeight)) 

            log.debug('Patching {} in at [{} - {}], [{} - {}]'.format(
                type(glCanvas).__name__, xstart, xend, ystart, yend))
            
            data[ystart:yend, xstart:xend] = bmp

        data[:, :,  3] = 255

        mplimg.imsave(filename, data)

    async.idle(doScreenshot)
    status.update(
        strings.messages['CanvasPanel.screenshot.pleaseWait'].format(filename))

    fslsettings.write('canvasPanelScreenshotLastDir', op.dirname(filename))

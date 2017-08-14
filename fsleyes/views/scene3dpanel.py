#!/usr/bin/env python
#
# scene3dpanel.py - The Scene3DPanel class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`Scene3DPanel` class, a FSLeyes view which
draws the scene in 3D.
"""


import logging

import wx

import numpy as np

import fsl.utils.transform                as transform
import fsleyes.displaycontext.scene3dopts as scene3dopts
import fsleyes.gl.wxglscene3dcanvas       as scene3dcanvas
import fsleyes.actions                    as actions
from . import                                canvaspanel


log = logging.getLogger(__name__)


class Scene3DPanel(canvaspanel.CanvasPanel):
    """The ``Scene3DPanel`` is a :class:`.CanvasPanel` which draws the
    contents of the :class:`.OverlayList` as a 3D scene.


    The ``Scene3DPanel`` uses a :class:`.Scene3DCanvas`, which manages all of
    the GL state and drawing logic. A :class:`.Scene3DViewProfile` instance
    is used to manage all of the user interaction logic.


    The scene properties are described and changed via a :class:`.Scene3DOpts`
    instance, accessible through the :meth:`.CanvasPanel.getSceneOptions`
    method.
    """


    def __init__(self, parent, overlayList, displayCtx, frame):
        """Create a ``Scene3dPanel``.

        :arg parent:      A :mod:`wx` parent object.
        :arg overlayList: A :class:`.OverlayList` instance.
        :arg displayCtx:  A :class:`.DisplayContext` instance.
        :arg frame:       The :class:`.FSLeyesFrame` instance.
        """

        sceneOpts = scene3dopts.Scene3DOpts()

        canvaspanel.CanvasPanel.__init__(self,
                                         parent,
                                         overlayList,
                                         displayCtx,
                                         frame,
                                         sceneOpts)

        contentPanel = self.getContentPanel()

        self.__canvas = scene3dcanvas.WXGLScene3DCanvas(contentPanel,
                                                        overlayList,
                                                        displayCtx)

        self.__canvas.bindProps('pos',          displayCtx, 'location')
        self.__canvas.bindProps('showCursor',   sceneOpts)
        self.__canvas.bindProps('cursorColour', sceneOpts)
        self.__canvas.bindProps('bgColour',     sceneOpts)
        self.__canvas.bindProps('showLegend',   sceneOpts)
        self.__canvas.bindProps('occlusion',    sceneOpts)
        self.__canvas.bindProps('light',        sceneOpts)
        self.__canvas.bindProps('lightPos',     sceneOpts)
        self.__canvas.bindProps('zoom',         sceneOpts)
        self.__canvas.bindProps('offset',       sceneOpts)
        self.__canvas.bindProps('rotation',     sceneOpts)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.__canvas, flag=wx.EXPAND, proportion=1)
        contentPanel.SetSizer(sizer)

        self.centrePanelLayout()
        self.initProfile()
        self.syncLocation = True


    def destroy(self):
        """Must be called when this ``Scene3DPanel`` is no longer in use.
        """

        self.__canvas.destroy()
        self.__canvas = None
        canvaspanel.CanvasPanel.destroy(self)



    def getGLCanvases(self):
        """Returns all of the :class:`.SliceCanvas` instances contained
        within this ``Scene3DPanel``.
        """
        return [self.__canvas]


    def getActions(self):
        """Overrides :meth:`.ViewPanel.getActions`. Returns a list of actions
        that can be executed on this ``Scene3DPanel``, and which will be added
        to its view menu.
        """
        actionz = [self.screenshot,
                   self.showCommandLineArgs,
                   self.applyCommandLineArgs,
                   None,
                   self.toggleDisplaySync,
                   self.resetDisplay,
                   None,
                   self.toggleOverlayList,
                   self.toggleLocationPanel,
                   self.toggleOverlayInfo,
                   self.toggleDisplayPanel,
                   self.toggleCanvasSettingsPanel,
                   self.toggleAtlasPanel,
                   self.toggleDisplayToolBar,
                   self.toggleLookupTablePanel,
                   self.toggleClusterPanel,
                   self.toggleClassificationPanel,
                   self.removeAllPanels]

        def makeTuples(actionz):

            tuples = []

            for a in actionz:
                if isinstance(a, actions.Action):
                    tuples.append((a.__name__, a))

                elif isinstance(a, tuple):
                    tuples.append((a[0], makeTuples(a[1])))

                elif a is None:
                    tuples.append((None, None))

            return tuples

        return makeTuples(actionz)


    @actions.action
    def resetDisplay(self):
        """An action which resets the current camera configuration
        (zoom/pan/rotation). See the :meth:`.Scene3DViewProfile.resetDisplay`
        method.
        """
        self.getCurrentProfile().resetDisplay()


    def doMovieUpdate(self, overlay, opts):
        """Overrides :meth:`.CanvasPanel.doMovieUpdate`. For x/y/z axis
        movies, the scene is rotated. Otherwise (for time) the ``CanvasPanel``
        implementation is called.
        """

        if self.movieAxis >= 3:
            canvaspanel.CanvasPanel.doMovieUpdate(self, overlay, opts)
        else:

            rate    = float(self.movieRate)
            rateMin = self.getConstraint('movieRate', 'minval')
            rateMax = self.getConstraint('movieRate', 'maxval')
            rate    = 0.1 + 0.9 * (rate - rateMin) / (rateMax - rateMin)
            rate    = rate * np.pi / 10

            canvas               = self.__canvas
            rots                 = [0, 0, 0]
            rots[self.movieAxis] = rate

            xform = transform.axisAnglesToRotMat(*rots)
            xform = transform.concat(xform, canvas.rotation)

            canvas.rotation = xform
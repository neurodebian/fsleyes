#!/usr/bin/env python
#
# rendertexturestack.py - The RenderTextureStack class.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides the :class:`RenderTextureStack` class, which is used
by the :class:`.SliceCanvas` class to store a collection of off-screen
:class:`.RenderTexture` instances containing rendered slices of
:class:`.GLObject` instances.
"""

import logging

import OpenGL.GL as gl

import fsleyes.gl.routines as glroutines
import fsleyes.gl.globject as globject
import fsl.utils.async     as async
import fsl.utils.status    as status
from . import                 rendertexture


log = logging.getLogger(__name__)


class RenderTextureStack(object):
    """The ``RenderTextureStack`` class creates and maintains a collection of
    :class:`.RenderTexture` instances, each of which is used to display a
    single slice of a :class:`.GLObject` along a specific display axis.

    The purpose of the ``RenderTextureStack`` is to pre-generate 2D slices of
    a :class:`.GLObject` so that they do not have to be rendered on-demand.
    Rendering a ``GLObject`` slices from a pre-generated off-screen texture
    provides better performance than rendering the ``GLObject`` slice
    in real time.

    The :class:`.RenderTexture` textures are updated in an idle loop, via the
    :func:`.async.idle` function.


    .. note:: A ``RenderTextureStack`` instance must be manually updated
              whenever its ``GLObject`` changes, via the
              :meth:`onGLObjectUpdate` method. ``RenderTextureStack``
              instances do not explicitly listen for ``GLObject`` changes
              themselves, because there is no guarantee that the textures
              will be refreshed before they need to be drawn.
    """

    
    def __init__(self, globj):
        """Create a ``RenderTextureStack``. An update listener is registered
        on the ``GLObject``, so that the textures can be refreshed whenever it
        changes.

        :arg globj: The :class:`.GLObject` instance.
        """

        self.name = '{}_{}_{}'.format(
            type(self).__name__,
            type(globj).__name__, id(self))

        self.__globj              = globj
        self.__maxNumTextures     = 256
        self.__maxWidth           = 1024
        self.__maxHeight          = 1024
        self.__defaultNumTextures = 64
        self.__defaultWidth       = 256
        self.__defaultHeight      = 256

        self.__textureDirty       = []
        self.__textures           = []

        self.__lastDrawnTexture   = None
        self.__updateQueue        = []

        async.idle(self.__textureUpdateLoop)

        log.memory('{}.init ({})'.format(type(self).__name__, id(self)))

        
    def __del__(self):
        """Prints a log message."""
        if log:
            log.memory('{}.del ({})'.format(type(self).__name__, id(self)))

        
    def destroy(self):
        """Must be called when this ``RenderTextureStack`` is no longer needed.
        Calls the :meth:`__destroyTextures` method.
        """
        self.__destroyTextures()


    def getGLObject(self):
        """Returns the :class:`.GLObject` associated with this
        ``RenderTextureStack``.
        """
        return self.__globj

    
    def draw(self, zpos, xform=None):
        """Draws the pre-generated :class:`.RenderTexture` which corresponds
        to the  specified Z position.

        :arg zpos:  Position of slice to render.

        :arg xform: Transformation matrix to apply to rendered slice vertices.
        """

        xax = self.__xax
        yax = self.__yax

        texIdx                  = self.__zposToIndex(zpos)
        self.__lastDrawnTexture = texIdx

        if texIdx < 0 or texIdx >= len(self.__textures):
            return

        lo, hi  = self.__globj.getDisplayBounds()
        texture = self.__textures[texIdx]

        if self.__textureDirty[texIdx]:
            self.__refreshTexture(texture, texIdx)

        log.debug('Drawing pre-rendered texture '
                  '[zax {}]: (zpos {}, slice {})'.format(
                      self.__zax,
                      zpos,
                      texIdx))

        texture.drawOnBounds(
            zpos, lo[xax], hi[xax], lo[yax], hi[yax], xax, yax, xform)

    
    def setAxes(self, xax, yax):
        """This method must be called when the display orientation of the
        :class:`.GLObject` changes. It destroys and re-creates all
        :class:`.RenderTexture` instances.
        """

        zax        = 3 - xax - yax
        self.__xax = xax
        self.__yax = yax
        self.__zax = zax

        res = self.__globj.getDataResolution(xax, yax)

        if res is not None: numTextures = res[zax]
        else:               numTextures = self.__defaultNumTextures

        if numTextures > self.__maxNumTextures:
            numTextures = self.__maxNumTextures

        self.__destroyTextures()
        
        for i in range(numTextures):
            self.__textures.append(
                rendertexture.RenderTexture('{}_{}'.format(self.name, i)))

        self.onGLObjectUpdate()

        
    def __destroyTextures(self):
        """Destroys all :class:`.RenderTexture` instances. This is performed
        asynchronously, via the ``.async.idle`` function.
        """

        texes = self.__textures
        self.__textures = []

        for tex in texes:
            async.idle(tex.destroy)


    def onGLObjectUpdate(self):
        """Must be called called when the :class:`.GLObject` display is
        updated. Re-calculates the display space Z-axis range, and marks
        all render textures as dirty.
        """
        
        lo, hi      = self.__globj.getDisplayBounds()
        self.__zmin = lo[self.__zax]
        self.__zmax = hi[self.__zax]

        log.debug('GLObject range [zax {}]: {} - {}'.format(
            self.__zax,
            self.__zmin,
            self.__zmax))

        self.__refreshAllTextures()

            
    def __refreshAllTextures(self, *a):
        """Marks all :class:`.RenderTexture`  instances as *dirty*, so that
        they will be refreshed by the :meth:`.__textureUpdateLoop`.
        """

        if self.__lastDrawnTexture is not None:
            lastIdx = self.__lastDrawnTexture
        else:
            lastIdx = len(self.__textures) / 2
            
        aboveIdxs = range(lastIdx, len(self.__textures))
        belowIdxs = range(lastIdx - 1, -1, -1)

        idxs = [0] * len(self.__textures)

        for i in range(len(self.__textures)):
            
            if len(aboveIdxs) > 0 and len(belowIdxs) > 0:
                if i % 2: idxs[i] = belowIdxs.pop(0)
                else:     idxs[i] = aboveIdxs.pop(0)
                
            elif len(aboveIdxs) > 0: idxs[i] = aboveIdxs.pop(0)
            else:                    idxs[i] = belowIdxs.pop(0)

        self.__textureDirty = [True] * len(self.__textures)
        self.__updateQueue  = idxs

        async.idle(self.__textureUpdateLoop)


    def __textureUpdateLoop(self):
        """This method is called via the :func:`.async.idle` function.
        It loops through all :class:`.RenderTexture` instances, and
        refreshes any that have been marked as *dirty*.

        Each call to this method causes one ``RenderTexture`` to be
        refreshed. After a ``RenderTexture`` has been refreshed, if there
        are dirty more ``RenderTexture`` instances, this method re-schedules
        itself to be called again via :func:`.async.idle`.
        """

        if len(self.__updateQueue) == 0 or len(self.__textures) == 0:
            return

        idx = self.__updateQueue.pop(0)

        if self.__textureDirty[idx]:

            tex = self.__textures[idx]
        
            log.debug('Refreshing texture slice {} (zax {})'.format(
                idx, self.__zax))
        
            self.__refreshTexture(tex, idx)

        if len(self.__updateQueue) > 0:
            async.idle(self.__textureUpdateLoop)

        
    def __refreshTexture(self, tex, idx):
        """Refreshes the given :class:`.RenderTexture`.

        :arg tex: The ``RenderTexture`` to refresh.
        :arg idx: Index of the ``RenderTexture``.
        """

        globj = self.__globj
        zpos  = self.__indexToZpos(idx)
        xax   = self.__xax
        yax   = self.__yax

        if not globj.ready():
            return

        if isinstance(globj, globject.GLImageObject):
            name = globj.image.name
        else:
            name = type(globj).__name__

        status.update('Pre-rendering {} slice {}...'.format(name, zpos))

        lo, hi = globj.getDisplayBounds()
        res    = globj.getDataResolution(xax, yax)

        if res is not None:
            width  = res[xax]
            height = res[yax]
        else:
            width  = self.__defaultWidth
            height = self.__defaultHeight

        if width  > self.__maxWidth:  width  = self.__maxWidth
        if height > self.__maxHeight: height = self.__maxHeight

        log.debug('Refreshing render texture for slice {} (zpos {}, '
                  'zax {}): {} x {}'.format(idx, zpos, self.__zax,
                                            width, height))

        tex.setSize(width, height)

        oldSize       = gl.glGetIntegerv(gl.GL_VIEWPORT)
        oldProjMat    = gl.glGetFloatv(  gl.GL_PROJECTION_MATRIX)
        oldMVMat      = gl.glGetFloatv(  gl.GL_MODELVIEW_MATRIX)

        tex.bindAsRenderTarget()
        glroutines.show2D(xax, yax, width, height, lo, hi)
        glroutines.clear((0, 0, 0, 0))

        globj.preDraw()
        globj.draw(zpos)
        globj.postDraw()
        tex.unbindAsRenderTarget()
        
        gl.glViewport(*oldSize)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadMatrixf(oldProjMat)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadMatrixf(oldMVMat)

        self.__textureDirty[idx] = False


    def __zposToIndex(self, zpos):
        """Converts a Z location in the display coordinate system into a
        ``RenderTexture`` index.
        """        
        zmin  = self.__zmin
        zmax  = self.__zmax
        ntexs = len(self.__textures)
        step  = (zmax - zmin) / float(ntexs)
        index = (zpos - zmin) / step

        # Be a little bit lenient at the boundaries
        if abs(index)         < 0.01: index = 0
        if abs(index - ntexs) < 0.01: index = ntexs - 1

        return int(index)

    
    def __indexToZpos(self, index):
        """Converts a ``RenderTexture`` index into a Z location in the display
        coordinate system.
        """
        zmin  = self.__zmin
        zmax  = self.__zmax
        ntexs = len(self.__textures)
        step  = (zmax - zmin) / float(ntexs)
        
        return index * (zmax - zmin) / ntexs + (zmin + 0.5 * step)

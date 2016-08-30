#!/usr/bin/env python
#
# profilemap.py - CanvasPanel -> Profile mappings.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module is used by the :class:`.Profile` and :class:`.ProfileManager`
classes.

It defines a few dictionaries which define the profile type to use for each
:class:`.ViewPanel` type, temporary mouse/keyboard interaction modes, and
alternate mode handlers for the profiles contained in the profiles package.

.. autosummary::
   profiles
   profileHandlers
   tempModeMap
   altHandlerMap
"""

import logging

from collections import OrderedDict

import wx

from fsleyes.views.orthopanel             import OrthoPanel
from fsleyes.views.lightboxpanel          import LightBoxPanel

from fsleyes.profiles.orthoviewprofile    import OrthoViewProfile
from fsleyes.profiles.orthoeditprofile    import OrthoEditProfile
from fsleyes.profiles.lightboxviewprofile import LightBoxViewProfile


log = logging.getLogger(__name__)


profiles  = {
    OrthoPanel    : ['view', 'edit'],
    LightBoxPanel : ['view']
}
"""This dictionary is used by the :class:`.ProfileManager` to figure out which
profiles are available for each :class:`.ViewPanel`. They are added as options
to the :attr:`.ViewPanel.profile` property.
"""


profileHandlers = {
    (OrthoPanel,    'view') : OrthoViewProfile,
    (OrthoPanel,    'edit') : OrthoEditProfile,
    (LightBoxPanel, 'view') : LightBoxViewProfile
}
"""This dictionary is used by the :class:`.ProfileManager` class to figure out
which :class:`.Profile` sub-class to create for a given :class:`.ViewPanel`
instance and profile identifier.
"""


# Important: Any temporary modes which use CTRL,
# ALT, or CTRL+ALT must not handle character events,
# as these modifiers are reserved for global
# shortcuts.


# For multi-key combinations, the modifier key
# IDs must be provided as a tuple, in alphabetical
# order. For example, to specify shift+ctrl, the
# tuple must be (wx.WXK_CTRL, wx.WXK_SHIFT)
tempModeMap = {

    # Command/CTRL puts the user in zoom mode,
    # and ALT puts the user in pan mode
    OrthoViewProfile : OrderedDict((
        (('nav',   wx.WXK_CONTROL),                'zoom'),
        (('nav',   wx.WXK_ALT),                    'pan'),
        (('nav',   wx.WXK_SHIFT),                  'slice'),
        (('nav',  (wx.WXK_CONTROL, wx.WXK_SHIFT)), 'bricon'))),

    # OrthoEditProfile inherits all of the
    # settings for OrthoViewProfile above,
    # but overrides a few key ones.
    OrthoEditProfile : OrderedDict((

        # CTRL+Shift puts the 
        # user in select mode
        (('nav',    (wx.WXK_CONTROL, wx.WXK_SHIFT)), 'sel'),
        
        (('selint',  wx.WXK_CONTROL),                'zoom'),
        (('selint',  wx.WXK_ALT),                    'pan'),
        (('selint',  wx.WXK_SHIFT),                  'slice'),
        (('selint', (wx.WXK_CONTROL, wx.WXK_SHIFT)), 'sel'),
        (('selint', (wx.WXK_ALT,     wx.WXK_SHIFT)), 'chrad'),
    )),

    LightBoxViewProfile : OrderedDict((
        (('view', wx.WXK_CONTROL), 'zoom'), ))
}
"""The ``tempModeMap`` dictionary defines temporary modes, for each
:class:`Profile` sub-class which, when in a given mode, can be accessed with a
keyboard modifer (e.g. Control, Shift, etc). For example, a temporary mode map
of::

    ('view', wx.WXK_SHIFT) : 'zoom'

states that when the ``Profile`` is in ``'view'`` mode, and the shift key is
held down, the ``Profile`` should temporarily switch to ``'zoom'`` mode.
"""


altHandlerMap = {

    OrthoViewProfile : OrderedDict((
        
        # in navigate, slice, and zoom mode, the
        # left mouse button navigates, the right
        # mouse button draws a zoom rectangle,
        # and the middle button pans.
        (('nav',  'LeftMouseDown'),   ('nav',  'LeftMouseDrag')),
        (('nav',  'MiddleMouseDrag'), ('pan',  'LeftMouseDrag')),
        (('nav',  'RightMouseDown'),  ('zoom', 'RightMouseDown')),
        (('nav',  'RightMouseDrag'),  ('zoom', 'RightMouseDrag')),
        (('nav',  'RightMouseUp'),    ('zoom', 'RightMouseUp')),

        # In slice mode, the left and right
        # mouse buttons work as for nav mode.
        (('slice', 'LeftMouseDown'),   ('nav',  'LeftMouseDown')),
        (('slice', 'LeftMouseDrag'),   ('nav',  'LeftMouseDrag')),
        (('slice', 'MiddleMouseDrag'), ('pan',  'LeftMouseDrag')),
        (('slice', 'RightMouseDown'),  ('zoom', 'RightMouseDown')),
        (('slice', 'RightMouseDrag'),  ('zoom', 'RightMouseDrag')),
        (('slice', 'RightMouseUp'),    ('zoom', 'RightMouseUp')),

        # In zoom mode, the left mouse button
        # navigates, the right mouse button
        # draws a zoom rectangle, and the
        # middle mouse button pans 
        (('zoom', 'RightMouseDown'),  ('zoom', 'RightMouseDrag')),
        (('zoom', 'LeftMouseDown'),   ('nav',  'LeftMouseDown')),
        (('zoom', 'LeftMouseDrag'),   ('nav',  'LeftMouseDrag')),
        (('zoom', 'MiddleMouseDrag'), ('pan',  'LeftMouseDrag')))),

    OrthoEditProfile : OrderedDict((

        # The OrthoEditProfile is in
        # 'nav' mode by default.
        # 
        # Right mouse button allows
        # the user to select voxels
        (('nav', 'RightMouseDown'), ('sel', 'LeftMouseDown')),
        (('nav', 'RightMouseDrag'), ('sel', 'LeftMouseDrag')),
        (('nav', 'RightMouseUp'),   ('sel', 'LeftMouseUp')),

        # When in select mode (e.g. when the
        # shift key is held down), the right
        # mouse button allows the user to
        # deselect voxels.
        (('sel',    'RightMouseDown'),  ('desel',  'LeftMouseDown')),
        (('sel',    'RightMouseDrag'),  ('desel',  'LeftMouseDrag')),
        (('sel',    'RightMouseUp'),    ('desel',  'LeftMouseUp')),
        
        # Middle mouse always pans.
        (('sel',    'MiddleMouseDrag'), ('pan', 'LeftMouseDrag')),
        (('desel',  'MiddleMouseDrag'), ('pan', 'LeftMouseDrag')),
        (('selint', 'MiddleMouseDrag'), ('pan', 'LeftMouseDrag')),

        (('sel',    'MouseWheel'),      ('chsize',  'MouseWheel')),
        (('desel',  'MouseWheel'),      ('chsize',  'MouseWheel')),
        (('selint', 'MouseWheel'),      ('chthres', 'MouseWheel')),

        # Keyboard navigation works in the
        # select modes in the same way that
        # it works in navigate mode (as
        # defined in the OrthoViewProfile)
        (('sel',    'Char'), ('nav', 'Char')),
        (('desel',  'Char'), ('nav', 'Char')),
        (('selint', 'Char'), ('nav', 'Char')),
    )),

    LightBoxViewProfile : OrderedDict((
        (('view', 'LeftMouseDown'), ('view', 'LeftMouseDrag')), ))
}
"""The ``altHandlerMap`` dictionary defines alternate handlers for a given
mode and event type. Entries in this dictionary allow a :class:`.Profile`
sub-class to define a handler for a single mode and event type, but to re-use
that handler for other modes and event types. For example, the following
alternate handler mapping::

    ('zoom', 'MiddleMouseDrag'), ('pan',  'LeftMouseDrag'))

states that when the ``Profile`` is in ``'zoom'`` mode, and a
``MiddleMouseDrag`` event occurs, the ``LeftMouseDrag`` handler for the
``'pan'`` mode should be called.

.. note:: Event bindings defined in the ``altHandlerMap`` take precdence over
          the event bindings defined in the :class:`.Profile` sub-class. So
          you can use the ``altHandlerMap`` to override the default behaviour
          of a ``Profile``.
"""

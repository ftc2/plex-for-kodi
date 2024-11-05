# coding=utf-8
from .kodi_util import ADDON


def T(ID, eng=''):
    s = ADDON.getLocalizedString(ID)
    return s if s != "" else eng

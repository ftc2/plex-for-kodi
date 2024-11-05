# coding=utf-8
from kodi_six import xbmcgui, xbmc

from lib.monitor import MONITOR


def setGlobalProperty(key, val, base='script.plex.{0}', wait=False):
    xbmcgui.Window(10000).setProperty(base.format(key), val)
    if wait:
        waited = 0
        while getGlobalProperty(key) != val and waited < 2:
            if MONITOR.waitForAbort(0.1):
                break
            waited += 0.1


def setGlobalBoolProperty(key, boolean, base='script.plex.{0}'):
    xbmcgui.Window(10000).setProperty(base.format(key), boolean and '1' or '')



class IPCException(Exception):
    def __init__(self, msg, status_code=None):
        self.msg = msg
        self.status_code = status_code

    def __str__(self):
        return '{}: {}'.format(self.msg, self.status_code)


class IPCTimeoutException(IPCException):
    pass


def getGlobalProperty(key, consume=False, wait=False, interval=0.1, timeout=36000):
    resp = xbmc.getInfoLabel('Window(10000).Property(script.plex.{0})'.format(key))
    if wait and not resp:
        waited = 0
        while not MONITOR.abortRequested() and not resp and waited < timeout:
            if MONITOR.waitForAbort(interval):
                break
            resp = xbmc.getInfoLabel('Window(10000).Property(script.plex.{0})'.format(key))
            waited += 1

        if waited >= timeout:
            # timed out
            raise IPCTimeoutException('Timed out while waiting for: {}'.format(key))

    if consume:
        setGlobalProperty(key, '', wait=wait)

    return resp


def waitForGPEmpty(key, interval=0.1, timeout=36000):
    resp = xbmc.getInfoLabel('Window(10000).Property(script.plex.{0})'.format(key))
    if resp:
        waited = 0
        while not MONITOR.abortRequested() and resp and waited < timeout:
            if MONITOR.waitForAbort(interval):
                break
            resp = xbmc.getInfoLabel('Window(10000).Property(script.plex.{0})'.format(key))
            waited += 1
        if waited >= timeout:
            raise IPCTimeoutException('Timed out while waiting for emptiness of: {}'.format(key))
    return True


waitForConsumption = waitForGPEmpty
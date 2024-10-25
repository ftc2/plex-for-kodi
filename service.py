# -*- coding: utf-8 -*-
from __future__ import absolute_import

# noinspection PyUnresolvedReferences
from lib.kodi_util import xbmc, log, ADDON, getGlobalProperty, setGlobalProperty
from lib.update_checker import update_loop


def main():
    if getGlobalProperty('service.started'):
        # Prevent add-on updates from starting a new version of the addon
        return

    log('Started', realm="Service")
    setGlobalProperty('service.started', '1', wait=True)

    if ADDON.getSetting('kiosk.mode') == 'true':
        xbmc.log('script.plexmod: Starting from service (Kiosk Mode)', xbmc.LOGINFO)
        delay = ADDON.getSetting('kiosk.delay') or "0"
        xbmc.executebuiltin('RunScript(script.plexmod,1{})'.format(",{}".format(delay) if delay != "0" else ""))

    update_loop()

if __name__ == '__main__':
    main()
    log("Exited", realm="Service")

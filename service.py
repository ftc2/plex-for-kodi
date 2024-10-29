# -*- coding: utf-8 -*-
from __future__ import absolute_import

try:
    from importlib import reload
except ImportError:
    try:
        from imp import reload
    except ImportError:
        pass
        # python 2.7 has "reload" natively

import lib.update_checker as uc
import lib.kodi_util as ku
import lib.logging as lo


def main():
    if ku.getGlobalProperty('service.started'):
        # Prevent add-on updates from starting a new version of the addon
        return

    lo.service_log('Started', realm="Service")
    ku.setGlobalProperty('service.started', '1', wait=True)

    if ku.ADDON.getSetting('kiosk.mode') == 'true':
        ku.xbmc.log('script.plexmod: Starting from service (Kiosk Mode)', ku.xbmc.LOGINFO)
        delay = ku.ADDON.getSetting('kiosk.delay') or "0"
        ku.xbmc.executebuiltin('RunScript(script.plexmod,1{})'.format(",{}".format(delay) if delay != "0" else ""))

    if not ku.FROM_KODI_REPOSITORY and ku.ADDON.getSetting('auto_update_check') != "false":
        while not ku.xbmc.Monitor().abortRequested():
            # enter the update loop. if it exits positively, it wants to be reloaded
            if uc.update_loop():
                lo.service_log("Reloading update_checker due to code changes", realm="Service")
                reload(uc)
                reload(ku)
                reload(lo)

                # reload ADDON
                ku.ADDON = ku.xbmcaddon.Addon()
            else:
                # update loop didn't exit cleanly, break
                break

if __name__ == '__main__':
    main()
    lo.service_log("Exited", realm="Service")

# coding=utf-8
import os
import datetime
import json
import traceback

from lib.kodi_util import (xbmc, xbmcgui, ADDON, IPCTimeoutException, waitForGPEmpty, ICON_PATH,
                           setGlobalProperty, getGlobalProperty, KODI_VERSION_MAJOR)
from lib.settings_util import getSetting, setSetting
from lib.i18n import T
from lib.logging import service_log as log


def update_loop():
    # update checker and auto update logic
    from lib.updater import get_updater, ServiceMonitor, UpdateException, UpdaterSkipException

    monitor = ServiceMonitor()
    last_update_check = getSetting('last_update_check', datetime.datetime.fromtimestamp(0))
    check_interval = datetime.timedelta(hours=getSetting('update_interval_hours', 4))
    check_immediate = getSetting('update_check_startup', True)
    mode = getSetting('update_source', 'repository')

    updater = get_updater(mode)(branch='develop_kodi21' if KODI_VERSION_MAJOR > 18 else 'addon_kodi18')

    def should_check():
        return not any([
            xbmc.Player().isPlaying(),
            getGlobalProperty('running') != '1',
            getGlobalProperty('started') != '1',
            getGlobalProperty('is_active') != '1',
            getGlobalProperty('waiting_for_start')
        ])

    def disable_enable_addon():
        log("Toggling")
        try:
            xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled',
                                     'params': {'addonid': 'script.plexmod', 'enabled': False}}))
            xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled',
                                     'params': {'addonid': 'script.plexmod', 'enabled': True}}))
        except:
            raise

    while not getGlobalProperty('running') and not monitor.abortRequested():
        if monitor.waitForAbort(1):
            return

    log('Checking for updates periodically')

    while not monitor.abortRequested():
        now = datetime.datetime.now()

        # try consuming an update mode change
        mode_change = getGlobalProperty('update_source_changed', consume=True)
        allow_downgrade = False
        if mode_change and mode_change != mode:
            updater = get_updater(mode_change)(branch='develop_kodi21' if KODI_VERSION_MAJOR > 18 else 'addon_kodi18')
            mode = mode_change
            allow_downgrade = True
            check_immediate = True

        if (last_update_check + check_interval <= now or check_immediate) and not monitor.sleeping:
            if should_check():
                addon_version = ADDON.getAddonInfo('version')
                try:
                    pd = None
                    if check_immediate:
                        check_immediate = False

                    log('Checking for updates')
                    update_version = updater.check(addon_version, allow_downgrade=allow_downgrade)
                    log('Current: {}, Latest: {}, Update/Sidegrade/Downgrade: {}'.format(addon_version,
                                                                                         updater.remote_version,
                                                                                         update_version))

                    last_update_check = datetime.datetime.now()
                    setSetting('last_update_check', last_update_check)

                    if update_version:
                        log("Update found: {}".format(update_version))
                        # notify user in main app and wait for response
                        setGlobalProperty('update_is_downgrade', updater.is_downgrade and '1' or '', wait=True)
                        setGlobalProperty('update_available', update_version, wait=True)

                        try:
                            resp = getGlobalProperty('update_response', consume=True, wait=True)
                        except IPCTimeoutException:
                            # timed out
                            raise UpdaterSkipException('No user response')

                        log("User response: {}".format(resp))

                        if resp == "commence":
                            # wait for UI to close
                            try:
                                waitForGPEmpty('running', timeout=200)
                            except IPCTimeoutException:
                                raise UpdateException('Timeout waiting for UI to close')
                        else:
                            raise UpdaterSkipException()

                        pd = xbmcgui.DialogProgressBG()
                        pd.create("Update", message="Downloading")
                        had_already = os.path.exists(updater.archive_path)
                        if not had_already:
                            log("Update found: {}, downloading".format(update_version))
                            zip_loc = updater.download()

                            if zip_loc:
                                log("Update zip downloaded to: {}".format(zip_loc))
                        else:
                            log("Update {} previously downloaded, using previous zip".format(update_version))

                        pd.update(25, message="Unpacking")

                        dir_loc = updater.unpack()

                        has_major_changes = updater.get_major_changes()

                        pd.update(50, message="Installing")

                        if dir_loc:
                            dest_loc = updater.install(dir_loc)
                            if dest_loc:
                                log("Version {} installed. Major changes: {}".format(update_version,
                                                                                     has_major_changes))
                                pd.update(75, message="Cleaning up")
                                updater.cleanup()
                                pd.update(100, message="Preparing to start")
                                monitor.waitForAbort(1.0)

                                do_start = True
                                if has_major_changes:
                                    log("Major changes detected, prompting the user: {}".format(has_major_changes))

                                    kw = {}
                                    if KODI_VERSION_MAJOR >= 20:
                                        kw = {'defaultbutton': xbmcgui.DLG_YESNO_YES_BTN}
                                    do_start = xbmcgui.Dialog().yesno(
                                        T(33681, 'Service updated')
                                        if has_major_changes == "service" else
                                        T(33687, 'Translation updated'),
                                        (T(33682, 'The update {} has had changes to the updater itself. In '
                                                  'order for the updated updater service to work, a Kodi restart is '
                                                  'necessary. The addon will work normally, though. Do you still '
                                                  'want to run the addon?')
                                         if has_major_changes == "service" else
                                         T(33688, 'The currently in-use translation has been updated. In '
                                                  'order to load the new translation, a Kodi restart is necessary. '
                                                  'The addon will still run properly, but you might see badly or '
                                                  'untranslated strings. Do you still want to run the addon?')
                                         ).format(update_version),
                                        nolabel=T(32329, "No"),
                                        yeslabel=T(32328, "Yes"),
                                        **kw
                                    )

                                xbmc.executebuiltin('UpdateLocalAddons', True)
                                xbmc.executebuiltin('ActivateWindow(Home)', True)
                                pd.close()
                                del pd
                                #disable_enable_addon()

                                if do_start:
                                    xbmc.executebuiltin('RunScript(script.plexmod,0,0,1)')

                except UpdateException as e:
                    log(e, xbmc.LOGWARNING)

                except UpdaterSkipException:
                    log("Update skipped")

                except Exception as e:
                    log(traceback.format_exc(), xbmc.LOGERROR)
                    xbmc.executebuiltin('Notification({0},"{1}",{2},{3})'.format("Update",
                                                                               "Update failed, see log, not starting.",
                                                                               5000,
                                                                               ICON_PATH))

                finally:
                    setGlobalProperty('update_available', '')
                    setGlobalProperty('update_response', '')
                    setGlobalProperty('update_source_changed', '')
                    setGlobalProperty('update_is_downgrade', '')
                    # lel
                    try:
                        if pd:
                            try:
                                pd.close()
                                del pd
                            except:
                                pass
                    except:
                        pass

        # tick every two seconds if home or settings windows are active, otherwise every 10
        interval = getGlobalProperty('active_window') in ("HomeWindow", "SettingsWindow") and 2 or 10
        if monitor.waitForAbort(interval):
            break

        if not getSetting('auto_update_check', True):
            break

# coding=utf-8

import math
from six import ensure_str
from plexnet import util as pnUtil

from lib import util
from lib.data_cache import dcm
from lib.util import T
from lib.genres import GENRES_TV_BY_SYN
from . import busy
from . import kodigui
from . import optionsdialog
from . import playersettings


class SeasonsMixin(object):
    SEASONS_CONTROL_ATTR = "subItemListControl"

    THUMB_DIMS = {
        'show': {
            'main.thumb': util.scaleResolution(347, 518),
            'item.thumb': util.scaleResolution(174, 260)
        },
        'episode': {
            'main.thumb': util.scaleResolution(347, 518),
            'item.thumb': util.scaleResolution(198, 295)
        },
        'artist': {
            'main.thumb': util.scaleResolution(519, 519),
            'item.thumb': util.scaleResolution(215, 215)
        }
    }

    def _createListItem(self, mediaItem, obj):
        mli = kodigui.ManagedListItem(
            obj.title or '',
            thumbnailImage=obj.defaultThumb.asTranscodedImageURL(*self.THUMB_DIMS[mediaItem.type]['item.thumb']),
            data_source=obj
        )
        return mli

    def getSeasonProgress(self, show, season):
        """
        calculates the season progress based on how many episodes are watched and, optionally, if there's an episode
        in progress, take that into account as well
        """
        watchedPerc = season.viewedLeafCount.asInt() / season.leafCount.asInt() * 100
        for v in show.onDeck:
            if v.parentRatingKey == season.ratingKey and v.viewOffset:
                vPerc = int((v.viewOffset.asInt() / v.duration.asFloat()) * 100)
                watchedPerc += vPerc / season.leafCount.asFloat()
        return watchedPerc > 0 and math.ceil(watchedPerc) or 0

    def fillSeasons(self, show, update=False, seasonsFilter=None, selectSeason=None, do_focus=True):
        seasons = show.seasons()
        if not seasons or (seasonsFilter and not seasonsFilter(seasons)):
            return False

        items = []
        idx = 0
        focus = None
        for season in seasons:
            if selectSeason and season == selectSeason:
                continue

            mli = self._createListItem(show, season)
            if mli:
                mli.setProperty('index', str(idx))
                mli.setProperty('thumb.fallback', 'script.plex/thumb_fallbacks/show.png')
                mli.setProperty('unwatched.count', not season.isWatched and str(season.unViewedLeafCount) or '')
                mli.setBoolProperty('unwatched.count.large', not season.isWatched and season.unViewedLeafCount > 999)
                mli.setBoolProperty('watched', season.isFullyWatched)
                if not season.isWatched and focus is None and season.index.asInt() > 0:
                    focus = idx
                    mli.setProperty('progress', util.getProgressImage(None, self.getSeasonProgress(show, season)))
                items.append(mli)
                idx += 1

        subItemListControl = getattr(self, self.SEASONS_CONTROL_ATTR)
        if update:
            subItemListControl.replaceItems(items)
        else:
            subItemListControl.reset()
            subItemListControl.addItems(items)

        if focus is not None and do_focus:
            subItemListControl.setSelectedItemByPos(focus)

        return True


class DeleteMediaMixin(object):
    def delete(self, item=None):
        item = item or self.mediaItem
        button = optionsdialog.show(
            T(32326, 'Really delete?'),
            T(33035, "Delete {}: {}?").format(type(item).__name__, item.defaultTitle),
            T(32328, 'Yes'),
            T(32329, 'No')
        )

        if button != 0:
            return

        if not self._delete(item=item):
            util.messageDialog(T(32330, 'Message'), T(32331, 'There was a problem while attempting to delete the media.'))
            return
        return True

    @busy.dialog()
    def _delete(self, item, do_close=False):
        success = item.delete()
        util.LOG('Media DELETE: {0} - {1}', item, success and 'SUCCESS' or 'FAILED')
        if success and do_close:
            self.doClose()
        return success


class RatingsMixin(object):
    def populateRatings(self, video, ref, hide_ratings=False):
        def sanitize(src):
            return src.replace("themoviedb", "tmdb").replace('://', '/')

        setProperty = getattr(ref, "setProperty")
        getattr(ref, "setProperties")(('rating.stars', 'rating', 'rating.image', 'rating2', 'rating2.image'), '')

        if video.userRating:
            stars = str(int(round((video.userRating.asFloat() / 10) * 5)))
            setProperty('rating.stars', stars)

        if hide_ratings:
            return

        if video.TYPE == "movie" and "movies" not in util.getSetting("show_ratings"):
            return

        if (video.TYPE in ("episode", "show", "season") and
                "series" not in util.getSetting("show_ratings")):
            return

        audienceRating = video.audienceRating

        if video.rating or audienceRating:
            if video.rating:
                rating = video.rating
                if video.ratingImage.startswith('rottentomatoes:'):
                    rating = '{0}%'.format(int(rating.asFloat() * 10))

                setProperty('rating', rating)
                if video.ratingImage:
                    setProperty('rating.image', 'script.plex/ratings/{0}.png'.format(sanitize(video.ratingImage)))
            if audienceRating:
                if video.audienceRatingImage.startswith('rottentomatoes:'):
                    audienceRating = '{0}%'.format(int(audienceRating.asFloat() * 10))
                setProperty('rating2', audienceRating)
                if video.audienceRatingImage:
                    setProperty('rating2.image',
                                'script.plex/ratings/{0}.png'.format(sanitize(video.audienceRatingImage)))
        else:
            setProperty('rating', video.rating)


class SpoilersMixin(object):
    def __init__(self, *args, **kwargs):
        self._noSpoilers = None
        self.spoilerSetting = ["unwatched"]
        self.noTitles = False
        self.noRatings = False
        self.noImages = False
        self.noResumeImages = False
        self.noSummaries = False
        self.spoilersAllowedFor = True
        self.cacheSpoilerSettings()

    def cacheSpoilerSettings(self):
        self.spoilerSetting = util.getSetting('no_episode_spoilers4')
        self.noTitles = 'no_unwatched_episode_titles' in self.spoilerSetting
        self.noRatings = 'hide_ratings' in self.spoilerSetting
        self.noImages = 'blur_images' in self.spoilerSetting
        self.noResumeImages = 'blur_resume_images' in self.spoilerSetting
        self.noSummaries = 'hide_summary' in self.spoilerSetting
        self.spoilersAllowedFor = util.getSetting('spoilers_allowed_genres2')

    @property
    def noSpoilers(self):
        return self.getNoSpoilers()

    def getCachedGenres(self, rating_key):
        genres = dcm.getCacheData("show_genres", rating_key)
        if genres:
            return [pnUtil.AttributeDict(tag=g) for g in genres]

    def getNoSpoilers(self, item=None, show=None):
        """
        when called without item or show, retains a global noSpoilers value, otherwise return dynamically based on item
        or show
        returns: "off" if spoilers unnecessary, otherwise "unwatched" or "funwatched"
        """
        if not item and not show and self._noSpoilers is not None:
            return self._noSpoilers

        if item and item.type != "episode":
            return "off"

        nope = "funwatched" if "in_progress" in self.spoilerSetting else "unwatched" \
            if "unwatched" in self.spoilerSetting else "off"

        if nope != "off" and self.spoilersAllowedFor:
            # instead of making possibly multiple separate API calls to find genres for episode's shows, try to get
            # a cached value instead
            genres = []
            if item or show:
                genres = self.getCachedGenres(item and item.grandparentRatingKey or show.ratingKey)

            if not genres:
                show = getattr(self, "show_", show or (item and item.show()) or None)
                if not show:
                    return "off"

            if not genres and show:
                genres = show.genres()

            for g in genres:
                main_tag = GENRES_TV_BY_SYN.get(g.tag)
                if main_tag and main_tag in self.spoilersAllowedFor:
                    nope = "off"
                    break

        if item or show:
            self._noSpoilers = nope
            return self._noSpoilers
        return nope

    def hideSpoilers(self, ep, fully_watched=None, watched=None, use_cache=True):
        """
        returns boolean on whether we should hide spoilers for the given episode
        """
        watched = watched if watched is not None else ep.isWatched
        fullyWatched = fully_watched if fully_watched is not None else ep.isFullyWatched
        nspoil = self.getNoSpoilers(item=ep if not use_cache else None)
        return ((nspoil == 'funwatched' and not fullyWatched) or
                (nspoil == 'unwatched' and not watched))

    def getThumbnailOpts(self, ep, fully_watched=None, watched=None, hide_spoilers=None):
        if not self.noImages or self.getNoSpoilers(item=ep) == "off":
            return {}
        return (hide_spoilers if hide_spoilers is not None else
                self.hideSpoilers(ep, fully_watched=fully_watched, watched=watched)) \
            and {"blur": util.addonSettings.episodeNoSpoilerBlur} or {}


class PlaybackBtnMixin(object):
    def __init__(self, *args, **kwargs):
        self.playBtnClicked = False

    def reset(self, *args, **kwargs):
        self.playBtnClicked = False

    def onReInit(self):
        self.playBtnClicked = False


PLEX_LEGACY_LANGUAGE_MAP = {
    "pb": ("pt", "pt-BR"),
}


class PlexSubtitleDownloadMixin(object):
    def __init__(self, *args, **kwargs):
        super(PlexSubtitleDownloadMixin, self).__init__()

    @staticmethod
    def get_subtitle_language_tuple():
        from iso639 import languages
        lang_code_parse, lang_code = PLEX_LEGACY_LANGUAGE_MAP.get(pnUtil.ACCOUNT.subtitlesLanguage,
                                                                  (pnUtil.ACCOUNT.subtitlesLanguage,
                                                                   pnUtil.ACCOUNT.subtitlesLanguage))
        language = languages.get(part1=lang_code_parse)
        return language, lang_code_parse, lang_code


    def downloadPlexSubtitles(self, video, non_playback=False):
        """

        @param video:
        @return: False if user backed out, None if no subtitles found, or the downloaded subtitle stream
        """
        language, lang_code_parse, lang_code = PlexSubtitleDownloadMixin.get_subtitle_language_tuple()


        util.DEBUG_LOG("Using language {} for subtitle search", ensure_str(str(language.name)))

        subs = None
        with busy.BusyBlockingContext(delay=True):
            subs = video.findSubtitles(language=lang_code,
                                       hearing_impaired=pnUtil.ACCOUNT.subtitlesSDH,
                                       forced=pnUtil.ACCOUNT.subtitlesForced)

        if subs:
            with kodigui.WindowProperty(self, 'settings.visible', '1'):
                options = []
                for sub in sorted(subs, key=lambda s: s.score.asInt(), reverse=True):
                    info = ""
                    if sub.hearingImpaired.asInt() or sub.forced.asInt():
                        add = []
                        if sub.hearingImpaired.asInt():
                            add.append(T(33698, "HI"))
                        if sub.forced.asInt():
                            add.append(T(33699, "forced"))
                        info = " ({})".format(", ".join(add))
                    options.append((sub.key, (T(33697, "{provider_title}, Score: {subtitle_score}{subtitle_info}").format(
                        provider_title=sub.providerTitle,
                        subtitle_score=sub.score,
                        subtitle_info=info), sub.title)))
                choice = playersettings.showOptionsDialog(T(33700, "Download subtitles: {}").format(ensure_str(language.name)),
                                                          options, trim=False, non_playback=non_playback)
                if choice is None:
                    return False

                with busy.BusyBlockingContext(delay=True):
                    video.downloadSubtitles(choice)
                    tries = 0
                    sub_downloaded = False
                    util.DEBUG_LOG("Waiting for subtitle download: {}", choice)
                    while tries < 50:
                        for stream in video.findSubtitles(language=lang_code,
                                                          hearing_impaired=pnUtil.ACCOUNT.subtitlesSDH,
                                                          forced=pnUtil.ACCOUNT.subtitlesForced):
                            if stream.downloaded.asBool():
                                util.DEBUG_LOG("Subtitle downloaded: {}", stream.extendedDisplayTitle)
                                sub_downloaded = stream
                                break
                        if sub_downloaded:
                            break
                        tries += 1
                        util.MONITOR.waitForAbort(0.1)
                    # stream will be auto selected
                    video.reload(includeExternalMedia=1, includeChapters=1, skipRefresh=1)
                    # reselect fresh media
                    media = [m for m in video.media() if m.ratingKey == video.mediaChoice.media.ratingKey][0]
                    video.setMediaChoice(media=media, partIndex=video.mediaChoice.partIndex)
                    # double reload is probably not necessary
                    video.reload(fromMediaChoice=True, forceSubtitlesFromPlex=True, skipRefresh=1)
                    for stream in video.subtitleStreams:
                        if stream.selected.asBool():
                            util.DEBUG_LOG("Selecting subtitle: {}", stream.extendedDisplayTitle)
                            return stream
        else:
            util.showNotification(util.T(33696, "No Subtitles found."),
                                  time_ms=1500, header=util.T(32396, "Subtitles"))

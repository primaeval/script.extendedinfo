# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

import urllib
import urllib2
import os
import time
import hashlib
import json
import re
import threading
import datetime
from functools import wraps

import xbmc
import xbmcgui
import xbmcvfs

import addon


def run_async(func):
    """
    Decorator to run a function in a separate thread
    """
    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func,
                                   args=args,
                                   kwargs=kwargs)
        func_hl.start()
        return func_hl

    return async_func


def busy_dialog(func):
    """
    Decorator to show busy dialog while function is running
    Only one of the decorated functions may run simultaniously
    """

    @wraps(func)
    def decorator(self, *args, **kwargs):
        xbmc.executebuiltin("ActivateWindow(busydialog)")
        result = func(self, *args, **kwargs)
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        return result

    return decorator


def dictfind(lst, key, value):
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return dic
    return ""


def get_infolabel(name):
    return xbmc.getInfoLabel(name).decode("utf-8")


def format_time(time, time_format=None):
    """
    get formatted time
    time_format = h, m or None
    """
    try:
        intTime = int(time)
    except Exception:
        return time
    hour = str(intTime / 60)
    minute = str(intTime % 60).zfill(2)
    if time_format == "h":
        return hour
    elif time_format == "m":
        return minute
    elif intTime >= 60:
        return hour + " h " + minute + " min"
    else:
        return minute + " min"


def merge_dicts(*dict_args):
    '''
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    '''
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def check_version():
    """
    check version, open TextViewer if update detected
    """
    if not addon.setting("changelog_version") == addon.VERSION:
        xbmcgui.Dialog().textviewer(heading=addon.LANG(24036),
                                    text=read_from_file(os.path.join(addon.PATH, "changelog.txt"), True))
        addon.set_setting("changelog_version", addon.VERSION)
    if not addon.setting("first_start_infodialog"):
        addon.set_setting("first_start_infodialog", "True")
        xbmcgui.Dialog().ok(heading=addon.NAME,
                            line1=addon.LANG(32140),
                            line2=addon.LANG(32141))


def calculate_age(born, died=False):
    """
    calculate age based on born / died
    display notification for birthday
    return death age when already dead
    """
    if died:
        ref_day = died.split("-")
    elif born:
        date = datetime.date.today()
        ref_day = [date.year, date.month, date.day]
    else:
        return ""
    actor_born = born.split("-")
    base_age = int(ref_day[0]) - int(actor_born[0])
    if len(actor_born) > 1:
        diff_months = int(ref_day[1]) - int(actor_born[1])
        diff_days = int(ref_day[2]) - int(actor_born[2])
        if diff_months < 0 or (diff_months == 0 and diff_days < 0):
            base_age -= 1
        elif diff_months == 0 and diff_days == 0 and not died:
            notify("%s (%i)" % (addon.LANG(32158), base_age))
    return base_age


def millify(n):
    """
    make large numbers human-readable, return string
    """
    millnames = [' ', '.000', ' ' + addon.LANG(32000), ' ' + addon.LANG(32001), ' ' + addon.LANG(32002)]
    if not n or n <= 100:
        return ""
    n = float(n)
    char_count = len(str(n))
    millidx = (char_count / 3) - 1
    if millidx == 3 or char_count == 9:
        return '%.2f%s' % (n / 10 ** (3 * millidx), millnames[millidx])
    else:
        return '%.0f%s' % (n / 10 ** (3 * millidx), millnames[millidx])


def media_streamdetails(filename, streamdetails):
    info = {}
    video = streamdetails['video']
    audio = streamdetails['audio']
    if video:
        if (video[0]['width'] <= 720 and video[0]['height'] <= 480):
            info['VideoResolution'] = "480"
        elif (video[0]['width'] <= 768 and video[0]['height'] <= 576):
            info['VideoResolution'] = "576"
        elif (video[0]['width'] <= 960 and video[0]['height'] <= 544):
            info['VideoResolution'] = "540"
        elif (video[0]['width'] <= 1280 and video[0]['height'] <= 720):
            info['VideoResolution'] = "720"
        elif (video[0]['width'] >= 1281 or video[0]['height'] >= 721):
            info['VideoResolution'] = "1080"
        else:
            info['videoresolution'] = ""
        info['VideoCodec'] = str(video[0]['codec'])
        if (video[0]['aspect'] < 1.4859):
            info['VideoAspect'] = "1.33"
        elif (video[0]['aspect'] < 1.7190):
            info['VideoAspect'] = "1.66"
        elif (video[0]['aspect'] < 1.8147):
            info['VideoAspect'] = "1.78"
        elif (video[0]['aspect'] < 2.0174):
            info['VideoAspect'] = "1.85"
        elif (video[0]['aspect'] < 2.2738):
            info['VideoAspect'] = "2.20"
        else:
            info['VideoAspect'] = "2.35"
    elif (('bluray' or 'blu-ray' or 'brrip' or 'bdrip' or 'hddvd' or 'hd-dvd') in filename):
        info['VideoResolution'] = '1080'
    elif ('dvd' in filename) or (filename.endswith('.vob' or '.ifo')):
        info['VideoResolution'] = '576'
    if audio:
        info['AudioCodec'] = audio[0]['codec']
        info['AudioChannels'] = audio[0]['channels']
    return info


def get_year(year_string):
    """
    return last 4 chars of string
    """
    if year_string and len(year_string) > 3:
        return year_string[:4]
    else:
        return ""


def fetch_musicbrainz_id(artist, artist_id=-1):
    """
    fetches MusicBrainz ID for given *artist and returns it
    uses musicbrainz.org
    """
    base_url = "http://musicbrainz.org/ws/2/artist/?fmt=json"
    url = '&query=artist:%s' % urllib.quote_plus(artist)
    results = get_JSON_response(url=base_url + url,
                                cache_days=30,
                                folder="MusicBrainz")
    if results and len(results["artists"]) > 0:
        log("found artist id for %s: %s" % (artist, results["artists"][0]["id"]))
        return results["artists"][0]["id"]
    else:
        return None


def get_http(url=None, headers=False):
    """
    fetches data from *url, returns it as a string
    """
    succeed = 0
    if not headers:
        headers = {'User-agent': 'XBMC/17.0 ( phil65@kodi.tv )'}
    request = urllib2.Request(url)
    for (key, value) in headers.iteritems():
        request.add_header(key, value)
    while (succeed < 2) and (not xbmc.abortRequested):
        try:
            response = urllib2.urlopen(request, timeout=3)
            return response.read()
        except Exception:
            log("get_http: could not get data from %s" % url)
            xbmc.sleep(1000)
            succeed += 1
    return None


def get_JSON_response(url="", cache_days=7.0, folder=False, headers=False):
    """
    get JSON response for *url, makes use of prop and file cache.
    """
    now = time.time()
    hashed_url = hashlib.md5(url).hexdigest()
    if folder:
        cache_path = xbmc.translatePath(os.path.join(addon.DATA_PATH, folder))
    else:
        cache_path = xbmc.translatePath(os.path.join(addon.DATA_PATH))
    path = os.path.join(cache_path, hashed_url + ".txt")
    cache_seconds = int(cache_days * 86400.0)
    prop_time = addon.get_global(hashed_url + "_timestamp")
    if prop_time and now - float(prop_time) < cache_seconds:
        try:
            prop = json.loads(addon.get_global(hashed_url))
            # log("prop load for %s. time: %f" % (url, time.time() - now))
            if prop:
                return prop
        except Exception:
            # log("could not load prop data for %s" % url)
            pass
    if xbmcvfs.exists(path) and ((now - os.path.getmtime(path)) < cache_seconds):
        results = read_from_file(path)
        # log("loaded file for %s. time: %f" % (url, time.time() - now))
    else:
        response = get_http(url, headers)
        try:
            results = json.loads(response)
            # log("download %s. time: %f" % (url, time.time() - now))
            save_to_file(results, hashed_url, cache_path)
        except Exception:
            log("Exception: Could not get new JSON data from %s. Tryin to fallback to cache" % url)
            log(response)
            results = read_from_file(path) if xbmcvfs.exists(path) else []
    if not results:
        return []
    addon.set_global(hashed_url + "_timestamp", str(now))
    addon.set_global(hashed_url, json.dumps(results))
    return results


class FunctionThread(threading.Thread):

    def __init__(self, function=None, param=None):
        threading.Thread.__init__(self)
        self.function = function
        self.param = param
        self.setName(self.function.__name__)
        log("init " + self.function.__name__)

    def run(self):
        self.listitems = self.function(self.param)
        return True


def get_file(url):
    clean_url = xbmc.translatePath(urllib.unquote(url)).replace("image://", "")
    if clean_url.endswith("/"):
        clean_url = clean_url[:-1]
    cached_thumb = xbmc.getCacheThumbName(clean_url)
    vid_cache_file = os.path.join("special://profile/Thumbnails/Video", cached_thumb[0], cached_thumb)
    cache_file_jpg = os.path.join("special://profile/Thumbnails/", cached_thumb[0], cached_thumb[:-4] + ".jpg").replace("\\", "/")
    cache_file_png = cache_file_jpg[:-4] + ".png"
    if xbmcvfs.exists(cache_file_jpg):
        log("cache_file_jpg Image: " + url + "-->" + cache_file_jpg)
        return xbmc.translatePath(cache_file_jpg)
    elif xbmcvfs.exists(cache_file_png):
        log("cache_file_png Image: " + url + "-->" + cache_file_png)
        return cache_file_png
    elif xbmcvfs.exists(vid_cache_file):
        log("vid_cache_file Image: " + url + "-->" + vid_cache_file)
        return vid_cache_file
    try:
        request = urllib2.Request(url)
        request.add_header('Accept-encoding', 'gzip')
        response = urllib2.urlopen(request, timeout=3)
        data = response.read()
        response.close()
        log('image downloaded: ' + url)
    except Exception:
        log('image download failed: ' + url)
        return ""
    if not data:
        return ""
    image = cache_file_png if url.endswith(".png") else cache_file_jpg
    try:
        with open(xbmc.translatePath(image), "wb") as f:
            f.write(data)
        return xbmc.translatePath(image)
    except Exception:
        log('failed to save image ' + url)
        return ""


def get_favs_by_type(fav_type):
    """
    returns dict list containing favourites with type *fav_type
    """
    return [fav for fav in get_favs() if fav["Type"] == fav_type]


def get_fav_path(fav):
    if fav["type"] == "media":
        return "PlayMedia(%s)" % (fav["path"])
    elif fav["type"] == "script":
        return "RunScript(%s)" % (fav["path"])
    elif "window" in fav and "windowparameter" in fav:
        return "ActivateWindow(%s,%s)" % (fav["window"], fav["windowparameter"])
    else:
        log("error parsing favs")


def get_favs():
    """
    returns dict list containing favourites
    """
    items = []
    data = get_kodi_json(method="Favourites.GetFavourites",
                         params='{"type": null, "properties": ["path", "thumbnail", "window", "windowparameter"]}')
    if "result" not in data or data["result"]["limits"]["total"] == 0:
        return []
    for fav in data["result"]["favourites"]:
        path = get_fav_path(fav)
        items.append({'label': fav["title"],
                      'thumb': fav["thumbnail"],
                      'Type': fav["type"],
                      'Builtin': path,
                      'path': "plugin://script.extendedinfo/?info=action&&id=" + path})
    return items


def get_icon_panel(number):
    """
    get icon panel with index *number, returns dict list based on skin strings
    """
    items = []
    offset = number * 5 - 5
    for i in xrange(1, 6):
        infopanel_path = get_skin_string("IconPanelItem%i.Path" % (i + offset))
        items.append({'label': get_skin_string("IconPanelItem%i.Label" % (i + offset)),
                      'path': "plugin://script.extendedinfo/?info=action&&id=" + infopanel_path,
                      'thumb': get_skin_string("IconPanelItem%i.Icon" % (i + offset)),
                      'id': "IconPanelitem%i" % (i + offset),
                      'Type': get_skin_string("IconPanelItem%i.Type" % (i + offset))})
    return items


def get_skin_string(name):
    return xbmc.getInfoLabel("Skin.String(%s)").decode("utf-8")


def set_skin_string(name, value):
    xbmc.executebuiltin("Skin.SetString(%s, %s)" % (name, value))


def log(txt):
    if isinstance(txt, str):
        txt = txt.decode("utf-8", 'ignore')
    message = u'%s: %s' % (addon.ID, txt)
    xbmc.log(msg=message.encode("utf-8", 'ignore'),
             level=xbmc.LOGDEBUG)


def get_browse_dialog(default="", heading=addon.LANG(1024), dlg_type=3, shares="files", mask="", use_thumbs=False, treat_as_folder=False):
    return xbmcgui.Dialog().browse(dlg_type, heading, shares, mask, use_thumbs, treat_as_folder, default)


def save_to_file(content, filename, path=""):
    """
    dump json and save to *filename in *path
    """
    if path == "":
        text_file_path = get_browse_dialog() + filename + ".txt"
    else:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
        text_file_path = os.path.join(path, filename + ".txt")
    now = time.time()
    text_file = xbmcvfs.File(text_file_path, "w")
    json.dump(content, text_file)
    text_file.close()
    # log("saved textfile %s. Time: %f" % (text_file_path, time.time() - now))
    return True


def read_from_file(path="", raw=False):
    """
    return data from file with *path
    """
    if path == "":
        path = get_browse_dialog(dlg_type=1)
    if not xbmcvfs.exists(path):
        return False
    try:
        with open(path) as f:
            # log("opened textfile %s." % (path))
            if not raw:
                result = json.load(f)
            else:
                result = f.read()
        return result
    except Exception:
        log("failed to load textfile: " + path)
        return False


def convert_youtube_url(raw_string):
    youtube_id = extract_youtube_id(raw_string)
    if youtube_id:
        return 'plugin://script.extendedinfo/?info=youtubevideo&&id=%s' % youtube_id
    return ""


def extract_youtube_id(raw_string):
    vid_ids = None
    if raw_string and 'youtube.com/v' in raw_string:
        vid_ids = re.findall('http://www.youtube.com/v/(.{11})\??', raw_string, re.DOTALL)
    elif raw_string and 'youtube.com/watch' in raw_string:
        vid_ids = re.findall('youtube.com/watch\?v=(.{11})\??', raw_string, re.DOTALL)
    if vid_ids:
        return vid_ids[0]
    else:
        return ""


def notify(header="", message="", icon=addon.ICON, time=5000, sound=True):
    xbmcgui.Dialog().notification(heading=header,
                                  message=message,
                                  icon=icon,
                                  time=time,
                                  sound=sound)


def get_kodi_json(method, params):
    json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": %s, "id": 1}' % (method, params))
    json_query = unicode(json_query, 'utf-8', errors='ignore')
    return json.loads(json_query)


def prettyprint(string):
    log(json.dumps(string,
                   sort_keys=True,
                   indent=4,
                   separators=(',', ': ')))


def pass_dict_to_skin(data=None, prefix="", window_id=10000):
    window = xbmcgui.Window(window_id)
    if not data:
        return None
    for (key, value) in data.iteritems():
        if not value:
            continue
        value = unicode(value)
        window.setProperty('%s%s' % (prefix, key), value)


def listitem_to_windowprops(data=None, prefix="", window_id=10000):
    window = xbmcgui.Window(window_id)
    if not data:
        return None
    keys = ["artwork", "infos", "properties"]
    window.setProperty('%slabel' % (prefix), data.get("label"))
    window.setProperty('%spath' % (prefix), data.get("path"))
    for key in keys:
        for (k, v) in data.get(key, {}).iteritems():
            if not v:
                continue
            window.setProperty('%s%s' % (prefix, k), unicode(v))


def merge_dict_lists(items, key="job"):
    crew_ids = []
    crews = []
    for item in items:
        if item["properties"]["id"] not in crew_ids:
            crew_ids.append(item["properties"]["id"])
            crews.append(item)
        else:
            index = crew_ids.index(item["properties"]["id"])
            if key in crews[index]:
                crews[index][key] = crews[index][key] + " / " + item[key]
    return crews


def set_window_props(name, data, prefix=""):
    if not data:
        addon.set_global('%s%s.Count' % (prefix, name), '0')
        log("%s%s.Count = None" % (prefix, name))
        return None
    for (count, result) in enumerate(data):
        for (key, value) in result.iteritems():
            value = unicode(value)
            addon.set_global('%s%s.%i.%s' % (prefix, name, count + 1, key), value)
        for key, value in result.get("properties", {}).iteritems():
            if not value:
                continue
            addon.set_global('%s%s.%i.%s' % (prefix, name, count + 1, key), value)
    addon.set_global('%s%s.Count' % (prefix, name), str(len(data)))


def create_listitems(data=None, preload_images=0):
    if not data:
        return []
    itemlist = []
    for (count, result) in enumerate(data):
        listitem = xbmcgui.ListItem(label=result.get("label", ""),
                                    label2=result.get("label2", ""),
                                    path=result.get("path", ""))
        if "properties" in result:
            props = {k: unicode(v) for k, v in result["properties"].items() if v}
            for key, value in props.iteritems():
                listitem.setProperty(key, unicode(value))
        if "artwork" in result:
            artwork = {k: v.replace("https://", "http://") for k, v in result["artwork"].items() if v}
            listitem.setArt(artwork)
        if "infos" in result:
            infos = {k.lower(): v for k, v in result["infos"].items() if v}
            listitem.setInfo("video", infos)
        if "videoinfo" in result:
            infos = {k.lower(): v for k, v in result["videoinfo"].items() if v}
            listitem.addStreamInfo("video", infos)
        if "audioinfo" in result:
            infos = {k.lower(): v for k, v in result["audioinfo"].items() if v}
            listitem.addStreamInfo("audio", infos)
        listitem.setProperty("index", str(count))
        itemlist.append(listitem)
    return itemlist


def clean_text(text):
    if not text:
        return ""
    text = re.sub('(From Wikipedia, the free encyclopedia)|(Description above from the Wikipedia.*?Wikipedia)', '', text)
    text = re.sub('<(.|\n|\r)*?>', '', text)
    text = text.replace('<br \/>', '[CR]')
    text = text.replace('<em>', '[I]').replace('</em>', '[/I]')
    text = text.replace('&amp;', '&')
    text = text.replace('&gt;', '>').replace('&lt;', '<')
    text = text.replace('&#39;', "'").replace('&quot;', '"')
    text = re.sub("\n\\.$", "", text)
    text = text.replace('User-contributed text is available under the Creative Commons By-SA License and may also be available under the GNU FDL.', '')
    while text:
        s = text[0]
        e = text[-1]
        if s in [u'\u200b', " ", "\n"]:
            text = text[1:]
        elif e in [u'\u200b', " ", "\n"]:
            text = text[:-1]
        elif s.startswith(".") and not s.startswith(".."):
            text = text[1:]
        else:
            break
    return text.strip()

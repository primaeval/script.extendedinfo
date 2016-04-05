# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

import json
import itertools
import KodiJson
import Utils
import addon
import time


class LocalDB(object):

    def __init__(self, *args, **kwargs):
        self.movie_imdbs = []
        self.movie_ids = []
        self.movie_titles = []
        self.movie_otitles = []
        self.tvshow_ids = []
        self.tvshow_originaltitles = []
        self.tvshow_titles = []
        self.tvshow_imdbs = []
        self.artists = []
        self.albums = []

    def get_artists(self):
        self.artists = KodiJson.get_artists(properties=["musicbrainzartistid", "thumbnail"])
        return self.artists

    def get_similar_artists(self, artist_id):
        import LastFM
        simi_artists = LastFM.get_similar_artists(artist_id)
        if simi_artists is None:
            Utils.log('Last.fm didn\'t return proper response')
            return None
        if not self.artists:
            self.artists = self.get_artists()
        artists = []
        for simi_artist, kodi_artist in itertools.product(simi_artists, self.artists):
            if kodi_artist['musicbrainzartistid'] and kodi_artist['musicbrainzartistid'] == simi_artist['mbid']:
                artists.append(kodi_artist)
            elif kodi_artist['artist'] == simi_artist['name']:
                data = Utils.get_kodi_json(method="AudioLibrary.GetArtistDetails",
                                           params='{"properties": ["genre", "description", "mood", "style", "born", "died", "formed", "disbanded", "yearsactive", "instrument", "fanart", "thumbnail"], "artistid": %s}' % str(kodi_artist['artistid']))
                item = data["result"]["artistdetails"]
                artwork = {"thumb": item['thumbnail'],
                           "fanart": item['fanart']}
                artists.append({"label": item['label'],
                                "artwork": artwork,
                                "title": item['label'],
                                "Genre": " / ".join(item['genre']),
                                "Artist_Description": item['description'],
                                "userrating": item['userrating'],
                                "Born": item['born'],
                                "Died": item['died'],
                                "Formed": item['formed'],
                                "Disbanded": item['disbanded'],
                                "YearsActive": " / ".join(item['yearsactive']),
                                "Style": " / ".join(item['style']),
                                "Mood": " / ".join(item['mood']),
                                "Instrument": " / ".join(item['instrument']),
                                "LibraryPath": 'musicdb://artists/%s/' % item['artistid']})
        Utils.log('%i of %i artists found in last.FM are in Kodi database' % (len(artists), len(simi_artists)))
        return artists

    def get_similar_movies(self, dbid):
        movie = Utils.get_kodi_json(method="VideoLibrary.GetMovieDetails",
                                    params='{"properties": ["genre","director","country","year","mpaa"], "movieid":%s }' % dbid)
        if "moviedetails" not in movie['result']:
            return []
        comp_movie = movie['result']['moviedetails']
        genres = comp_movie['genre']
        data = Utils.get_kodi_json(method="VideoLibrary.GetMovies",
                                   params='{"properties": ["genre","director","mpaa","country","year"], "sort": { "method": "random" } }')
        if "movies" not in data['result']:
            return []
        quotalist = []
        for item in data['result']['movies']:
            item["mediatype"] = "movie"
            diff = abs(int(item['year']) - int(comp_movie['year']))
            hit = 0.0
            miss = 0.00001
            quota = 0.0
            for genre in genres:
                if genre in item['genre']:
                    hit += 1.0
                else:
                    miss += 1.0
            if hit > 0.0:
                quota = float(hit) / float(hit + miss)
            if genres and item['genre'] and genres[0] == item['genre'][0]:
                quota += 0.3
            if diff < 3:
                quota += 0.3
            elif diff < 6:
                quota += 0.15
            if comp_movie['country'] and item['country'] and comp_movie['country'][0] == item['country'][0]:
                quota += 0.4
            if comp_movie['mpaa'] and item['mpaa'] and comp_movie['mpaa'] == item['mpaa']:
                quota += 0.4
            if comp_movie['director'] and item['director'] and comp_movie['director'][0] == item['director'][0]:
                quota += 0.6
            quotalist.append((quota, item["movieid"]))
        quotalist = sorted(quotalist,
                           key=lambda quota: quota[0],
                           reverse=True)
        movies = []
        for i, list_movie in enumerate(quotalist):
            if comp_movie['movieid'] is not list_movie[1]:
                newmovie = self.get_movie(list_movie[1])
                movies.append(newmovie)
                if i == 20:
                    break
        return movies

    def get_movies(self, filter_str="", limit=10):
        props = '"properties": ["title", "originaltitle", "votes", "playcount", "year", "genre", "studio", "country", "tagline", "plot", "runtime", "file", "plotoutline", "lastplayed", "trailer", "rating", "resume", "art", "streamdetails", "mpaa", "director", "writer", "cast", "dateadded", "imdbnumber"]'
        data = Utils.get_kodi_json(method="VideoLibrary.GetMovies",
                                   params='{%s, %s, "limits": {"end": %d}}' % (props, filter_str, limit))
        if "result" in data and "movies" in data["result"]:
            return [self.handle_movies(item) for item in data["result"]["movies"]]
        else:
            return []

    def get_tvshows(self, filter_str="", limit=10):
        props = '"properties": ["title", "genre", "year", "rating", "plot", "studio", "mpaa", "cast", "playcount", "episode", "imdbnumber", "premiered", "votes", "lastplayed", "fanart", "thumbnail", "file", "originaltitle", "sorttitle", "episodeguide", "season", "watchedepisodes", "dateadded", "tag", "art"]'
        data = Utils.get_kodi_json(method="VideoLibrary.GetTVShows",
                                   params='{%s, %s, "limits": {"end": %d}}' % (props, filter_str, limit))
        if "result" in data and "tvshows" in data["result"]:
            return [self.handle_tvshows(item) for item in data["result"]["tvshows"]]
        else:
            return []

    def handle_movies(self, movie):
        trailer = "plugin://script.extendedinfo/?info=playtrailer&&dbid=%s" % str(movie['movieid'])
        if addon.setting("infodialog_onclick") != "false":
            path = 'plugin://script.extendedinfo/?info=extendedinfo&&dbid=%s' % str(movie['movieid'])
        else:
            path = 'plugin://script.extendedinfo/?info=playmovie&&dbid=%i' % movie['movieid']
        if (movie['resume']['position'] and movie['resume']['total']) > 0:
            resume = "true"
            played = '%s' % int((float(movie['resume']['position']) / float(movie['resume']['total'])) * 100)
        else:
            resume = "false"
            played = '0'
        stream_info = Utils.media_streamdetails(movie['file'].encode('utf-8').lower(),
                                                movie['streamdetails'])
        db_movie = {'label': movie.get('label'),
                    'path': path}
        db_movie["infos"] = {'title': movie.get('label'),
                             'File': movie.get('file'),
                             'year': str(movie.get('year')),
                             'writer': " / ".join(movie['writer']),
                             'userrating': movie.get('userrating'),
                             'trailer': trailer,
                             'Rating': str(round(float(movie['rating']), 1)),
                             'director': " / ".join(movie.get('director')),
                             'writer': " / ".join(movie.get('writer')),
                             'plot': movie.get('plot'),
                             'originaltitle': movie.get('originaltitle')}
        db_movie["properties"] = {'imdb_id': movie.get('imdbnumber'),
                                  'PercentPlayed': played,
                                  'Resume': resume,
                                  'dbid': str(movie['movieid'])}
        db_movie["artwork"] = movie['art']
        streams = []
        for i, item in enumerate(movie['streamdetails']['audio']):
            language = item['language']
            if language not in streams and language != "und":
                streams.append(language)
                db_movie["properties"]['AudioLanguage.%d' % (i + 1)] = language
                db_movie["properties"]['AudioCodec.%d' % (i + 1)] = item['codec']
                db_movie["properties"]['AudioChannels.%d' % (i + 1)] = str(item['channels'])
        subs = []
        for i, item in enumerate(movie['streamdetails']['subtitle']):
            language = item['language']
            if language not in subs and language != "und":
                subs.append(language)
                db_movie["properties"]['SubtitleLanguage.%d' % (i + 1)] = language
        db_movie["properties"].update(stream_info)
        return {k: v for k, v in db_movie.items() if v}

    def handle_tvshows(self, tvshow):
        if addon.setting("infodialog_onclick") != "false":
            path = 'plugin://script.extendedinfo/?info=extendedtvinfo&&dbid=%s' % tvshow['tvshowid']
        else:
            path = 'plugin://script.extendedinfo/?info=action&&id=ActivateWindow(videos,videodb://tvshows/titles/%s/,return)' % tvshow['tvshowid']
        db_tvshow = {'label': tvshow.get('label'),
                     'title': tvshow.get('label'),
                     'genre': " / ".join(tvshow.get('genre')),
                     'File': tvshow.get('file'),
                     'year': str(tvshow.get('year')),
                     'originaltitle': tvshow.get('originaltitle'),
                     'imdb_id': tvshow.get('imdbnumber'),
                     'path': path,
                     'Play': "",
                     'dbid': str(tvshow['tvshowid']),
                     'Rating': str(round(float(tvshow['rating']), 1))}
        db_tvshow.update(tvshow['art'])
        return {k: v for k, v in db_tvshow.items() if v}

    def get_movie(self, movie_id):
        response = Utils.get_kodi_json(method="VideoLibrary.GetMovieDetails",
                                       params='{"properties": ["title", "originaltitle", "votes", "playcount", "year", "genre", "studio", "country", "tagline", "plot", "runtime", "file", "plotoutline", "lastplayed", "trailer", "rating", "resume", "art", "streamdetails", "mpaa", "director", "writer", "cast", "dateadded", "imdbnumber"], "movieid":%s }' % str(movie_id))
        if "result" in response and "moviedetails" in response["result"]:
            return self.handle_movies(response["result"]["moviedetails"])
        return {}

    def get_tvshow(self, tvshow_id):
        response = Utils.get_kodi_json(method="VideoLibrary.GetTVShowDetails",
                                       params='{"properties": ["title", "genre", "year", "rating", "plot", "studio", "mpaa", "cast", "playcount", "episode", "imdbnumber", "premiered", "votes", "lastplayed", "fanart", "thumbnail", "file", "originaltitle", "sorttitle", "episodeguide", "season", "watchedepisodes", "dateadded", "tag", "art"], "tvshowid":%s }' % str(tvshow_id))
        if "result" in response and "tvshowdetails" in response["result"]:
            return self.handle_tvshows(response["result"]["tvshowdetails"])
        return {}

    def get_albums(self):
        data = Utils.get_kodi_json(method="AudioLibrary.GetAlbums",
                                   params='{"properties": ["title"]}')
        if "result" not in data or "albums" not in data['result']:
            return []
        return data['result']['albums']

    def merge_with_local_movie_info(self, online_list, library_first=True, sortkey=False):
        if not self.movie_titles:
            # now = time.time()
            self.movie_ids = addon.get_global("movie_ids.JSON")
            if self.movie_ids and self.movie_ids != "[]":
                self.movie_ids = json.loads(self.movie_ids)
                self.movie_otitles = json.loads(addon.get_global("movie_otitles.JSON"))
                self.movie_titles = json.loads(addon.get_global("movie_titles.JSON"))
                self.movie_imdbs = json.loads(addon.get_global("movie_imdbs.JSON"))
            else:
                self.movie_ids = []
                self.movie_imdbs = []
                self.movie_otitles = []
                self.movie_titles = []
                for item in KodiJson.get_movies(["originaltitle", "imdbnumber"]):
                    self.movie_ids.append(item["movieid"])
                    self.movie_imdbs.append(item["imdbnumber"])
                    self.movie_otitles.append(item["originaltitle"].lower())
                    self.movie_titles.append(item["label"].lower())
                addon.set_global("movie_ids.JSON", json.dumps(self.movie_ids))
                addon.set_global("movie_otitles.JSON", json.dumps(self.movie_otitles))
                addon.set_global("movie_titles.JSON", json.dumps(self.movie_titles))
                addon.set_global("movie_imdbs.JSON", json.dumps(self.movie_imdbs))
            # Utils.log("create_light_movielist: " + str(now - time.time()))
        # now = time.time()
        local_items = []
        remote_items = []
        for item in online_list:
            index = False
            if "imdb_id" in item.get("properties", {}) and item["properties"]["imdb_id"] in self.movie_imdbs:
                index = self.movie_imdbs.index(item["properties"]["imdb_id"])
            elif "title" in item.get("infos", {}) and item["infos"]['title'].lower() in self.movie_titles:
                index = self.movie_titles.index(item["infos"]['title'].lower())
            elif "originaltitle" in item.get("infos", {}) and item["infos"]["originaltitle"].lower() in self.movie_otitles:
                index = self.movie_otitles.index(item["infos"]["originaltitle"].lower())
            if index:
                local_item = self.get_movie(self.movie_ids[index])
                if local_item:
                    try:
                        diff = abs(int(local_item["year"]) - int(item["infos"]["year"]))
                        if diff > 1:
                            remote_items.append(item)
                            continue
                    except Exception:
                        pass
                    item["properties"].update(local_item["properties"])
                    item["infos"].update(local_item["infos"])
                    item["artwork"].update(local_item["artwork"])
                    if library_first:
                        local_items.append(item)
                    else:
                        remote_items.append(item)
                else:
                    remote_items.append(item)
            else:
                remote_items.append(item)
        # Utils.log("compare time: " + str(now - time.time()))
        if sortkey:
            local_items = sorted(local_items, key=lambda k: k["infos"][sortkey], reverse=True)
            remote_items = sorted(remote_items, key=lambda k: k["infos"][sortkey], reverse=True)
        return local_items + remote_items

    def merge_with_local_tvshow_info(self, online_list, library_first=True, sortkey=False):
        if not self.tvshow_titles:
            # now = time.time()
            self.tvshow_ids = addon.get_global("tvshow_ids.JSON")
            if self.tvshow_ids and self.tvshow_ids != "[]":
                self.tvshow_ids = json.loads(self.tvshow_ids)
                self.tvshow_originaltitles = json.loads(addon.get_global("tvshow_originaltitles.JSON"))
                self.tvshow_titles = json.loads(addon.get_global("tvshow_titles.JSON"))
                self.tvshow_imdbs = json.loads(addon.get_global("tvshow_imdbs.JSON"))
            else:
                self.tvshow_ids = []
                self.tvshow_imdbs = []
                self.tvshow_originaltitles = []
                self.tvshow_titles = []
                for item in KodiJson.get_tvshows(["originaltitle", "imdbnumber"]):
                    self.tvshow_ids.append(item["tvshowid"])
                    self.tvshow_imdbs.append(item["imdbnumber"])
                    self.tvshow_originaltitles.append(item["originaltitle"].lower())
                    self.tvshow_titles.append(item["label"].lower())
                addon.set_global("tvshow_ids.JSON", json.dumps(self.tvshow_ids))
                addon.set_global("tvshow_originaltitles.JSON", json.dumps(self.tvshow_originaltitles))
                addon.set_global("tvshow_titles.JSON", json.dumps(self.tvshow_titles))
                addon.set_global("tvshow_imdbs.JSON", json.dumps(self.tvshow_imdbs))
            # Utils.log("create_light_tvshowlist: " + str(now - time.time()))
        # now = time.time()
        local_items = []
        remote_items = []
        for item in online_list:
            index = None
            if "imdb_id" in item and item["imdb_id"] in self.tvshow_imdbs:
                index = self.tvshow_imdbs.index(item["imdb_id"])
            elif "title" in item.get("infos", {}) and item["infos"]['title'].lower() in self.tvshow_titles:
                index = self.tvshow_titles.index(item["infos"]['title'].lower())
            elif "originaltitle" in item.get("infos", {}) and item["infos"]["originaltitle"].lower() in self.tvshow_originaltitles:
                index = self.tvshow_originaltitles.index(item["infos"]["originaltitle"].lower())
            if index:
                local_item = self.get_tvshow(self.tvshow_ids[index])
                if local_item:
                    try:
                        diff = abs(int(local_item["year"]) - int(item["infos"]["year"]))
                        if diff > 1:
                            remote_items.append(item)
                            continue
                    except Exception:
                        pass
                    item["properties"].update(local_item["properties"])
                    item["infos"].update(local_item["infos"])
                    item["artwork"].update(local_item["artwork"])
                    if library_first:
                        local_items.append(item)
                    else:
                        remote_items.append(item)
                else:
                    remote_items.append(item)
            else:
                remote_items.append(item)
        # Utils.log("compare time: " + str(now - time.time()))
        if sortkey:
            local_items = sorted(local_items,
                                 key=lambda k: k["infos"][sortkey],
                                 reverse=True)
            remote_items = sorted(remote_items,
                                  key=lambda k: k["infos"][sortkey],
                                  reverse=True)
        return local_items + remote_items

    def compare_album_with_library(self, online_list):
        if not self.albums:
            self.albums = self.get_albums()
        for item in online_list:
            for local_item in self.albums:
                if not item["name"] == local_item["title"]:
                    continue
                data = Utils.get_kodi_json(method="AudioLibrary.getAlbumDetails",
                                           params='{"properties": ["thumbnail"], "albumid":%s }' % local_item["albumid"])
                album = data["result"]["albumdetails"]
                item["dbid"] = album["albumid"]
                item["path"] = 'plugin://script.extendedinfo/?info=playalbum&&dbid=%i' % album['albumid']
                if album["thumbnail"]:
                    item.update({"thumb": album["thumbnail"]})
                break
        return online_list

    def get_set_name(self, dbid):
        data = Utils.get_kodi_json(method="VideoLibrary.GetMovieDetails",
                                   params='{"properties": ["setid"], "movieid":%s }' % dbid)
        if "result" not in data or "moviedetails" not in data["result"]:
            return None
        set_dbid = data['result']['moviedetails'].get('setid')
        if set_dbid:
            data = Utils.get_kodi_json(method="VideoLibrary.GetMovieSetDetails",
                                       params='{"setid":%s }' % set_dbid)
            return data['result']['setdetails'].get('label')

    def get_imdb_id(self, media_type, dbid):
        if not dbid:
            return None
        if media_type == "movie":
            data = Utils.get_kodi_json(method="VideoLibrary.GetMovieDetails",
                                       params='{"properties": ["imdbnumber","title", "year"], "movieid":%s }' % dbid)
            if "result" in data and "moviedetails" in data["result"]:
                return data['result']['moviedetails']['imdbnumber']
        elif media_type == "tvshow":
            data = Utils.get_kodi_json(method="VideoLibrary.GetTVShowDetails",
                                       params='{"properties": ["imdbnumber","title", "year"], "tvshowid":%s }' % dbid)
            if "result" in data and "tvshowdetails" in data["result"]:
                return data['result']['tvshowdetails']['imdbnumber']
        return None

    def get_tvshow_id_by_episode(self, dbid):
        if not dbid:
            return None
        data = Utils.get_kodi_json(method="VideoLibrary.GetEpisodeDetails",
                                   params='{"properties": ["tvshowid"], "episodeid":%s }' % dbid)
        if "episodedetails" in data["result"]:
            return self.get_imdb_id(media_type="tvshow",
                                    dbid=str(data['result']['episodedetails']['tvshowid']))
        else:
            return None

local_db = LocalDB()

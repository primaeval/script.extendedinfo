# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

import xbmc
import xbmcgui
import collections
from Utils import *
import DialogVideoInfo
import DialogTVShowInfo
import DialogActorInfo
from TheMovieDB import *
import time
from threading import Timer
from BaseClasses import DialogBaseList

SORTS = {"movie": {ADDON.getLocalizedString(32110): "popularity",
                   xbmc.getLocalizedString(172): "release_date",
                   ADDON.getLocalizedString(32108): "revenue",
                   # "Release Date": "primary_release_date",
                   xbmc.getLocalizedString(20376): "original_title",
                   ADDON.getLocalizedString(32112): "vote_average",
                   ADDON.getLocalizedString(32111): "vote_count"},
         "tv": {ADDON.getLocalizedString(32110): "popularity",
                xbmc.getLocalizedString(20416): "first_air_date",
                ADDON.getLocalizedString(32112): "vote_average",
                ADDON.getLocalizedString(32111): "vote_count"},
         "favorites": {ADDON.getLocalizedString(32157): "created_at"},
         "list": {ADDON.getLocalizedString(32157): "created_at"},
         "rating": {ADDON.getLocalizedString(32157): "created_at"}}
TRANSLATIONS = {"movie": xbmc.getLocalizedString(20338),
                "tv": xbmc.getLocalizedString(20364)}

include_adult = str(ADDON.getSetting("include_adults")).lower()


class T9Search(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.callback = kwargs.get("call")
        self.search_string = kwargs.get("start_value", "")
        self.previous = False
        self.prev_time = 0
        self.timer = None
        self.color_timer = None

    def onInit(self):
        if self.search_string:
            self.get_autocomplete_labels()
        self.classic_mode = False
        self.update_search_label()
        keys = (("1", "ABC"),
                ("2", "DEF"),
                ("3", "GHI"),
                ("4", "JKL"),
                ("5", "MNO"),
                ("6", "PQR"),
                ("7", "STU"),
                ("8", "VWX"),
                ("9", "YZ"),
                ("DEL", "<--"),
                ("0", "___"),
                ("KEYB", "CLASSIC"))
        key_dict = collections.OrderedDict(keys)
        listitems = []
        for key, value in key_dict.iteritems():
            li = xbmcgui.ListItem("[B]%s[/B]" % key, value)
            li.setProperty("key", key)
            li.setProperty("value", value)
            listitems.append(li)
        self.getControl(9090).addItems(listitems)
        self.setFocusId(9090)
        self.getControl(600).setLabel("[B]%s[/B]_" % self.search_string)

    @run_async
    def update_search_label(self):
        while True:
            time.sleep(1)
            if int(time.time()) % 2 == 0:
                self.getControl(600).setLabel("[B]%s[/B]_" % self.search_string)
            else:
                self.getControl(600).setLabel("[B]%s[/B][COLOR 00FFFFFF]_[/COLOR]" % self.search_string)

    def onClick(self, control_id):
        if control_id == 9090:
            letters = self.getControl(9090).getSelectedItem().getProperty("value")
            number = self.getControl(9090).getSelectedItem().getProperty("key")
            letter_list = [c for c in letters]
            now = time.time()
            time_diff = now - self.prev_time
            if number == "DEL":
                if self.search_string:
                    self.search_string = self.search_string[:-1]
            elif number == "0":
                if self.search_string:
                    self.search_string += " "
            elif number == "KEYB":
                self.classic_mode = True
                self.close()
            elif self.previous != letters or time_diff >= 1:
                self.prev_time = now
                self.previous = letters
                self.search_string += letter_list[0]
                self.color_labels(letter_list[0], letters)
            elif time_diff < 1:
                if self.color_timer:
                    self.color_timer.cancel()
                self.prev_time = now
                idx = (letter_list.index(self.search_string[-1]) + 1) % len(letter_list)
                self.search_string = self.search_string[:-1] + letter_list[idx]
                self.color_labels(letter_list[idx], letters)
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(1.0, self.callback, (self.search_string,))
            self.timer.start()
            self.getControl(600).setLabel("[B]%s[/B]_" % self.search_string)
            self.get_autocomplete_labels()
        elif control_id == 9091:
            self.search_string = self.getControl(9091).getSelectedItem().getLabel()
            self.getControl(600).setLabel("[B]%s[/B]_" % self.search_string)
            self.get_autocomplete_labels()
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(0.0, self.callback, (self.search_string,))
            self.timer.start()

    def color_labels(self, letter, letters):
        label = "[COLOR=FFFF3333]%s[/COLOR]" % letter
        self.getControl(9090).getSelectedItem().setLabel2(letters.replace(letter, label))
        self.color_timer = Timer(1.0, self.reset_color, (self.getControl(9090).getSelectedItem(),))
        self.color_timer.start()

    def reset_color(self, item):
        label = item.getLabel2()
        label = label.replace("[COLOR=FFFF3333]", "").replace("[/COLOR]", "")
        item.setLabel2(label)

    @run_async
    def get_autocomplete_labels(self):
        self.getControl(9091).reset()
        listitems = get_autocomplete_items(self.search_string)
        self.getControl(9091).addItems(create_listitems(listitems))


class DialogVideoList(DialogBaseList):

    @busy_dialog
    def __init__(self, *args, **kwargs):
        super(DialogVideoList, self).__init__()
        self.layout = "poster"
        self.type = kwargs.get('type', "movie")
        self.search_string = kwargs.get('search_string', "")
        self.filter_label = kwargs.get("filter_label", "")
        self.mode = kwargs.get("mode", "filter")
        self.list_id = kwargs.get("list_id", False)
        self.sort = kwargs.get('sort', "popularity")
        self.sort_label = kwargs.get('sort_label', "Popularity")
        self.order = kwargs.get('order', "desc")
        force = kwargs.get('force', False)
        self.logged_in = check_login()
        self.filters = kwargs.get('filters', [])
        if self.listitem_list:
            self.listitems = create_listitems(self.listitem_list)
            self.total_items = len(self.listitem_list)
        else:
            self.update_content(force_update=force)
            # notify(str(self.totalpages))

    def update_ui(self):
        super(DialogVideoList, self).update_ui()
        self.window.setProperty("Type", TRANSLATIONS[self.type])
        if self.type == "tv":
            self.window.getControl(5006).setVisible(False)
            self.window.getControl(5008).setVisible(False)
            self.window.getControl(5009).setVisible(False)
            self.window.getControl(5010).setVisible(False)
        else:
            self.window.getControl(5006).setVisible(True)
            self.window.getControl(5008).setVisible(True)
            self.window.getControl(5009).setVisible(True)
            self.window.getControl(5010).setVisible(True)

    def onAction(self, action):
        focusid = self.getFocusId()
        if action in self.ACTION_PREVIOUS_MENU:
            self.close()
            pop_window_stack()
        elif action in self.ACTION_EXIT_SCRIPT:
            self.close()
        elif action == xbmcgui.ACTION_CONTEXT_MENU:
            if not focusid == 500:
                return None
            item_id = self.getControl(focusid).getSelectedItem().getProperty("id")
            if self.type == "tv":
                listitems = [ADDON.getLocalizedString(32169)]
            else:
                listitems = [ADDON.getLocalizedString(32113)]
            if self.logged_in:
                listitems += [xbmc.getLocalizedString(14076)]
                if not self.type == "tv":
                    listitems += [ADDON.getLocalizedString(32107)]
                if self.mode == "list":
                    listitems += [ADDON.getLocalizedString(32035)]
            # context_menu = ContextMenu.ContextMenu(u'DialogContextMenu.xml', ADDON_PATH, labels=listitems)
            # context_menu.doModal()
            selection = xbmcgui.Dialog().select(ADDON.getLocalizedString(32151), listitems)
            if selection == 0:
                rating = get_rating_from_user()
                if rating:
                    send_rating_for_media_item(self.type, item_id, rating)
                    xbmc.sleep(2000)
                    self.update_content(force_update=True)
                    self.update_ui()
            elif selection == 1:
                change_fav_status(item_id, self.type, "true")
            elif selection == 2:
                xbmc.executebuiltin("ActivateWindow(busydialog)")
                listitems = [ADDON.getLocalizedString(32139)]
                account_lists = get_account_lists()
                for item in account_lists:
                    listitems.append("%s (%i)" % (item["name"], item["item_count"]))
                listitems.append(ADDON.getLocalizedString(32138))
                xbmc.executebuiltin("Dialog.Close(busydialog)")
                index = xbmcgui.Dialog().select(ADDON.getLocalizedString(32136), listitems)
                if index == 0:
                    listname = xbmcgui.Dialog().input(ADDON.getLocalizedString(32137), type=xbmcgui.INPUT_ALPHANUM)
                    if listname:
                        list_id = create_list(listname)
                        xbmc.sleep(1000)
                        change_list_status(list_id, item_id, True)
                elif index == len(listitems) - 1:
                    self.remove_listDialog(account_lists)
                elif index > 0:
                    change_list_status(account_lists[index - 1]["id"], item_id, True)
                    # xbmc.sleep(2000)
                    # self.update_content(force_update=True)
                    # self.update_ui()
            elif selection == 3:
                change_list_status(self.list_id, item_id, False)
                self.update_content(force_update=True)
                self.update_ui()

    def onClick(self, control_id):
        super(DialogVideoList, self).onClick(control_id)
        if control_id in [500]:
            add_to_window_stack(self)
            self.close()
            media_id = self.getControl(control_id).getSelectedItem().getProperty("id")
            media_type = self.getControl(control_id).getSelectedItem().getProperty("media_type")
            if media_type:
                self.type = media_type
            if self.type == "tv":
                dialog = DialogTVShowInfo.DialogTVShowInfo(u'script-%s-DialogVideoInfo.xml' % ADDON_NAME, ADDON_PATH, id=media_id)
            elif self.type == "person":
                dialog = DialogActorInfo.DialogActorInfo(u'script-%s-DialogInfo.xml' % ADDON_NAME, ADDON_PATH, id=media_id)
            else:
                dialog = DialogVideoInfo.DialogVideoInfo(u'script-%s-DialogVideoInfo.xml' % ADDON_NAME, ADDON_PATH, id=media_id)
            dialog.doModal()
        elif control_id == 5002:
            self.get_genre()
            self.update_content()
            self.update_ui()
        elif control_id == 5003:
            dialog = xbmcgui.Dialog()
            ret = dialog.yesno(heading=ADDON.getLocalizedString(32151), line1=ADDON.getLocalizedString(32106), nolabel=ADDON.getLocalizedString(32150), yeslabel=ADDON.getLocalizedString(32149))
            result = xbmcgui.Dialog().input(xbmc.getLocalizedString(345), "", type=xbmcgui.INPUT_NUMERIC)
            if result:
                if ret:
                    order = "lte"
                    value = "%s-12-31" % result
                    label = " < " + result
                else:
                    order = "gte"
                    value = "%s-01-01" % result
                    label = " > " + result
                if self.type == "tv":
                    self.add_filter("first_air_date.%s" % order, value, xbmc.getLocalizedString(20416), label)
                else:
                    self.add_filter("primary_release_date.%s" % order, value, xbmc.getLocalizedString(345), label)
                self.mode = "filter"
                self.page = 1
                self.update_content()
                self.update_ui()
        # elif control_id == 5011:
        #     dialog = xbmcgui.Dialog()
        #     ret = True
        #     if not self.type == "tv":
        #         ret = dialog.yesno(heading=ADDON.getLocalizedString(32151), line1=ADDON.getLocalizedString(32106), nolabel=ADDON.getLocalizedString(32150), yeslabel=ADDON.getLocalizedString(32149))
        #     result = xbmcgui.Dialog().input(xbmc.getLocalizedString(32112), "", type=xbmcgui.INPUT_NUMERIC)
        #     if result:
        #         if ret:
        #             order = "lte"
        #             label = " < " + result
        #         else:
        #             order = "gte"
        #             label = " > " + result
        #         self.add_filter("vote_average.%s" % order, float(result) / 10.0, ADDON.getLocalizedString(32112), label)
        #         self.mode = "filter"
        #         self.page = 1
        #         self.update_content()
        #         self.update_ui()
        elif control_id == 5012:
            dialog = xbmcgui.Dialog()
            ret = True
            if not self.type == "tv":
                ret = dialog.yesno(heading=ADDON.getLocalizedString(32151), line1=ADDON.getLocalizedString(32106), nolabel=ADDON.getLocalizedString(32150), yeslabel=ADDON.getLocalizedString(32149))
            result = xbmcgui.Dialog().input(xbmc.getLocalizedString(32111), "", type=xbmcgui.INPUT_NUMERIC)
            if result:
                if ret:
                    order = "lte"
                    label = " < " + result
                else:
                    order = "gte"
                    label = " > " + result
                self.add_filter("vote_count.%s" % order, result, ADDON.getLocalizedString(32111), label)
                self.mode = "filter"
                self.page = 1
                self.update_content()
                self.update_ui()

        elif control_id == 5004:
            if self.order == "asc":
                self.order = "desc"
            else:
                self.order = "asc"
            self.update_content()
            self.update_ui()
        elif control_id == 5005:
            self.filters = []
            self.page = 1
            self.mode = "filter"
            self.update_content()
            self.update_ui()
        elif control_id == 5006:
            self.get_certification()
            self.update_content()
            self.update_ui()
        elif control_id == 5008:
            self.get_actor()
            self.update_content()
            self.update_ui()
        elif control_id == 5009:
            self.get_keyword()
            self.update_content()
            self.update_ui()
        elif control_id == 5010:
            self.get_company()
            self.update_content()
            self.update_ui()
        elif control_id == 5007:
            self.filters = []
            self.page = 1
            self.mode = "filter"
            if self.type == "tv":
                self.type = "movie"
                self.filters = []
            else:
                self.type = "tv"
                self.filters = []
            if self.mode == "list":
                self.mode = "filter"
            self.update_content()
            self.update_ui()
        elif control_id == 6000:
            dialog = T9Search(u'script-%s-T9Search.xml' % ADDON_NAME, ADDON_PATH, call=self.search, start_value=self.search_string)
            dialog.doModal()
            if dialog.classic_mode:
                result = xbmcgui.Dialog().input(xbmc.getLocalizedString(16017), "", type=xbmcgui.INPUT_ALPHANUM)
                if result and result > -1:
                    self.search(result)
            if self.total_items > 0:
                self.setFocusId(500)

        elif control_id == 7000:
            if self.type == "tv":
                listitems = [ADDON.getLocalizedString(32145)]  # rated tv
                if self.logged_in:
                    listitems.append(ADDON.getLocalizedString(32144))   # starred tv
            else:
                listitems = [ADDON.getLocalizedString(32135)]  # rated movies
                if self.logged_in:
                    listitems.append(ADDON.getLocalizedString(32134))   # starred movies
            xbmc.executebuiltin("ActivateWindow(busydialog)")
            if self.logged_in:
                account_lists = get_account_lists()
                for item in account_lists:
                    listitems.append("%s (%i)" % (item["name"], item["item_count"]))
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            index = xbmcgui.Dialog().select(ADDON.getLocalizedString(32136), listitems)
            if index == -1:
                pass
            elif index == 0:
                self.mode = "rating"
                self.sort = "created_at"
                self.sort_label = ADDON.getLocalizedString(32157)
                self.filters = []
                self.page = 1
                self.update_content()
                self.update_ui()
            elif index == 1:
                self.mode = "favorites"
                self.sort = "created_at"
                self.sort_label = ADDON.getLocalizedString(32157)
                self.filters = []
                self.page = 1
                self.update_content()
                self.update_ui()
            else:
                # offset = len(listitems) - len(account_lists)
                # notify(str(offset))
                list_id = account_lists[index - 2]["id"]
                list_title = account_lists[index - 2]["name"]
                self.close()
                dialog = DialogVideoList(u'script-%s-VideoList.xml' % ADDON_NAME, ADDON_PATH, color=self.color, filters=[], mode="list", list_id=list_id, filter_label=list_title)
                dialog.doModal()

    def get_sort_type(self):
        listitems = []
        sort_strings = []
        if self.mode in ["favorites", "rating", "list"]:
            sort_key = self.mode
        else:
            sort_key = self.type
        for (key, value) in SORTS[sort_key].iteritems():
            listitems.append(key)
            sort_strings.append(value)
        index = xbmcgui.Dialog().select(ADDON.getLocalizedString(32104), listitems)
        if index > -1:
            if sort_strings[index] == "vote_average":
                self.add_filter("vote_count.gte", "10", "Vote Count (greater)", "10")
            self.sort = sort_strings[index]
            self.sort_label = listitems[index]

    def add_filter(self, key, value, typelabel, label):
        if ".gte" in key or ".lte" in key:
            self.force_overwrite = True
        else:
            self.force_overwrite = False
        super(DialogVideoList, self).add_filter(key, value, typelabel, label)

    def get_genre(self):
        response = get_tmdb_data("genre/%s/list?language=%s&" % (self.type, ADDON.getSetting("LanguageID")), 10)
        id_list = [item["id"] for item in response["genres"]]
        label_list = [item["name"] for item in response["genres"]]
        index = xbmcgui.Dialog().select(ADDON.getLocalizedString(32151), label_list)
        if index > -1:
            self.add_filter("with_genres", str(id_list[index]), xbmc.getLocalizedString(135), str(label_list[index]))
            self.mode = "filter"
            self.page = 1

    def get_actor(self):
        result = xbmcgui.Dialog().input(xbmc.getLocalizedString(16017), "", type=xbmcgui.INPUT_ALPHANUM)
        if result and result > -1:
            response = get_person_id(result)
            if result == -1:
                return None
            self.add_filter("with_people", str(response["id"]), ADDON.getLocalizedString(32156), response["name"])
            self.mode = "filter"
            self.page = 1

    def get_company(self):
        result = xbmcgui.Dialog().input(xbmc.getLocalizedString(16017), "", type=xbmcgui.INPUT_ALPHANUM)
        if result and result > -1:
            response = search_company(result)
            if result == -1:
                return None
            if len(response) > 1:
                names = [item["name"] for item in response]
                selection = xbmcgui.Dialog().select(ADDON.getLocalizedString(32151), names)
                if selection > -1:
                    response = response[selection]
            elif response:
                response = response[0]
            else:
                notify("no company found")
            self.add_filter("with_companies", str(response["id"]), xbmc.getLocalizedString(20388), response["name"])
            self.mode = "filter"
            self.page = 1

    def get_keyword(self):
        result = xbmcgui.Dialog().input(xbmc.getLocalizedString(16017), "", type=xbmcgui.INPUT_ALPHANUM)
        if result and result > -1:
            response = get_keyword_id(result)
            if not response:
                return None
            keyword_id = response["id"]
            name = response["name"]
            if result > -1:
                self.add_filter("with_keywords", str(keyword_id), ADDON.getLocalizedString(32114), name)
                self.mode = "filter"
                self.page = 1

    def get_certification(self):
        response = get_certification_list(self.type)
        country_list = []
        for (key, value) in response.iteritems():
            country_list.append(key)
        index = xbmcgui.Dialog().select(xbmc.getLocalizedString(21879), country_list)
        if index == -1:
            return None
        cert_list = []
        country = country_list[index]
        for item in response[country]:
            label = "%s  -  %s" % (item["certification"], item["meaning"])
            cert_list.append(label)
        index = xbmcgui.Dialog().select(ADDON.getLocalizedString(32151), cert_list)
        if index == -1:
            return None
        cert = cert_list[index].split("  -  ")[0]
        self.add_filter("certification_country", country, ADDON.getLocalizedString(32153), country)
        self.add_filter("certification", cert, ADDON.getLocalizedString(32127), cert)
        self.page = 1
        self.mode = "filter"

    def fetch_data(self, force=False):
        sortby = self.sort + "." + self.order
        if self.type == "tv":
            temp = "tv"
            rated = ADDON.getLocalizedString(32145)
            starred = ADDON.getLocalizedString(32144)
        else:
            temp = "movies"
            rated = ADDON.getLocalizedString(32135)
            starred = ADDON.getLocalizedString(32134)
        if self.mode == "search":
            url = "search/multi?query=%s&page=%i&include_adult=%s&" % (urllib.quote_plus(self.search_string), self.page, include_adult)
            self.filter_label = ADDON.getLocalizedString(32146) % self.search_string
        elif self.mode == "list":
            url = "list/%s?language=%s&" % (str(self.list_id), ADDON.getSetting("LanguageID"))
            # self.filter_label = ADDON.getLocalizedString(32036)
        elif self.mode == "favorites":
            url = "account/%s/favorite/%s?language=%s&page=%i&session_id=%s&sort_by=%s&" % (get_account_info(), temp, ADDON.getSetting("LanguageID"), self.page, get_session_id(), sortby)
            self.filter_label = starred
        elif self.mode == "rating":
            if self.logged_in:
                session_id_string = "session_id=" + get_session_id()
                url = "account/%s/rated/%s?language=%s&page=%i&%s&sort_by=%s&" % (get_account_info(), temp, ADDON.getSetting("LanguageID"), self.page, session_id_string, sortby)
            else:
                url = "guest_session/%s/rated_movies?language=%s&" % (get_guest_session_id(), ADDON.getSetting("LanguageID"))
            self.filter_label = rated
        else:
            self.set_filter_url()
            self.set_filter_label()
            url = "discover/%s?sort_by=%s&%slanguage=%s&page=%i&include_adult=%s&" % (self.type, sortby, self.filter_url, ADDON.getSetting("LanguageID"), self.page, include_adult)
        if force:
            response = get_tmdb_data(url, 0)
        else:
            response = get_tmdb_data(url, 2)
        if self.mode == "list":
            return handle_tmdb_movies(response["items"]), 1, len(response["items"])
        if "results" not in response:
            # self.close()
            return [], 0, 0
        if not response["results"]:
            notify(xbmc.getLocalizedString(284))
        if self.mode == "search":
            return handle_tmdb_multi_search(response["results"]), response["total_pages"], response["total_results"]
        elif self.type == "movie":
            return handle_tmdb_movies(response["results"], False, None), response["total_pages"], response["total_results"]
        else:
            return handle_tmdb_tvshows(response["results"], False, None), response["total_pages"], response["total_results"]

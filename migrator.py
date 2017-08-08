from tkinter import *
from tkinter import messagebox, filedialog, ttk
import spotipy
import spotipy.util as util
import mutagen
from mutagen import id3
import re
import configparser


class Login(Frame):
    def __init__(self, root):
        self.root = root
        self.root.title("Welcome")
        super().__init__(self.root)

        # create the labels and boxes for the usernames and passwords
        self.username_text = Label(self, text="Username:")
        self.username_entered = Entry(self)

        # put the labels and boxes in the proper positions
        self.username_text.grid(row=0, column=0)
        self.username_entered.grid(row=0, column=1)

        self.login_button = Button(self, text="Login", command=self.log_user_in)
        self.login_button.grid(row=1)
        self.pack()

    def log_user_in(self):

        username = self.username_entered.get()
        scopes = "playlist-read-private	playlist-modify-public playlist-modify-private user-library-read " \
                 "user-library-modify "
        try:
            config = configparser.ConfigParser()
            config.read("config.ini")
            token = util.prompt_for_user_token(username=username, scope=scopes,
                                               client_id=config["DEFAULT"]["client_id"],
                                               client_secret=config["DEFAULT"]["client_secret"],
                                               redirect_uri="http://127.0.0.1:8000/")
            self.client = spotipy.Spotify(auth=token)
        except:
            messagebox.askretrycancel(title="Incorrect Login", message="Incorrect Login")
            raise
        self.logged_in(self.client, username)

    def logged_in(self, spotify_client, username):
        app_page = MainPage(Tk(), spotify_client, username)
        self.root.destroy()
        app_page.mainloop()


class MainPage(Frame):
    def __init__(self, root, spotify_client, username):
        """
        :param root: tk root to inherit
        :param spotify_client: spotify client with authorization
        :param username: user's spotify username
        """
        root.title("Spotify Migrator")
        super().__init__(root)
        self.spotify_client = spotify_client
        self.username = username

        self.user_playlists = Playlists(self, spotify_client, self.username)
        self.selected_files = LoadedFiles(self)
        self.not_found_files = LoadedFiles(self)
        self.playlist_text = Label(self, text="Playlists")
        self.loaded_files_text = Label(self, text="Loaded Songs")
        self.not_found_files_text = Label(self, text="Songs Not Found")

        # inner frame 1
        self.button_frame = Frame(self)
        self.search_button = Button(self.button_frame, text="Search for Files", command=self.ask_for_filenames)
        self.migrate_button = Button(self.button_frame, text="Add to Playlist",
                                     command=lambda:
                                     self.transfer_files(self.user_playlists.get_selected_id(), 0))
        self.your_music_button = Button(self.button_frame, text="Add to Your Music",
                                        command=lambda:
                                        self.transfer_files(self.user_playlists.get_selected_id(), 1))
        self.search_button.grid(row=0)
        self.migrate_button.grid(row=1, column=0, sticky=W)
        self.your_music_button.grid(row=1, column=1, sticky=E)

        # inner frame 2
        self.option_frame = Frame(self)
        self.market_entry = Entry(self.option_frame)
        self.market_entry.insert(0, "Enter market (Ex. UK)")
        self.market_entry.bind("<FocusIn>", self.temporary_text_in)
        self.market_entry.bind("<FocusOut>", self.temporary_text_out)
        self.explicit_var = BooleanVar()
        self.explicit_label = Label(self.option_frame, text="Explicit")
        self.explicit_checkbox = Checkbutton(self.option_frame, variable=self.explicit_var,
                                             onvalue=True, offvalue=False, command=self.explicit_value_change)
        self.market_entry.grid(row=0)
        self.explicit_label.grid(row=1, sticky=W)
        self.explicit_checkbox.grid(row=1)

        # position widgets
        self.button_frame.grid(row=0, sticky=W)
        self.option_frame.grid(row=0, sticky=E)
        self.playlist_text.grid(row=1, sticky=NW)
        self.user_playlists.grid(row=2)
        self.loaded_files_text.grid(row=3, sticky=NW)
        self.selected_files.grid(row=4)
        self.not_found_files_text.grid(row=5, sticky=NW)
        self.not_found_files.grid(row=6)
        self.pack()

    # inserts example text in market entry box when empty
    def temporary_text_in(self, event):
        widget = event.widget
        default_text = "Enter market (Ex. UK)"
        if widget.get() == default_text:
            widget.delete(0, len(widget.get()))

    # removes example text in market entry box when focused on
    def temporary_text_out(self, event):
        widget = event.widget
        default_text = "Enter market (Ex. UK)"
        if widget.get() == "":
            widget.insert(0, default_text)

    # set the value for explicit songs to True or False
    def explicit_value_change(self):
        if self.explicit_var.get():
            self.explicit_var.set(False)
            return
        self.explicit_var.set(True)

    # collect the files and add them to the selected_files list
    def ask_for_filenames(self):

        Tk().withdraw()
        self.files = filedialog.askopenfilenames(initialdir="/", title="Select file")

        name = ""
        artist = ""
        album = ""

        for count, file in enumerate(self.files, start=1):
            try:
                if file.endswith(".m4a"):
                    song = mutagen.File(file)
                    name = song["\xa9nam"]
                    artist = song["\xa9ART"]
                    album = song["\xa9alb"]

                else:  # then it must be an .mp3 file - if not, then exception
                    song = id3.ID3(file)

                    name = song["TIT2"]
                    artist = song['TPE1']
                    album = song["TALB"]
            except KeyError:
                pass
            except:
                messagebox.askretrycancel(title="Wrong File Type", message="Only select .mp3, .mp4 files")
                raise

            location = file
            details = [name, artist, album]
            for c, detail in enumerate(details):
                if isinstance(details[c], list):
                    details[c] = details[c][0]
            details.append(location)
            details = tuple(details)
            self.selected_files.load_tree(str(count), details)

    def track_regex(self, string):
        """
        :param string: title of the track
        :return: a list of the words track's title
        """
        return [x.lower() for x in re.findall("[\w][^ ()]*", string)]

    def find_right_track(self, results, local_name_groups, list_of_tracks, explicit_preference):
        """
        compare title name to title name of songs on spotify by the same artist
        :param results: original json of results from search (needed for scrolling pages of tracks)
        :param local_name_groups: list containing the split up title of the track to find
        :param list_of_tracks: list of tracks by the artist on spotify
        :param explicit_preference: whether the user prefers explicit songs or not
        :return: return correct track on spotify
        """
        index = 0
        most_matches = 0
        matches = []
        not_last_page = True
        while results["tracks"]["next"] or not_last_page:
            if not results["tracks"]["next"]:
                not_last_page = False
            for i, track in enumerate(list_of_tracks):
                grouped_track_name = self.track_regex(self.simplify_metadata(track["name"]))
                track_matches = sum([1 for x in grouped_track_name if x in local_name_groups])
                # need to enforce that remixes aren't mistaken for the non-remix and vice versa
                if ("remix" in local_name_groups and "remix" not in grouped_track_name) \
                        or ("remix" in grouped_track_name and "remix" not in local_name_groups):
                    continue
                if track_matches > most_matches:
                    most_matches = track_matches
                    index = i
                if most_matches == len(local_name_groups):
                    return list_of_tracks[index]
            matches.append(list_of_tracks[index])
            if results["tracks"]["next"]:
                results = self.spotify_client.next(results["tracks"])
                list_of_tracks = self.prefer_songs(results, explicit_preference)

        if not matches or abs(matches-len(local_name_groups)) > 1:
            return []
        return matches[len(matches) - 1]


    def simplify_metadata(self, song_data):
        """
        :param song_data: string of either the song name or song artist metadata
        :return: song_from_file with proper artist metadata
        """
        lowercase_string = song_data.lower()
        features = ["ft.", "feat.", "&"]
        for keyword in features:
            if keyword in lowercase_string:
                keyword_index = lowercase_string.find(keyword)
                remix_index = lowercase_string.find("remix")
                if keyword_index < remix_index and remix_index > 0:
                    lowercase_string = lowercase_string[:remix_index] + lowercase_string[remix_index + 6:keyword_index] + \
                                       lowercase_string[keyword_index + len(keyword):]
                else:
                    lowercase_string = lowercase_string.split(keyword)[0]
        return lowercase_string


    def trim_results(self, items, key, explicit_preference):
        index1 = 0
        indices = []
        try:
            for x in items:
                index2 = 1
                for y in items[index1 + 1:]:
                    if x[key] == y[key]:
                        if x["explicit"] == explicit_preference and y["explicit"] != explicit_preference:
                            indices.append(index2)
                        elif x["explicit"] != explicit_preference and y["explicit"] == explicit_preference:
                            indices.append(index1)
                    index2 += 1
                index1 += 1
        except:
            raise
            pass
        indices = set(indices)
        indices = sorted(indices)
        indices.reverse()

        for index in indices:
            del items[index]
        return items


    def prefer_songs(self, results, explicit_preference):
        return self.trim_results(results["tracks"]["items"], "name", explicit_preference)


    def get_track_id(self, artist, song_data, market, explicit_preference):
        """
        :param artist: artist name
        :param song_data: list containing song metadata
        :param market: country to look for tracks in if needed
        :param explicit_preference: preference for explicit songs or not (True or False)
        :return: return tracks that were found
        """
        artist = artist
        songs = [group[0] for group in song_data]
        found_tracks = []

        split_song_names = [self.track_regex(song) for song in songs]
        song_values = [group[1] for group in song_data]
        results = self.spotify_client.search(q="artist:" + "\"" + artist + "\"", type="track", limit=50, market=market)
        tracks = self.prefer_songs(results, explicit_preference)

        if not tracks:
            return []
        else:
            for split_song_name, values_list in zip(split_song_names, song_values):
                found = self.find_right_track(results, split_song_name, tracks, explicit_preference)
                if not found:
                    found_tracks.append(values_list)
                else:
                    found_tracks.append(found)
        return found_tracks


    def transfer_files(self, playlist_selection, transfer_type):
        """
        :param playlist_selection: the user's playlist to transfer selected files to
        :param transfer_type: 0 for playlist transfer, 1 for Your Music transfer
        """

        # get the song info to search for
        tracks = []
        songs_by_artist = dict()
        song_info = []

        # song name, artist, album, path
        for child in self.selected_files.get_children():
            song_name = self.simplify_metadata(self.selected_files.item(child)["values"][0])
            artist_name = self.simplify_metadata(self.selected_files.item(child)["values"][1])
            song_info.append(([song_name, artist_name] + self.selected_files.item(child)["values"][2:],
                              self.selected_files.item(child)["values"]))

        for (song, values) in song_info:
            if song[1] not in songs_by_artist:
                songs_by_artist[song[1]] = []
            songs_by_artist[song[1]].append((song[0], values))

        # search for song on Spotify
        for artist in songs_by_artist:
            try:
                result = self.get_track_id(artist, songs_by_artist[artist], self.market_entry.get(),
                                           explicit_preference=self.explicit_var.get())
                tracks.extend(result)
            except:
                raise
                pass

        track_ids = [track["id"] for track in tracks if isinstance(track, dict)]
        missing_tracks = [track for track in tracks if isinstance(track, list)]

        if len(track_ids) > 0:
            if transfer_type == 0 and playlist_selection:
                self.spotify_client.user_playlist_add_tracks(user=self.username,
                                                             playlist_id=playlist_selection,
                                                             tracks=track_ids, position=0)
                self.user_playlists.refresh()
            elif transfer_type == 1:
                self.spotify_client.current_user_saved_tracks_add(tracks=track_ids)

        for child in self.selected_files.get_children():
            self.selected_files.delete(child)
        for value_list in missing_tracks:
            self.not_found_files.insert("", "end", values=value_list)


class LoadedFiles(ttk.Treeview):
    def __init__(self, root):
        super().__init__(root)
        self["columns"] = ("Name", "Artist", "Album", "Path")

        # edit the headings
        self.heading("#0", text="Track #")
        self.heading("Name", text="Name")
        self.heading("Artist", text="Artist")
        self.heading("Album", text="Album")
        self.heading("Path", text="Path")

        # edit the column configurations
        self.column("#0", anchor=CENTER, width=50)
        self.column("Name", anchor=W, width=150)
        self.column("Artist", anchor=W, width=100)
        self.column("Album", anchor=W, width=150)
        self.column("Path", anchor=W, width=250)
        self.pack()

    def load_tree(self, count, file_data):
        self.insert("", "end", text=count, values=file_data)


class Playlists(ttk.Treeview):
    def __init__(self, root, spotify_client, username):
        super().__init__(root, selectmode=BROWSE)
        self.bind('<<TreeviewSelect>>', self.on_select)
        self['show'] = "headings"
        self["columns"] = ("Name", "# of Tracks", "ID")
        self.client = spotify_client
        self.username = username

        # edit the headings
        self.heading("Name", text="Name")
        self.heading("# of Tracks", text="# of Tracks")
        self.heading("ID", text="ID")

        # edit the column configurations
        self.column("Name", anchor=W, width=150)
        self.column("# of Tracks", anchor=W, width=100)
        self.column("ID", anchor=W, width=225)

        self.playlists = self.load_lists()
        self.pack()

    # save playlist for migration when selected
    def on_select(self, event):
        self.selected = event.widget.selection()

    # playlist id for adding tracks
    def get_selected_id(self):
        try:
            return self.item(self.selected)["values"][2]
        except:
            return None

    # load user playlists with name, numbers of tracks, id
    def load_lists(self):
        self.playlists = self.client.user_playlists(self.username)
        for json_data in self.playlists["items"]:
            try:
                if json_data["owner"]["uri"] == "spotify:user:" + self.username:
                    name = json_data["name"]
                    song_count = json_data["tracks"]["total"]
                    playlist_id = json_data["id"]
                    self.insert("", "end", values=(name, song_count, playlist_id))
            except KeyError:
                pass
        return self.playlists

    # remove playlist info and replace with updated playlists
    def refresh(self):
        self.delete(*self.get_children())
        self.load_lists()


tk = Tk()
A = Login(tk)
A.mainloop()

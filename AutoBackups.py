#!python3
# coding=UTF8
# @author       Avtandil Kikabidze
# @copyright        Copyright (c) 2008-2014, Avtandil Kikabidze aka LONGMAN (akalongman@gmail.com)
# @link             http://long.ge
# @license      GNU General Public License version 2 or later;

import sublime
import sublime_plugin
import sys
import os
import shutil
import filecmp
import re
import time
import threading


reloader_name = 'AutoBackups.autobackups.reloader'
from imp import reload

if reloader_name in sys.modules:
    reload(sys.modules[reloader_name])

from AutoBackups.autobackups import reloader
from AutoBackups.autobackups.paths_helper import PathsHelper

settings = None
lastbackups = None


def plugin_loaded():
    global settings
    global lastbackups

    lastbackups = {}
    platform = sublime.platform().title()

    if (platform == "Osx"):
        platform = "OSX"
    settings = sublime.load_settings(
        'AutoBackups (' + platform + ').sublime-settings')

    backup_dir = settings.get('backup_dir')
    backup_per_day = settings.get('backup_per_day')
    backup_per_time = settings.get('backup_per_time')

    PathsHelper.initialize(
        platform, backup_dir, backup_per_day, backup_per_time)
    print('AutoBackups: Plugin Initialized')
    sublime.set_timeout(gc, 10000)


def gc():
    backup_time = settings.get('delete_old_backups', 0)
    if (backup_time > 0):
        thread = AutoBackupsGcBackup(backup_time)
        thread.start()


class AutoBackupsEventListener(sublime_plugin.EventListener):

    def on_post_save_async(self, view):
        self.save_backup(view, 0)

    def save_backup(self, view, on_load_event):
        if not view or view.is_read_only():
            return

        view_size = view.size()
        max_backup_file_size = settings.get('max_backup_file_size_bytes')
        if (view_size is None):
            self.console('Size of view not available')
            return

        if (max_backup_file_size is None):
            self.console('Max allowed size from config not available')
            return

        # don't save files above configured size
        if view_size > max_backup_file_size:
            self.console(
                'Backup not saved, file too large (%d bytes)' % view.size())
            return

        filename = view.file_name()
        if filename is None:
            return

        # not create file backup if current file is backup
        if on_load_event & self.is_backup_file(filename):
            return

        newname = PathsHelper.get_backup_filepath(filename, on_load_event)
        if newname is None:
            return

        last_backupname = lastbackups.get(filename)

        # not create file backup if no changes from last backup
        if filename and last_backupname:
            if filecmp.cmp(filename, last_backupname):
                return

        # not create file if exists
        if on_load_event & os.path.isfile(newname):
            return

        (backup_dir, file_to_write) = os.path.split(newname)

        if not os.access(backup_dir, os.F_OK):
            os.makedirs(backup_dir)

        shutil.copy(filename, newname)

        lastbackups[filename] = newname
        self.console('Backup saved to: ' + newname.replace('\\', '/'))

    def is_backup_file(self, path):
        backup_per_time = settings.get('backup_per_time')
        path = PathsHelper.normalise_path(path)
        base_dir = PathsHelper.get_base_dir(False)
        base_dir = PathsHelper.normalise_path(base_dir)
        if (backup_per_time == 'folder'):
            base_dir = base_dir[:-7]

        backup_dir_len = len(base_dir)
        sub = path[0:backup_dir_len]

        if sub == base_dir:
            return True
        else:
            return False

    def console(self, *args):
        print(*args)

    def fileChanged(self, text):
        return

    def encode(self, text):
        if isinstance(text, str):
            text = text.encode('UTF-8')
        return text


class AutoBackupsOpenBackupCommand(sublime_plugin.WindowCommand):
    datalist = []
    curline = 1

    def run(self):
        backup_per_day = settings.get('backup_per_day')

        window = self.window
        view = window.active_view()

        open_in_same_line = settings.get('open_in_same_line', True)
        if (open_in_same_line):
            (row, col) = view.rowcol(view.sel()[0].begin())
            self.curline = row + 1

        if (not backup_per_day):
            filepath = view.file_name()
            newname = PathsHelper.get_backup_filepath(filepath)
            if os.path.isfile(newname):
                window.open_file(newname)
            else:
                sublime.error_message(
                    'Backup for ' + filepath + ' not exists!')
        else:
            f_files = self.getData(False)

            if not f_files:
                sublime.error_message('Backups for this file not exists!')
                return

            backup_per_time = settings.get('backup_per_time')
            if (backup_per_time):
                window.show_quick_panel(f_files, self.timeFolders)
            else:
                window.show_quick_panel(f_files, self.openFile)
            return

    def getData(self, time_folder):
        filename = PathsHelper.normalise_path(
            self.window.active_view().file_name(), True)
        basedir = PathsHelper.get_base_dir(True)

        backup_per_time = settings.get('backup_per_time')
        if (backup_per_time):
            if (backup_per_time == 'folder'):
                f_files = []
                if (time_folder is not False):
                    tm_folders = self.getData(False)
                    tm_folder = tm_folders[time_folder][0]
                    basedir = basedir + '/' + tm_folder

                    if (not os.path.isdir(basedir)):
                        sublime.error_message(
                            'Folder ' + basedir + ' not found!')

                    for folder in os.listdir(basedir):
                        fl = basedir + '/' + folder + '/' + filename
                        match = re.search(r"^[0-9+]{6}$", folder)
                        if os.path.isfile(fl) and match is not None:
                            folder_name, file_name = os.path.split(fl)
                            f_file = []
                            thetime = self.formatTime(folder)
                            f_file.append(thetime + ' - ' + file_name)
                            f_file.append(fl)
                            f_files.append(f_file)
                else:
                    path, flname = os.path.split(filename)
                    (filepart, extpart) = os.path.splitext(flname)
                    for folder in os.listdir(basedir):
                        match = re.search(
                            r"^[0-9+]{4}-[0-9+]{2}-[0-9+]{2}$", folder)
                        if match is not None:
                            folder_name, file_name = os.path.split(filename)
                            f_file = []
                            basedir2 = basedir + '/' + folder
                            count = 0
                            last = ''
                            for folder2 in os.listdir(basedir2):
                                match = re.search(r"^[0-9+]{6}$", folder2)
                                if match is not None:
                                    basedir3 = basedir + '/' + folder + \
                                        '/' + folder2 + '/' + filename
                                    if os.path.isfile(basedir3):
                                        count += 1
                                        last = folder2
                            if (count > 0):
                                f_file.append(folder)
                                f_file.append(
                                    'Backups: ' + str(count) + ', Last edit: ' + self.formatTime(last))
                                f_files.append(f_file)
            elif (backup_per_time == 'file'):
                f_files = []
                if (time_folder is not False):
                    tm_folders = self.getData(False)
                    tm_folder = tm_folders[time_folder][0]
                    path, flname = os.path.split(filename)
                    basedir = basedir + '/' + tm_folder + '/' + path
                    (filepart, extpart) = os.path.splitext(flname)

                    if (not os.path.isdir(basedir)):
                        sublime.error_message(
                            'Folder ' + basedir + ' not found!')

                    for folder in os.listdir(basedir):
                        fl = basedir + '/' + folder
                        match = re.search(
                            r"^" + re.escape(filepart) + "_([0-9+]{6})" + re.escape(extpart) + "$", folder)

                        if os.path.isfile(fl) and match is not None:
                            thetime = self.formatTime(match.group(1))
                            f_file = []
                            f_file.append(thetime + ' - ' + flname)
                            f_file.append(fl)
                            f_files.append(f_file)
                else:
                    path, flname = os.path.split(filename)
                    (filepart, extpart) = os.path.splitext(flname)
                    for folder in os.listdir(basedir):
                        match = re.search(
                            r"^[0-9+]{4}-[0-9+]{2}-[0-9+]{2}$", folder)
                        if match is not None:
                            folder_name, file_name = os.path.split(filename)
                            f_file = []
                            basedir2 = basedir + '/' + folder + '/' + path
                            count = 0
                            last = ''
                            if (os.path.isdir(basedir2)):
                                for sfile in os.listdir(basedir2):
                                    match = re.search(
                                        r"^" + re.escape(filepart) + "_([0-9+]{6})" + re.escape(extpart) + "$", sfile)
                                    if match is not None:
                                        count += 1
                                        last = match.group(1)
                            if (count > 0):
                                f_file.append(folder)
                                f_file.append(
                                    'Backups: ' + str(count) + ', Last edit: ' + self.formatTime(last))
                                f_files.append(f_file)
        else:
            f_files = []
            for folder in os.listdir(basedir):
                fl = basedir + '/' + folder + '/' + filename
                match = re.search(r"^[0-9+]{4}-[0-9+]{2}-[0-9+]{2}$", folder)
                if os.path.isfile(fl) and match is not None:
                    folder_name, file_name = os.path.split(fl)
                    f_file = []
                    f_file.append(folder + ' - ' + file_name)
                    f_file.append(fl)
                    f_files.append(f_file)
        f_files.reverse()
        self.datalist = f_files
        return f_files

    def timeFolders(self, parent):
        if (parent == -1):
            return

        # open file
        f_files = self.getData(parent)
        show_previews = settings.get('show_previews', True)
        if (show_previews):
            self.original_view = self.window.active_view()
            sublime.set_timeout_async(lambda: self.window.show_quick_panel(
                f_files, self.openFile, on_highlight=self.showFile), 100)
        else:
            sublime.set_timeout_async(
                lambda: self.window.show_quick_panel(f_files, self.openFile), 100)

        return

    def showFile(self, file):
        if (file == -1):
            return

        f_files = self.datalist
        filename = f_files[file][1]
        window = self.window

        view = window.open_file(
            filename + ":" + str(self.curline), sublime.ENCODED_POSITION | sublime.TRANSIENT)
        view.set_read_only(True)

    def openFile(self, file):
        if (file == -1):
            if self.original_view:
                window = self.window
                window.focus_view(self.original_view)
            return

        f_files = self.datalist
        filename = f_files[file][1]

        window = self.window
        view = window.open_file(
            filename + ":" + str(self.curline), sublime.ENCODED_POSITION)
        view.set_read_only(True)
        window.focus_view(view)

    def formatTime(self, time):
        return time[0:2] + ':' + time[2:4] + ':' + time[4:6]


class AutoBackupsGcBackup(threading.Thread):
    backup_time = 0

    def __init__(self, back_time):
        self.backup_time = back_time
        threading.Thread.__init__(self)

    def run(self):
        import datetime
        basedir = PathsHelper.get_base_dir(True)
        backup_time = self.backup_time

        if (backup_time < 1):
            return

        diff = (backup_time + 1) * 24 * 3600
        deleted = 0
        now_time = time.time()
        for folder in os.listdir(basedir):
            match = re.search(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", folder)
            if match is not None:
                folder_time = time.mktime(
                    datetime.datetime.strptime(folder, "%Y-%m-%d").timetuple())
                if (now_time - folder_time > diff):
                    fldr = basedir + '/' + folder
                    try:
                        shutil.rmtree(fldr, onerror=self.onerror)
                        deleted = deleted + 1
                    except Exception as e:
                        print(e)

        if (deleted > 0):
            diff = backup_time * 24 * 3600
            dt = now_time - diff
            date = datetime.datetime.fromtimestamp(dt).strftime('%Y-%m-%d')
            print('AutoBackups: Deleted ' + str(deleted) +
                  ' backup folders older than ' + date)

    def onerror(self, func, path, exc_info):
        import stat
        if not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

#!python3
# coding=UTF8
# @author 		Avtandil Kikabidze
# @copyright 		Copyright (c) 2008-2014, Avtandil Kikabidze aka LONGMAN (akalongman@gmail.com)
# @link 			http://long.ge
# @license 		GNU General Public License version 2 or later;

import os
import re
import datetime
from . import win32helpers


class PathsHelper(object):
    platform = False
    backup_dir = False
    backup_per_day = False
    backup_per_time = False

    @staticmethod
    def initialize(pl, backup_dir, backup_per_day, backup_per_time):
        PathsHelper.platform = pl
        PathsHelper.backup_dir = backup_dir
        PathsHelper.backup_per_day = backup_per_day
        PathsHelper.backup_per_time = backup_per_time

    @staticmethod
    def get_base_dir(only_base):
        # Configured setting
        backup_dir = PathsHelper.backup_dir
        now_date = datetime.datetime.now()
        date = now_date.strftime('%Y-%m-%d')

        backup_per_day = PathsHelper.backup_per_day
        if (backup_per_day and not only_base):
            backup_dir = backup_dir + '/' + date

        time = now_date.strftime('%H%M%S')
        backup_per_time = PathsHelper.backup_per_time
        if (backup_per_day and backup_per_time == 'folder' and not only_base):
            backup_dir = backup_dir + '/' + time

        if backup_dir != '':
            return os.path.expanduser(backup_dir)

    @staticmethod
    def timestamp_file(filename, on_load_event):
        (filepart, extensionpart) = os.path.splitext(filename)

        backup_per_day = PathsHelper.backup_per_day
        backup_per_time = PathsHelper.backup_per_time
        if (backup_per_day and backup_per_time == 'file'):
            date = datetime.datetime.now()
            if on_load_event:
                date = date - datetime.timedelta(seconds=-1)
            time = date.strftime('%H%M%S')
            name = '%s_%s%s' % (filepart, time, extensionpart,)
        else:
            name = '%s%s' % (filepart, extensionpart,)
        return name

    @staticmethod
    def get_backup_path(filepath):
        path = os.path.expanduser(os.path.split(filepath)[0])
        backup_base = PathsHelper.get_base_dir(False)
        path = PathsHelper.normalise_path(path)
        return os.path.join(backup_base, path)

    @staticmethod
    def normalise_path(path, slashes=False):
        if (path is None):
            return ''

        if PathsHelper.platform != 'Windows':
            # remove any leading / before combining with backup_base
            path = re.sub(r'^/', '', path)
            return path

        path = path.replace('/', '\\')

        # transform subst mapping drive to actual path
        if re.search(r'^(\w):', path):
            path = win32helpers.get_mapping(path[:2]) + path[2:]

        # windows only: transform C: into just C
        path = re.sub(r'^(\w):', r'\1', path)

        # windows only: transform \\remotebox\share into
        # network\remotebox\share
        path = re.sub(r'^\\\\([\w\-]{2,})', r'network\\\1', path)

        if slashes:
            path = path.replace('\\', '/')

        return path

    @staticmethod
    def get_backup_filepath(filepath, on_load_event):
        filename = os.path.split(filepath)[1]
        return os.path.join(PathsHelper.get_backup_path(filepath), PathsHelper.timestamp_file(filename, on_load_event))

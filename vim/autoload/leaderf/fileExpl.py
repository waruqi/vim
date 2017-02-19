#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vim
import re
import os
import os.path
import fnmatch
import time
from functools import wraps
from leaderf.utils import *
from leaderf.explorer import *
from leaderf.manager import *

def showRelativePath(func):
    @wraps(func)
    def deco(*args, **kwargs):
        if lfEval("g:Lf_ShowRelativePath") == '1':
            # os.path.relpath() is too slow!
            dir = os.getcwd() if len(args) == 1 else args[1]
            cwd_length = len(lfEncode(dir))
            if not dir.endswith(os.sep):
                cwd_length += 1
            return [line[cwd_length:] for line in func(*args, **kwargs)]
        else:
            return func(*args, **kwargs)
    return deco


#*****************************************************
# FileExplorer
#*****************************************************
class FileExplorer(Explorer):
    def __init__(self):
        self._cur_dir = ''
        self._content = []
        self._cache_dir = os.path.join(lfEval("g:Lf_CacheDiretory"),
                                       '.LfCache',
                                       'python' + lfEval("g:Lf_PythonVersion"),
                                       'file')
        self._cache_index = os.path.join(self._cache_dir, 'cacheIndex')
        self._initCache()

    def _initCache(self):
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)
        if not os.path.exists(self._cache_index):
            with lfOpen(self._cache_index, 'w', errors='ignore'):
                pass

    def _getFiles(self, dir):
        start_time = time.time()
        wildignore = lfEval("g:Lf_WildIgnore")
        file_list = []
        for dir_path, dirs, files in os.walk(dir, followlinks = False
                if lfEval("g:Lf_FollowLinks") == '0' else True):
            dirs[:] = [i for i in dirs if True not in (fnmatch.fnmatch(i,j)
                       for j in wildignore['dir'])]
            for name in files:
                if True not in (fnmatch.fnmatch(name, j)
                                for j in wildignore['file']):
                    file_list.append(lfEncode(os.path.join(dir_path,name)))
                if time.time() - start_time > float(
                        lfEval("g:Lf_IndexTimeLimit")):
                    return file_list
        return file_list

    @showRelativePath
    def _getFileList(self, dir):
        dir = dir if dir.endswith(os.sep) else dir + os.sep
        with lfOpen(self._cache_index, 'r+', errors='ignore') as f:
            lines = f.readlines()
            path_length = 0
            target = -1
            for i, line in enumerate(lines):
                path = line.split(None, 2)[2].strip()
                if dir.startswith(path) and len(path) > path_length:
                    path_length = len(path)
                    target = i

            if target != -1:
                lines[target] = re.sub('^\S*',
                                       '%.3f' % time.time(),
                                       lines[target])
                f.seek(0)
                f.truncate(0)
                f.writelines(lines)
                with lfOpen(os.path.join(self._cache_dir,
                                         lines[target].split(None, 2)[1]),
                            'r', errors='ignore') as cache_file:
                    if lines[target].split(None, 2)[2].strip() == dir:
                        return cache_file.readlines()
                    else:
                        file_list = [line for line in cache_file.readlines()
                                     if line.startswith(dir)]
                        if file_list == []:
                            file_list = self._getFiles(dir)
                        return file_list
            else:
                start_time = time.time()
                file_list = self._getFiles(dir)
                delta_seconds = time.time() - start_time
                if delta_seconds > float(lfEval("g:Lf_NeedCacheTime")):
                    cache_file_name = ''
                    if len(lines) < int(lfEval("g:Lf_NumberOfCache")):
                        f.seek(0, 2)
                        ts = time.time()
                        line = '%.3f cache_%.3f %s\n' % (ts, ts, dir)
                        f.write(line)
                        cache_file_name = 'cache_%.3f' % ts
                    else:
                        for i, line in enumerate(lines):
                            path = line.split(None, 2)[2].strip()
                            if path.startswith(dir):
                                cache_file_name = line.split(None, 2)[1].strip()
                                line = '%.3f %s %s\n' % (time.time(),
                                        cache_file_name, dir)
                                break
                        if cache_file_name == '':
                            timestamp = lines[0].split(None, 2)[0]
                            oldest = 0
                            for i, line in enumerate(lines):
                                if line.split(None, 2)[0] < timestamp:
                                    timestamp = line.split(None, 2)[0]
                                    oldest = i
                            cache_file_name = lines[oldest].split(None, 2)[1].strip()
                            lines[oldest] = '%.3f %s %s\n' % (time.time(),
                                            cache_file_name, dir)
                        f.seek(0)
                        f.truncate(0)
                        f.writelines(lines)
                    with lfOpen(os.path.join(self._cache_dir, cache_file_name),
                                'w', errors='ignore') as cache_file:
                        for line in file_list:
                            cache_file.write(line + '\n')
                return file_list

    def _refresh(self):
        dir = os.path.abspath(self._cur_dir)
        dir = dir if dir.endswith(os.sep) else dir + os.sep
        with lfOpen(self._cache_index, 'r+', errors='ignore') as f:
            lines = f.readlines()
            path_length = 0
            target = -1
            for i, line in enumerate(lines):
                path = line.split(None, 2)[2].strip()
                if dir.startswith(path) and len(path) > path_length:
                    path_length = len(path)
                    target = i

            if target != -1:
                lines[target] = re.sub('^\S*', '%.3f' % time.time(), lines[target])
                f.seek(0)
                f.truncate(0)
                f.writelines(lines)
                cache_file_name = lines[target].split(None, 2)[1]
                file_list = self._getFiles(dir)
                with lfOpen(os.path.join(self._cache_dir, cache_file_name),
                            'w', errors='ignore') as cache_file:
                    for line in file_list:
                        cache_file.write(line + '\n')

    def getContent(self, *args, **kwargs):
        if len(args) > 0:
            if os.path.exists(lfDecode(args[0])):
                lfCmd("silent cd %s" % args[0])
            else:
                lfCmd("echohl ErrorMsg | redraw | echon "
                      "'Unknown directory `%s`' | echohl NONE" % args[0])
                return None
        dir = os.getcwd()
        if lfEval("g:Lf_UseMemoryCache") == 0 or dir != self._cur_dir:
            self._cur_dir = dir
            self._content = self._getFileList(dir)
        return self._content

    def getFreshContent(self, *args, **kwargs):
        self._refresh()
        self._content = self._getFileList(self._cur_dir)
        return self._content

    def getStlCategory(self):
        return 'File'

    def getStlCurDir(self):
        return escQuote(lfEncode(os.path.abspath(self._cur_dir)))

    def supportsMulti(self):
        return True

    def supportsNameOnly(self):
        return True


#*****************************************************
# FileExplManager
#*****************************************************
class FileExplManager(Manager):
    def _getExplClass(self):
        return FileExplorer

    def _defineMaps(self):
        lfCmd("call leaderf#fileExplMaps()")

    def _createHelp(self):
        help = []
        help.append('" <CR>/<double-click>/o : open file under cursor')
        help.append('" x : open file under cursor in a horizontally split window')
        help.append('" v : open file under cursor in a vertically split window')
        help.append('" t : open file under cursor in a new tabpage')
        help.append('" i : switch to input mode')
        help.append('" s : select multiple files')
        help.append('" a : select all files')
        help.append('" c : clear all selections')
        help.append('" q : quit')
        help.append('" <F5> : refresh the cache')
        help.append('" <F1> : toggle this help')
        help.append('" ---------------------------------------------------------')
        return help

#*****************************************************
# fileExplManager is a singleton
#*****************************************************
fileExplManager = FileExplManager()

__all__ = ['fileExplManager']

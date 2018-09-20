#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vim
import re
import os
import sys
import os.path
import subprocess
import tempfile
import itertools
import multiprocessing
from .utils import *
from .explorer import *
from .manager import *
from .asyncExecutor import AsyncExecutor


#*****************************************************
# BufTagExplorer
#*****************************************************
class BufTagExplorer(Explorer):
    def __init__(self):
        self._ctags = lfEval("g:Lf_Ctags")
        self._supports_preview = int(lfEval("g:Lf_PreviewCode"))
        self._tag_list = {}        # a dict with (key, value) = (buffer number, taglist)
        self._buf_changedtick = {} # a dict with (key, value) = (buffer number, changedtick)
        self._executor = []

    def getContent(self, *args, **kwargs):
        if "--all" in kwargs.get("arguments", {}): # all buffers
            cur_buffer = vim.current.buffer
            for b in vim.buffers:
                if b.options["buflisted"]:
                    if lfEval("bufloaded(%d)" % b.number) == '0':
                        vim.current.buffer = b
            if vim.current.buffer != cur_buffer:
                vim.current.buffer = cur_buffer

            for b in vim.buffers:
                if b.options["buflisted"] and b.name:
                    changedtick = int(lfEval("getbufvar(%d, 'changedtick')" % b.number))
                    if changedtick != self._buf_changedtick.get(b.number, -1):
                        break
            else:
                return list(itertools.chain.from_iterable(self._tag_list.values()))

            return itertools.chain.from_iterable(self._getTagList())
        else:
            result = self._getTagResult(vim.current.buffer)
            if not isinstance(result, list):
                result = self._formatResult(*result)
            tag_list = []
            for i, line in enumerate(result):
                if self._supports_preview and i & 1:
                    tag_list.append(line)
                else:
                    first, second = line.rsplit(":", 1)
                    tag_list.append("{}\t  :{}".format(first.rsplit("\t", 1)[0], second))
            return tag_list

    def _getTagList(self):
        buffers = [b for b in vim.buffers]
        n = multiprocessing.cpu_count()
        for i in range(0, len(vim.buffers), n):
            tag_list = []
            exe_result = []
            for b in buffers[i:i+n]:
                if b.options["buflisted"] and b.name:
                    result = self._getTagResult(b)
                    if isinstance(result, list):
                        tag_list.extend(result)
                    else:
                        exe_result.append(result)
            if not exe_result:
                yield tag_list
            else:
                exe_taglist = (self._formatResult(*r) for r in exe_result)
                # list can reduce the flash of screen
                yield list(itertools.chain(tag_list, itertools.chain.from_iterable(exe_taglist)))

    def _getTagResult(self, buffer):
        if not buffer.name:
            return []
        changedtick = int(lfEval("getbufvar(%d, 'changedtick')" % buffer.number))
        # there is no change since last call
        if changedtick == self._buf_changedtick.get(buffer.number, -1):
            if buffer.number in self._tag_list:
                return self._tag_list[buffer.number]
            else:
                return []
        else:
            self._buf_changedtick[buffer.number] = changedtick

        if lfEval("getbufvar(%d, '&filetype')" % buffer.number) == "cpp":
            extra_options = "--c++-kinds=+p"
        elif lfEval("getbufvar(%d, '&filetype')" % buffer.number) == "c":
            extra_options = "--c-kinds=+p"
        elif lfEval("getbufvar(%d, '&filetype')" % buffer.number) == "python":
            extra_options = "--language-force=Python"
        else:
            extra_options = ""

        executor = AsyncExecutor()
        self._executor.append(executor)
        if buffer.options["modified"] == True:
            if sys.version_info >= (3, 0):
                tmp_file = partial(tempfile.NamedTemporaryFile, encoding=lfEval("&encoding"))
            else:
                tmp_file = tempfile.NamedTemporaryFile

            with tmp_file(mode='w+', suffix='_'+os.path.basename(buffer.name), delete=False) as f:
                for line in buffer[:]:
                    f.write(line + '\n')
                file_name = f.name
            # {tagname}<Tab>{tagfile}<Tab>{tagaddress}[;"<Tab>{tagfield}..]
            # {tagname}<Tab>{tagfile}<Tab>{tagaddress};"<Tab>{kind}<Tab>{scope}
            cmd = '{} -n -u --fields=Ks {} -f- "{}"'.format(self._ctags, extra_options, lfDecode(file_name))
            result = executor.execute(cmd, cleanup=partial(os.remove, file_name))
        else:
            cmd = '{} -n -u --fields=Ks {} -f- "{}"'.format(self._ctags, extra_options, lfDecode(buffer.name))
            result = executor.execute(cmd)

        return (buffer, result)

    def _formatResult(self, buffer, result):
        if not buffer.name:
            return []

        # a list of [tag, file, line, kind, scope]
        output = [line.split('\t') for line in result if line is not None]
        if not output:
            return []

        if len(output[0]) < 4:
            lfCmd("echoerr '%s'" % escQuote(str(output[0])))
            return []

        tag_total_len = 0
        max_kind_len = 0
        max_tag_len = 0
        for _, item  in enumerate(output):
            tag_len = len(item[0])
            tag_total_len += tag_len
            if tag_len > max_tag_len:
                max_tag_len = tag_len
            kind_len = len(item[3])
            if kind_len > max_kind_len:
                max_kind_len = kind_len
        ave_taglen = tag_total_len // len(output)
        tag_len = min(max_tag_len, ave_taglen * 2)

        tab_len = buffer.options["shiftwidth"]
        std_tag_kind_len = tag_len // tab_len * tab_len + tab_len + max_kind_len

        tag_list = []
        for _, item  in enumerate(output):
            scope = item[4] if len(item) > 4 else "Global"
            tag_kind = "{:{taglen}s}\t{}".format(item[0],   # tag
                                                 item[3],   # kind
                                                 taglen=tag_len
                                                 )
            tag_kind_len = int(lfEval("strdisplaywidth('%s')" % escQuote(tag_kind)))
            num = std_tag_kind_len - tag_kind_len
            space_num = num if num > 0 else 0
            bufname = buffer.name if vim.options["autochdir"] else lfRelpath(buffer.name)
            line = "{}{}\t{}\t{:2s}{}:{}\t{}".format(tag_kind,
                                                     ' ' * space_num,
                                                     scope,          # scope
                                                     ' ',
                                                     bufname,        # file
                                                     item[2][:-2],   # line
                                                     buffer.number
                                                     )
            tag_list.append(line)
            if self._supports_preview:
                # code = "{:{taglen}s}\t{}".format(' ' * len(item[0]),
                #                                  buffer[int(item[2][:-2]) - 1].lstrip(),
                #                                  taglen=tag_len
                #                                  )
                code = "\t\t{}".format(buffer[int(item[2][:-2]) - 1].lstrip())
                tag_list.append(code)

        self._tag_list[buffer.number] = tag_list

        return tag_list

    def getStlCategory(self):
        return 'BufTag'

    def getStlCurDir(self):
        return escQuote(lfEncode(os.getcwd()))

    def removeCache(self, buf_number):
        if buf_number in self._tag_list:
            del self._tag_list[buf_number]

        if buf_number in self._buf_changedtick:
            del self._buf_changedtick[buf_number]

    def cleanup(self):
        for exe in self._executor:
            exe.killProcess()
        self._executor = []


#*****************************************************
# BufTagExplManager
#*****************************************************
class BufTagExplManager(Manager):
    def __init__(self):
        super(BufTagExplManager, self).__init__()
        self._match_ids = []
        self._supports_preview = int(lfEval("g:Lf_PreviewCode"))
        self._orig_line = ''

    def _getExplClass(self):
        return BufTagExplorer

    def _defineMaps(self):
        lfCmd("call leaderf#BufTag#Maps()")
        lfCmd("augroup Lf_BufTag")
        lfCmd("autocmd!")
        lfCmd("autocmd BufWipeout * call leaderf#BufTag#removeCache(expand('<abuf>'))")
        lfCmd("autocmd VimLeavePre * call leaderf#BufTag#cleanup()")
        lfCmd("augroup END")

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return
        line = args[0]
        if line[0].isspace(): # if g:Lf_PreviewCode == 1
            buffer = args[1]
            line_nr = args[2]
            line = buffer[line_nr - 2]
        # {tag} {kind} {scope} {file}:{line} {buf_number}
        items = re.split(" *\t *", line)
        tagname = items[0]
        line_nr = items[3].rsplit(":", 1)[1]
        buf_number = items[4]
        lfCmd("hide buffer +%s %s" % (line_nr, buf_number))
        if "preview" not in kwargs:
            lfCmd("norm! ^")
            lfCmd("call search('\V%s', 'Wc', line('.'))" % escQuote(tagname))
        lfCmd("norm! zz")
        lfCmd("setlocal cursorline! | redraw | sleep 20m | setlocal cursorline!")

    def _getDigest(self, line, mode):
        """
        specify what part in the line to be processed and highlighted
        Args:
            mode: 0, return the whole line
                  1, return the tagname
                  2, return the remaining part
        """
        if mode == 0:
            return line
        elif mode == 1:
            return re.split(" *\t *", line, 1)[0]
        else:
            return re.split(" *\t *", line, 1)[1]

    def _getDigestStartPos(self, line, mode):
        """
        return the start position of the digest returned by _getDigest()
        Args:
            mode: 0, return the start position of the whole line
                  1, return the start position of tagname
                  2, return the start position remaining part
        """
        if mode == 0:
            return 0
        elif mode == 1:
            return 0
        else:
            return len(line) - len(re.split(" *\t *", line, 1)[1])

    def _createHelp(self):
        help = []
        help.append('" <CR>/<double-click>/o : open file under cursor')
        help.append('" x : open file under cursor in a horizontally split window')
        help.append('" v : open file under cursor in a vertically split window')
        help.append('" t : open file under cursor in a new tabpage')
        help.append('" i/<Tab> : switch to input mode')
        help.append('" p : preview the result')
        help.append('" q/<Esc> : quit')
        help.append('" <F1> : toggle this help')
        help.append('" ---------------------------------------------------------')
        return help

    def _afterEnter(self):
        super(BufTagExplManager, self)._afterEnter()
        id = int(lfEval('''matchadd('Lf_hl_buftagKind', '^[^\t]*\t\zs\S\+')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_buftagScopeType', '[^\t]*\t\S\+\s*\zs\w\+:')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_buftagScope', '^[^\t]*\t\S\+\s*\(\w\+:\)\=\zs\S\+')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_buftagDirname', '[^\t]*\t\S\+\s*\S\+\s*\zs[^\t]\+')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_buftagLineNum', '\d\+\t\ze\d\+$')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_buftagCode', '^\s\+.*')'''))
        self._match_ids.append(id)

    def _beforeExit(self):
        super(BufTagExplManager, self)._beforeExit()
        for i in self._match_ids:
            lfCmd("silent! call matchdelete(%d)" % i)
        self._match_ids = []

    def _getUnit(self):
        """
        indicates how many lines are considered as a unit
        """
        if self._supports_preview:
            return 2
        else:
            return 1

    def _supportsRefine(self):
        return True

    def _fuzzyFilter(self, is_full_path, get_weight, iterable):
        """
        return a list, each item is a triple (weight, line1, line2)
        """
        if self._supports_preview:
            if len(iterable) < 2:
                return []
            getDigest = partial(self._getDigest, mode=0 if is_full_path else 1)
            triples = ((get_weight(getDigest(line)), line, iterable[2*i+1])
                       for i, line in enumerate(iterable[::2]))
            return (t for t in triples if t[0])
        else:
            return super(BufTagExplManager, self)._fuzzyFilter(is_full_path,
                                                               get_weight,
                                                               iterable)

    def _refineFilter(self, first_get_weight, get_weight, iterable):
        if self._supports_preview:
            if len(iterable) < 2:
                return []
            getDigest = self._getDigest
            tuples = ((first_get_weight(getDigest(line, 1)), get_weight(getDigest(line, 2)),
                       line, iterable[2*i+1]) for i, line in enumerate(iterable[::2]))
            return ((i[0] + i[1], i[2], i[3]) for i in tuples if i[0] and i[1])
        else:
            return super(BufTagExplManager, self)._refineFilter(first_get_weight,
                                                                get_weight,
                                                                iterable)

    def _regexFilter(self, iterable):
        if self._supports_preview:
            try:
                if ('-2' == lfEval("g:LfNoErrMsgMatch('', '%s')" % escQuote(self._cli.pattern))):
                    return iter([])
                else:
                    result = []
                    for i, line in enumerate(iterable[::2]):
                        if ('-1' != lfEval("g:LfNoErrMsgMatch('%s', '%s')" %
                            (escQuote(self._getDigest(line, 1).strip()),
                                escQuote(self._cli.pattern)))):
                            result.append(line)
                            result.append(iterable[2*i+1])
                    return result
            except vim.error:
                return iter([])
        else:
            return super(BufTagExplManager, self)._regexFilter(iterable)

    def _getList(self, pairs):
        """
        return a list constructed from pairs
        Args:
            pairs: a list of tuple(weight, line, ...)
        """
        if self._supports_preview:
            result = []
            for _, p in enumerate(pairs):
                result.append(p[1])
                result.append(p[2])
            return result
        else:
            return super(BufTagExplManager, self)._getList(pairs)

    def _toUp(self):
        if self._supports_preview:
            lfCmd("norm! 2k")
        else:
            super(BufTagExplManager, self)._toUp()

    def _toDown(self):
        if self._supports_preview:
            lfCmd("norm! 3jk")
        else:
            super(BufTagExplManager, self)._toDown()

    def removeCache(self, buf_number):
        self._getExplorer().removeCache(buf_number)

    def _previewResult(self, preview):
        if not self._needPreview(preview):
            return

        line = self._getInstance().currentLine
        orig_pos = self._getInstance().getOriginalPos()
        cur_pos = (vim.current.tabpage, vim.current.window, vim.current.buffer)

        line_nr = self._getInstance().window.cursor[0]

        saved_eventignore = vim.options['eventignore']
        vim.options['eventignore'] = 'BufLeave,WinEnter,BufEnter'
        try:
            vim.current.tabpage, vim.current.window, vim.current.buffer = orig_pos
            self._acceptSelection(line, self._getInstance().buffer, line_nr, preview=True)
        finally:
            vim.current.tabpage, vim.current.window, vim.current.buffer = cur_pos
            vim.options['eventignore'] = saved_eventignore

    def _bangEnter(self):
        self._relocateCursor()

    def _relocateCursor(self):
        inst = self._getInstance()
        orig_buf_nr = inst.getOriginalPos()[2].number
        orig_line = inst.getOriginalCursor()[0]
        tags = []
        for index, line in enumerate(inst.buffer, 1):
            if self._supports_preview and index & 1 == 0:
                continue
            items = re.split(" *\t *", line)
            line_nr = int(items[3].rsplit(":", 1)[1])
            buf_number = int(items[4])
            if orig_buf_nr == buf_number:
                tags.append((index, buf_number, line_nr))
        last = len(tags) - 1
        while last >= 0:
            if tags[last][2] <= orig_line:
                break
            last -= 1
        if last >= 0:
            index = tags[last][0]
            lfCmd(str(index))
            lfCmd("norm! zz")


#*****************************************************
# bufTagExplManager is a singleton
#*****************************************************
bufTagExplManager = BufTagExplManager()

__all__ = ['bufTagExplManager']

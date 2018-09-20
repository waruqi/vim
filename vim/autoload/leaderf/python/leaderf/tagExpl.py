#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vim
import re
import os
import os.path
from .utils import *
from .explorer import *
from .manager import *


#*****************************************************
# TagExplorer
#*****************************************************
class TagExplorer(Explorer):
    def __init__(self):
        self._tag_list = []

    def getContent(self, *args, **kwargs):
        if self._tag_list:
            return self._tag_list
        else:
            return self.getFreshContent()

    def getFreshContent(self, *args, **kwargs):
        self._tag_list = []
        for tagfile in vim.eval("tagfiles()"):
            with lfOpen(os.path.abspath(tagfile), 'r', errors='ignore') as f:
                taglist = f.readlines()
                self._tag_list.extend(taglist[6:])
        return self._tag_list

    def getStlCategory(self):
        return 'Tag'

    def getStlCurDir(self):
        return escQuote(lfEncode(os.getcwd()))


#*****************************************************
# TagExplManager
#*****************************************************
class TagExplManager(Manager):
    def __init__(self):
        super(TagExplManager, self).__init__()
        self._match_ids = []

    def _getExplClass(self):
        return TagExplorer

    def _defineMaps(self):
        lfCmd("call leaderf#Tag#Maps()")

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return
        line = args[0]
        # {tagname}<Tab>{tagfile}<Tab>{tagaddress}[;"<Tab>{tagfield}..]
        tagname, tagfile, right = line.split('\t', 2)
        res = right.split(';"\t', 1)
        tagaddress = res[0]
        try:
            lfCmd("hide edit %s" % escSpecial(tagfile))
        except vim.error as e: # E37
            lfPrintError(e)

        if tagaddress[0] not in '/?':
            lfCmd(tagaddress)
        else:
            lfCmd("norm! gg")

            # In case there are mutiple matches.
            if len(res) > 1:
                result = re.search('(?<=\t)line:\d+', res[1])
                if result:
                    line_nr = result.group(0).split(':')[1]
                    lfCmd(line_nr)
                else: # for c, c++
                    keyword = "(class|enum|struct|union)"
                    result = re.search('(?<=\t)%s:\S+' % keyword, res[1])
                    if result:
                        tagfield = result.group(0).split(":")
                        name = tagfield[0]
                        value = tagfield[-1]
                        lfCmd("call search('\m%s\_s\+%s\_[^;{]*{', 'w')" % (name, value))

            pattern = "\M" + tagaddress[1:-1]
            lfCmd("call search('%s', 'w')" % escQuote(pattern))

        if lfEval("search('\V%s', 'wc')" % escQuote(tagname)) == '0':
            lfCmd("norm! ^")
        lfCmd("norm! zz")
        lfCmd("setlocal cursorline! | redraw | sleep 20m | setlocal cursorline!")

    def _getDigest(self, line, mode):
        """
        specify what part in the line to be processed and highlighted
        Args:
            mode: 0, return the full path
                  1, return the name only
                  2, return the directory name
        """
        if not line:
            return ''
        return line.split('\t', 1)[0]

    def _getDigestStartPos(self, line, mode):
        """
        return the start position of the digest returned by _getDigest()
        Args:
            mode: 0, return the start postion of full path
                  1, return the start postion of name only
                  2, return the start postion of directory name
        """
        return 0

    def _createHelp(self):
        help = []
        help.append('" <CR>/<double-click>/o : open file under cursor')
        help.append('" x : open file under cursor in a horizontally split window')
        help.append('" v : open file under cursor in a vertically split window')
        help.append('" t : open file under cursor in a new tabpage')
        help.append('" i/<Tab> : switch to input mode')
        help.append('" q/<Esc> : quit')
        help.append('" <F5> : refresh the cache')
        help.append('" <F1> : toggle this help')
        help.append('" ---------------------------------------------------------')
        return help

    def _afterEnter(self):
        super(TagExplManager, self)._afterEnter()
        id = int(lfEval('''matchadd('Lf_hl_tagFile', '^.\{-}\t\zs.\{-}\ze\t')'''))
        self._match_ids.append(id)
        id = int(lfEval('''matchadd('Lf_hl_tagType', ';"\t\zs[cdefFgmpstuv]\ze\(\t\|$\)')'''))
        self._match_ids.append(id)
        keyword = ["namespace", "class", "enum", "file", "function", "kind", "struct", "union"]
        for i in keyword:
            id = int(lfEval('''matchadd('Lf_hl_tagKeyword', '\(;"\t.\{-}\)\@<=%s:')''' % i))
            self._match_ids.append(id)

    def _beforeExit(self):
        super(TagExplManager, self)._beforeExit()
        for i in self._match_ids:
            lfCmd("silent! call matchdelete(%d)" % i)
        self._match_ids = []


#*****************************************************
# tagExplManager is a singleton
#*****************************************************
tagExplManager = TagExplManager()

__all__ = ['tagExplManager']

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import vim
import sys
import time
import operator
import itertools
import multiprocessing
from functools import partial
from functools import wraps
from .instance import LfInstance
from .cli import LfCli
from .utils import *
from .fuzzyMatch import FuzzyMatch

is_fuzzyEngine_C = False
try:
    import fuzzyEngine
    is_fuzzyEngine_C = True
    cpu_count = multiprocessing.cpu_count()
    lfCmd("let g:Lf_fuzzyEngine_C = 1")
except ImportError:
    lfCmd("let g:Lf_fuzzyEngine_C = 0")

is_fuzzyMatch_C = False
try:
    import fuzzyMatchC
    is_fuzzyMatch_C = True
    lfCmd("let g:Lf_fuzzyMatch_C = 1")
except ImportError:
    lfCmd("let g:Lf_fuzzyMatch_C = 0")

if sys.version_info >= (3, 0):
    def isAscii(str):
        try:
            str.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False
else:
    def isAscii(str):
        try:
            str.decode("ascii")
            return True
        except UnicodeDecodeError:
            return False


def modifiableController(func):
    @wraps(func)
    def deco(self, *args, **kwargs):
        if self._getExplorer().getStlCategory() in ("Search_History", "Cmd_History"):
            return func(self, *args, **kwargs)
        self._getInstance().buffer.options['modifiable'] = True
        func(self, *args, **kwargs)
        self._getInstance().buffer.options['modifiable'] = False
    return deco

#*****************************************************
# Manager
#*****************************************************
class Manager(object):
    def __init__(self):
        self._autochdir = 0
        self._instance = None
        self._cli = LfCli()
        self._explorer = None
        self._content = []
        self._index = 0
        self._help_length = 0
        self._show_help = False
        self._selections = {}
        self._highlight_pos = []
        self._highlight_refine_pos = []
        self._highlight_ids = []
        self._orig_line = ''
        self._launched = False
        self._ctrlp_pressed = False
        self._fuzzy_engine = None
        self._result_content = []
        self._getExplClass()

    #**************************************************************
    # abstract methods, in fact all the functions can be overridden
    #**************************************************************
    def _getExplClass(self):
        """
        this function MUST be overridden
        return the name of Explorer class
        """
        raise NotImplementedError("Can't instantiate abstract class Manager "
                                  "with abstract methods _getExplClass")

    def _defineMaps(self):
        pass

    def _cmdExtension(self, cmd):
        """
        this function can be overridden to add new cmd
        if return true, exit the input loop
        """
        pass

    def _argaddFiles(self, files):
        # It will raise E480 without 'silent!'
        lfCmd("silent! argdelete *")
        for file in files:
            lfCmd("argadd %s" % escSpecial(file))

    def _acceptSelection(self, *args, **kwargs):
        if len(args) == 0:
            return
        file = args[0]
        try:
            if file.startswith('+'):
                file = os.path.abspath(file)
            lfCmd("hide edit %s" % escSpecial(file))
        except vim.error as e: # E37
            lfPrintError(e)

    def _getDigest(self, line, mode):
        """
        this function can be overridden
        specify what part in the line to be processed and highlighted
        Args:
            mode: 0, return the full path
                  1, return the name only
                  2, return the directory name
        """
        if mode == 0:
            return line
        elif mode == 1:
            return getBasename(line)
        else:
            return getDirname(line)

    def _getDigestStartPos(self, line, mode):
        """
        this function can be overridden
        return the start position of the digest returned by _getDigest()
        Args:
            mode: 0, return the start postion of full path
                  1, return the start postion of name only
                  2, return the start postion of directory name
        """
        if mode == 0 or mode == 2:
            return 0
        else:
            return lfBytesLen(getDirname(line))

    def _createHelp(self):
        return []

    def _setStlMode(self, **kwargs):
        if self._cli.isFuzzy:
            if self._getExplorer().supportsNameOnly():
                if self._cli.isFullPath:
                    mode = 'FullPath'
                else:
                    mode = 'NameOnly'
            else:
                mode = 'Fuzzy'
        else:
            mode = 'Regex'

        modes = {"--nameOnly", "--fullPath", "--fuzzy", "--regex"}
        for opt in kwargs.get("arguments", {}):
            if opt in modes:
                if opt == "--regex":
                    mode = 'Regex'
                elif self._getExplorer().supportsNameOnly():
                    if opt == "--nameOnly":
                        mode = 'NameOnly'
                    elif opt == "--fullPath":
                        mode = 'FullPath'
                    else: # "--fuzzy"
                        if self._cli.isFullPath:
                            mode = 'FullPath'
                        else:
                            mode = 'NameOnly'
                elif opt in ("--nameOnly", "--fullPath", "--fuzzy"):
                        mode = 'Fuzzy'

                break

        self._getInstance().setStlMode(mode)
        self._cli.setCurrentMode(mode)

    def _beforeEnter(self):
        self._resetAutochdir()

    def _afterEnter(self):
        self._cleanup()
        self._defineMaps()
        lfCmd("runtime syntax/leaderf.vim")
        if is_fuzzyEngine_C:
            self._fuzzy_engine = fuzzyEngine.createFuzzyEngine(cpu_count, False)

    def _beforeExit(self):
        self._cleanup()
        self._getExplorer().cleanup()
        if self._fuzzy_engine:
            fuzzyEngine.closeFuzzyEngine(self._fuzzy_engine)
            self._fuzzy_engine = None

    def _afterExit(self):
        pass

    def _bangEnter(self):
        pass

    def _getList(self, pairs):
        """
        this function can be overridden
        return a list constructed from pairs
        Args:
            pairs: a list of tuple(weight, line, ...)
        """
        return [p[1] for p in pairs]

    def _getUnit(self):
        """
        indicates how many lines are considered as a unit
        """
        return 1

    def _supportsRefine(self):
        return False

    def _previewResult(self, preview):
        pass

    def _restoreOrigCwd(self):
        pass

    def _needExit(self, line, arguments):
        return True

    #**************************************************************

    def _needPreview(self, preview):
        """
        Args:
            preview:
                if True, always preview the result no matter what `g:Lf_PreviewResult` is.
        """
        preview_dict = lfEval("g:Lf_PreviewResult")
        category = self._getExplorer().getStlCategory()
        if not preview and int(preview_dict.get(category, 0)) == 0:
            return False

        if self._getInstance().window.cursor[0] <= self._help_length:
            return False

        if self._getInstance().empty() or vim.current.buffer != self._getInstance().buffer:
            return False

        if self._ctrlp_pressed == True:
            return True

        line = self._getInstance().currentLine
        if self._orig_line == line and self._getInstance().buffer.options['modifiable']:
            return False

        self._orig_line = line

        return True

    def _getInstance(self):
        if self._instance is None or self._instance.buffer not in vim.buffers:
            self._instance = LfInstance(self._getExplorer().getStlCategory(),
                                        self._beforeEnter,
                                        self._afterEnter,
                                        self._beforeExit,
                                        self._afterExit)
        return self._instance

    def _createHelpHint(self):
        if self._getExplorer().getStlCategory() in ("Search_History", "Cmd_History"):
            return
        help = []
        if not self._show_help:
            if lfEval("get(g:, 'Lf_HideHelp', 0)") == '0':
                help.append('" Press <F1> for help')
                help.append('" ---------------------------------------------------------')
        else:
            help += self._createHelp()
        self._help_length = len(help)
        cursor_line = self._getInstance().window.cursor[0]
        self._getInstance().buffer.append(help, 0)
        self._getInstance().window.cursor = (cursor_line + self._help_length, 0)

    def _hideHelp(self):
        del self._getInstance().buffer[:self._help_length]
        self._help_length = 0

    def _getExplorer(self):
        if self._explorer is None:
            self._explorer = self._getExplClass()()
        return self._explorer

    def _resetAutochdir(self):
        if int(lfEval("&autochdir")) == 1:
            self._autochdir = 1
            lfCmd("set noautochdir")
        else:
            self._autochdir = 0

    def _setAutochdir(self):
        if self._autochdir == 1:
            # When autochdir is set, Vim will change the current working directory
            # to the directory containing the file which was opened or selected.
            lfCmd("set autochdir")

    def _toUp(self):
        lfCmd("norm! k")

    def _toDown(self):
        if self._getInstance().getCurrentPos()[0] == self._getInstance().window.height:
            self._setResultContent()

        lfCmd("norm! j")

    def _pageUp(self):
        lfCmd('exec "norm! \<PageUp>"')

    def _pageDown(self):
        self._setResultContent()

        lfCmd('exec "norm! \<PageDown>"')

    def _leftClick(self):
        if self._getInstance().window.number == int(lfEval("v:mouse_win")):
            lfCmd("exec v:mouse_lnum")
            lfCmd("exec 'norm!'.v:mouse_col.'|'")
            self.clearSelections()
            exit_loop = False
        else:
            self.quit()
            exit_loop = True
        return exit_loop

    def _search(self, content, is_continue=False, step=40000):
        self.clearSelections()
        self._clearHighlights()
        self._clearHighlightsPos()
        self._cli.highlightMatches()
        if not self._cli.pattern:   # e.g., when <BS> or <Del> is typed
            self._getInstance().setBuffer(content)
            self._getInstance().setStlResultsCount(len(content))
            return

        if self._cli.isFuzzy:
            self._fuzzySearch(content, is_continue, step)
        else:
            self._regexSearch(content, is_continue, step)

        self._previewResult(False)

    def _filter(self, step, filter_method, content, is_continue,
                use_fuzzy_engine=False, return_index=False):
        """ Construct a list from result of filter_method(content).

        Args:
            step: An integer to indicate the number of lines to filter one time.
            filter_method: A function to apply `content` as parameter and
                return an iterable.
            content: The list to be filtered.
        """
        unit = self._getUnit()
        step = step // unit * unit
        length = len(content)
        if self._index == 0:
            self._previous_result = []
            self._cb_content = []
            self._result_content = content
            self._index = min(step, length)
            cur_content = content[:self._index]
        else:
            if not is_continue and not self._getInstance().empty():
                self._cb_content += self._result_content

            if len(self._cb_content) >= step:
                cur_content = self._cb_content[:step]
                self._cb_content = self._cb_content[step:]
            else:
                cur_content = self._cb_content
                left = step - len(self._cb_content)
                self._cb_content = []
                if self._index < length:
                    end = min(self._index + left, length)
                    cur_content += content[self._index:end]
                    self._index = end

        if use_fuzzy_engine:
            if return_index:
                mode = 0 if self._cli.isFullPath else 1
                tmp_content = [self._getDigest(line, mode) for line in cur_content]
                result = filter_method(source=tmp_content)
                result = (result[0], [cur_content[i] for i in result[1]])
            else:
                result = filter_method(source=cur_content)

            if is_continue:
                self._previous_result = (self._previous_result[0] + result[0],
                                         self._previous_result[1] + result[1])
                result = self._previous_result
            else:
                self._previous_result = result
        else:
            result = list(filter_method(cur_content))
            if is_continue:
                self._previous_result += result
                result = self._previous_result
            else:
                self._previous_result = result

        return result

    def _fuzzyFilter(self, is_full_path, get_weight, iterable):
        """
        return a list, each item is a pair (weight, line)
        """
        getDigest = partial(self._getDigest, mode=0 if is_full_path else 1)
        pairs = ((get_weight(getDigest(line)), line) for line in iterable)
        MIN_WEIGHT = fuzzyMatchC.MIN_WEIGHT if is_fuzzyMatch_C else FuzzyMatch.MIN_WEIGHT
        return (p for p in pairs if p[0] > MIN_WEIGHT)

    def _refineFilter(self, first_get_weight, get_weight, iterable):
        getDigest = self._getDigest
        triples = ((first_get_weight(getDigest(line, 1)),
                    get_weight(getDigest(line, 2)), line)
                    for line in iterable)
        MIN_WEIGHT = fuzzyMatchC.MIN_WEIGHT if is_fuzzyMatch_C else FuzzyMatch.MIN_WEIGHT
        return ((i[0] + i[1], i[2]) for i in triples if i[0] > MIN_WEIGHT and i[1] > MIN_WEIGHT)

    def _fuzzySearch(self, content, is_continue, step):
        encoding = lfEval("&encoding")
        use_fuzzy_engine = False
        use_fuzzy_match_c = False
        if self._cli.isRefinement:
            if self._cli.pattern[0] == '':    # e.g. ;abc
                if self._fuzzy_engine and isAscii(self._cli.pattern[1]):
                    use_fuzzy_engine = True
                    return_index = True
                    pattern = fuzzyEngine.initPattern(self._cli.pattern[1])
                    filter_method = partial(fuzzyEngine.fuzzyMatchEx, engine=self._fuzzy_engine,
                                            pattern=pattern, is_name_only=False, sort_results=not is_continue)
                    getHighlights = partial(fuzzyEngine.getHighlights, engine=self._fuzzy_engine,
                                            pattern=pattern, is_name_only=False)
                    highlight_method = partial(self._highlight, True, getHighlights, True)
                elif is_fuzzyMatch_C and isAscii(self._cli.pattern[1]):
                    use_fuzzy_match_c = True
                    pattern = fuzzyMatchC.initPattern(self._cli.pattern[1])
                    getWeight = partial(fuzzyMatchC.getWeight, pattern=pattern, is_name_only=False)
                    getHighlights = partial(fuzzyMatchC.getHighlights, pattern=pattern, is_name_only=False)
                    filter_method = partial(self._fuzzyFilter, True, getWeight)
                    highlight_method = partial(self._highlight, True, getHighlights)
                else:
                    fuzzy_match = FuzzyMatch(self._cli.pattern[1], encoding)
                    getWeight = fuzzy_match.getWeight
                    getHighlights = fuzzy_match.getHighlights
                    filter_method = partial(self._fuzzyFilter, True, getWeight)
                    highlight_method = partial(self._highlight, True, getHighlights)
            else:   # e.g. abc;def
                if is_fuzzyMatch_C and isAscii(self._cli.pattern[0]):
                    is_ascii_0 = True
                    pattern_0 = fuzzyMatchC.initPattern(self._cli.pattern[0])
                    getWeight_0 = partial(fuzzyMatchC.getWeight, pattern=pattern_0, is_name_only=True)
                    getHighlights_0 = partial(fuzzyMatchC.getHighlights, pattern=pattern_0, is_name_only=True)
                else:
                    is_ascii_0 = False
                    fuzzy_match_0 = FuzzyMatch(self._cli.pattern[0], encoding)
                    getWeight_0 = fuzzy_match_0.getWeight
                    getHighlights_0 = fuzzy_match_0.getHighlights

                if is_fuzzyMatch_C and isAscii(self._cli.pattern[1]):
                    is_ascii_1 = True
                    pattern_1 = fuzzyMatchC.initPattern(self._cli.pattern[1])
                    getWeight_1 = partial(fuzzyMatchC.getWeight, pattern=pattern_1, is_name_only=False)
                    getHighlights_1 = partial(fuzzyMatchC.getHighlights, pattern=pattern_1, is_name_only=False)
                else:
                    is_ascii_1 = False
                    fuzzy_match_1 = FuzzyMatch(self._cli.pattern[1], encoding)
                    getWeight_1 = fuzzy_match_1.getWeight
                    getHighlights_1 = fuzzy_match_1.getHighlights

                    use_fuzzy_match_c = is_ascii_0 and is_ascii_1

                filter_method = partial(self._refineFilter, getWeight_0, getWeight_1)
                highlight_method = partial(self._highlightRefine, getHighlights_0, getHighlights_1)
        else:
            if self._fuzzy_engine and isAscii(self._cli.pattern):
                use_fuzzy_engine = True
                pattern = fuzzyEngine.initPattern(self._cli.pattern)
                if self._getExplorer().getStlCategory() == "File" and self._cli.isFullPath:
                    return_index = False
                    filter_method = partial(fuzzyEngine.fuzzyMatch, engine=self._fuzzy_engine, pattern=pattern,
                                            is_name_only=False, sort_results=not is_continue)
                elif self._getExplorer().getStlCategory() in ["Self", "Buffer", "Mru", "BufTag",
                        "Function", "History", "Cmd_History", "Search_History"]:
                    return_index = True
                    filter_method = partial(fuzzyEngine.fuzzyMatchEx, engine=self._fuzzy_engine, pattern=pattern,
                                            is_name_only=True, sort_results=not is_continue)
                else:
                    return_index = True
                    filter_method = partial(fuzzyEngine.fuzzyMatchEx, engine=self._fuzzy_engine, pattern=pattern,
                                            is_name_only=not self._cli.isFullPath, sort_results=not is_continue)

                getHighlights = partial(fuzzyEngine.getHighlights, engine=self._fuzzy_engine,
                                        pattern=pattern, is_name_only=not self._cli.isFullPath)
                highlight_method = partial(self._highlight, self._cli.isFullPath, getHighlights, True)
            elif is_fuzzyMatch_C and isAscii(self._cli.pattern):
                use_fuzzy_match_c = True
                pattern = fuzzyMatchC.initPattern(self._cli.pattern)
                if self._getExplorer().getStlCategory() == "File" and self._cli.isFullPath:
                    getWeight = partial(fuzzyMatchC.getWeight, pattern=pattern, is_name_only=False)
                    getHighlights = partial(fuzzyMatchC.getHighlights, pattern=pattern, is_name_only=False)
                else:
                    getWeight = partial(fuzzyMatchC.getWeight, pattern=pattern, is_name_only=True)
                    getHighlights = partial(fuzzyMatchC.getHighlights, pattern=pattern, is_name_only=True)

                filter_method = partial(self._fuzzyFilter, self._cli.isFullPath, getWeight)
                highlight_method = partial(self._highlight, self._cli.isFullPath, getHighlights)
            else:
                fuzzy_match = FuzzyMatch(self._cli.pattern, encoding)
                if self._getExplorer().getStlCategory() == "File" and self._cli.isFullPath:
                    filter_method = partial(self._fuzzyFilter,
                                            self._cli.isFullPath,
                                            fuzzy_match.getWeight2)
                elif self._getExplorer().getStlCategory() in ["Self", "Buffer", "Mru", "BufTag",
                        "Function", "History", "Cmd_History", "Search_History"]:
                    filter_method = partial(self._fuzzyFilter,
                                            self._cli.isFullPath,
                                            fuzzy_match.getWeight3)
                else:
                    filter_method = partial(self._fuzzyFilter,
                                            self._cli.isFullPath,
                                            fuzzy_match.getWeight)

                highlight_method = partial(self._highlight,
                                           self._cli.isFullPath,
                                           fuzzy_match.getHighlights)

        if use_fuzzy_engine:
            if  return_index == True:
                step = 20000 * cpu_count
            else:
                step = 40000 * cpu_count

            pair = self._filter(step, filter_method, content, is_continue, True, return_index)
            if is_continue: # result is not sorted
                pairs = sorted(zip(*pair), key=operator.itemgetter(0), reverse=True)
                self._result_content = self._getList(pairs)
            else:
                self._result_content = pair[1]
            self._getInstance().setBuffer(self._result_content[:self._getInstance().window.height + 100])
            self._getInstance().setStlResultsCount(len(self._result_content))
        else:
            if step == 40000:
                if use_fuzzy_match_c:
                    step = 40000
                elif self._getExplorer().supportsNameOnly() and self._cli.isFullPath:
                    step = 6000
                else:
                    step = 12000

            pairs = self._filter(step, filter_method, content, is_continue)
            pairs.sort(key=operator.itemgetter(0), reverse=True)
            self._result_content = self._getList(pairs)
            self._getInstance().setBuffer(self._result_content[:self._getInstance().window.height + 100])
            self._getInstance().setStlResultsCount(len(self._result_content))

        highlight_method()

    def _clearHighlights(self):
        for i in self._highlight_ids:
            lfCmd("silent! call matchdelete(%d)" % i)
        self._highlight_ids = []

    def _clearHighlightsPos(self):
        self._highlight_pos = []
        self._highlight_refine_pos = []

    def _resetHighlights(self):
        self._clearHighlights()
        for i, pos in enumerate(self._highlight_pos, self._help_length + 1):
            pos = [[i] + p for p in pos]
            # The maximum number of positions is 8 in matchaddpos().
            for j in range(0, len(pos), 8):
                id = int(lfEval("matchaddpos('Lf_hl_match', %s)" % str(pos[j:j+8])))
                self._highlight_ids.append(id)

        for i, pos in enumerate(self._highlight_refine_pos, self._help_length + 1):
            pos = [[i] + p for p in pos]
            # The maximum number of positions is 8 in matchaddpos().
            for j in range(0, len(pos), 8):
                id = int(lfEval("matchaddpos('Lf_hl_matchRefine', %s)" % str(pos[j:j+8])))
                self._highlight_ids.append(id)

    def _highlight(self, is_full_path, get_highlights, use_fuzzy_engine=False):
        # matchaddpos() is introduced by Patch 7.4.330
        if (lfEval("exists('*matchaddpos')") == '0' or
                lfEval("g:Lf_HighlightIndividual") == '0'):
            return
        cb = self._getInstance().buffer
        if self._getInstance().empty(): # buffer is empty.
            return

        highlight_number = int(lfEval("g:Lf_NumberOfHighlight"))
        self._clearHighlights()

        getDigest = partial(self._getDigest, mode=0 if is_full_path else 1)
        unit = self._getUnit()

        if use_fuzzy_engine:
            self._highlight_pos = get_highlights(source=[getDigest(line)
                                                         for line in cb[:][:highlight_number:unit]])
        else:
            # e.g., self._highlight_pos = [ [ [2,3], [6,2] ], [ [1,4], [7,6], ... ], ... ]
            # where [2, 3] indicates the highlight starts at the 2nd column with the
            # length of 3 in bytes
            self._highlight_pos = [get_highlights(getDigest(line))
                                   for line in cb[:][:highlight_number:unit]]
        for i, pos in enumerate(self._highlight_pos):
            start_pos = self._getDigestStartPos(cb[unit*i], 0 if is_full_path else 1)
            if start_pos > 0:
                for j in range(len(pos)):
                    pos[j][0] += start_pos
            pos = [[unit*i+1] + p for p in pos]
            # The maximum number of positions is 8 in matchaddpos().
            for j in range(0, len(pos), 8):
                id = int(lfEval("matchaddpos('Lf_hl_match', %s)" % str(pos[j:j+8])))
                self._highlight_ids.append(id)

    def _highlightRefine(self, first_get_highlights, get_highlights):
        # matchaddpos() is introduced by Patch 7.4.330
        if (lfEval("exists('*matchaddpos')") == '0' or
                lfEval("g:Lf_HighlightIndividual") == '0'):
            return
        cb = self._getInstance().buffer
        if self._getInstance().empty(): # buffer is empty.
            return

        highlight_number = int(lfEval("g:Lf_NumberOfHighlight"))
        self._clearHighlights()

        getDigest = self._getDigest
        unit = self._getUnit()
        self._highlight_pos = [first_get_highlights(getDigest(line, 1))
                               for line in cb[:][:highlight_number:unit]]
        for i, pos in enumerate(self._highlight_pos):
            start_pos = self._getDigestStartPos(cb[unit*i], 1)
            if start_pos > 0:
                for j in range(len(pos)):
                    pos[j][0] += start_pos
            pos = [[unit*i+1] + p for p in pos]
            # The maximum number of positions is 8 in matchaddpos().
            for j in range(0, len(pos), 8):
                id = int(lfEval("matchaddpos('Lf_hl_match', %s)" % str(pos[j:j+8])))
                self._highlight_ids.append(id)

        self._highlight_refine_pos = [get_highlights(getDigest(line, 2))
                                      for line in cb[:][:highlight_number:unit]]
        for i, pos in enumerate(self._highlight_refine_pos):
            start_pos = self._getDigestStartPos(cb[unit*i], 2)
            if start_pos > 0:
                for j in range(len(pos)):
                    pos[j][0] += start_pos
            pos = [[unit*i+1] + p for p in pos]
            # The maximum number of positions is 8 in matchaddpos().
            for j in range(0, len(pos), 8):
                id = int(lfEval("matchaddpos('Lf_hl_matchRefine', %s)" % str(pos[j:j+8])))
                self._highlight_ids.append(id)

    def _regexFilter(self, iterable):
        try:
            if ('-2' == lfEval("g:LfNoErrMsgMatch('', '%s')" % escQuote(self._cli.pattern))):
                return iter([])
            else:
                return (line for line in iterable
                        if '-1' != lfEval("g:LfNoErrMsgMatch('%s', '%s')" %
                        (escQuote(self._getDigest(line, 0).strip()),
                         escQuote(self._cli.pattern))))
        except vim.error:
            return iter([])

    def _regexSearch(self, content, is_continue, step):
        if not self._cli.isPrefix:
            self._index = 0
        lines = self._filter(8000, self._regexFilter, content, is_continue)
        self._getInstance().setBuffer(lines)

    def clearSelections(self):
        for i in self._selections.values():
            lfCmd("call matchdelete(%d)" % i)
        self._selections.clear()

    def _cleanup(self):
        if lfEval("g:Lf_RememberLastSearch") == '0':
            self._cli.clear()
            self._clearHighlights()
            self._clearHighlightsPos()
            self._help_length = 0
        self.clearSelections()

    @modifiableController
    def toggleHelp(self):
        self._show_help = not self._show_help
        del self._getInstance().buffer[:self._help_length]
        self._createHelpHint()
        self.clearSelections()
        self._resetHighlights()

    def _accept(self, file, mode, *args, **kwargs):
        if file:
            if mode == '':
                pass
            elif mode == 'h':
                lfCmd("split")
            elif mode == 'v':
                lfCmd("vsplit")
            elif mode == 't':
                lfCmd("tabedit")
                tab_pos = int(lfEval("g:Lf_TabpagePosition"))
                if tab_pos == 0:
                    lfCmd("tabm 0")
                elif tab_pos == 1:
                    lfCmd("tabm -1")
                elif tab_pos == 3:
                    lfCmd("tabm")
            self._acceptSelection(file, *args, **kwargs)

    def accept(self, mode=''):
        if self._getInstance().window.cursor[0] <= self._help_length:
            lfCmd("norm! j")
            return
        if len(self._selections) > 0:
            files = []
            for i in sorted(self._selections.keys()):
                files.append(self._getInstance().buffer[i-1])
            if "--stayOpen" in self._arguments:
                try:
                    vim.current.tabpage, vim.current.window, vim.current.buffer = self._getInstance().getOriginalPos()
                except vim.error: # error if original buffer is an No Name buffer
                    pass
            else:
                self._getInstance().exitBuffer()
            if mode == '':
                self._argaddFiles(files)
                self._accept(files[0], mode)
            else:
                for file in files:
                    self._accept(file, mode)
            need_exit = True
        else:
            file = self._getInstance().currentLine
            line_nr = self._getInstance().window.cursor[0]
            need_exit = self._needExit(file, self._arguments)
            if need_exit:
                if "--stayOpen" in self._arguments:
                    try:
                        vim.current.tabpage, vim.current.window, vim.current.buffer = self._getInstance().getOriginalPos()
                    except vim.error: # error if original buffer is an No Name buffer
                        pass
                else:
                    self._getInstance().exitBuffer()
            self._accept(file, mode, self._getInstance().buffer, line_nr) # for bufTag

        if need_exit:
            self._setAutochdir()
            self._restoreOrigCwd()
            return None
        else:
            self._beforeExit()
            self._content = vim.current.buffer[:]
            return False

    def quit(self):
        self._getInstance().exitBuffer()
        self._setAutochdir()
        self._restoreOrigCwd()

    def refresh(self, normal_mode=True):
        self._getExplorer().cleanup()
        content = self._getExplorer().getFreshContent()
        if not content:
            lfCmd("echohl Error | redraw | echo ' No content!' | echohl NONE")
            return

        if normal_mode: # when called in Normal mode
            self._getInstance().buffer.options['modifiable'] = True

        self._clearHighlights()
        self._clearHighlightsPos()
        self.clearSelections()

        self._getInstance().initBuffer(content, self._getUnit(), self._getExplorer().setContent)
        self._content = self._getInstance().buffer[:]
        self._iteration_end = True

        if self._cli.pattern:
            self._index = 0
            self._search(self._content)

        if normal_mode: # when called in Normal mode
            self._createHelpHint()
            self._resetHighlights()
            self._getInstance().buffer.options['modifiable'] = False

    def addSelections(self):
        nr = self._getInstance().window.number
        if (int(lfEval("v:mouse_win")) != 0 and
                nr != int(lfEval("v:mouse_win"))):
            return
        elif nr == int(lfEval("v:mouse_win")):
            lfCmd("exec v:mouse_lnum")
            lfCmd("exec 'norm!'.v:mouse_col.'|'")
        line_nr = self._getInstance().window.cursor[0]
        if line_nr <= self._help_length:
            lfCmd("norm! j")
            return

        if line_nr in self._selections:
            lfCmd("call matchdelete(%d)" % self._selections[line_nr])
            del self._selections[line_nr]
        else:
            id = int(lfEval("matchadd('Lf_hl_selection', '\%%%dl.')" % line_nr))
            self._selections[line_nr] = id

    def selectMulti(self):
        orig_line = self._getInstance().window.cursor[0]
        nr = self._getInstance().window.number
        if (int(lfEval("v:mouse_win")) != 0 and
                nr != int(lfEval("v:mouse_win"))):
            return
        elif nr == int(lfEval("v:mouse_win")):
            cur_line = int(lfEval("v:mouse_lnum"))
        self.clearSelections()
        for i in range(min(orig_line, cur_line), max(orig_line, cur_line)+1):
            if i > self._help_length and i not in self._selections:
                id = int(lfEval("matchadd('Lf_hl_selection', '\%%%dl.')" % (i)))
                self._selections[i] = id

    def selectAll(self):
        line_num = len(self._getInstance().buffer)
        if line_num > 300:
            lfCmd("echohl Error | redraw | echo ' Too many files selected!' | echohl NONE")
            lfCmd("sleep 1")
            return
        for i in range(line_num):
            if i >= self._help_length and i+1 not in self._selections:
                id = int(lfEval("matchadd('Lf_hl_selection', '\%%%dl.')" % (i+1)))
                self._selections[i+1] = id

    def startExplorer(self, win_pos, *args, **kwargs):
        self._arguments = kwargs.get("arguments", {})
        self._cli.setNameOnlyFeature(self._getExplorer().supportsNameOnly())
        self._cli.setRefineFeature(self._supportsRefine())
        lfCmd("echohl WarningMsg | redraw |"
              "echo ' searching ...' | echohl NONE")
        content = self._getExplorer().getContent(*args, **kwargs)
        if not content:
            lfCmd("echohl Error | redraw | echo ' No content!' | echohl NONE")
            return
        self._getInstance().enterBuffer(win_pos)

        self._getInstance().setStlCategory(self._getExplorer().getStlCategory())
        self._setStlMode(**kwargs)
        self._getInstance().setStlCwd(self._getExplorer().getStlCurDir())

        if lfEval("g:Lf_RememberLastSearch") == '1' and self._launched and self._cli.pattern:
            pass
        else:
            lfCmd("normal! gg")
            self._index = 0

        self._start_time = time.time()

        self._pattern = kwargs.get("pattern", "") or kwargs.get("arguments", {}).get("--input", "")
        self._cli.setPattern(self._pattern)

        if isinstance(content, list):
            if len(content[0]) == len(content[0].rstrip("\r\n")):
                self._content = content
            else:
                self._content = [line.rstrip("\r\n") for line in content]
            self._iteration_end = True
            self._getInstance().setStlTotal(len(self._content)//self._getUnit())
            self._result_content = self._content
            self._getInstance().setStlResultsCount(len(self._content))
            if lfEval("g:Lf_RememberLastSearch") == '1' and self._launched and self._cli.pattern:
                pass
            else:
                self._getInstance().setBuffer(self._content[:self._getInstance().window.height + 100])

            if not kwargs.get('bang', 0):
                self.input()
            else:
                lfCmd("echo")
                self._getInstance().buffer.options['modifiable'] = False
                self._bangEnter()
        else:
            self._result_content = []
            if lfEval("g:Lf_CursorBlink") == '0':
                self._getInstance().initBuffer(content, self._getUnit(), self._getExplorer().setContent)
                self._content = self._getInstance().buffer[:]
                self._iteration_end = True
                self.input()
            else:
                self._content = []
                self._iteration_end = False
                self._backup = None
                self.input(content)

        self._launched = True

    def setContent(self, content):
        if content is None or self._iteration_end == True:
            if self._cli.pattern and (self._index < len(self._content) or len(self._cb_content) > 0):
                if self._fuzzy_engine:
                    step = 10000 * cpu_count
                else:
                    step = 10000
                self._search(self._content, True, step)
                return True
            return False

        i = -1
        for i, line in enumerate(itertools.islice(content, 10)):
            if line is None:
                continue
            self._content.append(line)
            if self._index == 0:
                if self._getInstance().empty():
                    self._getInstance().buffer[0] = line
                else:
                    self._getInstance().appendLine(line)

        if i == -1:
            self._iteration_end = True
            self._getExplorer().setContent(self._content)
            self._getInstance().setStlTotal(len(self._content)//self._getUnit())
            self._getInstance().setStlResultsCount(len(self._content))
            lfCmd("redrawstatus")
            if self._index < len(self._content):
                self._search(self._content, True, 1000)
            return False
        else:
            if time.time() - self._start_time > 0.1:
                self._start_time = time.time()
                self._getInstance().setStlTotal(len(self._content)//self._getUnit())
                self._getInstance().setStlResultsCount(len(self._content))
                lfCmd("redrawstatus")
                if self._index < len(self._content):
                    self._search(self._content, True, 1000)
            return True

    def _setResultContent(self):
        if len(self._result_content) > len(self._getInstance().buffer):
            self._getInstance().setBuffer(self._result_content)

    @modifiableController
    def input(self, content=None):
        self._hideHelp()
        self._resetHighlights()

        if self._iteration_end == False and self._backup:
            content = self._backup

        if self._pattern:
            self._search(self._content)

        for cmd in self._cli.input(partial(self.setContent, content)):
            if equal(cmd, '<Update>'):
                self._search(self._content)
            elif equal(cmd, '<Shorten>'):
                lfCmd("normal! gg")
                self._index = 0 # search from beginning
                self._search(self._content)
            elif equal(cmd, '<Mode>'):
                self._setStlMode()
                lfCmd("normal! gg")
                self._index = 0 # search from beginning
                if self._cli.pattern:
                    self._search(self._content)
            elif equal(cmd, '<Up>') or equal(cmd, '<C-K>'):
                self._toUp()
                self._previewResult(False)
            elif equal(cmd, '<Down>') or equal(cmd, '<C-J>'):
                self._toDown()
                self._previewResult(False)
            elif equal(cmd, '<LeftMouse>'):
                if self._leftClick():
                    break
                self._previewResult(False)
            elif equal(cmd, '<2-LeftMouse>'):
                self._leftClick()
                if self.accept() is None:
                    break
            elif equal(cmd, '<CR>'):
                if self.accept() is None:
                    break
            elif equal(cmd, '<C-X>'):
                if self.accept('h') is None:
                    break
            elif equal(cmd, '<C-]>'):
                if self.accept('v') is None:
                    break
            elif equal(cmd, '<C-T>'):
                if self.accept('t') is None:
                    break
            elif equal(cmd, '<Quit>'):
                self.quit()
                break
            elif equal(cmd, '<Tab>'):   # switch to Normal mode
                self._setResultContent()
                self.clearSelections()
                self._cli.hideCursor()
                self._createHelpHint()
                self._resetHighlights()
                self._backup = content
                break
            elif equal(cmd, '<F5>'):
                self.refresh(False)
            elif equal(cmd, '<C-LeftMouse>') or equal(cmd, '<C-S>'):
                if self._getExplorer().supportsMulti():
                    self.addSelections()
            elif equal(cmd, '<S-LeftMouse>'):
                if self._getExplorer().supportsMulti():
                    self.selectMulti()
            elif equal(cmd, '<C-A>'):
                if self._getExplorer().supportsMulti():
                    self.selectAll()
            elif equal(cmd, '<C-L>'):
                self.clearSelections()
            elif equal(cmd, '<C-P>'):
                self._ctrlp_pressed = True
                self._previewResult(True)
                self._ctrlp_pressed = False
            elif equal(cmd, '<PageUp>'):
                self._pageUp()
                self._previewResult(False)
            elif equal(cmd, '<PageDown>'):
                self._pageDown()
                self._previewResult(False)
            else:
                if self._cmdExtension(cmd):
                    break

#  vim: set ts=4 sw=4 tw=0 et :

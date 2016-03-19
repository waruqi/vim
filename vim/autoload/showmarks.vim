" This is the default, and used in ShowMarksSetup to set up info for any
" possible mark (not just those specified in the possibly user-supplied list
" of marks to show -- it can be changed on-the-fly).
let s:all_marks = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.'`^<>[]{}()\""


" Function: ShowMarksOn
" Description: Enable showmarks, and show them now.
function! showmarks#ShowMarksOn()
	if g:showmarks_enable == 0
		call showmarks#ShowMarksToggle()
	else
		call showmarks#ShowMarks()
	endif
endfunction

" Function: ShowMarksToggle()
" Description: This function toggles whether marks are displayed or not.
function! showmarks#ShowMarksToggle()
	if ! exists('b:showmarks_shown')
		let b:showmarks_shown = 0
	endif

	if b:showmarks_shown == 0
		let g:showmarks_enable = 1
		call showmarks#ShowMarks()
		if g:showmarks_auto_toggle
			augroup ShowMarks
				autocmd!
				autocmd CursorHold * call showmarks#ShowMarks()
			augroup END
		endif
	else
		let g:showmarks_enable = 0
		call s:ShowMarksHideAll()
		if g:showmarks_auto_toggle
			augroup ShowMarks
				autocmd!
				autocmd BufEnter * call s:ShowMarksHideAll()
			augroup END
		endif
	endif
endfunction

" Function: ShowMarks()
" Description: This function runs through all the marks and displays or
" removes signs as appropriate. It is called on the CursorHold autocommand.
" We use the l:mark_at_line variable to track what marks we've shown (placed)
" in this call to ShowMarks; to only actually place the first mark on any
" particular line -- this forces only the first mark (according to the order
" of showmarks_include) to be shown (i.e., letters take precedence over marks
" like paragraph and sentence.)
function! showmarks#ShowMarks()
	if g:showmarks_enable == 0
		return
	endif

	if   ((match(g:showmarks_ignore_type, "[Hh]") > -1) && (&buftype    == "help"    ))
	\ || ((match(g:showmarks_ignore_type, "[Qq]") > -1) && (&buftype    == "quickfix"))
	\ || ((match(g:showmarks_ignore_type, "[Pp]") > -1) && (&pvw        == 1         ))
	\ || ((match(g:showmarks_ignore_type, "[Rr]") > -1) && (&readonly   == 1         ))
	\ || ((match(g:showmarks_ignore_type, "[Mm]") > -1) && (&modifiable == 0         ))
		return
	endif

	let config_marks = s:IncludeMarks()
	redir => msg
	silent! execute 'marks ' . config_marks
	redir END
	let listed_marks = map(split(msg, '\n')[1:-1], escape('matchstr(v:val, "\S")', '\'))
	let marks = []
	for c in listed_marks + ['(', ')', '{', '}']
		if stridx(config_marks, c) > -1
			call add(marks, c)
		endif
	endfor
	let l:mark_at_line = {}

	for c in marks
		let line = s:LineNumberOf(c)
		if line > 0
			let placed_mark = get(l:mark_at_line, line, '')
			if strlen(placed_mark)
				if c =~ '\a'
					call s:DefineHighlight('')
					call s:ChangeHighlight(placed_mark, 'ShowMarksHLm')
				endif
			else
				call s:DefineSign(c)
				call s:DefineHighlight(c)
				call s:ChangeHighlight(c, s:TextHLGroup(c))
				let l:mark_at_line[line] = c
				call s:PlaceSign(c)
			endif
		endif
	endfor

	" TODO rewrite clearly
	for placed in filter(s:SignPlacementInfo(), 'index(values(l:mark_at_line), substitute(v:val["name"], "ShowMarks_", "", "")) == -1')
		execute 'sign unplace ' . placed.id . ' buffer=' . winbufnr(0)
	endfor

	let b:showmarks_shown = 1
endfunction

" Function: ShowMarksClearMark()
" Description: This function hides the mark at the current line.
" Only marks a-z and A-Z are supported.
function! showmarks#ShowMarksClearMark()
	let ln = line(".")
	let n = 0
	let s:maxmarks = strlen(s:IncludeMarks())
	while n < s:maxmarks
		let c = strpart(s:IncludeMarks(), n, 1)
		if c =~# '[a-zA-Z]' && ln == s:LineNumberOf(c)
			let id = n + (s:maxmarks * winbufnr(0))
			execute 'sign unplace '.id.' buffer='.winbufnr(0)
			execute "delmarks " . c
		endif
		let n = n + 1
	endwhile
endfunction

" Function: ShowMarksClearAll()
" Description: This function clears all marks in the buffer.
" Only marks a-z and A-Z are supported.
function! showmarks#ShowMarksClearAll()
	let n = 0
	let s:maxmarks = strlen(s:IncludeMarks())
	while n < s:maxmarks
		let c = strpart(s:IncludeMarks(), n, 1)
		if c =~# '[a-zA-Z]'
			let id = n + (s:maxmarks * winbufnr(0))
			execute 'sign unplace '.id.' buffer='.winbufnr(0)
			execute "delmarks " . c
		endif
		let n = n + 1
	endwhile
	let b:showmarks_shown = 0
endfunction

" Function: ShowMarksPlaceMark()
" Description: This function will place the next unplaced mark (in priority
" order) to the current location. The idea here is to automate the placement
" of marks so the user doesn't have to remember which marks are placed or not.
" Hidden marks are considered to be unplaced.
" Only marks a-z are supported.
function! showmarks#ShowMarksPlaceMark()
	" Find the first, next, and last [a-z] mark in showmarks_include (i.e.
	" priority order), so we know where to "wrap".
	let first_alpha_mark = -1
	let last_alpha_mark  = -1
	let next_mark        = -1

	if !exists('b:previous_auto_mark')
		let b:previous_auto_mark = -1
	endif

	" Find the next unused [a-z] mark (in priority order); if they're all
	" used, find the next one after the previously auto-assigned mark.
	let n = 0
	let s:maxmarks = strlen(s:IncludeMarks())
	while n < s:maxmarks
		let c = strpart(s:IncludeMarks(), n, 1)
		if c =~# '[a-z]'
			if s:LineNumberOf(c) <= 1
				" Found an unused [a-z] mark; we're done.
				let next_mark = n
				break
			endif

			if first_alpha_mark < 0
				let first_alpha_mark = n
			endif
			let last_alpha_mark = n
			if n > b:previous_auto_mark && next_mark == -1
				let next_mark = n
			endif
		endif
		let n = n + 1
	endwhile

	if next_mark == -1 && (b:previous_auto_mark == -1 || b:previous_auto_mark == last_alpha_mark)
		" Didn't find an unused mark, and haven't placed any auto-chosen marks yet,
		" or the previously placed auto-chosen mark was the last alpha mark --
		" use the first alpha mark this time.
		let next_mark = first_alpha_mark
	endif

	if (next_mark == -1)
		echohl WarningMsg
		echo 'No marks in [a-z] included! (No "next mark" to choose from)'
		echohl None
		return
	endif

	let c = strpart(s:IncludeMarks(), next_mark, 1)
	let b:previous_auto_mark = next_mark
	execute 'mark '.c
	call showmarks#ShowMarks()
endfunction

" Function: ShowMarksHooksMark()
" Description: Hooks normal m command for calling ShowMarks() with it.
function! showmarks#ShowMarksHooksMark()
	execute 'normal! m' . nr2char(getchar())
	call showmarks#ShowMarks()
endfunction


" Function: IncludeMarks()
" Description: This function returns the list of marks (in priority order) to
" show in this buffer.  Each buffer, if not already set, inherits the global
" setting; if the global include marks have not been set; that is set to the
" default value.
function! s:IncludeMarks()
	let key = 'showmarks_include'
	let marks = get(b:, key, get(g:, key, s:all_marks))
	if get(b:, 'showmarks_previous_include', '') != marks
		let b:showmarks_previous_include = marks
		call s:ShowMarksHideAll()
		call showmarks#ShowMarks()
	endif
	return marks
endfunction

" Function: LineNumberOf()
" Paramaters: mark - mark (e.g.: t) to find the line of.
" Description: Find line number of specified mark in current buffer.
" Returns: Line number.
function! s:LineNumberOf(mark)
	let pos = getpos("'" . a:mark)
	if pos[0] && pos[0] != bufnr("%")
		return 0
	else
		return pos[1]
	endif
endfunction

" Function: ShowMarksHideAll()
" Description: This function hides all marks in the buffer.
" It simply removes the signs.
function! s:ShowMarksHideAll()
	for placed in s:SignPlacementInfo()
		execute 'sign unplace ' . placed.id . ' buffer=' . winbufnr(0)
	endfor
	let b:showmarks_shown = 0
endfunction

" Function: DefineHighlight()
" Description: This function defines highlight.
function! s:DefineHighlight(mark)
	if a:mark != ''
		let texthl = s:TextHLGroup(a:mark)
		let mark_type = s:MarkType(a:mark)
	else
		let texthl = 'ShowMarksHLm'
		let mark_type = 'multi'
	endif

	redir => msg
	silent! execute ':highlight ' . texthl
	redir END

	if msg !~ 'cleared'
		return
	endif

	let highlight_args = get(g:, 'showmarks_hlargs_' . mark_type, '')
	let highlight_group = get(g:, 'showmarks_hlgroup_' . mark_type, '')

	if highlight_args == '' && highlight_group == ''
		return
	endif

	" Color group is given priority over args.
	if highlight_group != ''
		silent! execute ':highlight link ' . texthl . ' ' . highlight_group
	else
		silent! execute ':highlight ' . texthl . ' ' . highlight_args
	endif
endfunction

" Function: DefineSign()
function! s:DefineSign(mark)
	let sign_name = 'ShowMarks_' . a:mark
	silent! execute 'sign list ' . sign_name
	if v:errmsg =~ '^E155:' " E155 Unknown sign
		let mark_type = s:MarkType(a:mark)
		let text = printf('%.2s', get(g:, 'showmarks_text' . mark_type, "\t"))
		let text = substitute(text, '\v\t|\s', a:mark, '')
		let texthl = s:TextHLGroup(a:mark)
		let cmd = printf('sign define %s %s text=%s texthl=%s',
					\	sign_name,
					\	get(g:, 'showmarks_hlline_' . mark_type) ? 'linehl=' . texthl : '',
					\	text,
					\	texthl
					\ )
		execute escape(cmd, '\')
	endif
endfunction

" Function: SignId()
function! s:SignId(mark)
	let included_marks = s:IncludeMarks()
	return stridx(included_marks, a:mark) + (strlen(included_marks) * winbufnr(0))
endfunction

" Function: SignPlacementInfo()
" Description: get list of placed sign info {'id': n, 'line': n, 'name': s} in current buffer
function! s:SignPlacementInfo()
	redir => msg
	silent! execute printf('sign place buffer=%s', winbufnr(0))
	redir END
	let info = []
	let obj = {}
	let pattern = escape('\v\s+line=(\d+)\s+id=(\d+)\s+name=(\p+)', '=')
	for item in map(split(msg, '\n'), 'matchlist(v:val, ''' . pattern . ''')[1:3]')
		if len(item) > 0
			let [obj.line, obj.id, obj.name] = item
			call add(info, copy(obj))
		endif
	endfor
	return info
endfunction

" Function: PlaceSign()
function! s:PlaceSign(mark)
	let sign_id     = s:SignId(a:mark)
	let line_number = s:LineNumberOf(a:mark)
	execute printf('sign unplace %s buffer=%s',
				\	sign_id,
				\	winbufnr(0)
				\ )
	execute printf('sign place %s name=ShowMarks_%s line=%s buffer=%s',
				\	sign_id,
				\	a:mark,
				\	line_number,
				\	winbufnr(0)
				\ )
endfunction

" Function: ChangeHighlight()
" Description: redefine texthl attribute of mark
function! s:ChangeHighlight(mark_name, new_texthl)
	redir => old_def
	silent! execute printf('sign list ShowMarks_%s', a:mark_name)
	redir END
	let old_def = substitute(old_def, '\v.*sign\s+', '', '')
	let old_texthl = matchstr(old_def, '\vtexthl\=\zs.+\ze$')

	if old_texthl != a:new_texthl
		execute 'sign define ' . substitute(old_def, '\v(text|line)hl\=\zs\w+\ze', a:new_texthl, 'g')
	endif
endfunction

" Function: MarkType()
function! s:MarkType(char)
	if a:char =~ '\l'
		return 'lower'
	elseif a:char =~ '\u'
		return 'upper'
	else
		return 'other'
	endif
endfunction

" Function: TextHLGroup()
" Description: return proper texthl group name for character
function! s:TextHLGroup(char)
	return 'ShowMarksHL' . s:MarkType(a:char)[0]
endfunction


" -----------------------------------------------------------------------------
" vim:ts=4:sw=4:noet

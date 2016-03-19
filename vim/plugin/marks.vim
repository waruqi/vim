
function! s:Add_Mark_Menu(menu_clear)
    if has("gui_running")

		if (a:menu_clear)

			tmenu icon=MarkLocal.png ToolBar.MarkLocal  mark it
			amenu ToolBar.MarkLocal <Leader>mm

			tmenu icon=MarkGlobal.png ToolBar.MarkGlobal  mark it
			amenu ToolBar.MarkGlobal <Leader>mg

			tmenu icon=MarkClear.png ToolBar.MarkClear  mark clean
			amenu ToolBar.MarkClear <Leader>mh

		endif

	endif

endfunction


autocmd BufEnter * call s:Add_Mark_Menu(1)

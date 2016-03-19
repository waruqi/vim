
function! s:Add_Symbols_Menu(menu_clear)
    if has("gui_running")

		if (a:menu_clear)
			silent! unmenu &symbols
			silent! unmenu! &symbols

			" add menus
			amenu <silent> &symbols.make\ symbols :!cscope -bkq <CR>:cs add ./cscope.out<CR>:!ctags -L ./cscope.files --c-kinds=+p --c++-kinds=+p --fields=+iaS --extra=+q . <CR><CR>
			amenu <silent> &symbols.jump\ back <Esc><C-T><CR>
			amenu <silent> &symbols.Find\ functions\ calling\ this\ function :cs find c <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ functions\ called\ by\ this\ function :cs find d <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ this\ egrep\ pattern :cs find e <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ this\ file :cs find f <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ this\ definition :cs find g <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ files\ #including\ this\ file :cs find i <C-R>=expand("<cfile>") <CR><CR>
			amenu <silent> &symbols.Find\ this\ Symbol :cs find s <C-R>=expand("<cword>") <CR><CR>
			amenu <silent> &symbols.Find\ assignments\ to :cs find t <C-R>=expand("<cword>") <CR><CR>

			" add toolbar
			tmenu icon=MakeSymbols.png ToolBar.MakeSymbols  make symbols
			amenu ToolBar.MakeSymbols  :!cscope -bkq <CR>:cs add ./cscope.out<CR>:!ctags -L ./cscope.files --c-kinds=+p --c++-kinds=+p --fields=+iaS --extra=+q . <CR><CR>
		
			tmenu icon=Jumpback.png ToolBar.Jumpback  jump back 
			amenu ToolBar.Jumpback  <Esc><C-T><CR>

			tmenu icon=JumpDef.png ToolBar.JumpDef  jump to definition
			amenu ToolBar.JumpDef  :cs find g <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindReference.png ToolBar.FindReference  find reference
			amenu ToolBar.FindReference  :cs find s <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindCallor.png ToolBar.FindCallor  find functions calling this function
			amenu ToolBar.FindCallor  :cs find c <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindCalledor.png ToolBar.FindCalledor  find functions called by this function
			amenu ToolBar.FindCalledor  :cs find d <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindAssignments.png ToolBar.FindAssignments  find assignments
			amenu ToolBar.FindAssignments  :cs find t <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindFile.png ToolBar.FindFile  find file
			amenu ToolBar.FindFile  :cs find f <C-R>=expand("<cword>") <CR><CR>

			tmenu icon=FindIncludes.png ToolBar.FindIncludes  find includes
			amenu ToolBar.FindIncludes  :cs find i <C-R>=expand("<cfile>") <CR><CR>

		endif

	endif

endfunction


autocmd BufEnter * call s:Add_Symbols_Menu(1)

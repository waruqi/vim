" Vim color file
"  Maintainer: Tiza
" Last Change: 2002/10/30 Wed 00:12.
"     version: 1.7
" This color scheme uses a light background.

set background=dark
hi clear
if exists("syntax_on")
  syntax reset
endif

let g:colors_name = "ruki"

if (has("gui_running"))
hi Normal			gui=None		guifg=Black		guibg=#f5f5f5
hi PreProc			gui=None		guifg=Red		guibg=NONE
hi Keyword			gui=NONE		guifg=Blue		guibg=NONE
hi Type				gui=NONE		guifg=Blue		guibg=NONE
hi Comment			gui=italic		guifg=#008000	guibg=NONE
hi Constant			gui=NONE		guifg=#800080	guibg=NONE
hi String			gui=NONE		guifg=#FF00FF	guibg=NONE
hi Statement		gui=NONE		guifg=Blue		guibg=NONE
hi LineNr			gui=NONE		guifg=#808080	guibg=NONE
else
hi Cursor	        cterm=None      ctermfg=LightGray
hi Normal			cterm=None		ctermfg=White		ctermbg=NONE
hi PreProc			cterm=None		ctermfg=LightRed	ctermbg=NONE
hi Keyword			cterm=NONE		ctermfg=Lightblue	ctermbg=NONE
hi Type				cterm=NONE		ctermfg=LightBlue	ctermbg=NONE
hi Comment			cterm=NONE	    ctermfg=LightGreen	ctermbg=NONE
hi Constant			cterm=NONE		ctermfg=Brown		ctermbg=NONE
hi String			cterm=NONE		ctermfg=Magenta     ctermbg=NONE
hi Statement		cterm=NONE		ctermfg=LightRed	ctermbg=NONE
hi LineNr			cterm=NONE		ctermfg=LightGray	ctermbg=NONE

endif


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
hi PreProc			gui=None		guifg=Red		guibg=None
hi Keyword			gui=None		guifg=Blue		guibg=None
hi Type				gui=None		guifg=Blue		guibg=None
hi Comment			gui=Italic		guifg=#008000	guibg=None
hi Constant			gui=None		guifg=#800080	guibg=None
hi String			gui=None		guifg=#FF00FF	guibg=None
hi Statement		gui=None		guifg=Blue		guibg=None
hi LineNr			gui=None		guifg=#808080	guibg=None

else

hi Normal			cterm=None		ctermfg=White		ctermbg=None
hi PreProc			cterm=None		ctermfg=Red	        ctermbg=None
hi Keyword			cterm=None		ctermfg=LightBlue	ctermbg=None
hi Type				cterm=None		ctermfg=LightBlue	ctermbg=None
hi Comment			cterm=None	    ctermfg=LightGreen	ctermbg=None
hi Constant			cterm=None		ctermfg=Brown		ctermbg=None
hi String			cterm=None		ctermfg=Magenta     ctermbg=None
hi Statement		cterm=None		ctermfg=LightBlue	ctermbg=None
hi LineNr			cterm=None		ctermfg=LightGray	ctermbg=None
hi Title            cterm=None      ctermfg=Magenta     ctermbg=None
hi VertSplit	    cterm=Reverse
hi Visual	        cterm=reverse

endif


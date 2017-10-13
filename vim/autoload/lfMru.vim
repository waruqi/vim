" ============================================================================
" File:        lfMru.vim
" Description:
" Author:      Yggdroot <archofortune@gmail.com>
" Website:     https://github.com/Yggdroot
" Note:
" License:     Apache License, Version 2.0
" ============================================================================

if leaderf#versionCheck() == 0  " this check is necessary
    finish
endif

exec g:Lf_py "from leaderf.mru import *"

function! lfMru#record(name)
    if a:name == '' || !filereadable(a:name)
        return
    endif

    exec g:Lf_py 'mru.saveToCache(r"""'.a:name.'""")'
endfunction

function! lfMru#recordBuffer(bufNum)
    exec g:Lf_py 'mru.setBufferTimestamp('.a:bufNum.')'
endfunction

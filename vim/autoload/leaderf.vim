" ============================================================================
" File:        leaderf.vim
" Description:
" Author:      Yggdroot <archofortune@gmail.com>
" Website:     https://github.com/Yggdroot
" Note:
" License:     Apache License, Version 2.0
" ============================================================================

exec g:Lf_py "import vim, sys, os.path"
exec g:Lf_py "cwd = vim.eval('expand(\"<sfile>:p:h\")')"
exec g:Lf_py "sys.path.insert(0, os.path.join(cwd, 'leaderf', 'python'))"

function! leaderf#versionCheck()
    if g:Lf_PythonVersion == 2 && pyeval("sys.version_info < (2, 7)")
        echohl Error
        echo "Error: LeaderF requires python2.7+, your current version is " . pyeval("sys.version")
        echohl None
        return 0
    elseif g:Lf_PythonVersion == 3 && py3eval("sys.version_info < (3, 1)")
        echohl Error
        echo "Error: LeaderF requires python3.1+, your current version is " . pyeval("sys.version")
        echohl None
        return 0
    elseif g:Lf_PythonVersion != 2 && g:Lf_PythonVersion != 3
        echohl Error
        echo "Error: Invalid value of `g:Lf_PythonVersion`, value must be 2 or 3."
        echohl None
        return 0
    endif
    return 1
endfunction

function! leaderf#LfPy(cmd)
    exec g:Lf_py . a:cmd
endfunction

function! leaderf#removeCache(bufNum)
    if exists("g:Lf_bufTagExpl_loaded")
        call leaderf#BufTag#removeCache(a:bufNum)
    endif

    if exists("g:Lf_functionExpl_loaded")
        call leaderf#Function#removeCache(a:bufNum)
    endif
endfunction

function! leaderf#cleanup()
    if exists("g:Lf_fileExpl_loaded")
        call leaderf#File#cleanup()
    endif

    if exists("g:Lf_bufTagExpl_loaded")
        call leaderf#BufTag#cleanup()
    endif

    if exists("g:Lf_functionExpl_loaded")
        call leaderf#Function#cleanup()
    endif
endfunction

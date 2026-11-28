@echo off
rem HarmonicFitness on Windows, from PowerShell or cmd: runs ./harmonicfitness (a shell script) in Git Bash, so
rem `./harmonicfitness <command>` works the same in PowerShell as in Git Bash (PowerShell finds this .cmd for it;
rem in cmd, type `.\harmonicfitness <command>`). Git Bash comes with Git for Windows. HARMONICFITNESS_BASH names
rem another bash.exe. Never the bash on PATH: in PowerShell that is often WSL's, a different computer.
setlocal
set "HF_BASH="
if defined HARMONICFITNESS_BASH call :try "%HARMONICFITNESS_BASH%"
if not defined HF_BASH for /f "delims=" %%G in ('where git.exe 2^>nul') do if not defined HF_BASH call :fromgit "%%~dpG"
if not defined HF_BASH call :try "%ProgramW6432%\Git\bin\bash.exe"
if not defined HF_BASH call :try "%ProgramFiles%\Git\bin\bash.exe"
if not defined HF_BASH call :try "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
if not defined HF_BASH call :try "%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined HF_BASH (
  echo HarmonicFitness runs in Git Bash, which comes with Git for Windows, and it isn't on this computer. Install it from https://git-scm.com/download/win ^(the default options are fine^), open a new terminal, and run this again. 1>&2
  exit /b 1
)
rem Forward slashes: the script finds its own folder with dirname, which reads only those.
set "HF_SCRIPT=%~dp0harmonicfitness"
set "HF_SCRIPT=%HF_SCRIPT:\=/%"
"%HF_BASH%" "%HF_SCRIPT%" %*
exit /b %ERRORLEVEL%

:fromgit
rem git.exe lives in <Git>\cmd, <Git>\bin or <Git>\mingw64\bin; Git Bash in <Git>\bin.
call :try "%~1..\bin\bash.exe"
if not defined HF_BASH call :try "%~1..\..\bin\bash.exe"
exit /b 0

:try
if exist "%~f1" set "HF_BASH=%~f1"
exit /b 0

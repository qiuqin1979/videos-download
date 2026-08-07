' start.vbs - Silent launcher for Video Downloader (no CMD window)
Set WshShell = CreateObject("WScript.Shell")
Dim scriptDir
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\") - 1)
WshShell.Run "cmd /c """ & scriptDir & "\start.bat"""", 0, False
Set WshShell = Nothing

' ============================================================
'  Crea un acceso directo en el Escritorio para abrir la app
'  con un solo doble clic.
'  Uso: doble clic en este archivo UNA SOLA VEZ.
' ============================================================
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

carpetaApp = fso.GetParentFolderName(WScript.ScriptFullName)
escritorio = WshShell.SpecialFolders("Desktop")

Set atajo = WshShell.CreateShortcut(escritorio & "\Control Avicola.lnk")
atajo.TargetPath = carpetaApp & "\iniciar_app.bat"
atajo.WorkingDirectory = carpetaApp
atajo.WindowStyle = 1
atajo.IconLocation = "%SystemRoot%\System32\shell32.dll, 43"
atajo.Description = "Abrir Sistema de Control Avicola"
atajo.Save

MsgBox "Listo. Se creo el acceso directo 'Control Avicola' en tu Escritorio." & vbCrLf & _
       "Desde ahora solo necesitas hacer doble clic ahi para abrir la app.", 64, "Acceso directo creado"

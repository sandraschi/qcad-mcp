; Fleet Tauri: kill UI + backend before install/uninstall (backend locks resources/*.exe).
!macro KillFleetSidecars
  DetailPrint "Stopping fleet processes..."
  ExecWait 'taskkill /F /IM qcad-mcp-backend.exe /T' $0
  ExecWait 'taskkill /F /IM qcad-mcp-native.exe /T' $0
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::KillProcessCurrentUser "qcad-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcessCurrentUser "qcad-mcp-native.exe"
    Pop $0
  !else
    nsis_tauri_utils::KillProcess "qcad-mcp-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcess "qcad-mcp-native.exe"
    Pop $0
  !endif
  Sleep 2000
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro KillFleetSidecars
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro KillFleetSidecars
!macroend

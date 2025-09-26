 
## windows

Add-MpPreference -ExclusionPath "d:\workshop\vmm\uploads\"



python -m uvicorn main:app --host 0.0.0.0 --port 8000


powershell -Command "Start-Process -FilePath \"C:\Program Files\Windows Defender\MpCmdRun.exe\" -ArgumentList \"-Restore\", \"-ListAll\" -Wait -NoNewWindow -PassThru"
The following items are quarantined:

ThreatName = TrojanDropper:Win32/Conficker.gen!A
      file:C:\Users\vboxuser\Desktop\C9E0917FE3231A652C014AD76B55B26A.exe quarantined at ?9/?26/?2025 3:23:34 AM (UTC)
      file:C:\Users\vboxuser\AppData\Local\Temp\VirtualBox Dropped Files\2025-09-26T04_23_45.612552500Z\C9E0917FE3231A652C014AD76B55B26A.exe quarantined at ?9/?26/?2025 4:24:00 AM (UTC)
      file:C:\Users\vboxuser\Desktop\C9E0917FE3231A652C014AD76B55B26A.exe quarantined at ?9/?26/?2025 4:24:00 AM (UTC)

Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  SI ProcessName
-------  ------    -----      -----     ------     --  -- -----------
     25       3      428       1196       0.02   4996   1 MpCmdRun



"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" guestcontrol win10-64-defender --username vboxuser --password 123456 run --exe cmd.exe -- /c powershell -Command "& 'C:\Program Files\Windows Defender\MpCmdRun.exe' -Restore -ListAll" 





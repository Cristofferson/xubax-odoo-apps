; Instalador del agente Analitix para Windows.
;
; Lo que este instalador tiene que resolver, y por qué está resuelto así:
;
;   · El agente tiene que arrancar solo al encender la tienda, sin que nadie
;     inicie sesión. Se registra como TAREA PROGRAMADA que corre como SYSTEM al
;     arranque, y no como servicio de Windows: un servicio de verdad exige que
;     el ejecutable hable el protocolo de control de servicios, y un binario de
;     PyInstaller que no lo hace es un servicio que Windows mata a los treinta
;     segundos por "no responder". La tarea programada es nativa, reinicia sola
;     si el proceso muere y no necesita binarios de terceros.
;
;   · La configuración lleva la llave del equipo, así que NO va en Archivos de
;     Programa: va en ProgramData, que es donde Windows espera datos que la
;     aplicación escribe, y el instalador no la sobrescribe si ya existe —
;     reinstalar no puede borrarle la llave a una tienda que ya está midiendo.

#define AppName        "Analitix Agent"
#define AppPublisher   "XUBAX"
#define AppURL         "https://www.xubax.com/analitix"
#define AppExe         "analitix-agent.exe"
#ifndef AppVersion
  #define AppVersion   "1.0.0"
#endif

[Setup]
AppId={{B4E1B0B6-9C1E-4F0B-9E3D-A5A2D1C8F001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\Analitix
DefaultGroupName=Analitix
DisableProgramGroupPage=yes
OutputBaseFilename=AnalitixAgentSetup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
; El motor de visión no cabe en 32 bits ni tiene por qué: cualquier mini PC de
; los últimos diez años es x64.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\..\LICENSE

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\analitix-agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; La configuración de ejemplo se copia SOLO si no hay ya una: reinstalar no
; puede borrarle la llave a una tienda en marcha.
Source: "..\config.example.yaml"; DestDir: "{commonappdata}\Analitix"; \
    DestName: "agent.yaml"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\Analitix"
Name: "{commonappdata}\Analitix\state"
Name: "{commonappdata}\Analitix\logs"

[Icons]
Name: "{group}\Editar la configuración"; Filename: "notepad.exe"; \
    Parameters: """{commonappdata}\Analitix\agent.yaml"""
Name: "{group}\Ver el registro"; Filename: "notepad.exe"; \
    Parameters: """{commonappdata}\Analitix\logs\agent.log"""
Name: "{group}\Probar en esta ventana"; Filename: "{app}\{#AppExe}"; \
    Parameters: "--verbose"; WorkingDir: "{app}"

[Run]
; Al arranque de la máquina y como SYSTEM, para que la tienda no dependa de que
; alguien inicie sesión. /RL HIGHEST porque abrir un dispositivo de video pide
; privilegios en algunas capturadoras.
Filename: "{sys}\schtasks.exe"; \
    Parameters: "/Create /F /TN ""Analitix Agent"" /RU SYSTEM /RL HIGHEST /SC ONSTART /TR ""\""{app}\{#AppExe}\"""""; \
    Flags: runhidden; StatusMsg: "Registrando el arranque automático..."
; Y arrancarlo ya, para que el técnico vea el equipo en línea sin reiniciar.
Filename: "{sys}\schtasks.exe"; Parameters: "/Run /TN ""Analitix Agent"""; \
    Flags: runhidden; StatusMsg: "Arrancando el agente..."
Filename: "notepad.exe"; Parameters: """{commonappdata}\Analitix\agent.yaml"""; \
    Description: "Abrir la configuración para pegar la URL y la llave"; \
    Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""Analitix Agent"""; \
    Flags: runhidden; RunOnceId: "StopTask"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""Analitix Agent"""; \
    Flags: runhidden; RunOnceId: "DelTask"

[UninstallDelete]
; El estado sí se va; la configuración NO — si alguien desinstala para
; reinstalar una versión nueva, borrarle la llave le cuesta una visita a la
; tienda.
Type: filesandordirs; Name: "{commonappdata}\Analitix\state"
Type: filesandordirs; Name: "{commonappdata}\Analitix\logs"

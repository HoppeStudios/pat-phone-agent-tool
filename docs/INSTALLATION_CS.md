# Instalace a požadavky

Tato verze používá Codex přihlášený přes existující účet ChatGPT. Claude Code není potřeba. Pro češtinu používá místní rozpoznávání Parakeet TDT v3 a hlas Piper Jiří.

Pro experimentální připojení Androidu přes síť použijte [návod Android SIP / Tailscale](ANDROID_SIP.md). Následující požadavky se týkají původní varianty přes Bluetooth.

## Co je potřeba pro Bluetooth

Počítač musí mít Windows 11 a procesor Intel nebo AMD x64. Telefon může být Android nebo iPhone. Potřebuje funkční SIM, možnost odchozích hovorů a Bluetooth spojení s počítačem.

Windows musí mít zapnutý Režim pro vývojáře. Jde o nastavení celého počítače, které umožňuje registraci vývojových aplikací. Jeho zapnutí vyžaduje výslovný souhlas a oprávnění správce. Pro aktuálního uživatele musí být také zapnuté nastavení Povolit tomuto počítači přístup k mobilním zařízením.

Pro zvuk je potřeba VB CABLE a vhodný druhý virtuální reproduktor. Lze použít existující Steam Streaming Speakers nebo virtuální reproduktor Voicemeeteru. Zařízení nesmí být ve Windows skrytá nebo zakázaná. Výchozí reproduktor a mikrofon mají dál zůstat na běžné náhlavní soupravě.

Na Androidu povolte u spárovaného počítače telefonní hovory. Při párování otevřete nastavení Bluetooth telefonu a porovnejte kód na obou zařízeních. Kód musí potvrdit člověk. U telefonu se dvěma SIM vyberte správnou SIM pro odchozí hovory přímo v telefonu.

## Instalace

```powershell
git clone --branch android-sip-tailscale --single-branch https://github.com/HoppeStudios/pat-phone-agent-tool.git
cd pat-phone-agent-tool
powershell -File .\setup-codex.ps1
powershell -File .\scripts\Install-PhoneHelper.ps1 -EnableDeveloperMode -EnableMobileAccess
```

Použijte Python 3.12 a běžné okno PowerShellu pod vlastním účtem. Případnou výzvu Windows pro správce potvrzuje uživatel. Instalační skript ji nepotvrzuje za něj a neprovádí nucený restart.

Spusťte `.venv\Scripts\pythonw.exe .\note.py`, vyplňte jméno, oblast a časové pásmo, přečtěte podmínky a přijměte je pouze tehdy, pokud souhlasíte. Potom nastavte telefon. Pro české hovory použijte jazyk `cs`. Neznámí volající mohou zůstat v režimu Ask.

## Wi-Fi a Tailscale

Nový experimentální adaptér používá Voice SIP Agent 0.4.2, Shizuku 13.6.0, Tailscale na obou zařízeních a Asterisk 22.12.0 ve WSL. USB slouží k úvodní instalaci a spuštění Shizuku; zvuk má potom procházet sítí. Tento režim nepotřebuje Windows Bluetooth helper, Režim pro vývojáře ani virtuální zvuková zařízení.

Uživatel musí potvrdit instalaci APK, autorizaci USB a oprávnění Shizuku. Hlavní bránu zapněte jen s jeho souhlasem. Příchozí hovory pro oba sloty zůstávají vypnuté, výchozí SIM má hodnotu Refuse a konkrétní slot se předává v každém požadovaném hovoru. Odchozí volání je v klientovi zpočátku vypnuté.

Na Androidu 13 je ověřené oprávnění, registrace SIP přes Tailscale a místní zvuková smyčka. Skutečný zvuk přes SIM v obou směrech a zobrazené číslo zatím vyžadují první hovor na vlastní druhý telefon nebo souhlasícího příjemce. Síťový adaptér nepodporuje příchozí hovory ani převzetí hovoru uživatelem. Po restartu telefonu může být nutné Shizuku znovu spustit.

Podrobný postup, přesné hashe a omezení jsou v [Android SIP návodu](ANDROID_SIP.md).

## Cena a ověření

Samotný fork je bez poplatku za software a nepotřebuje placené telefonní API. Používá existující přístup ke Codexu a mobilní tarif. Jejich limity a případné poplatky stále platí. Základní potřebné funkce Voicemeeteru jsou dostupné jako donationware. Není potřeba kupovat volitelné funkce.

Příkaz `iphonecall self-test` ověřuje pouze umělé příklady výběru telefonu. `iphonecall phones` a `iphonecall status` kontrolují telefon bez vytáčení. První skutečný test proveďte s vlastním druhým telefonem nebo člověkem, který s testem souhlasí. Ověřte zvuk v obou směrech a zobrazené číslo volajícího. Rozpoznávání může zaměnit názvy výrobků nebo jména, proto je během hovoru potvrzujte.

Podrobné kroky, aktualizace a řešení problémů jsou v [anglickém návodu](INSTALLATION.md).

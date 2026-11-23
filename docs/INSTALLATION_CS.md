# Instalace a požadavky

Tato verze používá Codex přihlášený přes existující účet ChatGPT. Claude Code není potřeba. Pro češtinu používá místní rozpoznávání Parakeet TDT v3 a hlas Piper Jiří.

## Co je potřeba

Počítač musí mít Windows 11 a procesor Intel nebo AMD x64. Telefon může být Android nebo iPhone. Potřebuje funkční SIM, možnost odchozích hovorů a Bluetooth spojení s počítačem.

Windows musí mít zapnutý Režim pro vývojáře. Jde o nastavení celého počítače, které umožňuje registraci vývojových aplikací. Jeho zapnutí vyžaduje výslovný souhlas a oprávnění správce. Pro aktuálního uživatele musí být také zapnuté nastavení Povolit tomuto počítači přístup k mobilním zařízením.

Pro zvuk je potřeba VB CABLE a vhodný druhý virtuální reproduktor. Lze použít existující Steam Streaming Speakers nebo virtuální reproduktor Voicemeeteru. Zařízení nesmí být ve Windows skrytá nebo zakázaná. Výchozí reproduktor a mikrofon mají dál zůstat na běžné náhlavní soupravě.

Na Androidu povolte u spárovaného počítače telefonní hovory. Při párování otevřete nastavení Bluetooth telefonu a porovnejte kód na obou zařízeních. Kód musí potvrdit člověk. U telefonu se dvěma SIM vyberte správnou SIM pro odchozí hovory přímo v telefonu.

## Instalace

```powershell
git clone --branch codex-czech-setup --single-branch https://github.com/HoppeStudios/pat-phone-agent-tool.git
cd pat-phone-agent-tool
powershell -File .\setup-codex.ps1
powershell -File .\scripts\Install-PhoneHelper.ps1 -EnableDeveloperMode -EnableMobileAccess
```

Použijte Python 3.12 a běžné okno PowerShellu pod vlastním účtem. Případnou výzvu Windows pro správce potvrzuje uživatel. Instalační skript ji nepotvrzuje za něj a neprovádí nucený restart.

Spusťte `.venv\Scripts\pythonw.exe .\note.py`, vyplňte jméno, oblast a časové pásmo, přečtěte podmínky a přijměte je pouze tehdy, pokud souhlasíte. Potom nastavte telefon. Pro české hovory použijte jazyk `cs`. Neznámí volající mohou zůstat v režimu Ask.

## Wi-Fi a Tailscale

Tato verze potřebuje Bluetooth pro zvuk skutečného hovoru přes SIM. Wi-Fi ani Tailscale samy nezpřístupní zvuk telefonního hovoru běžné aplikaci na Androidu. Síťové ovládání telefonu a přenos zvuku oběma směry jsou různé věci. Připojení přes ADB není důkaz funkční hlasové brány.

Existuje [experimentální úprava scrcpy](https://github.com/Genymobile/scrcpy/pull/7004) pro přenos mikrofonu z počítače do Androidu. Vyžaduje Android 13 nebo novější a zvláštní sestavení klienta. Cílí na VoIP a její funkce závisí na konkrétním telefonu. Není součástí tohoto forku. Podpora skutečného hovoru přes SIM se musí ověřit na daném zařízení v obou směrech.

## Cena a ověření

Samotný fork je bez poplatku za software a nepotřebuje placené telefonní API. Používá existující přístup ke Codexu a mobilní tarif. Jejich limity a případné poplatky stále platí. Základní potřebné funkce Voicemeeteru jsou dostupné jako donationware. Není potřeba kupovat volitelné funkce.

Příkaz `iphonecall self-test` ověřuje pouze umělé příklady výběru telefonu. `iphonecall phones` a `iphonecall status` kontrolují telefon bez vytáčení. První skutečný test proveďte s vlastním druhým telefonem nebo člověkem, který s testem souhlasí. Ověřte zvuk v obou směrech a zobrazené číslo volajícího. Rozpoznávání může zaměnit názvy výrobků nebo jména, proto je během hovoru potvrzujte.

Podrobné kroky, aktualizace a řešení problémů jsou v [anglickém návodu](INSTALLATION.md).

"""Generate this installation's secrets without placing them in source or tool output."""
import json
from pathlib import Path
import secrets
import subprocess
import os

import argparse
import ipaddress

parser = argparse.ArgumentParser(description="Create private Android SIP configuration, without starting calls or changing phone permissions.")
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--adb', required=True, type=Path)
parser.add_argument('--serial', required=True)
parser.add_argument('--pc', required=True)
parser.add_argument('--phone', required=True)
parser.add_argument('--linux', required=True)
parser.add_argument('--distro', default='Debian')
options = parser.parse_args()
source = Path(__file__).resolve().parents[1]
runtime = options.runtime.resolve()
if (runtime / 'host.pid').exists():
    raise SystemExit('Stop and verify the owned, idle SIP processes before reconfiguring; inspect stale PID files manually.')
if not options.adb.is_absolute() or not options.adb.is_file():
    raise SystemExit('Provide the existing absolute ADB executable path.')
network = dict(pc=options.pc, phone=options.phone, linux=options.linux)
for name in ('pc', 'phone'):
    if ipaddress.ip_address(network[name]) not in ipaddress.ip_network('100.64.0.0/10'):
        raise SystemExit('Select verified Tailscale IPv4 peers.')
linux = ipaddress.ip_address(network['linux'])
if linux.version != 4 or not linux.is_private or linux.is_loopback:
    raise SystemExit('Select the current private WSL IPv4 address.')
import re
if not re.fullmatch(r'[A-Za-z0-9._:-]+', options.serial):
    raise SystemExit('Invalid Android serial.')
check = subprocess.run(['wsl.exe','-d',options.distro,'--exec','python3','-c',
    "from pathlib import Path; import os; p=Path('/var/lib/pat-codex-sip/runtime.pid'); alive=p.exists() and Path('/proc/'+p.read_text().strip()).exists(); raise SystemExit(1 if alive else 0)"], check=False)
if check.returncode:
    raise SystemExit('Stop the owned, idle Linux SIP supervisor before configuring.')
runtime.mkdir(parents=True, exist_ok=True)
config_path = runtime / 'runtime-private.json'
if config_path.exists():
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
else:
    config = dict(ami_user='pat_codex', ami_secret=secrets.token_hex(32), relay_token=secrets.token_hex(32),
                  sip_user='pat-android', sip_secret=secrets.token_hex(32))
config.update(ami_port=15038, relay_port=18002, adb=str(options.adb),
              phone_serial=options.serial, phone_slot=0, pc_tailscale_address=network['pc'],
              phone_tailscale_address=network['phone'], linux_address=network['linux'],
              windows_pid_file=str(runtime / 'host.pid'), outbound_enabled=False, wsl_distro=options.distro)
config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
root = '/var/lib/pat-codex-sip'
prefix = '/opt/pat-codex-sip/asterisk-22.12.0'
linux_config = dict(relay_token=config['relay_token'], relay_port=config['relay_port'],
                    asterisk_prefix=prefix, asterisk_config=root+'/etc/asterisk.conf',
                    asterisk_log=root+'/state/asterisk.stdout.log', runtime_pid_file=root+'/runtime.pid')
modules = ['pbx_config', 'app_audiosocket', 'res_audiosocket', 'app_echo', 'func_timeout',
           'res_sorcery_config', 'res_sorcery_memory', 'res_sorcery_astdb', 'res_pjproject',
           'res_pjsip', 'res_pjsip_pubsub', 'res_pjsip_header_funcs', 'res_pjsip_authenticator_digest', 'res_pjsip_outbound_authenticator_digest',
           'res_pjsip_endpoint_identifier_user', 'res_pjsip_registrar', 'res_pjsip_session',
           'res_pjsip_sdp_rtp', 'res_pjsip_nat', 'res_rtp_asterisk', 'chan_pjsip',
           'codec_ulaw', 'codec_alaw', 'codec_resample', 'bridge_simple', 'bridge_native_rtp']
files = {
    'runtime-private.json': json.dumps(linux_config),
    'etc/asterisk.conf': f'''[directories]
astetcdir => {root}/etc
astmoddir => {prefix}/lib/asterisk/modules
astvarlibdir => {root}/state/lib/asterisk
astdbdir => {root}/state/db
astkeydir => {root}/state/keys
astdatadir => {root}/state/lib/asterisk
astagidir => {root}/state/agi-bin
astspooldir => {root}/state/spool
astrundir => {root}/state/run
astlogdir => {root}/state/log
astsbindir => {prefix}/sbin
[options]
verbose = 0
debug = 0
live_dangerously = no
''',
    'etc/modules.conf': '[modules]\nautoload=no\n'+''.join('load='+name+'.so\n' for name in modules),
    'etc/logger.conf': '[logfiles]\nconsole=warning,error,notice\nmessages=warning,error,notice\n',
    'etc/acl.conf': '; No named network ACLs. SIP uses per-endpoint authentication.\n',
    'etc/cdr.conf': '[general]\nenable=no\n',
    'etc/cel.conf': '[general]\nenable=no\n',
    'etc/features.conf': '[general]\n',
    'etc/indications.conf': '[general]\ncountry=us\n',
    'etc/udptl.conf': '[general]\n',
    'etc/pjproject.conf': '[startup]\ntype=startup\nlog_level=2\n',
    'etc/manager.conf': f'''[general]
enabled=yes
port=15038
bindaddr=127.0.0.1
displayconnects=no
[{config['ami_user']}]
secret={config['ami_secret']}
deny=0.0.0.0/0.0.0.0
permit=127.0.0.1/255.255.255.255
read=call,system,originate
write=call,originate
''',
    'etc/pjsip.conf': f'''[transport-tailscale]
type=transport
protocol=tcp
bind=0.0.0.0:15060
local_net=127.0.0.0/8
external_media_address={network['pc']}
[pat-android]
type=endpoint
transport=transport-tailscale
context=pat-reject
disallow=all
allow=ulaw,alaw
auth=pat-android-auth
outbound_auth=pat-android-auth
aors=pat-android
direct_media=no
force_rport=yes
rtp_symmetric=yes
rewrite_contact=yes
timers=no
[pat-android-auth]
type=auth
auth_type=userpass
username={config['sip_user']}
password={config['sip_secret']}
[pat-android]
type=aor
max_contacts=1
remove_existing=yes
qualify_frequency=30
''',
    'etc/extensions.conf': '''[pat-reject]
; No incoming dialplan applications are available.
[pat-local-test]
exten => echo,1,Answer()
same => n,Echo()
same => n,Hangup()
[pat-status]
exten => android,hint,PJSIP/pat-android
''',
    'etc/rtp.conf': '[general]\nrtpstart=19000\nrtpend=19020\nstrictrtp=yes\nicesupport=no\n',
    'sip_runtime.py': (source / 'scripts/sip_runtime.py').read_text(encoding='utf-8'),
    'sip_relay.py': (source / 'scripts/sip_relay.py').read_text(encoding='utf-8'),
}
writer = '''import json,os,sys,pathlib
root=pathlib.Path('/var/lib/pat-codex-sip')
root.chmod(0o700)
for name,data in json.load(sys.stdin).items():
 p=root/name
 p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 p.write_text(data,encoding='utf-8')
 p.chmod(0o600)
for name in ('lib','db','keys','data','agi-bin','spool','run','log'):
 (root/'state'/name).mkdir(parents=True,exist_ok=True,mode=0o700)
'''
subprocess.run(['wsl.exe','-d',options.distro,'--exec','python3','-c',writer],
               input=json.dumps(files),text=True,check=True)
(runtime / 'android_sip_host.py').write_text((source / 'scripts/android_sip_host.py').read_text(encoding='utf-8'), encoding='utf-8')
print('Private local SIP configuration generated. No phone calls or Startup entries changed.')

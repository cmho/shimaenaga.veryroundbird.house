## PDS Modifications for https://altq.net

Goals:
- allow serving a custom web page on the PDS root
- generate a status page for the PDS including account usage

See https://altq.net/status.html how it looks (hopefully boring enough)

Detailed explanations: TBD

For now:
- my PDS runs on Ubuntu 24.04
- read and modify the files appropriately
- put them in their respective directories
- restart PDS via systemctl

Note: The `generate-status.py` script needs the Python `psutil` library. Install it with e.g. 
```shell
apt install python3-psutil
```

License: MIT
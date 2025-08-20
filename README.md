# XDAQ/ThorVision Examples

## Install 
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

## Run the example script

```bash
python3 xdaq_thorvision.py
```

### What the script does:
- **XDAQ acquisition**: Starts continuous data acquisition for `10` seconds from all XDAQ data streams
- **Camera recording**: Immediately begins recording from all connected Thor Vision cameras for `10` seconds and saves files to the `recordings/` directory

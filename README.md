# XDAQ Examples

## Setup virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./pyxdaq/ 
pip install -e ./PyThorVision/
```

## Run XDAQ acquisition with Thor Vision cameras
This example demonstrates running 30 seconds of XDAQ data acquisition across all data streams.
When the XDAQ acquisition reaches a timestep of 100,000, camera recording will automatically start and continue for 10 seconds.

```bash
python3 xdaq_thorvision.py
```

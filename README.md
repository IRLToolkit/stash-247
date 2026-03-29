# stash-247

### A Python script which makes use of the Stash API to play back VODs.

## Getting Started (Linux/WSL)

- You must have at least Python 3.9 installed.
- `git clone https://github.com/IRLToolkit/stash-247.git` - Download the repo
- `cd stash-247` - Change directories to the repository
- Write a file called `.env` to the directory with the following env values (see [`.env.example`](.env.example)):
  - `STASH_API_TOKEN` - API token created within the stash interface
  - `STASH_247_DATASTORE_ID` - ID of the datastore to fetch VODs from. Available after the `/dashboard/datastore/` part of the URL when viewing a datastore
  - `STASH_247_DATASTORE_TAG` - A tag applied to objects in the datastore, which will be used to select media to add to the playlist
  - `STASH_247_OBS_WEBSOCKET_URL` - obs-websocket WS URL for the OBS instance that will have the video player
  - `STASH_247_OBS_WEBSOCKET_PASSWORD` - obs-websocket authentication password
  - `STASH_247_OBS_INPUT_UUID` - Input ("source" as the UI tends to call it) UUID of a media source that this script will control
- `./run.sh` - Execute run.sh, which will create a new venv for you, install the dependencies, and then run the main.py script

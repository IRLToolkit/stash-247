import logging
import os
import sys
import typing
import random
import signal
import queue
import asyncio
import aiohttp
import simpleobsws
import dotenv

dotenv.load_dotenv()

SHUFFLE = True

API_TOKEN = os.getenv('STASH_API_TOKEN')
DATASTORE_ID = os.getenv('STASH_247_DATASTORE_ID')
TAG = os.getenv('STASH_247_DATASTORE_TAG')

OBS_WEBSOCKET_URL = os.getenv('STASH_247_OBS_WEBSOCKET_URL')
OBS_WEBSOCKET_PASSWORD = os.getenv('STASH_247_OBS_WEBSOCKET_PASSWORD')
OBS_INPUT_UUID = os.getenv('STASH_247_OBS_INPUT_UUID', '')

logging.basicConfig(level = logging.DEBUG)
logging.getLogger('simpleobsws').setLevel(logging.INFO)

mediaEndedEvent = None

class BadEnqueueException(Exception):
	pass

class ExitingException(Exception):
	pass

def log_input_uuids(data):
	logging.info('Available OBS inputs:')
	for input in data:
		logging.info(' - UUID: {} | Name: {}'.format(input['inputUuid'], input['inputName']))

async def fetch_playlist_objects() -> list[typing.Any]:
	headers = {
		'Authorization': 'Bearer {}'.format(API_TOKEN)
	}
	async with aiohttp.ClientSession() as session: # TODO: Iterate response
		async with session.get('https://stash.irltoolkit.com/api/v1/datastore/object/list?datastoreId={}&tags={}&limit=100'.format(DATASTORE_ID, TAG), headers = headers) as resp:
			if not resp.ok:
				logging.error('Failed to fetch objects for datastore {}. Got status {} and text: {}'.format(DATASTORE_ID, resp.status, await resp.text()))
				return []
			responseData = await resp.json()
			return responseData['objects']

async def fetch_media_part_url(mediaPartId) -> str | None:
	headers = {
		'Authorization': 'Bearer {}'.format(API_TOKEN)
	}
	async with aiohttp.ClientSession() as session:
		async with session.get('https://stash.irltoolkit.com/api/v1/datastore/mediaPart/download?mediaPartId={}'.format(mediaPartId), headers = headers) as resp:
			if not resp.ok:
				logging.error('Failed to fetch download URL for media part {}. Got status {} and text: {}'.format(mediaPartId, resp.status, await resp.text()))
				return None
			responseData = await resp.json()
			return responseData['downloadUrl']

async def enqueue_file_url(ws, url) -> bool:
	req = simpleobsws.Request(
		'SetInputSettings',
		{
			'inputUuid': OBS_INPUT_UUID,
			'inputSettings': {
				'is_local_file': True,
#				'input': url,
#				'seekable': True,
#				'reconnect_delay_sec': 60,
				'local_file': url,
				'looping': False,
				'restart_on_activate': False,
				'clear_on_media_end': True
			}
		}
	)
	resp = await ws.call(req)
	if not resp.ok():
		logging.warning('Failed to apply new media URL to replay source. Got obs-websocket status {} and comment: {}'.format(resp.requestStatus.code, resp.requestStatus.comment))
	return resp.ok()

async def on_media_started(eventData):
	if eventData['inputUuid'] != OBS_INPUT_UUID:
		return
	logging.debug('Received media started event from replay input')

async def on_media_ended(eventData):
	if eventData['inputUuid'] != OBS_INPUT_UUID:
		return
	if mediaEndedEvent:
		mediaEndedEvent.set()
	logging.debug('Received media ended event from replay input')

async def main():
	quitEvent = asyncio.Event()
	loop = asyncio.get_running_loop()
	loop.add_signal_handler(signal.SIGINT, lambda: quitEvent.set())

	global mediaEndedEvent
	mediaEndedEvent = asyncio.Event()

	ws = simpleobsws.WebSocketClient(url = OBS_WEBSOCKET_URL, password = OBS_WEBSOCKET_PASSWORD)
	ws.register_event_callback(on_media_started, 'MediaInputPlaybackStarted')
	ws.register_event_callback(on_media_ended, 'MediaInputPlaybackEnded')

	try:
		if not await ws.connect() or not await ws.wait_until_identified():
			logging.error('Failed to connect or identify with obs-websocket server.')
			return 1
	except:
		logging.exception('Exception while connecting to obs-websocket server:\n')
		return 1

	logging.info('Connected and identified to obs-websocket server')

	req = simpleobsws.Request('GetInputList', {'inputKind': 'ffmpeg_source'})
	resp = await ws.call(req)
	if not resp.ok():
		logging.error('Failed to call GetInputList: {}'.format(resp.requestStatus.comment))
		await ws.disconnect()
		return 0

	if not OBS_INPUT_UUID:
		log_input_uuids(resp.responseData['inputs'])
		logging.error('STASH_247_OBS_INPUT_UUID variable is empty or undefined. Please populate it.')
		await ws.disconnect()
		return 0

	found = False
	for input in resp.responseData['inputs']:
		if input['inputUuid'] == OBS_INPUT_UUID:
			logging.info('Using {} input {} for reruns'.format(input['inputKind'], input['inputName']))
			found = True
	if not found:
		log_input_uuids(resp.responseData['inputs'])
		logging.error('Failed to find an OBS input with UUID: {}'.format(OBS_INPUT_UUID))
		await ws.disconnect()
		return 0

	while True:
		objectList = await fetch_playlist_objects()
		if not objectList:
			logging.error('No objects returned by fetch_playlist_objects(). Cannot play')
			break
		logging.info('Stash API returned {} datastore objects to play'.format(len(objectList)))

		if SHUFFLE:
			random.shuffle(objectList)

		try:
			for object in objectList:
				for mediaPart in object['mediaParts']:
					playbackUrl = await fetch_media_part_url(mediaPart['id'])
					if not playbackUrl:
						continue
					logging.info('Now playing part {} of object created at {}: {}'.format(mediaPart['partNumber'], object['createdAt'], object['contentTitle']))
					mediaEndedEvent.clear()
					if not await enqueue_file_url(ws, playbackUrl):
						raise BadEnqueueException()
					await asyncio.wait(
						[
							asyncio.create_task(quitEvent.wait()),
							asyncio.create_task(mediaEndedEvent.wait())
						],
						return_when = asyncio.FIRST_COMPLETED
					)
					if quitEvent.is_set():
						raise ExitingException()
		except (BadEnqueueException, ExitingException):
			break

	logging.info('Shutting down...')
	await enqueue_file_url(ws, '') # Clear media source file
	await ws.disconnect()
	return 0

if __name__ == "__main__":
	sys.exit(asyncio.run(main()))

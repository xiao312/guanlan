"""Compile verified ParaView images, without replotting or temporal interpolation."""
from pathlib import Path
import shutil
import subprocess
from guanlan.media.package import verified_frames
from guanlan.media.contract import digest
from guanlan.media.remote import write_json


def video(state, output, ffmpeg='ffmpeg', fps=4):
    if type(fps) is not int or not 1 <= fps <= 30: raise ValueError('fps must be 1-30')
    executable = shutil.which(ffmpeg)
    if not executable: raise ValueError('ffmpeg is not installed; pass --ffmpeg with an approved executable')
    output = Path(output)
    if output.exists(): raise ValueError('video output exists; choose a new directory')
    manifest, payloads = verified_frames(state)
    if len(manifest['preset']['times']) < 2: raise ValueError('video requires at least two prepared times')
    output.mkdir(parents=True)
    videos = []
    for block in manifest['preset']['blocks']:
        for field in block.get('fields', ['']):
            frames = [f for f in manifest['frames'] if f['block'] == block['id'] and f['field'] == field]
            frames.sort(key=lambda f: manifest['preset']['times'].index(f['time']))
            destination = output / (block['id'] + ('-'+field if field else '') + '.mp4')
            command = [executable, '-hide_banner', '-loglevel', 'error', '-n', '-f', 'image2pipe', '-framerate', str(fps),
                       '-vcodec', 'png', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                       '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-movflags', '+faststart', str(destination)]
            subprocess.run(command, input=b''.join(payloads[f['file']] for f in frames), check=True, timeout=180,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            videos.append({'path': str(destination), 'file': destination.name, 'block': block['id'], 'field': field,
                           'bytes': destination.stat().st_size, 'sha256': digest(destination.read_bytes()), 'frames': len(frames), 'fps': fps})
    write_json(output/'videos.json', {'preset': manifest['preset'], 'videos': videos})
    return {'videos': videos, 'time_policy': 'uniform playback cadence; actual simulation time burned into each image'}

from __future__ import annotations

import atexit
import re
import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union
from gradio import strings
import os

from modules.shared import cmd_opts

from discord_webhook import send_to_discord

LOCALHOST_RUN = "localhost.run"
REMOTE_MOE = "remote.moe"
localhostrun_pattern = re.compile(r"(?P<url>https?://\S+\.lhr\.life)")
remotemoe_pattern = re.compile(r"(?P<url>https?://\S+\.remote\.moe)")


def gen_key(path: Union[str, Path]) -> None:
    path = Path(path)
    arg_string = f'ssh-keygen -t rsa -b 4096 -N "" -q -f {path.as_posix()}'
    args = shlex.split(arg_string)
    subprocess.run(args, check=True)
    path.chmod(0o600)


def ssh_tunnel(host: str = LOCALHOST_RUN) -> None:
    ssh_name = "id_rsa"
    ssh_path = Path(__file__).parent.parent / ssh_name

    tmp = None
    if not ssh_path.exists():
        try:
            gen_key(ssh_path)
        # write permission error or etc
        except subprocess.CalledProcessError:
            tmp = TemporaryDirectory()
            ssh_path = Path(tmp.name) / ssh_name
            gen_key(ssh_path)

    port = cmd_opts.port if cmd_opts.port else 7860

    arg_string = f"ssh -R 80:127.0.0.1:{port} -o StrictHostKeyChecking=no -i {ssh_path.as_posix()} {host}"
    args = shlex.split(arg_string)

    tunnel = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8"
    )

    atexit.register(tunnel.terminate)
    if tmp is not None:
        atexit.register(tmp.cleanup)

    tunnel_url = ""
    lines = 27 if host == LOCALHOST_RUN else 5
    pattern = localhostrun_pattern if host == LOCALHOST_RUN else remotemoe_pattern

    for _ in range(lines):
        line = tunnel.stdout.readline()
        if line.startswith("Warning"):
            print(line, end="")

        url_match = pattern.search(line)
        if url_match:
            tunnel_url = url_match.group("url")
            break
    else:
        raise RuntimeError(f"Failed to run {host}")

    # print(f" * Running on {tunnel_url}")
    os.environ['webui_url'] = tunnel_url
    colab_url = os.getenv('colab_url')
    if cmd_opts.multiple:
        send_to_discord(tunnel_url, cmd_opts.webhook)
        strings.en[
            "RUNNING_LOCALLY_SEPARATED"] = f"Public WebUI Colab remote.moe URL: {tunnel_url}"
        strings.en["SHARE_LINK_DISPLAY"] = "Please do not use this link we are getting ERROR: Exception in ASGI application:  {}"
    else:
        strings.en["SHARE_LINK_MESSAGE"] = f"Public WebUI Colab URL: {tunnel_url}"


def googleusercontent_tunnel():
    colab_url = os.getenv('colab_url')
    strings.en["SHARE_LINK_MESSAGE"] = f"WebUI Colab URL: {colab_url}"


if cmd_opts.localhostrun:
    print("localhost.run detected, trying to connect...")
    ssh_tunnel(LOCALHOST_RUN)

if cmd_opts.remotemoe:
    print("remote.moe detected, trying to connect...")
    ssh_tunnel(REMOTE_MOE)

if cmd_opts.googleusercontent:
    print("googleusercontent.com detected, trying to connect...")
    googleusercontent_tunnel()

if cmd_opts.multiple:
    print("all detected, remote.moe trying to connect...")
    ssh_tunnel(REMOTE_MOE)
    googleusercontent_tunnel()
    ssh_tunnel(LOCALHOST_RUN)

#!/usr/bin/env python3.7
# ------------------------------------------------------- #
#                                                         #
# dline                                                   #
#                                                         #
# http://github.com/NatTupper/dline                       #
#                                                         #
# Licensed under GNU GPLv3                                #
#                                                         #
# ------------------------------------------------------- #

from dline.utils.version import check_versions
if not check_versions():
    print("Please install the correct versions with: " +\
            "pip install --user -r requirements.txt")
    quit()

import os
import asyncio
import curses
import subprocess
import argparse
from discord import TextChannel
from dline.input.input_handler import key_input, typing_handler
from dline.ui.ui import draw_screen, draw_help
from dline.utils.globals import gc, kill, Found
from dline.utils.settings import copy_skeleton, load_config
from dline.utils.updates import check_for_updates
from dline.utils.threads import WorkerThread
from dline.utils.token_utils import get_token, store_token
from dline.utils.log import log, startLogging, msglog
from dline.client.guildlog import PrivateGuild, GuildLog
from dline.client.channellog import PrivateChannel, ChannelLog
from dline.client.on_message import on_incoming_message

init_complete = False

# Set terminal X11 window title
print('\33]0;dline\a', end='', flush=True)

gc.initClient()

@gc.client.event
async def on_ready():
    # these values are set in settings.yaml
    if gc.settings["default_prompt"] is not None:
        gc.client.prompt = gc.settings["default_prompt"].lower()
    else:
        gc.client.prompt = '~'

    if gc.settings["default_activity"] is not None:
        await gc.client.set_activity(gc.settings["default_activity"])

    privateGuild = PrivateGuild(gc.client.user)
    channels = []
    channel_logs = []
    nchannels = 0
    for idx,channel in enumerate(gc.client.private_channels):
        chl = PrivateChannel(channel, privateGuild, idx)
        channels.append(chl)
        channel_logs.append(ChannelLog(chl, []))
        nchannels += 1
    privateGuild.set_channels(channels)
    privateGuild.set_nchannels(nchannels)
    gc.guild_log_tree.append(GuildLog(privateGuild, channel_logs))

    for guild in gc.client.guilds:
        # Null check to check guild availability
        if guild is None:
            continue
        serv_logs = []
        nchannels = 0
        for channel in guild.channels:
            # Null checks to test for bugged out channels
            #if channel is None or channel.type is None:
            #    continue
            # Null checks for bugged out members
            if guild.me is None or guild.me.id is None \
                    or channel.permissions_for(guild.me) is None:
                continue
            if isinstance(channel, TextChannel):
                nchannels += 1
                if channel.permissions_for(guild.me).read_messages:
                    serv_logs.append(ChannelLog(channel, []))

        # add the channellog to the tree
        gl = GuildLog(guild, serv_logs)
        gl.set_nchannels(nchannels)
        gc.guild_log_tree.append(gl)

    if gc.settings["default_guild"] is not None:
        gc.client.set_current_guild(gc.settings["default_guild"])
        if gc.client.current_guild is None:
            print("ERROR: default_guild not found!")
            raise KeyboardInterrupt
            return
        if gc.settings["default_channel"] is not None:
            gc.client.current_channel = gc.settings["default_channel"].lower()
            gc.client.prompt = gc.settings["default_channel"].lower()

    # start our own coroutines
    gc.client.loop.create_task(gc.client.run_calls())
    gc.ui_thread.start()
    while not gc.ui.isInitialized:
        await asyncio.sleep(0.1)

    await gc.client.init_channel()
    draw_screen()

    gc.key_input_thread = WorkerThread(gc, key_input)
    gc.typing_handler_thread = WorkerThread(gc, typing_handler)
    gc.exit_thread = WorkerThread(gc, kill)

    gc.key_input_thread.start()
    gc.typing_handler_thread.start()

    global init_complete
    init_complete = True

# called whenever the client receives a message (from anywhere)
@gc.client.event
async def on_message(message):
    await gc.client.wait_until_ready()
    if init_complete:
        msglog(message)
        await on_incoming_message(message)

@gc.client.event
async def on_message_edit(msg_old, msg_new):
    await gc.client.wait_until_ready()
    if msg_old.clean_content == msg_new.clean_content:
        return
    clog = gc.client.current_channel
    if clog is None:
        return
    ft = gc.ui.views[str(clog.id)].formattedText
    msg_new.content = msg_new.content + " **(edited)**"
    idx = 0
    while True:
        if len(ft.messages) >= idx:
            break
        if ft.messages[idx].id == msg_old.id:
            ft.messages[idx].content = msg_new.content
            break
        idx += 1
    ft.refresh()

    if init_complete and msg_old.channel is gc.client.current_channel:
        draw_screen()

@gc.client.event
async def on_message_delete(msg):
    log("Attempting to delete")
    await gc.client.wait_until_ready()
    # TODO: PM's have 'None' as a guild -- fix this later
    if msg.guild is None: return

    try:
        for guildlog in gc.guild_log_tree:
            if guildlog.guild == msg.guild:
                for channellog in guildlog.logs:
                    if channellog.channel == msg.channel:
                        ft = gc.ui.views[str(channellog.channel.id)].formattedText
                        channellog.logs.remove(msg)
                        ft.messages.remove(msg)
                        ft.refresh()
                        log("Deleted, updating")
                        if msg.channel is gc.client.current_channel:
                            draw_screen()
                        return
    except:
        # if the message cannot be found, an exception will be raised
        # this could be #1: if the message was already deleted,
        # (happens when multiple calls get excecuted within the same time)
        # or the user was banned, (in which case all their msgs disappear)
        pass
    log("Could not delete message: {}".format(msg.clean_content))

async def runSimpleHelp():
    load_config(gc, None)
    curses.wrapper(gc.ui.run)
    draw_help(terminateAfter=True)

def terminate_curses():
    curses.nocbreak()
    gc.ui.screen.keypad(False)
    curses.echo()
    curses.endwin()

def convert_confdir():
    from shutil import move
    move(os.getenv("HOME")+"/.config/Discline", \
            os.getenv("HOME")+"/.config/dline")
    move(os.getenv("HOME")+"/.config/dline/config", \
            os.getenv("HOME")+"/.config/dline/config.yaml")

def main():
    token = None
    parser = argparse.ArgumentParser(description="A terminal Discord client", \
            add_help=False)
    parser.add_argument("-h", "--help", help="Print command line arguments", \
            action="store_true")
    parser.add_argument("--store-token", help="Store your token", \
            action="store_true")
    parser.add_argument("--copy-skeleton", help="Copy default config", \
            action="store_true")
    parser.add_argument("--token-path", help="Specify a token file")
    parser.add_argument("--config-path", help="Specify a config path")
    parser.add_argument("-v", "--version", help="Print version", \
            action="store_true")

    args = parser.parse_args()
    # check for legacy config path
    if os.path.exists(os.getenv("HOME") + "/.config/Discline"):
        convert_confdir()
    config_path = None
    if args.help:
        try:
            asyncio.get_event_loop().run_until_complete(runSimpleHelp())
        except SystemExit:
            pass
        terminate_curses()
        quit()
    elif args.store_token:
        store_token()
        quit()
    elif args.copy_skeleton:
        copy_skeleton()
        quit()
    elif args.version:
        commit_id = subprocess.run(("git", "log"), stdout=subprocess.PIPE) \
                .stdout.decode("utf-8").split('\n')[0].replace("commit ","")
        print("dline at commit {}".format(commit_id[:8]))
        quit()
    if args.token_path:
        try:
            with open(args.token_path) as f:
                token = f.read().strip()
        except:
            print("Error: Cannot read token from path")
            quit()
    if args.config_path:
        config_path = args.config_path

    load_config(gc, config_path)

    log_messages = False
    if gc.settings and gc.settings["debug"]:
        if gc.settings["message_log"]:
            log_messages = True
        startLogging(log_messages)

    check_for_updates()
    if token is None:
        token = get_token()

    print(gc.term.yellow("Starting..."))

    # start the client
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(gc.client.run(token, bot=False))
    except:
        loop.close()

    if gc.ui.isInitialized:
        terminate_curses()

if __name__ == "__main__":
    main()

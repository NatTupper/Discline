import curses
import curses.ascii as ascii
import logging
import re
import time
from dline.ui import ui
from dline.utils.log import log
from dline.utils.globals import gc
from dline.commands.sendfile import send_file
from dline.commands.channel_jump import channel_jump

KEY_CTRL_UP = 574
KEY_CTRL_RIGHT = 568
KEY_CTRL_DOWN = 531
KEY_CTRL_LEFT = 553

def key_input():
    # if the next two aren't here, input does not work
    curses.cbreak()
    curses.noecho()
    editWin = gc.ui.editWin
    gc.ui_thread.wait_until_ui_task_completes((ui.draw_edit_win, True))
    while not gc.doExit:
        ch = editWin.getch()
        if ch == -1 or not gc.ui.displayPanel.hidden():
            time.sleep(0.01)
            continue

        if chr(ch) != '\n' and len(gc.ui.messageEdit.inputBuffer) > 0 and \
                gc.ui.messageEdit.inputBuffer[0] != ord('/'):
            gc.typingBeingHandled = True
        # prevents crashes when enter is hit and input buf is empty
        if chr(ch) == '\n' and not gc.ui.messageEdit.inputBuffer:
            continue
        if ch == curses.KEY_PPAGE:
            gc.ui.channel_log_offset -= gc.settings["scroll_lines"]
            ui.draw_screen()
            continue
        elif ch == curses.KEY_NPAGE:
            gc.ui.channel_log_offset += gc.settings["scroll_lines"]
            ui.draw_screen()
            continue
        elif ch == curses.KEY_RESIZE:
            gc.ui.resize()
            ui.draw_screen()
            continue
        elif ch == curses.KEY_DC:
            # TODO: Add functionality here
            ui.draw_screen()
            continue
        # For later ctrl+key combos
        elif ascii.isctrl(ch):
            pass
        elif ch == KEY_CTRL_LEFT:
            gc.client.channel_backward()
            ui.draw_screen()
            continue
        elif ch == KEY_CTRL_RIGHT:
            gc.client.channel_forward()
            ui.draw_screen()
            continue
        # if ESC is pressed, clear messageEdit buffer
        elif ch == 27:
            ch = editWin.getch()
            if ch in (0x7f, ord('\b'), curses.KEY_BACKSPACE):
                gc.ui.messageEdit.reset()
                gc.ui_thread.wait_until_ui_task_completes((ui.draw_edit_win, True))
            continue
        ret = gc.ui.messageEdit.addKey(ch)
        if ret is not None:
            input_handler(ret)
            gc.ui.messageEdit.reset()
        call = (ui.draw_edit_win, True)
        gc.ui_thread.funcs.append(call)
        while not gc.doExit and (call in gc.ui_thread.funcs or \
                call[0].__name__ in gc.ui_thread.locks):
            time.sleep(0.01)
    log("key_input finished")
    gc.tasksExited += 1

def typing_handler():
    if not gc.settings["send_is_typing"]: return

    log("typing_handler started")
    while not gc.doExit:
        if gc.typingBeingHandled:
            call = (gc.client.current_channel.trigger_typing,)
            gc.client.async_funcs.append(call)
            while not gc.doExit and (call in gc.client.async_funcs or \
                    call[0].__name__ in gc.client.locks):
                time.sleep(0.1)
            for second in range(50):
                if gc.doExit:
                    break
                time.sleep(0.1)
            gc.typingBeingHandled = False
            if gc.doExit:
                break
        time.sleep(0.1)
    log("typing_handler finished")
    gc.tasksExited += 1

def input_handler(text):
    # Must be a command
    if text.startswith(gc.settings["prefix"]):
        text = text[1:]
        arg = None
        if ' ' in text:
            command,arg = text.split(" ", 1)
        elif not text:
            return
        else:
            command = text
            arg = None
        parseCommand(command, arg)
    # Must be text
    else:
        # Emoji
        if text.count(':')%2 == 0:
            text = parseEmoji(text)
        if '@' in text:
            sects = []
            for sect in text.lower().strip().split('@'):
                sects.append(sect.split(' '))
            mentions = []
            for sect in sects:
                if not sect:
                    continue
                for member in gc.client.current_guild.members:
                    for i in reversed(range(len(sect))):
                        segment = sect[:i+1]
                        if not segment[0]:
                            continue
                        if " ".join(segment).lower() in member.display_name.lower():
                            m = re.search('@'+" ".join(segment), text)
                            if m is None:
                                continue
                            text = text[:m.start()] + '{}' + text[m.end():]
                            mention = "<@!" + str(member.id) + ">"
                            mentions.append(mention)
                            break
            text = text.format(*mentions)
        for i in range(0,3):
            try:
                gc.client.wait_until_client_task_completes(\
                        (gc.client.current_channel.send, text))
                break
            except:
                time.sleep(3)

def parseCommand(command, arg=None):
    if arg is None:
        if command in ("refresh", "update"):
            ui.draw_screen()
            log("Manual update done", logging.info)
        elif command in ("quit", "exit"):
            try: gc.exit_thread.start()
            except SystemExit: pass
        elif command in ("help", 'h'): ui.draw_help()
        elif command in ("guilds", "glds", "servers", "servs"): ui.draw_guildlist()
        elif command in ("channels", "chans"): ui.draw_channellist()
        elif command == "emojis": ui.draw_emojilist()
        elif command in ("users", "members"): ui.draw_userlist()
        elif command == "nick": change_nick()
        elif command == "dm": change_guild("private messages")
        elif command in ("del", "rm"): gc.client.remove_last_message()
        elif command[0] == 'c':
            try:
                if command[1].isdigit():
                    channel_jump(command)
                    ui.draw_screen()
            except IndexError:
                pass
        return

    if command in ('guild', 'g', 'server', 's'):
        change_guild(arg)
    elif command in ("channel", 'c'):
        gc.client.current_channel = arg
        gc.ui.channel_log_offset = -1
        ui.draw_screen()
    elif command == "nick":
        change_nick(arg)
        return
    elif command in ("game", "activity"):
        gc.client.wait_until_client_task_completes((gc.client.set_activity, arg))
    elif command == "file":
        send_file(arg)
    elif command == "status":
        status = arg.lower()
        if status in ("away", "afk"):
            status = "idle"
        elif "disturb" in status:
            status = "dnd"

        if status in ("online", "offline", "idle", "dnd"):
            gc.client.wait_until_client_task_completes(\
                    (gc.client.set_status, status))

def change_nick(arg=None):
    try:
        gc.client.wait_until_client_task_completes(\
                (gc.client.current_guild.me.edit,{'nick':arg}))
    except:
        pass

def change_guild(arg):
    prev_guild = gc.client.current_guild
    gc.client.set_current_guild(arg)
    if gc.client.current_guild is prev_guild:
        return
    log("changed guild")
    gc.ui.channel_log_offset = -1
    ui.draw_screen()

def parseEmoji(text):
    if gc.client.user.premium:
        for emoji in gc.client.emojis:
            short_name = ':' + emoji.name + ':'
            if short_name in text:
                full_name = "<:{}:{}>".format(emoji.name, emoji.id)
                text = text.replace(short_name, full_name)
    elif gc.client.current_guild.emojis is not None and \
            len(gc.client.current_guild.emojis) > 0:
        for emoji in gc.client.current_guild.emojis:
            short_name = ':' + emoji.name + ':'
            if short_name in text:
                full_name = "<:{}:{}>".format(emoji.name, emoji.id)
                text = text.replace(short_name, full_name)

    return text

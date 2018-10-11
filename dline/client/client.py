import sys
import time
import asyncio
import logging
import discord
from dline.client.channellog import PrivateChannel
from dline.utils.log import log
from dline.utils.globals import gc, Found, NoChannelsFoundException
from dline.ui.ui_utils import calc_mutations
from dline.ui.ui import set_display, draw_screen
from dline.ui.view import init_view

# inherits from discord.py's Client
class Client(discord.Client):
    def __init__(self, *args, **kwargs):
        self._current_guild = None
        self._current_channel = None
        self._prompt = ""
        self._status = None
        self._activity = None
        self.async_funcs = []
        self.locks = []
        super().__init__(*args, **kwargs)

    async def run_calls(self):
        self.locks = []
        while not gc.doExit:
            if len(self.async_funcs) > 0:
                call = self.async_funcs.pop()
                func = call[0]
                self.locks.append(func.__name__)
                args = []
                opt_args = {}
                if len(call) > 1:
                    for arg in call[1:]:
                        if isinstance(arg, dict):
                            opt_args = arg
                        else:
                            args.append(arg)
                try:
                    await func(*args, **opt_args)
                except Exception as e:
                    log("Could not await {}".format(func))
                    log("\targs: {}\n\topt_args: {}".format(args, opt_args))
                    log("\terror: {}".format(e))
                self.locks.remove(func.__name__)
            await asyncio.sleep(0.01)

    def wait_until_client_task_completes(self, call):
        func = call[0]
        args = []
        if len(call) > 1:
            args = call[1:]
        self.async_funcs.append(call)
        while call in self.async_funcs or \
                func.__name__ in self.locks:
            time.sleep(0.01)

    async def on_error(self, event_method, *args, **kwargs):
        import traceback
        log('Ignoring exception in {}'.format(event_method))
        traceback.print_exc()

    @property
    def prompt(self):
        return self._prompt
    @prompt.setter
    def prompt(self, prompt):
        self._prompt = prompt

    @property
    def current_guild(self):
        # discord.Guild object
        return self._current_guild

    def channel_backward(self):
        channels = self._current_guild.channels
        current_index = self._current_channel.position
        nchannels = self.current_guild_log.nchannels
        new_index = current_index-1
        if new_index < 0:
            new_index = nchannels-1

        for channel in channels:
            if isinstance(channel, discord.TextChannel) and\
                    channel.position == new_index:
                self.set_current_channel(channel)
                break

    def channel_forward(self):
        channels = self._current_guild.channels
        current_index = self._current_channel.position
        nchannels = self.current_guild_log.nchannels
        new_index = current_index+1
        if new_index >= nchannels:
            new_index = 0

        for channel in channels:
            if isinstance(channel, discord.TextChannel) and\
                    channel.position == new_index:
                self.set_current_channel(channel)
                break

    def set_current_guild(self, guild):
        if isinstance(guild, str):
            for gldlog in gc.guild_log_tree:
                gld = gldlog.guild
                if guild.lower() in gld.name.lower():
                    if not gld.channels:
                        set_display("This guild is empty!")
                        return
                    self._current_guild = gld
                    # find first non-ignored channel, set channel, mark flags as False
                    def_chan = None
                    lowest = 999
                    for chan in gld.channels:
                        if isinstance(chan, discord.TextChannel) and \
                                chan.permissions_for(gld.me).read_messages and \
                                chan.position < lowest:
                            try:
                                # Skip over ignored channels
                                for serv_key in gc.settings["channel_ignore_list"]:
                                    if serv_key["guild_name"].lower() == gld.name:
                                        for name in serv_key["ignores"]:
                                            if chan.name.lower() == name.lower():
                                                raise Found
                            except Found:
                                continue
                            except:
                                e = sys.exc_info()[0]
                                log("Exception raised during channel ignore list parsing: {}".format(e),
                                        logging.error)
                                return
                            lowest = chan.position
                            def_chan = chan
                        elif isinstance(chan, PrivateChannel):
                            def_chan = chan
                        else:
                            continue
                        try:
                            if def_chan is None:
                                raise NoChannelsFoundException
                            self.current_channel = def_chan
                            for chanlog in gldlog.logs:
                                if chanlog.channel is def_chan:
                                    chanlog.unread = False
                                    chanlog.mentioned_in = False
                                    return
                        except NoChannelsFoundException:
                            log("No channels found.")
                            return
                        except AttributeError as e:
                            log("Attribute error: {}".format(e))
                            return
                        except:
                            e = sys.exc_info()[0]
                            log("Error when setting channel flags!: {}".format(e), logging.error)
                            continue
                    return
            return
        self._current_guild = guild

    @property
    def current_channel(self):
        return self._current_channel

    def set_current_channel(self, channel):
        if isinstance(channel, str):
            try:
                gld = self.current_guild
                channel_found = None
                channel_score = 0.0
                for chl in gld.channels:
                    if channel.lower() in chl.name.lower() and \
                            isinstance(chl, discord.TextChannel) and \
                            chl.permissions_for(gld.me).read_messages:
                        score = len(channel) / len(chl.name)
                        if score > channel_score:
                            channel_found = chl
                            channel_score = score
                    elif isinstance(chl, PrivateChannel) and \
                            channel.lower() in chl.name.lower():
                        channel_found = chl
                        break
                if channel_found != None:
                    self._current_channel = channel_found
                    self._prompt = channel_found.name
                    if len(gc.channels_entered) > 0:
                        chanlog = self.current_channel_log
                        chanlog.unread = False
                        chanlog.mentioned_in = False
                    return
                raise RuntimeError("Could not find channel!")
            except RuntimeError as e:
                log("RuntimeError during channel setting: {}".format(e), logging.error)
                return
            except AttributeError as e:
                log("Attribute error, chanlog is None: {}".format(e), logging.error)
                return
            except:
                e = sys.exc_info()[0]
                log("Unknown exception during channel setting: {}".format(e), logging.error)
                return
        self._current_channel = channel
        self._prompt = channel.name
        if len(gc.channels_entered) > 0:
            chanlog = self.current_channel_log
            chanlog.unread = False
            chanlog.mentioned_in = False

    @current_channel.setter
    def current_channel(self, channel):
        self.set_current_channel(channel)

    @property
    def current_guild_log(self):
        for slog in gc.guild_log_tree:
            if slog.guild is self._current_guild:
                return slog

    @property
    def current_channel_log(self):
        slog = self.current_guild_log
        for idx, clog in enumerate(slog.logs):
            if clog.channel.name.lower() == self._current_channel.name.lower():
                if isinstance(clog.channel, PrivateChannel) or \
                        (isinstance(clog.channel, discord.TextChannel) and \
                        clog.channel.permissions_for(slog.guild.me).read_messages):
                    return clog

    @property
    def online(self):
        online_count = 0
        if self.current_guild is not None:
            if isinstance(self.current_guild, discord.Guild):
                for member in self.current_guild.members:
                    if member is None: continue # happens if a member left the guild
                    if isinstance(member, discord.Member):
                        if member.status is not discord.Status.offline:
                            online_count +=1
                return online_count
            else:
                for user in self.current_guild.members:
                    for guild in self.guilds:
                        member = guild.get_member(user.id)
                        if member is not None:
                            if member.status != discord.Status.offline:
                                online_count += 1
                            break
                return online_count

    @property
    def activity(self):
        return self._activity

    async def set_activity(self, activity):
        self._activity = discord.Activity(name=activity,type=0)
        self._status = discord.Status.online
        # Note: the 'afk' kwarg handles how the client receives messages, (rates, etc)
        # This is meant to be a "nice" feature, but for us it causes more headache
        # than its worth.
        if self._activity is not None and self._activity != "":
            if self._status is not None and self._status != "":
                try: await self.change_presence(activity=self._activity, status=self._status, afk=False)
                except: pass
            else:
                try: await self.change_presence(activity=self._activity, status=discord.Status.online, afk=False)
                except: pass

    @property
    def status(self):
        return self._status
    async def set_status(self, status):
        if status == "online":
            self._status = discord.Status.online
        elif status == "offline":
            self._status = discord.Status.offline
        elif status == "idle":
            self._status = discord.Status.idle
        elif status == "dnd":
            self._status = discord.Status.dnd

        if self._activity is not None and self._activity != "":
            try:
                await self.change_presence(activity=self._activity, status=self._status, afk=False)
            except:
                pass
        else:
            try:
                await self.change_presence(status=self._status, afk=False)
            except:
                pass

    async def send_typing(self, channel):
        if channel.permissions_for(self.current_guild.me).send_messages:
            await super().send_typing(channel)

    def remove_last_message(self):
        log("Attempting to delete last message")
        messages = gc.ui.views[str(self.current_channel.id)].formattedText.messages
        message = None
        i = len(messages)-1
        while i >= 0:
            message = messages[i]
            if message.author.id == self.user.id:
                log("Deleting message '{}'".format(message.clean_content))
                self.wait_until_client_task_completes((message.delete,))
                gc.ui.views[str(self.current_channel.id)].formattedText.refresh()
                draw_screen()
                return
            i -= 1
        log("Could not delete last message")

    async def init_channel(self, channel=None):
        clog = None
        if channel is None:
            clog = self.current_channel_log
            log("Initializing current channel")
        else:
            log("Initializing channel {}".format(channel.name))
            try:
                for gldlog in gc.guild_log_tree:
                    for chllog in gldlog.logs:
                        if chllog.channel == channel:
                            clog = chllog
                            raise Found
            except Found:
                pass
        if isinstance(clog.channel, PrivateChannel) or \
                isinstance(clog.channel, discord.TextChannel) and \
                clog.channel.permissions_for(clog.guild.me).read_messages:
            try: #TODO: Remove try/except once bug is fixed
                async for msg in clog.channel.history(limit=gc.settings["max_log_entries"]):
                    if msg.edited_at is not None:
                        msg.content += " **(edited)**"
                    # needed for modification of past messages
                    #self.messages.append(msg)
                    clog.insert(0, calc_mutations(msg))
            except discord.Forbidden:
                log("Cannot enter channel {}: Forbidden.".format(clog.channel.name))
                init_view(gc, clog.channel)
                return
            except Exception as e:
                log("error: {}".format(e))
            gc.channels_entered.append(clog.channel)
            init_view(gc, clog.channel) # initialize view
            for msg in clog.logs:
                gc.ui.views[str(clog.channel.id)].formattedText.addMessage(msg)

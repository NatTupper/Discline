
class PrivateGuild:
    def __init__(self, me):
        self.name = "Private Messages"
        self.roles = None
        self.emojis = None
        self.channels = None
        self.me = me
        self.members = []

    def set_channels(self, channels):
        self.channels = channels
        if not channels:
            return
        for channel in channels:
            for member in channel.members:
                if member not in self.members:
                    self.members.append(member)

    def set_nchannels(self, nchannels):
        self.nchannels = nchannels

# Simple wrapper class to hold a list of ChannelLogs
class GuildLog():
    def __init__(self, guild, channel_log_list):
        self._guild = guild
        self._channel_logs = list(channel_log_list)

    @property
    def guild(self):
        return self._guild

    @property
    def name(self):
        return self._guild.name

    @property
    def logs(self):
        return self._channel_logs

    def set_nchannels(self, nchannels):
        self.nchannels = nchannels

    def clear_logs(self):
        for channel_log in self._channel_logs:
            del channel_log[:]

    # takes list of ChannelLog
    def add_logs(self, log_list):
        for logs in log_list:
            self._channel_logs.append(logs)

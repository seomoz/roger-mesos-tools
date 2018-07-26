import slackweb
from sets import Set
from datetime import datetime
from slackclient import SlackClient

from cli.settings import Settings
from cli.appconfig import AppConfig
from cli.utils import printException, printErrorMsg


class WebHook:

    def __init__(self):
        self.disabled = True
        self.emoji = ':rocket:'
        self.defChannel = ''
        self.config_dir = ''
        self.username = 'roger-deploy-bot'
        self.settingObj = Settings()
        self.appconfigObj = AppConfig()
        self.configLoadFlag = False
        self.config = ''
        self.config_channels = []
        self.config_envs = []
        self.config_commands = []

    def webhookSetting(self):
        """
        Prepares webhook setting from roger-mesos-tools.config file
        File should have all the required variables otherwise it exits
        with a warning message
        """
        try:
            self.config_dir = self.settingObj.getConfigDir()
            roger_env = self.appconfigObj.getRogerEnv(self.config_dir)
            if 'slack_webhook_url' in roger_env.keys():
                self.webhookURL = roger_env['slack_webhook_url']
            if 'slack_api_token' in roger_env.keys():
                self.token = roger_env['slack_api_token']
            if 'slack_default_channel' in roger_env.keys():
                self.defChannel = roger_env['slack_default_channel']
            if 'slack_deploy_botid' in roger_env.keys():
                self.botid = roger_env['slack_deploy_botid']
        except (Exception) as e:
            print("Warning: slackweb basic initialization failed (error: %s).\
            Not using slack." % e)
            return
        try:
            self.sc = SlackClient(self.token)
            self.client = slackweb.Slack(url=self.webhookURL)
            self.disabled = False
        except (Exception) as e:
            print("Warning: slackweb basic initialization failed (error: %s).\
            Not using slack." % e)
            return  # disabled flag remains False

    def custom_api_call(self, text, channel):
        """ Makes the webhook call
        Keyword arguments:
        text -- message to be posted
        channel -- to which channel

        posts a message if rogeros - bot is present
        """
        try:
            self.webhookSetting()
            if len(channel) == 0:
                channel = self.defChannel
            var = self.sc.api_call("channels.list")
            length = len(var['channels'])
            for iterator in range(0, length):
                # getting rid of # for comparison
                if channel[1:] == var['channels'][iterator]['name']:
                    if self.botid in var['channels'][iterator]['members']:
                        if not self.disabled:
                            self.client.notify(channel=channel, username=self.username,
                                               icon_emoji=self.emoji, text=text)
        except (Exception) as e:
            # notify to channel and log it as well
            printException(e)
            raise

    def areBasicKeysAvailableInConfig(self, config):
        if 'notifications' not in config:
            return False
        tempList = config['notifications'].keys()
        if 'channels' not in tempList:
            return False  # if no channel is available nothing can be done
        if 'envs' not in tempList:
            self.config_envs = ['dev', 'production', 'staging', 'local']
        if 'commands' not in tempList:
            self.config_commands = ['pull', 'build', 'push']
        return True

    def areBasicKeysAvailableInAppdata(self, appdata):
        tempList = appdata.keys()
        if 'notifications' not in tempList:
            return False
        appKeys = appdata['notifications'].keys()
        if 'channels' not in appKeys:
            return False
        return True

    def configLevelSettings(self, config_file):
        """ Prepares all the config_level settings as variables

        Keyword arguments:
        config_file -- This is the file name passed as argument
        return three sets of channels, envs and commands.
        self variable as config level variable not expected to change for the run
        """
        if (not self.configLoadFlag):
            self.config = self.appconfigObj.getConfig(self.config_dir, config_file)
            self.configLoadFlag = True
            if(not self.areBasicKeysAvailableInConfig(self.config)):
                return
            try:
                self.config_channels = Set(self.config['notifications']['channels'])
                if 'envs' in self.config['notifications'].keys():
                    self.config_envs = Set(self.config['notifications']['envs'])
                if 'commands' in self.config['notifications'].keys():
                    self.config_commands = Set(self.config['notifications']['commands'])
                if (len(self.config_channels) == 0 or len(self.config_envs) == 0 or len(self.config_commands) == 0):
                    return
            except (Exception, KeyError, ValueError) as e:
                # notify to channel and log it as well
                printException(e)
                raise

    def invoke_webhook(self, appdata, config_file, action, env, user):
        """ Pepares set and posts to slack channel

        Keyword arguments:
        appdata -- this is value related to an app
        hook_input_metric -- value it  gets from hook class per app
        config_file -- the file name under for the app deployment
        """
        envSet = []
        commandsSet = []
        self.function_execution_start_time = datetime.now()
        self.webhookSetting()
        self.configLevelSettings(config_file)
        self.action = action
        self.envr = env
        self.user = user
        self.app_name = appdata['name'] 
        try:

            if(not self.areBasicKeysAvailableInAppdata(appdata)):
                return
            if 'notifications' in appdata:
                channelsSet = Set(appdata['notifications']['channels'])
                # to handle if tag is there but no data is present
                if (len(self.config_channels) != 0):
                    channelsSet = channelsSet.union(self.config_channels)
                # to handle if tag is there
                if 'envs' in appdata['notifications'].keys():
                    envSet = Set(appdata['notifications']['envs'])
                # to handle if tag is there but data is not there
                if (len(self.config_envs) != 0):
                    envSet = envSet.union(self.config_envs)
                if 'commands' in appdata['notifications'].keys():
                    commandsSet = Set(appdata['notifications']['commands'])
                if (len(self.config_commands) != 0):
                    commandsSet = commandsSet.union(self.config_commands)
                if (len(channelsSet) == 0 or len(envSet) == 0 or len(commandsSet) == 0):
                    return
            else:
                if list(self.config_envs)[0] == 'all':
                    self.config_envs = ['dev', 'production', 'staging', 'local']
                if list(self.config_commands)[0] == 'all':
                    self.config_commands = ['pull', 'build', 'push']
                self.postToSlack(self.action, self.config_envs, self.config_commands, self.config_channels)
                return
            if list(envSet)[0] == 'all':
                envSet = ['dev', 'production', 'staging', 'local']
            if list(commandsSet)[0] == 'all':
                commandsSet = ['pull', 'build', 'push']
        except (Exception, KeyError, ValueError) as e:
            printException(e)
            raise
        try:
            self.postToSlack(self.action, envSet, commandsSet, channelsSet)
        except (Exception) as e:
            self.custom_api_call("Error : %s" % e, self.defChannel)
            printException(e)
            raise

    def postToSlack(self, action, envSet, commandsSet, channelsSet):
        """ Prepares post to slack channel
        Keyword arguments:
        action -- action extracted from hookname_input_metric
        envSet -- set of accepted environment
        commandsSet -- set of accepted commandssets
        channelsSet -- set of accepted channelsets
        """
        try:
            if ('post' in action and self.envr in envSet and action.split('_')[1] in commandsSet):
                for channel in channelsSet:
                    timeElapsed = '{0:.2f}'.format((datetime.now() - self.function_execution_start_time).total_seconds() * 1000)
                    timeasInt = float(timeElapsed)
                    h, m, s, ms = self.makeTimeReadable(timeasInt)
                    readableTime = self.createMesage(h, m, s, ms)
                    slackMessage = ("Completed *" + action.split('_')[1] + "* of *" + self.app_name + "* on *" + self.envr + "* in *" + readableTime + "*  (triggered by *" + self.user + "*)")
                    self.custom_api_call(slackMessage, '#' + channel)
        except (Exception) as e:
            self.custom_api_call("Error : %s" % e, self.defChannel)
            printException(e)
            raise

    def makeTimeReadable(self, ms):
        """ Make time readable

        Keyword arguments:
        ms -- time in miliseconds
        """
        s = ms / 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return h, m, s, ms

    def createMesage(self, h, m, s, ms):
        message = ''
        if int(h) > 0:
            message += str(int(h)) + "h "
        if int(m) > 0:
            message += str(int(m)) + "m "
        if int(s) > 0:
            message += str(int(s)) + "s "
        message += str(ms) + "ms "
        return message

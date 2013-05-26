import os
import ConfigParser


class TwitterConfig(object):
    def __init__(self, filename):
        self.filename = filename
        self.config = ConfigParser.RawConfigParser()
        # create file if not exists
        if not os.path.exists(self.filename):
            open(self.filename, 'w').close()
        with open(self.filename) as fp:
            self.config.readfp(fp)

    def get(self, option, account=None, default=None):
        section = account or 'general'
        try:
            return self.config.get(section, option)
        except ConfigParser.NoSectionError:
            return default

    def set(self, option, value, account=None):
        section = account or 'general'
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)
        return self

    def unset(self, option, account=None):
        section = account or 'general'
        self.config.remove_option(section, option)
        if len(self.config.items(section)) == 0:
            self.config.remove_section(section)
        return self

    def remove_account(self, account):
        section = account or 'general'
        self.config.remove_section(section)
        return self

    def list_accounts(self):
        return [section for section in self.config.sections() if section != 'general']

    def save(self, filename=None):
        filename = filename or self.filename
        with open(filename, 'w') as fp:
            self.config.write(fp)
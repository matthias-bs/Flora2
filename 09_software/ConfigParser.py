"""
Minimal and functional version of CPython's ConfigParser module.
Source: https://github.com/Mika64/micropython-lib/blob/master/configparser/ConfigParser.py

20210131 MPr:
    - Added methods getboolean(), getint() and getfloat()
    - Added skipping of lines starting with '#' (but no proper handling of comments in remaining part of line) 
20210206 MPr:
    - read() method rewritten to consume less memory by reading and evaluating config file
      line by line
20210211 MPr:
    - modified read() to process a list of files, added silently ignoring non-existent files
20210711 MPr:
    - modified getboolean() to allow passing of fallback as integer
"""

TRUE_ENCODINGS = ["1", "yes", "true", "on", "True"]

class ConfigParser:
    def __init__(self, delimiters, inline_comment_prefixes):
        self.config_dict = {}
    
    def sections(self):
        """Return a list of section names, excluding [DEFAULT]"""
        to_return = [section for section in self.config_dict.keys() if not section in "DEFAULT"]
        return to_return

    def add_section(self, section):
        """Create a new section in the configuration."""
        self.config_dict[section] = {}

    def has_section(self, section):
        """Indicate whether the named section is present in the configuration."""
        if section in self.config_dict.keys():
            return True
        else:
            return False

    def add_option(self, section, option):
        """Create a new option in the configuration."""
        if self.has_section(section) and not option in self.config_dict[section]:
            self.config_dict[section][option] = None
        else:
            raise

    def options(self, section):
        """Return a list of option names for the given section name."""
        if not section in self.config_dict:
            raise
        return self.config_dict[section].keys()

    def read(self, filename=None, fp=None):
        if type(filename) is list:
            for f in filename:
                self._read(f)
        else:
            self._read(filename)
            
    def _read(self, filename=None, fp=None):
        """Read and parse a filename or a list of filenames."""
        if not fp and not filename:
            print("ERROR : no filename and no fp")
            raise
        elif not fp and filename:
            try:
                with open(filename, 'r') as fp:
                    self.config_dict = {}
                    section = 'Default'
                    
                    for line in fp:
                        # split line at first separator '#' and take first part
                        line = line.split('#', 1)[0]
                        
                        # remove leading/trailing whitespaces
                        line = line.strip()
                        
                        if line.startswith('[') and line.endswith(']'):
                            section = line.replace('[','').replace(']','')
                            self.config_dict[section] = {}
                        
                        if '=' in line:
                            value = None
                            option, value = line.split('=', 1)
                            option = option.strip()
                            value = value.strip()
                            self.config_dict[section][option] = value
           
            except FileNotFoundError:
                return
           
    def get(self, section, option, fallback=''):
        """Get value of a givenoption in a given section."""
        if not self.has_section(section):
            raise
        if not self.has_option(section,option):
            if (fallback == ''):
                raise
            else:
                return fallback

        return self.config_dict[section][option]

    def getboolean(self, section, option, fallback=None):
        """Get value of a givenoption in a given section."""
        if not self.has_section(section):
            raise
        if not self.has_option(section,option):
            if (fallback == None):
                raise
            else:
                return ((fallback in TRUE_ENCODINGS) or (fallback==1))
        
        return (self.config_dict[section][option].lower() in TRUE_ENCODINGS)

    def getint(self, section, option, fallback=None):
        """Get value of a givenoption in a given section."""
        if not self.has_section(section):
            raise
        if not self.has_option(section,option):
            if (fallback == None):
                raise
            else:
                return fallback
        return int(self.config_dict[section][option])
 
    def getfloat(self, section, option, fallback=None):
        """Get value of a givenoption in a given section."""
        if not self.has_section(section):
            raise
        if not self.has_option(section,option):
            if (fallback == None):
                raise
            else:
                return fallback
        return float(self.config_dict[section][option])

    def has_option(self, section, option):
        """Check for the existence of a given option in a given section."""
        if not section in self.config_dict:
            raise
        if option in self.config_dict[section].keys():
            return True
        else:
            return False

    def write(self, filename = None, fp = None):
        """Write an .ini-format representation of the configuration state."""
        if not fp and not filename:
            print("ERROR : no filename and no fp")
            raise
        elif not fp and filename:
            fp = open(filename,'w')

        for section in self.config_dict.keys():
            fp.write('[%s]\n' % section)
            for option in self.config_dict[section].keys():
                fp.write('\n%s =' % option)
                values = self.config_dict[section][option]
                if type(values) == type([]):
                    fp.write('\n    ')
                    values = '\n    '.join(values)
                else:
                    fp.write(' ')
                fp.write(values)
                fp.write('\n')
            fp.write('\n')


    def remove_option(self, section, option):
        """Remove an option."""
        if not self.has_section(section) \
                or not self.has_option(section,option):
                    raise
        del self.config_dict[section][option]

    def remove_section(self, section):
        """Remove a file section."""
        if not self.has_section(section):
            raise
        del self.config_dict[section]

import re
import pandas as pd
import os


class format_log:    # this part of code is from LogPai https://github.com/LogPai

    def __init__(self, log_format, indir='./'):
        self.path = indir
        self.logName = None
        self.df_log = None
        self.log_format = log_format

    def format(self, logName, max_lines=None):


        self.logName=logName

        self.load_data(max_lines=max_lines)

        return self.df_log


    def generate_logformat_regex(self, logformat):
        """ Function to generate regular expression to split logs messages
        """
        headers = []
        splitters = re.split(r'(<[^<>]+>)', logformat)
        regex = ''
        for k in range(len(splitters)):
            if k % 2 == 0:
                splitter = re.sub(' +', '\\\s+', splitters[k])
                regex += splitter
            else:
                header = splitters[k].strip('<').strip('>')
                regex += '(?P<%s>.*?)' % header
                headers.append(header)
        regex = re.compile('^' + regex + '$')
        return headers, regex
    def log_to_dataframe(self, log_file, regex, headers, logformat, max_lines=None):
        """ Function to transform logs file to dataframe
        """
        log_messages = []
        linecount = 0
        with open(log_file, 'r', encoding='UTF-8') as fin:
            for line in fin.readlines():
                try:
                    match = regex.search(line.strip())
                    message = [match.group(header) for header in headers]
                    log_messages.append(message)
                    linecount += 1
                except Exception as e:
                    pass
                if max_lines and linecount >= max_lines:
                    break
        logdf = pd.DataFrame(log_messages, columns=headers)
        logdf.insert(0, 'LineId', None)
        logdf['LineId'] = [i + 1 for i in range(linecount)]
        return logdf

    def load_data(self, max_lines=None):
        headers, regex = self.generate_logformat_regex(self.log_format)
        self.df_log = self.log_to_dataframe(os.path.join(self.path, self.logName), regex, headers, self.log_format, max_lines=max_lines)

def read_log_file(file_path):
    log_entries = []
    with open(file_path, 'r', encoding='UTF-8') as file:
        for line in file:
            stripped_line = line.strip()
            if stripped_line:  # 检查是否为空行
                # 去除前后反引号
                cleaned_line = stripped_line.strip('`')
                log_entries.append(cleaned_line)
    return log_entries


if __name__ == "__main__":
    print("Hello")
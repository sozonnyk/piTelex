import ftplib
import txCode

LINE_WIDTH = 69

def wrap_tty_line(line: str, width: int = LINE_WIDTH) -> list:
    lines = []
    line = txCode.BaudotMurrayCode.translate(line).strip()

    while len(line) > width:
        split_at = line.rfind(" ", 0, width + 1)
        if split_at <= 0:
            split_at = width
        lines.append(line[:split_at].strip())
        line = line[split_at:].strip()

    lines.append(line)
    return lines

class Weather():
    def __init__(self):
        self.server = "ftp.bom.gov.au"
        self.path = 'anon/gen/fwo/'
        self.filename = 'IDN10064.txt'
        self.content = b""
        self.today = ""
        self.tomorrow = ""

    def content_retr(self, buf: bytes):
        self.content += buf

    def get(self):
        ftp = ftplib.FTP(self.server)
        ftp.login()
        ftp.cwd(self.path)
        ftp.retrbinary("RETR " + self.filename, self.content_retr)
        ftp.quit()

    def forecast(self):
        self.get()
        content = self.content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        delim = "\n\n"
        split_forecast = content.split(delim)
        forecast_idxs = [i for i, x in enumerate(split_forecast) if "Forecast" in x]

        result_list = []
        result_list += split_forecast[forecast_idxs[1]:forecast_idxs[2]]
        result_list += split_forecast[forecast_idxs[2]:forecast_idxs[3]]

        trimmed_result_list=[]
        for line in result_list:
            trimmed_result_list += [x.strip() for x in line.splitlines()]

        # Wrap after teletype translation so expanded replacement text counts.
        shortened_result_list=[]
        for line in trimmed_result_list:
            shortened_result_list += wrap_tty_line(line)

        return "\r\n".join(shortened_result_list)

#print(Weather().forecast())

import re
import ftplib

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
        content = self.content.decode("utf-8")
        delim = "\n\n"
        split_forecast = content.split(delim)
        forecast_idxs = [i for i, x in enumerate(split_forecast) if "Forecast" in x]

        result_list = []
        result_list += split_forecast[forecast_idxs[1]:forecast_idxs[2]]
        result_list += split_forecast[forecast_idxs[2]:forecast_idxs[3]]

        trimmed_result_list=[]
        for line in result_list:
            trimmed_result_list += [x.strip() for x in line.split("\r\n")]

        # 69 characters per line
        shortened_result_list=[]
        for line in trimmed_result_list:
            shortened_result_list += [line[i:i+68] for i in range(0, len(line), 68)]

        return "\r\n".join(shortened_result_list)

#print(Weather().forecast())
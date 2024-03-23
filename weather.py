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



    def print(self):
        self.get()
        content = self.content.decode("utf-8")
        delim = "\n\n"
        split_forecast = content.split(delim)
        forecast_idxs = [i for i, x in enumerate(split_forecast) if "Forecast" in x]

        print("\n".join(split_forecast[forecast_idxs[1]:forecast_idxs[2]]))
        print("\n")
        print("\n".join(split_forecast[forecast_idxs[2]:forecast_idxs[3]]))


w = Weather()
w.print()
import datetime
import os
import glob
import numpy as np
from pathlib import Path

class FileWriter:
    def __init__(self, path_to_file="../data/"):
        self._path = path_to_file
        self.f = None

    def start_file(self):
        try:
            os.makedirs(self._path)
        except:
            pass

        filename = str(datetime.datetime.today().strftime("%Y-%m-%d_%H_%M_%S")) + ".csv"
        path_file = Path(self._path) / filename
        self.f = open(path_file, 'ab+')

    def append_data(self, data):
        np.savetxt(self.f, data, delimiter=',', newline=',')

    def finish_file(self):
        # remove last comma and close file (maybe comma will be need for target label in the future)
        self.f.seek(-1, os.SEEK_END)
        self.f.truncate()
        self.f.close()

    def delete_latest_file(self):
        files = sorted(glob.glob(self._path + "*.csv"))
        if len(files) != 0:
            os.remove(files[-1])
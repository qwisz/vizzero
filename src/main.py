import json
import sys
import numpy as np
import time
import zmq
from PySide2.QtWidgets import QMainWindow, QApplication, QSplitter, QWidget, QTabWidget, QVBoxLayout, QPushButton
from PySide2.QtCore import Qt

import draw
import threading
import FileWriter
import handsim
import subprocess

N_PASSES = 1 # number of dropped frames for 1 drawing
DRAW_BUFFER_SIZE = 25 # it's 20 fps if n_passes = 1
WRITE_BUFFER_SIZE = 100
RECORDING_DURATION = 5. # seconds

class Interface:
    def __init__(self, verbose=False):
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PAIR)
        self._socket.connect("tcp://localhost:3004")

        self.verbose = verbose

        if self.verbose:
            print ("Client Ready!")

        # Send a quick message to tell node process we are up and running
        self.send(json.dumps({
            'action': 'started',
            'command': 'status',
            'message': time.time() * 1000.0
        }))

    def send(self, msg):
        """
        Sends a message to TCP server
        :param msg: str
            A string to send to node TCP server, could be a JSON dumps...
        :return: None
        """
        if self.verbose:
            print('<- out ' + msg)
        self._socket.send(msg.encode('ascii'))
        return

    def recv(self):
        """
        Checks the ZeroMQ for data
        :return: str
            String of data
        """
        return self._socket.recv()

    def close(self):
        """
        Closes the zmq context
        """
        self._backend.close()
        self._context.term()


class RingBuffer(np.ndarray):
    """A multidimensional ring buffer."""

    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return

    def __array_wrap__(self, out_arr, context=None):
        return np.ndarray.__array_wrap__(self, out_arr, context)

    def append(self, x):
        """Adds element x to the ring buffer."""
        x = np.asarray(x)
        self[:, :-1] = self[:, 1:]
        self[:, -1] = x


class DataThread(threading.Thread):

    data_running = True

    def __init__(self, canvas, window):
        super(DataThread, self).__init__()
        self.canvas = canvas
        self.window = window
        self.file_writer = FileWriter.FileWriter()

    def stop_data(self):
        self.data_running = False

    def run(self):
        nb_chan = 8
        verbose = True
        # Create a new python interface.
        interface = Interface(verbose=verbose)
        # Signal buffer
        signal = RingBuffer(np.zeros((nb_chan + 1, 2500)))

        draw_buffer = np.zeros((DRAW_BUFFER_SIZE, 8))
        write_buffer = np.zeros((WRITE_BUFFER_SIZE, 8)) # (WRITE_BUFFER_SIZE, 8 + 1) for target label
        i_pass = N_PASSES
        i_draw = 0 # draw_buffer's index
        i_write = 0 # write_buffer's index
        db_len = 0
        self.file_writer.start_file()
        start_time = None
        is_write = True

        try:
            while self.data_running:
                msg = interface.recv()
                try:
                    dicty = json.loads(msg)
                    action = dicty.get('action')
                    command = dicty.get('command')
                    message = dicty.get('message')
                    if start_time is None:
                        start_time = time.time()

                    if command == 'sample':
                        if action == 'process':
                            # Do sample processing here
                            try:
                                if type(message) is not dict:
                                    print("sample is not a dict", message)
                                    raise ValueError
                                # Get keys of sample
                                data = np.zeros(nb_chan + 1)

                                data[:-1] = message.get('channelData')

                                if is_write:
                                    write_buffer[i_write] = data[:-1]
                                    i_write += 1

                                    if i_write == WRITE_BUFFER_SIZE:
                                        self.file_writer.append_data(write_buffer)
                                        i_write = 0
                                        cur_time = time.time()
                                        if cur_time - start_time >= RECORDING_DURATION:
                                            self.file_writer.finish_file()
                                            is_write = False

                                if i_pass < N_PASSES:
                                    i_pass += 1
                                    continue
                                else:
                                    draw_buffer[db_len] = data[:-1]
                                    db_len += 1

                                    if db_len == DRAW_BUFFER_SIZE:
                                        self.canvas.feed_data(draw_buffer, DRAW_BUFFER_SIZE)
                                        db_len = 0

                                    i_pass = 0


                                # uniform
                                # if i_pass < N_PASSES:
                                #     i_pass += 1
                                #     continue
                                # else:
                                #     i_draw = 0
                                #
                                # if i_draw < N_PASSES:
                                #     draw_buffer[db_len] = data[:-1]
                                #     db_len += 1
                                #     i_draw += 1
                                #
                                #     if db_len == DRAW_BUFFER_SIZE:
                                #         self.canvas.feed_data(draw_buffer, DRAW_BUFFER_SIZE)
                                #         db_len = 0
                                # else:
                                #     i_pass = 0
                                # uniform


                                ### not mine ###
                                # data[-1] = message.get('timeStamp')

                                # Add data to end of ring buffer
                                # signal.append(data)
                                # self.canvas.feed_data(data)
                                print(message.get('sampleNumber'))
                                #################

                            except ValueError as e:
                                print(e)
                    elif command == 'status':
                        if action == 'active':
                            interface.send(json.dumps({
                                'action': 'alive',
                                'command': 'status',
                                'message': time.time() * 1000.0
                            }))
                except KeyboardInterrupt:
                    print("W: interrupt received, stopping")
                    print("Python ZMQ Link Clean Up")
                    interface.close()
                    raise ValueError("Peace")
        except BaseException as e:
            print(e)
        finally:
            self.file_writer.finish_file()

        interface.close()


class Tabs(QTabWidget):
    def __init__(self):
        super(Tabs, self).__init__()
        self.all_tabs = []
        self.handsim_view = handsim.create_hand_sim_widget()
        self.build_widgets()

    def build_widgets(self):
        self.all_tabs.append(self.handsim_view)
        self.addTab(self.all_tabs[0], 'Sim')
        self.all_tabs.append(QWidget())
        self.addTab(self.all_tabs[1], 'Fixed')
        self.all_tabs.append(QWidget())
        self.addTab(self.all_tabs[2], 'Keyboard')
        self.all_tabs.append(QWidget())
        self.addTab(self.all_tabs[3], 'Сontinuous')


#    def create_tab(self):
#        self.all_tabs.append(QtWidgets.QWidget())
#        self.addTab(self.all_tabs[len(self.all_tabs) - 1],
#                    'Tab {}'.format(len(self.all_tabs)))

    def close_tab(self, index):
        widget = self.widget(index)
        widget.deleteLater()
        self.removeTab(index)


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle('vizzero')

        vbox = QVBoxLayout(self)
        window = QWidget()
        window.setLayout(vbox)

        self.myo_canvas = draw.Canvas()
        self.myo_canvas.native.setParent(window)

        self.btnStart = QPushButton("Start data")
        self.btnStop = QPushButton("Stop data")
        vbox.addWidget(self.btnStart)
        vbox.addWidget(self.btnStop)
        vbox.addWidget(self.myo_canvas.native)

        self.btnStart.clicked.connect(self.on_start)
        self.btnStop.clicked.connect(self.on_stop)
        self.node_proc = None

        self.tabs = Tabs()
        self.handsim_view = self.tabs.handsim_view
        splitter1 = QSplitter(Qt.Horizontal)
        splitter1.addWidget(self.tabs)
        splitter1.addWidget(window)
        splitter1.setSizes([70, 30])

        self.setCentralWidget(splitter1)

    def on_start(self):
        self.node_proc = subprocess.Popen(["node", "../index.js"])

    def on_stop(self):
        if None is not self.node_proc:
            self.node_proc.kill()
        else:
            print("no data process found")


def main(argv):
    appQt = QApplication(sys.argv)
    window = MainWindow()
    window.myo_canvas.thread = DataThread(window.myo_canvas, window)
    window.myo_canvas.thread.start()
    window.setWindowTitle("Starting and stopping the process")
    window.show()
    ret = appQt.exec_()
    window.myo_canvas.thread.stop_data()
    print("quitting")
    window.myo_canvas.thread.join()
    #doesn't work. close files? release resources?
    sys.exit(ret)

if __name__ == '__main__':
    main(sys.argv[1:])

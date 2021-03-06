from PySide2.QtCore import QUrl, QDir
from PySide2.QtWebEngineWidgets import QWebEngineView
import sys
from HandSimServer import *

sys.path.append('./handsim')


def create_hand_sim_widget(parent=None):
    sim_in_new_thread()
    view = QWebEngineView(parent)
    view.setUrl(QUrl.fromLocalFile(QDir.currentPath() + "/../handjs/index.html"))
    return view


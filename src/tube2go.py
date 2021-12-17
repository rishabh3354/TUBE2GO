import json
import os
import shutil
import sys
import time
import webbrowser
from copy import deepcopy
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QUrl, QSettings, QStringListModel, QProcess
from PyQt5.QtGui import QDesktopServices, QIcon, QPixmap, QFont
from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox, QFileDialog, QStyle, QCheckBox, QLineEdit, \
    QCompleter, QAbstractItemView, QTableWidgetItem, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView
from account_threads import SaveLocalInToken, RefreshButtonThread, PytubeStatusThread, SyncAccountIdWithDb
from accounts import get_user_data_from_local, days_left, ApplicationStartupTask, check_for_local_token
from helper import process_html_data, check_internet_connection, check_default_location, process_html_data_playlist, \
    get_thumbnail_path_from_local, safe_string, get_local_download_data, save_after_delete, get_stream_quality, \
    get_downloaded_data_filter
from home_threads import HomeThreads, PixMapLoadingThread, CompleterThread, SearchThreads
from country_names_all import COUNTRIES, SERVER_REVERSE, COUNTRIES_REVERSE, SORT_BY_REVERSE, \
    EXPLORE_REVERSE, EXPLORE, SORT_BY, SERVER, STREAM_QUALITY_DICT, STREAM_QUALITY_REVERSE_DICT, AFTER_PLAYBACK, \
    AFTER_PLAYBACK_REVERSE
from system_monitor import RamThread, NetSpeedThread, CpuThread, DummyDataThread
from utils import get_time_format, human_format, set_all_countries_icons, set_server_icons
from youtube_script import get_initial_download_dir
from template import set_style_for_pause_play_button
from ui_main_trial import Ui_MainWindow
from youtube_threads import ProcessYtV, DownloadVideo, ProcessYtVPlayList, GetPlaylistVideos, \
    DownloadVideoPlayList, FileSizeThread, FileSizeThreadSingleVideo, PlayThread, PlayPlaylistThread
from helper import FREQUENCY_MAPPER
from settings import YouTubeSettings, UrlDialog

PRODUCT_NAME = "TUBE2GO"
THEME_PATH = '/snap/tube2go/current/'

PLAYLIST_SIZE_CACHE = {}
HOME_CACHE = {}


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.youtube_setting_ui = YouTubeSettings()
        self.url_dialog_ui = UrlDialog()
        self.theme = open(THEME_PATH + 'dark.qss', 'r').read()
        self.setStyleSheet(self.theme)
        self.youtube_setting_ui.setStyleSheet(self.theme)
        self.url_dialog_ui.setStyleSheet(self.theme)
        self.setWindowTitle("Tube2Go")
        self.settings = QSettings("warlordsoft", "tube2go")
        self.tip_count = -1
        self.pytube_status = True
        self.ui.purchase_details.setEnabled(False)

        self.is_plan_active = True
        self.delete_source_file = True
        self.one_time_congratulate = True
        self.back_track_index = 0

        #  init net speed settings
        self.system_frequency = 1
        self.speed_unit = "MB/s | KB/s | B/s"
        self.temp_unit = "°C  (Celsius)"
        self.default_frequency()

        #  youtube settings ============================================================================================
        self.country = "US"
        self.explore = "trending"
        self.sort_by = "relevance"
        self.home_button_item = 20
        self.stream_quality = 2
        self.default_server = "http://invidio.xamh.de"
        self.after_playback_action = "loop_play"
        self.mpv_arguments = []
        self.Default_loc = get_initial_download_dir()
        self.Default_loc_playlist = get_initial_download_dir()
        self.youtube_setting_ui.ui.download_path_edit_2.setText(self.Default_loc + "/TUBE2GO")
        self.youtube_setting_ui.ui.download_path_edit_playlist.setText(self.Default_loc_playlist + "/TUBE2GO")
        self.youtube_setting_ui.ui.country.addItems(list(COUNTRIES.keys()))
        set_all_countries_icons(self)
        self.youtube_setting_ui.ui.country.setCurrentIndex(83)
        self.youtube_setting_ui.ui.server.addItems(list(SERVER.keys()))
        set_server_icons(self)
        self.youtube_setting_ui.ui.info_server.clicked.connect(self.server_info_popup)
        self.youtube_setting_ui.ui.no_of_videos.valueChanged.connect(self.change_no_of_home_item)
        self.youtube_setting_ui.ui.stream_quality.currentIndexChanged.connect(self.change_stream_quality)
        self.youtube_setting_ui.ui.download_path_button_2.clicked.connect(self.open_download_path)
        self.youtube_setting_ui.ui.close.clicked.connect(self.click_ok_button)
        self.youtube_setting_ui.ui.reset_default.clicked.connect(self.yt_settings_defaults)
        self.youtube_setting_ui.ui.country.currentIndexChanged.connect(self.select_country)
        self.youtube_setting_ui.ui.explore.currentIndexChanged.connect(self.select_explore)
        self.youtube_setting_ui.ui.sort_by.currentIndexChanged.connect(self.select_sort_by)
        self.youtube_setting_ui.ui.server.currentIndexChanged.connect(self.save_default_server)
        self.youtube_setting_ui.ui.after_playback.currentIndexChanged.connect(self.select_after_playback_action)

        # home widget ==================================================================================================
        self.ui.tableWidget.verticalHeader().setVisible(False)
        self.ui.tableWidget.horizontalHeader().setVisible(False)
        self.ui.home_progress_bar.setFixedHeight(2)
        self.ui.video_progressBar.setFixedHeight(2)
        self.ui.playlist_progressBar.setFixedHeight(2)
        self.ui.tableWidget.verticalHeader().setDefaultSectionSize(30)
        self.main_table_pointer = 140
        self.table_view_default_setting()
        self.thumbnail_list = []
        self.title_list = []
        self.pixmap_list = []
        self.videoid_list = []
        self.pixmap_cache = {}
        self.play_url = ""
        self.download_url = ""
        self.ui.home_button.clicked.connect(self.get_home_page)
        self.c_database = []
        self.page = 1
        self.hide_show_video_initial_banner(show=False)
        self.hide_show_playlist_initial_banner(show=False)
        self.ui.progress_bar.setFixedHeight(17)
        self.ui.account_progress_bar.setFixedHeight(2)
        self.ui.progress_bar.setFont(QFont('Ubuntu', 11))
        self.ui.stackedWidget.setCurrentIndex(0)
        self.completer = QCompleter()
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.completer.setMaxVisibleItems(20)
        self.ui.youtube_search.setCompleter(self.completer)
        self.completer.popup().setStyleSheet(self.theme)
        self.completer.activated.connect(self.get_search_suggestion_text, QtCore.Qt.QueuedConnection)
        self.ui.yt_settings.clicked.connect(self.open_yt_setting_page)
        self.ui.next_page.clicked.connect(self.next_page)
        self.ui.prev_page.clicked.connect(self.prev_page)
        self.ui.page_no.setVisible(False)
        self.ui.tableWidget.itemDoubleClicked.connect(self.select_item_on_double_clicked)
        self.ui.tableWidget.setFocusPolicy(QtCore.Qt.NoFocus)
        self.ui.copy_id.clicked.connect(
            lambda x: QApplication.clipboard().setText(self.ui.lineEdit_account_id_2.text()))
        self.ui.info_suggestion.clicked.connect(self.suggestion_info_popup)
        self.info_suggestion_count = 0
        # download tab default item to show
        self.speed = "0.0"
        self.unit = "B/s"

        # Video functionality ==================================================
        # init
        self.stop = False
        self.hide_show_play_pause_button(hide=True)
        self.pause = False
        self.counter = 0

        self.load_settings()
        self.show()
        self.get_home_page(True)

        # scroll zoom functionality:-
        self._zoom = 0
        self._empty = False
        self._scene = QGraphicsScene(self)
        self._photo = QGraphicsPixmapItem()
        self._scene.addItem(self._photo)
        self.ui.graphicsView_video.setScene(self._scene)
        self.ui.graphicsView_video.scale(2, 2)
        self.factor = 1
        self.setAcceptDrops(True)
        self.ui.graphicsView_video.setVisible(False)
        self.ui.graphicsView_playlist.setVisible(False)
        self.ui.graphicsView_playlist.setScene(self._scene)
        self.ui.graphicsView_playlist.scale(2, 2)

        # signal and slots =====

        # pause delete
        self.ui.pause_button.clicked.connect(self.pause_button_pressed)
        self.ui.delete_button.clicked.connect(self.trigger_delete_action)
        # miscellaneous
        self.ui.youtube_search.textEdited.connect(self.save_completer)
        self.url_dialog_ui.ui.process.clicked.connect(self.decide_video_or_playlist)
        self.url_dialog_ui.ui.paste_button.clicked.connect(self.paste_button_clicked)
        self.ui.search.clicked.connect(self.start_search_youtube)
        self.ui.download_button_2.clicked.connect(self.download_action)
        self.ui.select_format_obj_2.currentTextChanged.connect(self.check_for_audio_only)
        self.ui.select_quality_obj_2.currentIndexChanged.connect(self.show_file_size)
        self.ui.select_format_obj_2.currentIndexChanged.connect(self.show_file_size)
        self.ui.select_fps_obj_2.currentIndexChanged.connect(self.show_file_size)
        self.ui.play_from_videos.clicked.connect(self.play_video_from_videos_tab)

        # playlist functionality ======================================================

        # init
        self.play_list_counter = 1
        self.total_obj = list()
        self.playlist_urls = []

        # signal and slots
        self.ui.select_videos_playlist_2.currentIndexChanged.connect(self.show_video_thumbnail)
        self.ui.download_button_playlist_2.clicked.connect(self.download_action_playlist)
        self.ui.select_type_playlist_2.currentIndexChanged.connect(self.check_for_audio_only_playlist)
        self.ui.select_quality_playlist_2.currentIndexChanged.connect(self.check_for_audio_only_playlist)
        self.youtube_setting_ui.ui.download_path_button_playlist.clicked.connect(self.open_download_path_playlist)
        self.ui.play_from_playlist.clicked.connect(self.play_playlist)

        # Downloads functionality ======================================================

        # init
        self.downloaded_file_filter = "all_files"
        self.ui.filter_by.currentIndexChanged.connect(self.set_file_downloaded_filter)
        self.download_search_map_list = []

        # signal and slots
        self.ui.open_videos.clicked.connect(self.show_downloads_folder)
        self.ui.play_video.clicked.connect(self.play_videos_from_downloads)
        self.ui.play_video_mpv.clicked.connect(self.play_videos_mpv_from_downloads)
        self.ui.details_video.clicked.connect(self.details_video_from_downloads)
        self.ui.delete_videos.clicked.connect(self.delete_video_from_downloads)
        self.ui.listWidget.itemDoubleClicked.connect(self.play_videos_mpv_from_downloads)
        self.ui.search_videos.textChanged.connect(self.search_videos)
        self.ui.search_videos.cursorPositionChanged.connect(self.clear_search_bar_on_edit)
        self.ui.clear_history.clicked.connect(self.clear_all_history)

        # Accounts/About functionality ======================================================

        # init
        ApplicationStartupTask(PRODUCT_NAME).create_free_trial_offline()
        self.ui.error_message.clear()
        self.ui.error_message.setStyleSheet("color:red;")
        self.my_plan()
        self.check_pytube_issue()
        self.sync_account_id_with_warlord_soft()

        # signal and slots
        self.ui.warlordsoft_button.clicked.connect(self.redirect_to_warlordsoft)
        self.ui.donate_button.clicked.connect(self.redirect_to_paypal_donation)
        self.ui.rate_button.clicked.connect(self.redirect_to_rate_snapstore)
        self.ui.feedback_button.clicked.connect(self.redirect_to_feedback_button)
        self.ui.purchase_licence_2.clicked.connect(self.purchase_licence_2)
        self.ui.refresh_account_2.clicked.connect(self.refresh_account_2)
        self.ui.ge_more_apps.clicked.connect(self.ge_more_apps)
        self.ui.purchase_details.clicked.connect(self.purchase_details_after_payment)

        # net speed settings
        self.ui.horizontalSlider_freq.valueChanged.connect(self.change_frequency_net)
        self.ui.comboBox_speed_unit.currentIndexChanged.connect(self.change_net_speed_unit)
        self.ui.comboBox_cpu_temp.currentIndexChanged.connect(self.change_temp_unit)

        # Select theme icon ========================================================================
        self.set_icon_on_line_edit()

        # stack button
        self.ui.stack_video.clicked.connect(self.video_page)
        self.ui.stack_playlist.clicked.connect(self.playlist_page)
        self.ui.stack_downloads.clicked.connect(self.show_downloads_page)
        self.ui.stack_net_speed.clicked.connect(self.show_net_speed)
        self.ui.stack_themes.clicked.connect(self.home_page)
        self.ui.stack_accounts.clicked.connect(self.account_page)
        self.ui.stack_about.clicked.connect(self.about_page)
        self.ui.dock_home.clicked.connect(self.open_menu)
        self.ui.stack_paste_url.clicked.connect(self.open_url_dialog)
        self.ui.dock_back_home.clicked.connect(self.back_page)
        # dock button
        self.ui.dock_downloads.clicked.connect(self.show_downloads_page)
        self.ui.dock_paste_url.clicked.connect(self.open_url_dialog)
        self.ui.dock_yt_home.clicked.connect(self.home_page)
        self.ui.dock_account.clicked.connect(self.account_page)
        self.ui.dock_speed.clicked.connect(self.show_net_speed)

    def open_menu(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.stackedWidget.setCurrentIndex(7)
        self.ui.dock_home.setEnabled(False)
        self.ui.dock_back_home.setEnabled(True)

    def back_page(self):
        self.ui.stackedWidget.setCurrentIndex(self.back_track_index)
        if self.back_track_index == 7:
            self.ui.dock_home.setEnabled(False)
        else:
            self.ui.dock_home.setEnabled(True)

    def video_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.stackedWidget.setCurrentIndex(1)
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)

    def playlist_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.stackedWidget.setCurrentIndex(2)
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)

    def account_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.stackedWidget.setCurrentIndex(5)
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)
        try:
            account_id = str(self.ui.lineEdit_account_id_2.text())
            if account_id not in ["", None]:
                self.ui.error_message_2.setText(
                    f'<html><head/><body><p align="center"><span style=" color:#4e9a06;">If you have changed your PC or lost your account, </span><a href="https://warlordsoftwares.in/contact_us/?account_id={account_id}&application={PRODUCT_NAME}"><span style=" text-decoration: underline; color:#ef2929;">@Contact us</span></a><span style=" color:#4e9a06;"> to restore.</span></p></body></html>')
        except Exception as e:
            print(e)
            self.ui.error_message_2.setText(
                '<html><head/><body><p align="center"><span style=" color:#4e9a06;">If you have changed your PC or lost your account, </span><a href="https://warlordsoftwares.in/contact_us/"><span style=" text-decoration: underline; color:#ef2929;">@Contact us</span></a><span style=" color:#4e9a06;"> to restore.</span></p></body></html>')

    def about_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.stackedWidget.setCurrentIndex(6)
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)

    def show_downloads_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)
        self.ui.stackedWidget.setCurrentIndex(3)
        self.get_user_download_data()

    def home_page(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)
        self.ui.stackedWidget.setCurrentIndex(0)

    def show_net_speed(self):
        if self.back_track_index != self.ui.stackedWidget.currentIndex():
            self.back_track_index = self.ui.stackedWidget.currentIndex()
        self.ui.dock_back_home.setEnabled(True)
        self.ui.dock_home.setEnabled(True)
        self.ui.stackedWidget.setCurrentIndex(4)
        try:
            dummy_data_thread = self.dummy_data_thread.isRunning()
        except Exception:
            dummy_data_thread = False
        try:
            cpu_thread = self.cpu_thread.isRunning()
        except Exception:
            cpu_thread = False
        try:
            ram_thread = self.ram_thread.isRunning()
        except Exception:
            ram_thread = False
        try:
            net_speed_thread = self.net_speed_thread.isRunning()
        except Exception:
            net_speed_thread = False
        if not dummy_data_thread:
            self.load_annimation_data()
        if not cpu_thread:
            self.start_cpu_thread()
        if not ram_thread:
            self.start_ram_thread()
        if not net_speed_thread:
            self.start_net_speed_thread()

    def mousePressEvent(self, event):
        self.dragPos = event.globalPos()

    # graphic view

    def setPhoto(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.ui.graphicsView_video.setDragMode(QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
        else:
            self._empty = True
            self.ui.graphicsView_video.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())
        self.fitInView()

    def setPhoto_playlist(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.ui.graphicsView_playlist.setDragMode(QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
        else:
            self._empty = True
            self.ui.graphicsView_playlist.setDragMode(QGraphicsView.NoDrag)
            self._photo.setPixmap(QPixmap())
        self.fitInView_playlist()

    def fitInView(self, scale=True):
        try:
            rect = QtCore.QRectF(self._photo.pixmap().rect())
            if not rect.isNull():
                self.ui.graphicsView_video.setSceneRect(rect)
                if self.hasPhoto():
                    unity = self.ui.graphicsView_video.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                    self.ui.graphicsView_video.scale(1 / unity.width(), 1 / unity.height())
                    viewrect = self.ui.graphicsView_video.viewport().rect()
                    scenerect = self.ui.graphicsView_video.transform().mapRect(rect)
                    factor = min(viewrect.width() / scenerect.width(),
                                 viewrect.height() / scenerect.height())
                    self.ui.graphicsView_video.scale(factor, factor)
                self._zoom = 0
        except Exception as e:
            pass

    def fitInView_playlist(self, scale=True):
        try:
            rect = QtCore.QRectF(self._photo.pixmap().rect())
            if not rect.isNull():
                self.ui.graphicsView_playlist.setSceneRect(rect)
                if self.hasPhoto():
                    unity = self.ui.graphicsView_playlist.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
                    self.ui.graphicsView_playlist.scale(1 / unity.width(), 1 / unity.height())
                    viewrect = self.ui.graphicsView_playlist.viewport().rect()
                    scenerect = self.ui.graphicsView_playlist.transform().mapRect(rect)
                    factor = min(viewrect.width() / scenerect.width(),
                                 viewrect.height() / scenerect.height())
                    self.ui.graphicsView_playlist.scale(factor, factor)
                self._zoom = 0
        except Exception as e:
            pass

    def hasPhoto(self):
        return not self._empty

    """
        Youtube settings ===============================================================================================
        
    """

    def click_ok_button(self):
        self.youtube_setting_ui.hide()
        self.home_page()
        global HOME_CACHE
        HOME_CACHE = {}
        self.get_home_page()

    def change_no_of_home_item(self):
        self.home_button_item = self.youtube_setting_ui.ui.no_of_videos.value()

    def change_stream_quality(self):
        self.stream_quality = STREAM_QUALITY_DICT.get(self.youtube_setting_ui.ui.stream_quality.currentText(), 1)

    def save_default_server(self):
        self.default_server = SERVER.get(self.youtube_setting_ui.ui.server.currentText(), "http://invidio.xamh.de")

    def select_country(self):
        self.country = COUNTRIES.get(self.youtube_setting_ui.ui.country.currentText(), "US")

    def select_after_playback_action(self):
        self.after_playback_action = AFTER_PLAYBACK.get(self.youtube_setting_ui.ui.after_playback.currentText(),
                                                        "loop_play")

    def select_explore(self):
        self.explore = EXPLORE.get(self.youtube_setting_ui.ui.explore.currentText(), "trending")

    def select_sort_by(self):
        self.sort_by = EXPLORE.get(self.youtube_setting_ui.ui.sort_by.currentText(), "relevance")

    def yt_settings_defaults(self):
        self.msg = QMessageBox()
        self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setText("Are you sure want to reset to default settings?")
        yes_button = self.msg.addButton(QMessageBox.Yes)
        no_button = self.msg.addButton(QMessageBox.No)
        self.msg.exec_()
        if self.msg.clickedButton() == yes_button:
            #  yt setting defaults
            self.youtube_setting_ui.ui.country.setCurrentIndex(83)
            self.youtube_setting_ui.ui.explore.setCurrentIndex(0)
            self.youtube_setting_ui.ui.sort_by.setCurrentIndex(0)
            self.youtube_setting_ui.ui.server.setCurrentIndex(0)
            self.youtube_setting_ui.ui.no_of_videos.setValue(20)
            self.youtube_setting_ui.ui.stream_quality.setCurrentIndex(1)
            self.youtube_setting_ui.ui.after_playback.setCurrentIndex(0)
            self.country = "US"
            self.explore = "trending"
            self.sort_by = "relevance"
            self.default_server = "http://invidio.xamh.de"
            self.after_playback_action = "loop_play"
            self.Default_loc = get_initial_download_dir()
            self.Default_loc_playlist = get_initial_download_dir()
            self.youtube_setting_ui.ui.download_path_edit_2.setText(self.Default_loc + "/TUBE2GO")
            self.youtube_setting_ui.ui.download_path_edit_playlist.setText(self.Default_loc_playlist + "/TUBE2GO")
        if self.msg.clickedButton() == no_button:
            pass

    def open_yt_setting_page(self):
        self.youtube_setting_ui.show()
        self.youtube_setting_ui.raise_()
        self.youtube_setting_ui.activateWindow()

    """
            Home settings ===============================================================================================

    """

    def disable_enable_prev_next_page(self, show=True):
        if show:
            self.ui.next_page.setEnabled(True)
            self.ui.prev_page.setEnabled(True)
        else:
            self.ui.next_page.setEnabled(False)
            self.ui.prev_page.setEnabled(False)

    def hide_show_video_initial_banner(self, show=True):
        if show:
            for i in range(self.ui.gridLayout_5.count() - 1, -1, -1):
                items = self.ui.gridLayout_5.itemAt(i).widget()
                if items:
                    items.setVisible(True)
        else:
            for i in range(self.ui.gridLayout_5.count() - 1, -1, -1):
                items = self.ui.gridLayout_5.itemAt(i).widget()
                if items:
                    items.setVisible(False)

    def hide_show_playlist_initial_banner(self, show=True):
        if show:
            for i in range(self.ui.gridLayout_8.count() - 1, -1, -1):
                items = self.ui.gridLayout_8.itemAt(i).widget()
                if items:
                    items.setVisible(True)
        else:
            for i in range(self.ui.gridLayout_8.count() - 1, -1, -1):
                items = self.ui.gridLayout_8.itemAt(i).widget()
                if items:
                    items.setVisible(False)

    def hide_show_download_initial_banner(self, show=True):
        if show:
            self.ui.listWidget.setVisible(True)
            self.ui.label_26.setVisible(False)
        else:
            self.ui.listWidget.setVisible(False)
            self.ui.label_26.setVisible(True)

    def server_info_popup(self):
        title = "TUBE2GO SERVER INFO!"
        message = "Change the server name if you are facing any issues related to loading Home page/Search on youtube.\n\n" \
                  "Reason: It might be possible that TUBE2GO server is down for temporary basis on your country.\n\n" \
                  "Note: You can also switch to another server if home page loading speed is slow."
        self.popup_message(title, message)

    def suggestion_info_popup(self, message=None):
        self.msg = QMessageBox()
        self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setText("TUBE2GO Tips and Tricks!")
        if message:
            self.msg.setInformativeText(message)
        else:
            self.msg.setInformativeText(
                "Change your country from settings to improve search results and switch to regional home page.")
        close = self.msg.addButton(QMessageBox.Yes)
        next_tip = self.msg.addButton(QMessageBox.Yes)
        prev_tip = self.msg.addButton(QMessageBox.Yes)
        next_tip.setText('Next Tip')
        prev_tip.setText('Previous Tip')
        close.setText('Close')
        next_tip.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowRight)))
        prev_tip.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowLeft)))
        close.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_BrowserStop)))
        self.msg.exec_()
        message_list = [
            "For YouTube search suggestion, press space-bar key after keyword for accurate search suggestion.",
            "You can select YouTube stream play quality from the App settings.",
            "You can set number of video item by default on home screen from the App settings.",
            "Mpv stream player Keyboard shortcuts:\n\nQ :   Stop and Quit Player\nF :   "
            "Toggle Fullscreen\nP :  Pause / Playback\n9 and 0 :    Volume Control\nW and E :"
            "   ZoomIn/ZoomOut\nShift+A :    Screen Aspect Ratio\nArrow Keys :   Seek 5 seconds.",
            "Change TUBE2GO server from the App settings if you are facing server down issues in your country.",
            ]
        try:
            if self.msg.clickedButton() == next_tip:
                if self.tip_count <= 3:
                    self.tip_count += 1
                    self.suggestion_info_popup(message_list[self.tip_count])
                else:
                    self.tip_count = 0
                    self.suggestion_info_popup(message_list[self.tip_count])
            elif self.msg.clickedButton() == prev_tip:
                if self.tip_count >= 1:
                    self.tip_count -= 1
                    self.suggestion_info_popup(message_list[self.tip_count])
                else:
                    self.tip_count = 4
                    self.suggestion_info_popup(message_list[self.tip_count])
            elif self.msg.clickedButton() == close:
                pass
        except Exception as e:
            pass

    def keyPressEvent(self, qKeyEvent):
        if qKeyEvent.key() == QtCore.Qt.Key_Return:
            self.start_search_youtube()
        else:
            super().keyPressEvent(qKeyEvent)

    def open_url_dialog(self):
        self.url_dialog_ui.show()
        self.url_dialog_ui.raise_()
        self.url_dialog_ui.activateWindow()

    def select_item_on_double_clicked(self, item):
        video_id = self.videoid_list[item.row()]
        self.download_url = video_id
        self.play_video(video_id)

    def signal_for_row_button_table(self, row):
        self.video_url = self.videoid_list[int(str(row).split("-")[1])]
        if "v" in row:
            webbrowser.open(self.video_url)
        elif "d" in row:
            self.ytv_link_clicked(self.video_url)
        elif "w" in row:
            self.play_video(self.video_url)
        else:
            webbrowser.open(self.videoid_list[int(str(row).split("-")[1])])

    def play_video(self, stream_url):
        self.ui.home_progress_bar.setRange(0, 0)
        try:
            play_thread = self.play_thread.isRunning()
        except Exception as e:
            play_thread = False
        if not play_thread:
            self.play_thread = PlayThread(stream_url, self.pytube_status, self)
            self.play_thread.get_stream_url.connect(self.finish_getting_stream_url)
            self.play_thread.stream_url_error.connect(self.error_getting_stream_url)
            self.play_thread.start()

    def play_playlist(self):
        if self.playlist_urls:
            self.ui.playlist_progressBar.setRange(0, 0)
            try:
                play_playlist_thread = self.play_playlist_thread.isRunning()
            except Exception as e:
                play_playlist_thread = False

            if not play_playlist_thread:
                try:
                    if self.ui.select_videos_playlist_2.currentText() != "Select All":
                        stream_url = self.playlist_urls[self.ui.select_videos_playlist_2.currentIndex() - 1]
                    else:
                        stream_url = self.playlist_urls[0]
                except Exception as e:
                    print(e)
                    stream_url = self.self.playlist_urls[-1]

                if self.ui.select_type_playlist_2.currentText() == "AUDIO - MP3":
                    self.play_playlist_thread = PlayPlaylistThread(stream_url, self.pytube_status, True, self)
                else:
                    self.play_playlist_thread = PlayPlaylistThread(stream_url, self.pytube_status, False, self)

                self.play_playlist_thread.get_stream_url.connect(self.finish_getting_stream_url_playlist)
                self.play_playlist_thread.stream_url_error.connect(self.error_getting_stream_url_playlist)
                self.play_playlist_thread.start()
        else:
            self.popup_message(title="No YouTube playlist To Watch!",
                               message="Please add YouTube Playlist From The Home Tab.")

    def play_video_from_videos_tab(self):
        try:
            if self.ui.select_format_obj_2.currentText() != "Select Format":
                self.ui.video_progressBar.setRange(0, 0)
                if self.ui.select_format_obj_2.currentText() == "AUDIO - MP3":
                    stream = get_stream_quality(self.audio_stream_url, self.stream_quality, True)
                else:
                    stream = get_stream_quality(self.stream_url, self.stream_quality, False)
                self.process = QProcess()
                self.process.readyReadStandardOutput.connect(self.handle_stdout_from_videos)
                self.mpv_arguments = []
                if self.after_playback_action == "loop_play":
                    self.mpv_arguments.append("--loop")
                self.mpv_arguments.append("--force-window")
                self.mpv_arguments.append(stream)
                self.mpv_arguments.append("--title={0}".format(self.title))
                self.mpv_arguments.append("--gpu-context=x11")
                self.process.start("mpv", self.mpv_arguments)
            else:
                self.popup_message(title="No Audio/Video File To Play!",
                                   message="Please Select YouTube Video From The Home Tab.")
        except Exception as e:
            print(e)

    def finish_getting_stream_url(self, stream_url):
        try:
            mvp_thread = self.process.isRunning()
        except Exception as e:
            mvp_thread = False
        if not mvp_thread:
            try:
                stream = get_stream_quality(stream_url.get("stream_url"), self.stream_quality)
                self.process = QProcess()
                self.process.readyReadStandardOutput.connect(self.handle_stdout)
                self.mpv_arguments = []
                if self.after_playback_action == "loop_play":
                    self.mpv_arguments.append("--loop")
                self.mpv_arguments.append("--force-window")
                self.mpv_arguments.append(stream)
                self.mpv_arguments.append("--title={0}".format(stream_url.get("title")))
                self.mpv_arguments.append("--gpu-context=x11")
                self.process.start("mpv", self.mpv_arguments)
            except Exception as e:
                print(e)

    def finish_getting_stream_url_playlist(self, stream_url):
        try:
            mvp_thread = self.process.isRunning()
        except Exception as e:
            mvp_thread = False
        if not mvp_thread:
            try:
                if stream_url.get("audio_type"):
                    stream = get_stream_quality(stream_url.get("stream_url"), self.stream_quality, True)
                else:
                    stream = get_stream_quality(stream_url.get("stream_url"), self.stream_quality)

                self.process = QProcess()
                self.process.readyReadStandardOutput.connect(self.handle_stdout_playlist)
                self.mpv_arguments = []
                if self.after_playback_action == "loop_play":
                    self.mpv_arguments.append("--loop")
                self.mpv_arguments.append("--force-window")
                self.mpv_arguments.append(stream)
                self.mpv_arguments.append("--title={0}".format(stream_url.get("title")))
                self.mpv_arguments.append("--gpu-context=x11")
                self.process.start("mpv", self.mpv_arguments)
            except Exception as e:
                print(e)

    def error_getting_stream_url(self, error_string):
        self.ui.home_progress_bar.setRange(0, 1)
        self.popup_message(title="YouTube Video Could not Play!",
                           message="This Video Is Not Available Or Deleted Or Regionally Restricted From YouTube.")

    def error_getting_stream_url_playlist(self, error_string):
        self.ui.playlist_progressBar.setRange(0, 0)
        self.popup_message(title="YouTube Playlist Video Could not Play!",
                           message="This Playlist Video Is Not Available Or Deleted Or Regionally Restricted From YouTube.")

    def handle_stdout_from_videos(self):
        try:
            self.ui.video_progressBar.setRange(0, 1)
        except Exception as e:
            print(e)

    def handle_stdout(self):
        try:
            self.ui.home_progress_bar.setRange(0, 1)
        except Exception as e:
            print(e)

    def handle_stdout_playlist(self):
        try:
            self.ui.playlist_progressBar.setRange(0, 1)
        except Exception as e:
            print(e)

    def next_page(self):
        try:
            search_thread = self.search_thread.isRunning()
        except Exception as e:
            search_thread = False
        try:
            pixmap_thread = self.pixmap_load_thread.isRunning()
        except Exception as e:
            pixmap_thread = False

        if not search_thread and not pixmap_thread:
            self.page += 1
            self.ui.stackedWidget.setCurrentIndex(0)
            if len(HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(f"{self.page}", {}).get(
                    "content", [])) != 0:
                self.disable_enable_prev_next_page(show=True)
                if self.page == 1:
                    self.ui.prev_page.setEnabled(False)
                self.ui.home_progress_bar.setRange(0, 0)
                self.title_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("content", [])
                self.pixmap_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("pixmap_cache", [])
                self.videoid_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("videoid_list", [])
                self.thumbnail_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("thumbnail_list", [])
                self.process_images_into_table()
                self.ui.home_progress_bar.setRange(0, 1)
                self.set_page_no()
            else:
                self.disable_enable_prev_next_page(show=True)
                if self.page == 1:
                    self.ui.prev_page.setEnabled(False)
                self.start_search_youtube()
        else:
            self.popup_message(title="Process Already In Queue",
                               message="Please wait, Image thumbnails on this page are loading!")

    def prev_page(self):
        try:
            search_thread = self.search_thread.isRunning()
        except Exception as e:
            search_thread = False
        try:
            pixmap_thread = self.pixmap_load_thread.isRunning()
        except Exception as e:
            pixmap_thread = False

        if not search_thread and not pixmap_thread:
            if self.page > 1:
                self.page -= 1
                self.ui.stackedWidget.setCurrentIndex(0)

            if len(HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(f"{self.page}", {}).get(
                    "content", [])) != 0:
                self.disable_enable_prev_next_page(show=True)
                if self.page == 1:
                    self.ui.prev_page.setEnabled(False)

                self.ui.home_progress_bar.setRange(0, 0)
                self.title_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("content", [])
                self.pixmap_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("pixmap_cache", [])
                self.videoid_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("videoid_list", [])
                self.thumbnail_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("thumbnail_list", [])
                self.process_images_into_table()
                self.set_page_no()
                self.ui.home_progress_bar.setRange(0, 1)
            else:
                self.disable_enable_prev_next_page(show=True)
                if self.page == 1:
                    self.ui.prev_page.setEnabled(False)
                self.start_search_youtube()
        else:
            self.popup_message(title="Process Already In Queue",
                               message="Please wait, Image thumbnails on this page are loading!")

    def get_search_suggestion_text(self):
        try:
            self.ui.youtube_search.setText(str(str(self.ui.youtube_search.text()).split("🔍  ")[1]))
            self.start_search_youtube()
        except Exception as e:
            print(e)
            pass

    def set_page_no(self):
        self.ui.page_no.setVisible(True)
        self.ui.page_no.setText(f"Page {self.page}")

    def start_search_youtube(self):
        query = self.ui.youtube_search.text()
        if len(HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {})) == 0:
            self.page = 1
        try:
            search_thread = self.search_thread.isRunning()
        except Exception as e:
            search_thread = False
        try:
            pixmap_thread = self.pixmap_load_thread.isRunning()
        except Exception as e:
            pixmap_thread = False

        if not search_thread and not pixmap_thread:
            if len(HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(f"{self.page}", {}).get(
                    "content", [])) != 0:
                self.disable_enable_prev_next_page(show=True)
                self.page = 1
                if self.page == 1:
                    self.ui.prev_page.setEnabled(False)

                self.ui.home_progress_bar.setRange(0, 0)
                self.title_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("content", [])
                self.pixmap_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("pixmap_cache", [])
                self.videoid_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("videoid_list", [])
                self.thumbnail_list = HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {}).get(
                    f"{self.page}", {}).get("thumbnail_list", [])
                self.process_images_into_table()
                self.set_page_no()
                self.ui.home_progress_bar.setRange(0, 1)
            else:
                if query not in [None, ""]:
                    if check_internet_connection():
                        self.ui.home_progress_bar.setRange(0, 0)
                        self.search_thread = SearchThreads(self.default_server, query, self.country, str(self.page),
                                                           self.sort_by, self)
                        self.search_thread.search_results.connect(self.get_search_results)
                        self.search_thread.start()
                    else:
                        self.ui.home_progress_bar.setRange(0, 1)
                        self.popup_message(title="No internet connection", message="Please connect to the internet")
        else:
            self.popup_message(title="Process Already In Queue",
                               message="Please wait for the Running process to finish!")

    def get_search_results(self, data):
        self.disable_enable_prev_next_page(show=True)
        if self.page == 1:
            self.ui.prev_page.setEnabled(False)
        self.set_page_no()
        self.result(data)

    def get_home_page(self, initial=False):
        try:
            search_thread = self.search_thread.isRunning()
        except Exception as e:
            search_thread = False
        try:
            pixmap_thread = self.pixmap_load_thread.isRunning()
        except Exception as e:
            pixmap_thread = False

        if not search_thread and not pixmap_thread:
            self.ui.page_no.setVisible(False)
            self.disable_enable_prev_next_page(show=False)
            if len(HOME_CACHE.get("home", {}).get("content", [])) != 0:
                self.ui.home_progress_bar.setRange(0, 0)
                self.title_list = HOME_CACHE.get("home", {}).get("content", [])
                self.pixmap_list = HOME_CACHE.get("home", {}).get("pixmap_cache", [])
                self.videoid_list = HOME_CACHE.get("home", {}).get("videoid_list", [])
                self.thumbnail_list = HOME_CACHE.get("home", {}).get("thumbnail_list", [])
                self.process_images_into_table()
                self.ui.home_progress_bar.setRange(0, 1)
            else:
                if check_internet_connection():
                    try:
                        home_thread = self.home_thread.isRunning()
                    except Exception as e:
                        home_thread = False
                    try:
                        pixmap_thread = self.pixmap_load_thread.isRunning()
                    except Exception as e:
                        pixmap_thread = False

                    if not home_thread and not pixmap_thread:
                        self.ui.home_progress_bar.setRange(0, 0)
                        self.ui.youtube_search.clear()
                        self.home_thread = HomeThreads(self.default_server, self.country, self.explore, self)

                        self.home_thread.home_results.connect(self.result)
                        self.home_thread.server_change_error.connect(self.server_error_handle)
                        self.home_thread.start()
                else:
                    self.ui.home_progress_bar.setRange(0, 1)
                    if not initial:
                        self.popup_message(title="No internet connection", message="Please connect to the internet")
        else:
            self.popup_message(title="Search Process Already In Queue",
                               message="Please wait, Image thumbnails on this page are loading!")

    def server_error_handle(self, msg):
        self.ui.home_progress_bar.setRange(0, 1)
        self.popup_message(title="Could not connect to the server!", message="TUBE2GO server is currently busy,"
                                                                             " please try again after some time.\n\n"
                                                                             "Tip: Switch to another server from settings might resolve this issue.")

    def table_view_default_setting(self):
        self.ui.tableWidget.setColumnCount(3)
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.verticalHeader().setDefaultSectionSize(125)
        self.ui.tableWidget.setColumnWidth(0, 60)
        self.ui.tableWidget.setColumnWidth(1, 205)
        self.ui.tableWidget.setColumnWidth(2, 500)
        self.ui.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def process_images_into_table(self):
        try:
            self.ui.tableWidget.setRowCount(len(self.thumbnail_list))
            for row in range(len(self.pixmap_list)):
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-youtube-play-button-500.png"),
                               QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
                icon2 = QtGui.QIcon()
                icon2.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-download-from-cloud-90.png"),
                                QtGui.QIcon.Normal,
                                QtGui.QIcon.Off)

                icon3 = QtGui.QIcon()
                icon3.addPixmap(QtGui.QPixmap(":/myresource/resource/play.png"),
                                QtGui.QIcon.Normal,
                                QtGui.QIcon.Off)
                widget = QtWidgets.QWidget()
                horizontalLayout_24 = QtWidgets.QVBoxLayout()
                button = QtWidgets.QToolButton(widget)
                horizontalLayout_24.addWidget(button)
                button2 = QtWidgets.QToolButton(widget)
                button3 = QtWidgets.QToolButton(widget)
                sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
                button.setSizePolicy(sizePolicy)
                button2.setSizePolicy(sizePolicy)
                button3.setSizePolicy(sizePolicy)
                button.setIcon(icon)
                button2.setIcon(icon2)
                button3.setIcon(icon3)
                button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                button2.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                button3.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                button.setToolTip("Watch on YouTube")
                button2.setToolTip("Download")
                button3.setToolTip("Watch")
                button.setStyleSheet(
                    "QToolButton{background-color: #233547;}\nQToolButton:hover {background-color: #314a62;}")
                button2.setStyleSheet(
                    "QToolButton{background-color: #233547;}\nQToolButton:hover {background-color: #314a62;}")
                button3.setStyleSheet(
                    "QToolButton{background-color: #233547;}\nQToolButton:hover {background-color: #314a62;}")
                button.setIconSize(QtCore.QSize(30, 30))
                button2.setIconSize(QtCore.QSize(30, 30))
                button3.setIconSize(QtCore.QSize(30, 30))
                horizontalLayout_24.addWidget(button2)
                horizontalLayout_24.addWidget(button3)
                verticalLayout_8 = QtWidgets.QVBoxLayout(widget)
                verticalLayout_8.addLayout(horizontalLayout_24)
                button.clicked.connect(lambda _, r=f"v-{row}": self.signal_for_row_button_table(r))
                button2.clicked.connect(lambda _, r=f"d-{row}": self.signal_for_row_button_table(r))
                button3.clicked.connect(lambda _, r=f"w-{row}": self.signal_for_row_button_table(r))
                self.ui.tableWidget.setCellWidget(row, 0, widget)

            for row in range(len(self.pixmap_list)):
                icon = QtGui.QIcon()
                icon.addPixmap(self.pixmap_list[row], QtGui.QIcon.Normal, QtGui.QIcon.Off)
                chkBoxItem = QTableWidgetItem(icon, "")
                self.ui.tableWidget.setItem(row, 1, chkBoxItem)

            for row, value in enumerate(self.title_list, 0):
                widget = QtWidgets.QWidget()
                widgetText = QtWidgets.QLabel(f"{value}")
                widgetLayout = QtWidgets.QHBoxLayout()
                widgetLayout.addWidget(widgetText)
                widgetLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
                widget.setLayout(widgetLayout)
                self.ui.tableWidget.setCellWidget(row, 2, widget)
            self.ui.tableWidget.setIconSize(QtCore.QSize(197, 165))
        except Exception as e:
            print(e)
            self.table_view_default_setting()
            self.popup_message(title="Could not load images!", message="Please select valid image file", error=True)

    def set_icon_on_line_edit(self):
        self.url_dialog_ui.ui.yt_video_link.addAction(QIcon(":/myresource/resource/icons8-search-500.png"),QLineEdit.LeadingPosition)
        self.ui.search_videos.addAction(QIcon(":/myresource/resource/icons8-search-500.png"), QLineEdit.LeadingPosition)
        self.ui.youtube_search.addAction(QIcon(":/myresource/resource/icons8-search-500.png"),QLineEdit.LeadingPosition)
        self.url_dialog_ui.ui.yt_video_link.setTextMargins(5, 0, 0, 0)
        self.ui.search_videos.setTextMargins(5, 0, 0, 0)
        self.ui.youtube_search.setTextMargins(5, 0, 0, 0)
        self.ui.youtube_search.setClearButtonEnabled(True)
        self.ui.search_videos.setClearButtonEnabled(True)
        self.url_dialog_ui.ui.yt_video_link.setClearButtonEnabled(True)
        self.ui.youtube_search.findChild(QtWidgets.QAction, "_q_qlineeditclearaction").setIcon(QtGui.QIcon(":/myresource/resource/icons8-multiply-52.png"))
        self.ui.search_videos.findChild(QtWidgets.QAction, "_q_qlineeditclearaction").setIcon(QtGui.QIcon(":/myresource/resource/icons8-multiply-52.png"))
        self.url_dialog_ui.ui.yt_video_link.findChild(QtWidgets.QAction, "_q_qlineeditclearaction").setIcon(QtGui.QIcon(":/myresource/resource/icons8-multiply-52.png"))

    def save_completer(self):
        try:
            self.completer_obj = CompleterThread(self.default_server, self.ui.youtube_search.text(), self.country, self)
            self.completer_obj.get_completer_value.connect(self.load_completer_data)
            self.completer_obj.start()

            model = QStringListModel()
            model.setStringList(self.c_database)
            self.completer.setModel(model)
        except:
            pass

    def decide_video_or_playlist(self):
        if self.url_dialog_ui.ui.video_vs.isChecked():
            self.ytv_link_clicked()
        elif self.url_dialog_ui.ui.playlist_vs.isChecked():
            self.ytv_link_clicked_playlist()

    def load_completer_data(self, data):
        try:
            self.c_database = data
        except:
            pass

    def result(self, data):
        self.thumbnail_list = []
        self.title_list = []
        self.pixmap_list = []
        self.videoid_list = []
        self.table_view_default_setting()
        if not data.get("result_data", []):
            self.country = "DE"
            self.youtube_setting_ui.ui.country.setCurrentText(COUNTRIES_REVERSE.get(self.country, "Germany"))
            self.settings.setValue("country", "DE")
            title = "YouTube Home Page Server is Under Maintenance In Your Region"
            message = "\nTips:\n1. Try to change your server from the app settings." \
                      "\n2. Try to change your region from the app settings." \
                      "\n3. For now default country is set to Germany Region Automatically." \
                      "\n\nNote: Search and Download YouTube videos will work even when " \
                      "the home page server is under Maintenance." \
                      "\nPlease be patient, Sorry For The Inconvenience.\n\n!Please Restart your Application!"
            self.popup_message(title, message)
            self.ui.home_progress_bar.setRange(0, 1)
        else:
            for item in data.get("result_data", [])[: self.home_button_item]:
                if item.get("videoId", '') == '':
                    continue
                thumbnail = "https://i.ytimg.com/vi/" + \
                            item.get("videoThumbnails", {})[4].get("url", "").split("/vi/")[1].split("/")[
                                0] + "/mqdefault.jpg"
                video_id = 'https://www.youtube.com/watch?v=' + item.get("videoId", '')
                content = """<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-weight:600;">{{title}}</span></p>
                <p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:12pt; font-weight:600;"><br /></p>
                <p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-size:10pt; font-weight:600;">Views</span><span style=" font-size:10pt;"> : {{views}}</span></p>
                <p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-size:10pt; font-weight:600;">Channel</span><span style=" font-size:10pt;"> : {{channel}}</span></p>
                <p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-size:10pt; font-weight:600;">Duration</span><span style=" font-size:10pt;">: {{duration}}</span></p>
                <p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-size:10pt; font-weight:600;">Published</span><span style=" font-size:10pt;">: {{published_on}}</span></p>"""
                content = content.replace("{{title}}", item.get("title", "")).replace("{{views}}", human_format(
                    item.get("viewCount", 0))).replace("{{channel}}", item.get("author", "")).replace("{{duration}}",
                                                                                                      get_time_format(
                                                                                                          item.get(
                                                                                                              "lengthSeconds",
                                                                                                              0))).replace(
                    "{{published_on}}", item.get("publishedText", ""))

                self.thumbnail_list.append(thumbnail)
                self.videoid_list.append(video_id)
                self.title_list.append(content)

        if data.get("content_type", "") == "home":
            try:
                HOME_CACHE["home"] = {"content": self.title_list,
                                      "pixmap_cache": [],
                                      "thumbnail_list": self.thumbnail_list,
                                      "videoid_list": self.videoid_list,
                                      }
            except Exception as e:
                print(e)

            self.pixmap_load_thread = PixMapLoadingThread(self.thumbnail_list, self.pixmap_cache, "home", self)
        else:
            self.pixmap_load_thread = PixMapLoadingThread(self.thumbnail_list, self.pixmap_cache, "search", self)
            try:
                if len(HOME_CACHE.get("search", {}).get(str(self.ui.youtube_search.text()), {})) != 0:
                    HOME_CACHE["search"][str(self.ui.youtube_search.text())][str(self.page)] = {
                        "content": self.title_list,
                        "pixmap_cache": [],
                        "thumbnail_list": self.thumbnail_list,
                        "videoid_list": self.videoid_list,
                        }
                else:
                    HOME_CACHE.setdefault("search", {str(self.ui.youtube_search.text()): {str(self.page): {}}})
                    HOME_CACHE["search"].setdefault(str(self.ui.youtube_search.text()), {str(self.page): {}})
                    HOME_CACHE["search"][str(self.ui.youtube_search.text())][str(self.page)] = {
                        "content": self.title_list,
                        "pixmap_cache": [],
                        "thumbnail_list": self.thumbnail_list,
                        "videoid_list": self.videoid_list,
                        }
            except Exception as e:
                print(e)

        self.pixmap_load_thread.finish.connect(self.setProgressVal_pixmap_finish)
        self.pixmap_load_thread.progress.connect(self.setProgressVal_pixmap)
        self.pixmap_load_thread.finish_first_pixmap.connect(self.first_finish_pixmap)
        self.pixmap_load_thread.start()

    def setProgressVal_pixmap(self, pixmap_image):
        try:
            self.pixmap_list.append(pixmap_image.get("pixmap"))
            if pixmap_image.get("content_type", "") == "home":
                HOME_CACHE["home"]["pixmap_cache"].append(pixmap_image.get("pixmap"))
            else:
                HOME_CACHE["search"][str(self.ui.youtube_search.text())][str(self.page)].get("pixmap_cache", []).append(
                    pixmap_image.get("pixmap"))
        except Exception as e:
            print(e)

        self.process_images_into_table()

    def first_finish_pixmap(self):
        try:
            search_thread = self.search_thread.isRunning()
        except Exception as e:
            search_thread = False
        if not search_thread:
            self.ui.home_progress_bar.setRange(0, 1)

    def setProgressVal_pixmap_finish(self, data):
        self.pixmap_cache.update(dict(zip(self.thumbnail_list, self.pixmap_list)))

    """
        Net speed settings =============================================================================================
    """

    def default_frequency(self):
        self.ui.horizontalSlider_freq.setValue(4)
        self.ui.frequency_label.setText("1.0 Sec")

    def change_net_speed_unit(self):
        self.speed_unit = self.ui.comboBox_speed_unit.currentText()
        try:
            dummy_data_thread = self.dummy_data_thread.isRunning()
        except Exception:
            dummy_data_thread = False
        if not dummy_data_thread:
            self.load_annimation_data()
        try:
            self.net_speed_thread.terminate()
            self.start_net_speed_thread()
        except Exception as e:
            pass

    def change_temp_unit(self):
        self.temp_unit = self.ui.comboBox_cpu_temp.currentText()
        try:
            dummy_data_thread = self.dummy_data_thread.isRunning()
        except Exception:
            dummy_data_thread = False
        if not dummy_data_thread:
            self.load_annimation_data()
        try:
            self.cpu_thread.terminate()
            self.start_cpu_thread()
        except Exception as e:
            pass

    def change_frequency_net(self):
        self.system_frequency = FREQUENCY_MAPPER.get(self.ui.horizontalSlider_freq.value(), 4)
        self.ui.frequency_label.setText(str(self.system_frequency) + " Sec")
        try:
            dummy_data_thread = self.dummy_data_thread.isRunning()
        except Exception:
            dummy_data_thread = False
        if not dummy_data_thread:
            self.load_annimation_data()
        try:
            self.net_speed_thread.terminate()
            self.start_net_speed_thread()
        except Exception as e:
            pass
        try:
            self.cpu_thread.terminate()
            self.start_cpu_thread()
        except Exception as e:
            pass
        try:
            self.ram_thread.terminate()
            self.start_ram_thread()
        except Exception as e:
            pass

    def start_cpu_thread(self):
        self.cpu_thread = CpuThread(self.system_frequency, self.temp_unit, self)
        self.cpu_thread.change_value.connect(self.setProgress_cpu)
        self.cpu_thread.start()

    def start_ram_thread(self):
        self.ram_thread = RamThread(self.system_frequency, self)
        self.ram_thread.change_value.connect(self.setProgress_ram)
        self.ram_thread.start()

    def start_net_speed_thread(self):
        self.net_speed_thread = NetSpeedThread(self.system_frequency, self.speed_unit, self)
        self.net_speed_thread.change_value.connect(self.setProgress_net_speed)
        self.net_speed_thread.start()

    def load_annimation_data(self):
        self.dummy_data_thread = DummyDataThread(self)
        self.dummy_data_thread.change_value.connect(self.setProgress_dummy_data)
        self.dummy_data_thread.start()

    def setProgress_cpu(self, value):
        self.ui.cpu_usage.setText(value[0])
        self.ui.cpu_temp.setText(value[1])

    def setProgress_ram(self, value):
        self.ui.ram_usage.setText(value[0])
        self.ui.ram_total.setText(value[1])
        self.ui.ram_free.setText(value[2])

    def setProgress_net_speed(self, value):
        self.ui.internet_speed.setText(value[0][0])
        self.ui.internet_unit.setText(value[0][1])
        self.ui.internet_connection.setText(value[1])
        self.speed = value[0][0]
        self.unit = value[0][1]

    def setProgress_dummy_data(self, value):
        self.ui.cpu_usage.setText(value[0])
        self.ui.ram_usage.setText(value[0])
        self.ui.internet_speed.setText(value[1])

    """
        load/save settings =============================================================================================
    """

    def closeEvent(self, event):
        self.save_settings()
        self.youtube_setting_ui.hide()
        self.url_dialog_ui.hide()
        super().closeEvent(event)

    def save_settings(self):
        self.settings.setValue("delete_source_file_check", self.delete_source_file)
        self.settings.setValue("default_loc", self.Default_loc)
        self.settings.setValue("default_loc_playlist", self.Default_loc_playlist)
        self.settings.setValue("net_speed_unit", self.ui.comboBox_speed_unit.currentText())
        self.settings.setValue("system_frequency", self.ui.horizontalSlider_freq.value())
        self.settings.setValue("cpu_temp_unit", self.ui.comboBox_cpu_temp.currentText())

        #  one time congratulate
        self.settings.setValue("one_time_congratulate", self.one_time_congratulate)
        # save window state
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        # save youtube settings
        self.settings.setValue("country", COUNTRIES.get(self.youtube_setting_ui.ui.country.currentText(), "US"))
        self.settings.setValue("explore", EXPLORE.get(self.youtube_setting_ui.ui.explore.currentText(), "trending"))
        self.settings.setValue("sort_by", SORT_BY.get(self.youtube_setting_ui.ui.sort_by.currentText(), "relevance"))
        self.settings.setValue("home_button_item", self.youtube_setting_ui.ui.no_of_videos.value())
        self.settings.setValue("default_server",
                               SERVER.get(self.youtube_setting_ui.ui.server.currentText(), "http://invidio.xamh.de"))
        self.settings.setValue("stream_quality", STREAM_QUALITY_DICT.get(self.youtube_setting_ui.ui.stream_quality.currentText(), 2))
        self.settings.setValue("after_playback_action", AFTER_PLAYBACK.get(self.youtube_setting_ui.ui.after_playback.currentText(), "loop_play"))

    def load_settings(self):
        if self.settings.contains("delete_source_file_check"):
            self.delete_source_file = json.loads(self.settings.value("delete_source_file_check").lower())
        if self.settings.contains("default_loc"):
            self.Default_loc = self.settings.value("default_loc")
            self.youtube_setting_ui.ui.download_path_edit_2.setText(self.Default_loc + "/TUBE2GO")
        if self.settings.contains("default_loc_playlist"):
            self.Default_loc_playlist = self.settings.value("default_loc_playlist")
            self.youtube_setting_ui.ui.download_path_edit_playlist.setText(self.Default_loc_playlist + "/TUBE2GO")

        if self.settings.contains("net_speed_unit"):
            self.speed_unit = self.settings.value("net_speed_unit")
            self.ui.comboBox_speed_unit.setCurrentText(self.speed_unit)
        if self.settings.contains("system_frequency"):
            self.system_frequency = FREQUENCY_MAPPER.get(int(self.settings.value("system_frequency")), 4)
            self.ui.horizontalSlider_freq.setValue(int(self.settings.value("system_frequency")))
            self.ui.frequency_label.setText(
                str(FREQUENCY_MAPPER.get(int(self.settings.value("system_frequency")), "1.0")) + " Sec")
        if self.settings.contains("cpu_temp_unit"):
            self.temp_unit = self.settings.value("cpu_temp_unit")
            self.ui.comboBox_cpu_temp.setCurrentText(self.temp_unit)

        #  one time congratulate
        if self.settings.contains("one_time_congratulate"):
            self.one_time_congratulate = json.loads(self.settings.value("one_time_congratulate"))

        # load window state
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        if self.settings.contains("windowState"):
            self.restoreState(self.settings.value("windowState", ""))

        #  youtube settings load
        if self.settings.contains("country"):
            self.country = self.settings.value("country")
            self.youtube_setting_ui.ui.country.setCurrentText(COUNTRIES_REVERSE.get(self.country, "United States"))
        if self.settings.contains("explore"):
            self.explore = self.settings.value("explore")
            self.youtube_setting_ui.ui.explore.setCurrentText(EXPLORE_REVERSE.get(self.explore, "Trending"))
        if self.settings.contains("sort_by"):
            self.sort_by = self.settings.value("sort_by")
            self.youtube_setting_ui.ui.sort_by.setCurrentText(SORT_BY_REVERSE.get(self.sort_by, "Relevance"))
        if self.settings.contains("home_button_item"):
            self.home_button_item = json.loads(self.settings.value("home_button_item", "20"))
            self.youtube_setting_ui.ui.no_of_videos.setValue(self.home_button_item)
        if self.settings.contains("default_server"):
            self.default_server = self.settings.value("default_server")
            self.youtube_setting_ui.ui.server.setCurrentText(SERVER_REVERSE.get(self.default_server, "TUBE2GO-SERVER-1"))
        if self.settings.contains("stream_quality"):
            self.stream_quality = json.loads(self.settings.value("stream_quality"))
            self.youtube_setting_ui.ui.stream_quality.setCurrentText(
                STREAM_QUALITY_REVERSE_DICT.get(self.stream_quality, "High"))
        if self.settings.contains("after_playback_action"):
            self.after_playback_action = self.settings.value("after_playback_action")
            self.youtube_setting_ui.ui.after_playback.setCurrentText(
                AFTER_PLAYBACK_REVERSE.get(self.after_playback_action, "Loop Play"))

    def show_file_size(self):
        try:
            file_size_single_video_thread_status = self.file_size_single_video_thread.isRunning()
        except Exception as e:
            file_size_single_video_thread_status = False
        if not file_size_single_video_thread_status:
            if self.ui.select_quality_obj_2.currentText() not in ["", None, 'Select Quality']:
                self.file_size_single_video_thread = FileSizeThreadSingleVideo(self, self)
                self.file_size_single_video_thread.get_size_of_single_video_file.connect(
                    self.set_file_size_single_video)
                self.file_size_single_video_thread.start()

    def set_file_size_single_video(self, size):
        if size:
            self.ui.video_size_5.setText(f"{size}")

    def file_download_success_dialog(self, title, folder_path, play_path):
        self.msg = QMessageBox()
        self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
        self.msg.setIcon(QMessageBox.Information)
        self.msg.setText(title)
        self.msg.setInformativeText("")
        close = self.msg.addButton(QMessageBox.Yes)
        show_in_downloads = self.msg.addButton(QMessageBox.Yes)
        play = self.msg.addButton(QMessageBox.Yes)
        mpv_play = self.msg.addButton(QMessageBox.Yes)
        open_folder = self.msg.addButton(QMessageBox.Yes)
        open_folder.setText('Open Folder')
        show_in_downloads.setText('Show Downloads')
        play.setText('Play')
        mpv_play.setText('MPV Play')
        close.setText('Close')
        play.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_MediaPlay)))
        mpv_play.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_MediaPlay)))
        close.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_BrowserStop)))
        open_folder.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_DirIcon)))
        show_in_downloads.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_DirOpenIcon)))
        self.msg.exec_()
        try:
            if self.msg.clickedButton() == open_folder:
                QDesktopServices.openUrl(QUrl(folder_path))
            elif self.msg.clickedButton() == play:
                QDesktopServices.openUrl(QUrl(play_path))
            elif self.msg.clickedButton() == mpv_play:
                self.process = QProcess()
                self.mpv_arguments = []
                if self.after_playback_action == "loop_play":
                    self.mpv_arguments.append("--loop")
                self.mpv_arguments.append("--force-window")
                self.mpv_arguments.append(play_path)
                self.mpv_arguments.append("--title={0}".format(title))
                self.mpv_arguments.append("--gpu-context=x11")
                self.process.start("mpv", self.mpv_arguments)
            elif self.msg.clickedButton() == show_in_downloads:
                self.show_downloads_page()
            elif self.msg.clickedButton() == close:
                pass
        except Exception as e:
            pass

    def pause_button_pressed(self):
        try:
            video_thread_running = self.process_ytv_thread.isRunning()
        except Exception as e:
            video_thread_running = False
        try:
            playlist_thread_running = self.process_ytv_play_list_thread.isRunning()
        except Exception as e:
            playlist_thread_running = False

        if video_thread_running:
            if self.pause:
                self.process_ytv_thread.resume()
                set_style_for_pause_play_button(self, pause=True)
                self.pause = False
            else:
                self.process_ytv_thread.pause()
                set_style_for_pause_play_button(self, pause=False)
                self.pause = True
        elif playlist_thread_running:
            if self.pause:
                self.process_ytv_play_list_thread.resume()
                set_style_for_pause_play_button(self, pause=True)
                self.pause = False
            else:
                self.process_ytv_play_list_thread.pause()
                set_style_for_pause_play_button(self, pause=False)
                self.pause = True

    def trigger_delete_action(self):
        try:
            self.msg = QMessageBox()
            self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
            self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
            self.msg.setIcon(QMessageBox.Information)
            self.msg.setText("Are you sure want to stop on-going task?")
            yes_button = self.msg.addButton(QMessageBox.Yes)
            no_button = self.msg.addButton(QMessageBox.No)
            self.msg.exec_()
            if self.msg.clickedButton() == yes_button:
                self.delete_button_pressed()
            if self.msg.clickedButton() == no_button:
                pass
        except Exception as e:
            self.popup_message(title="Error while deleting the task!", message="", error=True)
            pass

    def delete_button_pressed(self):
        try:
            video_thread_running = self.process_ytv_thread.isRunning()
        except Exception as e:
            video_thread_running = False
        try:
            playlist_thread_running = self.process_ytv_play_list_thread.isRunning()
        except Exception as e:
            playlist_thread_running = False

        try:
            if video_thread_running:
                self.progress_bar_disable()
                self.pause = False
                set_style_for_pause_play_button(self, pause=True)
                self.hide_show_play_pause_button(hide=True)
                self.process_ytv_thread.kill()
            elif playlist_thread_running:
                self.progress_bar_disable()
                self.pause = False
                set_style_for_pause_play_button(self, pause=True)
                self.hide_show_play_pause_button(hide=True)
                self.process_ytv_play_list_thread.kill()
        except Exception as e:
            pass

    def popup_message(self, title, message, error=False):
        self.msg = QMessageBox()
        self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
        if error:
            self.msg.setIcon(QMessageBox.Warning)
        else:
            self.msg.setIcon(QMessageBox.Information)
        self.msg.setText(title)
        self.msg.setInformativeText(message)
        self.msg.setStandardButtons(QMessageBox.Ok)
        self.msg.exec_()

    def progress_bar_enable(self):
        self.ui.progress_bar.setRange(0, 0)

    def progress_bar_disable(self):
        self.ui.progress_bar.setRange(0, 1)

    def open_download_path(self):
        folder_loc = QFileDialog.getExistingDirectory(self, "Select Downloads Directory",
                                                      self.Default_loc,
                                                      QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder_loc:
            if check_default_location(folder_loc):
                self.youtube_setting_ui.ui.download_path_edit_2.setText(folder_loc + "/TUBE2GO")
                self.Default_loc = folder_loc
            else:
                self.popup_message(title="Download Path Invalid", message="Download Path Must Inside Home Directory")
                return False

    def check_for_audio_only(self):
        if self.ui.select_format_obj_2.currentText() == "AUDIO - MP3":
            self.ui.select_fps_obj_2.setEnabled(False)
            self.ui.select_quality_obj_2.setEnabled(False)
        else:
            self.ui.select_fps_obj_2.setEnabled(True)
            self.ui.select_quality_obj_2.setEnabled(True)

    def hide_show_play_pause_button(self, hide=True):
        self.ui.pause_button.setVisible(not hide)
        self.ui.delete_button.setVisible(not hide)

    def ytv_link_clicked(self, link=None):
        if link:
            data = link
        else:
            data = self.url_dialog_ui.ui.yt_video_link.text()
        if data != "":
            if check_internet_connection():
                try:
                    is_running = self.process_ytv_thread.isRunning()
                except Exception as e:
                    is_running = False
                try:
                    is_playlist_fetch_running = self.get_videos_list.isRunning()
                except Exception as e:
                    is_playlist_fetch_running = False
                try:
                    is_playlist_download_running = self.process_ytv_play_list_thread.isRunning()
                except Exception as e:
                    is_playlist_download_running = False
                try:
                    is_playlist_process = self.process_ytv_playlist_thread.isRunning()
                except Exception as e:
                    is_playlist_process = False
                if not is_running and not is_playlist_fetch_running and not is_playlist_download_running and not is_playlist_process:
                    self.progress_bar_enable()
                    self.ui.select_format_obj_2.clear()
                    self.ui.select_quality_obj_2.clear()
                    self.ui.select_fps_obj_2.clear()
                    try:
                        net_speed_thread = self.net_speed_thread.isRunning()
                    except Exception as e:
                        net_speed_thread = False
                        pass
                    if not net_speed_thread:
                        self.start_net_speed_thread()
                    self.process_ytv_thread = ProcessYtV(data, True, self.Default_loc, self)
                    self.process_ytv_thread.change_value.connect(self.setProgressVal)
                    self.process_ytv_thread.start()
                    self.url_dialog_ui.hide()
                else:
                    self.popup_message(title="Task Already In Queue",
                                       message="Please wait for the Running task to finish!")
            else:
                self.popup_message(title="No internet connection", message="Please check your internet connection!")

    def paste_button_clicked(self):
        self.url_dialog_ui.ui.yt_video_link.clear()
        self.url_dialog_ui.ui.yt_video_link.setText(QApplication.clipboard().text())

    def setProgressVal(self, yt_data):
        self.progress_bar_disable()
        if yt_data.get("status"):
            self.hide_show_video_initial_banner(show=True)
            self.yt = yt_data.get("yt")
            self.title = yt_data.get("title")
            self.length = yt_data.get("length")
            self.stream_url = yt_data.get("stream_url")
            self.watch_url = yt_data.get("watch_url")
            self.audio_stream_url = yt_data.get("audio_stream_url")
            self.thumbnail_path, title, length = process_html_data(yt_data, self.Default_loc)
            self.ui.textBrowser_thumbnail_9.setVisible(False)
            self.ui.graphicsView_video.setVisible(True)
            self.ui.video_title_5.setText(title)
            self.ui.video_length_5.setText(f"{length}")
            self.ui.by_channel.setText(yt_data.get("channel", ""))
            self.ui.views.setText(human_format(yt_data.get("views", 0)))
            self.ui.descriptions.setText(yt_data.get("description", ""))
            self.ui.watch_url.setText(f"<html><head/><body><p><a href='{self.watch_url}'>"
                                      f"<span style=' text-decoration: none; "
                                      f"color:#4e9a06;'>{self.watch_url}</span></a></p></body></html>")

            if yt_data.get("length") == '00m:00s':
                self.popup_message(title="Live youtube Video Detected!",
                                   message="Live youtube Video cannot be downloaded.")
            all_format, all_quality, all_fps = yt_data.get("quality_data")

            for index, item in enumerate(all_quality):
                self.ui.select_quality_obj_2.addItem(item)
                icon = QtGui.QIcon()
                if index in [0, 1, 2]:
                    icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-ok-144.png"), QtGui.QIcon.Normal,
                                   QtGui.QIcon.Off)
                else:
                    if not self.is_plan_active:
                        icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-lock-96.png"), QtGui.QIcon.Normal,
                                       QtGui.QIcon.Off)
                    else:
                        icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-ok-144.png"), QtGui.QIcon.Normal,
                                       QtGui.QIcon.Off)
                self.ui.select_quality_obj_2.setItemIcon(index, icon)

            for index, item in enumerate(all_format):
                self.ui.select_format_obj_2.addItem(item)
                icon = QtGui.QIcon()
                if index == 0:
                    icon.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"), QtGui.QIcon.Normal,
                                   QtGui.QIcon.Off)
                else:
                    if not self.is_plan_active:
                        icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-lock-96.png"), QtGui.QIcon.Normal,
                                       QtGui.QIcon.Off)
                    else:
                        if index == 1:
                            icon.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"),
                                           QtGui.QIcon.Normal,
                                           QtGui.QIcon.Off)
                        else:
                            icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-music-120.png"), QtGui.QIcon.Normal,
                                           QtGui.QIcon.Off)
                self.ui.select_format_obj_2.setItemIcon(index, icon)

            for index, item in enumerate(all_fps):
                self.ui.select_fps_obj_2.addItem(item)
                icon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-tick-box-120.png"), QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
                self.ui.select_fps_obj_2.setItemIcon(index, icon)

            self.ui.select_quality_obj_2.setCurrentIndex(0)
            self.ui.select_format_obj_2.setCurrentIndex(0)
            self.ui.select_fps_obj_2.setCurrentIndex(0)
            self.ui.stackedWidget.setCurrentIndex(1)
            self.setPhoto(QPixmap(self.thumbnail_path))
            self.ui.dock_back_home.setEnabled(True)
            self.ui.dock_home.setEnabled(True)
        else:
            if not self.pytube_status:
                self.popup_message(title="Application is in Schedule Maintenance",
                                   message="Video Downloading Option Is Not Available Right Now."
                                           " We Are Pushing New Updates, Please Check In A While."
                                           "\n\nNote: You Can Still Play Videos In The App. Sorry For The Inconvenience.")
            else:
                self.popup_message(title="Youtube video not available!",
                                   message="This video is not available. Please check your url !")

    def download_action(self):
        context = dict()
        context["quality"] = (str(self.ui.select_quality_obj_2.currentText()).split(" ")[0]).lower()
        try:
            is_running = self.process_ytv_thread.isRunning()
        except Exception as e:
            is_running = False
        try:
            is_playlist_fetch_running = self.get_videos_list.isRunning()
        except Exception as e:
            is_playlist_fetch_running = False
        try:
            is_playlist_download_running = self.process_ytv_play_list_thread.isRunning()
        except Exception as e:
            is_playlist_download_running = False

        if is_running or is_playlist_fetch_running or is_playlist_download_running:
            self.popup_message(title="Task Already In Queue", message="Please wait for the Running task to finish!")
        else:
            if context["quality"] not in ['select', '', None] and not is_running \
                    and not is_playlist_fetch_running and not is_playlist_download_running:
                context["formats"] = (str(self.ui.select_format_obj_2.currentText()).split(" ")[2]).lower()
                context["fps"] = int(str(self.ui.select_fps_obj_2.currentText()).split(" ")[0])
                context["url"] = self.url_dialog_ui.ui.yt_video_link.text()
                context["is_hd_plus"] = True
                if self.ui.select_format_obj_2.currentText() == "VIDEO - MP4" or self.ui.select_format_obj_2.currentText() == "VIDEO - WEBM":
                    context["type"] = "video"
                if self.ui.select_format_obj_2.currentText() == "AUDIO - MP3" or self.ui.select_format_obj_2.currentText() == "AUDIO - MP3":
                    context["type"] = "audio"
                self.progress_bar_enable()
                self.ui.progress_bar.setRange(0, 100)
                context["location"] = self.Default_loc
                context["yt"] = self.yt
                context["main_obj"] = self
                self.counter = 0
                response = self.block_pro_plan_for_videos()
                if response:
                    self.process_ytv_thread = DownloadVideo(context, self)
                    self.process_ytv_thread.change_value.connect(self.tc_process_download)
                    self.process_ytv_thread.finished.connect(self.tc_finished_downloading_thread)
                    self.process_ytv_thread.converting_videos.connect(self.tc_converting_videos)
                    self.process_ytv_thread.error.connect(self.tc_error_on_downloading)
                    self.process_ytv_thread.no_error.connect(self.tc_no_error)
                    self.process_ytv_thread.after_kill.connect(self.tc_after_kill)
                    self.process_ytv_thread.start()
            else:
                if context["quality"] == "select":
                    self.popup_message(title="No Audio/Video File To Download!",
                                       message="Please Select YouTube Video From The Home Tab.")
                else:
                    self.popup_message(title="Invalid Youtube Url", message="Please check your video link !")

    def block_pro_plan_for_videos(self):
        if self.ui.select_quality_obj_2.currentText() in ['144p (LD)', '240p (LD)', '360p (SD)']\
                and self.ui.select_format_obj_2.currentText() == 'VIDEO - MP4':
            return True
        else:
            response = self.check_your_plan()
        return response

    def tc_process_download(self, value_dict):
        if not value_dict.get("is_killed"):
            display_status = "({0}%) Completed: {1} of {2}               " \
                             "Speed: @{3}{4}".format(value_dict.get("progress"),
                                                     value_dict.get("downloaded"),
                                                     value_dict.get("total_size"),
                                                     self.speed,
                                                     self.unit)

            self.ui.progress_bar.setRange(0, 100)
            self.ui.progress_bar.setFormat(display_status)
            self.ui.progress_bar.setValue(value_dict.get("progress"))
        else:
            self.ui.progress_bar.reset()
            self.progress_bar_disable()

    def tc_finished_downloading_thread(self, json_data):
        if not json_data.get("is_killed"):
            self.hide_show_play_pause_button(hide=True)
            self.progress_bar_disable()
            try:
                self.download_page()
            except Exception as e:
                pass
            folder_path = json_data.get("file_path")
            play_path = json_data.get("play_path")
            if self.counter == 0:
                self.counter += 1
                message = f"Download Success\n\n{json_data.get('title')}"
                self.file_download_success_dialog(message, folder_path, play_path)

    def tc_converting_videos(self, value_dict):
        if value_dict.get("progress") % 2 == 0:
            if value_dict.get("type") == "audio":
                self.ui.progress_bar.setFormat("Converting audio to mp3 ...")
            else:
                self.ui.progress_bar.setFormat("Merging audio video ...")
        elif value_dict.get("progress") % 2 != 0:
            self.ui.progress_bar.resetFormat()
            self.ui.progress_bar.setRange(0, 100)
            self.ui.progress_bar.setValue(value_dict.get("progress"))

    def tc_error_on_downloading(self, error_dict):
        if error_dict.get("error") == "File Already Exists":
            file_path = error_dict.get("file_path")
            play_path = error_dict.get("play_path")
            title = error_dict.get("title")
            message = f"File Already Exists!\n\n{title}"
            if file_path and play_path:
                self.file_download_success_dialog(message, file_path, play_path)
            else:
                self.popup_message(title="File Already Exists", message=error_dict.get("error"))
        else:
            self.popup_message(title="Error Occurred", message=error_dict.get("error"))
            self.hide_show_play_pause_button(hide=True)

    def tc_no_error(self, message):
        if message == "no_error":
            self.hide_show_play_pause_button(hide=False)

    def tc_after_kill(self, unfinished_file_path):
        try:
            self.progress_bar_disable()
            os.remove(unfinished_file_path)

        except Exception as e:
            pass

    """
    
    <===========================================  Playlist Functionality:  =============================================> 
    
    """

    def open_download_path_playlist(self):
        folder_loc = QFileDialog.getExistingDirectory(self, "Select Downloads Directory",
                                                      self.Default_loc_playlist,
                                                      QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder_loc:
            if check_default_location(folder_loc):
                self.youtube_setting_ui.ui.download_path_edit_playlist.setText(folder_loc + "/TUBE2GO")
                self.Default_loc_playlist = folder_loc
            else:
                self.popup_message(title="Download Path Invalid", message="Download Path Must Inside Home Directory")
                return False

    def ytv_link_clicked_playlist(self):
        self.play_list_counter = 1
        data = self.url_dialog_ui.ui.yt_video_link.text()
        if data != "":
            if check_internet_connection():
                try:
                    is_running = self.process_ytv_thread.isRunning()
                except Exception as e:
                    is_running = False
                try:
                    is_size_running = self.file_size_thread.isRunning()
                except Exception as e:
                    is_size_running = False
                try:
                    is_playlist_fetch_running = self.get_videos_list.isRunning()
                except Exception as e:
                    is_playlist_fetch_running = False
                try:
                    is_playlist_download_running = self.process_ytv_play_list_thread.isRunning()
                except Exception as e:
                    is_playlist_download_running = False
                try:
                    is_playlist_process = self.process_ytv_playlist_thread.isRunning()
                except Exception as e:
                    is_playlist_process = False
                if not is_running and not is_playlist_fetch_running and not is_playlist_download_running and not is_playlist_process and not is_size_running:
                    self.progress_bar_enable()
                    try:
                        net_speed_thread = self.net_speed_thread.isRunning()
                    except Exception as e:
                        net_speed_thread = False
                        pass
                    if not net_speed_thread:
                        self.start_net_speed_thread()
                    self.ui.select_videos_playlist_2.clear()
                    self.ui.select_quality_playlist_2.clear()
                    self.ui.select_type_playlist_2.clear()
                    self.ui.select_videos_playlist_2.setEnabled(False)
                    self.ui.select_quality_playlist_2.setEnabled(False)
                    self.ui.select_type_playlist_2.setEnabled(False)
                    self.process_ytv_playlist_thread = ProcessYtVPlayList(self.url_dialog_ui.ui.yt_video_link.text(),
                                                                          self.Default_loc_playlist, self)
                    self.process_ytv_playlist_thread.change_value_playlist.connect(self.setProgressVal_playlist)
                    self.process_ytv_playlist_thread.start()
                    self.url_dialog_ui.hide()
                else:
                    self.popup_message(title="Task Already In Queue",
                                       message="Please wait for the Running task to finish!")
            else:
                self.popup_message(title="No internet connection", message="Please check your internet connection!")

    def download_action_playlist(self):
        context = dict()
        try:
            context["quality"] = (str(self.ui.select_quality_playlist_2.currentText()).split(" ")[0]).lower()
            context["formats"] = (str(self.ui.select_type_playlist_2.currentText()).split(" ")[2]).lower()
        except Exception as e:
            pass
        try:
            is_video_running = self.process_ytv_thread.isRunning()
        except Exception as e:
            is_video_running = False
        try:
            is_playlist_download_running = self.process_ytv_play_list_thread.isRunning()
        except Exception as e:
            is_playlist_download_running = False
        try:
            is_playlist_fetch_running = self.get_videos_list.isRunning()
        except Exception as e:
            is_playlist_fetch_running = False

        if is_video_running:
            self.popup_message(title="Task Already In Queue", message="Please wait for the Running task to finish!")
        elif is_playlist_fetch_running:
            self.popup_message(title="Info", message="Please wait. Playlist videos are loading.")
        elif is_playlist_download_running:
            self.popup_message(title="Info", message="Please wait. Playlist videos are Already Downloading.")
        else:
            if context["quality"] not in ['select', '',
                                          None] and not is_video_running and not is_playlist_fetch_running:
                context["video_type"] = self.ui.select_type_playlist_2.currentText()
                context["selected_video"] = safe_string((self.ui.select_videos_playlist_2.currentText()))
                context["selected_video_index"] = self.ui.select_videos_playlist_2.currentIndex()

                context["all_yt_playlist_obj"] = self.total_obj
                context["playlist"] = self.playlist
                context["location"] = self.Default_loc_playlist
                context["main_obj"] = self
                self.progress_bar_enable()
                self.ui.progress_bar.setRange(0, 100)
                response = self.block_pro_plan_for_playlist()
                if response:
                    self.process_ytv_play_list_thread = DownloadVideoPlayList(context, self)
                    self.process_ytv_play_list_thread.change_value.connect(self.tc_process_download_playlist)
                    self.process_ytv_play_list_thread.finished.connect(self.tc_finished_downloading_thread_playlist)
                    self.process_ytv_play_list_thread.after_kill.connect(self.tc_after_kill_playlist)
                    self.process_ytv_play_list_thread.playlist_finished.connect(
                        self.tc_finished_downloading_thread_playlist_all)
                    self.process_ytv_play_list_thread.error_playlist.connect(self.error_playlist)
                    self.process_ytv_play_list_thread.ffmpeg_conversion.connect(self.ffmpeg_playlist_conversion)
                    self.process_ytv_play_list_thread.start()
                    self.hide_show_play_pause_button(hide=False)
            else:
                if context["quality"] == "select":
                    self.popup_message(title="No Audio/Video Playlist To Download!",
                                       message="Please Select YouTube Video From The Home Tab.")
                else:
                    self.popup_message(title="Invalid Youtube Url", message="Please check your YT video url !")

    def block_pro_plan_for_playlist(self):
        if self.ui.select_quality_playlist_2.currentText() in ['144p (LD)', '240p (LD)', '360p (SD)']\
                and self.ui.select_type_playlist_2.currentText() == 'VIDEO - MP4' and \
                self.ui.select_videos_playlist_2.currentText() != "Select All":
            return True
        else:
            response = self.check_your_plan()
        return response

    def tc_process_download_playlist(self, value_dict):
        if value_dict.get("complete_playlist"):
            counter = value_dict.get("counter")
            display_status = "Video {0} of {1}:     ({2}%) Completed: {3} of {4}        " \
                             "Speed: @{5}{6}".format(counter,
                                                     self.total_videos,
                                                     value_dict.get("progress"),
                                                     value_dict.get("downloaded"),
                                                     value_dict.get("total_size"),
                                                     self.speed,
                                                     self.unit)
            self.ui.progress_bar.setRange(0, self.total_videos)
            self.ui.progress_bar.setFormat(display_status)
            self.ui.progress_bar.setValue(counter)
        else:
            if not value_dict.get("is_killed"):
                display_status = "({0}%) Completed: {1} of {2}               " \
                                 "Speed: @{3}{4}".format(value_dict.get("progress"),
                                                         value_dict.get("downloaded"),
                                                         value_dict.get("total_size"),
                                                         self.speed,
                                                         self.unit)

                self.ui.progress_bar.setRange(0, 100)
                self.ui.progress_bar.setFormat(display_status)
                self.ui.progress_bar.setValue(value_dict.get("progress"))
            else:
                self.progress_bar_disable()

    def ffmpeg_playlist_conversion(self, value_dict):
        self.hide_show_play_pause_button(hide=True)
        if value_dict.get("complete_playlist"):
            file_type = value_dict.get("type")
            counter = value_dict.get("counter")
            if file_type == "AUDIO - MP3":
                display_status = "Converting Audio {0} of {1}".format(counter, self.total_videos)
            else:
                display_status = "Converting Video {0} of {1}".format(counter, self.total_videos)
            self.ui.progress_bar.setRange(0, self.total_videos)
            self.ui.progress_bar.setFormat(display_status)
            self.ui.progress_bar.setValue(counter)
        else:
            if not value_dict.get("is_killed"):
                self.ui.progress_bar.resetFormat()
                self.ui.progress_bar.setRange(0, 100)
                self.ui.progress_bar.setValue(value_dict.get("progress"))
            else:
                self.progress_bar_disable()

    def setProgressVal_playlist(self, yt_playlist):
        if yt_playlist.get("status"):
            yt_video_data = yt_playlist.get("video_context")
            if yt_video_data:
                self.total_videos = yt_playlist.get("playlist_length")
                self.get_videos_list = GetPlaylistVideos(True, yt_playlist["playlist_videos"],
                                                         self.Default_loc_playlist)
                self.get_videos_list.get_video_list.connect(self.set_video_list)
                self.get_videos_list.partial_finish.connect(self.partial_finish)
                self.get_videos_list.finished_video_list.connect(self.finish_video_list)
                self.get_videos_list.partial_progress.connect(self.partial_progress_format)
                self.get_videos_list.start()
            else:
                self.progress_bar_disable()
                self.popup_message(title="Invalid Youtube Playlist Url", message="Please check your Playlist link !")
                return

            if yt_video_data.get("status"):
                self.hide_show_playlist_initial_banner(show=True)
                self.playlist = yt_playlist.get("playlist")
                self.playlist_title = yt_playlist.get("playlist_title")
                self.total_videos = yt_playlist.get("playlist_length")
                self.watch_url_playlist = yt_playlist.get("playlist_url", "")
                self.thumbnail_path_playlist, title, total_videos = process_html_data_playlist(yt_playlist, self.Default_loc_playlist)
                self.ui.textBrowser_playlist_thumbnail.setVisible(False)
                self.ui.graphicsView_playlist.setVisible(True)
                self.ui.video_title_playlist.setText(f"{title}")
                self.ui.video_length_playlist.setText(f"Calculating..")
                self.ui.video_total_playlist.setText(f"{total_videos}")
                self.ui.video_size_playlist.setText(f"Calculating..")
                self.ui.watch_url_playlist.setText(f"<html><head/><body><p><a href='{self.watch_url_playlist}'>"
                                                   f"<span style=' text-decoration: none; "
                                                   f"color:#4e9a06;'>{self.watch_url_playlist}</span></a></p></body></html>")
                self.ui.by_channel_playlist.setText(yt_playlist.get("video_context", {}).get("channel", ""))
                self.ui.views_playlist.setText(human_format(yt_playlist.get("video_context", {}).get("views", "")))
                self.ui.descriptions_playlist.setText(yt_playlist.get("video_context", {}).get("description", ""))
                all_format, all_quality_playlist, all_fps = yt_video_data.get("quality_data")
                self.ui.select_quality_playlist_2.addItems(all_quality_playlist)
                self.ui.select_type_playlist_2.addItems(["VIDEO - MP4", "AUDIO - MP3"])
                icon1 = QtGui.QIcon()
                icon1.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-ok-144.png"), QtGui.QIcon.Normal,
                                QtGui.QIcon.Off)
                self.ui.select_quality_playlist_2.setItemIcon(0, icon1)
                icon2 = QtGui.QIcon()
                icon2.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"), QtGui.QIcon.Normal,
                                QtGui.QIcon.Off)
                self.ui.select_type_playlist_2.setItemIcon(0, icon2)
                self.ui.stackedWidget.setCurrentIndex(2)
                self.setPhoto_playlist(QPixmap(self.thumbnail_path_playlist))
                self.ui.dock_back_home.setEnabled(True)
                self.ui.dock_home.setEnabled(True)
            else:
                self.progress_bar_disable()
                self.popup_message(title="Invalid Youtube Playlist Url", message="Please check your Playlist link !")
        else:
            self.progress_bar_disable()
            if not self.pytube_status:
                self.popup_message(title="Application is in Schedule Maintenance",
                                   message="Video Downloading Option Is Not Available Right Now."
                                           " We Are Pushing New Updates, Please Check In A While."
                                           "\n\nNote: You Can Still Play Videos In The App. Sorry For The Inconvenience.")
            else:
                self.popup_message(title="Invalid Youtube Playlist Url", message="Please check your Playlist link !")

    def set_video_list(self, play_list_videos):
        if self.play_list_counter > self.total_videos:
            display_status = "Loading Video {0} of {1}".format(self.total_videos, self.total_videos)
        else:
            display_status = "Loading Video {0} of {1}".format(self.play_list_counter, self.total_videos)
        self.ui.progress_bar.setRange(0, self.total_videos)
        self.ui.progress_bar.setFormat(display_status)
        self.ui.progress_bar.setValue(self.play_list_counter)
        self.ui.select_videos_playlist_2.addItem(play_list_videos)
        icon = QtGui.QIcon()
        if play_list_videos == "Select All":
            if not self.is_plan_active:
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-lock-96.png"), QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
            else:
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-double-tick-100.png"), QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
        else:
            icon.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.ui.select_videos_playlist_2.setItemIcon(self.play_list_counter - 1, icon)
        self.play_list_counter += 1

    def partial_finish(self):
        self.progress_bar_enable()

    def partial_progress_format(self, size_dict):
        self.ui.progress_bar.resetFormat()
        v_index = size_dict.get("counter", 1)
        display_status = "Fetching Video Quality {0} of {1}".format(v_index, self.total_videos)
        self.ui.progress_bar.setRange(0, self.total_videos)
        self.ui.progress_bar.setFormat(display_status)
        self.ui.progress_bar.setValue(v_index)

    def finish_video_list(self, playlist_quality_dict):
        self.total_obj = playlist_quality_dict.get("total_obj")
        self.playlist_urls = playlist_quality_dict.get("playlist_urls")
        self.ui.select_videos_playlist_2.setEnabled(True)
        self.ui.select_quality_playlist_2.setEnabled(True)
        self.ui.select_type_playlist_2.setEnabled(True)
        self.ui.select_quality_playlist_2.clear()
        self.ui.select_type_playlist_2.clear()
        all_format = playlist_quality_dict.get("all_format")
        all_quality = playlist_quality_dict.get("all_quality")

        for index, item in enumerate(all_quality):
            self.ui.select_quality_playlist_2.addItem(item)
            icon = QtGui.QIcon()
            if index in [0, 1, 2]:
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-ok-144.png"), QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
            else:
                if not self.is_plan_active:
                    icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-lock-96.png"), QtGui.QIcon.Normal,
                                   QtGui.QIcon.Off)
                else:
                    icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-ok-144.png"), QtGui.QIcon.Normal,
                                   QtGui.QIcon.Off)
            self.ui.select_quality_playlist_2.setItemIcon(index, icon)

        for index, item in enumerate(all_format):
            self.ui.select_type_playlist_2.addItem(item)
            icon = QtGui.QIcon()
            if index == 0:
                icon.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"), QtGui.QIcon.Normal,
                               QtGui.QIcon.Off)
            else:
                if not self.is_plan_active:
                    icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-lock-96.png"), QtGui.QIcon.Normal,
                                   QtGui.QIcon.Off)
                else:
                    if index == 1:
                        icon.addPixmap(QtGui.QPixmap(":/myresource/resource/video_7.png"),
                                       QtGui.QIcon.Normal,
                                       QtGui.QIcon.Off)
                    else:
                        icon.addPixmap(QtGui.QPixmap(":/myresource/resource/icons8-music-120.png"), QtGui.QIcon.Normal,
                                       QtGui.QIcon.Off)
            self.ui.select_type_playlist_2.setItemIcon(index, icon)

        self.progress_bar_disable()

    def tc_finished_downloading_thread_playlist(self, json_data):
        if not json_data.get("is_killed"):
            title = json_data.get("title")
            self.hide_show_play_pause_button(hide=True)
            self.progress_bar_disable()
            folder_path = json_data.get("file_path")
            play_path = json_data.get("play_path")
            message = f"Download Success!\n\n{title}"
            self.file_download_success_dialog(message, folder_path, play_path)

    def tc_finished_downloading_thread_playlist_all(self, json_data):
        if not json_data.get("is_killed"):
            self.hide_show_play_pause_button(hide=True)
            self.progress_bar_disable()
            folder_path = json_data.get("file_path")
            play_path = json_data.get("play_path")
            all_videos_list = ["Download Success\n\n", f"Playlist Name: {self.playlist.title}\n\n"]

            for i in range(self.ui.select_videos_playlist_2.count()):
                v_title = self.ui.select_videos_playlist_2.itemText(i)
                if v_title != "Select All":
                    v_title = str(i) + ". " + v_title + "\n"
                    all_videos_list.append(v_title)

            res = "".join(all_videos_list)
            self.file_download_success_dialog(res, folder_path, play_path)

    def error_playlist(self, error_dict):
        self.hide_show_play_pause_button(hide=True)
        if error_dict.get("error") == "File Already Exists":
            file_path = error_dict.get("file_path")
            play_path = error_dict.get("play_path")
            file_title = error_dict.get("file")
            if file_path and play_path:
                self.file_download_success_dialog(f"File Already in your Downloads!\n\n{file_title}", file_path,
                                                  play_path)
            else:
                self.popup_message(title="File Already Exists", message=error_dict.get("error"))
        else:
            self.popup_message(title="Error Occurred", message=error_dict.get("error"))

    def tc_after_kill_playlist(self, unfinished_file_path):
        try:
            self.progress_bar_disable()
            os.remove(unfinished_file_path)
        except Exception as e:
            pass

    def show_video_thumbnail(self):
        try:
            process_ytv_playlist_thread = self.process_ytv_playlist_thread.isRunning()
        except Exception as e:
            process_ytv_playlist_thread = False
        try:
            get_videos_list = self.get_videos_list.isRunning()
        except Exception as e:
            get_videos_list = False

        if not process_ytv_playlist_thread and not get_videos_list:
            try:
                title_text = self.ui.select_videos_playlist_2.currentText()
                if title_text not in ["Select All", None, ""]:
                    index = self.ui.select_videos_playlist_2.currentIndex()
                    yt_play_list_obj = self.total_obj[index - 1]
                    thumbnail_url = yt_play_list_obj.thumbnail_url
                    thumbnail_image_path = get_thumbnail_path_from_local(title_text, thumbnail_url,
                                                                         self.Default_loc_playlist)
                    self.ui.textBrowser_playlist_thumbnail.setPixmap(QPixmap(thumbnail_image_path))
                    self.ui.video_title_playlist.setText(f"{title_text}")
                    self.ui.video_total_playlist.setText(f"{str(self.total_videos)}")
            except Exception as e:
                pass
            if self.ui.select_videos_playlist_2.currentText() in ["", None]:
                pass
            else:
                if len(PLAYLIST_SIZE_CACHE) != 0:
                    title = safe_string(self.ui.select_videos_playlist_2.currentText())
                    quality = safe_string(self.ui.select_quality_playlist_2.currentText())
                    p_type = safe_string(self.ui.select_type_playlist_2.currentText())

                    if PLAYLIST_SIZE_CACHE.get(f"{title}{quality}{p_type}") is not None:
                        values_dict = PLAYLIST_SIZE_CACHE.get(f"{title}{quality}{p_type}")
                        video_size = values_dict.get("video_size", "N/A")
                        video_length = values_dict.get("video_length", "N/A")
                        if video_size or video_length:
                            self.ui.video_size_playlist.setText(f"{video_size}")
                            title_text = self.ui.select_videos_playlist_2.currentText()
                            if title_text in ["Select All", None, ""]:
                                self.ui.video_title_playlist.setText(f"{self.playlist_title}")
                            else:
                                self.ui.video_title_playlist.setText(
                                    f"{self.ui.select_videos_playlist_2.currentText()}")
                            self.ui.video_total_playlist.setText(f"{str(self.total_videos)}")
                            self.ui.video_length_playlist.setText(f"{video_length}")
                        self.progress_bar_disable()
                    else:
                        self.file_size_thread = FileSizeThread(self, self)
                        self.file_size_thread.get_size_of_file.connect(self.set_file_size)
                        self.file_size_thread.start()
                        self.progress_bar_enable()
                else:
                    self.file_size_thread = FileSizeThread(self, self)
                    self.file_size_thread.get_size_of_file.connect(self.set_file_size)
                    self.file_size_thread.start()
                    self.progress_bar_enable()

    def set_file_size(self, size_dict):
        global PLAYLIST_SIZE_CACHE
        title = safe_string(self.ui.select_videos_playlist_2.currentText())
        quality = safe_string(self.ui.select_quality_playlist_2.currentText())
        p_type = safe_string(self.ui.select_type_playlist_2.currentText())
        PLAYLIST_SIZE_CACHE[f"{title}{quality}{p_type}"] = size_dict
        video_size = size_dict.get("video_size")
        video_length = size_dict.get("video_length")

        if video_size or video_length:
            self.ui.video_size_playlist.setText(f"{video_size}")
            title_text = self.ui.select_videos_playlist_2.currentText()
            if title_text in ["Select All", None, ""]:
                self.ui.video_title_playlist.setText(f"{self.playlist_title}")
            else:
                self.ui.video_title_playlist.setText(f"{self.ui.select_videos_playlist_2.currentText()}")
            self.ui.video_total_playlist.setText(f"{str(self.total_videos)}")
            self.ui.video_length_playlist.setText(f"{video_length}")

        self.progress_bar_disable()

    def check_for_audio_only_playlist(self):
        try:
            process_ytv_playlist_thread = self.process_ytv_playlist_thread.isRunning()
        except Exception as e:
            process_ytv_playlist_thread = False
        try:
            get_videos_list = self.get_videos_list.isRunning()
        except Exception as e:
            get_videos_list = False

        if not process_ytv_playlist_thread and not get_videos_list:
            if self.ui.select_type_playlist_2.currentText() == "AUDIO - MP3":
                self.ui.select_quality_playlist_2.setEnabled(False)
            elif self.ui.select_type_playlist_2.currentText() in ['VIDEO - MP4', 'VIDEO - WEBM']:
                self.ui.select_quality_playlist_2.setEnabled(True)

            if self.ui.select_videos_playlist_2.currentText() in ["", None]:
                pass
            else:
                try:
                    file_size_thread_running = self.file_size_thread.isRunning()
                except Exception as e:
                    file_size_thread_running = False
                if not file_size_thread_running:
                    self.file_size_thread = FileSizeThread(self, self)
                    self.file_size_thread.get_size_of_file.connect(self.set_file_size)
                    self.file_size_thread.start()
                    self.progress_bar_enable()

    """
        Downloads functionality:--------------------------------------------------
    """

    def clear_all_history(self):
        try:
            self.msg = QMessageBox()
            self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
            self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
            self.msg.setIcon(QMessageBox.Information)
            self.msg.setText("Are you sure want to clear all videos and playlist history?")
            cb = QCheckBox("Delete all Source file too")
            cb.setChecked(self.delete_source_file)
            self.msg.setCheckBox(cb)
            yes_button = self.msg.addButton(QMessageBox.Yes)
            no_button = self.msg.addButton(QMessageBox.No)
            self.msg.exec_()
            if self.msg.clickedButton() == yes_button:
                if cb.isChecked():
                    self.delete_source_file = True
                    self.clear_download_history_all()
                else:
                    self.delete_source_file = False
                    self.clear_download_history_all()
                self.get_user_download_data()
            if self.msg.clickedButton() == no_button:
                if cb.isChecked():
                    self.delete_source_file = True
                else:
                    self.delete_source_file = False

        except Exception as e:
            self.popup_message(title="Error while deleting the file!", message="", error=True)
            pass

    def clear_download_history_all(self):
        try:
            video_history_path = self.Default_loc + "/TUBE2GO/.downloads/download_data.json"
            os.remove(video_history_path)
        except Exception as e:
            pass
        try:
            playlist_history_path = self.Default_loc_playlist + "/TUBE2GO/.downloads/download_data.json"
            os.remove(playlist_history_path)
        except Exception as e:
            pass
        if self.delete_source_file:
            try:
                video_file_path = self.Default_loc + "/TUBE2GO"
                shutil.rmtree(video_file_path)
            except Exception as e:
                pass
            try:
                playlist_video_path = self.Default_loc_playlist + "/TUBE2GO"
                shutil.rmtree(playlist_video_path)
            except Exception as e:
                pass

    def set_file_downloaded_filter(self):
        self.downloaded_file_filter = "_".join(str(self.ui.filter_by.currentText()).lower().split(" "))
        self.ui.search_videos.clear()
        self.download_search_map_list = []
        self.get_user_download_data()

    def get_user_download_data(self):
        try:
            self.ui.listWidget.clear()
            size = QtCore.QSize()
            size.setHeight(100)
            size.setWidth(100)
            if self.downloaded_file_filter == "all_files":
                if self.Default_loc == self.Default_loc_playlist:
                    user_json_data = get_local_download_data(self.Default_loc)
                else:
                    user_json_data = get_local_download_data(self.Default_loc) + get_local_download_data(
                        self.Default_loc_playlist)
            elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
                user_json_data = get_local_download_data(self.Default_loc_playlist)
            else:
                user_json_data = get_local_download_data(self.Default_loc)
            if user_json_data:
                self.hide_show_download_initial_banner(show=True)
            else:
                self.hide_show_download_initial_banner(show=False)
            user_json_data = sorted(user_json_data, key=lambda k: k['sort_param'], reverse=True)
            exist_entry = [self.ui.listWidget.item(x).text() for x in range(self.ui.listWidget.count())]
            filter_user_json_data = get_downloaded_data_filter(user_json_data, self.downloaded_file_filter)
            for row in filter_user_json_data:
                thumbnail_path = row.get("thumbnail_path")
                if not os.path.isfile(thumbnail_path):
                    thumbnail_path = ":/myresource/resource/download_preview.png"
                title = row.get("title_show")
                file_type = str(row.get("type")).upper()
                resolution = str(row.get("resolution")).upper()
                subtype = str(row.get("subtype")).upper()
                length = row.get("length")
                file_size = row.get("size")
                if file_type == "AUDIO":
                    details = f"{title}\n🇦​​​​​🇺​​​​​🇩​​​​​🇮​​​​​🇴​​​​​\nSize: {file_size}\nLength: {length}"
                else:
                    details = f"{title}\n🇻​​​​​🇮​​​​​🇩​​​​​🇪​​​​​🇴​​​​​-{resolution}-{subtype}\nSize: {file_size}\nLength: {length}"

                if details not in exist_entry:
                    icon = QtGui.QIcon()
                    icon.addPixmap(QtGui.QPixmap(thumbnail_path), QtGui.QIcon.Normal, QtGui.QIcon.Off)
                    item = QtWidgets.QListWidgetItem(icon, details)
                    item.setSizeHint(size)
                    self.ui.listWidget.addItem(item)
            self.ui.listWidget.setIconSize(QtCore.QSize(150, 150))
        except Exception as e:
            self.popup_message(title="Error while getting download history!", message="", error=True)
            pass

    def show_downloads_folder(self):
        try:
            if self.downloaded_file_filter == "all_files":
                if self.Default_loc == self.Default_loc_playlist:
                    user_json_data = get_local_download_data(self.Default_loc)
                else:
                    user_json_data = get_local_download_data(self.Default_loc) + get_local_download_data(
                        self.Default_loc_playlist)
            elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
                user_json_data = get_local_download_data(self.Default_loc_playlist)
            else:
                user_json_data = get_local_download_data(self.Default_loc)
            user_json_data = get_downloaded_data_filter(user_json_data, self.downloaded_file_filter)
            user_json_data = sorted(user_json_data, key=lambda k: k['sort_param'], reverse=True)
            c_index = self.ui.listWidget.currentIndex().row()
            if c_index != -1:
                selected_video = user_json_data[c_index]
                download_path = selected_video.get("download_path")
                if not os.path.isdir(download_path):
                    self.popup_message(title="Directory not found!", message="", error=True)
                else:
                    QDesktopServices.openUrl(QUrl(download_path))
            else:
                self.popup_message(title="Please select file first!", message="", error=True)
        except Exception as e:
            self.popup_message(title="Error while opening the directory!", message="", error=True)
            pass

    def play_videos_from_downloads(self):
        try:
            if self.downloaded_file_filter == "all_files":
                if self.Default_loc == self.Default_loc_playlist:
                    user_json_data = get_local_download_data(self.Default_loc)
                else:
                    user_json_data = get_local_download_data(self.Default_loc) + get_local_download_data(
                        self.Default_loc_playlist)
            elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
                user_json_data = get_local_download_data(self.Default_loc_playlist)
            else:
                user_json_data = get_local_download_data(self.Default_loc)
            user_json_data = get_downloaded_data_filter(user_json_data, self.downloaded_file_filter)
            user_json_data = sorted(user_json_data, key=lambda k: k['sort_param'], reverse=True)
            c_index = self.ui.listWidget.currentIndex().row()
            if c_index != -1:
                if len(self.download_search_map_list) > 0:
                    selected_video = self.download_search_map_list[c_index]
                else:
                    selected_video = user_json_data[c_index]
                file_path = selected_video.get("file_path")
                if not os.path.isfile(file_path):
                    self.popup_message(title="File not found or deleted!", message="", error=True)
                else:
                    QDesktopServices.openUrl(QUrl(file_path))
            else:
                self.popup_message(title="Please select file first!!", message="", error=True)
        except Exception as e:
            self.popup_message(title="Error while playing the media!", message="", error=True)
            pass

    def play_videos_mpv_from_downloads(self):
        try:
            if self.downloaded_file_filter == "all_files":
                if self.Default_loc == self.Default_loc_playlist:
                    user_json_data = get_local_download_data(self.Default_loc)
                else:
                    user_json_data = get_local_download_data(self.Default_loc) + get_local_download_data(
                        self.Default_loc_playlist)
            elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
                user_json_data = get_local_download_data(self.Default_loc_playlist)
            else:
                user_json_data = get_local_download_data(self.Default_loc)
            user_json_data = get_downloaded_data_filter(user_json_data, self.downloaded_file_filter)
            user_json_data = sorted(user_json_data, key=lambda k: k['sort_param'], reverse=True)
            c_index = self.ui.listWidget.currentIndex().row()
            if c_index != -1:
                if len(self.download_search_map_list) > 0:
                    selected_video = self.download_search_map_list[c_index]
                else:
                    selected_video = user_json_data[c_index]
                file_path = selected_video.get("file_path")
                if not os.path.isfile(file_path):
                    self.popup_message(title="File not found or deleted!", message="", error=True)
                else:
                    self.process = QProcess()
                    self.mpv_arguments = []
                    if self.after_playback_action == "loop_play":
                        self.mpv_arguments.append("--loop")
                    self.mpv_arguments.append("--force-window")
                    self.mpv_arguments.append(file_path)
                    self.mpv_arguments.append("--title={0}".format(selected_video.get("title_show", PRODUCT_NAME)))
                    self.mpv_arguments.append("--gpu-context=x11")
                    self.process.start("mpv", self.mpv_arguments)
            else:
                self.popup_message(title="Please select file first!!", message="", error=True)
        except Exception as e:
            self.popup_message(title="Error while playing the media!", message="", error=True)
            pass

    def details_video_from_downloads(self):
        try:
            c_index = self.ui.listWidget.currentIndex().row()
            if c_index != -1:
                if self.downloaded_file_filter == "all_files":
                    if self.Default_loc == self.Default_loc_playlist:
                        video_info = get_local_download_data(self.Default_loc)
                    else:
                        video_info = get_local_download_data(self.Default_loc) + get_local_download_data(
                            self.Default_loc_playlist)
                elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
                    video_info = get_local_download_data(self.Default_loc_playlist)
                else:
                    video_info = get_local_download_data(self.Default_loc)
                video_info = get_downloaded_data_filter(video_info, self.downloaded_file_filter)
                video_info = sorted(video_info, key=lambda k: k['sort_param'], reverse=True)
                if len(self.download_search_map_list) > 0:
                    video_info = self.download_search_map_list[c_index]
                else:
                    video_info = video_info[c_index]
                title = video_info.get("title_show", "-")
                length = video_info.get("length", "-")
                author = video_info.get("author", "-")
                v_type = video_info.get("type", "-")
                if v_type == "video":
                    fps = video_info.get("fps", "-")
                    resolution = video_info.get("resolution", "-")
                    subtype = video_info.get("subtype", "-")
                else:
                    fps = "N/A"
                    resolution = "N/A"
                    subtype = "MP3"
                size = video_info.get("size", "-")
                url = video_info.get("url", "-")
                download_date = video_info.get("download_date", "-")
                download_time = video_info.get("download_time", "-")
                all_videos_list = [
                    f"From Channel -      {str(author).upper()}\n"
                    f"File Type -     {str(v_type).upper()}\n"
                    f"Length -        {length}\n"
                    f"Resolution -        {str(resolution).upper()}\n"
                    f"Format -        {str(subtype).upper()}\n"
                    f"FPS -       {fps}\n"
                    f"Size -      {size}\n"
                    f"Watch URL -     {url}\n"
                    f"Downloaded On -     {download_date} {download_time}"]
                res = "".join(all_videos_list)
                self.popup_message(f"Title | {title}", res)
            else:
                self.popup_message(title="Please select file first!", message="", error=True)
        except Exception as e:
            self.popup_message(title="Error while getting details!", message="", error=True)
            pass

    def delete_video_from_downloads(self):
        try:
            self.msg = QMessageBox()
            self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
            self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
            self.msg.setIcon(QMessageBox.Information)
            c_index = self.ui.listWidget.currentIndex().row()
            if c_index != -1:
                current_file_to_delete = self.ui.listWidget.currentItem().text()
                self.msg.setText(f"Are you sure want to delete ?\n\n{current_file_to_delete}")
                cb = QCheckBox("Delete Source file too")
                cb.setChecked(self.delete_source_file)
                self.msg.setCheckBox(cb)
                yes_button = self.msg.addButton(QMessageBox.Yes)
                no_button = self.msg.addButton(QMessageBox.No)
                self.msg.exec_()
                if self.msg.clickedButton() == yes_button:
                    if cb.isChecked():
                        self.delete_source_file = True
                        self.delete_entry_from_list(delete_source_file=True)
                    else:
                        self.delete_source_file = False
                        self.delete_entry_from_list()
                if self.msg.clickedButton() == no_button:
                    if cb.isChecked():
                        self.delete_source_file = True
                    else:
                        self.delete_source_file = False
            else:
                self.popup_message(title="Please select file first!", message="", error=True)
        except Exception as e:
            self.popup_message(title="Error while deleting the file!", message="", error=True)
            pass

    def delete_entry_from_list(self, delete_source_file=False):
        if self.downloaded_file_filter == "all_files":
            if self.Default_loc == self.Default_loc_playlist:
                video_info = get_local_download_data(self.Default_loc)
            else:
                video_info = get_local_download_data(self.Default_loc) + get_local_download_data(
                    self.Default_loc_playlist)
        elif self.downloaded_file_filter in ["playlist_video", "playlist_audio"]:
            video_info = get_local_download_data(self.Default_loc_playlist)
        else:
            video_info = get_local_download_data(self.Default_loc)
        video_info_without_filter = deepcopy(video_info)
        c_index = self.ui.listWidget.currentIndex().row()
        if c_index != -1:
            video_info = get_downloaded_data_filter(video_info, self.downloaded_file_filter)
            video_info = sorted(video_info, key=lambda k: k['sort_param'], reverse=True)
            if self.downloaded_file_filter != "all_files":
                video_info_copy = video_info_without_filter
            else:
                video_info_copy = deepcopy(video_info)
            if len(self.download_search_map_list) > 0:
                poped_item = self.download_search_map_list.pop(c_index)
            else:
                poped_item = video_info.pop(c_index)
            poped_item_copy_index = video_info_copy.index(poped_item)
            video_info_copy.pop(poped_item_copy_index)
            delete_location = str(poped_item.get("download_path")).split("TUBE2GO")[0]
            video_info_copy_1 = []
            for item_dict in video_info_copy:
                if delete_location in item_dict.get("download_path"):
                    video_info_copy_1.append(item_dict)
            save_after_delete(video_info_copy_1, delete_location)
            self.ui.listWidget.clear()
            self.ui.search_videos.clear()
            self.get_user_download_data()
            if delete_source_file:
                try:
                    file_path = poped_item.get("file_path")
                    os.remove(file_path)
                except Exception as e:
                    pass
        else:
            self.popup_message(title="Please select file first!", message="", error=True)

    def search_videos(self):
        try:
            search_string = self.ui.search_videos.text()
            if search_string in ["", None]:
                self.ui.filter_by.setCurrentIndex(0)
                self.downloaded_file_filter = "all_files"

            if self.Default_loc == self.Default_loc_playlist:
                video_info = get_local_download_data(self.Default_loc)
            else:
                video_info = get_local_download_data(self.Default_loc) + get_local_download_data(
                    self.Default_loc_playlist)
            video_info = sorted(video_info, key=lambda k: k['sort_param'], reverse=True)
            exist_entry = [x.get("title_show") for x in video_info]
            index = -1
            flag = 0
            index_list = set()
            for entry in exist_entry:
                index += 1
                if search_string.lower() in entry.lower():
                    index_list.add(index)
                    flag = 1
            if flag == 0:
                pass
            else:
                self.ui.listWidget.clear()
                size = QtCore.QSize()
                size.setHeight(100)
                size.setWidth(100)
                self.download_search_map_list = []
                for number in range(0, len(video_info)):
                    if number in index_list:
                        row = video_info[number]
                        self.download_search_map_list.append(row)
                        thumbnail_path = row.get("thumbnail_path")
                        if not os.path.isfile(thumbnail_path):
                            thumbnail_path = ":/myresource/resource/download_preview.png"
                        title = row.get("title_show")
                        file_type = str(row.get("type")).upper()
                        resolution = str(row.get("resolution")).upper()
                        subtype = str(row.get("subtype")).upper()
                        length = row.get("length")
                        file_size = row.get("size")
                        if file_type == "AUDIO":
                            details = f"{title}\n🇦​​​​​🇺​​​​​🇩​​​​​🇮​​​​​🇴​​​​​\nSize: {file_size}\nLength: {length}"
                        else:
                            details = f"{title}\n🇻​​​​​🇮​​​​​🇩​​​​​🇪​​​​​🇴​​​​​-{resolution}-{subtype}\nSize: {file_size}\nLength: {length}"

                        if details not in exist_entry:
                            icon = QtGui.QIcon()
                            icon.addPixmap(QtGui.QPixmap(thumbnail_path), QtGui.QIcon.Normal, QtGui.QIcon.Off)
                            item = QtWidgets.QListWidgetItem(icon, details)
                            item.setSizeHint(size)
                            self.ui.listWidget.addItem(item)
                self.ui.listWidget.setIconSize(QtCore.QSize(150, 150))
        except Exception as e:
            self.popup_message(title="Error while searching the files!", message="", error=True)
            pass

    def clear_search_bar_on_edit(self):
        if self.ui.search_videos.text() == "Search Download History":
            self.ui.search_videos.clear()

    """
            About page functionality ===================================================================================
    """

    def pro_plan_hide_plan_compare_chart(self):
        self.ui.groupBox.setVisible(False)
        self.ui.groupBox_2.setVisible(True)
        self.ui.purchase_licence_2.setVisible(False)
        self.ui.refresh_account_2.setVisible(False)

    def redirect_to_warlordsoft(self):
        warlord_soft_link = "https://warlordsoftwares.in/"
        webbrowser.open(warlord_soft_link)

    def redirect_to_paypal_donation(self):
        paypal_donation_link = "https://www.paypal.com/paypalme/rishabh3354/5"
        webbrowser.open(paypal_donation_link)

    def ge_more_apps(self):
        paypal_donation_link = "https://snapcraft.io/search?q=rishabh"
        webbrowser.open(paypal_donation_link)

    def redirect_to_rate_snapstore(self):
        QDesktopServices.openUrl(QUrl("snap://tube2go"))

    def redirect_to_feedback_button(self):
        feedback_link = "https://warlordsoftwares.in/contact_us/"
        webbrowser.open(feedback_link)

    def purchase_details_after_payment(self):
        if check_internet_connection():
            account_dict = get_user_data_from_local()
            if account_dict:
                account_id = str(account_dict.get("email")).split("@")[0]
                if account_id:
                    warlord_soft_link = f"https://warlordsoftwares.in/warlord_soft/subscription/?product={PRODUCT_NAME}&account_id={account_id} "
                else:
                    warlord_soft_link = f"https://warlordsoftwares.in/warlord_soft/dashboard/"
                webbrowser.open(warlord_soft_link)
                time.sleep(5)
                webbrowser.open("https://warlordsoftwares.in/warlord_soft/your_plan/")
        else:
            self.popup_message(title="No internet connection", message="Please check your internet connection!")

    def purchase_licence_2(self):
        if check_internet_connection():
            account_dict = get_user_data_from_local()
            if account_dict:
                account_id = str(account_dict.get("email")).split("@")[0]
                if account_id:
                    warlord_soft_link = f"https://warlordsoftwares.in/warlord_soft/subscription/?product={PRODUCT_NAME}&account_id={account_id} "
                else:
                    warlord_soft_link = f"https://warlordsoftwares.in/signup/"
                webbrowser.open(warlord_soft_link)
                data = dict()
                data["email"] = f"{account_id}@warlordsoft.in"
                data["password"] = f"{account_id}@warlordsoft.in"
                data["re_password"] = f"{account_id}@warlordsoft.in"
                self.save_token = SaveLocalInToken(data)
                self.save_token.start()
        else:
            self.popup_message(title="No internet connection", message="Please check your internet connection!")

    def sync_account_id_with_warlord_soft(self):
        try:
            if check_internet_connection():
                account_dict = get_user_data_from_local()
                if account_dict:
                    account_id = str(account_dict.get("email")).split("@")[0]
                    data = dict()
                    data["sync_url"] = f"warlord_soft/subscription/?product={PRODUCT_NAME}&account_id={account_id}"
                    data["email"] = f"{account_id}@warlordsoft.in"
                    data["password"] = f"{account_id}@warlordsoft.in"
                    data["re_password"] = f"{account_id}@warlordsoft.in"
                    self.sync_account = SyncAccountIdWithDb(data)
                    self.sync_account.start()
        except Exception as e:
            print(e)
            pass

    def refresh_account_2(self):
        self.ui.error_message.clear()
        self.ui.account_progress_bar.setRange(0, 0)
        self.refresh_thread = RefreshButtonThread(PRODUCT_NAME, self)
        self.refresh_thread.change_value_refresh.connect(self.after_refresh)
        self.refresh_thread.start()

    def after_refresh(self, response_dict):
        if response_dict.get("status"):
            user_plan_data = get_user_data_from_local()
            if user_plan_data:
                self.logged_in_user_plan_page(user_plan_data)
        else:
            self.ui.error_message.setText(response_dict.get("message"))
        self.ui.account_progress_bar.setRange(0, 1)

    def my_plan(self):
        token = check_for_local_token()
        if token not in [None, ""]:
            user_plan_data = get_user_data_from_local()
            if user_plan_data:
                self.logged_in_user_plan_page(user_plan_data)
            else:
                user_plan_data = dict()
                user_plan_data['plan'] = "N/A"
                user_plan_data['expiry_date'] = "N/A"
                user_plan_data['email'] = "N/A"
                self.logged_in_user_plan_page(user_plan_data)
        else:
            user_plan_data = get_user_data_from_local()
            if user_plan_data:
                self.logged_in_user_plan_page(user_plan_data)

    def check_pytube_issue(self):
        if check_internet_connection():
            self.pytube_status_thread = PytubeStatusThread(PRODUCT_NAME, self)
            self.pytube_status_thread.change_value_pytube_status.connect(self.get_pytube_response)
            self.pytube_status_thread.start()

    def get_pytube_response(self, context):
        try:
            if context["response"]:
                if context["title"] == "Video Downloading Option Is Not Available Right Now! (Schedule Maintenance).":
                    self.pytube_status = False
                self.popup_message(context["title"], str(context["message"]).replace('\\n', '\n'))
        except Exception as e:
            pass

    def logged_in_user_plan_page(self, user_plan_data):
        self.ui.groupBox_2.setVisible(False)
        account_email = user_plan_data.get('email')
        plan = user_plan_data.get("plan", "N/A")
        expiry_date = user_plan_data.get("expiry_date")
        if account_email:
            account_id = str(account_email).split("@")[0]
            self.ui.lineEdit_account_id_2.setText(account_id)
        else:
            self.ui.lineEdit_account_id_2.setText("N/A")
        if plan == "Free Trial":
            self.ui.lineEdit_plan_2.setText("Evaluation")
        elif plan == "Life Time Free Plan":
            self.ui.purchase_details.setEnabled(True)
            self.ui.purchase_licence_2.setEnabled(False)
            self.ui.refresh_account_2.setEnabled(False)
            self.ui.lineEdit_plan_2.setText(plan)
            self.pro_plan_hide_plan_compare_chart()
            if self.one_time_congratulate:
                self.ui.account_progress_bar.setRange(0, 1)
                self.popup_message(title="Congratulations! Plan Upgraded to PRO",
                                   message="Your plan has been upgraded to PRO. Enjoy lifetime licence. "
                                           "Thankyou for your purchase.\n\nPLEASE RESTART YOUR APP TO SEE CHANGES.")
                self.one_time_congratulate = False
        else:
            self.ui.purchase_licence_2.setText("UPGRADE PLAN")
            self.ui.lineEdit_plan_2.setText(plan)
            self.ui.purchase_details.setEnabled(True)

        if expiry_date:
            if plan == "Life Time Free Plan":
                self.ui.lineEdit_expires_on_2.setText(f"{PRODUCT_NAME} PRO VERSION")
                self.is_plan_active = True
            else:
                plan_days_left = days_left(expiry_date)
                if plan_days_left == "0 Day(s) Left":
                    self.ui.error_message.setText("Evaluation period ended, Upgrade to Pro")
                    self.ui.lineEdit_expires_on_2.setText(plan_days_left)
                    self.is_plan_active = False
                else:
                    self.is_plan_active = True
                    self.ui.lineEdit_expires_on_2.setText(plan_days_left)
        else:
            self.ui.lineEdit_expires_on_2.setText("N/A")

    def check_your_plan(self):
        if not self.is_plan_active:
            self.msg = QMessageBox()
            self.msg.setWindowFlag(QtCore.Qt.FramelessWindowHint)
            self.msg.setStyleSheet("background-color:#263a4e;color:#eaeaea;")
            self.msg.setIcon(QMessageBox.Information)
            self.msg.setText("Evaluation period ended, Upgrade to Pro")
            self.msg.setInformativeText(
                "In TUBE2GO free version, HD+ video quality option is not available. But you can still download SD quality videos.\n"
                "Please support the developer and purchase a license to UNLOCK this feature.")
            purchase = self.msg.addButton(QMessageBox.Yes)
            close = self.msg.addButton(QMessageBox.Yes)
            purchase.setText('Purchase Licence')
            close.setText('Close')
            purchase.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton)))
            close.setIcon(QIcon(QApplication.style().standardIcon(QStyle.SP_BrowserStop)))
            self.msg.exec_()
            try:
                if self.msg.clickedButton() == purchase:
                    self.account_page()
                elif self.msg.clickedButton() == close:
                    pass
            except Exception as e:
                pass
            return False
        return True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())

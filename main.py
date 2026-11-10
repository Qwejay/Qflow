import os
import sys
import time
import random
import threading
import queue
import traceback
import json
import base64
import io
import math
import uuid
import ctypes
from ctypes import wintypes
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageGrab, ImageChops, ImageDraw, ImageStat
import pyautogui
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController
import copy
from datetime import datetime
from collections import namedtuple

__app_name__   = "Qflow"
__version__    = "3.0.0"
__author__     = "QwejayHuang"
__company__    = "Qwesoft"
__description__= "可视化节点办公自动化引擎"

HAS_PYPERCLIP = HAS_OPENCV = HAS_AUDIO = HAS_PYSTRAY = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    print("⚠️ 提示: 未安装 pyperclip，键盘'粘贴模式'和剪贴板节点将不可用。")

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    print("⚠️ 警告: 未安装 opencv-python，高级图像识别功能受限。")

try:
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    HAS_AUDIO = True
except ImportError:
    print("⚠️ 提示: 未安装 pycaw 或 comtypes，声音检测节点将不可用。")

try:
    import pystray
    from pystray import MenuItem
    HAS_PYSTRAY = True
except ImportError:
    print("⚠️ 提示: 未安装 pystray，系统托盘功能将不可用。可执行 pip install pystray 安装。")

# 保留 PyAutoGUI 左上角紧急中止保护，避免自动化失控时无法手动打断。
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore

def init_dpi_awareness():
    """彻底关闭 Windows 系统的位图缩放插值，开启 1:1 物理清晰渲染"""
    if sys.platform.startswith('win'):
        try:
            # 优先使用 Windows 10 1703+ 的 Per-Monitor V2 (级别最高，彻底消除字体模糊发胖)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                # Windows 8.1 / 10 旧版 Per-Monitor (级别 2)
                shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    # Windows 系统级感知 (级别 1)
                    shcore.SetProcessDpiAwareness(1)
                except Exception:
                    try:
                        user32.SetProcessDPIAware()
                    except Exception:
                        pass

init_dpi_awareness()

def get_screen_dpi():
    """获取当前显示器的真实物理 DPI"""
    try:
        hdc = user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 = LOGPIXELSX
        user32.ReleaseDC(0, hdc)
        return dpi if dpi > 0 else 96
    except Exception:
        return 96

SCREEN_DPI = get_screen_dpi()
SCALE_FACTOR = max(0.5, min(4.0, SCREEN_DPI / 96.0))
SCALE_X = SCALE_Y = SCALE_FACTOR

def get_virtual_screen_geometry():
    try:
        return (
            user32.GetSystemMetrics(76),  # SM_XVIRTUALSCREEN
            user32.GetSystemMetrics(77),  # SM_YVIRTUALSCREEN
            user32.GetSystemMetrics(78),  # SM_CXVIRTUALSCREEN
            user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
        )
    except Exception:
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

VX, VY, VW, VH = get_virtual_screen_geometry()
Box = namedtuple('Box', 'left top width height')

def safe_float(value, default=0.0):
    try:
        val = float(value)
        return val if math.isfinite(val) else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    try:
        val = float(value)
        return int(val) if math.isfinite(val) else default
    except (ValueError, TypeError):
        return default

THEMES = {
    'Dark': {
        'bg_app': '#1B1C1F', 'bg_sidebar': '#232529', 'bg_canvas': '#151619', 'bg_panel': '#232529',
        'bg_node': '#2D3036', 'bg_header': '#363A42', 'bg_card': '#32363E', 'fg_title': '#F3F4F6',
        'fg_text': '#E5E7EB', 'fg_sub': '#9CA3AF', 'accent': '#4F9CF9', 'grid': '#23262B',
        'wire': '#6B7280', 'wire_active': '#FBBF24', 'socket': '#D1D5DB', 'btn_bg': '#3E434D',
        'input_bg': '#181A1E',
        'input_fg': '#F3F4F6', 'button_fg': '#F9FAFB', 'accent_fg': '#FFFFFF',
        'success': '#22C55E', 'success_fg': '#052E16', 'danger': '#EF4444', 'danger_fg': '#FFFFFF',
        'warning': '#F59E0B', 'warning_fg': '#1F2937', 'control': '#A855F7', 'sensor': '#F97316',
        'var_node': '#06B6D4', 'wire_hl': '#38BDF8', 'shadow': '#0D0E10',
        'hover': '#4B5262', 'select_box': '#38BDF8', 'active_border': '#38BDF8', 'marker': '#EF4444',
        'btn_hover': '#525866', 'hl_running': '#FACC15', 'hl_ok': '#22C55E', 'hl_fail': '#EF4444',
        'breakpoint': '#E11D48', 'log_bg': '#16181C', 'log_fg': '#D1D5DB', 'win_node': '#0D9488',
        'log_info': '#60A5FA', 'log_success': '#4ADE80', 'log_warning': '#FBBF24',
        'log_error': '#F87171', 'log_exec': '#9CA3AF', 'log_paused': '#FDE047',
        'tooltip_bg': '#2D3036', 'tooltip_fg': '#F3F4F6', 'node_header_fg': '#FFFFFF',
        'preview_bg': '#0F1012', 'overlay_bg': '#262930', 'overlay_fg': '#FFFFFF'
    },
    'Light': {
        'bg_app': '#F3F4F6', 'bg_sidebar': '#EAECEF', 'bg_canvas': '#FAFAFA', 'bg_panel': '#EAECEF',
        'bg_node': '#FFFFFF', 'bg_header': '#D8DCE3', 'bg_card': '#FFFFFF', 'fg_title': '#111827',
        'fg_text': '#1F2937', 'fg_sub': '#4B5563', 'accent': '#2563EB', 'grid': '#E5E7EB',
        'wire': '#9CA3AF', 'wire_active': '#D97706', 'socket': '#6B7280', 'btn_bg': '#D1D5DB',
        'input_bg': '#FFFFFF',
        'input_fg': '#111827', 'button_fg': '#111827', 'accent_fg': '#FFFFFF',
        'success': '#16A34A', 'success_fg': '#FFFFFF', 'danger': '#DC2626', 'danger_fg': '#FFFFFF',
        'warning': '#F59E0B', 'warning_fg': '#111827', 'control': '#7C3AED', 'sensor': '#EA580C',
        'var_node': '#0891B2', 'wire_hl': '#0284C7', 'shadow': '#D1D5DB',
        'hover': '#9CA3AF', 'select_box': '#2563EB', 'active_border': '#2563EB', 'marker': '#DC2626',
        'btn_hover': '#C4C9D4', 'hl_running': '#EAB308', 'hl_ok': '#16A34A', 'hl_fail': '#DC2626',
        'breakpoint': '#DC2626', 'log_bg': '#FFFFFF', 'log_fg': '#1F2937', 'win_node': '#0F766E',
        'log_info': '#1D4ED8', 'log_success': '#15803D', 'log_warning': '#B45309',
        'log_error': '#B91C1C', 'log_exec': '#4B5563', 'log_paused': '#A16207',
        'tooltip_bg': '#1F2937', 'tooltip_fg': '#F9FAFB', 'node_header_fg': '#FFFFFF',
        'preview_bg': '#F3F4F6', 'overlay_bg': '#1F2937', 'overlay_fg': '#FFFFFF'
    }
}

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".qflow_settings.json")

SETTINGS = {
    'hotkey_start': '<f9>',
    'hotkey_stop': '<f10>',
    'theme': 'Dark'
}

def load_user_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if data.get('theme') in THEMES:
                        SETTINGS['theme'] = data['theme']
                    if isinstance(data.get('hotkey_start'), str):
                        SETTINGS['hotkey_start'] = data['hotkey_start']
                    if isinstance(data.get('hotkey_stop'), str):
                        SETTINGS['hotkey_stop'] = data['hotkey_stop']
    except Exception:
        pass

def save_user_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'theme': SETTINGS.get('theme', 'Dark'),
                'hotkey_start': SETTINGS.get('hotkey_start', '<f9>'),
                'hotkey_stop': SETTINGS.get('hotkey_stop', '<f10>'),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

load_user_settings()
COLORS = THEMES.get(SETTINGS.get('theme', 'Dark'), THEMES['Dark']).copy()

# 字体字号采用标准磅值，配合 tk scaling 自动实现亚像素级高清矢量渲染
FONTS = {
    'node_title': ('Microsoft YaHei UI', 10, 'bold'),
    'node_text': ('Microsoft YaHei UI', 9),
    'code': ('Consolas', 10),
    'small': ('Microsoft YaHei UI', 9),
    'log': ('Microsoft YaHei UI', 9)
}

LOG_LEVELS = {
    'info': {'color': '#64b5f6'},
    'success': {'color': '#81c784'},
    'warning': {'color': '#ffd54f'},
    'error': {'color': '#e57373'},
    'exec': {'color': '#9e9e9e'},
    'paused': {'color': '#fff176'}
}
NODE_WIDTH = int(200 * SCALE_FACTOR)
HEADER_HEIGHT = int(28 * SCALE_FACTOR)
PORT_START_Y = int(45 * SCALE_FACTOR)
PORT_STEP_Y = int(24 * SCALE_FACTOR)
GRID_SIZE = int(20 * SCALE_FACTOR)

NODE_CONFIG = {
    'start':      {'title': '▶ 开始', 'outputs': ['out'], 'color': '#2e7d32', 'desc': '流程的起点'},
    'end':        {'title': '⏹️ 结束', 'outputs': [], 'color': '#c62828', 'desc': '强制停止流程'},
    'open_app':   {'title': '🚀 打开程序', 'outputs': ['out', 'fail'], 'color': '#e65100', 'desc': '运行指定的可执行文件'},
    'bind_win':   {'title': '⚓ 绑定窗口（旧版）', 'outputs': ['success', 'fail'], 'color': '#00695c', 'desc': '旧项目兼容节点；新建组件栏已停用'},
    'loop':       {'title': '🔄 循环', 'outputs': ['loop', 'exit'], 'color': '#7b1fa2', 'desc': '重复执行指定次数或无限循环'},
    'wait':       {'title': '⏳ 延时', 'outputs': ['out'], 'color': '#4527a0', 'desc': '等待指定时间（支持固定或随机）'},
    'mouse':      {'title': '👆 鼠标', 'outputs': ['out'], 'color': '#1565c0', 'desc': '点击、移动、拖拽或滚动'},
    'keyboard':   {'title': '⌨️ 键盘', 'outputs': ['out'], 'color': '#1565c0', 'desc': '输入文本或按下组合键'},
    'clipboard':  {'title': '📋 剪贴板', 'outputs': ['out'], 'color': '#00838f', 'desc': '读取或写入系统剪贴板内容'},
    'notify':     {'title': '🔔 提示', 'outputs': ['out'], 'color': '#9a6700', 'desc': '显示屏幕通知气泡'},
    'cmd':        {'title': '💻 命令', 'outputs': ['out'], 'color': '#1565c0', 'desc': '执行系统CMD命令'},
    'web':        {'title': '🔗 网页', 'outputs': ['out'], 'color': '#0277bd', 'desc': '打开指定的URL'},
    'image':      {'title': '🎯 找图', 'outputs': ['found', 'timeout'], 'color': '#ef6c00', 'desc': '在屏幕上查找图片并执行点击操作'},
    'if_img':     {'title': '🔍 检测', 'outputs': ['yes', 'no'], 'color': '#ef6c00', 'desc': '检测屏幕是否包含指定图像'},
    'if_static':  {'title': '⏸️ 静止', 'outputs': ['yes', 'no'], 'color': '#d84315', 'desc': '检测指定区域画面是否保持静止'},
    'if_sound':   {'title': '🔊 声音', 'outputs': ['yes', 'no'], 'color': '#d84315', 'desc': '检测系统是否有声音输出或静音'},
    'set_var':    {'title': '[x] 变量', 'outputs': ['out'], 'color': '#00838f', 'desc': '设置或修改内存变量'},
    'var_switch': {'title': '⎇ 分流', 'outputs': ['else'], 'color': '#00838f', 'desc': '根据变量值判断并选择不同路径'},
    'sequence':   {'title': '🔀 序列', 'outputs': ['else'], 'color': '#7b1fa2', 'desc': '按顺序依次尝试多条路径'},
    'reroute':    {'title': '●', 'outputs': ['out'], 'color': '#777777', 'desc': '线路中继点，整理连线布局'}
}

PORT_TRANSLATION = {
    'out': '继续', 'yes': '是', 'no': '否', 'found': '找到', 'timeout': '超时',
    'loop': '循环', 'exit': '退出', 'else': '否则', 'success': '成功', 'fail': '失败'
}
MOUSE_ACTIONS = {'click': '点击', 'move': '移动', 'drag': '拖拽', 'scroll': '滚动'}
MOUSE_BUTTONS = {'left': '左键', 'right': '右键', 'middle': '中键'}
ACTION_MAP = {'click': '单击左键', 'double_click': '双击左键', 'right_click': '单击右键', 'none': '不执行操作'}
MATCH_STRATEGY_MAP = {'hybrid': '智能混合', 'template': '模板匹配', 'feature': '特征匹配'}

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip, add="+")
        self.widget.bind("<Leave>", self.hide_tip, add="+")
        self.widget.bind("<Destroy>", self.hide_tip, add="+")

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 14
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_attributes("-topmost", True)
            tw.wm_geometry(f"+{x}+{y}")
            label = tk.Label(
                tw, text=self.text, justify='left',
                background=COLORS['tooltip_bg'], foreground=COLORS['tooltip_fg'],
                relief='solid', borderwidth=1, padx=8, pady=4,
                font=("Microsoft YaHei UI", 8)
            )
            label.pack()
        except Exception:
            self.tip_window = None

    def hide_tip(self, event=None):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

class KeyboardEngine:
    _controller = KeyboardController()

    @staticmethod
    def safe_write(text, mode='direct'):
        text = str(text if text is not None else '')
        if mode == 'paste' and HAS_PYPERCLIP:
            old_clip = None
            clipboard_saved = False
            try:
                old_clip = pyperclip.paste()
                clipboard_saved = True
                pyperclip.copy(text)
                time.sleep(0.05)
                with KeyboardEngine._controller.pressed(keyboard.Key.ctrl):
                    KeyboardEngine._controller.press('v')
                    KeyboardEngine._controller.release('v')
                time.sleep(0.1)
                return
            except Exception as e:
                print(f"粘贴模式失败，回退到普通输入: {e}")
            finally:
                if clipboard_saved:
                    try:
                        pyperclip.copy(old_clip if old_clip is not None else '')
                    except Exception:
                        pass
        for char in text:
            try:
                KeyboardEngine._controller.type(char)
            except Exception:
                try:
                    pyautogui.write(char)
                except Exception:
                    pass
            time.sleep(0.005)

class VisualTips:
    @staticmethod
    def show_toast(message, duration=2000, use_sound=False, position='center'):
        try:
            top = tk.Toplevel()
            top.overrideredirect(True)
            top.attributes("-topmost", True, "-alpha", 0.92)
            top.configure(bg=COLORS['overlay_bg'], highlightthickness=1, highlightbackground=COLORS['accent'])

            lbl = tk.Label(
                top, text=message, fg=COLORS['overlay_fg'], bg=COLORS['overlay_bg'],
                padx=20, pady=10, font=("Microsoft YaHei UI", 10, "bold"), justify='left'
            )
            lbl.pack()

            top.update_idletasks()
            w, h = top.winfo_reqwidth(), top.winfo_reqheight()
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()

            if position == 'bottom_right':
                top.geometry(f"+{max(10, sw - w - 24)}+{max(10, sh - h - 68)}")
            else:
                top.geometry(f"+{max(10, sw // 2 - w // 2)}+{max(10, sh // 2 - h // 2)}")

            if use_sound:
                threading.Thread(target=lambda: ctypes.windll.kernel32.Beep(800, 260), daemon=True).start()

            top.after(max(300, int(duration)), lambda: top.winfo_exists() and top.destroy())
        except Exception:
            pass

class WindowEngine:
    TH32CS_SNAPPROCESS = 0x00000002
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_ulong),
            ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260)
        ]

    @staticmethod
    def _get_process_map():
        pid_map = {}
        hSnap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(WindowEngine.TH32CS_SNAPPROCESS, 0)
        if hSnap == -1:
            return pid_map
        try:
            pe32 = WindowEngine.PROCESSENTRY32()
            pe32.dwSize = ctypes.sizeof(WindowEngine.PROCESSENTRY32)
            if ctypes.windll.kernel32.Process32First(hSnap, ctypes.byref(pe32)):
                while True:
                    try:
                        exe_name = pe32.szExeFile.decode('gbk', 'ignore')
                    except Exception:
                        exe_name = pe32.szExeFile.decode('utf-8', 'ignore')
                    pid_map[pe32.th32ProcessID] = exe_name
                    if not ctypes.windll.kernel32.Process32Next(hSnap, ctypes.byref(pe32)):
                        break
        finally:
            ctypes.windll.kernel32.CloseHandle(hSnap)
        return pid_map

    @staticmethod
    def get_window_info(hwnd, pid_map=None):
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            bytes_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, bytes_buffer, length + 1)
            title = bytes_buffer.value
        cls_buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buff, 256)
        class_name = cls_buff.value
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe_name = pid_map.get(pid.value, "") if pid_map else ""
        return {'hwnd': hwnd, 'title': title, 'class_name': class_name, 'exe_name': exe_name, 'pid': pid.value}

    @staticmethod
    def get_window_rect(hwnd):
        try:
            rect = ctypes.wintypes.RECT()
            if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0:
                return Box(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        except Exception:
            pass
        rect = ctypes.wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return Box(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        return None

    @staticmethod
    def is_window_valid_target(hwnd, my_pid):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or user32.GetWindow(hwnd, 4) != 0:
            return False
        is_cloaked = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(is_cloaked), ctypes.sizeof(is_cloaked))
            if is_cloaked.value != 0:
                return False
        except Exception:
            pass
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == my_pid:
            return False
        cls_buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buff, 256)
        cls_name = cls_buff.value
        if cls_name in ['Progman', 'Shell_TrayWnd', 'Button', 'Static', 'WorkerW', 'Windows.UI.Core.CoreWindow', 'EdgeUiInputTopWnd', 'ApplicationFrameWindow']:
            return False
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w < 10 or h < 10:
            return False
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0 and cls_name == 'ApplicationFrameWindow':
            return False
        return True

    @staticmethod
    def smart_find_window(target_exe=None, target_class=None, target_title=None):
        pid_map = WindowEngine._get_process_map()
        found_hwnd = 0
        my_pid = os.getpid()
        def callback(hwnd, extra):
            nonlocal found_hwnd
            if not WindowEngine.is_window_valid_target(hwnd, my_pid):
                return True
            info = WindowEngine.get_window_info(hwnd, pid_map)
            match = True
            if target_exe and target_exe.lower() != info['exe_name'].lower():
                match = False
            if match and target_class and target_class.lower() != info['class_name'].lower():
                match = False
            if match and target_title and target_title.lower() not in info['title'].lower():
                match = False
            if match:
                found_hwnd = hwnd
                return False
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return found_hwnd

    @staticmethod
    def focus_window(hwnd):
        try:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            user32.AttachThreadInput(current_thread, target_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(current_thread, target_thread, False)
            return True
        except Exception:
            return False

class ImageUtils:
    @staticmethod
    def img_to_b64(image):
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception:
            return None

    @staticmethod
    def b64_to_img(b64_str):
        if not b64_str or not isinstance(b64_str, str):
            return None
        try:
            missing_padding = len(b64_str) % 4
            if missing_padding:
                b64_str += '=' * (4 - missing_padding)
            with Image.open(io.BytesIO(base64.b64decode(b64_str))) as src:
                src.load()
                return src.copy()
        except Exception:
            return None

    @staticmethod
    def make_thumb(image, size=(240, 135)):
        if not image:
            return None
        try:
            thumb = image.copy()
            thumb.thumbnail(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(thumb)
        except Exception:
            return None

class AudioEngine:
    @staticmethod
    def get_max_audio_peak():
        if not HAS_AUDIO:
            return 0.0
        initialized = False
        try:
            try:
                comtypes.CoInitialize()
                initialized = True
            except Exception:
                pass
            max_peak = 0.0
            for session in AudioUtilities.GetAllSessions():
                if session.State == 1:
                    meter = session._ctl.QueryInterface(IAudioMeterInformation)
                    max_peak = max(max_peak, meter.GetPeakValue())
            return max_peak
        except Exception:
            return 0.0
        finally:
            if initialized:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

class VisionEngine:
    @staticmethod
    def _mask_own_windows(img, bbox=None):
        """将截图中的本程序自身窗口全部涂黑遮蔽，彻底防止找图识别到本程序界面中的截图/缩略图"""
        if not img:
            return
        try:
            my_pid = os.getpid()
            own_rects = []
            def enum_cb(hwnd, _):
                if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value == my_pid:
                        rect = WindowEngine.get_window_rect(hwnd)
                        if rect and rect.width > 0 and rect.height > 0:
                            own_rects.append(rect)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if not own_rects:
                return

            base_x = bbox[0] if bbox else VX
            base_y = bbox[1] if bbox else VY
            draw = None

            for r in own_rects:
                ix1 = r.left - base_x
                iy1 = r.top - base_y
                ix2 = ix1 + r.width
                iy2 = iy1 + r.height

                if ix2 <= 0 or iy2 <= 0 or ix1 >= img.width or iy1 >= img.height:
                    continue

                cx1 = max(0, ix1)
                cy1 = max(0, iy1)
                cx2 = min(img.width, ix2)
                cy2 = min(img.height, iy2)

                if draw is None:
                    draw = ImageDraw.Draw(img)
                draw.rectangle([cx1, cy1, cx2, cy2], fill=(0, 0, 0))
        except Exception:
            pass

    @staticmethod
    def capture_screen(bbox=None, mask_self=True):
        try:
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            if img and mask_self:
                VisionEngine._mask_own_windows(img, bbox)
            return img
        except OSError:
            return None

    @staticmethod
    def locate(needle, confidence=0.8, timeout=0, stop_event=None, grayscale=True, multiscale=True, scaling_ratio=1.0, strategy='hybrid', region=None):
        if needle is None:
            return None
        start_time = time.time()
        while True:
            if stop_event and stop_event.is_set():
                return None

            capture_bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3]) if region else None
            haystack = VisionEngine.capture_screen(bbox=capture_bbox)

            if haystack is None:
                time.sleep(0.3)
                if timeout <= 0 or (time.time() - start_time >= timeout):
                    break
                continue

            try:
                result, _ = VisionEngine._advanced_match(needle, haystack, confidence, stop_event, grayscale, multiscale, scaling_ratio, strategy)
                if result:
                    offset_x = region[0] if region else VX
                    offset_y = region[1] if region else VY
                    return Box(result.left + offset_x, result.top + offset_y, result.width, result.height)
            except Exception:
                pass

            if timeout <= 0 or (time.time() - start_time >= timeout):
                break
            time.sleep(0.1)
        return None

    @staticmethod
    def _advanced_match(needle, haystack, confidence, stop_event, grayscale, multiscale, scaling_ratio, strategy):
        if not needle or not haystack:
            return None, 0.0
        if needle.width > haystack.width or needle.height > haystack.height:
            return None, 0.0
        if HAS_OPENCV:
            try:
                needle_rgb = np.array(needle.convert('RGB'))
                haystack_rgb = np.array(haystack.convert('RGB'))
                if grayscale:
                    nA = cv2.cvtColor(needle_rgb, cv2.COLOR_RGB2GRAY)
                    hA = cv2.cvtColor(haystack_rgb, cv2.COLOR_RGB2GRAY)
                else:
                    nA = cv2.cvtColor(needle_rgb, cv2.COLOR_RGB2BGR)
                    hA = cv2.cvtColor(haystack_rgb, cv2.COLOR_RGB2BGR)

                if strategy == 'feature':
                    return VisionEngine._feature_match_akaze(nA, hA)

                nH, nW = nA.shape[:2]
                hH, hW = hA.shape[:2]
                scales = [1.0]
                if multiscale and strategy != 'template':
                    scales = np.unique(np.append(np.linspace(scaling_ratio * 0.8, scaling_ratio * 1.2, 9), [1.0, scaling_ratio]))
                best_max, best_rect = -1.0, None
                for s in scales:
                    if stop_event and stop_event.is_set():
                        return None, 0.0
                    tW, tH = int(nW * s), int(nH * s)
                    if tW < 5 or tH < 5 or tW > hW or tH > hH:
                        continue
                    resized = nA if abs(s - 1.0) < 1e-4 else cv2.resize(nA, (tW, tH), interpolation=cv2.INTER_AREA)
                    res = cv2.matchTemplate(hA, resized, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val > best_max:
                        best_max, best_rect = max_val, Box(max_loc[0], max_loc[1], tW, tH)
                    if best_max > 0.985:
                        break
                if best_rect and best_max >= confidence:
                    return best_rect, best_max
                if strategy == 'hybrid' and confidence <= 0.85:
                    feat_rect, feat_score = VisionEngine._feature_match_akaze(nA, hA)
                    if feat_rect and feat_score >= confidence:
                        return feat_rect, feat_score
            except Exception:
                pass
        try:
            res = pyautogui.locate(needle, haystack, confidence=confidence, grayscale=grayscale)
            if res:
                return Box(res.left, res.top, res.width, res.height), 1.0
        except Exception:
            pass
        return None, 0.0

    @staticmethod
    def _feature_match_akaze(template, target, min_match_count=4):
        try:
            akaze = cv2.AKAZE_create()
            kp1, des1 = akaze.detectAndCompute(template, None)
            kp2, des2 = akaze.detectAndCompute(target, None)
            if des1 is None or des2 is None:
                return None, 0.0
            matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des1, des2, k=2)
            good = [pair[0] for pair in matches if len(pair) >= 2 and pair[0].distance < 0.75 * pair[1].distance]
            if len(good) >= min_match_count:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                M, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                if M is not None:
                    h, w = template.shape[:2]
                    pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
                    dst = cv2.perspectiveTransform(pts, M)
                    x_min, y_min = np.min(dst[:, :, 0]), np.min(dst[:, :, 1])
                    x_max, y_max = np.max(dst[:, :, 0]), np.max(dst[:, :, 1])
                    bw, bh = int(x_max - x_min), int(y_max - y_min)
                    if bw > 4 and bh > 4:
                        return Box(max(0, int(x_min)), max(0, int(y_min)), bw, bh), min(1.0, len(good) / min_match_count * 0.5 + 0.5)
            return None, 0.0
        except Exception:
            return None, 0.0

    @staticmethod
    def compare_images(img1, img2, threshold=0.99):
        """以归一化平均绝对像素差计算相似度，threshold 范围为 0..1。"""
        if img1 is None or img2 is None:
            return False
        try:
            threshold = max(0.0, min(1.0, safe_float(threshold, 0.99)))
            if img1.size != img2.size:
                img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
            diff = ImageChops.difference(img1.convert('RGB'), img2.convert('RGB'))
            mean_diff = ImageStat.Stat(diff.convert('L')).mean[0] / 255.0
            similarity = 1.0 - mean_diff
            return similarity >= threshold
        except Exception:
            return False

class LogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_panel'], **kwargs)
        self.toolbar = tk.Frame(self, bg=COLORS['bg_header'], height=28)
        self.toolbar.pack_propagate(False)
        self.toolbar.pack(fill='x')
        tk.Label(self.toolbar, text="📋 执行日志", bg=COLORS['bg_header'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9, 'bold')).pack(side='left', padx=10)
        btn_clear = tk.Button(self.toolbar, text="清空日志", command=self.clear, bg=COLORS['bg_header'], fg=COLORS['fg_sub'], bd=0, font=('Microsoft YaHei UI', 8), cursor='hand2', padx=6)
        btn_clear.pack(side='right', padx=6)

        self.text_frame = tk.Frame(self, bg=COLORS['log_bg'])
        self.scrollbar = ttk.Scrollbar(self.text_frame)
        self.text_area = tk.Text(
            self.text_frame, bg=COLORS['log_bg'], fg=COLORS['log_fg'],
            font=FONTS['log'], state='disabled', yscrollcommand=self.scrollbar.set,
            bd=0, padx=10, pady=6, highlightthickness=0
        )
        self.scrollbar.config(command=self.text_area.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.text_area.pack(side='left', fill='both', expand=True)
        for level, style in LOG_LEVELS.items():
            self.text_area.tag_config(level, foreground=COLORS.get(f'log_{level}', style['color']))

        self.text_frame.pack(fill='both', expand=True)

    def add_log(self, msg, level='info'):
        if not self.winfo_exists():
            return
        follow_tail = self.text_area.yview()[1] >= 0.98
        self.text_area.config(state='normal')
        self.text_area.insert('end', f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n", level)
        try:
            line_count = int(self.text_area.index('end-1c').split('.')[0])
            if line_count > 5000:
                self.text_area.delete('1.0', f'{line_count - 5000}.0')
        except (tk.TclError, ValueError):
            pass
        if follow_tail:
            self.text_area.see('end')
        self.text_area.config(state='disabled')

    def clear(self):
        self.text_area.config(state='normal')
        self.text_area.delete(1.0, 'end')
        self.text_area.config(state='disabled')

class AutomationCore:
    def __init__(self, log_callback, app_instance):
        self.running = False
        self.paused = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.log = log_callback
        self.app = app_instance
        self.project = None
        self.runtime_memory = {}
        self.memory_lock = threading.RLock()
        self.stats_lock = threading.Lock()
        self.io_lock = threading.Lock()
        self.run_generation = 0
        self.active_threads = 0
        self.thread_lock = threading.Lock()
        self.scaling_ratio = 1.0
        self.breakpoints = set()
        self.max_threads = 50
        self.pending_nodes = []
        self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
        self.performance_stats = {'nodes_executed': 0, 'errors': 0, 'start_time': None}

    def load_project(self, project_data):
        metadata = project_data.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError("项目 metadata 必须是对象")
        breakpoints = project_data.get('breakpoints', [])
        if not isinstance(breakpoints, list):
            raise ValueError("项目 breakpoints 必须是列表")
        dev_scale = safe_float(metadata.get('dev_scale_x', 1.0), 1.0)
        runtime_scale_x = SCALE_X
        scaling_ratio = runtime_scale_x / dev_scale if dev_scale > 0.1 and runtime_scale_x > 0.1 else 1.0
        self.project = project_data
        self.scaling_ratio = scaling_ratio
        self.breakpoints = set(breakpoints)
        if self.project and 'nodes' in self.project:
            for nid, node in self.project['nodes'].items():
                data = node.get('data', {})
                try:
                    if 'b64' in data and 'image' not in data and (img := ImageUtils.b64_to_img(data['b64'])):
                        self.project['nodes'][nid]['data']['image'] = img
                    if 'anchors' in data:
                        for anchor in data['anchors']:
                            if 'b64' in anchor and 'image' not in anchor and (img := ImageUtils.b64_to_img(anchor['b64'])):
                                anchor['image'] = img
                    if 'images' in data:
                        for img_item in data['images']:
                            if 'b64' in img_item and 'image' not in img_item and (img := ImageUtils.b64_to_img(img_item['b64'])):
                                img_item['image'] = img
                    if 'b64_preview' in data and (img := ImageUtils.b64_to_img(data['b64_preview'])):
                        self.project['nodes'][nid]['data']['roi_preview'] = img
                except Exception:
                    pass

    def start(self, start_node_id=None):
        with self.thread_lock:
            if self.running or not self.project:
                return
            self.running = True
            self.run_generation += 1
            generation = self.run_generation
            self.paused = False
            self.stop_event.clear()
            self.pause_event.set()
            self.active_threads = 0
            self.pending_nodes.clear()
        try:
            with self.memory_lock:
                self.runtime_memory.clear()
            self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
            self.performance_stats = {'nodes_executed': 0, 'errors': 0, 'start_time': time.time()}
            self.log("🚀 引擎启动", "exec")
            self.app.iconify()
            try:
                self.app.update_idletasks()
            except Exception:
                pass
            threading.Thread(target=self._run_flow_engine, args=(start_node_id, generation), daemon=True).start()
        except Exception as e:
            with self.thread_lock:
                self.running = False
                self.stop_event.set()
                self.pause_event.set()
                self.pending_nodes.clear()
            self.log(f"无法启动流程引擎: {e}", "error")
            self.app.after(0, self.app.reset_ui_state)
            raise

    def stop(self):
        with self.thread_lock:
            if not self.running:
                return
            self.stop_event.set()
            self.pause_event.set()
            self.pending_nodes.clear()
        self.log("🛑 正在停止流程...", "warning")

    def pause(self):
        with self.thread_lock:
            if not self.running or self.stop_event.is_set() or self.paused:
                return
            self.paused = True
            self.pause_event.clear()
        self.log("⏸️ 流程已暂停", "paused")
        self.app.after(0, lambda: self.app.update_debug_btn_state(True))

    def resume(self):
        with self.thread_lock:
            if not self.running or not self.paused:
                return
            self.paused = False
            self.pause_event.set()
        self.log("▶️ 流程继续执行", "info")
        self.app.after(0, lambda: self.app.update_debug_btn_state(False))

    def _smart_wait(self, seconds):
        end_time = time.time() + max(0.0, seconds)
        while time.time() < end_time:
            if self.stop_event.is_set():
                return False
            self._check_pause()
            time.sleep(min(0.05, max(0.005, end_time - time.time())))
        return not self.stop_event.is_set()

    def _check_pause(self, node_id=None):
        if node_id and node_id in self.breakpoints:
            if not self.paused:
                self.log(f"🔴 命中断点: {node_id}", "paused")
                self.pause()
                self.app.after(0, self.app.deiconify)
        if not self.pause_event.is_set():
            self.pause_event.wait()

    def _get_next_links(self, node_id, port_name='out'):
        if not isinstance(self.project, dict):
            return []
        nodes = self.project.get('nodes', {})
        links = self.project.get('links', [])
        if not isinstance(nodes, dict) or not isinstance(links, list):
            return []
        return [
            link.get('target')
            for link in links
            if isinstance(link, dict)
            and link.get('source') == node_id
            and link.get('source_port', 'out') == port_name
            and link.get('target') in nodes
        ]

    def _run_flow_engine(self, start_node_id=None, generation=None):
        user_stopped = False
        engine_error = False
        try:
            time.sleep(0.2)
            start_nodes = [start_node_id] if start_node_id else [nid for nid, n in self.project['nodes'].items() if n['type'] == 'start']
            if not start_nodes:
                self.log("未找到【开始】节点，请先在画布中添加开始节点", "error")
                return
            for start_id in start_nodes:
                self._fork_node(start_id)
            while True:
                with self.thread_lock:
                    active_threads = self.active_threads
                if active_threads <= 0:
                    break
                time.sleep(0.05)
            user_stopped = self.stop_event.is_set()
        except Exception as e:
            engine_error = True
            self.stop_event.set()
            self.pause_event.set()
            with self.thread_lock:
                self.pending_nodes.clear()
            traceback.print_exc()
            self.log(f"引擎异常: {str(e)}", "error")
        finally:
            with self.thread_lock:
                self.pending_nodes.clear()
            while True:
                with self.thread_lock:
                    active_threads = self.active_threads
                if active_threads <= 0:
                    break
                time.sleep(0.05)
            with self.thread_lock:
                if generation is None:
                    generation = self.run_generation
                current_run = generation == self.run_generation
                stats = self._stats_snapshot() if current_run else None
                if current_run:
                    self.running = False
            if stats is not None:
                if stats['start_time']:
                    elapsed = time.time() - stats['start_time']
                    self.log(f"📊 执行统计: {stats['nodes_executed']}个节点, {stats['errors']}个错误, 耗时{elapsed:.2f}秒", "info")
                if engine_error or stats['errors'] > 0:
                    self.log("⚠️ 流程结束（存在异常或错误）", "warning")
                elif user_stopped:
                    self.log("⏹️ 流程已停止", "warning")
                else:
                    self.log("🏁 流程正常结束", "success")
                self.app.after(0, lambda: self._finish_run_ui(generation, reset=False))
                self.app.after(100, lambda: self._finish_run_ui(generation, reset=True))

    def _finish_run_ui(self, generation, reset=False):
        with self.thread_lock:
            if generation != self.run_generation or self.running:
                return
        if reset:
            self.app.reset_ui_state()
        else:
            self.app.highlight_node_safe(None)
            self.app.deiconify()

    def _fork_node(self, node_id):
        with self.thread_lock:
            if node_id not in self.project['nodes'] or self.stop_event.is_set():
                return
            if self.active_threads >= self.max_threads:
                self.pending_nodes.append(node_id)
                return
            self.active_threads += 1
        try:
            threading.Thread(target=self._process_node_thread, args=(node_id,), daemon=True).start()
        except Exception:
            with self.thread_lock:
                self.active_threads -= 1
            raise

    def _process_node_thread(self, node_id):
        try:
            if self.stop_event.is_set():
                return
            if not (node := self.project['nodes'].get(node_id)):
                return
            self._check_pause(node_id)
            if self.stop_event.is_set():
                return
            self.app.highlight_node_safe(node_id, 'running')
            self.app.select_node_safe(node_id)
            try:
                out_port = self._execute_node(node)
                self._increment_stat('nodes_executed')
            except pyautogui.FailSafeException:
                self.log("🛑 触发 PyAutoGUI 左上角紧急中止保护！", "error")
                self.stop_event.set()
                self.pause_event.set()
                return
            except Exception as e:
                self.log(f"💥 节点[{node.get('data', {}).get('_user_title', node_id)}]错误: {e}", "error")
                traceback.print_exc()
                self._increment_stat('errors')
                out_port = 'fail'
            if out_port == '__STOP__' or self.stop_event.is_set():
                return

            if node['type'] != 'reroute':
                self.log(f"↳ [{node.get('data',{}).get('_user_title','Node')}] -> {PORT_TRANSLATION.get(out_port, out_port)}", "exec")

            self.app.highlight_node_safe(node_id, 'fail' if out_port in ['timeout', 'no', 'exit', 'else', 'fail'] else 'ok')
            time.sleep(0.01)
            for next_id in self._get_next_links(node_id, out_port):
                if self.stop_event.is_set():
                    break
                self._fork_node(next_id)
        finally:
            next_id = None
            with self.thread_lock:
                self.active_threads -= 1
                if self.pending_nodes and not self.stop_event.is_set():
                    next_id = self.pending_nodes.pop(0)
                    self.active_threads += 1
            if next_id is not None:
                try:
                    threading.Thread(target=self._process_node_thread, args=(next_id,), daemon=True).start()
                except Exception as e:
                    with self.thread_lock:
                        self.active_threads -= 1
                        self.pending_nodes.clear()
                        self.stop_event.set()
                        self.pause_event.set()
                    self.log(f"无法启动排队节点[{next_id}]，已停止剩余任务: {e}", "error")

    def _memory_snapshot(self):
        with self.memory_lock:
            return dict(self.runtime_memory)

    def _increment_stat(self, key):
        with self.stats_lock:
            self.performance_stats[key] += 1

    def _stats_snapshot(self):
        with self.stats_lock:
            return dict(self.performance_stats)

    def _replace_variables(self, text):
        if not isinstance(text, str):
            return str(text)
        for k, v in self._memory_snapshot().items():
            val_str = str(v) if v is not None else ""
            text = text.replace(f'${{{k}}}', val_str)
            text = text.replace(f'${k}', val_str)
            text = text.replace(f'{{{k}}}', val_str)
        return text

    def _update_context_rect(self):
        if self.context['window_handle']:
            try:
                if not user32.IsWindow(self.context['window_handle']):
                    self.log("⚠️ 绑定窗口已关闭，重置窗口上下文", "warning")
                    self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
                    return
                rect = WindowEngine.get_window_rect(self.context['window_handle'])
                if rect:
                    self.context['window_rect'] = rect
                    self.context['window_offset'] = (rect.left, rect.top)
                else:
                    self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
            except Exception:
                self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}

    def _ensure_window_focus(self):
        if self.context['window_handle']:
            try:
                WindowEngine.focus_window(self.context['window_handle'])
                self._update_context_rect()
                time.sleep(0.05)
            except Exception:
                pass

    def _execute_node(self, node):
        if self.stop_event.is_set():
            return '__STOP__'
        ntype = node['type']

        data = {k: (self._replace_variables(v) if isinstance(v, str) and ('$' in v or '{' in v) else v) for k, v in node.get('data', {}).items()}

        if self.context['window_handle']:
            self._update_context_rect()

        win_offset_x, win_offset_y = self.context['window_offset']
        win_region = self.context['window_rect']

        if ntype == 'reroute':
            return 'out'
        if ntype == 'start':
            return 'out'
        if ntype == 'end':
            self.stop_event.set()
            return '__STOP__'
        if ntype == 'wait':
            if data.get('delay_type') == 'random':
                low = safe_float(data.get('min_seconds', 1.0), 1.0)
                high = safe_float(data.get('max_seconds', 3.0), 3.0)
                if high < low:
                    low, high = high, low
                sec = random.uniform(low, high)
            else:
                sec = safe_float(data.get('seconds', 1.0), 1.0)
            return 'out' if self._smart_wait(sec) else '__STOP__'

        if ntype == 'notify':
            msg = data.get('msg', '执行到此节点')
            if "{ALL_VARS}" in msg.upper() or "{所有变量}" in msg or "${ALL_VARS}" in msg.upper() or "${所有变量}" in msg:
                memory = self._memory_snapshot()
                vars_list_str = "\n".join([f"• {k} = {v}" for k, v in memory.items()]) if memory else "（目前无任何内存变量）"
                for token in ("${ALL_VARS}", "${all_vars}", "${所有变量}", "{ALL_VARS}", "{all_vars}", "{所有变量}"):
                    msg = msg.replace(token, vars_list_str)

            use_sound = bool(data.get('use_sound', False))
            duration = safe_int(safe_float(data.get('duration', 2.0)) * 1000)
            self.app.after(0, lambda m=msg, d=duration, s=use_sound: VisualTips.show_toast(m, d, s))
            self.log(f"🔔 提示内容: {msg}", "info")
            return 'out'

        if ntype == 'open_app':
            path = str(data.get('path', '')).strip()
            args = str(data.get('args', '')).strip()
            if not path:
                self.log("❌ 启动失败: 未配置程序路径", "error")
                return 'fail'
            try:
                cmd_line = f'"{path}" {args}' if args else f'"{path}"'
                cwd = os.path.dirname(path)
                if not cwd or not os.path.exists(cwd):
                    cwd = None
                subprocess.Popen(cmd_line, shell=False, cwd=cwd)
                self.log(f"🚀 启动: {os.path.basename(path)}", "success")
                return 'out'
            except Exception as e:
                self.log(f"❌ 启动失败: {e}", "error")
                return 'fail'

        if ntype == 'bind_win':
            title = data.get('title', '')
            exe_name = data.get('exe_name', '')
            class_name = data.get('class_name', '')
            use_exe = bool(data.get('use_exe', True))
            use_class = bool(data.get('use_class', True))
            use_title = bool(data.get('use_title', False))
            target_exe = exe_name if use_exe else None
            target_class = class_name if use_class else None
            target_title = title if use_title else None
            if not target_exe and not target_class and not target_title:
                target_title = title
            hwnd = WindowEngine.smart_find_window(target_exe, target_class, target_title)
            if hwnd:
                WindowEngine.focus_window(hwnd)
                rect = WindowEngine.get_window_rect(hwnd)
                self.context['window_handle'] = hwnd
                self.context['window_rect'] = rect
                self.context['window_offset'] = (rect.left, rect.top) if rect else (0, 0)
                self.log(f"⚓ 已绑定: {exe_name or title or '窗口'}", "success")
                return 'success'
            else:
                self.log(f"❌ 未找到窗口 (Exe:{target_exe}, Class:{target_class}, Title:{target_title})", "warning")
                return 'fail'

        if ntype == 'set_var':
            with self.memory_lock:
                if 'batch_vars' in data:
                    self.runtime_memory.update({
                        i['name']: self._replace_variables(i.get('value', ''))
                        for i in data['batch_vars'] if isinstance(i, dict) and i.get('name')
                    })
                if data.get('var_name'):
                    self.runtime_memory[data['var_name']] = data.get('var_value', '')
            return 'out'

        if ntype == 'clipboard':
            mode = data.get('clip_mode', 'read')
            if mode == 'read':
                if HAS_PYPERCLIP:
                    with self.memory_lock:
                        self.runtime_memory[data.get('var_name', 'clipboard_data')] = pyperclip.paste()
                else:
                    self.log("⚠️ 未安装 pyperclip，无法读取剪贴板", "warning")
            elif mode == 'write':
                if HAS_PYPERCLIP:
                    pyperclip.copy(str(data.get('text', '')))
                else:
                    self.log("⚠️ 未安装 pyperclip，无法写入剪贴板", "warning")
            return 'out'

        if ntype == 'var_switch':
            if data.get('var_name'):
                with self.memory_lock:
                    val = str(self.runtime_memory.get(data.get('var_name', ''), ''))
                op, target = data.get('operator', '='), str(data.get('var_value', ''))
                if op == '=':
                    matched = (val == target)
                elif op == '!=':
                    matched = (val != target)
                elif op == 'contains':
                    matched = (target in val)
                elif op == '>':
                    matched = safe_float(val) > safe_float(target)
                elif op == '<':
                    matched = safe_float(val) < safe_float(target)
                else:
                    matched = (val != target)
                return 'yes' if matched else 'no'
            with self.memory_lock:
                vals = [str(self.runtime_memory.get(vn.strip(), '')) for vn in data.get('var_list', '').split(',') if vn.strip()]
            for case in data.get('cases', []):
                if vals and all(v == str(case.get('value', '')) for v in vals):
                    return case.get('id', 'else')
            return 'else'

        if ntype == 'sequence':
            for i in range(1, safe_int(data.get('num_steps', 3)) + 1):
                if self.stop_event.is_set():
                    return '__STOP__'
                target_id = (self._get_next_links(node['id'], str(i)) or [None])[0]
                if not target_id or target_id not in self.project['nodes']:
                    continue

                res_port = self._execute_node(self.project['nodes'][target_id])
                if res_port in ['yes', 'found', 'out', 'loop', 'success']:
                    next_nodes = self._get_next_links(target_id, res_port)
                    for nid in next_nodes:
                        self._fork_node(nid)
                    return '__STOP__'
            return 'else'

        if ntype == 'if_sound':
            if not HAS_AUDIO:
                return 'no'
            start_t = time.time()
            threshold = safe_float(data.get('threshold', 0.02))
            timeout = safe_float(data.get('timeout', 10.0))
            mode = data.get('detect_mode', 'has_sound')
            found = False
            while time.time() - start_t < timeout:
                if self.stop_event.is_set():
                    return '__STOP__'
                self._check_pause()
                peak = AudioEngine.get_max_audio_peak()
                if mode == 'has_sound':
                    if peak > threshold:
                        found = True
                        break
                else:
                    if peak < threshold:
                        found = True
                        break
                time.sleep(0.1)
            return 'yes' if found else 'no'

        if ntype == 'if_static':
            self._ensure_window_focus()
            roi = data.get('roi')
            if not roi or len(roi) < 4:
                return 'no'
            duration = safe_float(data.get('duration', 5.0))
            timeout = safe_float(data.get('timeout', 20.0))
            threshold = safe_float(data.get('threshold', 0.98))
            if self.context['window_handle'] and self.context['window_rect']:
                abs_x = roi[0] + win_offset_x
                abs_y = roi[1] + win_offset_y
            else:
                abs_x = roi[0]
                abs_y = roi[1]
            target_bbox = (abs_x, abs_y, abs_x + roi[2], abs_y + roi[3])
            start_check = time.time()
            static_start = time.time()
            last_frame = VisionEngine.capture_screen(bbox=target_bbox)
            while time.time() - start_check < timeout:
                if self.stop_event.is_set():
                    return '__STOP__'
                self._check_pause()

                if self.context['window_handle']:
                    fg_hwnd = user32.GetForegroundWindow()
                    if fg_hwnd != self.context['window_handle']:
                        self.log("⚠️ 窗口失去焦点或被遮挡，拉回前台并重置静止计时...", "warning")
                        self._ensure_window_focus()
                        time.sleep(0.3)
                        static_start = time.time()
                        last_frame = VisionEngine.capture_screen(bbox=target_bbox)
                        continue

                curr_frame = VisionEngine.capture_screen(bbox=target_bbox)
                is_static = VisionEngine.compare_images(last_frame, curr_frame, threshold)
                if is_static:
                    if time.time() - static_start >= duration:
                        return 'yes'
                else:
                    static_start = time.time()
                    last_frame = curr_frame
                time.sleep(0.2)
            return 'no'

        if ntype == 'image':
            self._ensure_window_focus()
            conf = safe_float(data.get('confidence', 0.9), 0.9)
            timeout_val = max(0.5, safe_float(data.get('timeout', 10.0), 10.0))
            search_region = win_region if win_region else None
            if (anchors := data.get('anchors', [])):
                primary_res = None
                for i, anchor in enumerate(anchors):
                    if self.stop_event.is_set():
                        return '__STOP__'
                    res = VisionEngine.locate(
                        anchor.get('image'), confidence=conf,
                        timeout=(timeout_val if i == 0 else 2.0),
                        stop_event=self.stop_event,
                        scaling_ratio=self.scaling_ratio,
                        strategy=data.get('match_strategy', 'hybrid'),
                        region=search_region
                    )
                    if not res:
                        return 'timeout'
                    if i == 0:
                        primary_res = res
                if primary_res:
                    off_x = safe_int(data.get('target_rect_x', 0)) - anchors[0].get('rect_x', 0)
                    off_y = safe_int(data.get('target_rect_y', 0)) - anchors[0].get('rect_y', 0)
                    search_region = (
                        int(primary_res.left + off_x) - 15,
                        int(primary_res.top + off_y) - 15,
                        safe_int(data.get('target_rect_w', 100)) + 30,
                        safe_int(data.get('target_rect_h', 100)) + 30
                    )

            start_time = time.time()
            auto_scroll = bool(data.get('auto_scroll', False))

            while True:
                if self.stop_event.is_set():
                    return '__STOP__'
                self._check_pause()
                res = VisionEngine.locate(
                    data.get('image'), confidence=conf, timeout=0,
                    stop_event=self.stop_event, region=search_region,
                    scaling_ratio=self.scaling_ratio,
                    strategy=data.get('match_strategy', 'hybrid')
                )
                if res:
                    if self.stop_event.is_set():
                        return '__STOP__'
                    with self.io_lock:
                        if (act := data.get('click_type', 'click')) != 'none':
                            rx, ry = data.get('relative_click_pos', (0.5, 0.5))
                            tx = res.left + (res.width * rx) + safe_int(data.get('offset_x', 0))
                            ty = res.top + (res.height * ry) + safe_int(data.get('offset_y', 0))
                            pyautogui.moveTo(tx, ty)
                            getattr(pyautogui, {'click': 'click', 'double_click': 'doubleClick', 'right_click': 'rightClick'}.get(act, 'click'))()
                    return 'found'

                if time.time() - start_time > timeout_val:
                    break

                if auto_scroll:
                    with self.io_lock:
                        if win_region:
                            cx = win_region.left + win_region.width // 2
                            cy = win_region.top + win_region.height // 2
                            pyautogui.moveTo(cx, cy)
                        else:
                            w, h = pyautogui.size()
                            pyautogui.moveTo(w // 2, h // 2)
                        pyautogui.scroll(safe_int(data.get('scroll_amount', -500)))
                    time.sleep(0.5)

                time.sleep(0.2)
            return 'timeout'

        if ntype == 'mouse':
            self._ensure_window_focus()
            if self.stop_event.is_set():
                return '__STOP__'
            with self.io_lock:
                action = data.get('mouse_action', 'click')
                dur = max(0.0, safe_float(data.get('duration', 0.5), 0.5))
                coord_mode = data.get('coord_mode', 'absolute')

                if action == 'drag':
                    curr_pos_x, curr_pos_y = pyautogui.position()

                    raw_sx = data.get('start_x')
                    raw_sy = data.get('start_y')
                    raw_ex = data.get('end_x')
                    raw_ey = data.get('end_y')

                    s_x = curr_pos_x if (raw_sx is None or str(raw_sx).strip() == "") else safe_int(raw_sx, 0)
                    s_y = curr_pos_y if (raw_sy is None or str(raw_sy).strip() == "") else safe_int(raw_sy, 0)
                    e_x = curr_pos_x if (raw_ex is None or str(raw_ex).strip() == "") else safe_int(raw_ex, 0)
                    e_y = curr_pos_y if (raw_ey is None or str(raw_ey).strip() == "") else safe_int(raw_ey, 0)

                    if coord_mode == 'relative' and self.context['window_handle']:
                        start_x_screen = s_x + win_offset_x if (raw_sx is not None and str(raw_sx).strip() != "") else s_x
                        start_y_screen = s_y + win_offset_y if (raw_sy is not None and str(raw_sy).strip() != "") else s_y
                        end_x_screen = e_x + win_offset_x if (raw_ex is not None and str(raw_ex).strip() != "") else e_x
                        end_y_screen = e_y + win_offset_y if (raw_ey is not None and str(raw_ey).strip() != "") else e_y
                    else:
                        start_x_screen, start_y_screen = s_x, s_y
                        end_x_screen, end_y_screen = e_x, e_y

                    pyautogui.moveTo(start_x_screen, start_y_screen, duration=0.1)
                    pyautogui.dragTo(end_x_screen, end_y_screen, button='left', duration=dur)
                else:
                    curr_pos_x, curr_pos_y = pyautogui.position()
                    raw_x_val = data.get('x')
                    raw_y_val = data.get('y')

                    if raw_x_val is None or str(raw_x_val).strip() == "":
                        target_x = curr_pos_x
                    else:
                        raw_x = safe_int(raw_x_val, 0)
                        target_x = raw_x + win_offset_x if (coord_mode == 'relative' and self.context['window_handle']) else raw_x

                    if raw_y_val is None or str(raw_y_val).strip() == "":
                        target_y = curr_pos_y
                    else:
                        raw_y = safe_int(raw_y_val, 0)
                        target_y = raw_y + win_offset_y if (coord_mode == 'relative' and self.context['window_handle']) else raw_y

                    if action in ('click', 'double_click'):
                        clicks = 2 if action == 'double_click' else (2 if str(data.get('click_count', 1)) in ['2', '双击'] else 1)
                        pyautogui.click(x=target_x, y=target_y, clicks=clicks, button=data.get('mouse_button', 'left'), duration=dur, interval=0.1)
                    elif action == 'move':
                        pyautogui.moveTo(target_x, target_y, duration=dur)
                    elif action == 'scroll':
                        pyautogui.moveTo(target_x, target_y, duration=dur)
                        pyautogui.scroll(safe_int(data.get('scroll_amount', -500)))
            return 'out'

        if ntype == 'keyboard':
            if self.stop_event.is_set():
                return '__STOP__'
            with self.io_lock:
                if data.get('kb_mode', 'text') == 'text':
                    if data.get('use_paste', True):
                        KeyboardEngine.safe_write(data.get('text', ''), 'paste')
                    else:
                        KeyboardEngine.safe_write(data.get('text', ''), 'direct')
                    if data.get('press_enter', False):
                        pyautogui.press('enter')
                else:
                    keys = [x.strip().lower() for x in data.get('key_name', 'enter').split('+') if x.strip()]
                    keys = ['win' if k == 'win' else k for k in keys]
                    try:
                        if keys:
                            pyautogui.hotkey(*keys)
                    except Exception as e:
                        self.log(f"按键发送失败: {e}", "error")
            return 'out'

        if ntype == 'cmd':
            try:
                cmd_str = str(data.get('command', '')).strip()
                if cmd_str:
                    subprocess.Popen(cmd_str, shell=True)
            except Exception as e:
                self.log(f"CMD错误: {e}", "error")
            return 'out'

        if ntype == 'web':
            url = str(data.get('url', '')).strip()
            if url:
                webbrowser.open(url)
            return 'out' if self._smart_wait(2) else '__STOP__'

        if ntype == 'loop':
            if data.get('infinite', True):
                return 'loop'
            with self.memory_lock:
                k = f"loop_{node['id']}"
                c = self.runtime_memory.get(k, 0)
                if c < safe_int(data.get('count', 3)):
                    self.runtime_memory[k] = c + 1
                    return 'loop'
                else:
                    self.runtime_memory.pop(k, None)
                    return 'exit'

        if ntype == 'if_img':
            self._ensure_window_focus()
            if not (imgs := data.get('images', [])):
                return 'no'

            if win_region:
                capture_bbox = (win_region.left, win_region.top, win_region.left + win_region.width, win_region.top + win_region.height)
            else:
                capture_bbox = None

            hay = VisionEngine.capture_screen(bbox=capture_bbox)
            if hay is None:
                self.log("屏幕截图失败，图像检测返回否", "warning")
                return 'no'
            for img in imgs:
                if self.stop_event.is_set():
                    return '__STOP__'
                if not isinstance(img, dict) or img.get('image') is None:
                    self.log("图像检测节点包含无效图片", "warning")
                    return 'no'
                if not VisionEngine._advanced_match(
                    img.get('image'), hay, safe_float(data.get('confidence', 0.9)),
                    self.stop_event, True, True, self.scaling_ratio, 'hybrid'
                )[0]:
                    return 'no'
            return 'yes'
        return 'out'

class HistoryManager:
    def __init__(self, editor):
        self.editor = editor
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50

    def save_state(self):
        state = self.editor.get_data()
        if self.undo_stack:
            last = json.dumps(self.undo_stack[-1], sort_keys=True)
            curr = json.dumps(state, sort_keys=True)
            if last == curr:
                return False
        self.undo_stack.append(state)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.editor.app.mark_dirty(True)
        return True

    def begin_edit(self):
        return self.editor.get_data()

    def commit_edit(self, before):
        if not isinstance(before, dict):
            return False
        current = self.editor.get_data()
        before_json = json.dumps(before, sort_keys=True)
        current_json = json.dumps(current, sort_keys=True)
        if before_json == current_json:
            return False
        if not self.undo_stack or json.dumps(self.undo_stack[-1], sort_keys=True) != before_json:
            self.undo_stack.append(before)
            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.editor.app.mark_dirty(True)
        return True

    def undo(self, event=None):
        if not self.undo_stack:
            return
        current = self.editor.get_data()
        if self.editor.load_data(self.undo_stack[-1]):
            self.undo_stack.pop()
            self.redo_stack.append(current)
            self.editor.app.property_panel.show_empty()
            self.editor.app.mark_dirty(True)

    def redo(self, event=None):
        if not self.redo_stack:
            return
        current = self.editor.get_data()
        if self.editor.load_data(self.redo_stack[-1]):
            self.redo_stack.pop()
            self.undo_stack.append(current)
            self.editor.app.property_panel.show_empty()
            self.editor.app.mark_dirty(True)

class GraphNode:
    next_node_number = 1

    def __init__(self, canvas, node_id, ntype, x, y, data=None):
        self.canvas, self.id, self.type, self.x, self.y = canvas, node_id, ntype, x, y
        self.data = data if data is not None else {}

        if 'node_number' not in self.data:
            self.data['node_number'] = GraphNode.next_node_number
            GraphNode.next_node_number += 1

        cfg = NODE_CONFIG.get(ntype, {})
        self.title_text, self.header_color = cfg.get('title', ntype), cfg.get('color', COLORS['bg_header'])
        if '_user_title' not in self.data:
            self.data['_user_title'] = self.title_text

        self.w = NODE_WIDTH
        self.h = 100
        self.tags = (f"node_{self.id}", "node")
        self.has_breakpoint = False
        self.widgets = []
        self.refresh_outputs()
        self.draw()

    def refresh_outputs(self):
        cfg = NODE_CONFIG.get(self.type, {})
        if self.type == 'sequence':
            steps = max(1, min(20, safe_int(self.data.get('num_steps', 3), 3)))
            self.outputs = [str(i) for i in range(1, steps + 1)] + ['else']
        elif self.type == 'var_switch':
            if self.data.get('var_name'):
                self.outputs = ['yes', 'no']
            else:
                self.outputs = [c['id'] for c in self.data.get('cases', []) if isinstance(c, dict) and c.get('id')] + ['else']
        else:
            self.outputs = list(cfg.get('outputs', []))

    def draw(self):
        self.refresh_outputs()
        z = self.canvas.zoom
        vx, vy, vw = self.x * z, self.y * z, self.w * z
        self.clear_widgets()
        self.canvas.delete(f"node_{self.id}")

        ports_h = max(1, len(self.outputs)) * PORT_STEP_Y
        widgets_h = 0
        self.has_widgets = False

        self.is_visual_node = self.type in ['image', 'if_img', 'if_static']
        self.is_app_node = self.type == 'open_app'
        self.is_bind_win_node = self.type == 'bind_win'

        if not self.is_visual_node and not self.is_app_node and self.type not in ['reroute', 'start', 'end', 'bind_win', 'var_switch', 'sequence', 'set_var', 'clipboard', 'web', 'if_sound']:
            widgets_h = 35
            self.has_widgets = True

        img_display_h = 0
        toolbar_h = 0
        if self.is_visual_node:
            toolbar_h = 38
            if self.type == 'if_img' and self.data.get('images'):
                img_list = self.data.get('images', [])
                if len(img_list) > 0:
                    rows = math.ceil(len(img_list) / 2.0)
                    img_display_h = (rows * 60) + 10
            else:
                target_img = self.data.get('image') if self.type == 'image' else self.data.get('roi_preview')
                if target_img and isinstance(target_img, Image.Image):
                    try:
                        iw, ih = target_img.size
                        scale = (self.w - 8) / iw
                        calc_h = int(ih * scale)
                        img_display_h = min(calc_h, 120) + 5
                    except Exception:
                        img_display_h = 80
        if self.is_app_node or self.is_bind_win_node:
            toolbar_h = 35

        if self.type == 'reroute':
            self.w, self.h = 30, 30
            vw, vh = self.w * z, self.h * z
            self.body_item = self.canvas.create_oval(vx, vy, vx + vw, vy + vh, fill=COLORS['wire'], outline=COLORS['bg_canvas'], width=2 * z, tags=self.tags + ('body', 'port_in', 'port_out', 'out'))
            self.sel_rect = self.canvas.create_rectangle(vx - 3 * z, vy - 3 * z, vx + vw + 3 * z, vy + vh + 3 * z, outline=COLORS['accent'], width=3 * z, tags=self.tags + ('selection',), state='hidden')
            if self.id in self.canvas.selected_node_ids:
                self.canvas.itemconfig(self.sel_rect, state='normal')
            self.hover_rect = self.canvas.create_rectangle(vx, vy, vx + vw, vy + vh, tags=self.tags + ('hover',), state='hidden')
            return

        self.h = PORT_START_Y + ports_h + widgets_h + toolbar_h + img_display_h + 8
        vh = self.h * z

        self.sel_rect = self.canvas.create_rectangle(vx - 3 * z, vy - 3 * z, vx + vw + 3 * z, vy + vh + 3 * z, outline=COLORS['accent'], width=3 * z, tags=self.tags + ('selection',), state='hidden')

        self.canvas.create_rectangle(vx + 3 * z, vy + 3 * z, vx + vw + 3 * z, vy + vh + 3 * z, fill=COLORS['shadow'], outline="", tags=self.tags)
        self.body_item = self.canvas.create_rectangle(vx, vy, vx + vw, vy + vh, fill=COLORS['bg_node'], outline=COLORS['bg_header'], width=1.5 * z, tags=self.tags + ('body',))
        self.canvas.create_rectangle(vx, vy, vx + vw, vy + HEADER_HEIGHT * z, fill=self.header_color, outline="", tags=self.tags + ('header',))
        title_str = str(self.data.get('_user_title', self.title_text))
        if len(title_str) > 16:
            title_str = title_str[:15] + "…"
        self.canvas.create_text(vx + 10 * z, vy + 14 * z, text=title_str, fill=COLORS['node_header_fg'], font=('Microsoft YaHei UI', max(7, int(10 * z)), 'bold'), anchor="w", tags=self.tags)
        if self.has_breakpoint:
            self.canvas.create_oval(vx + vw - 14 * z, vy + 8 * z, vx + vw - 6 * z, vy + 16 * z, fill=COLORS['breakpoint'], outline=COLORS['node_header_fg'], width=1.5, tags=self.tags)

        if self.type != 'start':
            iy = self.get_input_port_y(visual=True)
            self.canvas.create_oval(vx - 6 * z, iy - 6 * z, vx + 6 * z, iy + 6 * z, fill=COLORS['socket'], outline=COLORS['bg_canvas'], width=2 * z, tags=self.tags + ('port_in',))

        port_labels = PORT_TRANSLATION.copy()
        if self.type == 'var_switch':
            for c in self.data.get('cases', []):
                if isinstance(c, dict) and c.get('id'):
                    port_labels[c['id']] = f"={c.get('value', '')}"
        elif self.type == 'sequence':
            for out_p in self.outputs:
                if out_p.isdigit():
                    port_labels[out_p] = f"步骤 {out_p}"

        for i, name in enumerate(self.outputs):
            py = self.get_output_port_y(i, visual=True)
            self.canvas.create_oval(vx + vw - 6 * z, py - 6 * z, vx + vw + 6 * z, py + 6 * z, fill=COLORS.get(f"socket_{name}", COLORS['socket']), outline=COLORS['bg_canvas'], width=2 * z, tags=self.tags + (f'port_out_{name}', 'port_out', name))
            self.canvas.create_text(vx + vw - 12 * z, py, text=port_labels.get(name, name), fill=COLORS['fg_sub'], font=('Microsoft YaHei UI', max(6, int(9 * z))), anchor="e", tags=self.tags)

        self.widget_offset_y = PORT_START_Y + ports_h
        if self.has_widgets and z > 0.6:
            self.render_widgets(vx, vy, vw, z)
            self.widget_offset_y += 35

        if self.is_visual_node:
            toolbar_y = vy + (self.widget_offset_y * z)
            tool_frame = tk.Frame(self.canvas, bg=COLORS['bg_node'])
            def cmd_snip(nid=self.id):
                self.canvas.select_node(nid)
                self.canvas.app.do_snip()
            btn_snip = tk.Button(tool_frame, text="🎯 抓取目标", command=cmd_snip, bg=COLORS['accent'], fg='#ffffff', bd=0, font=('Microsoft YaHei UI', max(7, int(9 * z)), 'bold'), activebackground=COLORS['btn_hover'], cursor='hand2')
            btn_snip.pack(side='left', fill='x', expand=True, padx=0, pady=0)
            self.widgets.append(self.canvas.create_window(vx + vw / 2, toolbar_y, window=tool_frame, width=vw - 10 * z, height=26 * z, anchor='n', tags=self.tags))

            img_start_y = toolbar_y + 32 * z
            if self.type == 'if_img' and self.data.get('images'):
                imgs = self.data.get('images', [])
                cell_w = (vw - 12 * z) / 2
                cell_h = 55 * z
                for idx, item in enumerate(imgs):
                    if not item.get('image'):
                        continue
                    col = idx % 2
                    row = idx // 2
                    ix = vx + 4 * z + col * (cell_w + 4 * z)
                    iy = img_start_y + row * (cell_h + 4 * z)
                    self.canvas.create_rectangle(ix, iy, ix + cell_w, iy + cell_h, fill=COLORS['preview_bg'], outline=COLORS['wire'], width=1, tags=self.tags)
                    thumb_img = item['image'].copy()
                    thumb_img.thumbnail((max(1, int(cell_w)), max(1, int(cell_h))), Image.Resampling.LANCZOS)
                    tk_thumb = ImageTk.PhotoImage(thumb_img)
                    item['_tk_cache'] = tk_thumb
                    self.canvas.create_image(ix + cell_w / 2, iy + cell_h / 2, image=tk_thumb, anchor='center', tags=self.tags)
                    self.canvas.create_text(ix + 3 * z, iy + 3 * z, text=str(idx + 1), fill=COLORS['node_header_fg'], font=('Microsoft YaHei UI', max(6, int(8 * z)), 'bold'), anchor='nw', tags=self.tags)
            elif img_display_h > 0:
                target_img = self.data.get('image') if self.type == 'image' else self.data.get('roi_preview')
                if target_img and isinstance(target_img, Image.Image):
                    disp_w = int(vw - 8 * z)
                    disp_h = int((img_display_h - 5) * z)
                    if disp_w > 0 and disp_h > 0:
                        thumb = target_img.copy()
                        thumb.thumbnail((disp_w, disp_h), Image.Resampling.LANCZOS)
                        tk_thumb = ImageTk.PhotoImage(thumb)
                        self.data['_tk_cache'] = tk_thumb
                        self.canvas.create_rectangle(vx + 4 * z, img_start_y, vx + vw - 4 * z, img_start_y + disp_h, fill=COLORS['preview_bg'], outline=COLORS['wire'], width=1, tags=self.tags)
                        self.canvas.create_image(vx + vw / 2, img_start_y + disp_h / 2, image=tk_thumb, anchor='center', tags=self.tags)

        if self.is_app_node:
            toolbar_y = vy + (self.widget_offset_y * z)
            path = self.data.get('path', '')
            filename = os.path.basename(path) if path else "未选择程序"
            if len(filename) > 20:
                filename = filename[:18] + "..."
            icon_x = vx + 12 * z
            icon_y = toolbar_y + 5 * z
            self.canvas.create_rectangle(icon_x, icon_y, icon_x + 18 * z, icon_y + 22 * z, fill='#5c6bc0', outline='', tags=self.tags)
            self.canvas.create_polygon(icon_x + 12 * z, icon_y, icon_x + 18 * z, icon_y, icon_x + 18 * z, icon_y + 6 * z, fill='#3949ab', outline='', tags=self.tags)
            self.canvas.create_text(icon_x + 26 * z, icon_y + 11 * z, text=filename, fill=COLORS['fg_text'], font=('Microsoft YaHei UI', max(6, int(9 * z))), anchor='w', tags=self.tags)
        elif self.is_bind_win_node:
            toolbar_y = vy + (self.widget_offset_y * z)
            exe_name = self.data.get('exe_name', '')
            display_name = exe_name if exe_name else "未绑定进程"
            if len(display_name) > 20:
                display_name = display_name[:18] + "..."
            icon_x = vx + 12 * z
            icon_y = toolbar_y + 5 * z
            self.canvas.create_rectangle(icon_x, icon_y, icon_x + 18 * z, icon_y + 22 * z, fill='#00695c', outline='', tags=self.tags)
            self.canvas.create_text(icon_x + 5 * z, icon_y + 11 * z, text="⚓", fill='#ffffff', font=('Microsoft YaHei UI', max(8, int(11 * z))), anchor='w', tags=self.tags)
            self.canvas.create_text(icon_x + 26 * z, icon_y + 11 * z, text=display_name, fill=COLORS['fg_text'], font=('Microsoft YaHei UI', max(6, int(9 * z))), anchor='w', tags=self.tags)

        if self.id in self.canvas.selected_node_ids:
            self.canvas.itemconfig(self.sel_rect, state='normal')
            self.canvas.tag_lower(self.sel_rect, self.body_item)
        self.hover_rect = self.canvas.create_rectangle(vx - 1 * z, vy - 1 * z, vx + vw + 1 * z, vy + vh + 1 * z, outline=COLORS['hover'], width=1 * z, state='hidden', tags=self.tags + ('hover',))

    def render_widgets(self, vx, vy, vw, z):
        y_cursor = vy + (self.widget_offset_y * z)
        def create_entry(key, default, label_txt, width=8):
            val = self.data.get(key, default)
            frame = tk.Frame(self.canvas, bg=COLORS['bg_node'])
            tk.Label(frame, text=label_txt, bg=COLORS['bg_node'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 9)).pack(side='left')
            e = tk.Entry(frame, bg=COLORS['input_bg'], fg=COLORS['input_fg'], bd=0, width=width, insertbackground=COLORS['input_fg'], font=('Microsoft YaHei UI', 9))
            e.insert(0, str(val))
            e.pack(side='left', padx=5, ipady=2)
            e.bind("<FocusOut>", lambda ev: self.update_data(key, e.get(), refresh_ui=True))
            e.bind("<Return>", lambda ev: [self.update_data(key, e.get(), refresh_ui=True), self.canvas.focus_set()])
            self.widgets.append(self.canvas.create_window(vx + 10 * z, y_cursor, window=frame, anchor='nw', tags=self.tags))

        def create_combo(key, options_map, default, width=8):
            if isinstance(options_map, dict):
                options = list(options_map.values())
                curr_val = self.data.get(key, default)
                disp_val = options_map.get(curr_val, curr_val)
                map_inv = {v: k for k, v in options_map.items()}
            else:
                options = options_map
                disp_val = self.data.get(key, default)
                map_inv = None
            cb = ttk.Combobox(self.canvas, values=options, state='readonly', width=width, font=('Microsoft YaHei UI', 9))
            try:
                cb.set(disp_val)
            except Exception:
                pass
            def on_sel(ev):
                val = cb.get()
                final_val = map_inv.get(val, val) if map_inv else val
                self.update_data(key, final_val, refresh_ui=True)
            cb.bind("<<ComboboxSelected>>", on_sel)
            self.widgets.append(self.canvas.create_window(vx + 10 * z, y_cursor, window=cb, anchor='nw', tags=self.tags))

        if self.type == 'wait':
            create_entry('seconds', '1.0', '等待(s):')
        elif self.type == 'loop':
            create_entry('count', '5', '循环:')
        elif self.type == 'keyboard':
            create_entry('text', '', '文本:', width=10)
        elif self.type == 'cmd':
            create_entry('command', '', '命令:', width=11)
        elif self.type == 'notify':
            create_entry('msg', '执行到此节点', '提示:', width=10)
        elif self.type == 'mouse':
            create_combo('mouse_action', MOUSE_ACTIONS, 'click', width=12)

    def clear_widgets(self):
        for w in self.widgets:
            try:
                widget_name = self.canvas.itemcget(w, 'window')
                if widget_name:
                    self.canvas.nametowidget(widget_name).destroy()
            except Exception:
                pass
            try:
                self.canvas.delete(w)
            except Exception:
                pass
        self.widgets.clear()

    def update_data(self, key, value, refresh_ui=True):
        if str(self.data.get(key)) == str(value) and not isinstance(value, (list, dict, Image.Image)):
            return
        if refresh_ui:
            self.canvas.history.save_state()
        self.data[key] = value

        redraw_keys = {
            'msg', 'seconds', 'count', 'command', 'title', 'text',
            'mouse_action', 'cases', 'var_name', 'num_steps',
            'image', 'images', 'roi_preview', 'path', 'exe_name',
            'class_name', '_user_title'
        }
        if key in redraw_keys and refresh_ui:
            self.draw()
            self.canvas.redraw_links()

        if refresh_ui and self.canvas.app.property_panel.current_node == self:
            self.canvas.app.property_panel.load_node(self)

    def set_sensor_active(self, is_active):
        self.canvas.itemconfig(self.body_item, outline=COLORS['active_border'] if is_active else COLORS['bg_header'])

    def get_input_port_y(self, visual=False):
        if self.type == 'reroute':
            return (self.y + 15) * self.canvas.zoom if visual else self.y + 15
        offset = HEADER_HEIGHT + 14
        return (self.y + offset) * self.canvas.zoom if visual else self.y + offset

    def get_output_port_y(self, index=0, visual=False):
        if self.type == 'reroute':
            return (self.y + 15) * self.canvas.zoom if visual else self.y + 15
        offset = PORT_START_Y + (index * PORT_STEP_Y)
        return (self.y + offset) * self.canvas.zoom if visual else self.y + offset

    def get_port_y_by_name(self, port_name, visual=False):
        try:
            idx = self.outputs.index(port_name)
        except ValueError:
            idx = 0
        return self.get_output_port_y(idx, visual)

    def move_to(self, new_x, new_y):
        """平滑移动节点到新逻辑坐标，不销毁重建内嵌控件，避免松手卡顿"""
        dx = (new_x - self.x) * self.canvas.zoom
        dy = (new_y - self.y) * self.canvas.zoom
        self.x, self.y = new_x, new_y
        if abs(dx) > 1e-4 or abs(dy) > 1e-4:
            self.canvas.move(self.tags[0], dx, dy)

    def set_pos(self, x, y):
        self.x, self.y = x, y
        self.draw()

    def set_selected(self, selected):
        self.canvas.itemconfig(self.sel_rect, state='normal' if selected else 'hidden')
        if selected:
            self.canvas.tag_lower(self.sel_rect, self.body_item)

    def contains(self, log_x, log_y):
        return self.x <= log_x <= self.x + self.w and self.y <= log_y <= self.y + self.h

    def update_position(self, dx, dy):
        self.canvas.move(self.tags[0], dx, dy)

class FlowEditor(tk.Canvas):
    WORLD_EXTENT = 50000
    MIN_ZOOM = 0.25
    MAX_ZOOM = 3.0

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS['bg_canvas'], highlightthickness=0, **kwargs)
        self.app, self.nodes, self.links = app, {}, []
        self.selected_node_ids = set()
        self.drag_data = {"type": None}
        self.wire_start = self.temp_wire = self.selection_box = None
        self.history = HistoryManager(self)
        self.zoom = 1.0
        self._node_clipboard = []
        self._node_clipboard_links = []
        self._space_down = False
        self._initial_view_pending = True
        self._set_scrollregion()
        self.bind_events()
        self.full_redraw()

    def bind_events(self):
        self.bind("<ButtonPress-1>", self.on_lmb_press)
        self.bind("<B1-Motion>", self.on_lmb_drag)
        self.bind("<ButtonRelease-1>", self.on_lmb_release)
        self.bind("<Double-Button-1>", self.on_double_click)
        self.bind("<ButtonPress-3>", self.on_rmb_press)
        self.bind("<B3-Motion>", self.on_rmb_drag)
        self.bind("<ButtonRelease-3>", self.on_rmb_release)
        self.bind("<ButtonPress-2>", self.on_pan_start)
        self.bind("<B2-Motion>", self.on_pan_drag)
        self.bind("<ButtonRelease-2>", self.on_pan_end)
        self.bind("<Motion>", self.on_mouse_move)
        self.bind("<MouseWheel>", self.on_scroll)
        self.bind("<Button-4>", self.on_scroll)
        self.bind("<Button-5>", self.on_scroll)
        self.bind("<KeyPress-space>", self._space_press)
        self.bind("<KeyRelease-space>", self._space_release)
        self.bind("<KeyPress-f>", self._shortcut_fit_view)
        self.bind("<KeyPress-F>", self._shortcut_fit_view)
        self.bind("<Control-KeyPress-0>", self._shortcut_reset_zoom)
        self.bind("<Control-KeyPress-equal>", lambda e: self._shortcut_zoom(e, 1.1))
        self.bind("<Control-KeyPress-plus>", lambda e: self._shortcut_zoom(e, 1.1))
        self.bind("<Control-KeyPress-KP_Add>", lambda e: self._shortcut_zoom(e, 1.1))
        self.bind("<Control-KeyPress-minus>", lambda e: self._shortcut_zoom(e, 1 / 1.1))
        self.bind("<Control-KeyPress-KP_Subtract>", lambda e: self._shortcut_zoom(e, 1 / 1.1))
        self.bind("<Configure>", self._on_canvas_configure)

    def on_mouse_move(self, event):
        lx, ly = self.get_logical_pos(event.x, event.y)
        coord_lbl = getattr(self.app, "coord_status", None)
        if coord_lbl is not None and coord_lbl.winfo_exists():
            try:
                coord_lbl.configure(text=f"X: {int(lx)}  Y: {int(ly)}")
            except tk.TclError:
                pass

    def _is_text_input(self, event):
        try:
            widget_class = event.widget.winfo_class()
        except (AttributeError, tk.TclError):
            return False
        return widget_class in {"Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox", "Listbox"}

    def _shortcut_undo(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.history.undo()
        return "break"

    def _shortcut_redo(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.history.redo()
        return "break"

    def _shortcut_select_all(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if not self.nodes:
            return "break"
        self.select_node(None)
        for node_id, node in self.nodes.items():
            self.selected_node_ids.add(node_id)
            node.set_selected(True)
        self.app.property_panel.show_multi_select(len(self.selected_node_ids))
        self.redraw_links()
        return "break"

    def _shortcut_fit_view(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.fit_view()
        return "break"

    def _shortcut_reset_zoom(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        self.reset_zoom()
        return "break"

    def _shortcut_zoom(self, event, factor):
        if event is not None and self._is_text_input(event):
            return None
        self.zoom_by(factor)
        return "break"

    def _space_press(self, _event=None):
        self._space_down = True
        self.config(cursor="fleur")
        return "break"

    def _space_release(self, _event=None):
        self._space_down = False
        if self.drag_data.get("type") == "pan":
            self.drag_data = {"type": None}
        self.config(cursor="arrow")
        return "break"

    def _set_scrollregion(self):
        extent = self.WORLD_EXTENT * self.zoom
        self.configure(scrollregion=(-extent, -extent, extent, extent))

    def _place_world_point(self, world_x, world_y, screen_x, screen_y):
        extent = self.WORLD_EXTENT * self.zoom
        span = extent * 2.0
        target_left = world_x * self.zoom - screen_x
        target_top = world_y * self.zoom - screen_y
        self.xview_moveto(max(0.0, min(1.0, (target_left + extent) / span)))
        self.yview_moveto(max(0.0, min(1.0, (target_top + extent) / span)))

    def _on_canvas_configure(self, event=None):
        if self._initial_view_pending and self.winfo_width() > 2 and self.winfo_height() > 2:
            self._set_scrollregion()
            self.xview_moveto(0.5)
            self.yview_moveto(0.5)
            self._initial_view_pending = False
        self._draw_grid()
        self.redraw_links()

    def _update_zoom_label(self):
        label = getattr(self, "zoom_label", None)
        if label is not None and label.winfo_exists():
            try:
                label.configure(text=f"{round(self.zoom * 100)}%")
            except tk.TclError:
                pass
        status = getattr(self.app, "view_status", None)
        if status is not None and status.winfo_exists():
            try:
                sel_txt = f"  ·  已选 {len(self.selected_node_ids)} 项" if self.selected_node_ids else ""
                status.configure(text=f"{len(self.nodes)} 个节点  ·  {len(self.links)} 条连线{sel_txt}")
            except tk.TclError:
                pass

    def on_rmb_press(self, event):
        self._rmb_start = (event.x, event.y)
        self._rmb_moved = False
        self.scan_mark(event.x, event.y)

    def on_rmb_drag(self, event):
        if abs(event.x - self._rmb_start[0]) > 5 or abs(event.y - self._rmb_start[1]) > 5:
            self._rmb_moved = True
        if self._rmb_moved:
            self.config(cursor="fleur")
            self.scan_dragto(event.x, event.y, gain=1)
            self._draw_grid()

    def on_rmb_release(self, event):
        self.config(cursor="arrow")
        if not getattr(self, '_rmb_moved', False):
            self.on_right_click_menu(event)

    def on_pan_start(self, event):
        self.config(cursor="fleur")
        self.scan_mark(event.x, event.y)

    def on_pan_drag(self, event):
        self.scan_dragto(event.x, event.y, gain=1)
        self._draw_grid()

    def on_pan_end(self, event):
        self.config(cursor="arrow")

    def _on_delete_press(self, event=None):
        if event is not None and self._is_text_input(event):
            return None
        if self.selected_node_ids:
            self.history.save_state()
            for node_id in list(self.selected_node_ids):
                self.delete_node(node_id)
            self.select_node(None)
        return "break"

    def get_logical_pos(self, event_x, event_y):
        return self.canvasx(event_x) / self.zoom, self.canvasy(event_y) / self.zoom

    def full_redraw(self, event=None):
        for node in list(self.nodes.values()):
            node.clear_widgets()
        self.config(bg=COLORS['bg_canvas'])
        self._set_scrollregion()
        self.delete("all")
        self._draw_grid()
        for node in self.nodes.values():
            node.draw()
        self.redraw_links()
        self._update_zoom_label()

    def _draw_grid(self):
        self.delete("grid")
        w, h = self.winfo_width(), self.winfo_height()
        x1, y1, x2, y2 = self.canvasx(0), self.canvasy(0), self.canvasx(w), self.canvasy(h)
        if (step := int(GRID_SIZE * self.zoom)) < 6:
            return
        start_x, start_y = int(x1 // step) * step, int(y1 // step) * step
        for i in range(start_x, int(x2) + step, step):
            self.create_line(i, y1, i, y2, fill=COLORS['grid'], tags="grid")
        for i in range(start_y, int(y2) + step, step):
            self.create_line(x1, i, x2, i, fill=COLORS['grid'], tags="grid")
        self.tag_lower("grid")

    def add_node(self, ntype, x, y, data=None, node_id=None, save_history=True):
        if save_history:
            self.history.save_state()
        node = GraphNode(self, node_id or str(uuid.uuid4()), ntype, x, y, data)
        self.nodes[node.id] = node
        self.select_node(node.id)
        return node

    def delete_node(self, node_id):
        if node_id in self.nodes:
            self.links = [l for l in self.links if l.get('source') != node_id and l.get('target') != node_id]
            self.nodes[node_id].clear_widgets()
            self.delete(f"node_{node_id}")
            del self.nodes[node_id]
            self.redraw_links()

    def on_scroll(self, event):
        if getattr(event, "num", None) == 4:
            delta = 120
        elif getattr(event, "num", None) == 5:
            delta = -120
        else:
            delta = getattr(event, "delta", 0)
        if not delta:
            return "break"
        factor = 1.1 ** (delta / 120.0)
        self._zoom_at(self.zoom * factor, event.x, event.y)
        return "break"

    def _zoom_at(self, new_zoom, screen_x, screen_y):
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(new_zoom)))
        if abs(new_zoom - self.zoom) < 1e-6:
            return
        world_x = self.canvasx(screen_x) / self.zoom
        world_y = self.canvasy(screen_y) / self.zoom
        self.zoom = new_zoom
        self._set_scrollregion()
        self._place_world_point(world_x, world_y, screen_x, screen_y)
        self.full_redraw()

    def zoom_by(self, factor):
        self._zoom_at(self.zoom * factor, self.winfo_width() / 2, self.winfo_height() / 2)

    def reset_zoom(self):
        self._zoom_at(1.0, self.winfo_width() / 2, self.winfo_height() / 2)

    def fit_view(self, _event=None, selected_only=True):
        nodes = [self.nodes[nid] for nid in self.selected_node_ids if nid in self.nodes] if selected_only else []
        if not nodes:
            nodes = list(self.nodes.values())
        view_w = max(100, self.winfo_width())
        view_h = max(100, self.winfo_height())
        if not nodes:
            self.zoom = 1.0
            self._set_scrollregion()
            self._place_world_point(0, 0, view_w / 2, view_h / 2)
            self.full_redraw()
            return

        left = min(node.x for node in nodes)
        top = min(node.y for node in nodes)
        right = max(node.x + node.w for node in nodes)
        bottom = max(node.y + node.h for node in nodes)
        world_w = max(1, right - left)
        world_h = max(1, bottom - top)
        padding = 120
        zoom_x = max(1.0, view_w - padding) / world_w
        zoom_y = max(1.0, view_h - padding) / world_h
        self.zoom = max(self.MIN_ZOOM, min(1.35, zoom_x, zoom_y))
        self._set_scrollregion()
        self._place_world_point((left + right) / 2, (top + bottom) / 2, view_w / 2, view_h / 2)
        self.full_redraw()

    def on_double_click(self, event):
        world_x, world_y = self.get_logical_pos(event.x, event.y)
        if any(node.contains(world_x, world_y) for node in self.nodes.values()):
            return None
        self.open_quick_add(event.x_root, event.y_root, world_x, world_y)
        return "break"

    def open_quick_add(self, screen_x, screen_y, world_x, world_y):
        popup = tk.Toplevel(self)
        popup.title("快速添加节点")
        popup.configure(bg=COLORS['bg_panel'], highlightthickness=1, highlightbackground=COLORS['accent'])
        popup.transient(self.winfo_toplevel())
        popup.resizable(False, False)
        width, height = 380, 400
        x = max(8, min(screen_x, self.winfo_screenwidth() - width - 8))
        y = max(8, min(screen_y, self.winfo_screenheight() - height - 50))
        popup.geometry(f"{width}x{height}+{x}+{y}")

        tk.Label(
            popup, text="⚡ 快速添加节点", bg=COLORS['bg_panel'], fg=COLORS['fg_text'],
            font=('Microsoft YaHei UI', 10, 'bold'), anchor='w'
        ).pack(fill='x', padx=12, pady=(12, 6))
        search = tk.Entry(
            popup, bg=COLORS['input_bg'], fg=COLORS['input_fg'],
            insertbackground=COLORS['input_fg'], relief='flat', bd=0,
            font=('Microsoft YaHei UI', 10)
        )
        search.pack(fill='x', padx=12, pady=(0, 8), ipady=6)
        list_frame = tk.Frame(popup, bg=COLORS['bg_panel'])
        list_frame.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical')
        choices = tk.Listbox(
            list_frame, bg=COLORS['bg_card'], fg=COLORS['fg_text'],
            selectbackground=COLORS['accent'], selectforeground=COLORS['accent_fg'],
            activestyle='none', relief='flat', highlightthickness=0,
            font=('Microsoft YaHei UI', 9), yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=choices.yview)
        scrollbar.pack(side='right', fill='y')
        choices.pack(side='left', fill='both', expand=True)
        tk.Label(
            popup, text="回车添加 · 双击添加 · Esc 取消", bg=COLORS['bg_panel'],
            fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8), anchor='w'
        ).pack(fill='x', padx=12, pady=(0, 10))

        node_types = [node_type for node_type in NODE_CONFIG if node_type != 'bind_win']
        filtered_types = []

        def refresh_choices(_event=None):
            query = search.get().strip().casefold()
            filtered_types.clear()
            choices.delete(0, 'end')
            for node_type in node_types:
                config = NODE_CONFIG[node_type]
                searchable = f"{node_type} {config.get('title', '')} {config.get('desc', '')}".casefold()
                if not query or query in searchable:
                    filtered_types.append(node_type)
                    choices.insert('end', f"{config.get('title', node_type)}   —   {config.get('desc', '')}")
            if filtered_types:
                choices.selection_set(0)
                choices.activate(0)

        def add_selected(_event=None):
            selection = choices.curselection()
            if not selection and filtered_types:
                selection = (0,)
            if not selection:
                return "break"
            node_type = filtered_types[selection[0]]
            popup.destroy()
            self.history.save_state()
            self.add_node(node_type, round(world_x / GRID_SIZE) * GRID_SIZE, round(world_y / GRID_SIZE) * GRID_SIZE, save_history=False)
            self.focus_set()
            return "break"

        def move_to_list(_event=None):
            if filtered_types:
                choices.focus_set()
                choices.selection_clear(0, 'end')
                choices.selection_set(0)
                choices.activate(0)
            return "break"

        search.bind('<KeyRelease>', refresh_choices)
        search.bind('<Down>', move_to_list)
        search.bind('<Return>', add_selected)
        choices.bind('<Double-Button-1>', add_selected)
        choices.bind('<Return>', add_selected)
        popup.bind('<Escape>', lambda _e: popup.destroy())
        refresh_choices()
        search.focus_set()

    def on_lmb_press(self, event):
        self.focus_set()
        if self._space_down:
            self.drag_data = {"type": "pan"}
            self.scan_mark(event.x, event.y)
            self.config(cursor="fleur")
            return
        lx, ly = self.get_logical_pos(event.x, event.y)
        vx, vy = self.canvasx(event.x), self.canvasy(event.y)
        z = self.zoom
        items = self.find_overlapping(vx - 10 * z, vy - 10 * z, vx + 10 * z, vy + 10 * z)
        for item in items:
            t_list = self.gettags(item)
            if "port_out" in t_list and (nid := next((t[5:] for t in t_list if t.startswith("node_")), None)) and nid in self.nodes:
                # 若是 reroute 中继点，只有点击在右侧半圆区域或按住 Shift 时才拉出连线，否则允许拖动中继点
                node_obj = self.nodes[nid]
                if node_obj.type == 'reroute' and lx < node_obj.x + node_obj.w * 0.55 and not (event.state & 0x0001):
                    continue
                self.wire_start = {
                    'node': node_obj,
                    'port': next((t for t in t_list if t in node_obj.outputs), 'out')
                }
                self.drag_data = {"type": "wire"}
                return

        clicked_node = next((node for node in reversed(list(self.nodes.values())) if node.contains(lx, ly)), None)
        if clicked_node:
            ctrl_down = bool(event.state & 0x0004)
            if ctrl_down and clicked_node.id in self.selected_node_ids:
                self.selected_node_ids.remove(clicked_node.id)
                clicked_node.set_selected(False)
                if not self.selected_node_ids:
                    self.app.property_panel.show_empty()
                elif len(self.selected_node_ids) == 1:
                    self.app.property_panel.load_node(self.nodes[next(iter(self.selected_node_ids))])
                else:
                    self.app.property_panel.show_multi_select(len(self.selected_node_ids))
                self.drag_data = {"type": None}
                self.redraw_links()
                return
            if not ctrl_down and clicked_node.id not in self.selected_node_ids:
                self.select_node(clicked_node.id)
            elif ctrl_down:
                self.select_node(clicked_node.id, add=True)
            self.drag_data = {"type": "node", "last_vx": vx, "last_vy": vy, "dragged": False, "history_saved": False}
            for nid in self.selected_node_ids:
                self.tag_raise(f"node_{nid}")
        else:
            if not (event.state & 0x0004):
                self.select_node(None)
            self.drag_data = {"type": "box_select", "start_vx": vx, "start_vy": vy}
            self.selection_box = self.create_rectangle(vx, vy, vx, vy, outline=COLORS['select_box'], width=2, dash=(4, 4), tags="selection_box")

    def on_lmb_drag(self, event):
        vx, vy = self.canvasx(event.x), self.canvasy(event.y)
        if self.drag_data["type"] == "pan":
            self.scan_dragto(event.x, event.y, gain=1)
            self._draw_grid()
        elif self.drag_data["type"] == "node":
            if not self.drag_data.get("history_saved", False):
                self.history.save_state()
                self.drag_data["history_saved"] = True
            self.drag_data["dragged"] = True
            dx = vx - self.drag_data["last_vx"]
            dy = vy - self.drag_data["last_vy"]
            self.drag_data["last_vx"] = vx
            self.drag_data["last_vy"] = vy
            for nid in self.selected_node_ids:
                if nid in self.nodes:
                    node = self.nodes[nid]
                    node.x += dx / self.zoom
                    node.y += dy / self.zoom
                    node.update_position(dx, dy)
            self.redraw_links()
        elif self.drag_data["type"] == "box_select":
            if self.selection_box:
                self.coords(self.selection_box, self.drag_data["start_vx"], self.drag_data["start_vy"], vx, vy)
        elif self.drag_data["type"] == "wire":
            if self.temp_wire:
                self.delete(self.temp_wire)
            n, p = self.wire_start['node'], self.wire_start['port']
            x_start = (n.x + n.w) * self.zoom if n.type != 'reroute' else (n.x + 15) * self.zoom
            self.temp_wire = self.draw_bezier(x_start, n.get_port_y_by_name(p, visual=True), vx, vy, state="active")

    def on_lmb_release(self, event):
        if self.drag_data.get("type") == "pan":
            self.config(cursor="fleur" if self._space_down else "arrow")
            self.drag_data = {"type": None}
            self._draw_grid()
            return
        if self.drag_data.get("type") == "node":
            if self.drag_data.get("dragged", False):
                for nid in self.selected_node_ids:
                    if nid in self.nodes:
                        snapped_x = round(self.nodes[nid].x / GRID_SIZE) * GRID_SIZE
                        snapped_y = round(self.nodes[nid].y / GRID_SIZE) * GRID_SIZE
                        self.nodes[nid].move_to(snapped_x, snapped_y)
                self.redraw_links()
        elif self.drag_data.get("type") == "box_select":
            if self.selection_box:
                coords = self.coords(self.selection_box)
                if coords and len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    overlapping = self.find_overlapping(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                    for item in overlapping:
                        for t in self.gettags(item):
                            if t.startswith("node_") and t[5:] in self.nodes:
                                self.select_node(t[5:], add=True)
                self.delete(self.selection_box)
                self.selection_box = None
        elif self.drag_data.get("type") == "wire":
            if self.temp_wire:
                self.delete(self.temp_wire)
            lx, ly = self.get_logical_pos(event.x, event.y)
            for node in self.nodes.values():
                is_reroute = node.type == 'reroute'
                dist = math.hypot(lx - (node.x + 15 if is_reroute else node.x), ly - node.get_input_port_y(visual=False))
                if node.id != self.wire_start['node'].id and (dist < (48 / self.zoom) or node.contains(lx, ly)):
                    if node.type == 'start':
                        continue
                    source_id = self.wire_start['node'].id
                    source_port = self.wire_start['port']
                    if not any(l.get('source') == source_id and l.get('source_port', 'out') == source_port and l.get('target') == node.id for l in self.links):
                        self.history.save_state()
                        self.links.append({'id': str(uuid.uuid4()), 'source': source_id, 'source_port': source_port, 'target': node.id})
                        self.redraw_links()
                    break
        self.drag_data, self.wire_start, self.temp_wire = {"type": None}, None, None

    def select_node(self, node_id, add=False):
        if not add:
            for nid in self.selected_node_ids:
                if nid in self.nodes:
                    self.nodes[nid].set_selected(False)
            self.selected_node_ids.clear()
        if node_id and node_id in self.nodes:
            self.selected_node_ids.add(node_id)
            self.nodes[node_id].set_selected(True)
        if not self.selected_node_ids:
            self.app.property_panel.show_empty()
        elif len(self.selected_node_ids) == 1:
            self.app.property_panel.load_node(self.nodes[next(iter(self.selected_node_ids))])
        else:
            self.app.property_panel.show_multi_select(len(self.selected_node_ids))
        self.redraw_links()

    def draw_bezier(self, x1, y1, x2, y2, state="normal", link_id=None, highlighted=False):
        offset = max(50 * self.zoom, abs(x1 - x2) * 0.45)
        width = 3.5 * self.zoom if highlighted else (2.8 * self.zoom if state == "active" else 2 * self.zoom)
        color = COLORS['wire_hl'] if highlighted else COLORS['wire_active' if state == "active" else 'wire']
        return self.create_line(
            x1, y1, x1 + offset, y1, x2 - offset, y2, x2, y2,
            smooth=True, splinesteps=36, fill=color, width=width,
            arrow=tk.LAST, arrowshape=(int(8 * self.zoom), int(10 * self.zoom), int(4 * self.zoom)),
            tags=("link",) + ((f"link_{link_id}",) if link_id else ())
        )

    def redraw_links(self):
        self.delete("link")
        for l in self.links:
            if l['source'] in self.nodes and l['target'] in self.nodes:
                n1, n2 = self.nodes[l['source']], self.nodes[l['target']]
                x1 = (n1.x + n1.w) * self.zoom if n1.type != 'reroute' else (n1.x + 15) * self.zoom
                y1 = n1.get_port_y_by_name(l.get('source_port', 'out'), visual=True)
                x2 = n2.x * self.zoom if n2.type != 'reroute' else (n2.x + 15) * self.zoom
                y2 = n2.get_input_port_y(visual=True)
                self.draw_bezier(
                    x1, y1, x2, y2, link_id=l['id'],
                    highlighted=(l['source'] in self.selected_node_ids or l['target'] in self.selected_node_ids)
                )
        self.tag_lower("link")
        self.tag_lower("grid")
        self._update_zoom_label()

    def on_right_click_menu(self, event):
        vx, vy = self.canvasx(event.x), self.canvasy(event.y)
        for item in self.find_overlapping(vx - 6, vy - 6, vx + 6, vy + 6):
            tags = self.gettags(item)
            if (nid := next((t[5:] for t in tags if t.startswith("node_")), None)) and nid in self.nodes:
                if "port_out" in tags and self.nodes[nid].type != 'reroute':
                    port_name = next((t for t in tags if t in self.nodes[nid].outputs), 'out')
                    self.history.save_state()
                    self.links = [l for l in self.links if not (l.get('source') == nid and l.get('source_port', 'out') == port_name)]
                    self.redraw_links()
                    return
                if "port_in" in tags and self.nodes[nid].type != 'reroute':
                    self.history.save_state()
                    self.links = [l for l in self.links if l.get('target') != nid]
                    self.redraw_links()
                    return
        lx, ly = self.get_logical_pos(event.x, event.y)
        node = next((n for n in reversed(list(self.nodes.values())) if n.contains(lx, ly)), None)
        m = tk.Menu(self, tearoff=0, bg=COLORS['bg_card'], fg=COLORS['fg_text'], activebackground=COLORS['accent'], activeforeground=COLORS['accent_fg'], font=('Microsoft YaHei UI', 9))
        if node:
            if node.id not in self.selected_node_ids:
                self.select_node(node.id)
            m.add_command(label="▶ 从此节点开始测试运行", command=lambda n=node: self.app.toggle_run(n.id))
            m.add_separator()
            m.add_command(label="复制所选节点  (Ctrl+C)", command=self.copy_selected_nodes)
            m.add_command(label="粘贴节点  (Ctrl+V)", command=self.paste_nodes, state='normal' if self._node_clipboard else 'disabled')
            m.add_command(label="复制并粘贴  (Ctrl+D)", command=self.duplicate_selected_nodes)
            m.add_command(label="🔴 切换调试断点", command=lambda n=node: [self.history.save_state(), setattr(n, 'has_breakpoint', not n.has_breakpoint), n.draw()])
            if len(self.selected_node_ids) > 1:
                m.add_separator()
                m.add_command(label="⬅ 左对齐所选节点", command=lambda: self.align_nodes('left'))
                m.add_command(label="⬆ 顶部对齐所选节点", command=lambda: self.align_nodes('top'))
                m.add_command(label="↕ 垂直等距分布", command=lambda: self.align_nodes('distribute_v'))
            m.add_separator()
            m.add_command(label="🔌 断开该节点所有连线", command=lambda n=node: self._disconnect_node_links(n.id))
            m.add_command(label="🗑 删除所选节点  (Delete)", command=self._on_delete_press, foreground=COLORS['danger'])
        else:
            m.add_command(label="⚡ 在此处添加节点…  (双击空白)", command=lambda: self.open_quick_add(event.x_root, event.y_root, lx, ly))
            m.add_command(label="● 在此处添加线路中继点", command=lambda: self.add_node('reroute', round(lx / GRID_SIZE) * GRID_SIZE, round(ly / GRID_SIZE) * GRID_SIZE))
            m.add_separator()
            if self.selected_node_ids:
                m.add_command(label="复制所选节点  (Ctrl+C)", command=self.copy_selected_nodes)
            m.add_command(label="粘贴节点  (Ctrl+V)", command=self.paste_nodes, state='normal' if self._node_clipboard else 'disabled')
            m.add_command(label="全选所有节点  (Ctrl+A)", command=self._shortcut_select_all)
            if len(self.selected_node_ids) > 1:
                m.add_separator()
                m.add_command(label="⬅ 左对齐所选节点", command=lambda: self.align_nodes('left'))
                m.add_command(label="⬆ 顶部对齐所选节点", command=lambda: self.align_nodes('top'))
                m.add_command(label="↕ 垂直等距分布", command=lambda: self.align_nodes('distribute_v'))
            m.add_separator()
            m.add_command(label="适应画布视野  (F)", command=self.fit_view)
            m.add_command(label="重置缩放 100%  (Ctrl+0)", command=self.reset_zoom)
        m.post(event.x_root, event.y_root)

    def _disconnect_node_links(self, node_id):
        if any(l.get('source') == node_id or l.get('target') == node_id for l in self.links):
            self.history.save_state()
            self.links = [l for l in self.links if l.get('source') != node_id and l.get('target') != node_id]
            self.redraw_links()

    def copy_selected_nodes(self, event=None):
        selected = [self.nodes[node_id] for node_id in self.selected_node_ids if node_id in self.nodes]
        if not selected:
            return "break"
        selected_ids = {node.id for node in selected}
        self._node_clipboard = [
            {"old_id": node.id, "type": node.type, "x": node.x, "y": node.y,
             "data": self._clone_node_data(node.data)}
            for node in selected
        ]
        self._node_clipboard_links = [
            copy.deepcopy(link) for link in self.links
            if link.get('source') in selected_ids and link.get('target') in selected_ids
        ]
        self.app.log(f"📋 已复制 {len(self._node_clipboard)} 个节点", "info")
        return "break"

    def paste_nodes(self, event=None):
        if not self._node_clipboard:
            return "break"
        self.history.save_state()
        offset_x = offset_y = 40
        id_map = {}
        pasted = []
        for item in self._node_clipboard:
            node = self.add_node(
                item['type'], item['x'] + offset_x, item['y'] + offset_y,
                data=self._clone_node_data(item['data']), save_history=False
            )
            id_map[item['old_id']] = node.id
            pasted.append(node.id)
        for link in self._node_clipboard_links:
            if link.get('source') in id_map and link.get('target') in id_map:
                self.links.append({
                    'id': str(uuid.uuid4()),
                    'source': id_map[link['source']],
                    'source_port': link.get('source_port', 'out'),
                    'target': id_map[link['target']],
                })
        # 更新剪贴板内偏移，支持连续 Ctrl+V 阶梯粘贴
        for item in self._node_clipboard:
            item['x'] += offset_x
            item['y'] += offset_y
        self.select_node(None)
        for node_id in pasted:
            self.select_node(node_id, add=True)
        self.redraw_links()
        self.app.log(f"📌 已粘贴 {len(pasted)} 个节点", "success")
        return "break"

    def duplicate_selected_nodes(self, event=None):
        self.copy_selected_nodes()
        return self.paste_nodes()

    def align_nodes(self, mode):
        if len(self.selected_node_ids) < 2:
            return
        self.history.save_state()
        nodes = [self.nodes[nid] for nid in self.selected_node_ids if nid in self.nodes]
        if mode == 'left':
            target = min(n.x for n in nodes)
            for n in nodes:
                n.move_to(target, n.y)
        elif mode == 'top':
            target = min(n.y for n in nodes)
            for n in nodes:
                n.move_to(n.x, target)
        elif mode == 'distribute_v' and len(nodes) >= 3:
            nodes.sort(key=lambda n: n.y)
            top_y = nodes[0].y
            bottom_y = nodes[-1].y
            step = (bottom_y - top_y) / (len(nodes) - 1)
            for idx, n in enumerate(nodes):
                n.move_to(n.x, round((top_y + idx * step) / GRID_SIZE) * GRID_SIZE)
        self.redraw_links()

    def _clone_node_data(self, data):
        new_data = {}
        for k, v in data.items():
            if k in ['tk_image', '_tk_cache', 'node_number']:
                continue
            if isinstance(v, Image.Image):
                new_data[k] = v.copy()
            elif isinstance(v, list):
                new_list = []
                for item in v:
                    if isinstance(item, dict):
                        new_item = {}
                        for ik, iv in item.items():
                            if ik in ['tk_image', '_tk_cache']:
                                continue
                            if isinstance(iv, Image.Image):
                                new_item[ik] = iv.copy()
                                new_item['tk_image'] = ImageUtils.make_thumb(iv.copy())
                            else:
                                try:
                                    new_item[ik] = copy.deepcopy(iv)
                                except Exception:
                                    pass
                        new_list.append(new_item)
                    else:
                        try:
                            new_list.append(copy.deepcopy(item))
                        except Exception:
                            pass
                new_data[k] = new_list
            else:
                try:
                    new_data[k] = copy.deepcopy(v)
                except Exception:
                    pass

        if 'image' in new_data:
            new_data['tk_image'] = ImageUtils.make_thumb(new_data['image'])

        return new_data

    def sanitize_data_for_json(self, data):
        if isinstance(data, dict):
            clean = {}
            for key, value in data.items():
                if key in ('tk_image', '_tk_cache') or isinstance(value, ImageTk.PhotoImage):
                    continue
                if isinstance(value, Image.Image):
                    encoded_key = 'b64' if key == 'image' else 'b64_preview' if key == 'roi_preview' else key
                    encoded = ImageUtils.img_to_b64(value)
                    if encoded is None:
                        raise ValueError(f"图片字段 {key} 编码失败，已中止保存以避免丢失图片")
                    clean[encoded_key] = encoded
                    continue
                if key in ('image', 'roi_preview'):
                    continue
                clean[key] = self.sanitize_data_for_json(value)
            return clean
        if isinstance(data, list):
            return [self.sanitize_data_for_json(item) for item in data]
        if isinstance(data, Image.Image):
            encoded = ImageUtils.img_to_b64(data)
            if encoded is None:
                raise ValueError("图片编码失败，已中止保存以避免丢失图片")
            return encoded
        if isinstance(data, ImageTk.PhotoImage):
            return None
        return data

    def get_data(self):
        nodes_d = {}
        for node_id, node in self.nodes.items():
            clean_data = self.sanitize_data_for_json(node.data)
            nodes_d[node_id] = {
                'id': node_id, 'type': node.type, 'x': int(node.x), 'y': int(node.y),
                'data': clean_data, 'breakpoint': node.has_breakpoint,
            }
        breakpoints = [node_id for node_id, node in self.nodes.items() if node.has_breakpoint]
        metadata = {}
        try:
            current_metadata = self.app.core.project.get('metadata', {})
            if isinstance(current_metadata, dict):
                metadata = copy.deepcopy(current_metadata)
        except (AttributeError, TypeError):
            pass
        metadata.update({'dev_scale_x': SCALE_X, 'dev_scale_y': SCALE_Y, 'app_version': __version__})
        return {
            'nodes': nodes_d, 'links': copy.deepcopy(self.links),
            'breakpoints': breakpoints, 'metadata': metadata,
        }

    def load_data(self, data, _rollback=False):
        snapshot = None
        mutation_started = False
        previous_node_number = GraphNode.next_node_number
        try:
            if not isinstance(data, dict) or not isinstance(data.get('nodes'), dict) or not isinstance(data.get('links', []), list):
                raise ValueError("项目格式无效：nodes 必须是对象，links 必须是列表")
            data = copy.deepcopy(data)
            if not isinstance(data.get('metadata', {}), dict):
                raise ValueError("项目 metadata 必须是对象")
            if not isinstance(data.get('breakpoints', []), list):
                raise ValueError("项目 breakpoints 必须是列表")

            def prepare_images(value):
                if isinstance(value, dict):
                    for key in ('b64', 'b64_preview'):
                        encoded = value.get(key)
                        if encoded is not None:
                            if not isinstance(encoded, str) or not encoded:
                                raise ValueError(f"图片字段 {key} 无效")
                            try:
                                raw = base64.b64decode(encoded + '=' * (-len(encoded) % 4), validate=True)
                                with Image.open(io.BytesIO(raw)) as source_image:
                                    source_image.load()
                                    decoded = source_image.copy()
                            except Exception as image_error:
                                raise ValueError(f"项目图片 {key} 解码失败: {image_error}")
                            value['image' if key == 'b64' else 'roi_preview'] = decoded
                    for child in value.values():
                        if isinstance(child, (dict, list)):
                            prepare_images(child)
                elif isinstance(value, list):
                    for child in value:
                        prepare_images(child)

            prepare_images(data.get('nodes', {}))
            node_ids = set(data['nodes'])
            for nid, node_data in data['nodes'].items():
                if not isinstance(node_data, dict) or node_data.get('type') not in NODE_CONFIG:
                    raise ValueError(f"节点 {nid} 的类型无效")
                if not isinstance(node_data.get('data', {}), dict):
                    raise ValueError(f"节点 {nid} 的 data 必须是对象")
                for coordinate in ('x', 'y'):
                    try:
                        value = float(node_data[coordinate])
                    except (KeyError, TypeError, ValueError):
                        raise ValueError(f"节点 {nid} 的坐标 {coordinate} 无效")
                    if not math.isfinite(value):
                        raise ValueError(f"节点 {nid} 的坐标 {coordinate} 必须是有限数值")
            links = []
            for link in data.get('links', []):
                if not isinstance(link, dict) or link.get('source') not in node_ids or link.get('target') not in node_ids:
                    raise ValueError("项目包含无效连线：源节点或目标节点不存在")
                normalized_link = dict(link)
                normalized_link.setdefault('id', str(uuid.uuid4()))
                normalized_link.setdefault('source_port', 'out')
                links.append(normalized_link)
            if not _rollback:
                snapshot = self.get_data()
            mutation_started = True
            self.app.core.load_project(data)
            for node in list(self.nodes.values()):
                node.clear_widgets()
            self.delete("all")
            self.nodes.clear()
            self.links.clear()
            self.selected_node_ids.clear()
            breakpoints = set(data.get('breakpoints', []))

            max_node_number = 0
            for n_data in data.get('nodes', {}).values():
                node_number = safe_int(n_data.get('data', {}).get('node_number', 0), 0)
                if node_number > max_node_number:
                    max_node_number = node_number
            GraphNode.next_node_number = max_node_number + 1

            for nid, n_data in data.get('nodes', {}).items():
                d = n_data.get('data', {})
                if 'image' in d:
                    d['tk_image'] = ImageUtils.make_thumb(d['image'])
                if 'b64_preview' in d and (img := ImageUtils.b64_to_img(d['b64_preview'])):
                    d['roi_preview'] = img

                n = self.add_node(n_data['type'], n_data['x'], n_data['y'], data=d, node_id=nid, save_history=False)
                if n_data.get('breakpoint', False) or nid in breakpoints:
                    n.has_breakpoint = True
                    n.draw()
            self.links = links
            self.select_node(None)
            self.full_redraw()
            return True
        except Exception as e:
            if mutation_started and snapshot is not None and not _rollback:
                try:
                    if not self.load_data(snapshot, _rollback=True):
                        raise RuntimeError("无法重新构建原项目")
                    GraphNode.next_node_number = previous_node_number
                except Exception as rollback_error:
                    self.app.log(f"❌ 项目回滚失败: {rollback_error}", "error")
            self.app.log(f"❌ 加载失败: {e}", "error")
            return False

class PropertyPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS['bg_panel'])
        self.app, self.current_node = app, None
        self.static_monitor_active = False
        self.is_monitoring_audio = False

        header = tk.Frame(self, bg=COLORS['bg_sidebar'], height=38)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="属性设置", bg=COLORS['bg_sidebar'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 9, 'bold')).pack(side='left', padx=12, pady=8)

        self.scrollbar = ttk.Scrollbar(self, orient="vertical")
        self.scrollbar.pack(side='right', fill='y')
        self.canvas = tk.Canvas(self, bg=COLORS['bg_panel'], highlightthickness=0, yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.config(command=self.canvas.yview)

        self.content = tk.Frame(self.canvas, bg=COLORS['bg_panel'], padx=12, pady=10)
        self.content_id = self.canvas.create_window((0, 0), window=self.content, anchor='nw')

        def on_content_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            if event.height <= self.canvas.winfo_height():
                self.scrollbar.pack_forget()
                self.canvas.pack(side='left', fill='both', expand=True)
            else:
                self.scrollbar.pack(side='right', fill='y')
                self.canvas.pack(side='left', fill='both', expand=True)
        self.content.bind("<Configure>", on_content_configure)

        def on_canvas_configure(event):
            self.canvas.itemconfig(self.content_id, width=event.width)
        self.canvas.bind("<Configure>", on_canvas_configure)
        self.show_empty()

    def clear(self):
        for w in self.content.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.current_node = None
        self.static_monitor_active = False
        self.is_monitoring_audio = False

    def show_empty(self):
        self.clear()
        info_frame = tk.Frame(self.content, bg=COLORS['bg_panel'])
        info_frame.pack(fill='both', expand=True, pady=28)
        tk.Label(info_frame, text="未选中节点", bg=COLORS['bg_panel'], fg=COLORS['fg_title'], font=('Microsoft YaHei UI', 11, 'bold')).pack(pady=(0, 8))
        tk.Label(info_frame, text="• 从左侧拖拽或双击画布空白处添加节点\n• 点击画布中的节点可在此编辑详细参数\n• 空格 + 左键拖拽平移，滚轮以指针缩放", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 9), justify='left').pack(pady=4)

        var_help = tk.Frame(info_frame, bg=COLORS['bg_card'], padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS['bg_header'])
        var_help.pack(fill='x', pady=18)
        tk.Label(var_help, text="💡 动态变量语法", bg=COLORS['bg_card'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
        tk.Label(var_help, text="1. 使用【变量】或【剪贴板】节点写入变量\n2. 在任意输入框填入 ${变量名} 自动替换\n3. 提示节点支持 ${ALL_VARS} 打印全部变量", bg=COLORS['bg_card'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 8), justify='left').pack(anchor='w', pady=(4, 0))

    def show_multi_select(self, count):
        self.clear()
        box = tk.Frame(self.content, bg=COLORS['bg_panel'])
        box.pack(fill='x', pady=30)
        tk.Label(box, text=f"已选中 {count} 个节点", bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 11, 'bold')).pack(pady=(0, 12))
        self._btn(box, "⬅ 左对齐所选节点", lambda: self.app.editor.align_nodes('left'))
        self._btn(box, "⬆ 顶部对齐所选节点", lambda: self.app.editor.align_nodes('top'))
        if count >= 3:
            self._btn(box, "↕ 垂直等距分布", lambda: self.app.editor.align_nodes('distribute_v'))
        self._btn(box, "📋 复制所选 (Ctrl+C)", self.app.editor.copy_selected_nodes)
        self._btn(box, "🗑 删除所选 (Delete)", self.app.editor._on_delete_press, bg=COLORS['danger'])

    def load_node(self, node):
        self.clear()
        self.current_node = node
        ntype, data = node.type, node.data

        if ntype != 'reroute':
            meta_card = tk.Frame(self.content, bg=COLORS['bg_card'], padx=10, pady=8, highlightthickness=1, highlightbackground=COLORS['bg_header'])
            meta_card.pack(fill='x', pady=(0, 8))
            top_row = tk.Frame(meta_card, bg=COLORS['bg_card'])
            top_row.pack(fill='x')
            tk.Label(top_row, text=NODE_CONFIG.get(ntype, {}).get('title', ntype), bg=COLORS['bg_card'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 9, 'bold')).pack(side='left')
            tk.Label(top_row, text=f"#{data.get('node_number', 'N/A')}", bg=COLORS['bg_card'], fg=COLORS['fg_sub'], font=('Consolas', 9)).pack(side='right')
            desc_txt = NODE_CONFIG.get(ntype, {}).get('desc', '')
            if desc_txt:
                tk.Label(meta_card, text=desc_txt, bg=COLORS['bg_card'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8), anchor='w').pack(fill='x', pady=(2, 0))

            self._input(self.content, "节点名称", '_user_title', data.get('_user_title', node.title_text))

        if ntype == 'wait':
            sec = self._create_section("延时设置")
            self._combo(
                sec, "延时模式", 'delay_type', ['固定延时', '随机延时'],
                '随机延时' if data.get('delay_type') == 'random' else '固定延时',
                lambda e: self._save('delay_type', 'random' if e.widget.get() == '随机延时' else 'fixed', refresh_ui=True)
            )
            if data.get('delay_type') == 'random':
                f = tk.Frame(sec, bg=sec.cget('bg'))
                f.pack(fill='x', pady=4)
                self._compact_input(f, "最小(s)", 'min_seconds', data.get('min_seconds', 1.0), safe_float)
                self._compact_input(f, "最大(s)", 'max_seconds', data.get('max_seconds', 3.0), safe_float)
            else:
                self._input(sec, "等待秒数", 'seconds', data.get('seconds', 1.0), safe_float)

        elif ntype == 'loop':
            sec = self._create_section("循环设置")
            self._chk(sec, "无限循环（直到遇到结束节点或手动停止）", 'infinite', data.get('infinite', True))
            if not data.get('infinite', True):
                self._input(sec, "循环次数", 'count', data.get('count', 5), safe_int)

        elif ntype == 'notify':
            sec = self._create_section("气泡通知")
            self._input(sec, "提示内容", 'msg', data.get('msg', '当前所有变量: {ALL_VARS}'))
            self._input(sec, "持续时间(秒)", 'duration', data.get('duration', 2.0), safe_float)
            self._chk(sec, "播放提示音", 'use_sound', data.get('use_sound', False))

        elif ntype == 'set_var':
            sec = self._create_section("变量赋值")
            tk.Label(sec, text="每行一个变量（格式：变量名=变量值）：", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(0, 4))
            txt = tk.Text(sec, height=6, bg=COLORS['input_bg'], fg=COLORS['input_fg'], insertbackground=COLORS['input_fg'], bd=0, padx=6, pady=6, font=('Consolas', 9))
            txt.pack(fill='x', pady=(0, 6))
            existing = "".join([f"{i.get('name')}={i.get('value')}\n" for i in data.get('batch_vars', []) if isinstance(i, dict)])
            if not existing and data.get('var_name'):
                existing = f"{data.get('var_name')}={data.get('var_value')}"
            txt.insert('1.0', existing.rstrip('\n'))
            edit_snapshot = [None]
            def begin_vars_edit(_event=None):
                edit_snapshot[0] = self.app.editor.history.begin_edit()
            def save_vars(ev=None):
                parsed = []
                for line in txt.get('1.0', 'end').splitlines():
                    if '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip():
                            parsed.append({'name': k.strip(), 'value': v.strip()})
                self._save('batch_vars', parsed, self.current_node, refresh_ui=False)
                snapshot = edit_snapshot[0]
                edit_snapshot[0] = None
                if snapshot is not None:
                    self.app.editor.history.commit_edit(snapshot)
            txt.bind("<FocusIn>", begin_vars_edit)
            txt.bind("<FocusOut>", save_vars)
            self._btn(sec, "💾 应用变量列表", save_vars)

        elif ntype == 'var_switch':
            sec = self._create_section("分流模式")
            is_multi_case = not bool(data.get('var_name')) and bool(data.get('cases') or data.get('var_list'))
            mode_label = '多分支匹配 (Switch)' if is_multi_case else '单变量条件判断 (是/否)'
            def on_switch_mode(e):
                sel = e.widget.get()
                self.app.editor.history.save_state()
                if sel == '单变量条件判断 (是/否)':
                    if not data.get('var_name'):
                        data['var_name'] = 'my_var'
                    data.setdefault('operator', '=')
                    data.setdefault('var_value', '1')
                else:
                    data['var_name'] = ''
                    data.setdefault('var_list', 'my_var')
                    if not data.get('cases'):
                        data['cases'] = [
                            {'id': 'case_1', 'value': '1'},
                            {'id': 'case_2', 'value': '2'}
                        ]
                node.refresh_outputs()
                self.app.editor.links = [
                    l for l in self.app.editor.links
                    if l.get('source') != node.id or l.get('source_port', 'out') in node.outputs
                ]
                node.draw()
                self.app.editor.redraw_links()
                self.load_node(node)

            self._combo(sec, "模式", '_switch_mode', ['单变量条件判断 (是/否)', '多分支匹配 (Switch)'], mode_label, on_switch_mode)

            if not is_multi_case:
                if not data.get('var_name'):
                    data['var_name'] = 'my_var'
                    node.draw()
                cond_sec = self._create_section("判断条件（输出：是 / 否）")
                self._input(cond_sec, "变量名", 'var_name', data.get('var_name', 'my_var'))
                op_map = {'=': '等于 (=)', '!=': '不等于 (!=)', 'contains': '包含文本', '>': '数值大于 (>)', '<': '数值小于 (<)'}
                curr_op = data.get('operator', '=')
                self._combo(
                    cond_sec, "比较符", 'operator', list(op_map.values()),
                    op_map.get(curr_op, '等于 (=)'),
                    lambda e: self._save('operator', {v: k for k, v in op_map.items()}.get(e.widget.get(), '='), self.current_node, refresh_ui=False)
                )
                self._input(cond_sec, "目标值", 'var_value', data.get('var_value', ''))
            else:
                case_sec = self._create_section("多分支匹配规则")
                self._input(case_sec, "变量名(逗号分隔)", 'var_list', data.get('var_list', 'my_var'))
                tk.Label(case_sec, text="分支匹配值（每行一个分支值）：", bg=case_sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(4, 2))
                txt_cases = tk.Text(case_sec, height=5, bg=COLORS['input_bg'], fg=COLORS['input_fg'], insertbackground=COLORS['input_fg'], bd=0, padx=6, pady=6, font=('Consolas', 9))
                txt_cases.pack(fill='x', pady=(0, 6))
                curr_cases = data.get('cases', [])
                txt_cases.insert('1.0', "\n".join(str(c.get('value', '')) for c in curr_cases if isinstance(c, dict)))
                def apply_cases():
                    lines = [ln.strip() for ln in txt_cases.get('1.0', 'end').splitlines() if ln.strip()]
                    new_cases = [{'id': f'case_{idx + 1}', 'value': val} for idx, val in enumerate(lines)]
                    self._save('cases', new_cases, self.current_node, refresh_ui=True)
                    valid_ports = set(self.current_node.outputs)
                    self.app.editor.links = [
                        l for l in self.app.editor.links
                        if l.get('source') != self.current_node.id or l.get('source_port', 'out') in valid_ports
                    ]
                    self.app.editor.redraw_links()
                self._btn(case_sec, "🔄 更新分流端口", apply_cases, bg=COLORS['accent'])

        elif ntype == 'sequence':
            sec = self._create_section("顺序尝试序列")
            tk.Label(sec, text="按步骤 1..N 依次尝试连接的节点，任一步骤成功即接管后续流程；若全部失败则走【否则】端口。", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8), justify='left', wraplength=240).pack(anchor='w', pady=(0, 6))
            curr_steps = safe_int(data.get('num_steps', 3), 3)
            step_options = [str(i) for i in range(1, 13)]
            def on_steps_change(e):
                new_steps = max(1, min(12, safe_int(e.widget.get(), 3)))
                self._save('num_steps', new_steps, self.current_node, refresh_ui=True)
                valid_ports = set(self.current_node.outputs)
                self.app.editor.links = [
                    l for l in self.app.editor.links
                    if l.get('source') != self.current_node.id or l.get('source_port', 'out') in valid_ports
                ]
                self.app.editor.redraw_links()
            self._combo(sec, "步骤数量", 'num_steps', step_options, str(curr_steps), on_steps_change)

        elif ntype == 'clipboard':
            sec = self._create_section("剪贴板操作")
            CLIP_MODES = {'read': '读取到变量', 'write': '写入剪贴板'}
            curr_mode = data.get('clip_mode', 'read')
            self._combo(
                sec, "模式", 'clip_mode', list(CLIP_MODES.values()),
                CLIP_MODES.get(curr_mode),
                lambda e: self._save('clip_mode', {v: k for k, v in CLIP_MODES.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)
            )
            if data.get('clip_mode', 'read') == 'read':
                self._input(sec, "保存至变量", 'var_name', data.get('var_name', 'clipboard_data'))
            else:
                self._input(sec, "写入内容", 'text', data.get('text', ''))

        elif ntype == 'bind_win':
            sec = self._create_section("旧项目兼容节点")
            tk.Label(
                sec,
                text="“绑定窗口”已从新建组件库中停用。为避免旧版项目损坏，现有项目中的该节点仍保留原运行兼容；此处不再提供绑定设置。新流程请直接使用屏幕绝对坐标。",
                bg=sec.cget('bg'), fg=COLORS['fg_text'],
                font=('Microsoft YaHei UI', 9), justify='left', wraplength=240
            ).pack(anchor='w', pady=(2, 6))

        elif ntype == 'open_app':
            sec = self._create_section("程序配置")
            self._file_picker(sec, "程序路径", 'path', data.get('path', ''))
            self._input(sec, "启动参数", 'args', data.get('args', ''))

        elif ntype == 'cmd':
            sec = self._create_section("系统命令")
            self._input(sec, "命令内容", 'command', data.get('command', ''))
        elif ntype == 'web':
            sec = self._create_section("打开网页")
            self._input(sec, "网址 URL", 'url', data.get('url', 'https://'))
        elif ntype == 'mouse':
            sec = self._create_section("鼠标操作")

            curr_mode = data.get('coord_mode', 'absolute')
            coord_modes = {'absolute': '屏幕绝对坐标'}
            if curr_mode == 'relative':
                coord_modes['relative'] = '旧项目窗口相对坐标（兼容）'
            display_mode = coord_modes.get(curr_mode, '屏幕绝对坐标')
            self._combo(
                sec, "坐标模式", 'coord_mode', list(coord_modes.values()), display_mode,
                lambda e: self._save('coord_mode', {v: k for k, v in coord_modes.items()}.get(e.widget.get(), 'absolute'), self.current_node, refresh_ui=True)
            )

            def on_action_change(e):
                val = {v: k for k, v in MOUSE_ACTIONS.items()}.get(e.widget.get())
                self._save('mouse_action', val, self.current_node, refresh_ui=True)

            curr_action = data.get('mouse_action', 'click')
            if curr_action == 'double_click':
                curr_action = 'click'
            self._combo(sec, "动作", 'mouse_action', list(MOUSE_ACTIONS.values()), MOUSE_ACTIONS.get(curr_action, '点击'), on_action_change)

            if curr_action == 'click':
                self._combo(
                    sec, "按键", 'mouse_button', list(MOUSE_BUTTONS.values()),
                    MOUSE_BUTTONS.get(data.get('mouse_button', 'left')),
                    lambda e: self._save('mouse_button', {v: k for k, v in MOUSE_BUTTONS.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)
                )
                curr_clicks = str(data.get('click_count', '1'))
                disp_clicks = '双击' if curr_clicks in ['2', '双击'] else '单击'
                self._combo(
                    sec, "次数", 'click_count', ['单击', '双击'], disp_clicks,
                    lambda e: self._save('click_count', 1 if e.widget.get() == '单击' else 2, self.current_node, refresh_ui=True)
                )

            if curr_action in ['click', 'move', 'scroll']:
                coord = tk.Frame(sec, bg=sec.cget('bg'))
                coord.pack(fill='x', pady=5)
                self._compact_input(coord, "X", 'x', data.get('x', ''), safe_int)
                self._compact_input(coord, "Y", 'y', data.get('y', ''), safe_int)
                self._btn_icon(coord, "📍 拾取", self.app.pick_coordinate, width=6)
                tk.Label(sec, text="提示：X/Y 留空则在当前鼠标位置执行", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(anchor='w')

            if curr_action == 'scroll':
                scroll_f = tk.Frame(sec, bg=sec.cget('bg'))
                scroll_f.pack(fill='x', pady=5)
                self._input(scroll_f, "滚动量(负数向下)", 'scroll_amount', data.get('scroll_amount', -500), safe_int)

            elif curr_action == 'drag':
                start_coord = tk.Frame(sec, bg=sec.cget('bg'))
                start_coord.pack(fill='x', pady=5)
                tk.Label(start_coord, text="起始坐标:", bg=sec.cget('bg'), fg=COLORS['accent'], font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w', pady=(4, 0))
                start_input = tk.Frame(start_coord, bg=sec.cget('bg'))
                start_input.pack(fill='x', pady=2)
                self._compact_input(start_input, "X", 'start_x', data.get('start_x', ''), safe_int)
                self._compact_input(start_input, "Y", 'start_y', data.get('start_y', ''), safe_int)
                self._btn_icon(start_input, "📍 拾取", self.app.pick_start_coordinate, width=6)

                end_coord = tk.Frame(sec, bg=sec.cget('bg'))
                end_coord.pack(fill='x', pady=5)
                tk.Label(end_coord, text="目标坐标:", bg=sec.cget('bg'), fg=COLORS['accent'], font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w', pady=(4, 0))
                end_input = tk.Frame(end_coord, bg=sec.cget('bg'))
                end_input.pack(fill='x', pady=2)
                self._compact_input(end_input, "X", 'end_x', data.get('end_x', ''), safe_int)
                self._compact_input(end_input, "Y", 'end_y', data.get('end_y', ''), safe_int)
                self._btn_icon(end_input, "📍 拾取", self.app.pick_end_coordinate, width=6)

            self._input(sec, "移动耗时(秒)", 'duration', data.get('duration', 0.5), safe_float)

        elif ntype == 'keyboard':
            sec = self._create_section("键盘操作")
            def on_mode_change(e):
                val = 'text' if e.widget.get() == '输入文本' else 'key'
                self._save('kb_mode', val, self.current_node, refresh_ui=True)

            self._combo(sec, "模式", 'kb_mode', ['输入文本', '按键组合'], '输入文本' if data.get('kb_mode', 'text') == 'text' else '按键组合', on_mode_change)

            if data.get('kb_mode', 'text') == 'text':
                self._input(sec, "文本", 'text', data.get('text', ''))
                self._chk(sec, "粘贴模式（支持中文/高速防乱码）", 'use_paste', data.get('use_paste', True))
                self._chk(sec, "输入后自动按回车 (Enter)", 'press_enter', data.get('press_enter', False))
            else:
                self._input(sec, "组合键", 'key_name', data.get('key_name', 'enter'))
                tk.Label(sec, text="示例：ctrl+c、alt+tab、win+d、enter", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(anchor='w')

        elif ntype == 'image':
            base = self._create_section("目标图像")
            if 'tk_image' in data:
                self._draw_image_preview(base, data)
            self._btn(base, "📸 截取目标图像", self.app.do_snip, bg=COLORS['accent'])
            search = self._create_section("匹配参数")
            self._input(search, "相似度(0.1-1.0)", 'confidence', data.get('confidence', 0.9), safe_float)
            self._input(search, "超时(秒)", 'timeout', data.get('timeout', 10.0), safe_float)

            curr_strat = data.get('match_strategy', 'hybrid')
            self._combo(
                search, "算法", 'match_strategy', list(MATCH_STRATEGY_MAP.values()),
                MATCH_STRATEGY_MAP.get(curr_strat, '智能混合'),
                lambda e: self._save('match_strategy', {v: k for k, v in MATCH_STRATEGY_MAP.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)
            )

            self._chk(search, "未找到时自动滚动屏幕继续查找", 'auto_scroll', data.get('auto_scroll', False))
            if data.get('auto_scroll', False):
                self._input(search, "每次滚动量(负数向下)", 'scroll_amount', data.get('scroll_amount', -500), safe_int)

            act = self._create_section("找到后执行")
            self._combo(
                act, "动作", 'click_type', list(ACTION_MAP.values()),
                ACTION_MAP.get(data.get('click_type', 'click')),
                lambda e: self._save('click_type', {v: k for k, v in ACTION_MAP.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)
            )
            off = tk.Frame(act, bg=act.cget('bg'))
            off.pack(fill='x', pady=5)
            self._compact_input(off, "偏移X", 'offset_x', data.get('offset_x', 0), safe_int)
            self._compact_input(off, "Y", 'offset_y', data.get('offset_y', 0), safe_int)
            self._btn_icon(off, "🎯 定位", self.open_visual_offset_picker, bg=COLORS['control'], width=6)

        elif ntype == 'if_img':
            sec = self._create_section("多图检测配置")
            imgs = data.get('images', [])
            stat_frame = tk.Frame(sec, bg=sec.cget('bg'))
            stat_frame.pack(fill='x', pady=(0, 5))
            tk.Label(stat_frame, text=f"📚 已存参考图: {len(imgs)} 张（全部出现则走【是】）", bg=sec.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 8)).pack(anchor='w')
            self._btn(sec, "📸 截取并添加参考图", self.app.do_snip, bg=COLORS['accent'])
            if imgs:
                def pop_last_img():
                    new_imgs = imgs[:-1]
                    self._save('images', new_imgs, self.current_node, refresh_ui=True)
                def clear_imgs():
                    if messagebox.askyesno("确认清空", "确定要删除所有已保存的参考图片吗？", parent=self.app):
                        self._save('images', [], self.current_node, refresh_ui=True)
                self._btn(sec, "↩ 移除最后一张图片", pop_last_img)
                self._btn(sec, "🗑️ 清空所有图片", clear_imgs, bg=COLORS['danger'])
            param = self._create_section("匹配参数")
            self._input(param, "相似度(0.1-1.0)", 'confidence', data.get('confidence', 0.9), safe_float)

        elif ntype == 'if_static':
            base_sec = self._create_section("监控区域")
            if 'roi_preview' in data:
                preview_img = data['roi_preview']
                tk_preview = ImageUtils.make_thumb(preview_img) if isinstance(preview_img, Image.Image) else (preview_img if isinstance(preview_img, ImageTk.PhotoImage) else None)
                if tk_preview:
                    c = tk.Canvas(base_sec, width=240, height=135, bg=COLORS['preview_bg'], highlightthickness=1, highlightbackground=COLORS['bg_header'])
                    c.pack(pady=5)
                    c.create_image(120, 67, image=tk_preview, anchor='center')
                    c.image = tk_preview

            self._btn(base_sec, "📸 框选监控区域", self.app.do_snip, bg=COLORS['accent'])
            param_sec = self._create_section("检测参数")
            self._input(param_sec, "静止持续(秒)", 'duration', data.get('duration', 5.0), safe_float)
            self._input(param_sec, "最大超时(秒)", 'timeout', data.get('timeout', 20.0), safe_float)
            self._input(param_sec, "灵敏度(0.8-1.0)", 'threshold', data.get('threshold', 0.98), safe_float)
            monitor_frame = self._create_section("实时测试")
            self.lbl_monitor_status = tk.Label(monitor_frame, text="点击下方按钮测试区域静止状态", bg=monitor_frame.cget('bg'), fg=COLORS['fg_sub'], font=('Consolas', 9))
            self.lbl_monitor_status.pack(fill='x', pady=5)
            self.btn_monitor = self._btn(monitor_frame, "🔴 启动实时监控", self._toggle_static_monitor)

        elif ntype == 'if_sound':
            sec = self._create_section("声音检测")
            SOUND_MODES = {'has_sound': '检测有声音输出', 'is_silent': '检测保持静音'}
            curr_mode = data.get('detect_mode', 'has_sound')
            self._combo(
                sec, "模式", 'detect_mode', list(SOUND_MODES.values()),
                SOUND_MODES.get(curr_mode),
                lambda e: self._save('detect_mode', {v: k for k, v in SOUND_MODES.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)
            )
            self._input(sec, "音量阈值(0-1)", 'threshold', data.get('threshold', 0.02), safe_float)
            self._input(sec, "检测超时(秒)", 'timeout', data.get('timeout', 10.0), safe_float)
            btn_text = "⏹ 停止音量监测" if self.is_monitoring_audio else "🔊 实时监测系统音量"
            self.monitor_audio_btn = self._btn(sec, btn_text, self._toggle_audio_monitor)

    def _create_section(self, text):
        f = tk.Frame(self.content, bg=COLORS['bg_panel'], pady=5)
        f.pack(fill='x')
        tk.Label(f, text=text, bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
        tk.Frame(f, height=1, bg=COLORS['bg_header']).pack(fill='x', pady=(2, 6))
        return f

    def _input(self, parent, label, key, val, vfunc=None):
        target_node = self.current_node
        f = tk.Frame(parent, bg=parent.cget('bg'))
        f.pack(fill='x', pady=3)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left', padx=(0, 6))

        var = tk.StringVar(value=str(val))
        edit_snapshot = [None]
        def on_change(*args):
            new_val = var.get()
            self._save(key, vfunc(new_val) if vfunc else new_val, target_node, refresh_ui=False)
        def begin_edit(_event=None):
            edit_snapshot[0] = self.app.editor.history.begin_edit()
        def commit_edit(_event=None):
            snapshot = edit_snapshot[0]
            edit_snapshot[0] = None
            if snapshot is not None and self.app.editor.history.commit_edit(snapshot):
                if target_node and key in ('_user_title', 'seconds', 'count', 'text', 'command', 'msg'):
                    target_node.draw()
                    self.app.editor.redraw_links()
        var.trace_add("write", on_change)

        e = tk.Entry(f, bg=COLORS['input_bg'], fg=COLORS['input_fg'], bd=0, insertbackground=COLORS['input_fg'], font=('Microsoft YaHei UI', 9), textvariable=var)
        e.pack(fill='x', pady=1, ipady=4, padx=2, expand=True)
        e.bind("<FocusIn>", begin_edit)
        e.bind("<FocusOut>", commit_edit)
        e.bind("<Return>", lambda ev: [commit_edit(), self.app.editor.focus_set()])

    def _file_picker(self, parent, label, key, val):
        target_node = self.current_node
        f = tk.Frame(parent, bg=parent.cget('bg'))
        f.pack(fill='x', pady=3)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left', padx=(0, 4))
        input_container = tk.Frame(f, bg=COLORS['input_bg'])
        input_container.pack(side='left', fill='x', expand=True, padx=2, ipady=2)
        display_text = os.path.basename(val) if val else "点击选择..."
        if len(display_text) > 18:
            display_text = display_text[:16] + "..."
        lbl_display = tk.Label(input_container, text=f"📄 {display_text}", bg=COLORS['input_bg'], fg=COLORS['input_fg'] if val else COLORS['fg_sub'], font=('Microsoft YaHei UI', 9), anchor='w', cursor='hand2')
        lbl_display.pack(side='left', fill='x', expand=True, padx=5)
        if val:
            ToolTip(lbl_display, val)
            tk.Button(input_container, text="×", command=lambda: self._save(key, "", target_node, refresh_ui=True), bg=COLORS['input_bg'], fg=COLORS['danger'], bd=0, cursor="hand2", font=('Arial', 10, 'bold')).pack(side='right', padx=2)
        def pick():
            if (path := filedialog.askopenfilename(filetypes=[("可执行程序", "*.exe;*.bat;*.cmd"), ("所有文件", "*.*")])):
                self._save(key, path, target_node, refresh_ui=True)
        lbl_display.bind("<Button-1>", lambda e: pick())
        input_container.bind("<Button-1>", lambda e: pick())
        self._btn_icon(f, "📂", pick, width=3)

    def _compact_input(self, parent, label, key, val, vfunc=None):
        target_node = self.current_node
        tk.Label(parent, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left', padx=(4, 2))

        var = tk.StringVar(value=str(val))
        edit_snapshot = [None]
        def on_change(*args):
            new_val = var.get()
            self._save(key, vfunc(new_val) if vfunc else new_val, target_node, refresh_ui=False)
        def begin_edit(_event=None):
            edit_snapshot[0] = self.app.editor.history.begin_edit()
        def commit_edit(_event=None):
            snapshot = edit_snapshot[0]
            edit_snapshot[0] = None
            if snapshot is not None:
                self.app.editor.history.commit_edit(snapshot)
        var.trace_add("write", on_change)

        e = tk.Entry(parent, bg=COLORS['input_bg'], fg=COLORS['input_fg'], bd=0, width=6, insertbackground=COLORS['input_fg'], font=('Microsoft YaHei UI', 9), textvariable=var)
        e.pack(side='left', padx=2, ipady=3)
        e.bind("<FocusIn>", begin_edit)
        e.bind("<FocusOut>", commit_edit)
        e.bind("<Return>", lambda ev: [commit_edit(), self.app.editor.focus_set()])

    def _combo(self, parent, label, key, values, val, cmd):
        f = tk.Frame(parent, bg=parent.cget('bg'))
        f.pack(fill='x', pady=3)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left', padx=(0, 6))
        cb = ttk.Combobox(f, values=values, state='readonly', font=('Microsoft YaHei UI', 9))
        cb.set(val)
        cb.pack(fill='x', pady=2, expand=True)
        cb.bind("<<ComboboxSelected>>", cmd)

    def _btn(self, parent, txt, cmd, bg=None):
        bg = bg or COLORS['btn_bg']
        if bg == COLORS['warning']:
            fg = COLORS['warning_fg']
        elif bg in (COLORS['danger'], COLORS['success'], COLORS['accent'], COLORS['control'], COLORS['sensor'], COLORS['var_node']):
            fg = '#FFFFFF'
        else:
            fg = COLORS['fg_text']
        b = tk.Button(parent, text=txt, command=cmd, bg=bg, fg=fg, bd=0, activebackground=COLORS['btn_hover'], relief='flat', pady=4, font=('Microsoft YaHei UI', 9), cursor='hand2')
        b.pack(fill='x', pady=3)
        return b

    def _btn_icon(self, parent, txt, cmd, bg=None, color=None, width=None):
        tk.Button(parent, text=txt, command=cmd, bg=bg or COLORS['bg_card'], fg=color or COLORS['fg_text'], bd=0, activebackground=COLORS['btn_hover'], relief='flat', width=width, font=('Microsoft YaHei UI', 8), cursor='hand2', pady=2).pack(side='right', padx=2)

    def _chk(self, parent, txt, key, val):
        target_node = self.current_node
        var = tk.BooleanVar(value=val)
        tk.Checkbutton(
            parent, text=txt, variable=var, bg=parent.cget('bg'), fg=COLORS['fg_text'],
            selectcolor=COLORS['input_bg'], activebackground=parent.cget('bg'),
            activeforeground=COLORS['fg_text'], borderwidth=0, highlightthickness=0,
            font=('Microsoft YaHei UI', 9), cursor='hand2',
            command=lambda: self._save(key, var.get(), target_node, refresh_ui=True)
        ).pack(anchor='w', pady=3)

    def _save(self, key, val, node=None, refresh_ui=True):
        target = node if node else self.current_node
        if target:
            try:
                target.update_data(key, val, refresh_ui=refresh_ui)
            except Exception:
                pass

    def _draw_image_preview(self, parent, data):
        c = tk.Canvas(parent, width=240, height=135, bg=COLORS['preview_bg'], highlightthickness=1, highlightbackground=COLORS['bg_header'], cursor='hand2')
        c.pack(pady=5)
        c.create_image(120, 67, image=data['tk_image'], anchor='center')
        w, h = data['image'].size
        ratio = min(240 / w, 135 / h) if w > 0 and h > 0 else 0
        dw, dh = int(w * ratio), int(h * ratio)
        off_x, off_y = (240 - dw) // 2, (135 - dh) // 2
        def on_click(e):
            rx = max(0.0, min(1.0, (e.x - off_x) / dw if dw > 0 else 0))
            ry = max(0.0, min(1.0, (e.y - off_y) / dh if dh > 0 else 0))
            self._save('relative_click_pos', (rx, ry), self.current_node, refresh_ui=True)
        c.bind("<Button-1>", on_click)
        rx, ry = data.get('relative_click_pos', (0.5, 0.5))
        cx, cy = off_x + (rx * dw), off_y + (ry * dh)
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=COLORS['marker'], outline=COLORS['node_header_fg'], width=1.5)
        ToolTip(c, "点击缩略图可直接调整图像内部相对点击锚点（红点）")

    def open_visual_offset_picker(self):
        if not self.current_node or not self.current_node.data.get('image'):
            self.app.log("⚠️ 请先截取目标图像后再定位偏移", "warning")
            return
        self.app.iconify()
        self.app.update()
        time.sleep(0.35)
        full_screen = ImageGrab.grab(all_screens=True, bbox=(VX, VY, VX + VW, VY + VH))
        try:
            conf = safe_float(self.current_node.data.get('confidence', 0.8), 0.8)
            strat = self.current_node.data.get('match_strategy', 'hybrid')
            res = VisionEngine.locate(
                self.current_node.data.get('image'),
                confidence=min(0.85, conf),
                timeout=1.5,
                scaling_ratio=self.app.core.scaling_ratio,
                strategy=strat
            )
            if not res:
                self.app.deiconify()
                self.app.log("❌ 未在当前屏幕上找到目标基准图，请确保目标界面处于可见状态", "error")
                VisualTips.show_toast("❌ 未在当前屏幕找到目标图像", duration=2000)
                return
            top = tk.Toplevel(self.app)
            top.geometry(f"{VW}x{VH}+{VX}+{VY}")
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.config(cursor="crosshair")
            cv = tk.Canvas(top, width=full_screen.width, height=full_screen.height, highlightthickness=0)
            cv.pack()
            tk_img = ImageTk.PhotoImage(full_screen)
            cv.create_image(0, 0, image=tk_img, anchor='nw')

            cv.create_rectangle(res.left - VX, res.top - VY, res.left + res.width - VX, res.top + res.height - VY, outline='#22C55E', width=2)
            rx, ry = self.current_node.data.get('relative_click_pos', (0.5, 0.5))
            cx, cy = res.left + res.width * rx - VX, res.top + res.height * ry - VY

            cv.create_line(cx - 10, cy, cx + 10, cy, fill='#EF4444', width=2)
            cv.create_line(cx, cy - 10, cx, cy + 10, fill='#EF4444', width=2)
            line_id = cv.create_line(cx, cy, cx, cy, fill='#38BDF8', dash=(4, 4), width=2)
            text_id = cv.create_text(cx, cy, text="偏移: 0, 0", fill='#38BDF8', anchor='sw', font=('Consolas', 11, 'bold'))

            def on_motion(e):
                cv.coords(line_id, cx, cy, e.x, e.y)
                cv.coords(text_id, e.x + 12, e.y - 12)
                cv.itemconfig(text_id, text=f"偏移: {int(e.x - cx)}, {int(e.y - cy)}")
            def confirm(e):
                self._save('offset_x', int(e.x - cx), self.current_node, refresh_ui=False)
                self._save('offset_y', int(e.y - cy), self.current_node, refresh_ui=True)
                top.destroy()
                self.app.deiconify()
            cv.bind("<Motion>", on_motion)
            cv.bind("<Button-1>", confirm)
            cv.bind("<Button-3>", lambda e: [top.destroy(), self.app.deiconify()])
            top.bind("<Escape>", lambda e: [top.destroy(), self.app.deiconify()])
            top.img_ref = tk_img
            self.wait_window(top)
        except Exception:
            self.app.deiconify()
            traceback.print_exc()

    def _toggle_static_monitor(self):
        if self.static_monitor_active:
            self.static_monitor_active = False
            self.btn_monitor.config(text="🔴 启动实时监控", bg=COLORS['btn_bg'])
            self.lbl_monitor_status.config(text="监控已停止")
        else:
            if not self.current_node.data.get('roi'):
                self.app.log("⚠️ 请先框选监控区域", "warning")
                VisualTips.show_toast("⚠️ 请先点击【框选监控区域】", duration=1800)
                return
            self.static_monitor_active = True
            self.btn_monitor.config(text="⏹ 停止监控", bg=COLORS['danger'])
            threading.Thread(target=self._static_monitor_thread, daemon=True).start()

    def _static_monitor_thread(self):
        roi = self.current_node.data.get('roi')
        thr = safe_float(self.current_node.data.get('threshold', 0.98))
        dur = safe_float(self.current_node.data.get('duration', 5.0))

        ctx = self.app.core.context
        if ctx['window_handle'] and ctx['window_rect']:
            win_offset_x, win_offset_y = ctx['window_offset']
            abs_x = roi[0] + win_offset_x
            abs_y = roi[1] + win_offset_y
        else:
            abs_x = roi[0]
            abs_y = roi[1]

        target_bbox = (abs_x, abs_y, abs_x + roi[2], abs_y + roi[3])
        last_frame = VisionEngine.capture_screen(bbox=target_bbox)

        static_start = time.time()
        while self.static_monitor_active and self.current_node and self.current_node.type == 'if_static':
            curr = VisionEngine.capture_screen(bbox=target_bbox)
            is_static = VisionEngine.compare_images(last_frame, curr, thr)
            elapsed = time.time() - static_start if is_static else 0
            if self.lbl_monitor_status.winfo_exists():
                txt = f"{'🟢 画面静止' if is_static else '🌊 画面变化'} | {elapsed:.1f}s / {dur}s"
                color = COLORS['success'] if elapsed >= dur else (COLORS['fg_text'] if is_static else COLORS['warning'])
                self.app.after(0, lambda t=txt, c=color: self.lbl_monitor_status.winfo_exists() and self.lbl_monitor_status.config(text=t, fg=c))
            if not is_static:
                static_start = time.time()
                last_frame = curr
            time.sleep(0.1)
        self.static_monitor_active = False

    def _toggle_audio_monitor(self):
        self.is_monitoring_audio = not self.is_monitoring_audio
        self.monitor_audio_btn.config(text="⏹ 停止音量监测" if self.is_monitoring_audio else "🔊 实时监测系统音量")
        if self.is_monitoring_audio:
            threading.Thread(target=self._audio_monitor_thread, daemon=True).start()

    def _audio_monitor_thread(self):
        while self.is_monitoring_audio and self.winfo_exists():
            vol = AudioEngine.get_max_audio_peak()
            if vol > 0.001:
                self.app.log(f"📊 实时音量峰值: {vol:.4f}", "info")
            time.sleep(0.5)

class ExportWizardDialog(tk.Toplevel):
    def __init__(self, parent, app, project_data):
        super().__init__(parent)
        self.app = app
        self.project_data = project_data

        self.title("📦 打包导出向导")
        self.geometry("560x760")
        self.config(bg=COLORS['bg_panel'])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_mode = tk.StringVar(value="--hidden-run")
        self.var_single = tk.BooleanVar(value=True)
        self.var_icon = tk.StringVar(value="")
        self.var_show_toast = tk.BooleanVar(value=True)
        self.var_auto_start = tk.BooleanVar(value=True)
        self.var_auto_quit = tk.BooleanVar(value=True)

        x = max(20, parent.winfo_rootx() + (parent.winfo_width() - 560) // 2)
        y = max(20, parent.winfo_rooty() + (parent.winfo_height() - 760) // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS['accent'], height=56)
        header.pack(side='top', fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="发布独立自动化应用 (.exe)", bg=COLORS['accent'], fg='white', font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left', padx=20, pady=12)

        f_btn = tk.Frame(self, bg=COLORS['bg_sidebar'], height=58)
        f_btn.pack(side='bottom', fill='x')
        tk.Button(f_btn, text="📦 选择导出路径并开始打包", command=self._do_export, bg=COLORS['success'], fg=COLORS['success_fg'], font=('Microsoft YaHei UI', 10, 'bold'), bd=0, padx=18, pady=7, cursor="hand2").pack(side='right', padx=20, pady=10)
        tk.Button(f_btn, text="取消", command=self.destroy, bg=COLORS['bg_card'], fg=COLORS['fg_text'], bd=0, padx=15, pady=7, cursor="hand2").pack(side='right')

        content = tk.Frame(self, bg=COLORS['bg_panel'], padx=26, pady=12)
        content.pack(side='top', fill='both', expand=True)

        f_mode = tk.Frame(content, bg=COLORS['bg_panel'])
        f_mode.pack(fill='x', pady=(0, 6))
        tk.Label(f_mode, text="运行模式：", bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w', pady=(0, 4))

        rb1 = tk.Radiobutton(f_mode, text="👻 无痕静默运行 (推荐)", variable=self.var_mode, value="--hidden-run", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2")
        rb1.pack(anchor='w')
        tk.Label(f_mode, text="双击后无主窗口，将在右下角托盘驻留，适合正式交付使用。", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(anchor='w', padx=24)

        rb2 = tk.Radiobutton(f_mode, text="🖥️ 显示编辑器与控制台界面", variable=self.var_mode, value="--run", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2")
        rb2.pack(anchor='w', pady=(4, 0))

        f_opt = tk.Frame(content, bg=COLORS['bg_panel'])
        f_opt.pack(fill='x', pady=6)
        tk.Checkbutton(f_opt, text="🔒 开启防多开保护 (阻止重复双击导致冲突)", variable=self.var_single, bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2").pack(anchor='w')
        tk.Checkbutton(f_opt, text="🔔 开启运行时状态悬浮提示（启停时在右下角显示）", variable=self.var_show_toast, bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2").pack(anchor='w', pady=(2, 0))
        tk.Checkbutton(f_opt, text="🚀 双击EXE后自动开始执行 (取消则仅常驻后台等待快捷键)", variable=self.var_auto_start, bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2").pack(anchor='w', pady=(2, 0))
        tk.Checkbutton(f_opt, text="🏁 任务执行完毕后自动完全退出 (不勾选则挂起等待再次唤醒)", variable=self.var_auto_quit, bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'], activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'], font=('Microsoft YaHei UI', 9), cursor="hand2").pack(anchor='w', pady=(2, 0))

        f_icon = tk.Frame(content, bg=COLORS['bg_panel'])
        f_icon.pack(fill='x', pady=6)
        tk.Label(f_icon, text="自定义图标 (.ico)：", bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w', pady=(0, 2))
        icon_row = tk.Frame(f_icon, bg=COLORS['bg_panel'])
        icon_row.pack(fill='x')
        e_icon = tk.Entry(icon_row, textvariable=self.var_icon, bg=COLORS['input_bg'], fg=COLORS['input_fg'], insertbackground=COLORS['input_fg'], bd=0, font=('Microsoft YaHei UI', 9))
        e_icon.pack(side='left', fill='x', expand=True, ipady=4)
        tk.Button(icon_row, text="浏览...", command=self._pick_icon, bg=COLORS['btn_bg'], fg=COLORS['fg_text'], bd=0, padx=10, pady=3, cursor="hand2").pack(side='left', padx=(8, 0))

        f_delay = tk.Frame(content, bg=COLORS['bg_panel'])
        f_delay.pack(fill='x', pady=6)
        tk.Label(f_delay, text="延时启动(秒)：", bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 10, 'bold')).pack(side='left')
        self.var_delay = tk.IntVar(value=3)
        tk.Spinbox(f_delay, from_=0, to=60, textvariable=self.var_delay, width=5, bg=COLORS['input_bg'], fg=COLORS['input_fg'], buttonbackground=COLORS['bg_panel'], bd=0).pack(side='left', padx=6, ipady=2)
        tk.Label(f_delay, text="（留出时间将手离开鼠标或切换窗口）", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).pack(side='left')

        f_hk = tk.Frame(content, bg=COLORS['bg_panel'])
        f_hk.pack(fill='x', pady=6)
        tk.Label(f_hk, text="全局快捷键绑定：", bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w', pady=(0, 4))

        safe_hks = [f"<f{i}>" for i in range(1, 13)] + [f"<ctrl>+<f{i}>" for i in range(1, 13)] + ["<home>", "<end>", "<insert>", "<delete>", "<page up>", "<page down>"]

        hk_row1 = tk.Frame(f_hk, bg=COLORS['bg_panel'])
        hk_row1.pack(fill='x', pady=2)
        tk.Label(hk_row1, text="▶ 启动键:", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.var_hk_start = tk.StringVar(value=SETTINGS.get('hotkey_start', '<f9>'))
        if self.var_hk_start.get() not in safe_hks:
            self.var_hk_start.set("<f9>")
        ttk.Combobox(hk_row1, textvariable=self.var_hk_start, values=safe_hks, state='readonly', width=10).pack(side='left', padx=5)

        tk.Label(hk_row1, text="⏸ 停止(中止)键:", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left', padx=(10, 0))
        self.var_hk_stop = tk.StringVar(value=SETTINGS.get('hotkey_stop', '<f10>'))
        if self.var_hk_stop.get() not in safe_hks:
            self.var_hk_stop.set("<f10>")
        ttk.Combobox(hk_row1, textvariable=self.var_hk_stop, values=safe_hks, state='readonly', width=10).pack(side='left', padx=5)

        hk_row2 = tk.Frame(f_hk, bg=COLORS['bg_panel'])
        hk_row2.pack(fill='x', pady=5)
        tk.Label(hk_row2, text="❌ 完全退出键:", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.var_hk_quit = tk.StringVar(value="<ctrl>+<f12>")
        ttk.Combobox(hk_row2, textvariable=self.var_hk_quit, values=safe_hks, state='readonly', width=10).pack(side='left', padx=5)

        f_warn = tk.Frame(content, bg=COLORS['bg_card'], padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS['danger'])
        f_warn.pack(fill='x', pady=(8, 0))
        tk.Label(f_warn, text="⚠️ 防失控机制（全局紧急停止）", bg=COLORS['bg_card'], fg=COLORS['danger'], font=('Microsoft YaHei UI', 5, 'bold')).pack(anchor='w')
        tk.Label(f_warn, text="遇到死循环时，随时按【停止键】或将鼠标甩到屏幕左上角可立刻打断流程；按【完全退出键】或通过右下角托盘可彻底关闭程序。", bg=COLORS['bg_card'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 8), justify='left', wraplength=480).pack(anchor='w', pady=(3, 0))

    def _pick_icon(self):
        f = filedialog.askopenfilename(filetypes=[("Icon Files", "*.ico")])
        if f:
            self.var_icon.set(f)

    def _do_export(self):
        default_name = "导出自动化项目"
        if self.app.current_file_path:
            default_name = os.path.splitext(os.path.basename(self.app.current_file_path))[0]

        target_exe = filedialog.asksaveasfilename(initialfile=default_name, defaultextension=".exe", filetypes=[("Executable", "*.exe")])
        if not target_exe:
            return

        self.app.log("⏳ 正在准备编译环境...", "info")
        self.update()

        import glob
        csc_paths = glob.glob(r"C:\Windows\Microsoft.NET\Framework\v4.*\csc.exe")
        if not csc_paths:
            messagebox.showerror("错误", "未找到系统内置的 C# 编译器 (csc.exe)。\n您的系统可能缺少必要的 .NET Framework。")
            return
        csc_path = csc_paths[-1]

        if 'metadata' not in self.project_data:
            self.project_data['metadata'] = {}
        self.project_data['metadata']['export_settings'] = {
            'delay': self.var_delay.get(),
            'hotkey_start': self.var_hk_start.get(),
            'hotkey_stop': self.var_hk_stop.get(),
            'hotkey_quit': self.var_hk_quit.get(),
            'show_toast': self.var_show_toast.get(),
            'auto_start': self.var_auto_start.get(),
            'auto_quit': self.var_auto_quit.get()
        }
        json_str = json.dumps(self.project_data, ensure_ascii=False)
        b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        is_python = not getattr(sys, 'frozen', False)

        escaped_exe_path = exe_path.replace('\\', '\\\\')
        escaped_script_path = os.path.abspath(sys.argv[0]).replace('\\', '\\\\')
        is_python_str = str(is_python).lower()

        run_arg = self.var_mode.get()
        uuid_str = uuid.uuid4().hex

        mutex_code = ""
        if self.var_single.get():
            mutex_code = f"""
            bool createdNew;
            System.Threading.Mutex mutex = new System.Threading.Mutex(true, "QflowApp_{uuid_str}", out createdNew);
            if (!createdNew) {{ return; }}
            """

        cs_code = f"""
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

class Program {{
    [STAThread]
    static void Main(string[] args) {{
        {mutex_code}
        try {{
            string tempFile = Path.Combine(Path.GetTempPath(), "qflow_temp_" + Guid.NewGuid().ToString() + ".qflow");
            string exeName = "Qflow.exe";
            string portableEngine = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, exeName);
            string targetFileName = null;
            string targetArguments = null;

            if (File.Exists(portableEngine)) {{
                targetFileName = portableEngine;
                targetArguments = "\\"" + tempFile + "\\" {run_arg}";
            }}

            if (targetFileName == null) {{
                try {{
                    using (RegistryKey key = Registry.CurrentUser.OpenSubKey(@"Software\\Classes\\QflowProject\\shell\\open\\command")) {{
                        if (key != null) {{
                            string cmd = key.GetValue("") as string;
                            if (!string.IsNullOrEmpty(cmd) && cmd.StartsWith("\\"")) {{
                                int secondQuote = cmd.IndexOf("\\"", 1);
                                if (secondQuote > 1) {{
                                    string exePart = cmd.Substring(1, secondQuote - 1);
                                    string argsPart = cmd.Substring(secondQuote + 1).Trim();
                                    if (File.Exists(exePart)) {{
                                        targetFileName = exePart;
                                        targetArguments = argsPart.Replace("\\"%1\\"", "\\"" + tempFile + "\\"") + " {run_arg}";
                                    }}
                                }}
                            }}
                        }}
                    }}
                }} catch {{}}
            }}

            if (targetFileName == null) {{
                bool isPython = {is_python_str};
                string originalExe = @"{escaped_exe_path}";
                string scriptPath = @"{escaped_script_path}";

                if (File.Exists(originalExe)) {{
                    targetFileName = originalExe;
                    if (isPython) {{
                        targetArguments = "\\"" + scriptPath + "\\" \\"" + tempFile + "\\" {run_arg}";
                    }} else {{
                        targetArguments = "\\"" + tempFile + "\\" {run_arg}";
                    }}
                }}
            }}

            if (targetFileName == null) {{
                MessageBox.Show("运行失败：未在本机找到 Qflow 自动化引擎！\\n\\n【解决方案】\\n1. 绿色便携版：请将此程序与 Qflow.exe 放在同一个文件夹内运行。\\n2. 独立安装版：请在当前电脑上运行一次 Qflow 主程序完成环境注册。\\n", "缺失运行环境", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }}

            string b64 = "{b64_str}";
            byte[] bytes = Convert.FromBase64String(b64);
            string jsonContent = Encoding.UTF8.GetString(bytes);
            File.WriteAllText(tempFile, jsonContent, Encoding.UTF8);

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = targetFileName;
            psi.Arguments = targetArguments;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;

            Process p = Process.Start(psi);
            if (p != null) {{
                p.WaitForExit();
            }}
            try {{ File.Delete(tempFile); }} catch {{}}

        }} catch (Exception e) {{
            MessageBox.Show("启动发生异常：\\n" + e.Message, "系统致命错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }}
    }}
}}
"""
        temp_cs = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"qflow_launcher_{uuid.uuid4().hex[:8]}.cs")
        try:
            with open(temp_cs, "w", encoding="utf-8-sig") as f:
                f.write(cs_code)

            cmd_args = [csc_path, "/nologo", "/target:winexe", f"/out:{target_exe}", "/reference:System.Windows.Forms.dll", temp_cs]

            icon_file = self.var_icon.get().strip()
            if not icon_file or not os.path.exists(icon_file):
                if hasattr(sys, '_MEIPASS'):
                    icon_file = os.path.join(sys._MEIPASS, 'icon2.ico')
                else:
                    icon_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon2.ico')

            if icon_file and os.path.exists(icon_file):
                cmd_args.append(f"/win32icon:{icon_file}")

            res = subprocess.run(cmd_args, shell=False, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)

            if res.returncode == 0 and os.path.exists(target_exe):
                self.app.log(f"📦 成功打包应用: {os.path.basename(target_exe)}", "success")
                VisualTips.show_toast(f"🎉 EXE 打包成功：{os.path.basename(target_exe)}", duration=2500)
                self.destroy()
            else:
                err_msg = res.stdout.strip() if res.stdout else res.stderr.strip()
                self.app.log(f"❌ 打包失败 (代码:{res.returncode}): {err_msg}", "error")
                messagebox.showerror("打包失败", f"编译器返回错误:\n{err_msg}")
        except Exception as e:
            self.app.log(f"❌ 导出发生异常: {e}", "error")
            messagebox.showerror("异常", f"导出过程发生未知错误:\n{e}")
        finally:
            if os.path.exists(temp_cs):
                try:
                    os.remove(temp_cs)
                except Exception:
                    pass

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("系统设置")
        self.geometry("420x340")
        self.config(bg=COLORS['bg_panel'])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.app.stop_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 80, parent.winfo_rooty() + 80))

        f_theme = tk.Frame(self, bg=COLORS['bg_panel'], pady=12, padx=22)
        f_theme.pack(fill='x')
        tk.Label(f_theme, text="界面主题:", bg=COLORS['bg_panel'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.combo_theme = ttk.Combobox(f_theme, values=list(THEMES.keys()), state='readonly', font=('Microsoft YaHei UI', 9))
        self.combo_theme.set(SETTINGS.get('theme', 'Dark'))
        self.combo_theme.pack(side='right', fill='x', expand=True, padx=10)

        f_hk = tk.Frame(self, bg=COLORS['bg_panel'], pady=10, padx=22)
        f_hk.pack(fill='x')
        self.hk_vars = {
            'start': tk.StringVar(value=SETTINGS.get('hotkey_start', '<f9>')),
            'stop': tk.StringVar(value=SETTINGS.get('hotkey_stop', '<f10>'))
        }
        self._create_hotkey_entry(f_hk, "启动快捷键:", 'start', 0)
        self._create_hotkey_entry(f_hk, "停止快捷键:", 'stop', 1)
        tk.Label(f_hk, text="提示：点击输入框后直接按下键盘按键即可录制，右键可清空", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8)).grid(row=2, column=0, columnspan=2, sticky='w', pady=(4, 0))
        f_hk.columnconfigure(1, weight=1)

        f_assoc = tk.Frame(self, bg=COLORS['bg_panel'], pady=10, padx=22)
        f_assoc.pack(fill='x')
        self.var_assoc = tk.BooleanVar(value=self.app.is_file_associated())
        chk_assoc = tk.Checkbutton(
            f_assoc, text="关联 *.qflow 项目文件（支持双击直接打开）", variable=self.var_assoc,
            bg=COLORS['bg_panel'], fg=COLORS['fg_text'], selectcolor=COLORS['input_bg'],
            activebackground=COLORS['bg_panel'], activeforeground=COLORS['fg_text'],
            font=('Microsoft YaHei UI', 9), cursor="hand2"
        )
        chk_assoc.pack(anchor='w')

        btn_frame = tk.Frame(self, bg=COLORS['bg_panel'], pady=18)
        btn_frame.pack(side='bottom', fill='x')
        tk.Button(btn_frame, text="保存并应用", command=self.save, bg=COLORS['accent'], fg=COLORS['accent_fg'], bd=0, padx=18, pady=5, cursor='hand2', font=('Microsoft YaHei UI', 9, 'bold')).pack(side='right', padx=22)
        tk.Button(btn_frame, text="取消", command=self.on_cancel, bg=COLORS['btn_bg'], fg=COLORS['fg_text'], bd=0, padx=18, pady=5, cursor='hand2', font=('Microsoft YaHei UI', 9)).pack(side='right')

    def _create_hotkey_entry(self, parent, label, key, row):
        tk.Label(parent, text=label, bg=COLORS['bg_panel'], fg=COLORS['fg_text'], font=('Microsoft YaHei UI', 9)).grid(row=row, column=0, sticky='w', pady=6)
        e = tk.Entry(parent, textvariable=self.hk_vars[key], bg=COLORS['input_bg'], fg=COLORS['input_fg'], insertbackground=COLORS['input_fg'], bd=0, font=('Consolas', 9))
        e.grid(row=row, column=1, sticky='ew', padx=10, ipady=4)
        e.bind("<KeyPress>", lambda ev: self._on_key(ev, key))
        e.bind("<Button-3>", lambda ev: self.hk_vars[key].set(""))

    def _on_key(self, event, key):
        if event.keysym in ['Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Win_L', 'Win_R']:
            return "break"
        if event.keysym == 'Escape':
            self.hk_vars[key].set("")
            self.focus_set()
            return "break"

        parts = []
        if event.state & 0x0004:
            parts.append("<ctrl>")
        if event.state & 0x20000 or event.state & 0x0008:
            parts.append("<alt>")
        if event.state & 0x0001:
            parts.append("<shift>")

        sym = event.keysym.lower()
        if len(sym) > 1 and sym.startswith('f') and sym[1:].isdigit():
            sym = f"<{sym}>"
        elif sym.startswith('kp_'):
            if sym == 'kp_enter':
                sym = '<enter>'
            elif sym.replace('kp_', '').isdigit():
                sym = sym.replace('kp_', '')
            else:
                sym = f"<{sym}>"

        parts.append(sym)
        self.hk_vars[key].set("+".join(parts))
        return "break"

    def on_cancel(self):
        self.app.refresh_hotkeys()
        self.destroy()

    def save(self):
        start_hk = self.hk_vars['start'].get().strip()
        stop_hk = self.hk_vars['stop'].get().strip()
        if start_hk and start_hk == stop_hk:
            messagebox.showwarning("快捷键冲突", "启动快捷键与停止快捷键不能相同！", parent=self)
            return
        SETTINGS['theme'] = self.combo_theme.get()
        SETTINGS['hotkey_start'] = start_hk
        SETTINGS['hotkey_stop'] = stop_hk
        save_user_settings()
        if self.var_assoc.get():
            self.app.set_auto_associate(True)
            if not self.app.is_file_associated():
                self.app.register_file_association(silent=True)
        else:
            self.app.set_auto_associate(False)
            if self.app.is_file_associated():
                self.app.unregister_file_association(silent=True)
        COLORS.update(THEMES.get(SETTINGS['theme'], THEMES['Dark']))
        self.app.refresh_hotkeys()
        self.app.restart_ui()
        self.destroy()

class App(tk.Tk):
    def __init__(self, file_path=None, auto_run=False, hidden_run=False):
        super().__init__()

        try:
            self.tk.call('tk', 'scaling', SCREEN_DPI / 72.0)
        except Exception:
            pass

        self._hidden_run_mode = hidden_run
        if self._hidden_run_mode:
            self.withdraw()

        self.current_file_path = None
        self.is_dirty = False
        self._auto_run_mode = auto_run or hidden_run
        try:
            screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
            win_w = min(1420, max(920, screen_w - 60))
            win_h = min(920, max(620, screen_h - 100))
            self.geometry(f"{win_w}x{win_h}")
            self.minsize(min(900, max(760, screen_w - 40)), min(620, max(520, screen_h - 60)))
        except tk.TclError:
            self.geometry("1280x820")
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.core = AutomationCore(self.log, self)
        self.log_q = queue.Queue()
        self.drag_node_type, self.drag_ghost = None, None
        self.hotkey_listener = None
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self._setup_ui()
        self.refresh_hotkeys()
        self.bind_all("<Delete>", self._dispatch_delete, add="+")
        self.bind_all("<Control-z>", self._dispatch_undo, add="+")
        self.bind_all("<Control-y>", self._dispatch_redo, add="+")
        self.bind_all("<Control-Shift-Z>", self._dispatch_redo, add="+")
        self.bind_all("<Control-a>", self._dispatch_select_all, add="+")
        self.bind_all("<Control-c>", self._dispatch_copy, add="+")
        self.bind_all("<Control-v>", self._dispatch_paste, add="+")
        self.bind_all("<Control-d>", self._dispatch_duplicate, add="+")
        self.bind_all("<MouseWheel>", self._route_property_wheel, add="+")
        self.bind_all("<Button-4>", self._route_property_wheel, add="+")
        self.bind_all("<Button-5>", self._route_property_wheel, add="+")
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-o>", lambda e: self.load())
        self.bind("<Control-n>", lambda e: self.new_project())
        self.bind("<Control-Shift-S>", lambda e: self.save_as())

        if file_path and os.path.exists(file_path):
            self.current_file_path = file_path
            self.after(200, lambda: self._load_initial_file(auto_run or hidden_run))

        self.update_title()
        self.after(100, self._poll_log)
        self.after(500, self.show_welcome_guide)
        self.after(1000, self.check_file_association)

    def mark_dirty(self, dirty=True):
        if self.is_dirty != bool(dirty):
            self.is_dirty = bool(dirty)
            self.update_title()

    def _confirm_discard_changes(self, action_name="继续"):
        if not self.is_dirty or self._auto_run_mode or self._hidden_run_mode:
            return True
        res = messagebox.askyesnocancel(
            "未保存的修改",
            f"当前流程存在未保存的修改，是否在{action_name}前保存？",
            parent=self
        )
        if res is None:
            return False
        if res is True:
            return bool(self.save())
        return True

    def on_close_window(self):
        if not self._confirm_discard_changes("退出程序"):
            return
        self.quit_app()

    def new_project(self):
        if not self._confirm_discard_changes("新建项目"):
            return False
        self.editor.history.undo_stack.clear()
        self.editor.history.redo_stack.clear()
        self.editor.load_data({'nodes': {}, 'links': []})
        self.editor.add_node('start', 100, 100, save_history=False)
        self.current_file_path = None
        self.mark_dirty(False)
        self.after_idle(lambda: self.editor.fit_view(selected_only=False) if self.editor.winfo_exists() else None)
        self.log("📄 已新建空白流程项目", "info")
        return True

    def _route_property_wheel(self, event):
        panel = getattr(self, 'property_panel', None)
        if panel is None or not panel.winfo_exists():
            return None
        try:
            widget_path = str(event.widget)
            panel_path = str(panel)
            if widget_path != panel_path and not widget_path.startswith(panel_path + '.'):
                return None
            if getattr(event, 'num', None) == 4:
                delta = -1
            elif getattr(event, 'num', None) == 5:
                delta = 1
            else:
                raw = getattr(event, 'delta', 0)
                delta = int(-raw / 120)
                if delta == 0 and raw:
                    delta = -1 if raw > 0 else 1
            if delta:
                panel.canvas.yview_scroll(delta, 'units')
                return 'break'
        except tk.TclError:
            return None
        return None

    def _dispatch_editor_shortcut(self, event, method_name):
        editor = getattr(self, 'editor', None)
        if editor is None or not editor.winfo_exists() or editor._is_text_input(event):
            return None
        return getattr(editor, method_name)(event)

    def _dispatch_delete(self, event=None):
        return self._dispatch_editor_shortcut(event, '_on_delete_press')

    def _dispatch_undo(self, event=None):
        return self._dispatch_editor_shortcut(event, '_shortcut_undo')

    def _dispatch_redo(self, event=None):
        return self._dispatch_editor_shortcut(event, '_shortcut_redo')

    def _dispatch_select_all(self, event=None):
        return self._dispatch_editor_shortcut(event, '_shortcut_select_all')

    def _dispatch_copy(self, event=None):
        return self._dispatch_editor_shortcut(event, 'copy_selected_nodes')

    def _dispatch_paste(self, event=None):
        return self._dispatch_editor_shortcut(event, 'paste_nodes')

    def _dispatch_duplicate(self, event=None):
        return self._dispatch_editor_shortcut(event, 'duplicate_selected_nodes')

    def deiconify(self):
        if getattr(self, '_hidden_run_mode', False):
            return
        super().deiconify()

    def iconify(self):
        if getattr(self, '_hidden_run_mode', False):
            return
        super().iconify()

    def is_file_associated(self):
        import winreg
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            if not getattr(sys, 'frozen', False):
                py_exe = sys.executable
                if py_exe.lower().endswith("python.exe"):
                    py_exe = py_exe[:-10] + "pythonw.exe"
                expected_cmd = f'"{py_exe}" "{exe_path}" "%1"'
            else:
                expected_cmd = f'"{exe_path}" "%1"'

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.qflow") as key:
                if winreg.QueryValueEx(key, "")[0] != "QflowProject":
                    return False
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\QflowProject\shell\open\command") as key:
                if winreg.QueryValueEx(key, "")[0] != expected_cmd:
                    return False
            return True
        except Exception:
            return False

    def should_auto_associate(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Qflow") as key:
                val, _ = winreg.QueryValueEx(key, "AutoAssociate")
                return bool(val)
        except Exception:
            return True

    def set_auto_associate(self, enable=True):
        import winreg
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Qflow") as key:
                winreg.SetValueEx(key, "AutoAssociate", 0, winreg.REG_DWORD, 1 if enable else 0)
        except Exception:
            pass

    def register_file_association(self, silent=False):
        import winreg
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])

            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon2.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon2.ico')

            if not getattr(sys, 'frozen', False):
                py_exe = sys.executable
                if py_exe.lower().endswith("python.exe"):
                    py_exe = py_exe[:-10] + "pythonw.exe"
                cmd_str = f'"{py_exe}" "{exe_path}" "%1"'
                icon_str = f'"{icon_path}",0' if os.path.exists(icon_path) else f'"{py_exe}",0'
            else:
                cmd_str = f'"{exe_path}" "%1"'
                icon_str = f'"{icon_path}",0' if os.path.exists(icon_path) else f'"{exe_path}",0'

            key_path = r"Software\Classes\.qflow"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "QflowProject")

            key_path_prog = r"Software\Classes\QflowProject"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_prog) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Qflow 自动化项目")

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_prog + r"\DefaultIcon") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, icon_str)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path_prog + r"\shell\open\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, cmd_str)

            self.set_auto_associate(True)

            try:
                ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
            except Exception:
                pass

            self.log("🔗 已注册 .qflow 文件关联", "info")
            if not silent:
                VisualTips.show_toast("🔗 已关联 .qflow 项目文件", duration=2000)
        except Exception as e:
            if not silent:
                messagebox.showerror("失败", f"注册失败: {e}\n\n建议您以管理员身份重新运行程序后再试。")

    def unregister_file_association(self, silent=False):
        import winreg
        try:
            def delete_key_recursive(root, subkey):
                try:
                    with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                        while True:
                            try:
                                child = winreg.EnumKey(key, 0)
                                delete_key_recursive(key, child)
                            except OSError:
                                break
                    winreg.DeleteKey(root, subkey)
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

            delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\.qflow")
            delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\QflowProject")

            try:
                ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
            except Exception:
                pass

            self.log("🔗 已取消 .qflow 文件关联", "info")
            if not silent:
                VisualTips.show_toast("🔗 已取消 .qflow 文件关联", duration=2000)
        except Exception as e:
            self.log(f"取消关联失败: {e}", "warning")
            if not silent:
                messagebox.showerror("失败", f"取消关联失败: {e}")

    def check_file_association(self):
        if self._auto_run_mode:
            return
        if not self.is_file_associated() and self.should_auto_associate():
            self.register_file_association(silent=True)

    def _load_initial_file(self, auto_run):
        try:
            with open(self.current_file_path, 'r', encoding='utf-8-sig') as fp:
                project_data = json.load(fp)
            if not self.editor.load_data(project_data):
                raise ValueError("项目结构校验失败，已取消加载")
            self.mark_dirty(False)
            self.update_title()
            self.after_idle(lambda: self.editor.fit_view(selected_only=False) if self.editor.winfo_exists() else None)
            self.log(f"📂 已加载项目: {self.current_file_path}", "success")
            if auto_run:
                settings = self.editor.get_data().get('metadata', {}).get('export_settings', {})
                try:
                    delay = int(settings.get('delay', 0))
                except Exception:
                    delay = 0
                hk_start = settings.get('hotkey_start')
                hk_stop = settings.get('hotkey_stop')
                hk_quit = settings.get('hotkey_quit')
                auto_start = settings.get('auto_start', True)
                self._auto_quit = settings.get('auto_quit', True)
                self._show_export_toast = settings.get('show_toast', True)

                if hk_start:
                    SETTINGS['hotkey_start'] = hk_start
                if hk_stop:
                    SETTINGS['hotkey_stop'] = hk_stop
                if hk_quit:
                    SETTINGS['hotkey_quit'] = hk_quit
                self.refresh_hotkeys()

                self.setup_tray()

                if auto_start:
                    if delay > 0:
                        self.log(f"⏳ 延时 {delay} 秒后启动...", "info")
                        if self._show_export_toast:
                            VisualTips.show_toast(f"⏳ 准备就绪，延时 {delay} 秒后开始执行...", duration=max(2000, delay * 1000 - 500), position='bottom_right')
                        self.after(delay * 1000, lambda: self.toggle_run(None))
                    else:
                        self.log("🚀 检测到运行参数，即将自动启动...", "info")
                        self.after(500, lambda: self.toggle_run(None))
                else:
                    self.log("🟢 程序已挂起待命", "info")
                    if self._show_export_toast:
                        VisualTips.show_toast(f"🟢 程序已在后台待命，请按 {hk_start} 开始执行", duration=2500, position='bottom_right')
        except Exception as e:
            self.log(f"❌ 加载文件失败: {e}", "error")
            if getattr(self, '_hidden_run_mode', False) or getattr(self, '_auto_run_mode', False):
                self.quit_app()

    def setup_tray(self):
        if not HAS_PYSTRAY:
            return
        if hasattr(self, 'tray_icon') and self.tray_icon:
            return
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                image = Image.new('RGB', (64, 64), color=(30, 30, 30))

            menu = (
                MenuItem('▶ 启动任务', lambda: self.after(0, lambda: self.toggle_run(None))),
                MenuItem('⏹ 停止任务', lambda: self.after(0, self.core.stop)),
                MenuItem('❌ 完全退出', lambda: self.after(0, self.quit_app))
            )
            self.tray_icon = pystray.Icon("Qflow", image, "Qflow 自动化", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            self.log(f"托盘初始化失败: {e}", "error")

    def quit_app(self):
        if getattr(self, '_quit_requested', False):
            return
        self._quit_requested = True
        self.stop_hotkeys()
        if self.core.running:
            self.core.stop()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self._finish_quit()

    def _finish_quit(self):
        with self.core.thread_lock:
            active_threads = self.core.active_threads
        if self.core.running or active_threads:
            self.after(50, self._finish_quit)
            return
        try:
            self.destroy()
        except tk.TclError:
            pass

    def update_title(self):
        filename = os.path.basename(self.current_file_path) if self.current_file_path else "未命名流程"
        dirty_mark = " *" if getattr(self, 'is_dirty', False) else ""
        title_text = f"{__app_name__} {__version__} - {filename}{dirty_mark}"
        self.title(title_text)
        project_label = getattr(self, 'project_label', None)
        if project_label is not None and project_label.winfo_exists():
            try:
                project_label.configure(text=f"{filename}{dirty_mark}")
            except tk.TclError:
                pass

    def _setup_ui(self):
        self.configure(bg=COLORS['bg_app'])
        style = ttk.Style(self)
        try:
            if 'clam' in style.theme_names():
                style.theme_use('clam')
            style.configure(
                'TCombobox',
                fieldbackground=COLORS['input_bg'],
                background=COLORS['bg_panel'],
                foreground=COLORS['input_fg'],
                arrowcolor=COLORS['fg_text'],
                selectbackground=COLORS['accent'],
                selectforeground=COLORS['accent_fg'],
                bordercolor=COLORS['bg_header'],
                lightcolor=COLORS['bg_header'],
                darkcolor=COLORS['bg_header'],
            )
            style.map(
                'TCombobox',
                fieldbackground=[
                    ('disabled', COLORS['bg_panel']),
                    ('readonly', COLORS['input_bg']),
                    ('!disabled', COLORS['input_bg']),
                ],
                foreground=[
                    ('disabled', COLORS['fg_sub']),
                    ('readonly', COLORS['input_fg']),
                    ('!disabled', COLORS['input_fg']),
                ],
                background=[
                    ('disabled', COLORS['bg_panel']),
                    ('readonly', COLORS['bg_panel']),
                    ('active', COLORS['hover']),
                ],
                selectbackground=[('readonly', COLORS['accent'])],
                selectforeground=[('readonly', COLORS['accent_fg'])],
            )
            self.option_add('*TCombobox*Listbox.background', COLORS['input_bg'])
            self.option_add('*TCombobox*Listbox.foreground', COLORS['input_fg'])
            self.option_add('*TCombobox*Listbox.selectBackground', COLORS['accent'])
            self.option_add('*TCombobox*Listbox.selectForeground', COLORS['accent_fg'])
            self.option_add('*TCombobox*Listbox.font', ('Microsoft YaHei UI', 9))
            style.configure('Vertical.TScrollbar', background=COLORS['bg_panel'], troughcolor=COLORS['bg_app'], arrowcolor=COLORS['fg_text'], bordercolor=COLORS['bg_app'])
            style.configure('Horizontal.TScrollbar', background=COLORS['bg_panel'], troughcolor=COLORS['bg_app'], arrowcolor=COLORS['fg_text'], bordercolor=COLORS['bg_app'])
            if not getattr(self, '_combobox_popup_theme_bound', False):
                self.bind_class('TCombobox', '<Map>', self._on_combobox_mapped, add='+')
                self._combobox_popup_theme_bound = True
        except tk.TclError:
            pass
        for widget in self.winfo_children():
            widget.destroy()

        title_bar = tk.Frame(
            self, bg=COLORS['bg_panel'], height=52,
            highlightthickness=1, highlightbackground=COLORS['bg_header']
        )
        title_bar.pack(fill='x', side='top', pady=(6, 6), padx=10)
        title_bar.pack_propagate(False)

        run_group = tk.Frame(title_bar, bg=COLORS['bg_panel'])
        run_group.pack(side='right', padx=(8, 10), pady=7)

        self.btn_run = tk.Button(
            run_group, text=f"▶ 运行 ({SETTINGS.get('hotkey_start', '<f9>').upper()})",
            command=lambda: self.toggle_run(None),
            bg=COLORS['success'], fg=COLORS['success_fg'],
            activebackground=COLORS['success'], activeforeground=COLORS['success_fg'],
            font=('Microsoft YaHei UI', 9, 'bold'), padx=14, pady=5,
            bd=0, relief='flat', highlightthickness=0, cursor='hand2'
        )
        self.btn_run.pack(side='right')
        self.btn_pause = tk.Button(
            run_group, text="⏸ 暂停", command=self.toggle_pause,
            bg=COLORS['bg_header'], fg=COLORS['fg_text'],
            activebackground=COLORS['btn_hover'], activeforeground=COLORS['fg_text'],
            bd=0, relief='flat', highlightthickness=0, padx=10, pady=5,
            state='disabled', cursor='hand2', font=('Microsoft YaHei UI', 9)
        )
        self.btn_pause.pack(side='right', padx=(0, 6))

        brand = tk.Frame(title_bar, bg=COLORS['bg_panel'])
        brand.pack(side='left', padx=(12, 10), pady=5)
        tk.Label(
            brand, text=__app_name__, bg=COLORS['bg_panel'], fg=COLORS['accent'],
            font=('Microsoft YaHei UI', 13, 'bold'), anchor='w'
        ).pack(anchor='w')
        tk.Label(
            brand, text="可视化自动化", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'],
            font=('Microsoft YaHei UI', 8), anchor='w'
        ).pack(anchor='w')

        tk.Frame(title_bar, bg=COLORS['bg_header'], width=1).pack(
            side='left', fill='y', pady=11, padx=(0, 9)
        )

        ops = tk.Frame(title_bar, bg=COLORS['bg_panel'])
        ops.pack(side='left', fill='y', pady=7)

        def add_toolbar_button(parent, text, command, *, color=None, fg=None, tooltip=None):
            normal_bg = color or COLORS['bg_header']
            normal_fg = fg or COLORS['fg_text']
            button = tk.Button(
                parent, text=text, command=command, bg=normal_bg, fg=normal_fg,
                activebackground=COLORS['btn_hover'], activeforeground=normal_fg,
                bd=0, relief='flat', highlightthickness=0,
                padx=9, pady=5, cursor='hand2', font=('Microsoft YaHei UI', 9)
            )
            button.pack(side='left', padx=(0, 4))
            button.bind('<Enter>', lambda _e, w=button: w.configure(bg=COLORS['btn_hover']))
            button.bind('<Leave>', lambda _e, w=button, bg=normal_bg: w.configure(bg=bg))
            if tooltip:
                ToolTip(button, tooltip)
            return button

        add_toolbar_button(ops, "新建", self.new_project, tooltip="新建空白项目 (Ctrl+N)")
        add_toolbar_button(ops, "打开", self.load, tooltip="打开 .qflow 项目 (Ctrl+O)")
        add_toolbar_button(ops, "保存", self.save, tooltip="保存项目 (Ctrl+S)")
        add_toolbar_button(ops, "另存为", self.save_as, tooltip="另存为新文件 (Ctrl+Shift+S)")
        tk.Frame(ops, bg=COLORS['bg_header'], width=1).pack(
            side='left', fill='y', pady=7, padx=(4, 8)
        )
        add_toolbar_button(ops, "撤销", lambda: self.editor.history.undo(), tooltip="撤销上一步操作 (Ctrl+Z)")
        add_toolbar_button(ops, "重做", lambda: self.editor.history.redo(), tooltip="重做操作 (Ctrl+Y)")
        tk.Frame(ops, bg=COLORS['bg_header'], width=1).pack(
            side='left', fill='y', pady=7, padx=(4, 8)
        )
        add_toolbar_button(ops, "导出 EXE", self.export_exe, tooltip="将当前流程打包为可独立运行的 EXE 程序")
        add_toolbar_button(ops, "清空", self.clear, fg=COLORS['danger'], tooltip="清空画布所有节点（支持 Ctrl+Z 恢复）")
        add_toolbar_button(ops, "设置", self.open_settings, tooltip="主题、全局快捷键与文件关联设置")

        self.project_label = tk.Label(
            title_bar, text="未命名流程", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'],
            font=('Microsoft YaHei UI', 9), anchor='w'
        )
        self.project_label.pack(side='left', fill='x', expand=True, padx=(10, 8))

        self.main_paned = tk.PanedWindow(
            self, orient='vertical', bg=COLORS['bg_app'], sashwidth=5,
            sashrelief='flat', bd=0, opaqueresize=True
        )
        self.main_paned.pack(fill='both', expand=True, padx=10, pady=(0, 6))

        h_paned = tk.PanedWindow(
            self.main_paned, orient='horizontal', bg=COLORS['bg_app'],
            sashwidth=5, sashrelief='flat', bd=0, opaqueresize=True
        )
        self.editor_paned = h_paned
        self.main_paned.add(h_paned, minsize=360, stretch='always')

        toolbox = tk.Frame(h_paned, bg=COLORS['bg_sidebar'], highlightthickness=1, highlightbackground=COLORS['bg_header'])
        self._build_toolbox(toolbox)
        h_paned.add(toolbox, minsize=210, width=230)

        editor_host = tk.Frame(h_paned, bg=COLORS['bg_canvas'], highlightthickness=1, highlightbackground=COLORS['bg_header'])
        self.editor_host = editor_host
        self.editor = FlowEditor(editor_host, self)
        self.editor.pack(fill='both', expand=True)
        view_bar = tk.Frame(
            editor_host, bg=COLORS['bg_panel'], height=30,
            highlightthickness=1, highlightbackground=COLORS['bg_header']
        )
        view_bar.pack(side='bottom', fill='x')
        view_bar.pack_propagate(False)
        self.view_status = tk.Label(
            view_bar, text="1 个节点  ·  0 条连线", bg=COLORS['bg_panel'],
            fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 8), anchor='w'
        )
        self.view_status.pack(side='left', padx=10)
        self.coord_status = tk.Label(
            view_bar, text="X: 0  Y: 0", bg=COLORS['bg_panel'],
            fg=COLORS['fg_sub'], font=('Consolas', 8), anchor='w'
        )
        self.coord_status.pack(side='left', padx=12)

        view_controls = tk.Frame(view_bar, bg=COLORS['bg_panel'])
        view_controls.pack(side='right', padx=6, pady=3)

        def view_button(label, command, width=3, tooltip=None):
            button = tk.Button(
                view_controls, text=label, command=command, width=width,
                bg=COLORS['bg_header'], fg=COLORS['fg_text'],
                activebackground=COLORS['btn_hover'], activeforeground=COLORS['fg_text'],
                bd=0, relief='flat', highlightthickness=0,
                font=('Microsoft YaHei UI', 8), cursor='hand2', padx=4, pady=1
            )
            button.pack(side='left', padx=2)
            if tooltip:
                ToolTip(button, tooltip)
            return button

        view_button("−", lambda: self.editor.zoom_by(1 / 1.1), tooltip="缩小 (Ctrl+-)")
        self.editor.zoom_label = tk.Label(
            view_controls, text="100%", bg=COLORS['bg_panel'], fg=COLORS['fg_text'],
            width=5, font=('Microsoft YaHei UI', 8), anchor='center'
        )
        self.editor.zoom_label.pack(side='left', padx=3)
        view_button("+", lambda: self.editor.zoom_by(1.1), tooltip="放大 (Ctrl++)")
        view_button("100%", self.editor.reset_zoom, width=5, tooltip="重置缩放 (Ctrl+0)")
        view_button("适应画布", self.editor.fit_view, width=8, tooltip="适应全部节点或当前选中节点 (F)")

        h_paned.add(editor_host, minsize=400, stretch="always")
        self.property_panel = PropertyPanel(h_paned, self)
        self.property_panel.configure(highlightthickness=1, highlightbackground=COLORS['bg_header'])
        h_paned.add(self.property_panel, minsize=270, width=295)

        self.log_panel = LogPanel(self.main_paned, highlightthickness=1, highlightbackground=COLORS['bg_header'])
        self.main_paned.add(self.log_panel, minsize=80, height=140, stretch='never')

        self.editor.add_node('start', 100, 100, save_history=False)
        self.mark_dirty(False)
        self.after(180, lambda: self.editor.fit_view(selected_only=False) if self.editor.winfo_exists() else None)
        self.after_idle(self._restore_main_paned_layout)

    def _restore_main_paned_layout(self):
        if getattr(self, '_hidden_run_mode', False):
            return
        try:
            if not self.winfo_exists() or not self.main_paned.winfo_exists():
                return
            self.update_idletasks()
            height = self.main_paned.winfo_height()
            width = self.main_paned.winfo_width()
            workspace = getattr(self, 'editor_paned', None)
            workspace_height = workspace.winfo_height() if workspace and workspace.winfo_exists() else 0
            if width < 200 or height < 300 or workspace_height < 300:
                self.after(120, self._restore_main_paned_layout)
                return
            log_height = min(180, max(110, int(height * 0.16)))
            sash_y = max(360, height - log_height)
            sash_y = min(sash_y, height - 95)
            self.main_paned.sash_place(0, 0, sash_y)
        except (tk.TclError, AttributeError):
            pass

    def _build_toolbox(self, p):
        self._toolbox_group_open = {
            "流程控制": True,
            "鼠标与键盘": True,
            "应用与系统": True,
            "图像与感知": True,
            "变量与剪贴板": True,
        }

        search_bar = tk.Frame(p, bg=COLORS['bg_sidebar'], padx=8, pady=8)
        search_bar.pack(fill='x')
        tk.Label(
            search_bar, text="组件库（拖拽或双击画布添加）", bg=COLORS['bg_sidebar'], fg=COLORS['fg_sub'],
            font=('Microsoft YaHei UI', 8, 'bold')
        ).pack(anchor='w', pady=(0, 5))
        search_row = tk.Frame(
            search_bar, bg=COLORS['input_bg'], highlightthickness=1,
            highlightbackground=COLORS['bg_header']
        )
        search_row.pack(fill='x')
        self._toolbox_search = tk.Entry(
            search_row, bg=COLORS['input_bg'], fg=COLORS['fg_sub'],
            insertbackground=COLORS['input_fg'], relief='flat', bd=0,
            font=('Microsoft YaHei UI', 9)
        )
        self._toolbox_search.insert(0, "搜索组件…")
        self._toolbox_search_placeholder = True
        self._toolbox_search.pack(fill='x', padx=6, pady=5)
        self._toolbox_search.bind('<FocusIn>', self._toolbox_search_focus_in)
        self._toolbox_search.bind('<FocusOut>', self._toolbox_search_focus_out)
        self._toolbox_search.bind('<KeyRelease>', self._toolbox_search_changed)

        body = tk.Frame(p, bg=COLORS['bg_sidebar'])
        body.pack(fill='both', expand=True)
        canvas = tk.Canvas(body, bg=COLORS['bg_sidebar'], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        content = tk.Frame(canvas, bg=COLORS['bg_sidebar'])
        window_id = canvas.create_window((0, 0), window=content, anchor='nw', tags='toolbox_content')
        content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window_id, width=e.width))

        self._toolbox_canvas = canvas
        self._toolbox_content = content
        self._bind_toolbox_wheel(canvas)
        self._render_toolbox()

    def _toolbox_search_focus_in(self, _event=None):
        if getattr(self, '_toolbox_search_placeholder', False):
            self._toolbox_search.delete(0, 'end')
            self._toolbox_search.config(fg=COLORS['input_fg'])
            self._toolbox_search_placeholder = False

    def _toolbox_search_focus_out(self, _event=None):
        if not self._toolbox_search.get().strip():
            self._toolbox_search.delete(0, 'end')
            self._toolbox_search.insert(0, '搜索组件…')
            self._toolbox_search.config(fg=COLORS['fg_sub'])
            self._toolbox_search_placeholder = True

    def _toolbox_search_changed(self, _event=None):
        if not getattr(self, '_toolbox_search_placeholder', False):
            self._render_toolbox()

    def _bind_toolbox_wheel(self, widget):
        def on_wheel(event):
            canvas = getattr(self, '_toolbox_canvas', None)
            if not canvas or not canvas.winfo_exists():
                return
            if getattr(event, 'num', None) == 4:
                delta = -1
            elif getattr(event, 'num', None) == 5:
                delta = 1
            else:
                delta = int(-event.delta / 120)
                if delta == 0 and event.delta:
                    delta = -1 if event.delta > 0 else 1
            if delta:
                canvas.yview_scroll(delta, 'units')
            return 'break'

        try:
            widget.bind('<MouseWheel>', on_wheel, add='+')
            widget.bind('<Button-4>', on_wheel, add='+')
            widget.bind('<Button-5>', on_wheel, add='+')
            for child in widget.winfo_children():
                self._bind_toolbox_wheel(child)
        except tk.TclError:
            pass

    def _toggle_toolbox_group(self, title):
        self._toolbox_group_open[title] = not self._toolbox_group_open.get(title, True)
        self._render_toolbox()

    def _render_toolbox(self):
        content = getattr(self, '_toolbox_content', None)
        if content is None or not content.winfo_exists():
            return
        for child in content.winfo_children():
            child.destroy()

        query = ''
        if not getattr(self, '_toolbox_search_placeholder', False):
            query = self._toolbox_search.get().strip().casefold()

        groups = [
            ("流程控制", ['start', 'end', 'loop', 'wait', 'sequence', 'reroute']),
            ("鼠标与键盘", ['mouse', 'keyboard']),
            ("应用与系统", ['open_app', 'cmd', 'web', 'notify']),
            ("图像与感知", ['image', 'if_img', 'if_static', 'if_sound']),
            ("变量与剪贴板", ['set_var', 'var_switch', 'clipboard']),
        ]
        aliases = {
            'start': '开始 流程入口', 'end': '结束 停止 流程出口', 'loop': '循环 重复',
            'wait': '延时 等待', 'sequence': '序列 依次尝试', 'reroute': '线路 中继 连线',
            'mouse': '鼠标 点击 拖拽 滚动', 'keyboard': '键盘 输入 按键',
            'open_app': '打开程序 启动 应用', 'cmd': '命令 cmd 终端', 'web': '网页 url 浏览器',
            'notify': '提示 通知 气泡', 'image': '找图 图片 识别', 'if_img': '图像检测 图片判断',
            'if_static': '静止 画面变化 检测', 'if_sound': '声音 音频 检测',
            'set_var': '变量 设置 数据', 'var_switch': '变量分流 判断 条件',
            'clipboard': '剪贴板 复制 粘贴',
        }
        labels = {'reroute': '● 线路中继'}
        group_count = 0
        for title, node_types in groups:
            items = [t for t in node_types if t in NODE_CONFIG and t != 'bind_win']
            if query:
                items = [t for t in items if query in (
                    NODE_CONFIG[t].get('title', '') + ' ' + NODE_CONFIG[t].get('desc', '') + ' ' + aliases.get(t, '')
                ).casefold()]
            if not items:
                continue
            group_count += 1

            is_open = self._toolbox_group_open.get(title, True)
            if query:
                is_open = True
            header = tk.Frame(content, bg=COLORS['bg_sidebar'], cursor='hand2')
            header.pack(fill='x', padx=7, pady=(6, 1))
            marker = '▾' if is_open else '▸'
            hdr = tk.Label(
                header, text=f"{marker}  {title}  ·  {len(items)}", anchor='w',
                bg=COLORS['bg_sidebar'], fg=COLORS['fg_sub'],
                font=('Microsoft YaHei UI', 8, 'bold'), padx=2, pady=3, cursor='hand2'
            )
            hdr.pack(fill='x')
            for w in (header, hdr):
                w.bind('<Button-1>', lambda _e, group=title: self._toggle_toolbox_group(group))
            self._bind_toolbox_wheel(header)

            if not is_open:
                continue
            grid = tk.Frame(content, bg=COLORS['bg_sidebar'])
            grid.pack(fill='x', padx=5, pady=(0, 3))
            grid.grid_columnconfigure(0, weight=1, uniform='toolbox_component')
            grid.grid_columnconfigure(1, weight=1, uniform='toolbox_component')
            for index, node_type in enumerate(items):
                cfg = NODE_CONFIG[node_type]
                card = tk.Frame(
                    grid, bg=COLORS['bg_card'], cursor='hand2', height=30,
                    highlightthickness=1, highlightbackground=COLORS['bg_header']
                )
                card.grid(row=index // 2, column=index % 2, sticky='ew', padx=2, pady=2)
                card.grid_propagate(False)
                stripe = tk.Frame(card, bg=cfg['color'], width=3)
                stripe.pack(side='left', fill='y')
                item_label = tk.Label(
                    card, text=labels.get(node_type, cfg['title']),
                    bg=COLORS['bg_card'], fg=COLORS['fg_text'],
                    font=('Microsoft YaHei UI', 8), anchor='w', padx=5,
                    cursor='hand2'
                )
                item_label.pack(side='left', fill='both', expand=True)
                ToolTip(item_label, f"{cfg.get('desc', '')}\n（拖拽至画布或双击直接添加）")
                for w in (card, stripe, item_label):
                    w.bind('<ButtonPress-1>', lambda e, t=node_type: self.on_drag_start(e, t))
                    w.bind('<B1-Motion>', self.on_drag_move)
                    w.bind('<ButtonRelease-1>', self.on_drag_end)
                    w.bind('<Double-Button-1>', lambda e, t=node_type: self._quick_append_from_toolbox(t))
            self._bind_toolbox_wheel(grid)

        if group_count == 0:
            tk.Label(
                content, text='没有匹配的组件', bg=COLORS['bg_sidebar'],
                fg=COLORS['fg_sub'], font=('Microsoft YaHei UI', 9), pady=16
            ).pack(fill='x')
        content.update_idletasks()
        self._toolbox_canvas.configure(scrollregion=self._toolbox_canvas.bbox('all'))

    def _quick_append_from_toolbox(self, node_type):
        if self.drag_ghost:
            self.drag_ghost.destroy()
            self.drag_ghost = None
        cx = self.editor.canvasx(self.editor.winfo_width() / 2) / self.editor.zoom
        cy = self.editor.canvasy(self.editor.winfo_height() / 2) / self.editor.zoom
        offset = (len(self.editor.nodes) % 6) * GRID_SIZE
        self.editor.add_node(
            node_type,
            round((cx - NODE_WIDTH / 2 + offset) / GRID_SIZE) * GRID_SIZE,
            round((cy - 40 + offset) / GRID_SIZE) * GRID_SIZE
        )

    def _on_combobox_mapped(self, event):
        combo = event.widget
        try:
            self.after_idle(lambda widget=combo: self._style_combobox_popup(widget))
        except tk.TclError:
            pass

    def _style_combobox_popup(self, combo):
        try:
            if not combo.winfo_exists():
                return
            popup = self.tk.call('ttk::combobox::PopdownWindow', str(combo))
            listbox = f'{popup}.f.l'
            if not int(self.tk.call('winfo', 'exists', listbox)):
                return
            self.tk.call(
                listbox, 'configure',
                '-background', COLORS['input_bg'],
                '-foreground', COLORS['input_fg'],
                '-selectbackground', COLORS['accent'],
                '-selectforeground', COLORS['accent_fg'],
                '-font', ('Microsoft YaHei UI', 9),
            )
        except (tk.TclError, TypeError, ValueError):
            pass

    def on_drag_start(self, e, t):
        self.drag_node_type = t
        if self.drag_ghost:
            self.drag_ghost.destroy()
        self.drag_ghost = tk.Toplevel(self)
        self.drag_ghost.overrideredirect(True)
        self.drag_ghost.attributes("-topmost", True, "-alpha", 0.85)
        tk.Label(
            self.drag_ghost, text=f"  {NODE_CONFIG[t]['title']}  ",
            bg=COLORS['accent'], fg=COLORS['accent_fg'],
            font=('Microsoft YaHei UI', 9, 'bold'), pady=4
        ).pack()
        self.drag_ghost.geometry(f"+{e.x_root + 12}+{e.y_root + 12}")

    def on_drag_move(self, e):
        if self.drag_ghost:
            self.drag_ghost.geometry(f"+{e.x_root + 12}+{e.y_root + 12}")

    def on_drag_end(self, e):
        if self.drag_ghost:
            self.drag_ghost.destroy()
            self.drag_ghost = None
        target_widget = self.winfo_containing(e.x_root, e.y_root)
        if target_widget is not None and (target_widget == self.editor or str(target_widget).startswith(str(self.editor) + ".")):
            lx = self.editor.canvasx(e.x_root - self.editor.winfo_rootx()) / self.editor.zoom
            ly = self.editor.canvasy(e.y_root - self.editor.winfo_rooty()) / self.editor.zoom
            self.editor.add_node(
                self.drag_node_type,
                round(lx / GRID_SIZE) * GRID_SIZE,
                round(ly / GRID_SIZE) * GRID_SIZE
            )

    def do_snip(self):
        self.iconify()
        self.update()
        self.after(350, lambda: self._start_snip_overlay())

    def _start_snip_overlay(self):
        top = tk.Toplevel(self)
        top.geometry(f"{VW}x{VH}+{VX}+{VY}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(cursor="cross", bg="black")

        c = tk.Canvas(top, bg="black", highlightthickness=0)
        c.pack(fill='both', expand=True)
        c.create_text(VW // 2, 48, text="按住鼠标左键框选目标区域  |  按 ESC 取消", fill='#FFFFFF', font=('Microsoft YaHei UI', 12, 'bold'))
        s, r = [0, 0], [None]

        def dn(e):
            s[0], s[1] = e.x, e.y
            if r[0]:
                c.delete(r[0])
            r[0] = c.create_rectangle(e.x, e.y, e.x, e.y, outline='#EF4444', width=2)
        def mv(e):
            if r[0]:
                c.coords(r[0], s[0], s[1], e.x, e.y)
        def up(e):
            x1 = min(s[0], e.x) + VX
            y1 = min(s[1], e.y) + VY
            x2 = max(s[0], e.x) + VX
            y2 = max(s[1], e.y) + VY
            top.destroy()
            self.after(180, lambda: self._capture((x1, y1, x2, y2)))

        c.bind("<ButtonPress-1>", dn)
        c.bind("<B1-Motion>", mv)
        c.bind("<ButtonRelease-1>", up)
        top.bind("<Escape>", lambda e: [top.destroy(), self.deiconify()])

    def _capture(self, rect):
        x1, y1, x2, y2 = rect
        if x2 - x1 < 5 or y2 - y1 < 5:
            self.deiconify()
            return

        try:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
            self.deiconify()

            if (n := self.property_panel.current_node):
                self.editor.history.save_state()

                if n.type == 'if_img':
                    imgs = n.data.get('images', []).copy()
                    imgs.append({'id': uuid.uuid4().hex, 'image': img, 'tk_image': ImageUtils.make_thumb(img), 'b64': ImageUtils.img_to_b64(img)})
                    n.update_data('images', imgs, refresh_ui=False)
                elif n.type == 'if_static':
                    n.update_data('roi', (x1, y1, x2 - x1, y2 - y1), refresh_ui=False)
                    n.update_data('roi_preview', img, refresh_ui=False)
                    n.update_data('b64_preview', ImageUtils.img_to_b64(img), refresh_ui=False)
                else:
                    n.update_data('image', img, refresh_ui=False)
                    n.update_data('tk_image', ImageUtils.make_thumb(img), refresh_ui=False)
                    n.update_data('b64', ImageUtils.img_to_b64(img), refresh_ui=False)

                n.draw()
                self.editor.redraw_links()
                self.property_panel.load_node(n)
            self.log(f"🖼️ 截图完成: 位置({x1}, {y1}) 尺寸({x2 - x1}×{y2 - y1})", "success")

        except Exception as e:
            self.deiconify()
            self.log(f"截图失败: {e}", "error")

    def pick_coordinate(self):
        self.iconify()
        self.after(350, lambda: self._coord_overlay('x', 'y'))

    def pick_start_coordinate(self):
        self.iconify()
        self.after(350, lambda: self._coord_overlay('start_x', 'start_y'))

    def pick_end_coordinate(self):
        self.iconify()
        self.after(350, lambda: self._coord_overlay('end_x', 'end_y'))

    def _coord_overlay(self, key_x='x', key_y='y'):
        top = tk.Toplevel(self)
        top.geometry(f"{VW}x{VH}+{VX}+{VY}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(cursor="cross", bg="black")

        c = tk.Canvas(top, bg="black", highlightthickness=0)
        c.pack(fill='both', expand=True)

        c.create_text(
            VW // 2, 50,
            text="屏幕绝对坐标拾取：点击目标位置即可记录屏幕坐标",
            fill='#FBBF24', font=('Microsoft YaHei UI', 13, 'bold'), anchor='center'
        )
        c.create_text(VW // 2, 85, text="点击鼠标左键确认拾取  |  按 ESC 取消", fill='#FFFFFF', font=('Microsoft YaHei UI', 11), anchor='center')

        def clk(e):
            top.destroy()
            self.deiconify()

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            final_x, final_y = pt.x, pt.y
            self.log(f"📍 坐标拾取完成：({final_x}, {final_y})", "success")

            if self.property_panel.current_node:
                self.editor.history.save_state()
                self.property_panel.current_node.update_data(key_x, final_x, refresh_ui=False)
                self.property_panel.current_node.update_data(key_y, final_y, refresh_ui=False)
                self.property_panel.load_node(self.property_panel.current_node)

        c.bind("<Button-1>", clk)
        top.bind("<Escape>", lambda ev: [top.destroy(), self.deiconify()])

    def export_exe(self):
        ExportWizardDialog(self, self, self.editor.get_data())

    def refresh_hotkeys(self):
        self.stop_hotkeys()
        mapping = {}
        for key, callback in (
            (SETTINGS.get('hotkey_start'), self.on_hotkey_start),
            (SETTINGS.get('hotkey_stop'), self.on_hotkey_stop),
            (SETTINGS.get('hotkey_quit'), self.on_hotkey_quit),
        ):
            if not key:
                continue
            if key in mapping:
                self.log(f"快捷键冲突：{key} 被多个操作使用，快捷键未启用", "error")
                return
            mapping[key] = callback
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(mapping)
            self.hotkey_listener.start()
        except Exception as e:
            self.hotkey_listener = None
            self.log(f"全局快捷键启动失败: {e}", "error")

    def stop_hotkeys(self):
        listener, self.hotkey_listener = self.hotkey_listener, None
        if listener:
            try:
                listener.stop()
            except Exception as e:
                self.log(f"停止全局快捷键监听失败: {e}", "warning")

    def on_hotkey_start(self):
        self.after(0, self._safe_hotkey_start)

    def _safe_hotkey_start(self):
        if not self.core.running:
            self.log("⌨️ 快捷键启动", "info")
            self.toggle_run(None)

    def on_hotkey_stop(self):
        self.after(0, self._safe_hotkey_stop)

    def _safe_hotkey_stop(self):
        if self.core.running:
            self.log("⌨️ 快捷键停止", "warning")
            if getattr(self, '_auto_run_mode', False) or getattr(self, '_hidden_run_mode', False):
                if getattr(self, '_show_export_toast', True):
                    VisualTips.show_toast("🛑 紧急停止！当前任务流程已中断。", duration=1500, use_sound=True, position='bottom_right')
            self.core.stop()

    def on_hotkey_quit(self):
        self.after(0, self._safe_hotkey_quit)

    def _safe_hotkey_quit(self):
        if getattr(self, '_show_export_toast', True):
            VisualTips.show_toast("❌ 正在完全退出程序...", duration=1000, position='bottom_right')
        self.after(1000, self.quit_app)

    def open_settings(self):
        SettingsDialog(self, self)

    def restart_ui(self):
        data = self.editor.get_data()
        old_undo = list(self.editor.history.undo_stack)
        old_redo = list(self.editor.history.redo_stack)
        was_dirty = self.is_dirty
        self._setup_ui()
        self.editor.load_data(data)
        self.editor.history.undo_stack = old_undo
        self.editor.history.redo_stack = old_redo
        self.mark_dirty(was_dirty)

    def toggle_run(self, start_id):
        self.editor.focus_set()
        if self.core.running:
            self.core.stop()
            return

        btn_run = getattr(self, 'btn_run', None)
        btn_pause = getattr(self, 'btn_pause', None)
        if btn_run is not None:
            btn_run.config(text=f"⏹ 停止 ({SETTINGS.get('hotkey_stop', '<f10>').upper()})", bg=COLORS['danger'], fg=COLORS['danger_fg'])
        if btn_pause is not None:
            btn_pause.config(state='normal', text="⏸ 暂停", bg=COLORS['warning'], fg=COLORS['warning_fg'])
        self.core.load_project(self.editor.get_data())
        if getattr(self, '_auto_run_mode', False) or getattr(self, '_hidden_run_mode', False):
            if getattr(self, '_show_export_toast', True):
                VisualTips.show_toast("▶ 自动化任务开始执行", duration=2000, position='bottom_right')
        self.core.start(start_id)

    def toggle_pause(self):
        self.core.resume() if self.core.paused else self.core.pause()

    def update_debug_btn_state(self, paused):
        button = getattr(self, 'btn_pause', None)
        if button is not None:
            button.config(
                text="▶ 继续" if paused else "⏸ 暂停",
                bg=COLORS['success'] if paused else COLORS['warning'],
                fg=COLORS['success_fg'] if paused else COLORS['warning_fg']
            )

    def reset_ui_state(self):
        if getattr(self, '_hidden_run_mode', False) or getattr(self, '_auto_run_mode', False):
            if getattr(self, '_auto_quit', True):
                if getattr(self, '_show_export_toast', True):
                    VisualTips.show_toast("🏁 任务执行完毕，即将完全退出", duration=1500, position='bottom_right')
                self.after(1500, self.quit_app)
            else:
                if getattr(self, '_show_export_toast', True):
                    VisualTips.show_toast("🏁 任务已结束，挂起后台待命", duration=1500, position='bottom_right')
                self.core.running = False
            return

        self.core.running = False
        btn_run = getattr(self, 'btn_run', None)
        btn_pause = getattr(self, 'btn_pause', None)
        if btn_run is not None:
            btn_run.config(text=f"▶ 运行 ({SETTINGS.get('hotkey_start', '<f9>').upper()})", bg=COLORS['success'], fg=COLORS['success_fg'])
        if btn_pause is not None:
            btn_pause.config(text="⏸ 暂停", bg=COLORS['bg_header'], fg=COLORS['fg_text'], state='disabled')
        for n in self.editor.nodes:
            self.highlight_node_safe(n, None)

    def log(self, msg, level='info'):
        self.log_q.put((msg, level))

    def _poll_log(self):
        for _ in range(200):
            try:
                item = self.log_q.get_nowait()
            except queue.Empty:
                break
            self.log_panel.add_log(item[0], item[1])
        self.after(100, self._poll_log)

    def highlight_node_safe(self, nid, status=None):
        def _task():
            if not self.editor.winfo_exists():
                return
            self.editor.delete("hl")
            if nid and nid in self.editor.nodes and status:
                n = self.editor.nodes[nid]
                z = self.editor.zoom
                color = COLORS.get(f"hl_{status}", COLORS['hl_ok'])
                self.editor.create_rectangle(
                    n.x * z - 3 * z, n.y * z - 3 * z,
                    (n.x + n.w) * z + 3 * z, (n.y + n.h) * z + 3 * z,
                    outline=color, width=3 * z, tags="hl"
                )
        self.after(0, _task)

    def select_node_safe(self, nid):
        self.after(0, lambda: self.editor.select_node(nid))

    def save(self):
        if self.current_file_path:
            try:
                target_path = self.current_file_path
                temp_path = target_path + ".tmp"
                try:
                    with open(temp_path, 'w', encoding='utf-8') as fp:
                        json.dump(self.editor.get_data(), fp, ensure_ascii=False, indent=2)
                    os.replace(temp_path, target_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                self.mark_dirty(False)
                self.log(f"💾 已保存到: {target_path}", "success")
                VisualTips.show_toast(f"💾 已保存：{os.path.basename(target_path)}", duration=1500, position='bottom_right')
                self.update_title()
                return True
            except Exception as e:
                self.log(f"❌ 保存失败: {e}", "error")
                messagebox.showerror("保存失败", f"无法写入文件:\n{e}", parent=self)
                return False
        else:
            return self.save_as()

    def save_as(self):
        f = filedialog.asksaveasfilename(defaultextension=".qflow", filetypes=[("Qflow 项目", "*.qflow"), ("所有文件", "*.*")])
        if not f:
            return False
        previous_path = self.current_file_path
        self.current_file_path = f
        if not self.save():
            self.current_file_path = previous_path
            self.update_title()
            return False
        return True

    def load(self):
        if not self._confirm_discard_changes("打开新项目"):
            return
        if (f := filedialog.askopenfilename(filetypes=[("Qflow 项目", "*.qflow"), ("所有文件", "*.*")])):
            try:
                with open(f, 'r', encoding='utf-8-sig') as fp:
                    project_data = json.load(fp)
                if not self.editor.load_data(project_data):
                    return
                self.editor.history.undo_stack.clear()
                self.editor.history.redo_stack.clear()
                self.current_file_path = f
                self.mark_dirty(False)
                self.update_title()
                self.after_idle(lambda: self.editor.fit_view(selected_only=False) if self.editor.winfo_exists() else None)
                self.log(f"📂 已加载: {f}", "success")
            except Exception as e:
                self.log(f"❌ 加载失败: {e}", "error")
                messagebox.showerror("加载失败", f"项目文件损坏或格式不受支持:\n{e}", parent=self)

    def clear(self):
        if self.editor.nodes and not messagebox.askyesno(
            "清空流程", "确定清空当前流程中的全部节点和连线？此操作可通过撤销 (Ctrl+Z) 恢复。", parent=self
        ):
            return False
        if self.editor.nodes or self.editor.links:
            self.editor.history.save_state()
        self.editor.load_data({'nodes': {}, 'links': []})
        self.mark_dirty(True)
        return True

    def show_welcome_guide(self):
        self.log("✨ 欢迎使用 Qflow 可视化办公自动化软件！", "success")
        self.log("💡 快捷操作指引：", "info")
        self.log("1. 【添加节点】从左侧组件库拖拽到画布，或在画布空白处 [双击 / 右键] 快速搜索添加。", "info")
        self.log("2. 【建立连线】从节点右侧端口拖出曲线连接到目标节点；右键点击端口可快速断开连线。", "info")
        self.log("3. 【画布导航】鼠标滚轮以指针为中心缩放，按住 [空格+左键] 或 [鼠标中键/右键] 平移画布。", "info")
        self.log(f"4. 【运行控制】点击顶部 [▶ 运行] 或按全局快捷键 {SETTINGS.get('hotkey_start', '<f9>').upper()} 启动 / {SETTINGS.get('hotkey_stop', '<f10>').upper()} 停止。", "success")

if __name__ == "__main__":
    file_to_load = None
    auto_run = False
    hidden_run = False

    for arg in sys.argv[1:]:
        if arg.endswith('.qflow'):
            file_to_load = arg
        elif arg == '--run':
            auto_run = True
        elif arg == '--hidden-run':
            hidden_run = True

    app = App(file_path=file_to_load, auto_run=auto_run, hidden_run=hidden_run)
    app.mainloop()
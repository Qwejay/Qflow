import os
import sys
import time
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
from PIL import Image, ImageTk, ImageGrab, ImageChops
import pyautogui
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController
import copy
from datetime import datetime
from collections import namedtuple

__app_name__   = "Qflow"
__version__    = "1.7.6"
__author__     = "QwejayHuang"
__company__    = "QwejayHuang"
__description__= "可视化节点办公自动化引擎"

# --- 1. 可选依赖库统一检查 ---
HAS_PYPERCLIP = HAS_OPENCV = HAS_AUDIO = False

try: import pyperclip; HAS_PYPERCLIP = True
except ImportError: print("⚠️ 提示: 未安装 pyperclip，键盘'粘贴模式'和剪贴板节点将不可用。")

try: import cv2; import numpy as np; HAS_OPENCV = True
except ImportError: print("⚠️ 警告: 未安装 opencv-python，高级图像识别功能受限。")

try:
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    HAS_AUDIO = True
except ImportError: print("⚠️ 提示: 未安装 pycaw 或 comtypes，声音检测节点将不可用。")

# --- 2. 系统与配置管理 ---
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05  # 全局操作间隔，提升稳定性

# Windows API 常量
user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore

def get_virtual_screen_geometry():
    """获取所有屏幕组成的虚拟桌面坐标范围 (修复多屏截图问题)"""
    try:
        return (
            user32.GetSystemMetrics(76), # SM_XVIRTUALSCREEN
            user32.GetSystemMetrics(77), # SM_YVIRTUALSCREEN
            user32.GetSystemMetrics(78), # SM_CXVIRTUALSCREEN
            user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        )
    except:
        return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

# 获取虚拟屏幕参数
VX, VY, VW, VH = get_virtual_screen_geometry()

def get_scale_factor():
    try:
        if sys.platform.startswith('win'):
            try: shcore.SetProcessDpiAwareness(1) # 使用系统级感知，避免坐标错乱
            except: user32.SetProcessDPIAware()
        log_w, log_h = pyautogui.size()
        phy_w, phy_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if log_w == 0 or phy_w == 0: return 1.0, 1.0
        return max(0.5, min(4.0, phy_w / log_w)), max(0.5, min(4.0, phy_h / log_h))
    except: return 1.0, 1.0

SCALE_X, SCALE_Y = get_scale_factor()
SCALE_FACTOR = (SCALE_X + SCALE_Y) / 2.0
Box = namedtuple('Box', 'left top width height')

def safe_float(value, default=0.0):
    try: return float(value)
    except (ValueError, TypeError): return default

def safe_int(value, default=0):
    try: return int(float(value))
    except (ValueError, TypeError): return default

# --- 主题定义 ---
THEMES = {
    'Dark': {
        'bg_app': '#202020', 'bg_sidebar': '#2B2B2B', 'bg_canvas': '#181818', 'bg_panel': '#2B2B2B',
        'bg_node': '#353535', 'bg_header': '#3c3c3c', 'bg_card': '#404040', 'fg_title': '#eeeeee',
        'fg_text': '#dcdcdc', 'fg_sub': '#aaaaaa', 'accent': '#64b5f6', 'grid': '#2a2a2a',
        'wire': '#777777', 'wire_active': '#dcdcaa', 'socket': '#cfcfcf', 'btn_bg': '#505050',
        'input_bg': '#222222'
    },
    'Light': {
        'bg_app': '#f0f0f0', 'bg_sidebar': '#e0e0e0', 'bg_canvas': '#ffffff', 'bg_panel': '#e0e0e0',
        'bg_node': '#f5f5f5', 'bg_header': '#d0d0d0', 'bg_card': '#ffffff', 'fg_title': '#333333',
        'fg_text': '#222222', 'fg_sub': '#555555', 'accent': '#1976d2', 'grid': '#eeeeee',
        'wire': '#a0a0a0', 'wire_active': '#ff9800', 'socket': '#888888', 'btn_bg': '#bbbbbb',
        'input_bg': '#ffffff'
    }
}

COLORS = THEMES['Dark'].copy()
COLORS.update({
    'success': '#4caf50', 'danger': '#ef5350', 'warning': '#ffca28', 'control': '#ab47bc',
    'sensor': '#ff7043', 'var_node': '#26c6da', 'wire_hl': '#4fc3f7', 'shadow': '#101010',
    'hover': '#505050', 'select_box': '#4fc3f7', 'active_border': '#4fc3f7', 'marker': '#f44747',
    'btn_hover': '#606060', 'hl_running': '#ffeb3b', 'hl_ok': '#4caf50', 'hl_fail': '#f44747',
    'breakpoint': '#e53935', 'log_bg': '#1e1e1e', 'log_fg': '#d4d4d4', 'win_node': '#009688'
})

# 提升全局字体清晰度，增加字号，统一使用微软雅黑
FONTS = {
    'node_title': ('Microsoft YaHei', int(10 * SCALE_FACTOR), 'bold'), 
    'node_text': ('Microsoft YaHei', int(9 * SCALE_FACTOR)),
    'code': ('Consolas', int(10 * SCALE_FACTOR)), 
    'small': ('Microsoft YaHei', int(9 * SCALE_FACTOR)),
    'log': ('Consolas', int(10 * SCALE_FACTOR))
}

SETTINGS = {
    'hotkey_start': '<f9>',
    'hotkey_stop': '<f10>',
    'theme': 'Dark'
}

LOG_LEVELS = {
    'info': {'color': '#64b5f6'},      # 蓝色：普通引导
    'success': {'color': '#81c784'},   # 绿色：重要操作
    'warning': {'color': '#ffd54f'},   # 黄色：提示建议
    'error': {'color': '#e57373'},     # 红色：错误
    'exec': {'color': '#666666'},      # 灰色：装饰线
    'paused': {'color': '#fff176'}     # 亮黄：暂停
}
NODE_WIDTH = int(200 * SCALE_FACTOR)
HEADER_HEIGHT = int(28 * SCALE_FACTOR)
PORT_START_Y = int(45 * SCALE_FACTOR)
PORT_STEP_Y = int(24 * SCALE_FACTOR)
GRID_SIZE = int(20 * SCALE_FACTOR)

NODE_CONFIG = {
    'start':    {'title': '▶ 开始', 'outputs': ['out'], 'color': '#2e7d32', 'desc': '流程的起点'},
    'end':      {'title': '⏹️ 结束', 'outputs': [], 'color': '#c62828', 'desc': '强制停止流程'},
    'open_app': {'title': '🚀 打开程序', 'outputs': ['out', 'fail'], 'color': '#e65100', 'desc': '运行指定的可执行文件'},
    'bind_win': {'title': '⚓ 绑定窗口', 'outputs': ['success', 'fail'], 'color': '#00695c', 'desc': '锁定特定窗口，后续坐标基于此窗口'},
    'loop':     {'title': '🔄 循环', 'outputs': ['loop', 'exit'], 'color': '#7b1fa2', 'desc': '重复执行指定次数或无限循环'},
    'wait':     {'title': '⏳ 延时', 'outputs': ['out'], 'color': '#4527a0', 'desc': '等待指定时间'},
    'mouse':    {'title': '👆 鼠标', 'outputs': ['out'], 'color': '#1565c0', 'desc': '点击、移动、拖拽或滚动'},
    'keyboard': {'title': '⌨️ 键盘', 'outputs': ['out'], 'color': '#1565c0', 'desc': '输入文本或按下组合键'},
    'clipboard':{'title': '📋 剪贴板', 'outputs': ['out'], 'color': '#00838f', 'desc': '读取或写入系统剪贴板内容'},
    'notify':   {'title': '🔔 提示', 'outputs': ['out'], 'color': '#fdd835', 'desc': '显示屏幕通知气泡'},
    'cmd':      {'title': '💻 命令', 'outputs': ['out'], 'color': '#1565c0', 'desc': '执行系统CMD命令'},
    'web':      {'title': '🔗 网页', 'outputs': ['out'], 'color': '#0277bd', 'desc': '打开指定的URL'},
    'image':    {'title': '🎯 找图', 'outputs': ['found', 'timeout'], 'color': '#ef6c00', 'desc': '在屏幕上查找图片并操作'},
    'if_img':   {'title': '🔍 检测', 'outputs': ['yes', 'no'], 'color': '#ef6c00', 'desc': '检测屏幕是否包含指定图像'},
    'if_static':{'title': '⏸️ 静止', 'outputs': ['yes', 'no'], 'color': '#d84315', 'desc': '检测画面是否保持静止'},
    'if_sound': {'title': '🔊 声音', 'outputs': ['yes', 'no'], 'color': '#d84315', 'desc': '检测是否有声音输出'},
    'set_var':  {'title': '[x] 变量', 'outputs': ['out'], 'color': '#00838f', 'desc': '设置或修改内存变量'},
    'var_switch':{'title': '⎇ 分流', 'outputs': ['else'], 'color': '#00838f', 'desc': '根据变量值选择不同路径'},
    'sequence': {'title': '🔀 序列', 'outputs': ['else'], 'color': '#7b1fa2', 'desc': '按顺序尝试多条路径'},
    'reroute':  {'title': '●', 'outputs': ['out'], 'color': '#777777', 'desc': '线路中继点'}
}

PORT_TRANSLATION = {'out': '继续', 'yes': '是', 'no': '否', 'found': '找到', 'timeout': '超时', 'loop': '循环', 'exit': '退出', 'else': '否则', 'success': '成功', 'fail': '失败'}
MOUSE_ACTIONS = {'click': '点击', 'move': '移动', 'drag': '拖拽', 'scroll': '滚动', 'double_click': '双击'}
MOUSE_BUTTONS = {'left': '左键', 'right': '右键', 'middle': '中键'}
ACTION_MAP = {'click': '单击左键', 'double_click': '双击左键', 'right_click': '单击右键', 'none': '不执行操作'}
MATCH_STRATEGY_MAP = {'hybrid': '智能混合', 'template': '模板匹配', 'feature': '特征匹配'}

# --- 3. 基础工具类 ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert") if self.widget.bbox("insert") else (0,0,0,0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Microsoft YaHei", "9", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class KeyboardEngine:
    _controller = KeyboardController()
    
    @staticmethod
    def safe_write(text, mode='direct'):
        """mode: direct(按键模拟), paste(剪贴板粘贴)"""
        if mode == 'paste' and HAS_PYPERCLIP:
            try:
                old_clip = pyperclip.paste()
                pyperclip.copy(text)
                time.sleep(0.05)
                with KeyboardEngine._controller.pressed(keyboard.Key.ctrl):
                    KeyboardEngine._controller.press('v')
                    KeyboardEngine._controller.release('v')
                time.sleep(0.1)
                pyperclip.copy(old_clip)
            except Exception as e:
                print(f"粘贴模式失败，回退到普通输入: {e}")
                pyautogui.write(text)
        else:
            for char in text:
                try:
                    KeyboardEngine._controller.type(char)
                except:
                    pyautogui.write(char) # 回退
                time.sleep(0.005)

class VisualTips:
    """视觉提示小窗"""
    @staticmethod
    def show_toast(message, duration=2000, use_sound=False):
        try:
            top = tk.Toplevel()
            top.overrideredirect(True)
            top.attributes("-topmost", True, "-alpha", 0.9)
            top.configure(bg="#333333")
            
            lbl = tk.Label(top, text=message, fg="white", bg="#333333", padx=20, pady=10, font=("Microsoft YaHei", 12, "bold"))
            lbl.pack()
            
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
            top.geometry(f"+{sw//2 - 100}+{sh//2 - 50}")
            
            if use_sound:
                threading.Thread(target=lambda: ctypes.windll.kernel32.Beep(800, 300), daemon=True).start()
            
            top.after(duration, top.destroy)
        except: pass

class WindowEngine:
    TH32CS_SNAPPROCESS = 0x00000002
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_ulong), ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260)]

    @staticmethod
    def _get_process_map():
        pid_map = {}
        hSnap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(WindowEngine.TH32CS_SNAPPROCESS, 0)
        if hSnap == -1: return pid_map
        try:
            pe32 = WindowEngine.PROCESSENTRY32()
            pe32.dwSize = ctypes.sizeof(WindowEngine.PROCESSENTRY32)
            if ctypes.windll.kernel32.Process32First(hSnap, ctypes.byref(pe32)):
                while True:
                    try: exe_name = pe32.szExeFile.decode('gbk', 'ignore')
                    except: exe_name = pe32.szExeFile.decode('utf-8', 'ignore')
                    pid_map[pe32.th32ProcessID] = exe_name
                    if not ctypes.windll.kernel32.Process32Next(hSnap, ctypes.byref(pe32)): break
        finally:
            # 确保即使遇到解码异常，句柄也一定会被释放
            ctypes.windll.kernel32.CloseHandle(hSnap)
        return pid_map

    @staticmethod
    def get_window_info(hwnd, pid_map=None):
        if not hwnd: return None
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
        except: pass
        rect = ctypes.wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return Box(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        return None

    @staticmethod
    def is_window_valid_target(hwnd, my_pid):
        if not user32.IsWindowVisible(hwnd): return False
        if user32.IsIconic(hwnd): return False
        if user32.GetWindow(hwnd, 4) != 0: return False
        is_cloaked = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(is_cloaked), ctypes.sizeof(is_cloaked))
        if is_cloaked.value != 0: return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == my_pid: return False
        cls_buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buff, 256)
        cls_name = cls_buff.value
        if cls_name in ['Progman', 'Shell_TrayWnd', 'Button', 'Static', 'WorkerW', 'Windows.UI.Core.CoreWindow', 'EdgeUiInputTopWnd', 'ApplicationFrameWindow']: return False
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w < 10 or h < 10: return False 
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0 and cls_name == 'ApplicationFrameWindow': return False
        return True

    @staticmethod
    def get_all_windows():
        results = []
        pid_map = WindowEngine._get_process_map()
        my_pid = os.getpid()
        def callback(hwnd, extra):
            if WindowEngine.is_window_valid_target(hwnd, my_pid):
                info = WindowEngine.get_window_info(hwnd, pid_map)
                if info:
                    info['rect'] = WindowEngine.get_window_rect(hwnd)
                    if info['rect']: results.append(info)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return results

    @staticmethod
    def get_top_window_at_mouse():
        class POINT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        windows = WindowEngine.get_all_windows()
        for win in windows:
            r = win['rect']
            if r.left <= pt.x < (r.left + r.width) and r.top <= pt.y < (r.top + r.height):
                return win
        return None

    @staticmethod
    def smart_find_window(target_exe=None, target_class=None, target_title=None):
        pid_map = WindowEngine._get_process_map()
        found_hwnd = 0
        my_pid = os.getpid()
        def callback(hwnd, extra):
            nonlocal found_hwnd
            if not WindowEngine.is_window_valid_target(hwnd, my_pid): return True
            info = WindowEngine.get_window_info(hwnd, pid_map)
            match = True
            if target_exe and target_exe.lower() != info['exe_name'].lower(): match = False
            if match and target_class and target_class.lower() != info['class_name'].lower(): match = False
            if match and target_title and target_title.lower() not in info['title'].lower(): match = False
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
            if user32.IsIconic(hwnd): user32.ShowWindow(hwnd, 9) 
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            user32.AttachThreadInput(current_thread, target_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(current_thread, target_thread, False)
            return True
        except: return False
        
class ImageUtils:
    @staticmethod
    def img_to_b64(image):
        try: buffered = io.BytesIO(); image.save(buffered, format="PNG"); return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except: return None
    
    @staticmethod
    def b64_to_img(b64_str):
        if not b64_str or not isinstance(b64_str, str): return None
        try:
            missing_padding = len(b64_str) % 4
            if missing_padding: b64_str += '=' * (4 - missing_padding)
            return Image.open(io.BytesIO(base64.b64decode(b64_str)))
        except Exception: return None
    
    @staticmethod
    def make_thumb(image, size=(240, 135)):
        if not image: return None
        try: thumb = image.copy(); thumb.thumbnail(size); return ImageTk.PhotoImage(thumb)
        except: return None

class AudioEngine:
    @staticmethod
    def get_max_audio_peak():
        if not HAS_AUDIO: return 0.0
        try:
            try: comtypes.CoInitialize()
            except: pass
            sessions = AudioUtilities.GetAllSessions()
            max_peak = 0.0
            for session in sessions:
                if session.State == 1: 
                    meter = session._ctl.QueryInterface(IAudioMeterInformation)
                    peak = meter.GetPeakValue()
                    if peak > max_peak: max_peak = peak
            return max_peak
        except Exception: return 0.0

class VisionEngine:
    @staticmethod
    def capture_screen(bbox=None):
        try: return ImageGrab.grab(bbox=bbox, all_screens=True)
        except OSError: return None

    @staticmethod
    def locate(needle, confidence=0.8, timeout=0, stop_event=None, grayscale=True, multiscale=True, scaling_ratio=1.0, strategy='hybrid', region=None):
        start_time = time.time()
        while True:
            if stop_event and stop_event.is_set(): return None
            
            capture_bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3]) if region else None
            haystack = VisionEngine.capture_screen(bbox=capture_bbox)
            
            if haystack is None:
                time.sleep(0.5) 
                if timeout <= 0 or (time.time()-start_time >= timeout): break
                continue
            
            try:
                result, _ = VisionEngine._advanced_match(needle, haystack, confidence, stop_event, grayscale, multiscale, scaling_ratio, strategy)
                if result:
                    offset_x = region[0] if region else 0
                    offset_y = region[1] if region else 0
                    return Box(result.left + offset_x, result.top + offset_y, result.width, result.height)
            except Exception: pass
            
            if timeout <= 0 or (time.time()-start_time >= timeout): break
            time.sleep(0.1)
        return None

    @staticmethod
    def _advanced_match(needle, haystack, confidence, stop_event, grayscale, multiscale, scaling_ratio, strategy):
        if not needle or not haystack: return None, 0.0
        if needle.width > haystack.width or needle.height > haystack.height: return None, 0.0
        if HAS_OPENCV:
            try:
                if grayscale: 
                    nA = cv2.cvtColor(np.array(needle), cv2.COLOR_RGB2GRAY)
                    hA = cv2.cvtColor(np.array(haystack), cv2.COLOR_RGB2GRAY)
                else: 
                    nA = cv2.cvtColor(np.array(needle), cv2.COLOR_RGB2BGR)
                    hA = cv2.cvtColor(np.array(haystack), cv2.COLOR_RGB2BGR)
                
                if strategy == 'feature': 
                    return VisionEngine._feature_match_akaze(nA, hA)
                
                nH, nW = nA.shape[:2]; hH, hW = hA.shape[:2]; scales = [1.0]
                if multiscale: scales = np.unique(np.append(np.linspace(scaling_ratio * 0.8, scaling_ratio * 1.2, 10), [1.0, scaling_ratio]))
                best_max, best_rect = -1, None
                for s in scales:
                    if stop_event and stop_event.is_set(): return None, 0.0
                    tW, tH = int(nW * s), int(nH * s)
                    if tW < 5 or tH < 5 or tW > hW or tH > hH: continue
                    res = cv2.matchTemplate(hA, cv2.resize(nA, (tW, tH), interpolation=cv2.INTER_AREA), cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val > best_max: best_max, best_rect = max_val, Box(max_loc[0], max_loc[1], tW, tH)
                    if best_max > 0.99: break
                if best_rect and best_max >= confidence: return best_rect, best_max
            except Exception: pass
        try:
            res = pyautogui.locate(needle, haystack, confidence=confidence, grayscale=grayscale)
            if res: return Box(res.left, res.top, res.width, res.height), 1.0
        except: pass
        return None, 0.0

    @staticmethod
    def _feature_match_akaze(template, target, min_match_count=4):
        try:
            akaze = cv2.AKAZE_create()
            kp1, des1 = akaze.detectAndCompute(template, None); kp2, des2 = akaze.detectAndCompute(target, None)
            if des1 is None or des2 is None: return None, 0.0
            matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des1, des2, k=2)
            good = [m for m, n in matches if m.distance < 0.75 * n.distance]
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
                    return Box(max(0, int(x_min)), max(0, int(y_min)), int(x_max - x_min), int(y_max - y_min)), min(1.0, len(good)/len(kp1)*2.5)
            return None, 0.0
        except: return None, 0.0
    
    @staticmethod
    def compare_images(img1, img2, threshold=0.99):
        if not img1 or not img2: return False
        try:
            if img1.size != img2.size: img2 = img2.resize(img1.size, Image.LANCZOS)
            diff = ImageChops.difference(img1.convert('L'), img2.convert('L'))
            return (1.0 - (sum(diff.histogram()[10:]) / (img1.size[0] * img1.size[1]))) >= threshold
        except: return False

# --- 4. 日志与核心 ---
class LogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_panel'], **kwargs)
        self.toolbar = tk.Frame(self, bg=COLORS['bg_header'], height=28)
        self.toolbar.pack_propagate(False); self.toolbar.pack(fill='x')
        tk.Label(self.toolbar, text="📋 执行日志", bg=COLORS['bg_header'], fg='white', font=FONTS['node_title']).pack(side='left', padx=10)
        tk.Button(self.toolbar, text="🗑️", command=self.clear, bg=COLORS['bg_header'], fg=COLORS['danger'], bd=0).pack(side='right', padx=5)
        
        self.text_frame = tk.Frame(self, bg=COLORS['log_bg'])
        self.scrollbar = ttk.Scrollbar(self.text_frame)
        self.text_area = tk.Text(self.text_frame, bg=COLORS['log_bg'], fg=COLORS['log_fg'], font=FONTS['log'], state='disabled', yscrollcommand=self.scrollbar.set, bd=0, padx=5, pady=5)
        self.scrollbar.config(command=self.text_area.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.text_area.pack(side='left', fill='both', expand=True)
        for level, style in LOG_LEVELS.items(): self.text_area.tag_config(level, foreground=style['color'])
        
        self.text_frame.pack(fill='both', expand=True)

    def add_log(self, msg, level='info'):
        if not self.winfo_exists(): return
        self.text_area.config(state='normal')
        self.text_area.insert('end', f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n", level)
        self.text_area.see('end'); self.text_area.config(state='disabled')
        
    def clear(self): 
        self.text_area.config(state='normal'); self.text_area.delete(1.0, 'end'); self.text_area.config(state='disabled')

class AutomationCore:
    def __init__(self, log_callback, app_instance):
        self.running = False; self.paused = False; self.stop_event = threading.Event(); self.pause_event = threading.Event()
        self.log = log_callback; self.app = app_instance; self.project = None; self.runtime_memory = {}; self.io_lock = threading.Lock()
        self.active_threads = 0; self.thread_lock = threading.Lock(); self.scaling_ratio = 1.0; self.breakpoints = set()
        self.max_threads = 50 
        self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
        self.performance_stats = {'nodes_executed': 0, 'errors': 0, 'start_time': None}

    def load_project(self, project_data):
        self.project = project_data; self.scaling_ratio = 1.0; self.breakpoints = set(project_data.get('breakpoints', []))
        dev_scale = self.project.get('metadata', {}).get('dev_scale_x', 1.0); runtime_scale_x, _ = get_scale_factor()
        if dev_scale > 0.1 and runtime_scale_x > 0.1: self.scaling_ratio = runtime_scale_x / dev_scale
        if self.project and 'nodes' in self.project:
            for nid, node in self.project['nodes'].items():
                data = node.get('data', {})
                try:
                    if 'b64' in data and 'image' not in data and (img := ImageUtils.b64_to_img(data['b64'])): self.project['nodes'][nid]['data']['image'] = img
                    if 'anchors' in data:
                        for anchor in data['anchors']:
                            if 'b64' in anchor and 'image' not in anchor and (img := ImageUtils.b64_to_img(anchor['b64'])): anchor['image'] = img
                    if 'images' in data:
                        for img_item in data['images']:
                            if 'b64' in img_item and 'image' not in img_item and (img := ImageUtils.b64_to_img(img_item['b64'])): img_item['image'] = img
                    if 'b64_preview' in data and (img:=ImageUtils.b64_to_img(data['b64_preview'])): self.project['nodes'][nid]['data']['roi_preview'] = img
                except Exception: pass

    def start(self, start_node_id=None):
        if self.running or not self.project: return
        self.running = True; self.paused = False; self.stop_event.clear(); self.pause_event.set()
        self.runtime_memory = {}; self.active_threads = 0
        self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
        self.performance_stats = {'nodes_executed': 0, 'errors': 0, 'start_time': time.time()}
        self.log("🚀 引擎启动", "exec"); self.app.iconify()
        threading.Thread(target=self._run_flow_engine, args=(start_node_id,), daemon=True).start()

    def stop(self):
        if not self.running: return
        self.stop_event.set(); self.pause_event.set(); self.log("🛑 正在停止...", "warning")
        self.app.after(0, self.app.reset_ui_state)

    def pause(self): 
        self.paused = True; self.pause_event.clear(); self.log("⏸️ 流程暂停", "paused")
        self.app.after(0, lambda: self.app.update_debug_btn_state(True))
        
    def resume(self): 
        self.paused = False; self.pause_event.set(); self.log("▶️ 流程继续", "info")
        self.app.after(0, lambda: self.app.update_debug_btn_state(False))
    
    def _smart_wait(self, seconds):
        append_time = time.time() + seconds
        while time.time() < append_time:
            if self.stop_event.is_set(): return False
            self._check_pause(); time.sleep(0.05)
        return True
    
    def _check_pause(self, node_id=None):
        if node_id and node_id in self.breakpoints:
            if not self.paused: self.log(f"🔴 命中断点: {node_id}", "paused"); self.pause(); self.app.after(0, self.app.deiconify)
        if not self.pause_event.is_set(): self.pause_event.wait()
    
    def _get_next_links(self, node_id, port_name='out'): return [l['target'] for l in self.project['links'] if l['source'] == node_id and l.get('source_port') == port_name]
    
    def _run_flow_engine(self, start_node_id=None):
        try:
            start_nodes = [start_node_id] if start_node_id else [nid for nid, n in self.project['nodes'].items() if n['type'] == 'start']
            if not start_nodes: self.log("未找到开始节点", "error"); return
            for start_id in start_nodes: self._fork_node(start_id)
            while not self.stop_event.is_set():
                with self.thread_lock: 
                    if self.active_threads <= 0: break
                time.sleep(0.5)
        except Exception as e: traceback.print_exc(); self.log(f"引擎异常: {str(e)}", "error")
        finally:
            self.running = False
            if self.performance_stats['start_time']:
                elapsed = time.time() - self.performance_stats['start_time']
                self.log(f"📊 执行统计: {self.performance_stats['nodes_executed']}个节点, {self.performance_stats['errors']}个错误, 耗时{elapsed:.2f}秒", "info")
            self.log("🏁 流程结束", "info"); 
            self.app.highlight_node_safe(None); 
            self.app.after(0, self.app.deiconify); 
            self.app.after(100, self.app.reset_ui_state)

    def _fork_node(self, node_id):
        with self.thread_lock:
            if node_id not in self.project['nodes']: return
            if self.active_threads >= self.max_threads: return
            self.active_threads += 1
        threading.Thread(target=self._process_node_thread, args=(node_id,), daemon=True).start()

    def _process_node_thread(self, node_id):
        try:
            if self.stop_event.is_set(): return
            if not (node := self.project['nodes'].get(node_id)): return
            self._check_pause(node_id)
            if self.stop_event.is_set(): return
            self.app.highlight_node_safe(node_id, 'running'); self.app.select_node_safe(node_id)
            try: 
                out_port = self._execute_node(node)
                self.performance_stats['nodes_executed'] += 1
            except Exception as e: 
                self.log(f"💥 节点[{node_id}]错误: {e}", "error"); 
                traceback.print_exc(); 
                self.performance_stats['errors'] += 1
                out_port = 'fail'
            if out_port == '__STOP__' or self.stop_event.is_set(): return
            
            if node['type'] != 'reroute':
                self.log(f"↳ [{node.get('data',{}).get('_user_title','Node')}] -> {PORT_TRANSLATION.get(out_port, out_port)}", "exec")
            
            self.app.highlight_node_safe(node_id, 'fail' if out_port in ['timeout', 'no', 'exit', 'else', 'fail'] else 'ok')
            time.sleep(0.01)
            for next_id in self._get_next_links(node_id, out_port):
                if self.stop_event.is_set(): break
                self._fork_node(next_id)
        finally:
            with self.thread_lock: self.active_threads -= 1

    def _replace_variables(self, text):
        if not isinstance(text, str): return str(text)
        try:
            # 改进：同时兼容 {变量名}、${变量名} 和 简写 $变量名 替换模式
            for k, v in self.runtime_memory.items(): 
                val_str = str(v) if v is not None else ""
                text = text.replace(f'${{{k}}}', val_str)
                text = text.replace(f'${k}', val_str)
                text = text.replace(f'{{{k}}}', val_str)
        except Exception: pass
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
            except Exception as e:
                self.context = {'window_rect': None, 'window_handle': 0, 'window_offset': (0, 0)}
    
    def _ensure_window_focus(self):
        """强制聚焦绑定的窗口，确保操作不偏移"""
        if self.context['window_handle']:
            try:
                WindowEngine.focus_window(self.context['window_handle'])
                self._update_context_rect()
                time.sleep(0.05) 
            except: pass

    def _execute_node(self, node):
        if self.stop_event.is_set(): return '__STOP__'
        ntype = node['type']
        
        # 兼容性动态求值（当字符串包含 '$' 或 '{' 符号时，说明可能包含对应规则的变量占位符，触发翻译解析）
        data = {k: (self._replace_variables(v) if isinstance(v, str) and ('$' in v or '{' in v) else v) for k, v in node.get('data', {}).items()}
        
        # 窗口上下文维护
        if self.context['window_handle']: 
            self._update_context_rect()
        
        win_offset_x, win_offset_y = self.context['window_offset']
        win_region = self.context['window_rect'] 

        if ntype == 'reroute': return 'out'
        if ntype == 'start': return 'out'
        if ntype == 'end': self.stop_event.set(); return '__STOP__'
        if ntype == 'wait': return 'out' if self._smart_wait(safe_float(data.get('seconds', 1.0))) else '__STOP__'
        
        if ntype == 'notify':
            msg = data.get('msg', '执行到此节点')
            
            # 支持动态显示全部变量的特殊语法（兼容花括号和美元花括号）
            if "{ALL_VARS}" in msg.upper() or "{所有变量}" in msg or "${ALL_VARS}" in msg.upper() or "${所有变量}" in msg:
                vars_list_str = "\n".join([f"• {k} = {v}" for k, v in self.runtime_memory.items()]) if self.runtime_memory else "（目前无任何内存变量）"
                msg = msg.replace("${ALL_VARS}", vars_list_str).replace("${all_vars}", vars_list_str).replace("${所有变量}", vars_list_str).replace("{ALL_VARS}", vars_list_str).replace("{all_vars}", vars_list_str).replace("{所有变量}", vars_list_str)
                
            use_sound = bool(data.get('use_sound', False))
            duration = safe_int(safe_float(data.get('duration', 2.0)) * 1000)
            self.app.after(0, lambda: VisualTips.show_toast(msg, duration, use_sound))
            self.log(f"🔔 提示内容: {msg}", "info")
            return 'out'

        if ntype == 'open_app':
            path = data.get('path', '')
            args = data.get('args', '')
            try:
                cmd_line = f'"{path}" {args}' if args else f'"{path}"'
                cwd = os.path.dirname(path)
                if not cwd or not os.path.exists(cwd): 
                    cwd = None
                subprocess.Popen(cmd_line, shell=True, cwd=cwd)
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
                focus_success = WindowEngine.focus_window(hwnd)
                rect = WindowEngine.get_window_rect(hwnd)
                self.context['window_handle'] = hwnd
                self.context['window_rect'] = rect
                self.context['window_offset'] = (rect.left, rect.top) if rect else (0, 0)
                log_msg = f"⚓ 已绑定: {exe_name or title or '窗口'}"
                self.log(log_msg, "success")
                return 'success'
            else:
                self.log(f"❌ 未找到窗口 (Exe:{target_exe}, Class:{target_class}, Title:{target_title})", "warning")
                return 'fail'

        if ntype == 'set_var':
            if 'batch_vars' in data: [self.runtime_memory.update({i['name']:i['value']}) for i in data['batch_vars'] if i.get('name')]
            if data.get('var_name'): self.runtime_memory[data['var_name']] = data.get('var_value', '')
            return 'out'

        if ntype == 'clipboard':
            mode = data.get('clip_mode', 'read')
            if mode == 'read':
                if HAS_PYPERCLIP:
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
            val = str(self.runtime_memory.get(data.get('var_name',''), ''))
            op, target = data.get('operator', '='), data.get('var_value', '')
            if data.get('var_name'): return 'yes' if ((val==target) if op=='=' else (val!=target)) else 'no'
            vals = [str(self.runtime_memory.get(vn.strip(), '')) for vn in data.get('var_list', '').split(',') if vn.strip()]
            for case in data.get('cases', []):
                if all(v == case.get('value', '') for v in vals): return case.get('id', 'else')
            return 'else'
        
        if ntype == 'sequence':
            for i in range(1, safe_int(data.get('num_steps', 3)) + 1):
                if self.stop_event.is_set(): return '__STOP__'
                target_id = (self._get_next_links(node['id'], str(i)) or [None])[0]
                if not target_id: continue
        
                res_port = self._execute_node(self.project['nodes'][target_id])
                if res_port in ['yes', 'found', 'out', 'loop', 'success']:
                    next_nodes = self._get_next_links(target_id, res_port)
                    for nid in next_nodes: self._fork_node(nid)
                    return '__STOP__' 
            return 'else'
        
        if ntype == 'if_sound':
            if not HAS_AUDIO: return 'no'
            start_t = time.time()
            threshold = safe_float(data.get('threshold', 0.02))
            timeout = safe_float(data.get('timeout', 10.0))
            mode = data.get('detect_mode', 'has_sound')
            found = False
            while time.time() - start_t < timeout:
                if self.stop_event.is_set(): return '__STOP__'
                peak = AudioEngine.get_max_audio_peak()
                if mode == 'has_sound':
                    if peak > threshold: found = True; break
                else: 
                    if peak < threshold: found = True; break
                time.sleep(0.1)
            return 'yes' if found else 'no'

        if ntype == 'if_static':
            self._ensure_window_focus()
            roi = data.get('roi') 
            if not roi: return 'no'
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
            start_check = time.time(); static_start = time.time()
            last_frame = VisionEngine.capture_screen(bbox=target_bbox)
            while time.time() - start_check < timeout:
                if self.stop_event.is_set(): return '__STOP__'
                
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
                    if time.time() - static_start >= duration: return 'yes'
                else:
                    static_start = time.time(); last_frame = curr_frame
                time.sleep(0.2)
            return 'no'

        if ntype == 'image':
            self._ensure_window_focus()
            conf, timeout_val = safe_float(data.get('confidence', 0.9)), max(0.5, safe_float(data.get('timeout', 10.0)))
            search_region = win_region if win_region else None
            if (anchors := data.get('anchors', [])):
                primary_res = None
                for i, anchor in enumerate(anchors):
                    if self.stop_event.is_set(): return '__STOP__'
                    res = VisionEngine.locate(anchor['image'], confidence=conf, timeout=(timeout_val if i==0 else 2.0), stop_event=self.stop_event, strategy=data.get('match_strategy','hybrid'), region=search_region)
                    if not res: return 'timeout'
                    if i == 0: primary_res = res
                if primary_res:
                    off_x, off_y = safe_int(data.get('target_rect_x',0))-anchors[0].get('rect_y',0), safe_int(data.get('target_rect_y',0))-anchors[0].get('rect_y',0)
                    search_region = (max(0, int(primary_res.left+off_x)-15), max(0, int(primary_res.top+off_y)-15), safe_int(data.get('target_rect_w',100))+30, safe_int(data.get('target_rect_h',100))+30)

            start_time = time.time()
            auto_scroll = bool(data.get('auto_scroll', False))
            
            while True:
                if self.stop_event.is_set(): return '__STOP__'
                self._check_pause()
                res = VisionEngine.locate(data.get('image'), confidence=conf, timeout=0, stop_event=self.stop_event, region=search_region, strategy=data.get('match_strategy','hybrid'))
                if res:
                    with self.io_lock:
                        if (act := data.get('click_type', 'click')) != 'none':
                            rx, ry = data.get('relative_click_pos', (0.5, 0.5))
                            tx = res.left + (res.width * rx) + safe_int(data.get('offset_x', 0))
                            ty = res.top + (res.height * ry) + safe_int(data.get('offset_y', 0))
                            pyautogui.moveTo(tx, ty)
                            getattr(pyautogui, {'click':'click','double_click':'doubleClick','right_click':'rightClick'}.get(act, 'click'))()
                    return 'found'
                
                if time.time() - start_time > timeout_val:
                    break
                
                if auto_scroll:
                     with self.io_lock: 
                         if win_region:
                            cx = win_region[0] + win_region[2] // 2
                            cy = win_region[1] + win_region[3] // 2
                            pyautogui.moveTo(cx, cy)
                         pyautogui.scroll(safe_int(data.get('scroll_amount', -500)))
                     time.sleep(0.5)

                time.sleep(0.2)
            return 'timeout'

        if ntype == 'mouse':
            self._ensure_window_focus()
            with self.io_lock:
                action = data.get('mouse_action', 'click')
                dur = safe_float(data.get('duration', 0.5))
                coord_mode = data.get('coord_mode', 'relative')
                
                if action == 'drag':
                    start_x = safe_int(data.get('start_x', 0)) 
                    start_y = safe_int(data.get('start_y', 0))
                    end_x = safe_int(data.get('end_x', 0))
                    end_y = safe_int(data.get('end_y', 0))
                    
                    if coord_mode == 'relative' and self.context['window_handle']:
                        start_x_screen = start_x + win_offset_x
                        start_y_screen = start_y + win_offset_y
                        end_x_screen = end_x + win_offset_x
                        end_y_screen = end_y + win_offset_y
                    else:
                        start_x_screen = start_x
                        start_y_screen = start_y
                        end_x_screen = end_x
                        end_y_screen = end_y
                    
                    pyautogui.moveTo(start_x_screen, start_y_screen, duration=0.1)
                    pyautogui.dragTo(end_x_screen, end_y_screen, button='left', duration=dur)
                
                elif action == 'scroll':
                     pyautogui.scroll(safe_int(data.get('scroll_amount', -500)))

                else:
                    raw_x, raw_y = safe_int(data.get('x',0)), safe_int(data.get('y',0))
                    if coord_mode == 'relative' and self.context['window_handle']:
                        target_x = raw_x + win_offset_x
                        target_y = raw_y + win_offset_y
                    else:
                        target_x = raw_x
                        target_y = raw_y
                    
                    if action == 'click': 
                        pyautogui.click(x=target_x, y=target_y, clicks=safe_int(data.get('click_count', 1)), button=data.get('mouse_button', 'left'), duration=dur, interval=0.1)
                    elif action == 'double_click':
                        pyautogui.doubleClick(x=target_x, y=target_y, duration=dur, interval=0.1)
                    elif action == 'move': 
                        pyautogui.moveTo(target_x, target_y, duration=dur)
            return 'out'
        
        if ntype == 'keyboard':
            with self.io_lock:
                if data.get('kb_mode', 'text') == 'text': 
                    pyautogui.write(data.get('text',''))
                    if data.get('press_enter', False): 
                        pyautogui.press('enter')
                else: 
                    from pynput.keyboard import Controller, Key
                    kb = Controller()
                    keys = [x.strip().lower() for x in data.get('key_name', 'enter').split('+')]
            
                    # 按下所有修饰键
                    modifiers = []
                    main_key = None
                    for k in keys:
                        if k in ['alt', 'ctrl', 'shift', 'win']:
                            modifiers.append(k)
                        else:
                            main_key = k
            
                    # 按下修饰键
                    for m in modifiers:
                        if m == 'alt': kb.press(Key.alt)
                        elif m == 'ctrl': kb.press(Key.ctrl)
                        elif m == 'shift': kb.press(Key.shift)
                        elif m == 'win': kb.press(Key.cmd)
            
                    # 按下主键
                    if main_key == 'left': kb.press(Key.left)
                    elif main_key == 'right': kb.press(Key.right)
                    elif main_key == 'up': kb.press(Key.up)
                    elif main_key == 'down': kb.press(Key.down)
                    elif main_key == 'enter': kb.press(Key.enter)
                    elif main_key == 'space': kb.press(Key.space)
                    elif main_key == 'tab': kb.press(Key.tab)
                    elif main_key == 'escape': kb.press(Key.esc)
                    else: kb.press(main_key)
            
                    # 释放（先释放主键，再释放修饰键）
                    if main_key:
                        if main_key == 'left': kb.release(Key.left)
                        elif main_key == 'right': kb.release(Key.right)
                        elif main_key == 'up': kb.release(Key.up)
                        elif main_key == 'down': kb.release(Key.down)
                        else: kb.release(main_key)
            
                    for m in reversed(modifiers):
                        if m == 'alt': kb.release(Key.alt)
                        elif m == 'ctrl': kb.release(Key.ctrl)
                        elif m == 'shift': kb.release(Key.shift)
                        elif m == 'win': kb.release(Key.cmd)
            return 'out'
        
        if ntype == 'cmd':
            try: 
                subprocess.Popen(data.get('command', ''), shell=True)
            except Exception as e: self.log(f"CMD错误: {e}", "error")
            return 'out'
        if ntype == 'web': webbrowser.open(data.get('url')); self._smart_wait(2); return 'out'
        if ntype == 'loop':
            if data.get('infinite', True): return 'loop'
            with self.io_lock:
                k = f"loop_{node['id']}"; c = self.runtime_memory.get(k, 0)
                if c < safe_int(data.get('count', 3)): self.runtime_memory[k] = c + 1; return 'loop'
                else: 
                    if k in self.runtime_memory: del self.runtime_memory[k]
                    return 'exit'
        if ntype == 'if_img':
            self._ensure_window_focus()
            if not (imgs := data.get('images', [])): return 'no'
    
            if win_region:
                capture_bbox = (win_region.left, win_region.top, win_region.left + win_region.width, win_region.top + win_region.height)
            else:
                capture_bbox = None
        
            hay = VisionEngine.capture_screen(bbox=capture_bbox)
            for img in imgs:
                if not VisionEngine._advanced_match(img.get('image'), hay, safe_float(data.get('confidence',0.9)), self.stop_event, True, True, self.scaling_ratio, 'hybrid')[0]: return 'no'
            return 'yes'
        return 'out'

# --- 5. 历史记录与节点 ---
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
            if last == curr: return
        self.undo_stack.append(state)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history: self.undo_stack.pop(0)

    def undo(self, event=None):
        if not self.undo_stack: return
        self.redo_stack.append(self.editor.get_data())
        self.editor.load_data(self.undo_stack.pop())
        self.editor.app.property_panel.clear()

    def redo(self, event=None):
        if not self.redo_stack: return
        self.undo_stack.append(self.editor.get_data())
        self.editor.load_data(self.redo_stack.pop())
        self.editor.app.property_panel.clear()

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
        if '_user_title' not in self.data: self.data['_user_title'] = self.title_text
        
        self.outputs = cfg.get('outputs', [])
        if ntype == 'sequence': 
            self.outputs = [str(i) for i in range(1, safe_int(self.data.get('num_steps', 3)) + 1)] + ['else']
        elif ntype == 'var_switch':
            if self.data.get('var_name'): self.outputs = ['yes', 'no']
            else: self.outputs = [c['id'] for c in self.data.get('cases', [])] + ['else']

        self.w = NODE_WIDTH
        self.h = 100 
        self.tags = (f"node_{self.id}", "node")
        self.has_breakpoint = False
        self.widgets = [] 
        self.draw()

    def draw(self):
        z = self.canvas.zoom
        vx, vy, vw = self.x*z, self.y*z, self.w*z
        self.canvas.delete(f"node_{self.id}")
        
        ports_h = max(1, len(self.outputs)) * PORT_STEP_Y
        widgets_h = 0
        self.has_widgets = False
        
        self.is_visual_node = self.type in ['image', 'if_img', 'if_static']
        self.is_app_node = self.type == 'open_app'
        self.is_bind_win_node = self.type == 'bind_win'
        
        if not self.is_visual_node and not self.is_app_node and self.type not in ['reroute', 'start', 'end']:
            widgets_h = 35; self.has_widgets = True
            
        img_display_h = 0; toolbar_h = 0
        if self.is_visual_node:
            toolbar_h = 38 
            if self.type == 'if_img' and self.data.get('images'):
                img_list = self.data.get('images', [])
                if len(img_list) > 0:
                    rows = math.ceil(len(img_list) / 2.0); img_display_h = (rows * 60) + 10 
            else:
                target_img = self.data.get('image') if self.type == 'image' else self.data.get('roi_preview')
                if target_img and isinstance(target_img, Image.Image): 
                    try:
                        iw, ih = target_img.size; scale = (self.w - 8) / iw; calc_h = int(ih * scale); img_display_h = min(calc_h, 120) + 5
                    except: img_display_h = 80
        if self.is_app_node or self.is_bind_win_node: toolbar_h = 35 

        if self.type == 'reroute': 
            self.w, self.h = 30, 30
            vw, vh = self.w*z, self.h*z
            self.canvas.create_oval(vx, vy, vx+vw, vy+vh, fill=COLORS['wire'], outline="", tags=self.tags+('body',))
            self.sel_rect = self.canvas.create_rectangle(vx-3*z, vy-3*z, vx+vw+3*z, vy+vh+3*z, outline=COLORS['accent'], width=4*z, tags=self.tags+('selection',), state='hidden')
            if self.id in self.canvas.selected_node_ids: self.canvas.itemconfig(self.sel_rect, state='normal')
            self.hover_rect = self.canvas.create_rectangle(vx, vy, vx+vw, vy+vh, tags=self.tags+('hover',), state='hidden')
            return
        
        self.h = PORT_START_Y + ports_h + widgets_h + toolbar_h + img_display_h + 8
        vh = self.h * z 
        
        self.sel_rect = self.canvas.create_rectangle(vx-3*z, vy-3*z, vx+vw+3*z, vy+vh+3*z, outline=COLORS['accent'], width=4*z, tags=self.tags+('selection',), state='hidden')

        self.clear_widgets() 
        self.canvas.create_rectangle(vx+4*z, vy+4*z, vx+vw+4*z, vy+vh+4*z, fill=COLORS['shadow'], outline="", tags=self.tags)
        self.body_item = self.canvas.create_rectangle(vx, vy, vx+vw, vy+vh, fill=COLORS['bg_node'], outline=COLORS['bg_node'], width=2*z, tags=self.tags+('body',))
        self.canvas.create_rectangle(vx, vy, vx+vw, vy+HEADER_HEIGHT*z, fill=self.header_color, outline="", tags=self.tags+('header',))
        self.canvas.create_text(vx+10*z, vy+14*z, text=self.data.get('_user_title', self.title_text), fill=COLORS['fg_title'], font=('Microsoft YaHei', max(7, int(10*z)), 'bold'), anchor="w", tags=self.tags)
        if self.has_breakpoint: self.canvas.create_oval(vx+vw-12*z, vy+8*z, vx+vw-4*z, vy+16*z, fill=COLORS['breakpoint'], outline="white", width=1, tags=self.tags)

        if self.type != 'start':
            iy = self.get_input_port_y(visual=True)
            self.canvas.create_oval(vx-5*z, iy-5*z, vx+5*z, iy+5*z, fill=COLORS['socket'], outline=COLORS['bg_canvas'], width=2*z, tags=self.tags+('port_in',))
        
        port_labels = PORT_TRANSLATION.copy()
        if self.type == 'var_switch':
             for c in self.data.get('cases', []): port_labels[c['id']] = f"={c['value']}"

        for i, name in enumerate(self.outputs):
            py = self.get_output_port_y(i, visual=True)
            self.canvas.create_oval(vx+vw-5*z, py-5*z, vx+vw+5*z, py+5*z, fill=COLORS.get(f"socket_{name}", COLORS['socket']), outline=COLORS['bg_canvas'], width=2*z, tags=self.tags+(f'port_out_{name}','port_out',name))
            self.canvas.create_text(vx+vw-12*z, py, text=port_labels.get(name, name), fill=COLORS['fg_sub'], font=('Microsoft YaHei', max(6, int(9*z))), anchor="e", tags=self.tags)

        self.widget_offset_y = PORT_START_Y + ports_h
        if self.has_widgets and z > 0.6: 
            self.render_widgets(vx, vy, vw, z)
            self.widget_offset_y += 35

        if self.is_visual_node:
            toolbar_y = vy + (self.widget_offset_y * z)
            tool_frame = tk.Frame(self.canvas, bg=COLORS['bg_node'])
            def cmd_snip(nid=self.id): self.canvas.select_node(nid); self.canvas.app.do_snip()
            def cmd_test(nid=self.id): self.canvas.select_node(nid); self.canvas.app.property_panel.start_test_match()
            btn_snip = tk.Button(tool_frame, text="🎯 抓取目标", command=cmd_snip, bg=COLORS['accent'], fg='#ffffff', bd=0, font=('Microsoft YaHei', int(10*z), 'bold'), activebackground='#42a5f5', cursor='hand2')
            btn_snip.pack(side='left', fill='x', expand=True, padx=(0, 2), pady=0)
            btn_test = tk.Button(tool_frame, text="⚡", command=cmd_test, bg='#505050', fg='#eeeeee', bd=0, width=3, activebackground='#606060')
            btn_test.pack(side='right', fill='y', pady=0)
            self.widgets.append(self.canvas.create_window(vx + vw/2, toolbar_y, window=tool_frame, width=vw-10*z, height=26*z, anchor='n', tags=self.tags))
            
            img_start_y = toolbar_y + 32*z 
            if self.type == 'if_img' and self.data.get('images'):
                imgs = self.data.get('images', []); cell_w = (vw - 12*z) / 2; cell_h = 55 * z
                for idx, item in enumerate(imgs):
                    if not item.get('image'): continue
                    col = idx % 2; row = idx // 2; ix = vx + 4*z + col * (cell_w + 4*z); iy = img_start_y + row * (cell_h + 4*z)
                    self.canvas.create_rectangle(ix, iy, ix+cell_w, iy+cell_h, fill='#000000', outline=COLORS['wire'], width=1, tags=self.tags)
                    thumb_img = item['image'].copy(); thumb_img.thumbnail((int(cell_w), int(cell_h)), Image.Resampling.LANCZOS)
                    tk_thumb = ImageTk.PhotoImage(thumb_img); item['_tk_cache'] = tk_thumb 
                    self.canvas.create_image(ix + cell_w/2, iy + cell_h/2, image=tk_thumb, anchor='center', tags=self.tags)
                    self.canvas.create_text(ix+3*z, iy+3*z, text=str(idx+1), fill='white', font=('Microsoft YaHei', int(9*z), 'bold'), anchor='nw', tags=self.tags)
            elif img_display_h > 0:
                target_img = self.data.get('image') if self.type == 'image' else self.data.get('roi_preview')
                if target_img and isinstance(target_img, Image.Image): 
                    disp_w = int(vw - 8*z); disp_h = int((img_display_h - 5) * z); thumb = target_img.copy(); thumb.thumbnail((disp_w, disp_h), Image.Resampling.LANCZOS)
                    tk_thumb = ImageTk.PhotoImage(thumb); self.data['_tk_cache'] = tk_thumb 
                    self.canvas.create_rectangle(vx+4*z, img_start_y, vx+vw-4*z, img_start_y+disp_h, fill='#000000', outline=COLORS['wire'], width=1, tags=self.tags)
                    self.canvas.create_image(vx + vw/2, img_start_y + disp_h/2, image=tk_thumb, anchor='center', tags=self.tags)

        if self.is_app_node:
            toolbar_y = vy + (self.widget_offset_y * z); path = self.data.get('path', ''); filename = os.path.basename(path) if path else "未选择程序"
            if len(filename) > 20: filename = filename[:18] + "..."
            icon_x = vx + 12*z; icon_y = toolbar_y + 5*z
            self.canvas.create_rectangle(icon_x, icon_y, icon_x+18*z, icon_y+22*z, fill='#5c6bc0', outline='', tags=self.tags)
            self.canvas.create_polygon(icon_x+12*z, icon_y, icon_x+18*z, icon_y, icon_x+18*z, icon_y+6*z, fill='#3949ab', outline='', tags=self.tags)
            self.canvas.create_text(icon_x+26*z, icon_y+11*z, text=filename, fill=COLORS['fg_text'], font=('Microsoft YaHei', int(9*z)), anchor='w', tags=self.tags)
        elif self.is_bind_win_node:
            toolbar_y = vy + (self.widget_offset_y * z); exe_name = self.data.get('exe_name', ''); 
            display_name = exe_name if exe_name else "未绑定进程"
            if len(display_name) > 20: display_name = display_name[:18] + "..."
            icon_x = vx + 12*z; icon_y = toolbar_y + 5*z
            self.canvas.create_rectangle(icon_x, icon_y, icon_x+18*z, icon_y+22*z, fill='#00695c', outline='', tags=self.tags)
            self.canvas.create_text(icon_x+5*z, icon_y+11*z, text="⚓", fill='#ffffff', font=('Microsoft YaHei', int(12*z)), anchor='w', tags=self.tags)
            self.canvas.create_text(icon_x+26*z, icon_y+11*z, text=display_name, fill=COLORS['fg_text'], font=('Microsoft YaHei', int(9*z)), anchor='w', tags=self.tags)

        if self.id in self.canvas.selected_node_ids: self.canvas.itemconfig(self.sel_rect, state='normal')
        self.hover_rect = self.canvas.create_rectangle(vx-1*z, vy-1*z, vx+vw+1*z, vy+vh+1*z, outline=COLORS['hover'], width=1*z, state='hidden', tags=self.tags+('hover',))

    def render_widgets(self, vx, vy, vw, z):
        y_cursor = vy + (self.widget_offset_y * z) 
        def create_entry(key, default, label_txt, width=8):
            val = self.data.get(key, default); frame = tk.Frame(self.canvas, bg=COLORS['bg_node'])
            tk.Label(frame, text=label_txt, bg=COLORS['bg_node'], fg=COLORS['fg_sub'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left')
            e = tk.Entry(frame, bg=COLORS['input_bg'], fg='white', bd=0, width=width, insertbackground='white', font=('Microsoft YaHei', int(10 * SCALE_FACTOR))); e.insert(0, str(val)); e.pack(side='left', padx=5)
            e.bind("<FocusOut>", lambda ev: self.update_data(key, e.get(), refresh_ui=True)); e.bind("<Return>", lambda ev: [self.update_data(key, e.get(), refresh_ui=True), self.canvas.focus_set()])
            self.widgets.append(self.canvas.create_window(vx + 10*z, y_cursor, window=frame, anchor='nw', tags=self.tags))

        def create_combo(key, options_map, default, width=8):
            if isinstance(options_map, dict): options = list(options_map.values()); curr_val = self.data.get(key, default); disp_val = options_map.get(curr_val, curr_val); map_inv = {v: k for k, v in options_map.items()}
            else: options = options_map; disp_val = self.data.get(key, default); map_inv = None
            cb = ttk.Combobox(self.canvas, values=options, state='readonly', width=width, font=('Microsoft YaHei', int(9 * SCALE_FACTOR))); 
            try: cb.set(disp_val)
            except: pass
            def on_sel(ev): val = cb.get(); final_val = map_inv.get(val, val) if map_inv else val; self.update_data(key, final_val, refresh_ui=True)
            cb.bind("<<ComboboxSelected>>", on_sel)
            self.widgets.append(self.canvas.create_window(vx + 10*z, y_cursor, window=cb, anchor='nw', tags=self.tags))
            
        if self.type == 'wait': create_entry('seconds', '1.0', '等待(s):')
        elif self.type == 'loop': create_entry('count', '5', '循环:')
        elif self.type == 'keyboard': create_entry('text', '', '文本:', width=10)
        elif self.type == 'cmd': create_entry('command', '', '命令:', width=12)
        elif self.type == 'bind_win': create_entry('title', '', '标题:', width=10)
        elif self.type == 'notify': create_entry('msg', '执行到此节点', '提示:', width=10)
        elif self.type == 'mouse': create_combo('mouse_action', MOUSE_ACTIONS, 'click', width=12)

    def clear_widgets(self):
        for w in self.widgets:
            widget_name = self.canvas.itemcget(w, 'window')
            if widget_name:
                try:
                    self.canvas.nametowidget(widget_name).destroy()
                except Exception:
                    pass
            self.canvas.delete(w)
        self.widgets.clear()

    def update_data(self, key, value, refresh_ui=True):
        if str(self.data.get(key)) == str(value): return
        if refresh_ui: self.canvas.history.save_state()
        self.data[key] = value
        
        # 核心修复：添加所有在画布中使用的输入和选择键。当它们变化时触发画布静默重繪，彻底防范微型组件失焦导致的旧文本写回冲突。
        redraw_keys = ['msg', 'seconds', 'count', 'command', 'title', 'text', 'mouse_action', 'cases', 'var_name', 'image', 'images', 'roi_preview', 'path', 'exe_name', 'class_name', '_user_title']
        if key in redraw_keys: 
            self.draw() 
            
        if refresh_ui and self.canvas.app.property_panel.current_node == self: 
           self.canvas.app.property_panel.load_node(self)

    def set_sensor_active(self, is_active): self.canvas.itemconfig(self.body_item, outline=COLORS['active_border'] if is_active else COLORS['bg_node'])
    def get_input_port_y(self, visual=False): 
        if self.type == 'reroute': return (self.y + 15)*self.canvas.zoom if visual else self.y + 15
        offset = HEADER_HEIGHT + 14; return (self.y + offset)*self.canvas.zoom if visual else self.y + offset
    def get_output_port_y(self, index=0, visual=False): 
        if self.type == 'reroute': return (self.y + 15)*self.canvas.zoom if visual else self.y + 15
        offset = PORT_START_Y + (index * PORT_STEP_Y); return (self.y + offset)*self.canvas.zoom if visual else self.y + offset
    def get_port_y_by_name(self, port_name, visual=False):
        try: idx = self.outputs.index(port_name)
        except ValueError: idx = 0
        return self.get_output_port_y(idx, visual)
    def set_pos(self, x, y): self.x, self.y = x, y; self.draw()
    def set_selected(self, selected): self.canvas.itemconfig(self.sel_rect, state='normal' if selected else 'hidden'); (selected and self.canvas.tag_lower(self.sel_rect, self.body_item))
    def contains(self, log_x, log_y): return self.x <= log_x <= self.x + self.w and self.y <= log_y <= self.y + self.h
    def update_position(self, dx, dy): self.canvas.move(self.tags[0], dx, dy)

class FlowEditor(tk.Canvas):
    def __init__(self,parent,app,**kwargs):
        super().__init__(parent,bg=COLORS['bg_canvas'],highlightthickness=0,**kwargs)
        self.app,self.nodes,self.links=app,{},[]
        self.selected_node_ids = set(); self.drag_data = {"type": None}; self.wire_start = None; self.temp_wire = None; self.selection_box = None
        self.history = HistoryManager(self); self.zoom=1.0; self.bind_events(); self.full_redraw()
        
    def bind_events(self):
        self.bind("<ButtonPress-1>",self.on_lmb_press);self.bind("<B1-Motion>",self.on_lmb_drag);self.bind("<ButtonRelease-1>",self.on_lmb_release)
        self.bind("<ButtonPress-3>",self.on_rmb_press);self.bind("<B3-Motion>",self.on_rmb_drag);self.bind("<ButtonRelease-3>",self.on_rmb_release)
        self.bind("<ButtonPress-2>",self.on_pan_start);self.bind("<B2-Motion>",self.on_pan_drag);self.bind("<ButtonRelease-2>",self.on_pan_end)
        self.bind("<MouseWheel>",self.on_scroll)
        self.bind_all("<Delete>",self._on_delete_press,add="+");self.bind_all("<Control-z>", self.history.undo, add="+"); self.bind_all("<Control-y>", self.history.redo, add="+")
        self.bind("<Configure>",self.full_redraw)
    
    def on_rmb_press(self, event): self._rmb_start = (event.x, event.y); self._rmb_moved = False; self.scan_mark(event.x, event.y)
    def on_rmb_drag(self, event): (abs(event.x-self._rmb_start[0])>5 or abs(event.y-self._rmb_start[1])>5) and setattr(self,'_rmb_moved',True); self._rmb_moved and (self.config(cursor="fleur"),self.scan_dragto(event.x, event.y, gain=1),self._draw_grid())
    def on_rmb_release(self, event): self.config(cursor="arrow"); (not getattr(self,'_rmb_moved',False) and self.on_right_click_menu(event))
    def on_pan_start(self,event): self.config(cursor="fleur");self.scan_mark(event.x,event.y)
    def on_pan_drag(self,event): self.scan_dragto(event.x,event.y,gain=1);self._draw_grid()
    def on_pan_end(self,event): self.config(cursor="arrow")
    def _on_delete_press(self,e): 
        if self.selected_node_ids:
            self.history.save_state(); to_del = list(self.selected_node_ids)
            for nid in to_del: self.delete_node(nid)
            self.select_node(None)
    def get_logical_pos(self,event_x,event_y): return self.canvasx(event_x)/self.zoom,self.canvasy(event_y)/self.zoom
    def full_redraw(self,event=None): 
        self.config(bg=COLORS['bg_canvas']); self.delete("all");self._draw_grid(); [n.draw() for n in self.nodes.values()]; self.redraw_links()

    def _draw_grid(self):
        w,h=self.winfo_width(),self.winfo_height(); x1,y1,x2,y2=self.canvasx(0),self.canvasy(0),self.canvasx(w),self.canvasy(h)
        if (step:=int(GRID_SIZE*self.zoom))<5: return
        start_x,start_y=int(x1//step)*step,int(y1//step)*step
        for i in range(start_x,int(x2)+step,step): self.create_line(i,y1,i,y2,fill=COLORS['grid'],tags="grid")
        for i in range(start_y,int(y2)+step,step): self.create_line(x1,i,x2,i,fill=COLORS['grid'],tags="grid")
        self.tag_lower("grid")
    
    def add_node(self,ntype,x,y,data=None,node_id=None, save_history=True): 
        if save_history: self.history.save_state()
        node=GraphNode(self,node_id or str(uuid.uuid4()),ntype,x,y,data)
        self.nodes[node.id]=node; self.select_node(node.id); return node
    
    def delete_node(self,node_id):
        if node_id in self.nodes:
            self.links = [l for l in self.links if l['source'] != node_id and l['target'] != node_id]
            self.nodes[node_id].clear_widgets(); self.delete(f"node_{node_id}"); del self.nodes[node_id]; self.redraw_links()

    def on_scroll(self, e):
        old_zoom = self.zoom; new_zoom = max(0.4, min(3.0, self.zoom * (1.1 if e.delta > 0 else 0.9)))
        if new_zoom == self.zoom: return
        self.zoom = new_zoom; self.full_redraw()

    def on_lmb_press(self,event):
        lx,ly=self.get_logical_pos(event.x,event.y); vx,vy=self.canvasx(event.x),self.canvasy(event.y)
        z = self.zoom
        items = self.find_overlapping(vx-10*z,vy-10*z,vx+10*z,vy+10*z)
        for item in items:
            t_list = self.gettags(item)
            if "port_out" in t_list and (nid:=next((t[5:] for t in t_list if t.startswith("node_")),None)) and nid in self.nodes:
                self.wire_start={'node':self.nodes[nid],'port':next((t for t in t_list if t in self.nodes[nid].outputs),'out')};self.drag_data={"type":"wire"}; return
        
        clicked_node=next((node for node in reversed(list(self.nodes.values())) if node.contains(lx,ly)),None)
        if clicked_node:
            if not (event.state & 0x0004): 
                if clicked_node.id not in self.selected_node_ids: self.select_node(clicked_node.id)
            else: self.select_node(clicked_node.id, add=True)
            self.drag_data = {"type": "node", "last_vx": vx, "last_vy": vy, "dragged": False}
            self.history.save_state(); [self.tag_raise(f"node_{nid}") for nid in self.selected_node_ids]
        else:
            if not (event.state & 0x0004): self.select_node(None)
            self.drag_data = {"type": "box_select", "start_vx": vx, "start_vy": vy}; self.selection_box = self.create_rectangle(vx, vy, vx, vy, outline=COLORS['select_box'], width=2, dash=(4,4), tags="selection_box")

    def on_lmb_drag(self,event):
        lx,ly=self.get_logical_pos(event.x,event.y); vx,vy=self.canvasx(event.x),self.canvasy(event.y)
        if self.drag_data["type"]=="node":
            self.drag_data["dragged"] = True; dx = vx - self.drag_data["last_vx"]; dy = vy - self.drag_data["last_vy"]; self.drag_data["last_vx"] = vx; self.drag_data["last_vy"] = vy
            for nid in self.selected_node_ids:
                if nid in self.nodes: node = self.nodes[nid]; node.x += dx / self.zoom; node.y += dy / self.zoom; node.update_position(dx, dy)
            self.redraw_links()
        elif self.drag_data["type"]=="box_select":
            if self.selection_box: self.coords(self.selection_box, self.drag_data["start_vx"], self.drag_data["start_vy"], vx, vy)
        elif self.drag_data["type"]=="wire":
            if self.temp_wire: self.delete(self.temp_wire)
            n,p=self.wire_start['node'],self.wire_start['port']
            x_start = (n.x+n.w)*self.zoom if n.type!='reroute' else (n.x+15)*self.zoom
            self.temp_wire=self.draw_bezier(x_start, n.get_port_y_by_name(p,visual=True),vx,vy,state="active")

    def on_lmb_release(self,event):
        lx,ly=self.get_logical_pos(event.x,event.y)
        if self.drag_data.get("type")=="node":
            if self.drag_data.get("dragged", False):
                for nid in self.selected_node_ids:
                    if nid in self.nodes: self.nodes[nid].set_pos(round(self.nodes[nid].x/GRID_SIZE)*GRID_SIZE, round(self.nodes[nid].y/GRID_SIZE)*GRID_SIZE)
                self.redraw_links()
            else: 
                if self.history.undo_stack: self.history.undo_stack.pop()
        elif self.drag_data.get("type")=="box_select":
            if self.selection_box:
                coords = self.coords(self.selection_box)
                if coords and len(coords) == 4:
                    overlapping = self.find_overlapping(*coords)
                    [self.select_node(t[5:], add=True) for item in overlapping for t in self.gettags(item) if t.startswith("node_") and t[5:] in self.nodes]
                self.delete(self.selection_box); self.selection_box = None
        elif self.drag_data.get("type")=="wire":
            if self.temp_wire: self.delete(self.temp_wire)
            lx,ly=self.get_logical_pos(event.x,event.y)
            for node in self.nodes.values():
                is_reroute = node.type == 'reroute'
                dist = math.hypot(lx-(node.x+15 if is_reroute else node.x), ly-node.get_input_port_y(visual=False))
                if node.id!=self.wire_start['node'].id and dist < (45/self.zoom):
                    if node.type=='start': continue
                    self.history.save_state(); self.links.append({'id':str(uuid.uuid4()),'source':self.wire_start['node'].id,'source_port':self.wire_start['port'],'target':node.id}); self.redraw_links(); break
        self.drag_data,self.wire_start,self.temp_wire={"type":None},None,None
    
    def select_node(self, node_id, add=False):
        if not add: [self.nodes[nid].set_selected(False) for nid in self.selected_node_ids if nid in self.nodes]; self.selected_node_ids.clear()
        if node_id and node_id in self.nodes: self.selected_node_ids.add(node_id); self.nodes[node_id].set_selected(True)
        if not self.selected_node_ids: self.app.property_panel.show_empty()
        elif len(self.selected_node_ids) == 1: self.app.property_panel.load_node(self.nodes[next(iter(self.selected_node_ids))])
        else: self.app.property_panel.show_multi_select(len(self.selected_node_ids))
        self.redraw_links()

    def draw_bezier(self,x1,y1,x2,y2,state="normal",link_id=None, highlighted=False):
        offset=max(50*self.zoom,abs(x1-x2)*0.5); width = 4*self.zoom if highlighted else (3*self.zoom if state=="active" else 2*self.zoom)
        color = COLORS['wire_hl'] if highlighted else COLORS['wire_active' if state=="active" else 'wire']
        return self.create_line(x1,y1,x1+offset,y1,x2-offset,y2,x2,y2,smooth=True,splinesteps=50,fill=color,width=width,arrow=tk.NONE,tags=("link",)+((f"link_{link_id}",) if link_id else ()))
    
    def redraw_links(self):
        self.delete("link"); 
        for l in self.links:
            if l['source'] in self.nodes and l['target'] in self.nodes:
                n1,n2=self.nodes[l['source']],self.nodes[l['target']]
                x1 = (n1.x + n1.w)*self.zoom if n1.type != 'reroute' else (n1.x + 15)*self.zoom
                y1 = n1.get_port_y_by_name(l.get('source_port','out'),visual=True)
                x2 = n2.x*self.zoom if n2.type != 'reroute' else (n2.x + 15)*self.zoom
                y2 = n2.get_input_port_y(visual=True)
                self.draw_bezier(x1,y1,x2,y2,link_id=l['id'], highlighted=(l['source'] in self.selected_node_ids or l['target'] in self.selected_node_ids))
        self.tag_lower("link"); self.tag_lower("grid")

    def on_right_click_menu(self,event):
        vx,vy=self.canvasx(event.x),self.canvasy(event.y)
        for item in self.find_overlapping(vx-3,vy-3,vx+3,vy+3):
            tags=self.gettags(item)
            if (nid:=next((t[5:] for t in tags if t.startswith("node_")),None)):
                if "port_out" in tags: 
                     self.history.save_state(); self.links=[l for l in self.links if not (l['source']==nid and l.get('source_port')==next((t for t in tags if t in self.nodes[nid].outputs),'out'))]; self.redraw_links(); return
                if "port_in" in tags: 
                     self.history.save_state(); self.links=[l for l in self.links if not l['target']==nid]; self.redraw_links(); return
        lx, ly = self.get_logical_pos(event.x, event.y); node = next((n for n in reversed(list(self.nodes.values())) if n.contains(lx, ly)), None)
        m=tk.Menu(self,tearoff=0,bg=COLORS['bg_card'],fg=COLORS['fg_text'],font=('Microsoft YaHei', int(9 * SCALE_FACTOR)))
        if node:
            m.add_command(label="📥 复制",command=lambda: (self.history.save_state(), self.add_node(node.type, node.x+20, node.y+20, data=copy.deepcopy(node.data), save_history=False)))
            m.add_command(label="🔴 断点",command=lambda: setattr(node, 'has_breakpoint', not node.has_breakpoint) or node.draw())
            m.add_separator()
            m.add_command(label="❌ 删除",command=lambda: (self.history.save_state(), self.delete_node(node.id)),foreground=COLORS['danger'])
        else:
             if len(self.selected_node_ids) > 1:
                m.add_command(label="⬅ 左对齐", command=lambda: self.align_nodes('left'))
        m.post(event.x_root,event.y_root)

    def align_nodes(self, mode):
        if len(self.selected_node_ids) < 2: return
        self.history.save_state(); nodes = [self.nodes[nid] for nid in self.selected_node_ids if nid in self.nodes]
        if mode == 'left': target = min(n.x for n in nodes); [n.set_pos(target, n.y) for n in nodes]
        self.redraw_links()

    def sanitize_data_for_json(self, data):
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                if k in ['image', 'tk_image', 'roi_preview', '_tk_cache']: continue 
                if isinstance(v, (Image.Image, ImageTk.PhotoImage)): continue
                new_dict[k] = self.sanitize_data_for_json(v)
            return new_dict
        elif isinstance(data, list): return [self.sanitize_data_for_json(item) for item in data]
        else: return data

    def get_data(self):
        nodes_d = {}
        for nid, n in self.nodes.items():
            clean_data = self.sanitize_data_for_json(n.data)
            if 'image' in n.data and 'b64' not in clean_data: clean_data['b64'] = ImageUtils.img_to_b64(n.data['image'])
            if 'roi_preview' in n.data and 'b64_preview' not in clean_data: clean_data['b64_preview'] = ImageUtils.img_to_b64(n.data['roi_preview'])
            nodes_d[nid]={'id':nid,'type':n.type,'x':int(n.x),'y':int(n.y),'data':clean_data, 'breakpoint': n.has_breakpoint}
        breakpoints = [nid for nid, n in self.nodes.items() if n.has_breakpoint]
        return {'nodes':nodes_d, 'links':self.links, 'breakpoints': breakpoints, 'metadata':{'dev_scale_x':SCALE_X,'dev_scale_y':SCALE_Y}}

    def load_data(self,data):
        self.delete("all");self.nodes.clear();self.links.clear()
        try:
            self.app.core.load_project(data)
            breakpoints = set(data.get('breakpoints', []))
            
            max_node_number = 0
            for n_data in data.get('nodes',{}).values():
                node_number = n_data.get('data', {}).get('node_number', 0)
                if node_number > max_node_number:
                    max_node_number = node_number
            GraphNode.next_node_number = max_node_number + 1
            
            for nid,n_data in data.get('nodes',{}).items():
                d=n_data.get('data',{})
                if 'image' in d: d['tk_image'] = ImageUtils.make_thumb(d['image'])
                if 'b64_preview' in d and (img:=ImageUtils.b64_to_img(d['b64_preview'])): 
                    d['roi_preview'] = img 
                
                n = self.add_node(n_data['type'],n_data['x'],n_data['y'],data=d,node_id=nid, save_history=False)
                if n_data.get('breakpoint', False) or nid in breakpoints: n.has_breakpoint = True; n.draw()
            self.links=data.get('links',[])
            self.full_redraw()
        except Exception as e: self.app.log(f"❌ 加载失败: {e}", "error")

# --- 6. 属性面板 ---
class PropertyPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS['bg_panel'])
        self.app, self.current_node = app, None
        self.static_monitor_active = False
        self.is_monitoring_audio = False
        
        header = tk.Frame(self, bg=COLORS['bg_sidebar'], height=40)
        header.pack(fill='x')
        tk.Label(header, text="属性设置", bg=COLORS['bg_sidebar'], fg=COLORS['fg_sub'], font=('Microsoft YaHei', 11, 'bold')).pack(side='left', padx=10, pady=10)
        
        self.scrollbar = ttk.Scrollbar(self, orient="vertical")
        self.scrollbar.pack(side='right', fill='y')
        self.canvas = tk.Canvas(self, bg=COLORS['bg_panel'], highlightthickness=0, yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.config(command=self.canvas.yview)
        
        self.content = tk.Frame(self.canvas, bg=COLORS['bg_panel'], padx=10, pady=10)
        self.content_id = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        
        def on_content_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            if event.height <= self.canvas.winfo_height():
                self.scrollbar.pack_forget(); self.canvas.pack(side='left', fill='both', expand=True)
            else:
                self.scrollbar.pack(side='right', fill='y'); self.canvas.pack(side='left', fill='both', expand=True)
        self.content.bind("<Configure>", on_content_configure)
        
        def on_canvas_configure(event):
            self.canvas.itemconfig(self.content_id, width=event.width if self.scrollbar.winfo_ismapped() else event.width)
        self.canvas.bind("<Configure>", on_canvas_configure)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.show_empty()
    
    def clear(self): 
        for w in self.content.winfo_children(): 
            try: w.destroy()
            except: pass
        self.current_node = None; self.static_monitor_active = False; self.is_monitoring_audio = False

    def show_empty(self): 
        self.clear(); 
        info_frame = tk.Frame(self.content, bg=COLORS['bg_panel'])
        info_frame.pack(fill='both', expand=True, pady=40)
        tk.Label(info_frame, text="未选择节点", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei', 11, 'bold')).pack()
        tk.Label(info_frame, text="请在画布中点击节点以配置属性", bg=COLORS['bg_panel'], fg=COLORS['fg_sub'], font=('Microsoft YaHei', 9)).pack(pady=5)
        
    def show_multi_select(self, count): self.clear(); tk.Label(self.content, text=f"选中 {count} 个节点", bg=COLORS['bg_panel'], fg=COLORS['accent']).pack(pady=40)

    def load_node(self, node):
        self.clear(); self.current_node = node; ntype, data = node.type, node.data
        
        if ntype != 'reroute':
            f = tk.Frame(self.content, bg=self.content.cget('bg')); f.pack(fill='x', pady=2)
            tk.Label(f, text="节点编号", bg=self.content.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left')
            node_num = data.get('node_number', 'N/A')
            tk.Label(f, text=str(node_num), bg=COLORS['input_bg'], fg=COLORS['accent'], font=('Microsoft YaHei', int(10 * SCALE_FACTOR)), padx=5, pady=2).pack(fill='x', expand=True, pady=2, ipady=3)
        
        if ntype != 'reroute': self._input(self.content, "节点名称", '_user_title', data.get('_user_title', node.title_text))

        # 逻辑类
        if ntype == 'wait': self._input(self.content, "等待秒数", 'seconds', data.get('seconds', 1.0), safe_float)
        elif ntype == 'loop':
             self._chk(self.content, "无限循环", 'infinite', data.get('infinite', True))
             if not data.get('infinite', True): self._input(self.content, "循环次数", 'count', data.get('count', 5), safe_int)
        elif ntype == 'notify':
             self._input(self.content, "提示内容", 'msg', data.get('msg', '当前所有变量: {ALL_VARS}'))
             self._input(self.content, "持续时间(秒)", 'duration', data.get('duration', 2.0), safe_float)
             self._chk(self.content, "提示音", 'use_sound', data.get('use_sound', False))
        elif ntype == 'set_var':
            sec = self._create_section("变量设置"); tk.Label(sec, text="每行 'name=value':", bg=sec.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(anchor='w')
            txt = tk.Text(sec, height=5, bg=COLORS['input_bg'], fg='white', bd=0, font=('Microsoft YaHei', int(10 * SCALE_FACTOR))); txt.pack(fill='x', pady=(2,5))
            existing = "".join([f"{i.get('name')}={i.get('value')}\n" for i in data.get('batch_vars', [])])
            if not existing and data.get('var_name'): existing = f"{data.get('var_name')}={data.get('var_value')}"
            txt.insert('1.0', existing)
            def save_vars(ev=None): 
                self._save('batch_vars', [{'name':l.split('=')[0].strip(),'value':l.split('=')[1].strip()} for l in txt.get('1.0', 'end').strip().split('\n') if '=' in l], self.current_node, refresh_ui=False)
                self.app.editor.history.save_state()
            txt.bind("<FocusOut>", save_vars); self._btn(sec, "💾 保存变量列表", save_vars)
            
        elif ntype == 'clipboard':
            sec = self._create_section("剪贴板操作")
            CLIP_MODES = {'read': '读取到变量', 'write': '写入剪贴板'}
            curr_mode = data.get('clip_mode', 'read')
            self._combo(sec, "模式", 'clip_mode', list(CLIP_MODES.values()), CLIP_MODES.get(curr_mode), lambda e: [self._save('clip_mode', {v:k for k,v in CLIP_MODES.items()}.get(e.widget.get()), self.current_node, refresh_ui=True)])
            if data.get('clip_mode', 'read') == 'read':
                self._input(sec, "保存至变量", 'var_name', data.get('var_name', 'clipboard_data'))
            else:
                self._input(sec, "写入内容", 'text', data.get('text', ''))

        # 动作类
        elif ntype == 'bind_win':
            sec = self._create_section("绑定规则")
            self._input(sec, "进程名 (Exe)", 'exe_name', data.get('exe_name', ''))
            self._input(sec, "类名 (Class)", 'class_name', data.get('class_name', ''))
            self._input(sec, "标题包含", 'title', data.get('title', ''))
            tk.Label(sec, text="匹配策略:", bg=sec.cget('bg'), fg=COLORS['accent'], font=('Microsoft YaHei', int(10 * SCALE_FACTOR))).pack(anchor='w', pady=(5,0))
            f_chk = tk.Frame(sec, bg=sec.cget('bg')); f_chk.pack(fill='x')
            self._chk(f_chk, "匹配进程", 'use_exe', data.get('use_exe', True))
            self._chk(f_chk, "匹配类名", 'use_class', data.get('use_class', True))
            self._chk(f_chk, "匹配标题", 'use_title', data.get('use_title', False))
            tk.Frame(sec, height=1, bg=COLORS['bg_header']).pack(fill='x', pady=5)
            def start_pick(): self.app.iconify(); self.app.after(200, self.open_window_picker)
            tk.Button(sec, text="⌖ 智能拾取窗口", command=start_pick, bg=COLORS['accent'], fg='white', bd=0, font=('Microsoft YaHei', 10, 'bold'), cursor='hand2').pack(fill='x', ipady=3)
            
        elif ntype == 'open_app':
            sec = self._create_section("程序配置")
            self._file_picker(sec, "程序路径", 'path', data.get('path', ''))
            self._input(sec, "启动参数", 'args', data.get('args', ''))

        elif ntype == 'cmd': self._input(self.content, "系统命令", 'command', data.get('command', ''))
        elif ntype == 'web': self._input(self.content, "URL", 'url', data.get('url', ''))
        elif ntype == 'mouse':
            sec = self._create_section("鼠标操作")
            
            # [显式坐标模式] 允许用户自主选择相对或绝对
            COORD_MODES = {'relative': '相对绑定窗口 (推荐)', 'absolute': '绝对屏幕坐标'}
            curr_mode = data.get('coord_mode', 'relative')
            self._combo(sec, "坐标模式", 'coord_mode', list(COORD_MODES.values()), COORD_MODES.get(curr_mode, '相对绑定窗口 (推荐)'), 
                        lambda e: self._save('coord_mode', {v:k for k,v in COORD_MODES.items()}.get(e.widget.get()), self.current_node, refresh_ui=True))
            
            def on_action_change(e):
                val = {v:k for k,v in MOUSE_ACTIONS.items()}.get(e.widget.get())
                self._save('mouse_action', val, self.current_node, refresh_ui=True)

            curr_action = data.get('mouse_action', 'click')
            self._combo(sec, "动作", 'mouse_action', list(MOUSE_ACTIONS.values()), MOUSE_ACTIONS.get(curr_action, '点击'), on_action_change)
            
            if curr_action == 'click':
                self._combo(sec, "按键", 'mouse_button', list(MOUSE_BUTTONS.values()), MOUSE_BUTTONS.get(data.get('mouse_button', 'left')), lambda e: self._save('mouse_button', {v:k for k,v in MOUSE_BUTTONS.items()}.get(e.widget.get()), self.current_node, refresh_ui=True))
                self._combo(sec, "次数", 'click_count', ['单击','双击'], '单击' if str(data.get('click_count',1))=='1' else '双击', lambda e: self._save('click_count', 1 if e.widget.get()=='单击' else 2, self.current_node, refresh_ui=True))
            elif curr_action == 'double_click':
                tk.Label(sec, text="ℹ️ 执行左键双击", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(anchor='w')

            if curr_action in ['click', 'move', 'double_click']:
                coord = tk.Frame(sec, bg=sec.cget('bg')); coord.pack(fill='x', pady=5)
                self._compact_input(coord, "X", 'x', data.get('x', 0), safe_int)
                self._compact_input(coord, "Y", 'y', data.get('y', 0), safe_int)
                self._btn_icon(coord, "📍", self.app.pick_coordinate, width=3)
            elif curr_action == 'drag':
                start_coord = tk.Frame(sec, bg=sec.cget('bg')); start_coord.pack(fill='x', pady=5)
                tk.Label(start_coord, text="起始坐标:", bg=sec.cget('bg'), fg=COLORS['accent'], font=('Microsoft YaHei', int(10 * SCALE_FACTOR))).pack(anchor='w', pady=(5,0))
                start_input = tk.Frame(start_coord, bg=sec.cget('bg')); start_input.pack(fill='x', pady=2)
                self._compact_input(start_input, "X", 'start_x', data.get('start_x', 0), safe_int)
                self._compact_input(start_input, "Y", 'start_y', data.get('start_y', 0), safe_int)
                self._btn_icon(start_input, "📍", self.app.pick_start_coordinate, width=3)
                end_coord = tk.Frame(sec, bg=sec.cget('bg')); end_coord.pack(fill='x', pady=5)
                tk.Label(end_coord, text="目标坐标:", bg=sec.cget('bg'), fg=COLORS['accent'], font=('Microsoft YaHei', int(10 * SCALE_FACTOR))).pack(anchor='w', pady=(5,0))
                end_input = tk.Frame(end_coord, bg=sec.cget('bg')); end_input.pack(fill='x', pady=2)
                self._compact_input(end_input, "X", 'end_x', data.get('end_x', 0), safe_int)
                self._compact_input(end_input, "Y", 'end_y', data.get('end_y', 0), safe_int)
                self._btn_icon(end_input, "📍", self.app.pick_end_coordinate, width=3)
            
            elif curr_action == 'scroll':
                scroll_f = tk.Frame(sec, bg=sec.cget('bg')); scroll_f.pack(fill='x', pady=5)
                self._input(scroll_f, "滚动量(负数向下)", 'scroll_amount', data.get('scroll_amount', -500), safe_int)

        elif ntype == 'keyboard':
            sec = self._create_section("键盘操作")
            
            def on_mode_change(e):
                val = 'text' if e.widget.get()=='输入文本' else 'key'
                self._save('kb_mode', val, self.current_node, refresh_ui=True)

            self._combo(sec, "模式", 'kb_mode', ['输入文本', '按键组合'], '输入文本' if data.get('kb_mode','text')=='text' else '按键组合', on_mode_change)
            
            if data.get('kb_mode','text')=='text': 
                self._input(sec, "文本", 'text', data.get('text', ''))
                self._chk(sec, "粘贴模式 (快速/防乱码)", 'use_paste', data.get('use_paste', True))
                self._chk(sec, "按回车", 'press_enter', data.get('press_enter', False))
            else: self._input(sec, "组合键", 'key_name', data.get('key_name', '')); tk.Label(sec, text="例: ctrl+c", bg=sec.cget('bg'), fg=COLORS['fg_sub'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(anchor='w')

        # 视觉类
        elif ntype == 'image':
            base = self._create_section("目标图像")
            if 'tk_image' in data: self._draw_image_preview(base, data)
            self._btn(base, "📸 截取目标", self.app.do_snip)
            search = self._create_section("匹配参数")
            self._input(search, "相似度", 'confidence', data.get('confidence', 0.9), safe_float)
            self._input(search, "超时(s)", 'timeout', data.get('timeout', 10.0), safe_float)
            
            curr_strat = data.get('match_strategy', 'hybrid')
            self._combo(search, "算法", 'match_strategy', list(MATCH_STRATEGY_MAP.values()), MATCH_STRATEGY_MAP.get(curr_strat, '智能混合'), lambda e: self._save('match_strategy', {v:k for k,v in MATCH_STRATEGY_MAP.items()}.get(e.widget.get()), self.current_node, refresh_ui=True))

            self._chk(search, "未找到时尝试滚动", 'auto_scroll', data.get('auto_scroll', False))
            if data.get('auto_scroll', False):
                self._input(search, "滚动量(负数向下)", 'scroll_amount', data.get('scroll_amount', -500), safe_int)

            act = self._create_section("找到后执行")
            self._combo(act, "动作", 'click_type', list(ACTION_MAP.values()), ACTION_MAP.get(data.get('click_type', 'click')), lambda e: self._save('click_type', {v:k for k,v in ACTION_MAP.items()}.get(e.widget.get()), self.current_node, refresh_ui=True))
            off = tk.Frame(act, bg=act.cget('bg')); off.pack(fill='x', pady=5)
            self._compact_input(off, "偏X", 'offset_x', data.get('offset_x', 0), safe_int)
            self._compact_input(off, "Y", 'offset_y', data.get('offset_y', 0), safe_int)
            self._btn_icon(off, "🎯", self.open_visual_offset_picker, bg=COLORS['control'], width=3)
            self._btn(act, "⚡ 测试当前匹配", self.start_test_match)

        elif ntype == 'if_img':
            sec = self._create_section("多图检测配置")
            imgs = data.get('images', [])
            stat_frame = tk.Frame(sec, bg=sec.cget('bg'))
            stat_frame.pack(fill='x', pady=(0, 5))
            tk.Label(stat_frame, text=f"📚 已存参考图: {len(imgs)} 张", bg=sec.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(anchor='w')
            self._btn(sec, "📸 截取并添加参考图", self.app.do_snip, bg=COLORS['accent'])
            if imgs:
                def clear_imgs():
                    if messagebox.askyesno("确认清空", "确定要删除所有已保存的检测图片吗？"):
                        self._save('images', [], self.current_node, refresh_ui=True)
                self._btn(sec, "🗑️ 清空所有图片", clear_imgs, bg=COLORS['danger'])
            param = self._create_section("匹配参数")
            self._input(param, "相似度(0.1-1.0)", 'confidence', data.get('confidence', 0.9), safe_float)
            self._btn(param, "⚡ 测试当前屏幕匹配", self.start_test_match)

        elif ntype == 'if_static':
             base_sec = self._create_section("监控区域")
             if 'roi_preview' in data: 
                 preview_img = data['roi_preview']
                 tk_preview = None
                 if isinstance(preview_img, Image.Image):
                    tk_preview = ImageUtils.make_thumb(preview_img)
                 elif isinstance(preview_img, ImageTk.PhotoImage):
                    tk_preview = preview_img

                 if tk_preview:
                    c = tk.Canvas(base_sec, width=240, height=135, bg='black', highlightthickness=0); c.pack(pady=5)
                    c.create_image(120, 67, image=tk_preview, anchor='center')
                    c.image = tk_preview

             self._btn(base_sec, "📸 截取监控区域", self.app.do_snip)
             param_sec = self._create_section("检测参数")
             self._input(param_sec, "静止持续(s)", 'duration', data.get('duration', 5.0), safe_float)
             self._input(param_sec, "最大超时(s)", 'timeout', data.get('timeout', 20.0), safe_float)
             self._input(param_sec, "灵敏度(0-1)", 'threshold', data.get('threshold', 0.98), safe_float)
             monitor_frame = self._create_section("实时测试")
             self.lbl_monitor_status = tk.Label(monitor_frame, text="等待启动...", bg=monitor_frame.cget('bg'), fg=COLORS['fg_sub'], font=('Consolas', 10))
             self.lbl_monitor_status.pack(fill='x', pady=5)
             self.btn_monitor = self._btn(monitor_frame, "🔴 启动监控", self._toggle_static_monitor)

        elif ntype == 'if_sound':
             sec = self._create_section("声音检测")
             SOUND_MODES = {'has_sound': '检测声音', 'is_silent': '检测静音'}
             curr_mode = data.get('detect_mode', 'has_sound')
             self._combo(sec, "模式", 'detect_mode', list(SOUND_MODES.values()), SOUND_MODES.get(curr_mode), lambda e:self._save('detect_mode', {v: k for k, v in SOUND_MODES.items()}.get(e.widget.get()), self.current_node, refresh_ui=True))
             self._input(sec, "阈值(0-1)", 'threshold', data.get('threshold', 0.02), safe_float)
             self._input(sec, "超时(秒)", 'timeout', data.get('timeout', 10.0), safe_float)
             btn_text = "⏹ 停止" if self.is_monitoring_audio else "🔊 实时监测"
             self.monitor_audio_btn = self._btn(sec, btn_text, self._toggle_audio_monitor)

    def open_window_picker(self):
        top = tk.Toplevel(self.app)
        top.geometry(f"{VW}x{VH}+{VX}+{VY}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(bg="black", cursor="crosshair")
        
        canvas = tk.Canvas(top, bg="black", highlightthickness=0); canvas.pack(fill='both', expand=True)
        
        center_x = user32.GetSystemMetrics(0) // 2 - VX
        center_y = user32.GetSystemMetrics(1) // 2 - VY
        
        info_lbl = canvas.create_text(center_x, 50, text="移动鼠标选择窗口...", fill="white", font=('Microsoft YaHei', 14, 'bold'))
        detail_lbl = canvas.create_text(center_x, 80, text="", fill="#cccccc", font=('Microsoft YaHei', 11))
        self._highlight_rect = canvas.create_rectangle(0, 0, 0, 0, outline='#00ff00', width=4)
        self._temp_win_info = None

        def on_mouse_move(event):
            info = WindowEngine.get_top_window_at_mouse()
            if info and info.get('rect'):
                r = info['rect']
                cx, cy = r.left - VX, r.top - VY
                cw, ch = r.width, r.height
                canvas.coords(self._highlight_rect, cx, cy, cx+cw, cy+ch)
                canvas.itemconfig(info_lbl, text=f"进程: {info['exe_name']}")
                canvas.itemconfig(detail_lbl, text=f"类名: {info['class_name']}\n标题: {info['title']}")
                self._temp_win_info = info

        def on_click(event):
            if self._temp_win_info:
                self._save('exe_name', self._temp_win_info['exe_name'], self.current_node, refresh_ui=False)
                self._save('class_name', self._temp_win_info['class_name'], self.current_node, refresh_ui=False)
                self._save('title', self._temp_win_info['title'], self.current_node, refresh_ui=False)
                self._save('use_exe', True, self.current_node, refresh_ui=False)
                self._save('use_class', True, self.current_node, refresh_ui=False)
                self._save('use_title', False, self.current_node, refresh_ui=True) 
                self.app.log(f"已绑定进程: {self._temp_win_info['exe_name']}", "success")
            top.destroy(); self.app.deiconify()
        top.bind("<Motion>", on_mouse_move); top.bind("<Button-1>", on_click); top.bind("<Escape>", lambda e: [top.destroy(), self.app.deiconify()])

    # Helpers
    def _create_section(self, text):
        f = tk.Frame(self.content, bg=COLORS['bg_panel'], pady=5); f.pack(fill='x')
        tk.Label(f, text=text, bg=COLORS['bg_panel'], fg=COLORS['accent'], font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w')
        tk.Frame(f, height=1, bg=COLORS['bg_header']).pack(fill='x', pady=(2, 5))
        return f
    
    def _input(self, parent, label, key, val, vfunc=None):
        target_node = self.current_node 
        f = tk.Frame(parent, bg=parent.cget('bg')); f.pack(fill='x', pady=2)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left', padx=(0,5))
        
        var = tk.StringVar(value=str(val))
        def on_change(*args):
            new_val = var.get()
            self._save(key, vfunc(new_val) if vfunc else new_val, target_node, refresh_ui=False)
        var.trace_add("write", on_change)
        
        e = tk.Entry(f, bg=COLORS['input_bg'], fg='white', bd=0, insertbackground='white', font=('Microsoft YaHei', int(10 * SCALE_FACTOR)), textvariable=var)
        e.pack(fill='x', pady=2, ipady=3, expand=True)
        e.bind("<FocusOut>", lambda ev: self.app.editor.history.save_state())
        e.bind("<Return>", lambda ev: self.app.editor.focus_set())
        
    def _file_picker(self, parent, label, key, val):
        target_node = self.current_node
        f = tk.Frame(parent, bg=parent.cget('bg')); f.pack(fill='x', pady=2)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left')
        input_container = tk.Frame(f, bg=COLORS['input_bg']); input_container.pack(side='left', fill='x', expand=True, padx=2)
        display_text = os.path.basename(val) if val else "点击选择..."
        if len(display_text) > 20: display_text = display_text[:17] + "..."
        lbl_display = tk.Label(input_container, text=f"📄 {display_text}", bg=COLORS['input_bg'], fg='white' if val else '#888', font=('Microsoft YaHei', int(10 * SCALE_FACTOR)), anchor='w'); lbl_display.pack(side='left', fill='x', expand=True, padx=5)
        if val: 
            def on_enter(e): self.app.log(f"路径: {val}", "info") 
            lbl_display.bind("<Enter>", on_enter)
            tk.Button(input_container, text="×", command=lambda: [self._save(key, "", target_node, refresh_ui=True)], bg=COLORS['input_bg'], fg=COLORS['danger'], bd=0, cursor="hand2", font=('Arial', 10, 'bold')).pack(side='right', padx=2)
        def pick(): 
            if (path := filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All", "*.*")])): self._save(key, path, target_node, refresh_ui=True)
        lbl_display.bind("<Button-1>", lambda e: pick()); input_container.bind("<Button-1>", lambda e: pick()); self._btn_icon(f, "📂", pick)
        
    def _compact_input(self, parent, label, key, val, vfunc=None):
        target_node = self.current_node
        tk.Label(parent, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left', padx=(5,2))
        
        var = tk.StringVar(value=str(val))
        def on_change(*args):
            new_val = var.get()
            self._save(key, vfunc(new_val) if vfunc else new_val, target_node, refresh_ui=False)
        var.trace_add("write", on_change)
        
        e = tk.Entry(parent, bg=COLORS['input_bg'], fg='white', bd=0, width=6, textvariable=var)
        e.pack(side='left', padx=2)
        e.bind("<FocusOut>", lambda ev: self.app.editor.history.save_state())
        e.bind("<Return>", lambda ev: self.app.editor.focus_set())
        
    def _combo(self, parent, label, key, values, val, cmd):
        f = tk.Frame(parent, bg=parent.cget('bg')); f.pack(fill='x', pady=2)
        tk.Label(f, text=label, bg=parent.cget('bg'), fg=COLORS['fg_text'], font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(side='left', padx=(0,5))
        cb = ttk.Combobox(f, values=values, state='readonly', font=('Microsoft YaHei', int(10 * SCALE_FACTOR))); cb.set(val); cb.pack(fill='x', pady=2, expand=True); cb.bind("<<ComboboxSelected>>", cmd)
        
    def _btn(self, parent, txt, cmd, bg=None): return tk.Button(parent, text=txt, command=cmd, bg=bg or COLORS['btn_bg'], fg='white', bd=0, activebackground=COLORS['btn_hover'], relief='flat', pady=2, font=('Microsoft YaHei', int(9 * SCALE_FACTOR))).pack(fill='x', pady=3, ipady=1) or parent.winfo_children()[-1]
    def _btn_icon(self, parent, txt, cmd, bg=None, color=None, width=None): tk.Button(parent, text=txt, command=cmd, bg=bg or COLORS['bg_card'], fg=color or 'white', bd=0, activebackground=COLORS['btn_hover'], relief='flat', width=width).pack(side='right', padx=2)
    
    def _chk(self, parent, txt, key, val):
        target_node = self.current_node
        var = tk.BooleanVar(value=val)
        tk.Checkbutton(parent, text=txt, variable=var, bg=parent.cget('bg'), fg='white', selectcolor=COLORS['bg_app'], activebackground=parent.cget('bg'), borderwidth=0, highlightthickness=0, command=lambda: [self._save(key, var.get(), target_node, refresh_ui=True)]).pack(anchor='w', pady=2)
    
    def _save(self, key, val, node=None, refresh_ui=True):
        target = node if node else self.current_node
        if target: 
            try:
                target.update_data(key, val, refresh_ui=refresh_ui)
            except Exception as e:
                pass

    def _draw_image_preview(self, parent, data):
        c = tk.Canvas(parent, width=240, height=135, bg='black', highlightthickness=0); c.pack(pady=5)
        c.create_image(120, 67, image=data['tk_image'], anchor='center')
        w, h = data['image'].size
        ratio = min(240/w, 135/h) if w > 0 and h > 0 else 0
        dw, dh = int(w * ratio), int(h * ratio); off_x, off_y = (240 - dw) // 2, (135 - dh) // 2
        def on_click(e):
            rx = max(0.0, min(1.0, (e.x - off_x) / dw if dw > 0 else 0))
            ry = max(0.0, min(1.0, (e.y - off_y) / dh if dh > 0 else 0))
            self._save('relative_click_pos', (rx, ry), self.current_node, refresh_ui=True)
        c.bind("<Button-1>", on_click)
        rx, ry = data.get('relative_click_pos', (0.5, 0.5)); cx, cy = off_x + (rx * dw), off_y + (ry * dh)
        c.create_oval(cx-3, cy-3, cx+3, cy+3, fill=COLORS['marker'], outline='white', width=1)

    def open_visual_offset_picker(self):
        self.app.iconify(); time.sleep(0.3); full_screen = ImageGrab.grab(all_screens=True, bbox=(VX, VY, VX+VW, VY+VH))
        try:
            res = VisionEngine.locate(self.current_node.data.get('image'), confidence=0.8, timeout=1.0)
            if not res: self.app.deiconify(); messagebox.showerror("错误", "未在屏幕找到基准图"); return
            top = tk.Toplevel(self.app)
            top.geometry(f"{VW}x{VH}+{VX}+{VY}")
            top.overrideredirect(True)
            top.attributes("-topmost", True); top.config(cursor="crosshair")
            cv = tk.Canvas(top, width=full_screen.width, height=full_screen.height); cv.pack()
            tk_img = ImageTk.PhotoImage(full_screen); cv.create_image(0,0,image=tk_img,anchor='nw')
            
            cv.create_rectangle(res.left-VX, res.top-VY, res.left+res.width-VX, res.top+res.height-VY, outline='green', width=2)
            cx, cy = res.left+res.width/2 - VX, res.top+res.height/2 - VY
            
            cv.create_line(cx-10, cy, cx+10, cy, fill='red', width=2); cv.create_line(cx, cy-10, cx, cy+10, fill='red', width=2)
            line_id = cv.create_line(cx, cy, cx, cy, fill='blue', dash=(4, 4), width=1)
            text_id = cv.create_text(cx, cy, text="Offset: 0, 0", fill='blue', anchor='sw', font=('Consolas', 10, 'bold'))
            
            def on_motion(e): cv.coords(line_id, cx, cy, e.x, e.y); cv.coords(text_id, e.x + 10, e.y - 10); cv.itemconfig(text_id, text=f"Offset: {int(e.x-cx)}, {int(e.y-cy)}")
            def confirm(e): self._save('offset_x', int(e.x-cx), self.current_node, refresh_ui=False); self._save('offset_y', int(e.y-cy), self.current_node, refresh_ui=True); top.destroy(); self.app.deiconify()
            cv.bind("<Motion>", on_motion); cv.bind("<Button-1>", confirm); cv.bind("<Button-3>", lambda e: [top.destroy(), self.app.deiconify()])
            top.img_ref = tk_img; self.wait_window(top)
        except Exception as e: self.app.deiconify(); traceback.print_exc()

    def start_test_match(self): threading.Thread(target=self._test_match_worker, daemon=True).start()
    def _test_match_worker(self):
        self.app.iconify(); time.sleep(0.5); res_txt = "未找到"
        try:
            if self.current_node.type == 'if_img':
                imgs = self.current_node.data.get('images', []); passed = True; screen = VisionEngine.capture_screen()
                for img in imgs:
                    if not VisionEngine._advanced_match(img.get('image'), screen, 0.8, None, True, True, 1.0, 'hybrid')[0]: passed = False; break
                res_txt = "✅ 全部满足" if passed else "❌ 条件不满足"
            else:
                 strategy = self.current_node.data.get('match_strategy', 'hybrid')
                 res = VisionEngine.locate(self.current_node.data.get('image'), confidence=0.8, strategy=strategy)
                 res_txt = "✅ 找到" if res else "❌ 未找到"
        except: pass
        self.app.deiconify(); messagebox.showinfo("测试结果", res_txt)

    def _toggle_static_monitor(self):
        if self.static_monitor_active:
            self.static_monitor_active = False
            self.btn_monitor.config(text="🔴 启动监控", bg=COLORS['btn_bg']); self.lbl_monitor_status.config(text="监控已停止")
        else:
            if not self.current_node.data.get('roi'): messagebox.showwarning("提示", "请先截取监控区域！"); return
            self.static_monitor_active = True
            self.btn_monitor.config(text="⏹ 停止监控", bg=COLORS['danger'])
            threading.Thread(target=self._static_monitor_thread, daemon=True).start()

    def _static_monitor_thread(self):
        roi = self.current_node.data.get('roi')
        thr = safe_float(self.current_node.data.get('threshold', 0.98))
        dur = safe_float(self.current_node.data.get('duration', 5.0))
        
        if self.context['window_handle'] and self.context['window_rect']:
             win_offset_x, win_offset_y = self.context['window_offset']
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
                txt = f"{'🟢 静止' if is_static else '🌊 运动'} | {elapsed:.1f}s / {dur}s"
                color = COLORS['success'] if elapsed >= dur else (COLORS['fg_text'] if is_static else COLORS['warning'])
                self.app.after(0, lambda t=txt, c=color: self.lbl_monitor_status.config(text=t, fg=c))
            if not is_static: static_start = time.time(); last_frame = curr
            time.sleep(0.1)
        self.static_monitor_active = False

    def _toggle_audio_monitor(self):
        self.is_monitoring_audio = not self.is_monitoring_audio
        self.monitor_audio_btn.config(text="⏹ 停止" if self.is_monitoring_audio else "🔊 实时监测")
        if self.is_monitoring_audio: threading.Thread(target=self._audio_monitor_thread, daemon=True).start()

    def _audio_monitor_thread(self):
        while self.is_monitoring_audio and self.winfo_exists():
            vol = AudioEngine.get_max_audio_peak()
            if vol > 0.001: self.app.log(f"📊 音量峰值: {vol:.4f}", "info")
            time.sleep(0.5)

# --- 7. 设置对话框 ---
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent); self.app = app
        self.title("设置"); self.geometry("400x300"); self.config(bg=COLORS['bg_panel'])
        self.resizable(False, False); self.transient(parent); self.grab_set()
        self.app.stop_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))

        f_theme = tk.Frame(self, bg=COLORS['bg_panel'], pady=10, padx=20); f_theme.pack(fill='x')
        tk.Label(f_theme, text="界面主题:", bg=COLORS['bg_panel'], fg=COLORS['fg_text']).pack(side='left')
        self.combo_theme = ttk.Combobox(f_theme, values=list(THEMES.keys()), state='readonly'); self.combo_theme.set(SETTINGS.get('theme', 'Dark')); self.combo_theme.pack(side='right', fill='x', expand=True, padx=10)

        f_hk = tk.Frame(self, bg=COLORS['bg_panel'], pady=10, padx=20); f_hk.pack(fill='x')
        self.hk_vars = {'start': tk.StringVar(value=SETTINGS.get('hotkey_start', '<f9>')), 'stop': tk.StringVar(value=SETTINGS.get('hotkey_stop', '<f10>'))}
        self._create_hotkey_entry(f_hk, "启动快捷键:", 'start', 0)
        self._create_hotkey_entry(f_hk, "停止快捷键:", 'stop', 1)
        f_hk.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(self, bg=COLORS['bg_panel'], pady=20); btn_frame.pack(side='bottom', fill='x')
        tk.Button(btn_frame, text="保存并重启UI", command=self.save, bg=COLORS['accent'], fg='white', bd=0, padx=20).pack(side='right', padx=20)
        tk.Button(btn_frame, text="取消", command=self.on_cancel, bg=COLORS['btn_bg'], fg='white', bd=0, padx=20).pack(side='right')

    def _create_hotkey_entry(self, parent, label, key, row):
        tk.Label(parent, text=label, bg=COLORS['bg_panel'], fg=COLORS['fg_text']).grid(row=row, column=0, sticky='w', pady=5)
        e = tk.Entry(parent, textvariable=self.hk_vars[key], bg=COLORS['input_bg'], fg='white', insertbackground='white', readonlybackground=COLORS['input_bg'])
        e.grid(row=row, column=1, sticky='ew', padx=10)
        e.bind("<FocusIn>", lambda ev: e.config(state='normal', bg=COLORS['accent']))
        e.bind("<KeyPress>", lambda ev: self._on_key(ev, key))
        e.bind("<Button-3>", lambda ev: self.hk_vars[key].set("")) 

    def _on_key(self, event, key):
        if event.keysym in ['Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Win_L', 'Win_R']: return 
        if event.keysym == 'Escape': self.hk_vars[key].set(""); self.focus_set(); return "break"
        
        parts = []
        if event.state & 0x0004: parts.append("<ctrl>")
        if event.state & 0x20000 or event.state & 0x0008: parts.append("<alt>") 
        if event.state & 0x0001: parts.append("<shift>")
        
        sym = event.keysym.lower()
        if len(sym) > 1 and sym.startswith('f') and sym[1:].isdigit():
            sym = f"<{sym}>"
        elif sym.startswith('kp_'):
            if sym == 'kp_enter': sym = '<enter>'
            elif sym.replace('kp_', '').isdigit(): sym = sym.replace('kp_', '') 
            else: sym = f"<{sym}>"
        
        parts.append(sym)
        self.hk_vars[key].set("+".join(parts)); return "break" 
    
    def on_cancel(self): self.app.refresh_hotkeys(); self.destroy()
    def save(self):
        SETTINGS['theme'] = self.combo_theme.get(); SETTINGS['hotkey_start'] = self.hk_vars['start'].get(); SETTINGS['hotkey_stop'] = self.hk_vars['stop'].get()
        COLORS.update(THEMES.get(SETTINGS['theme'], THEMES['Dark'])); self.app.refresh_hotkeys(); self.app.restart_ui(); self.destroy()

# --- 8. 主程序 ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.geometry("1400x1100")
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception: pass
        
        self.core = AutomationCore(self.log, self); self.log_q = queue.Queue()
        self.drag_node_type, self.drag_ghost = None, None
        self.hotkey_listener = None
        self._setup_ui(); self.refresh_hotkeys()
        
        self.bind("<Control-s>", lambda e: self.save())
        
        self.update_title()
        self.after(100, self._poll_log)
        self.after(500, self.show_welcome_guide)

    def update_title(self):
        filename = os.path.basename(self.current_file_path) if self.current_file_path else "未命名"
        self.title(f"Qflow 1.7.5 - QwejayHuang - {filename}")

    def _setup_ui(self):
        self.configure(bg=COLORS['bg_app'])
        for widget in self.winfo_children(): widget.destroy()

        title_bar = tk.Frame(self, bg=COLORS['bg_app'], height=50); title_bar.pack(fill='x', pady=5, padx=20)
        tk.Label(title_bar, text="QFLOW", font=('Impact', 24), bg=COLORS['bg_app'], fg=COLORS['accent']).pack(side='left', padx=(0, 20))
        
        ops = tk.Frame(title_bar, bg=COLORS['bg_app']); ops.pack(side='left')
        for txt, cmd in [("📂 打开", self.load), ("💾 保存", self.save), ("📝 另存", self.save_as), ("🗑️ 清空", self.clear), ("⚙️ 设置", self.open_settings)]:
            tk.Button(ops, text=txt, command=cmd, bg=COLORS['bg_header'], fg='white', bd=0, padx=10, cursor='hand2', font=('Microsoft YaHei', 9)).pack(side='left', padx=2)
            
        self.btn_run = tk.Button(title_bar, text="▶ 启动", command=lambda: self.toggle_run(None), bg=COLORS['success'], fg='#1f1f1f', font=('Microsoft YaHei', 11, 'bold'), padx=15, bd=0, cursor='hand2'); self.btn_run.pack(side='right')
        self.btn_pause = tk.Button(title_bar, text="⏸ 暂停", command=self.toggle_pause, bg=COLORS['warning'], fg='#1f1f1f', bd=0, padx=10, state='disabled', cursor='hand2', font=('Microsoft YaHei', 9)); self.btn_pause.pack(side='right', padx=10)
        
        self.main_paned = tk.PanedWindow(self, orient='vertical', bg=COLORS['bg_app'], sashwidth=4, bd=0)
        self.main_paned.pack(fill='both', expand=True, padx=10, pady=(0, 5))
        
        h_paned = tk.PanedWindow(self.main_paned, orient='horizontal', bg=COLORS['bg_app'], sashwidth=4, bd=0)
        self.main_paned.add(h_paned, stretch="always")
        
        toolbox = tk.Frame(h_paned, bg=COLORS['bg_sidebar'])
        self._build_toolbox(toolbox)
        h_paned.add(toolbox, minsize=160, width=180)
        
        self.editor = FlowEditor(h_paned, self); h_paned.add(self.editor, minsize=400, stretch="always")
        self.property_panel = PropertyPanel(h_paned, self); h_paned.add(self.property_panel, minsize=280, width=180)
        
        self.log_panel = LogPanel(self.main_paned)
        self.main_paned.add(self.log_panel, minsize=80, height=130) # 状态栏默认高度
        
        self.editor.add_node('start', 100, 100, save_history=False)

    def _build_toolbox(self, p):
        canvas = tk.Canvas(p, bg=COLORS['bg_sidebar'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        content = tk.Frame(canvas, bg=COLORS['bg_sidebar'])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", tags="inner")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("inner", width=e.width))
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def _bind_mousewheel(widget):
            widget.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        content.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        tool_groups = [
            ("应用控制", ['open_app', 'bind_win', 'cmd', 'web']),
            ("逻辑组件", ['start', 'end', 'loop', 'sequence', 'set_var', 'var_switch', 'clipboard', 'notify']),
            ("动作执行", ['mouse', 'keyboard', 'wait']),
            ("视觉/感知", ['image', 'if_img', 'if_static', 'if_sound'])
        ]
        
        for title, items in tool_groups:
            lbl = tk.Label(content, text=title, bg=COLORS['bg_sidebar'], fg=COLORS['fg_sub'], font=('Microsoft YaHei', 9, 'bold'), pady=8)
            lbl.pack(anchor='w', padx=10)
            _bind_mousewheel(lbl)
            for t in items:
                if t not in NODE_CONFIG: continue
                f = tk.Frame(content, bg=COLORS['bg_card'], cursor="hand2", pady=2)
                f.pack(fill='x', pady=1, padx=8)
                tk.Frame(f, bg=NODE_CONFIG[t]['color'], width=4).pack(side='left', fill='y')
                l = tk.Label(f, text=NODE_CONFIG[t]['title'], bg=COLORS['bg_card'], fg=COLORS['fg_text'], font=('Microsoft YaHei', 9), anchor='w', padx=8, pady=6)
                l.pack(side='left', fill='both', expand=True)
                
                if 'desc' in NODE_CONFIG[t]: ToolTip(l, NODE_CONFIG[t]['desc'])
                
                _bind_mousewheel(f); _bind_mousewheel(l)
                
                for w in [f, l]: 
                    w.bind("<ButtonPress-1>", lambda e, t=t: self.on_drag_start(e, t))
                    w.bind("<B1-Motion>", self.on_drag_move)
                    w.bind("<ButtonRelease-1>", self.on_drag_end)

    def on_drag_start(self,e,t): self.drag_node_type=t; self.drag_ghost=tk.Toplevel(self); self.drag_ghost.overrideredirect(True); self.drag_ghost.attributes("-alpha",0.7); tk.Label(self.drag_ghost,text=NODE_CONFIG[t]['title'],bg=COLORS['accent'], font=('Microsoft YaHei', 9)).pack()
    def on_drag_move(self,e): (self.drag_ghost and self.drag_ghost.geometry(f"+{e.x_root+10}+{e.y_root+10}"))
    def on_drag_end(self,e):
        if self.drag_ghost: self.drag_ghost.destroy(); self.drag_ghost=None
        if self.editor.winfo_containing(e.x_root, e.y_root) == self.editor: self.editor.add_node(self.drag_node_type, self.editor.canvasx(e.x_root-self.editor.winfo_rootx())/self.editor.zoom, self.editor.canvasy(e.y_root-self.editor.winfo_rooty())/self.editor.zoom)

    def do_snip(self): self.iconify(); self.update(); self.after(400, lambda: self._start_snip_overlay())
    
    def _start_snip_overlay(self):
        top = tk.Toplevel(self)
        top.geometry(f"{VW}x{VH}+{VX}+{VY}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(cursor="cross", bg="black")
        
        c = tk.Canvas(top, bg="black", highlightthickness=0); c.pack(fill='both', expand=True)
        s, r = [0, 0], [None]
        
        def dn(e): s[0], s[1] = e.x, e.y; (r[0] and c.delete(r[0])); r[0] = c.create_rectangle(e.x, e.y, e.x, e.y, outline='red', width=2)
        def mv(e): (r[0] and c.coords(r[0], s[0], s[1], e.x, e.y))
        def up(e): 
            x1 = min(s[0], e.x) + VX
            y1 = min(s[1], e.y) + VY
            x2 = max(s[0], e.x) + VX
            y2 = max(s[1], e.y) + VY
            top.destroy(); self.after(200, lambda: self._capture((x1, y1, x2, y2)))
            
        c.bind("<ButtonPress-1>", dn); c.bind("<B1-Motion>", mv); c.bind("<ButtonRelease-1>", up); top.bind("<Escape>", lambda e: [top.destroy(), self.deiconify()])

    def _capture(self, rect):
        x1, y1, x2, y2 = rect
        if x2 - x1 < 5 or y2 - y1 < 5: 
            self.deiconify()
            return
        
        try:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
            self.deiconify()
            
            if (n := self.property_panel.current_node): 
                # 修复: 保存修改前状态，便于后续 Ctrl+Z 撤销
                self.editor.history.save_state() 
                
                if n.type == 'if_img': 
                    imgs = n.data.get('images', []).copy() # 拷贝防止直接污染引用
                    imgs.append({'id': uuid.uuid4().hex, 'image': img, 'tk_image': ImageUtils.make_thumb(img), 'b64': ImageUtils.img_to_b64(img)})
                    n.update_data('images', imgs, refresh_ui=False)
                elif n.type == 'if_static':
                    n.update_data('roi', (x1, y1, x2-x1, y2-y1), refresh_ui=False)
                    n.update_data('roi_preview', img, refresh_ui=False)
                    n.update_data('b64_preview', ImageUtils.img_to_b64(img), refresh_ui=False)
                    n.draw()
                else: 
                    n.update_data('image', img, refresh_ui=False)
                    n.update_data('tk_image', ImageUtils.make_thumb(img), refresh_ui=False)
                    n.update_data('b64', ImageUtils.img_to_b64(img), refresh_ui=False)
                    
                n.draw() 
                self.property_panel.load_node(n)
            self.log(f"🖼️ 截取成功 ({x1},{y1})", "success")
            
        except Exception as e: 
            self.deiconify()
            self.log(f"截图失败: {e}", "error")

    def get_active_bind_window_info(self):
        """查找流程中配置的窗口绑定节点，若窗口处于打开状态，则返回句柄、边界矩形及标题"""
        for nid, node in self.editor.nodes.items():
            if node.type == 'bind_win':
                exe_name = node.data.get('exe_name', '')
                class_name = node.data.get('class_name', '')
                title = node.data.get('title', '')
                use_exe = bool(node.data.get('use_exe', True))
                use_class = bool(node.data.get('use_class', True))
                use_title = bool(node.data.get('use_title', False))
                target_exe = exe_name if use_exe else None
                target_class = class_name if use_class else None
                target_title = title if use_title else None
                if not target_exe and not target_class and not target_title: 
                    target_title = title
                hwnd = WindowEngine.smart_find_window(target_exe, target_class, target_title)
                if hwnd:
                    rect = WindowEngine.get_window_rect(hwnd)
                    if rect:
                        return {'hwnd': hwnd, 'rect': rect, 'title': title or exe_name or class_name or "未命名窗口"}
        return None

    # --- 统一集成的智能拾取机制 ---
    def pick_coordinate(self): 
        self.iconify()
        self.after(400, lambda: self._coord_overlay('x', 'y'))
        
    def pick_start_coordinate(self): 
        self.iconify()
        self.after(400, lambda: self._coord_overlay('start_x', 'start_y'))
        
    def pick_end_coordinate(self): 
        self.iconify()
        self.after(400, lambda: self._coord_overlay('end_x', 'end_y'))

    def _coord_overlay(self, key_x='x', key_y='y'):
        top = tk.Toplevel(self)
        top.geometry(f"{VW}x{VH}+{VX}+{VY}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(cursor="cross", bg="black")
        
        c = tk.Canvas(top, bg="black", highlightthickness=0)
        c.pack(fill='both', expand=True)

        # 智能匹配窗口绑定状态
        bind_info = self.get_active_bind_window_info()
        rect = bind_info['rect'] if bind_info else None
        
        if rect:
            # 扣除多显示器虚拟桌面起始坐标，转为拾取窗口内的画布坐标
            cx1, cy1 = rect.left - VX, rect.top - VY
            cx2, cy2 = (rect.left + rect.width) - VX, (rect.top + rect.height) - VY
            
            # 在全屏覆盖层上使用高亮虚线框勾勒出用户绑定的窗口边界
            c.create_rectangle(cx1, cy1, cx2, cy2, outline='#64b5f6', width=3, dash=(4,4))
            c.create_text(cx1 + 10, cy1 + 20, text=f"⚓ 绑定窗口范围: {bind_info['title']}", fill='#64b5f6', font=('Microsoft YaHei', 11, 'bold'), anchor='w')
            c.create_text(VW//2, 50, text="[当前为：窗口绑定模式] 拾取的坐标已自动扣除窗口左上角偏移量（保存为相对坐标）", fill='#81c784', font=('Microsoft YaHei', 13, 'bold'), anchor='center')
        else:
            c.create_text(VW//2, 50, text="[当前为：绝对坐标模式] 未检测到运行中的绑定窗口，将保存为绝对屏幕坐标", fill='#ffd54f', font=('Microsoft YaHei', 13, 'bold'), anchor='center')

        c.create_text(VW//2, 85, text="点击鼠标左键确认拾取 | 按键盘 ESC 可直接取消返回", fill='#ffffff', font=('Microsoft YaHei', 11), anchor='center')

        def clk(e): 
            top.destroy()
            self.deiconify()
            
            # 使用 Windows 原生 API 检索鼠标当前全局物理绝对坐标，彻底根治多屏与缩放导致的偏移 Bug
            class POINT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            abs_x, abs_y = pt.x, pt.y
            
            final_x, final_y = abs_x, abs_y
            if rect:
                # 求出物理绝对坐标同目标绑定窗口左上角起点的差值
                final_x = abs_x - rect.left
                final_y = abs_y - rect.top
                self.log(f"📍 坐标拾取完成: 相对坐标 ({final_x}, {final_y}) (屏幕绝对坐标: {abs_x}, {abs_y})", "success")
            else:
                self.log(f"📍 坐标拾取完成: 绝对屏幕坐标 ({final_x}, {final_y})", "success")
            
            if self.property_panel.current_node:
                self.property_panel.current_node.update_data(key_x, final_x)
                self.property_panel.current_node.update_data(key_y, final_y)
                self.property_panel.load_node(self.property_panel.current_node)
        
        c.bind("<Button-1>", clk)
        top.bind("<Escape>", lambda ev: [top.destroy(), self.deiconify()])

    # 快捷键与运行控制
    def refresh_hotkeys(self):
        if self.hotkey_listener: self.hotkey_listener.stop()
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({SETTINGS['hotkey_start']: self.on_hotkey_start, SETTINGS['hotkey_stop']: self.on_hotkey_stop})
            self.hotkey_listener.start()
        except Exception: pass
    def stop_hotkeys(self):
        if self.hotkey_listener: self.hotkey_listener.stop(); self.hotkey_listener = None
    def on_hotkey_start(self):
        if not self.core.running: self.log("⌨️ 快捷键启动", "info"); self.after(0, lambda: self.toggle_run(None))
    def on_hotkey_stop(self):
        if self.core.running: self.log("⌨️ 快捷键停止", "warning"); self.core.stop()
    def open_settings(self): SettingsDialog(self, self)
    def restart_ui(self): data = self.editor.get_data(); self._setup_ui(); self.editor.load_data(data)

    def toggle_run(self, start_id): 
        self.editor.focus_set()
        if self.core.running: self.core.stop()
        else: self.btn_run.config(text="⏹ 停止", bg=COLORS['danger']); self.btn_pause.config(state='normal', text="⏸ 暂停", bg=COLORS['warning']); self.core.load_project(self.editor.get_data()); self.core.start(start_id)
    def toggle_pause(self): (self.core.resume() if self.core.paused else self.core.pause())
    def update_debug_btn_state(self, paused): self.btn_pause.config(text="▶ 继续" if paused else "⏸ 暂停", bg=COLORS['success'] if paused else COLORS['warning'])
    def reset_ui_state(self): self.core.running=False; self.btn_run.config(text="▶ 启动", bg=COLORS['success']); self.btn_pause.config(text="⏸ 暂停", bg=COLORS['warning'], state='disabled'); [self.highlight_node_safe(n, None) for n in self.editor.nodes]
    def log(self,msg, level='info'): self.log_q.put((msg, level))
    def _poll_log(self):
        while not self.log_q.empty(): item = self.log_q.get(); self.log_panel.add_log(item[0], item[1])
        self.after(100,self._poll_log)
    def highlight_node_safe(self, nid, status=None):
        def _task():
            if not self.editor.winfo_exists(): return
            self.editor.delete("hl")
            if nid and nid in self.editor.nodes and status:
                n = self.editor.nodes[nid]; z = self.editor.zoom; color = COLORS.get(f"hl_{status}", COLORS['hl_ok'])
                self.editor.create_rectangle(n.x * z - 3 * z, n.y * z - 3 * z, (n.x + n.w) * z + 3 * z, (n.y + n.h) * z + 3 * z, outline=color, width=3 * z, tags="hl")
        self.after(0, _task)
    def select_node_safe(self, nid): self.after(0, lambda: self.editor.select_node(nid))
    
    def save(self):
        if self.current_file_path:
            try:
                with open(self.current_file_path, 'w', encoding='utf-8') as fp:
                    json.dump(self.editor.get_data(), fp, ensure_ascii=False, indent=2)
                self.log(f"💾 已保存到: {self.current_file_path}", "success")
                self.update_title()
            except Exception as e:
                self.log(f"❌ 保存失败: {e}", "error")
        else:
            self.save_as()
            
    def save_as(self):
        if (f:=filedialog.asksaveasfilename(defaultextension=".qflow", filetypes=[("Qflow", "*.qflow"), ("All", "*.*")])): 
            self.current_file_path = f
            self.save()
            
    def load(self):
        if (f:=filedialog.askopenfilename(filetypes=[("Qflow", "*.qflow"), ("All", "*.*")])): 
            try:
                with open(f, 'r', encoding='utf-8') as fp: 
                    self.editor.load_data(json.load(fp))
                self.current_file_path = f
                self.update_title()
                self.log(f"📂 已加载: {f}", "success")
            except Exception as e:
                self.log(f"❌ 加载失败: {e}", "error")
                
    def clear(self): 
        self.editor.load_data({'nodes':{},'links':[]})
        self.current_file_path = None
        self.update_title()

    def show_welcome_guide(self):
        self.log("✨ 欢迎使用 Qflow-AI办公自动化软件！", "success")
        self.log("*.  快速上手指引：", "info")
        self.log("1. 【添加节点】从左侧工具栏直接 [拖动] 节点图标到中间画布。", "info")
        self.log("2. 【建立连线】点击节点右侧 of [○ 端口] 并拖动到另一个节点上。", "info")
        self.log("3. 【配置属性】单选画布上的节点，在右侧面板设置具体参数。", "info")
        self.log("4. 【右键菜单】右键点击 [节点] 可复制或删除；右键点击 [端口] 可清除连线。", "warning")
        self.log("5. 【运行控制】点击上方 [▶ 启动] 或使用快捷键 F9 (启动) / F10 (停止)。", "success")

if __name__ == "__main__": App().mainloop()

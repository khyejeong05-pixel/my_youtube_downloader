import os
import sys
import json
import time
import shutil
import queue
import urllib.request
import io
import threading
import datetime
import webbrowser
from tkinter import messagebox, filedialog
import tkinter as tk
import customtkinter as ctk
from PIL import Image
import yt_dlp

# CustomTkinter 기본 설정
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DownloadCancelledException(Exception):
    """사용자가 다운로드를 취소했을 때 발생시키는 예외"""
    pass

class DownloadTask:
    """각 다운로드 작업의 상태와 메타데이터를 저장하는 클래스"""
    def __init__(self, task_id, url, format_type, title="영상 정보를 가져오는 중..."):
        self.id = task_id
        self.url = url
        self.format_type = format_type
        self.title = title
        self.thumbnail_url = None
        self.thumbnail_img = None
        self.thumbnail_displayed = False
        self.duration = None
        
        # 다운로드 진행 상태 관련 변수들
        self.status = 'fetching'  # fetching, queued, downloading, converting, completed, failed, cancelled
        self.progress = 0.0
        self.speed_str = "0 KB/s"
        self.eta_str = "남은 시간: 계산 중..."
        self.downloaded_bytes_str = "0 MB / 0 MB"
        self.error_message = ""
        self.cancelled = False
        
        # UI 카드 프레임 내 위젯 참조들
        self.card_frame = None
        self.thumbnail_label = None
        self.title_label = None
        self.status_label = None
        self.progress_bar = None
        self.action_button = None

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity 유튜브 다운로더 v1.0")
        self.root.geometry("950, 700")
        self.root.minsize(850, 600)
        
        # 스레드 동기화 락 및 작업 리스트
        self.lock = threading.Lock()
        self.tasks = []
        self.task_counter = 0
        self.running = True
        
        # 설정 불러오기
        self.settings = self.load_settings()
        
        # ffmpeg 감지 여부 (시스템 PATH 및 로컬 실행 파일 체크)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        has_local_ffmpeg = os.path.exists(os.path.join(script_dir, 'ffmpeg.exe')) or os.path.exists(os.path.join(os.getcwd(), 'ffmpeg.exe'))
        self.ffmpeg_available = (shutil.which('ffmpeg') is not None) or has_local_ffmpeg
        
        # UI 위젯 그리기
        self.create_widgets()
        
        # 클립보드 감시 백그라운드 스레드 시작
        self.clipboard_thread = threading.Thread(target=self.clipboard_monitor_worker, daemon=True)
        self.clipboard_thread.start()
        
        # UI 실시간 업데이트 루프 시작
        self.root.after(100, self.update_ui_loop)
        
        # 종료 이벤트 바인딩
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        config_path = os.path.join(os.getcwd(), 'config.json')
        default_save_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(default_save_dir):
            default_save_dir = os.path.expanduser('~')
            
        default_settings = {
            'save_dir': default_save_dir,
            'clipboard_monitor': False,
            'max_downloads': 2
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    for k, v in default_settings.items():
                        if k not in settings:
                            settings[k] = v
                    return settings
            except Exception:
                return default_settings
        return default_settings

    def save_settings(self):
        config_path = os.path.join(os.getcwd(), 'config.json')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"설정 저장 실패: {e}")

    def create_widgets(self):
        # 전체 그리드 설정 (상단 입력부 / 중앙 리스트 / 하단 설정부)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # ----------------------------------------------------
        # 1. 상단 프레임 (URL 입력, 화질 선택, 추가 버튼)
        # ----------------------------------------------------
        top_frame = ctk.CTkFrame(self.root, height=130, corner_radius=10, fg_color="#1E1E2E")
        top_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=1)
        
        # 타이틀 및 타이틀 스타일 데코레이션
        title_label = ctk.CTkLabel(
            top_frame, 
            text="✨ ANTIGRAVITY YOUTUBE DOWNLOADER", 
            font=ctk.CTkFont(family="Malgun Gothic", size=18, weight="bold"),
            text_color="#7F5AF0"
        )
        title_label.grid(row=0, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")
        
        # URL 입력창
        self.url_entry = ctk.CTkEntry(
            top_frame, 
            placeholder_text="유튜브 동영상 또는 재생목록 주소(URL)를 입력하세요...",
            font=ctk.CTkFont(family="Malgun Gothic", size=13),
            height=38,
            fg_color="#1A1A24",
            border_color="#3F3F46"
        )
        self.url_entry.grid(row=1, column=0, padx=(15, 5), pady=(5, 15), sticky="ew")
        
        # 붙여넣기 버튼
        paste_btn = ctk.CTkButton(
            top_frame,
            text="📋 붙여넣기",
            width=90,
            height=38,
            font=ctk.CTkFont(family="Malgun Gothic", size=12, weight="bold"),
            fg_color="#2B2B36",
            hover_color="#3F3F46",
            cursor="hand2",
            command=self.paste_from_clipboard
        )
        paste_btn.grid(row=1, column=1, padx=5, pady=(5, 15), sticky="e")
        
        # 화질/포맷 선택창
        self.format_menu = ctk.CTkOptionMenu(
            top_frame,
            values=[
                "최고 화질 비디오 (MP4)",
                "1080p 고화질 비디오 (MP4)",
                "720p 일반 비디오 (MP4)",
                "480p 저화질 비디오 (MP4)",
                "MP3 고음질 오디오 (음악 추출)",
                "M4A 일반 오디오 (음악 추출)"
            ],
            width=200,
            height=38,
            font=ctk.CTkFont(family="Malgun Gothic", size=12),
            dropdown_font=ctk.CTkFont(family="Malgun Gothic", size=12),
            fg_color="#2B2B36",
            button_color="#2B2B36",
            button_hover_color="#3F3F46"
        )
        self.format_menu.grid(row=1, column=2, padx=5, pady=(5, 15), sticky="e")
        self.format_menu.set("최고 화질 비디오 (MP4)")
        
        # 다운로드 버튼
        download_btn = ctk.CTkButton(
            top_frame,
            text="📥 다운로드 추가",
            width=130,
            height=38,
            font=ctk.CTkFont(family="Malgun Gothic", size=13, weight="bold"),
            fg_color="#7F5AF0",
            hover_color="#6A49D8",
            cursor="hand2",
            command=self.on_download_click
        )
        download_btn.grid(row=1, column=3, padx=(5, 15), pady=(5, 15), sticky="e")
        
        # ----------------------------------------------------
        # 2. 중앙 프레임 (다운로드 리스트 스크롤 영역)
        # ----------------------------------------------------
        self.list_frame = ctk.CTkScrollableFrame(self.root, corner_radius=10, fg_color="#161622")
        self.list_frame.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        
        # 빈 상태 리스트 안내 문구
        self.empty_label = ctk.CTkLabel(
            self.list_frame,
            text="📥 추가된 다운로드 작업이 없습니다.\n유튜브 URL을 입력하고 다운로드 추가를 눌러주세요.",
            font=ctk.CTkFont(family="Malgun Gothic", size=14),
            text_color="#71717A"
        )
        self.empty_label.pack(pady=100)
        
        # ----------------------------------------------------
        # 3. 하단 프레임 (설정, 저장폴더, ffmpeg 경고, 업데이트)
        # ----------------------------------------------------
        bottom_frame = ctk.CTkFrame(self.root, height=90, corner_radius=10, fg_color="#1E1E2E")
        bottom_frame.grid(row=2, column=0, padx=15, pady=(10, 15), sticky="nsew")
        
        # 폴더 경로 레이블
        self.folder_label = ctk.CTkLabel(
            bottom_frame,
            text=f"저장 폴더: {self.settings['save_dir']}",
            font=ctk.CTkFont(family="Malgun Gothic", size=11),
            text_color="#94A3B8"
        )
        self.folder_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 2), sticky="w")
        
        # 폴더 변경 버튼
        change_folder_btn = ctk.CTkButton(
            bottom_frame,
            text="📁 폴더 변경",
            width=100,
            height=28,
            font=ctk.CTkFont(family="Malgun Gothic", size=11, weight="bold"),
            fg_color="#2B2B36",
            hover_color="#3F3F46",
            cursor="hand2",
            command=self.change_save_folder
        )
        change_folder_btn.grid(row=1, column=0, padx=(15, 5), pady=(2, 10), sticky="w")
        
        # 폴더 열기 버튼
        open_folder_btn = ctk.CTkButton(
            bottom_frame,
            text="📂 폴더 열기",
            width=100,
            height=28,
            font=ctk.CTkFont(family="Malgun Gothic", size=11, weight="bold"),
            fg_color="#2B2B36",
            hover_color="#3F3F46",
            cursor="hand2",
            command=self.open_save_folder
        )
        open_folder_btn.grid(row=1, column=1, padx=5, pady=(2, 10), sticky="w")
        
        # 클립보드 감시 토글 스위치
        self.clip_switch = ctk.CTkSwitch(
            bottom_frame,
            text="📋 클립보드 링크 자동 감지",
            font=ctk.CTkFont(family="Malgun Gothic", size=11),
            progress_color="#7F5AF0",
            command=self.toggle_clipboard_monitor
        )
        self.clip_switch.grid(row=1, column=2, padx=20, pady=(2, 10), sticky="w")
        if self.settings['clipboard_monitor']:
            self.clip_switch.select()
            
        # 동시 다운로드 수 선택
        concurrent_label = ctk.CTkLabel(
            bottom_frame,
            text="동시 다운로드:",
            font=ctk.CTkFont(family="Malgun Gothic", size=11),
            text_color="#94A3B8"
        )
        concurrent_label.grid(row=1, column=3, padx=(10, 5), pady=(2, 10), sticky="e")
        
        self.concurrent_menu = ctk.CTkOptionMenu(
            bottom_frame,
            values=["1", "2", "3", "4", "5"],
            width=65,
            height=28,
            font=ctk.CTkFont(family="Malgun Gothic", size=11),
            fg_color="#2B2B36",
            button_color="#2B2B36",
            button_hover_color="#3F3F46",
            command=self.change_max_downloads
        )
        self.concurrent_menu.grid(row=1, column=4, padx=5, pady=(2, 10), sticky="w")
        self.concurrent_menu.set(str(self.settings['max_downloads']))
        
        # yt-dlp 업데이트 버튼
        update_btn = ctk.CTkButton(
            bottom_frame,
            text="🔄 다운로더 엔진(yt-dlp) 업데이트",
            width=200,
            height=28,
            font=ctk.CTkFont(family="Malgun Gothic", size=11, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#1D4ED8",
            cursor="hand2",
            command=self.update_ytdlp
        )
        update_btn.grid(row=1, column=5, padx=15, pady=(2, 10), sticky="e")
        bottom_frame.grid_columnconfigure(5, weight=1)
        
        # ffmpeg 경고 메시지 표시
        if not self.ffmpeg_available:
            self.ffmpeg_warn_label = ctk.CTkLabel(
                bottom_frame,
                text="⚠️ ffmpeg이 설치되어 있지 않습니다. 일부 고화질 다운로드(1080p 이상) 및 MP3 추출 시 최적의 화질/포맷으로 변환이 제한될 수 있습니다.",
                font=ctk.CTkFont(family="Malgun Gothic", size=10, weight="bold"),
                text_color="#EF4444"
            )
            self.ffmpeg_warn_label.grid(row=2, column=0, columnspan=6, padx=15, pady=(0, 5), sticky="w")

    # ----------------------------------------------------
    # 기능 구현 함수들
    # ----------------------------------------------------
    def paste_from_clipboard(self):
        try:
            clipboard_text = self.root.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, clipboard_text.strip())
        except Exception:
            pass

    def toggle_clipboard_monitor(self):
        self.settings['clipboard_monitor'] = bool(self.clip_switch.get())
        self.save_settings()

    def change_max_downloads(self, val):
        self.settings['max_downloads'] = int(val)
        self.save_settings()
        self.process_queue()

    def change_save_folder(self):
        selected_dir = filedialog.askdirectory(initialdir=self.settings['save_dir'], title="다운로드 저장 폴더 선택")
        if selected_dir:
            self.settings['save_dir'] = os.path.abspath(selected_dir)
            self.folder_label.configure(text=f"저장 폴더: {self.settings['save_dir']}")
            self.save_settings()

    def open_save_folder(self):
        save_dir = self.settings['save_dir']
        if os.path.exists(save_dir):
            os.startfile(save_dir)
        else:
            messagebox.showerror("오류", "저장 폴더가 존재하지 않거나 액세스할 수 없습니다.")

    def update_ytdlp(self):
        def worker():
            try:
                # subprocess로 pip upgrade yt-dlp 실행
                import subprocess
                self.root.after(0, lambda: messagebox.showinfo("업데이트", "yt-dlp 다운로더 엔진 업데이트를 시작합니다. 잠시만 기다려주세요."))
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    capture_output=True, text=True, check=True
                )
                self.root.after(0, lambda: messagebox.showinfo("성공", "yt-dlp 엔진이 성공적으로 업데이트되었습니다!"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("오류", f"엔진 업데이트에 실패했습니다:\n{e}"))
        
        threading.Thread(target=worker, daemon=True).start()

    def on_download_click(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("입력 필요", "유튜브 동영상 링크를 입력해주세요.")
            return
            
        format_type = self.format_menu.get()
        self.url_entry.delete(0, tk.END)
        
        # 목록 비우기 라벨 숨기기
        if self.empty_label:
            self.empty_label.pack_forget()
            self.empty_label = None
            
        # 다운로드 작업 객체 생성 및 큐 추가
        self.add_download_task(url, format_type)

    def add_download_task(self, url, format_type, title="영상 정보를 불러오는 중..."):
        with self.lock:
            self.task_counter += 1
            task_id = self.task_counter
            task = DownloadTask(task_id, url, format_type, title)
            self.tasks.append(task)
            
        # 첫 단계: 정보 추출 스레드 기동
        threading.Thread(target=self.fetch_info_worker, args=(task,), daemon=True).start()

    def fetch_info_worker(self, task):
        # yt-dlp 메타데이터 고속 추출
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True, # 플레이리스트 등의 메타데이터를 신속 추출하기 위함
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(task.url, download=False)
                
            if not info:
                raise Exception("동영상 정보를 가져올 수 없습니다.")
                
            # 플레이리스트 형식인 경우 개별 작업으로 분리
            if 'entries' in info:
                entries = list(info['entries'])
                
                # 기존의 "정보 추출용" 작업 카드는 리스트에서 제거
                self.remove_task_ui_and_list(task)
                
                for entry in entries:
                    if entry:
                        video_url = entry.get('url') or entry.get('webpage_url')
                        if not video_url:
                            video_id = entry.get('id')
                            if video_id:
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                        if video_url:
                            v_title = entry.get('title') or "대기 중..."
                            self.add_download_task(video_url, task.format_type, title=v_title)
                return
            
            # 단일 동영상 정보 갱신
            task.title = info.get('title', '제목 없음')
            task.duration = info.get('duration')
            task.thumbnail_url = info.get('thumbnail')
            
            # 썸네일 다운로드 스레드 시작
            if task.thumbnail_url:
                threading.Thread(target=self.load_thumbnail_worker, args=(task,), daemon=True).start()
                
            # 상태 변경 후 대기 큐 진입
            task.status = 'queued'
            self.process_queue()
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = f"정보 로드 실패: {str(e)}"
            self.process_queue()

    def load_thumbnail_worker(self, task):
        try:
            req = urllib.request.Request(
                task.thumbnail_url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = response.read()
            img = Image.open(io.BytesIO(data))
            
            # 크기 조정
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.ANTIALIAS
                
            img = img.resize((100, 75), resample_filter)
            task.thumbnail_img = img
        except Exception as e:
            print(f"썸네일 로딩 오류 ({task.title}): {e}")

    def remove_task_ui_and_list(self, task):
        with self.lock:
            if task in self.tasks:
                self.tasks.remove(task)
            if task.card_frame:
                task.card_frame.destroy()
        
        # 목록이 텅 빈 경우 안내 메시지 복구
        self.check_list_empty()

    def check_list_empty(self):
        with self.lock:
            if len(self.tasks) == 0 and self.empty_label is None:
                self.empty_label = ctk.CTkLabel(
                    self.list_frame,
                    text="📥 추가된 다운로드 작업이 없습니다.\n유튜브 URL을 입력하고 다운로드 추가를 눌러주세요.",
                    font=ctk.CTkFont(family="Malgun Gothic", size=14),
                    text_color="#71717A"
                )
                self.empty_label.pack(pady=100)

    def process_queue(self):
        with self.lock:
            # 현재 실행 중인 다운로드 수 카운트
            active_count = sum(1 for t in self.tasks if t.status in ('downloading', 'converting'))
            max_dl = self.settings.get('max_downloads', 2)
            
            if active_count >= max_dl:
                return
                
            # 대기 중인 작업 찾아 다운로드 스레드 구동
            for task in self.tasks:
                if task.status == 'queued':
                    task.status = 'downloading'
                    threading.Thread(target=self.download_worker, args=(task,), daemon=True).start()
                    active_count += 1
                    if active_count >= max_dl:
                        break

    def get_format_options(self, format_type):
        """선택 포맷 및 ffmpeg 소유 여부에 맞춰 yt-dlp 포맷 옵션을 매핑"""
        opts = {}
        
        if format_type == "최고 화질 비디오 (MP4)":
            if self.ffmpeg_available:
                opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                opts['merge_output_format'] = 'mp4'
            else:
                opts['format'] = 'best[ext=mp4]/best'
                
        elif format_type == "1080p 고화질 비디오 (MP4)":
            if self.ffmpeg_available:
                opts['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
                opts['merge_output_format'] = 'mp4'
            else:
                opts['format'] = 'best[height<=720][ext=mp4]/best' # ffmpeg 부재 시 720p 단일파일
                
        elif format_type == "720p 일반 비디오 (MP4)":
            if self.ffmpeg_available:
                opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
                opts['merge_output_format'] = 'mp4'
            else:
                opts['format'] = 'best[height<=720][ext=mp4]/best'
                
        elif format_type == "480p 저화질 비디오 (MP4)":
            if self.ffmpeg_available:
                opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
                opts['merge_output_format'] = 'mp4'
            else:
                opts['format'] = 'best[height<=480][ext=mp4]/best'
                
        elif format_type == "MP3 고음질 오디오 (음악 추출)":
            opts['format'] = 'bestaudio/best'
            if self.ffmpeg_available:
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
                
        elif format_type == "M4A 일반 오디오 (음악 추출)":
            opts['format'] = 'bestaudio[ext=m4a]/best'
            
        return opts

    def download_worker(self, task):
        # 다운로드 파라미터 매핑
        save_dir = self.settings['save_dir']
        format_opts = self.get_format_options(task.format_type)
        
        # 진행 상태 훅 핸들러
        def progress_hook(d):
            if task.cancelled:
                raise DownloadCancelledException("사용자가 다운로드를 취소했습니다.")
                
            if d['status'] == 'downloading':
                # 진행 상황 계산
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                
                if total > 0:
                    task.progress = downloaded / total
                    task.downloaded_bytes_str = f"{self.format_bytes(downloaded)} / {self.format_bytes(total)}"
                else:
                    task.progress = 0.0
                    task.downloaded_bytes_str = f"{self.format_bytes(downloaded)} / 알 수 없음"
                
                speed = d.get('speed')
                task.speed_str = self.format_speed(speed)
                
                eta = d.get('eta')
                if eta is not None:
                    task.eta_str = f"남은 시간: {str(datetime.timedelta(seconds=int(eta)))}"
                else:
                    task.eta_str = "남은 시간: 계산 중..."
                    
            elif d['status'] == 'finished':
                task.status = 'converting'
                task.progress = 1.0
                task.speed_str = ""
                task.eta_str = "파일 병합/포맷 변환 중..."
                task.downloaded_bytes_str = "변환 작업 중"

        ydl_opts = {
            'outtmpl': os.path.join(save_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'windowsfilenames': True,  # 윈도우 특수문자 치환 활성화
            **format_opts
        }
        
        # 로컬 ffmpeg 폴더 위치 지정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(os.path.join(script_dir, 'ffmpeg.exe')):
            ydl_opts['ffmpeg_location'] = script_dir
        elif os.path.exists(os.path.join(os.getcwd(), 'ffmpeg.exe')):
            ydl_opts['ffmpeg_location'] = os.getcwd()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([task.url])
            
            if task.cancelled:
                task.status = 'cancelled'
            else:
                task.status = 'completed'
                task.progress = 1.0
                task.speed_str = ""
                task.eta_str = ""
                task.downloaded_bytes_str = "다운로드 완료"
                
        except DownloadCancelledException:
            task.status = 'cancelled'
            self.clean_partial_files(task, save_dir)
        except Exception as e:
            if task.cancelled:
                task.status = 'cancelled'
                self.clean_partial_files(task, save_dir)
            else:
                task.status = 'failed'
                task.error_message = str(e)
                print(f"다운로드 에러 ({task.title}): {e}")
        finally:
            self.process_queue()

    def clean_partial_files(self, task, save_dir):
        """취소 시 임시 파트 파일들을 청소"""
        try:
            # yt-dlp의 임시 파트 파일이나 원본 파일이 있다면 검색하여 삭제 시도
            if not task.title:
                return
            # 제목에 포함된 특수문자가 윈도우 파일명에서는 치환될 수 있으므로
            # 완벽한 1:1 일치가 아닐 수 있으나 기본적인 청소 시도
            for file in os.listdir(save_dir):
                if file.startswith(task.title[:15]) and (file.endswith('.part') or file.endswith('.ytdl')):
                    filepath = os.path.join(save_dir, file)
                    if os.path.exists(filepath):
                        os.remove(filepath)
        except Exception as e:
            print(f"임시 파일 정리 중 에러: {e}")

    def format_bytes(self, size):
        if size is None:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def format_speed(self, speed):
        if speed is None:
            return "0 B/s"
        return f"{self.format_bytes(speed)}/s"

    # ----------------------------------------------------
    # UI 생성 및 주기적 갱신
    # ----------------------------------------------------
    def create_task_card(self, task):
        # 개별 작업 카드를 위한 프레임 생성
        card = ctk.CTkFrame(self.list_frame, height=95, corner_radius=8, fg_color="#1E1E2E")
        card.pack(fill="x", padx=5, pady=5)
        card.grid_columnconfigure(1, weight=1)
        
        # 썸네일용 라벨 (초기 흑색 박스 설정)
        thumb_label = ctk.CTkLabel(card, text="🖼️ 로딩 중", width=100, height=75, fg_color="#161622", corner_radius=4)
        thumb_label.grid(row=0, column=0, padx=10, pady=10, rowspan=2, sticky="nsew")
        
        # 텍스트 정보 영역 프레임
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=5, pady=(8, 0), sticky="nsew")
        info_frame.grid_columnconfigure(0, weight=1)
        
        # 영상 제목
        title_lbl = ctk.CTkLabel(
            info_frame, 
            text=task.title,
            font=ctk.CTkFont(family="Malgun Gothic", size=12, weight="bold"),
            anchor="w",
            text_color="#E1E1E6"
        )
        title_lbl.grid(row=0, column=0, sticky="w")
        
        # 다운로드 정보 및 상태 표시줄
        status_lbl = ctk.CTkLabel(
            info_frame, 
            text="🔄 준비 중...", 
            font=ctk.CTkFont(family="Malgun Gothic", size=10),
            text_color="#94A3B8"
        )
        status_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))
        
        # 프로그레스바
        progress_bar = ctk.CTkProgressBar(card, height=6, progress_color="#7F5AF0", fg_color="#3F3F46")
        progress_bar.grid(row=1, column=1, padx=5, pady=(2, 10), sticky="ew")
        progress_bar.set(0.0)
        
        # 취소/삭제 액션 버튼
        action_btn = ctk.CTkButton(
            card,
            text="❌ 취소",
            width=65,
            height=28,
            font=ctk.CTkFont(family="Malgun Gothic", size=10, weight="bold"),
            fg_color="#EF4444",
            hover_color="#DC2626",
            cursor="hand2",
            command=lambda: self.on_task_action_click(task)
        )
        action_btn.grid(row=0, column=2, rowspan=2, padx=15, pady=10)
        
        # 객체 내 참조 저장
        task.card_frame = card
        task.thumbnail_label = thumb_label
        task.title_label = title_lbl
        task.status_label = status_lbl
        task.progress_bar = progress_bar
        task.action_button = action_btn

    def on_task_action_click(self, task):
        if task.status in ('fetching', 'queued', 'downloading', 'converting'):
            # 다운로드 취소
            task.cancelled = True
            task.status = 'cancelled'
            task.action_button.configure(text="삭제", fg_color="#EF4444", hover_color="#DC2626")
        else:
            # 리스트와 UI에서 완전히 삭제
            self.remove_task_ui_and_list(task)

    def update_ui_loop(self):
        if not self.running:
            return
            
        with self.lock:
            for task in list(self.tasks):
                # UI 카드가 아직 없으면 생성
                if task.card_frame is None:
                    self.create_task_card(task)
                    continue
                
                # 제목 갱신
                # 최대 길이를 초과하는 경우 말줄임표 처리
                display_title = task.title
                if len(display_title) > 60:
                    display_title = display_title[:57] + "..."
                task.title_label.configure(text=display_title)
                
                # 상태 및 바인딩 데이터 업데이트
                progress_val = 0.0
                btn_txt = "❌ 취소"
                btn_color = "#EF4444"
                btn_hover = "#DC2626"
                
                if task.status == 'fetching':
                    status_text = "🔄 영상 정보를 분석하는 중..."
                    task.progress_bar.configure(progress_color="#7F5AF0")
                elif task.status == 'queued':
                    status_text = "⏳ 대기 중 (다운로드 큐 대기)"
                    task.progress_bar.configure(progress_color="#7F5AF0")
                elif task.status == 'downloading':
                    status_text = f"📥 다운로드 중: {task.downloaded_bytes_str} ({task.speed_str}) | {task.eta_str}"
                    progress_val = task.progress
                    task.progress_bar.configure(progress_color="#10B981") # 녹색
                elif task.status == 'converting':
                    status_text = "⚙️ 파일 후처리 및 변합 작업 중 (잠시만 기다려주세요)..."
                    progress_val = 1.0
                    task.progress_bar.configure(progress_color="#3B82F6") # 파랑
                elif task.status == 'completed':
                    status_text = "✅ 다운로드 완료"
                    progress_val = 1.0
                    task.progress_bar.configure(progress_color="#10B981")
                    btn_txt = "🗑️ 삭제"
                elif task.status == 'failed':
                    # 에러 메시지 축약
                    err_msg = task.error_message
                    if "extractor" in err_msg.lower():
                        err_msg = "유효하지 않은 URL이거나 접근 제한된 영상입니다."
                    else:
                        err_msg = err_msg.split('\n')[0][:50]
                    status_text = f"❌ 다운로드 실패: {err_msg}"
                    progress_val = 0.0
                    task.progress_bar.configure(progress_color="#EF4444")
                    btn_txt = "🗑️ 삭제"
                elif task.status == 'cancelled':
                    status_text = "🛑 작업이 취소되었습니다."
                    progress_val = 0.0
                    task.progress_bar.configure(progress_color="#9CA3AF") # 회색
                    btn_txt = "🗑️ 삭제"
                
                task.status_label.configure(text=status_text)
                task.progress_bar.set(progress_val)
                task.action_button.configure(text=btn_txt, fg_color=btn_color, hover_color=btn_hover)
                
                # 다운로드 완료된 썸네일 적용
                if task.thumbnail_img and not task.thumbnail_displayed:
                    try:
                        ctk_img = ctk.CTkImage(
                            light_image=task.thumbnail_img, 
                            dark_image=task.thumbnail_img, 
                            size=(100, 75)
                        )
                        task.thumbnail_label.configure(image=ctk_img, text="")
                        task.thumbnail_displayed = True
                    except Exception as img_err:
                        print(f"이미지 업데이트 에러: {img_err}")
                        
        self.root.after(100, self.update_ui_loop)

    # ----------------------------------------------------
    # 백그라운드 클립보드 모니터링
    # ----------------------------------------------------
    def clipboard_monitor_worker(self):
        last_clipboard = ""
        while self.running:
            if self.settings.get('clipboard_monitor', False):
                try:
                    text = self.root.clipboard_get().strip()
                    if text and text != last_clipboard:
                        last_clipboard = text
                        # 유튜브 링크 규격 체크
                        if "youtube.com" in text or "youtu.be" in text:
                            # UI 입력란 갱신
                            self.root.after(0, self.update_url_input, text)
                except Exception:
                    pass
            time.sleep(1.0)

    def update_url_input(self, text):
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, text)
        # 사용자 피드백
        self.folder_label.configure(text_color="#10B981")
        self.folder_label.configure(text=f"클립보드 감지 링크 자동 입력됨: {text[:60]}...")
        # 3초 후에 라벨 복원
        self.root.after(3000, self.reset_folder_label)

    def reset_folder_label(self):
        self.folder_label.configure(text_color="#94A3B8")
        self.folder_label.configure(text=f"저장 폴더: {self.settings['save_dir']}")

    def on_closing(self):
        self.running = False
        # 현재 활성 작업들 강제 취소 플래그 설정
        with self.lock:
            for task in self.tasks:
                if task.status in ('fetching', 'queued', 'downloading', 'converting'):
                    task.cancelled = True
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()

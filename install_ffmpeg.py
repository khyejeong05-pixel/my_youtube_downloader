import os
import urllib.request
import zipfile
import shutil

url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
zip_path = "ffmpeg.zip"

print("FFmpeg 다운로드를 시작합니다 (약 40~50MB)...")
try:
    # User-Agent 설정하여 403 차단 방지
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
    print("다운로드 완료. 압축 해제 중...")
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        extracted = False
        for file_info in zip_ref.infolist():
            # zip 파일 내의 ffmpeg.exe 및 ffprobe.exe 찾기
            if file_info.filename.endswith('ffmpeg.exe') or file_info.filename.endswith('ffprobe.exe'):
                filename = os.path.basename(file_info.filename)
                with zip_ref.open(file_info) as source, open(filename, 'wb') as target:
                    shutil.copyfileobj(source, target)
                print(f"성공: {filename} 파일 추출 완료")
                extracted = True
                
        if not extracted:
            print("오류: zip 파일 내에서 ffmpeg.exe/ffprobe.exe를 찾을 수 없습니다.")
            
    # 임시 zip 파일 삭제
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    print("\n🎉 FFmpeg 설치 완료! 프로그램 폴더에 필요한 실행 파일이 배치되었습니다.")
    print("유튜브 다운로더 프로그램을 재실행하시면 1080p 이상 고화질 비디오 병합 및 MP3 오디오 변환 기능이 활성화됩니다.")

except Exception as e:
    print(f"설치 중 오류 발생: {e}")
    if os.path.exists(zip_path):
        os.remove(zip_path)

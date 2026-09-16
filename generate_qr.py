import os
import sys
import socket
import qrcode

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_qr(target_url=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    lan_ip = get_lan_ip()
    if not target_url:
        target_url = f"http://{lan_ip}:8501"

    print("=" * 60)
    print(f"  📶 本機區域網路 IPv4 位址: {lan_ip}")
    print(f"  📱 同 Wi-Fi 手機直連存取網址: {target_url}")
    print("=" * 60)
    print("\n【手機同 Wi-Fi 掃描專用 QR Code】\n")

    # 1. 終端機 ASCII 字符 QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    try:
        qr.print_ascii(invert=True)
    except Exception:
        qr.print_tty()

    print("\n" + "=" * 60 + "\n")

    # 2. 產出實體 PNG 圖片
    qr_img = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr_img.add_data(target_url)
    qr_img.make(fit=True)
    img = qr_img.make_image(fill_color="#0f172a", back_color="#ffffff")

    # 存檔至專案與 Artifacts 目錄
    local_png = os.path.abspath("mobile_access_qr.png")
    img.save(local_png)

    # 同時保留 lan_access_qr.png 相容性
    img.save(os.path.abspath("lan_access_qr.png"))

    artifact_dir = r"C:\Users\poipi\.gemini\antigravity-ide\brain\68026fc2-284c-47d7-b0f4-44d608076af9"
    artifact_png = os.path.join(artifact_dir, "mobile_access_qr.png")
    os.makedirs(artifact_dir, exist_ok=True)
    img.save(artifact_png)
    img.save(os.path.join(artifact_dir, "lan_access_qr.png"))

    # 驗證實體檔案存在性 (遵從 .antigravityrules Mandatory Workflow)
    assert os.path.exists(local_png), f"檔案未建立: {local_png}"
    assert os.path.exists(artifact_png), f"Artifact 檔案未建立: {artifact_png}"

    print(f"✅ 實體 QR Code 圖片已更新: {local_png}")
    print(f"✅ Artifact 實體圖檔已同步: {artifact_png}")

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    generate_qr(url_arg)

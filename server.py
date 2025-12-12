import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
import csv
from datetime import datetime

app = Flask(__name__)
CORS(app)


MY_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCm_lnruxp2gU69MmSamPhuhzwkXPPWKQI")
genai.configure(api_key=MY_API_KEY)

MODEL_LIST = [
    'models/gemini-2.5-flash',
    'models/gemini-2.5-flash-lite',
    'models/gemma-3-27b-it'
]


HISTORY_FILE = 'lich_su_chat_khach_hang.csv'



def khoi_tao_file_lich_su():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['UserID', 'Time', 'Role', 'Content'])


def luu_tin_nhan_vao_csv(user_id, role, content):
    khoi_tao_file_lich_su()
    with open(HISTORY_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), role, content])


def lay_lich_su_tu_csv(user_id):
    if not os.path.exists(HISTORY_FILE):
        return ""

    try:

        df = pd.read_csv(HISTORY_FILE)

        df['UserID'] = df['UserID'].astype(str)
        user_history = df[df['UserID'] == str(user_id)]


        recent_history = user_history.tail(10)

        history_text = ""
        for _, row in recent_history.iterrows():
            role_name = "Khách hàng" if row['Role'] == 'user' else "Nhân viên tư vấn"
            history_text += f"{role_name}: {row['Content']}\n"

        return history_text
    except Exception as e:
        print(f"Lỗi đọc lịch sử: {e}")
        return ""


FILE_CSV = 'danh_sach_san_pham.csv'
df_products = pd.DataFrame()
kho_hang_text = ""

if os.path.exists(FILE_CSV):
    try:
        df_products = pd.read_csv(FILE_CSV)
        if 'Link' not in df_products.columns: df_products['Link'] = ''
        df_products.fillna('', inplace=True)

        for _, row in df_products.iterrows():
            try:
                gia = f"{int(row['Price']):,}"
            except:
                gia = row['Price']
            link_info = f"| Link: {row['Link']}" if row['Link'] else ""
            kho_hang_text += f"- {row['Name']} | Giá: {gia} VNĐ {link_info} | {row['Description']}\n"
    except Exception as e:
        print(f"❌ Lỗi CSV Sản phẩm: {e}")


def tim_kiem_thu_cong(tu_khoa):
    if df_products.empty: return ""
    tu_khoa = tu_khoa.lower()
    mask = (df_products['Name'].str.lower().str.contains(tu_khoa, na=False) |
            df_products['Description'].str.lower().str.contains(tu_khoa, na=False))
    ket_qua = df_products[mask].head(5)
    ds = []
    for _, row in ket_qua.iterrows():
        try:
            gia = f"{int(row['Price']):,}"
        except:
            gia = row['Price']
        link_str = f"- Link: {row['Link']}" if row['Link'] else ""
        ds.append(f"- {row['Name']} (Giá: {gia} VNĐ) {link_str}")
    return "\n".join(ds)


def goi_ai_thong_minh(prompt):
    loi_cuoi = ""
    for model_name in MODEL_LIST:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            loi_cuoi = str(e)
            continue
    raise Exception(loi_cuoi)



@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    msg = data.get('message', '')

    user_id = data.get('user_id')
    if not user_id or user_id == "guest_unknown":
        user_id = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not msg: return jsonify({"reply": "..."})


    history_text_block = lay_lich_su_tu_csv(user_id)

    system_prompt = f"""
        Bạn là trí tuệ nhân tạo tư vấn của website Nội Thất Gỗ (NOITHATGO.VN).

        1. THÔNG TIN CỬA HÀNG:
        - Hotline: 0968 012 687 | Email: mviet1304@gmail.vn
        - Showroom: 1234 đường Láng, Cầu Giấy, Hà Nội
        - Giờ làm việc: 8h00 - 21h00

        2. CHÍNH SÁCH:
        - Vận chuyển: Miễn phí nội thành HN (trong ngày). Ngoại thành/Tỉnh 2-3 ngày.
        - Bảo hành: 12 tháng, bảo trì trọn đời.

        3. DANH SÁCH SẢN PHẨM TRONG KHO:
        --------------------------------------
        {kho_hang_text}
        --------------------------------------

        4. LỊCH SỬ TRÒ CHUYỆN CŨ (HÃY ĐỌC ĐỂ GIỮ MẠCH LOGIC):
        --------------------------------------
        {history_text_block}
        --------------------------------------

        NHIỆM VỤ:
        - Trả lời ngắn gọn đúng trọng tâm câu hỏi.
        - Dựa vào 'LỊCH SỬ TRÒ CHUYỆN', hãy trả lời tiếp nối mạch câu chuyện.
        - Nếu lịch sử trống (lần đầu chat), hãy chào hỏi. Nếu đã chat rồi, KHÔNG chào lại.
        - Ví dụ: Khách hỏi "Cái đó giá bao nhiêu", hãy xem lịch sử để biết "Cái đó" là gì.
        - Xưng "em", gọi khách là "anh/chị".
        - Tuyệt đối trung thực với dữ liệu kho hàng.
        """

    try:
        full_prompt = f"{system_prompt}\n\nKhách hàng (mới nhất): {msg}\nNhân viên tư vấn:"
        reply = goi_ai_thong_minh(full_prompt)


        luu_tin_nhan_vao_csv(user_id, "user", msg)
        luu_tin_nhan_vao_csv(user_id, "bot", reply)
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"❌ AI SẬP: {e}")
        tu_khoa = ""
        for k in ["sofa", "bàn", "ghế", "tủ", "giường", "kệ"]:
            if k in msg.lower(): tu_khoa = k; break

        fallback = "Hệ thống AI đang quá tải, em xin phép trả lời mặc định ạ.\n"
        if tu_khoa:
            kq = tim_kiem_thu_cong(tu_khoa)
            if kq:
                fallback += f"Em tìm thấy các mẫu '{tu_khoa}' này:\n{kq}"
            else:
                fallback += f"Em chưa thấy mẫu '{tu_khoa}' nào."
        else:
            fallback += "Anh/chị vui lòng gọi Hotline 0968.012.687 để được hỗ trợ ạ."

        return jsonify({"reply": fallback})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
